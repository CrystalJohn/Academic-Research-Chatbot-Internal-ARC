"""
Syllabus File Processor

Processes FPT University syllabus markdown files with intelligent chunking.
Each session and assessment becomes a separate chunk with rich metadata.

This enables RAG to answer questions like:
- "What topics are covered in week 5?"
- "Which sessions cover CLO2?"
- "What is the weight of the final exam?"

SKIP SECTIONS (not embedded to vector DB):
- Constructive Questions (168+ questions, too noisy for RAG)
"""

import re
import logging
from typing import List, Optional
from .base import BaseFileProcessor, ProcessedContent

logger = logging.getLogger(__name__)

# Sections to skip during embedding (too noisy, low value for RAG)
SKIP_SECTIONS = [
    "constructive question",
    "constructive questions",
    "cq(",  # Pattern like "168 Constructive question(s)"
]


class SyllabusProcessor(BaseFileProcessor):
    """
    Processor for FPT University syllabus markdown files.
    
    Creates semantic chunks:
    - Course overview chunk
    - One chunk per session (with session number, topic, CLOs, materials)
    - One chunk per assessment (with category, weight, CLOs)
    
    This enables accurate RAG responses for session/assessment queries.
    """
    
    def get_supported_extensions(self) -> List[str]:
        return [".md", ".markdown"]
    
    def process(self, content: bytes, filename: str) -> ProcessedContent:
        """
        Process syllabus markdown with semantic chunking.
        
        Args:
            content: Raw markdown bytes
            filename: Original filename
            
        Returns:
            ProcessedContent with semantic chunks as pages
            
        Note:
            Constructive Questions section is automatically skipped
            as it's too noisy for RAG (168+ questions, low value).
        """
        # Decode content
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
        
        original_length = len(text)
        
        # Remove sections that should be skipped (Constructive Questions)
        text_for_parsing = self._remove_skipped_sections(text)
        
        skipped_chars = original_length - len(text_for_parsing)
        if skipped_chars > 0:
            logger.info(f"Removed {skipped_chars} chars from skipped sections")
        
        # Extract subject code and name
        subject_code, subject_name = self._extract_subject_info(text)
        
        # Parse sessions and assessments (from cleaned text)
        sessions = self._parse_sessions(text_for_parsing)
        assessments = self._parse_assessments(text_for_parsing)
        
        # Parse CLOs
        clos = self._parse_clos(text_for_parsing)
        
        # Parse Materials
        materials = self._parse_materials(text_for_parsing)
        
        # Create semantic chunks
        chunks = []
        
        # Chunk 1: Course Overview
        overview_chunk = self._create_overview_chunk(
            subject_code, subject_name, len(sessions), len(assessments), text
        )
        chunks.append(overview_chunk)
        
        # Chunks for CLOs (grouped into one chunk for efficiency)
        if clos:
            clo_chunk = self._create_clos_chunk(subject_code, clos)
            chunks.append(clo_chunk)
        
        # Chunks for each session
        for session in sessions:
            chunk = self._create_session_chunk(subject_code, session)
            chunks.append(chunk)
        
        # Chunks for each assessment
        for assessment in assessments:
            chunk = self._create_assessment_chunk(subject_code, assessment)
            chunks.append(chunk)
        
        # Chunks for materials (grouped into one chunk)
        if materials:
            materials_chunk = self._create_materials_chunk(subject_code, materials)
            chunks.append(materials_chunk)
        
        logger.info(f"Created {len(chunks)} chunks for {subject_code}: "
                   f"1 overview, {len(clos)} CLOs, {len(sessions)} sessions, "
                   f"{len(assessments)} assessments, {len(materials)} materials")
        
        return ProcessedContent(
            text=text_for_parsing,  # Use cleaned text (without skipped sections)
            metadata={
                "filename": filename,
                "file_type": ".md",
                "processor": "syllabus",
                "subject_code": subject_code,
                "subject_name": subject_name,
                "session_count": len(sessions),
                "assessment_count": len(assessments),
                "clo_count": len(clos),
                "material_count": len(materials),
                "chunk_count": len(chunks),
                "skipped_chars": skipped_chars,
                "skipped_sections": ["Constructive Questions"] if skipped_chars > 0 else [],
            },
            pages=chunks
        )
    
    def _extract_subject_info(self, text: str) -> tuple:
        """Extract subject code and name from markdown."""
        # Pattern 1: Table format | Subject Code: | MAE101 |
        table_code_match = re.search(r'\|\s*Subject\s*Code:\s*\|\s*([A-Z]{3}\d{3})\s*\|', text, re.IGNORECASE)
        if table_code_match:
            subject_code = table_code_match.group(1).upper()
            
            # Try to find syllabus name from table
            table_name_match = re.search(r'\|\s*Syllabus\s*Name:\s*\|\s*([^|]+)\s*\|', text, re.IGNORECASE)
            if table_name_match:
                return subject_code, table_name_match.group(1).strip()
            return subject_code, "Unknown Course"
        
        # Pattern 2: # Course Name (ABC123)
        pattern = r'#\s+(.+?)\s*\(([A-Z]{3}\d{3})\)'
        match = re.search(pattern, text)
        
        if match:
            return match.group(2), match.group(1).strip()
        
        # Try to find just subject code
        code_match = re.search(r'\b([A-Z]{3}\d{3})\b', text)
        if code_match:
            return code_match.group(1), "Unknown Course"
        
        return "UNKNOWN", "Unknown Course"
    
    def _should_skip_section(self, section_text: str) -> bool:
        """Check if a section should be skipped (not embedded)."""
        section_lower = section_text.lower()
        for skip_pattern in SKIP_SECTIONS:
            if skip_pattern in section_lower:
                return True
        return False
    
    def _remove_skipped_sections(self, text: str) -> str:
        """
        Remove sections that should be skipped from text before processing.
        
        This removes Constructive Questions section which is typically:
        - Very large (168+ questions)
        - Low value for RAG (questions, not answers)
        - Noisy for semantic search
        """
        # Pattern to match "X Constructive question(s)" header and everything after
        # until next major section or end of file
        patterns = [
            # Match "168 Constructive question(s)" and table that follows
            r'\d+\s+Constructive\s+question\(s\).*?(?=\n\d+\s+\w+\(s\)|\n##|\Z)',
            # Match "## Constructive Questions" section
            r'##\s*Constructive\s+Questions.*?(?=\n##|\Z)',
        ]
        
        cleaned_text = text
        for pattern in patterns:
            match = re.search(pattern, cleaned_text, re.IGNORECASE | re.DOTALL)
            if match:
                skipped_length = len(match.group(0))
                logger.info(f"Skipping Constructive Questions section ({skipped_length} chars)")
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        return cleaned_text
    
    def _parse_sessions(self, text: str) -> List[dict]:
        """Parse session table from markdown."""
        sessions = []
        
        # Find session table - handle multiline rows
        lines = text.split('\n')
        in_session_table = False
        current_row = ""
        header_cols = []
        
        for line in lines:
            # Detect session table header (with or without spaces)
            if re.search(r'\|\s*Session\s*\|', line, re.IGNORECASE):
                in_session_table = True
                # Parse header columns
                header_cols = [h.strip().lower() for h in line.split('|')]
                header_cols = [h for h in header_cols if h]
                continue
            
            # Skip separator line
            if in_session_table and re.match(r'\|[-:\s|]+\|', line):
                continue
            
            # Detect end of session table (assessment table starts or Constructive Questions)
            if in_session_table and (
                re.search(r'\|\s*Category\s*\|', line, re.IGNORECASE) or
                re.search(r'Constructive question', line, re.IGNORECASE)
            ):
                # Process last row if any
                if current_row:
                    session = self._parse_session_row(current_row, header_cols)
                    if session:
                        sessions.append(session)
                break
            
            # Handle rows
            if in_session_table:
                if line.startswith('|') and re.match(r'\|\s*\d+\s*\|', line):
                    # New row starts with session number
                    # Process previous row first
                    if current_row:
                        session = self._parse_session_row(current_row, header_cols)
                        if session:
                            sessions.append(session)
                    current_row = line
                elif line.startswith('|') and current_row:
                    # Continuation of current row
                    current_row += " " + line.strip()
                elif not line.strip() and current_row:
                    # Empty line - process current row
                    session = self._parse_session_row(current_row, header_cols)
                    if session:
                        sessions.append(session)
                    current_row = ""
                elif line.strip() and not line.startswith('|') and not line.startswith('#') and current_row:
                    # Text continuation
                    current_row += " " + line.strip()
        
        # Process last row
        if current_row:
            session = self._parse_session_row(current_row, header_cols)
            if session:
                sessions.append(session)
        
        return sessions
    
    def _parse_session_row(self, line: str, header_cols: List[str] = None) -> Optional[dict]:
        """Parse a single session row."""
        # Split by | and clean
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p]  # Remove empty
        
        if len(parts) < 2:
            return None
        
        try:
            session_num = int(parts[0])
        except (ValueError, IndexError):
            return None
        
        # Build column mapping from header
        col_map = {}
        if header_cols:
            for i, col in enumerate(header_cols):
                if 'session' in col:
                    col_map['session'] = i
                elif 'topic' in col:
                    col_map['topic'] = i
                elif 'learning' in col or 'type' in col or 'mode' in col:
                    col_map['mode'] = i
                elif col in ('lo', 'clo') or 'lo' in col:
                    col_map['clo'] = i
                elif 'itu' in col:
                    col_map['itu'] = i
                elif 'material' in col:
                    col_map['materials'] = i
                elif 'task' in col or 'student' in col:
                    col_map['tasks'] = i
        
        # Default column positions if no header mapping
        if not col_map:
            col_map = {'session': 0, 'topic': 1, 'mode': 2, 'clo': 3, 'itu': 4, 'materials': 5, 'tasks': 7}
        
        # Extract fields
        topic = parts[col_map.get('topic', 1)] if col_map.get('topic', 1) < len(parts) else ""
        mode = parts[col_map.get('mode', 2)] if col_map.get('mode', 2) < len(parts) else ""
        
        # Extract CLOs/LOs
        clos = []
        clo_idx = col_map.get('clo', 3)
        if clo_idx < len(parts):
            clo_text = parts[clo_idx]
            # Match both CLO and LO patterns
            clo_matches = re.findall(r'(?:CLO|LO)\d+', clo_text, re.IGNORECASE)
            clos = [c.upper().replace('LO', 'CLO') for c in clo_matches]
        
        # Extract ITU (session type)
        itu = parts[col_map.get('itu', 4)] if col_map.get('itu', 4) < len(parts) else ""
        
        # Extract materials
        materials = parts[col_map.get('materials', 5)] if col_map.get('materials', 5) < len(parts) else ""
        
        # Extract tasks/activities - try multiple columns
        tasks = ""
        tasks_idx = col_map.get('tasks', 7)
        if tasks_idx < len(parts):
            tasks = parts[tasks_idx]
        elif len(parts) > 7:
            tasks = parts[7]
        
        return {
            "session_number": session_num,
            "topic": topic.replace('\n', ' ').strip(),
            "mode": mode,
            "clos": clos,
            "itu": itu,
            "materials": materials,
            "tasks": tasks,
        }
    
    def _parse_assessments(self, text: str) -> List[dict]:
        """Parse assessment table from markdown."""
        assessments = []
        
        lines = text.split('\n')
        in_assessment_table = False
        current_row = ""
        
        for line in lines:
            # Detect assessment table header
            if re.search(r'\|\s*Category\s*\|', line, re.IGNORECASE):
                in_assessment_table = True
                continue
            
            # Skip separator line
            if in_assessment_table and re.match(r'\|[-:\s|]+\|', line):
                continue
            
            if in_assessment_table:
                # New row starts with | and has a category name (not continuation)
                if line.startswith('|') and not line.startswith('|---'):
                    # Check if this is a new assessment row (starts with category name)
                    parts = [p.strip() for p in line.split('|')]
                    parts = [p for p in parts if p]
                    
                    # If first part looks like a category (not empty, not just numbers)
                    if parts and parts[0] and not parts[0].isdigit() and parts[0].lower() != 'category':
                        # Process previous row first
                        if current_row:
                            assessment = self._parse_assessment_row(current_row)
                            if assessment:
                                assessments.append(assessment)
                        current_row = line
                    else:
                        # Continuation of current row
                        current_row += " " + line
                elif line.strip() and not line.startswith('#') and not line.startswith('|'):
                    # Text continuation (wrapped content)
                    current_row += " " + line.strip()
                elif not line.strip() and current_row:
                    # Empty line - might end the row, but continue looking
                    pass
                elif line.startswith('#'):
                    # New section - end of table
                    break
        
        # Process last row
        if current_row:
            assessment = self._parse_assessment_row(current_row)
            if assessment:
                assessments.append(assessment)
        
        return assessments
    
    def _parse_assessment_row(self, line: str) -> Optional[dict]:
        """Parse a single assessment row."""
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p]
        
        if len(parts) < 4:
            return None
        
        category = parts[0] if len(parts) > 0 else ""
        assessment_type = parts[1] if len(parts) > 1 else ""
        
        # Skip header row
        if category.lower() == 'category':
            return None
        
        # Weight is in column 4 (index 3) - format: "25.0%" or "25%"
        weight = 0.0
        if len(parts) > 3:
            weight_str = parts[3]
            weight_match = re.search(r'(\d+(?:\.\d+)?)\s*%', weight_str)
            if weight_match:
                weight = float(weight_match.group(1))
        
        # Extract CLOs from CLO column (index 6)
        clos = []
        if len(parts) > 6:
            clo_text = parts[6]
            if 'all' in clo_text.lower():
                clos = ['All CLOs']
            else:
                clo_matches = re.findall(r'CLO\d+', clo_text, re.IGNORECASE)
                clos = [c.upper() for c in clo_matches]
        
        # Extract duration from column 5
        duration = parts[5] if len(parts) > 5 else ""
        
        return {
            "category": category,
            "type": assessment_type,
            "weight": weight,
            "clos": list(set(clos)) if clos else ['All CLOs'],
            "duration": duration,
        }
    
    def _parse_clos(self, text: str) -> List[dict]:
        """Parse CLO/LO table from markdown."""
        clos = []
        
        lines = text.split('\n')
        in_clo_table = False
        
        for line in lines:
            # Detect CLO table header
            if re.search(r'\|\s*CLO\s*Name\s*\|', line, re.IGNORECASE) or \
               re.search(r'\|\s*LO\s*Name\s*\|', line, re.IGNORECASE):
                in_clo_table = True
                continue
            
            # Skip separator line
            if in_clo_table and re.match(r'\|[-:\s|]+\|', line):
                continue
            
            # Detect end of CLO table
            if in_clo_table and (
                re.search(r'\|\s*Session\s*\|', line, re.IGNORECASE) or
                re.search(r'\d+\s+sessions?', line, re.IGNORECASE) or
                line.startswith('#')
            ):
                break
            
            if in_clo_table and line.startswith('|'):
                clo = self._parse_clo_row(line)
                if clo:
                    clos.append(clo)
        
        return clos
    
    def _parse_clo_row(self, line: str) -> Optional[dict]:
        """Parse a single CLO row."""
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p]
        
        if len(parts) < 2:
            return None
        
        # Skip header row
        if parts[0].lower() in ['clo name', 'lo name', 'name']:
            return None
        
        clo_id = parts[0] if len(parts) > 0 else ""
        clo_name = parts[1] if len(parts) > 1 else ""
        clo_details = parts[2] if len(parts) > 2 else ""
        
        # Try to extract CLO number
        clo_num_match = re.search(r'(\d+)', clo_id)
        if clo_num_match:
            clo_id = f"CLO{clo_num_match.group(1)}"
        
        return {
            "clo_id": clo_id,
            "name": clo_name,
            "details": clo_details,
        }
    
    def _parse_materials(self, text: str) -> List[dict]:
        """Parse materials table from markdown."""
        materials = []
        
        lines = text.split('\n')
        in_materials_table = False
        
        for line in lines:
            # Detect materials table header
            if re.search(r'\|\s*MaterialDescription\s*\|', line, re.IGNORECASE) or \
               re.search(r'\|\s*Material\s*Description\s*\|', line, re.IGNORECASE):
                in_materials_table = True
                continue
            
            # Skip separator line
            if in_materials_table and re.match(r'\|[-:\s|]+\|', line):
                continue
            
            # Detect end of materials table
            if in_materials_table and (
                re.search(r'\d+\s+LO\(s\)', line, re.IGNORECASE) or
                re.search(r'\|\s*CLO\s*Name\s*\|', line, re.IGNORECASE) or
                line.startswith('#')
            ):
                break
            
            if in_materials_table and line.startswith('|'):
                material = self._parse_material_row(line)
                if material:
                    materials.append(material)
        
        return materials
    
    def _parse_material_row(self, line: str) -> Optional[dict]:
        """Parse a single material row."""
        parts = [p.strip() for p in line.split('|')]
        parts = [p for p in parts if p]
        
        if len(parts) < 1:
            return None
        
        # Skip header row
        if parts[0].lower() in ['materialdescription', 'material description']:
            return None
        
        title = parts[0] if len(parts) > 0 else ""
        author = parts[1] if len(parts) > 1 else ""
        publisher = parts[2] if len(parts) > 2 else ""
        isbn = parts[5] if len(parts) > 5 else ""
        note = parts[9] if len(parts) > 9 else ""
        
        # Skip empty materials
        if not title or title.isspace():
            return None
        
        return {
            "title": title,
            "author": author,
            "publisher": publisher,
            "isbn": isbn,
            "note": note,
        }
    
    def _create_overview_chunk(
        self, 
        subject_code: str, 
        subject_name: str, 
        session_count: int,
        assessment_count: int,
        full_text: str
    ) -> dict:
        """Create course overview chunk."""
        # Extract any additional info from frontmatter
        source_url = ""
        source_match = re.search(r'source:\s*(.+)', full_text)
        if source_match:
            source_url = source_match.group(1).strip()
        
        content = f"""Course Overview: {subject_name} ({subject_code})

This syllabus contains {session_count} sessions and {assessment_count} assessments.

Subject Code: {subject_code}
Course Name: {subject_name}
Total Sessions: {session_count}
Total Assessments: {assessment_count}
Source: {source_url if source_url else 'FPT University Learning Management System'}

This is the official syllabus for {subject_code} at FPT University."""
        
        return {
            "index": 0,
            "title": f"Course Overview - {subject_code}",
            "content": content,
            "chunk_type": "overview",
            "subject_code": subject_code,
            "session_number": None,
        }
    
    def _create_session_chunk(self, subject_code: str, session: dict) -> dict:
        """Create a chunk for a single session."""
        session_num = session["session_number"]
        topic = session["topic"]
        mode = session["mode"]
        clos = ", ".join(session["clos"]) if session["clos"] else "Not specified"
        materials = session["materials"]
        tasks = session["tasks"]
        itu = session["itu"]
        
        # Calculate week number (assuming 3 sessions per week)
        week_number = (session_num - 1) // 3 + 1
        
        content = f"""Session {session_num} of {subject_code} (Week {week_number})

Topic: {topic}
Session Number: {session_num}
Week: {week_number}
Mode: {mode}
Session Type: {itu}
Learning Outcomes (CLOs): {clos}
Materials: {materials}
Student Tasks: {tasks}

In session {session_num} (week {week_number}) of {subject_code}, students will learn about {topic}. 
This session is conducted {mode} and covers {clos}.
Students should prepare: {materials}."""
        
        return {
            "index": session_num,
            "title": f"Session {session_num} - {topic[:50]}",
            "content": content,
            "chunk_type": "session",
            "subject_code": subject_code,
            "session_number": session_num,
            "week_number": week_number,
            "topic": topic,
            "mode": mode,
            "clos": session["clos"],
        }
    
    def _create_assessment_chunk(self, subject_code: str, assessment: dict) -> dict:
        """Create a chunk for a single assessment."""
        category = assessment["category"]
        assessment_type = assessment["type"]
        weight = assessment["weight"]
        clos = ", ".join(assessment["clos"]) if assessment["clos"] else "All CLOs"
        duration = assessment["duration"]
        
        content = f"""Assessment: {category} for {subject_code}

Category: {category}
Type: {assessment_type}
Weight: {weight}%
Duration: {duration if duration else 'Not specified'}
Learning Outcomes Assessed: {clos}

The {category} ({assessment_type}) accounts for {weight}% of the total grade in {subject_code}.
This assessment evaluates: {clos}.
{f'Duration: {duration}.' if duration else ''}"""
        
        return {
            "index": 1000 + len(assessment["category"]),  # Assessments after sessions
            "title": f"Assessment - {category}",
            "content": content,
            "chunk_type": "assessment",
            "subject_code": subject_code,
            "session_number": None,
            "category": category,
            "weight": weight,
            "clos": assessment["clos"],
        }
    
    def _create_clos_chunk(self, subject_code: str, clos: List[dict]) -> dict:
        """Create a chunk for all CLOs (grouped for efficiency)."""
        clo_lines = []
        for clo in clos:
            clo_id = clo["clo_id"]
            name = clo["name"]
            details = clo["details"]
            clo_lines.append(f"- {clo_id} ({name}): {details}")
        
        content = f"""Course Learning Outcomes (CLOs) for {subject_code}

This course has {len(clos)} learning outcomes:

{chr(10).join(clo_lines)}

Students completing {subject_code} should achieve all these learning outcomes."""
        
        return {
            "index": 1,  # Right after overview
            "title": f"CLOs - {subject_code}",
            "content": content,
            "chunk_type": "clos",
            "subject_code": subject_code,
            "session_number": None,
            "clo_count": len(clos),
        }
    
    def _create_materials_chunk(self, subject_code: str, materials: List[dict]) -> dict:
        """Create a chunk for all materials (grouped for efficiency)."""
        material_lines = []
        for i, mat in enumerate(materials, 1):
            title = mat["title"]
            author = mat["author"]
            publisher = mat["publisher"]
            isbn = mat["isbn"]
            note = mat["note"]
            
            line = f"{i}. {title}"
            if author:
                line += f" by {author}"
            if publisher:
                line += f" ({publisher})"
            if isbn:
                line += f" ISBN: {isbn}"
            if note:
                line += f" - {note}"
            material_lines.append(line)
        
        content = f"""Learning Materials for {subject_code}

This course uses {len(materials)} materials:

{chr(10).join(material_lines)}

Students should prepare these materials for {subject_code}."""
        
        return {
            "index": 2,  # After CLOs
            "title": f"Materials - {subject_code}",
            "content": content,
            "chunk_type": "materials",
            "subject_code": subject_code,
            "session_number": None,
            "material_count": len(materials),
        }


def is_syllabus_file(filename: str, content: bytes = None) -> bool:
    """
    Detect if a markdown file is a syllabus.
    
    Checks for:
    - Filename contains 'syllabus' or subject code pattern
    - Content has session table
    - Content has assessment table
    - Content has FPT University syllabus metadata table
    """
    filename_lower = filename.lower()
    
    # Check filename
    if 'syllabus' in filename_lower:
        return True
    
    # Check for subject code in filename (e.g., SWD392.md, MAE101.md)
    if re.search(r'[A-Z]{3}\d{3}', filename):
        return True
    
    # Check content if provided
    if content:
        try:
            text = content.decode('utf-8')
        except:
            return False
        
        # Check for FPT syllabus metadata table format
        # | Subject Code: | MAE101 |
        has_subject_code_table = bool(re.search(r'\|\s*Subject\s*Code:\s*\|', text, re.IGNORECASE))
        
        # Check for "# Syllabus Details" header
        has_syllabus_header = bool(re.search(r'#\s*Syllabus\s*Details', text, re.IGNORECASE))
        
        # Check for session table
        has_session_table = bool(re.search(r'\|\s*Session\s*\|', text, re.IGNORECASE))
        
        # Check for assessment table
        has_assessment_table = bool(re.search(r'\|\s*Category\s*\|.*Weight', text, re.IGNORECASE))
        
        # Check for FPT University markers
        has_fpt_marker = 'fpt.edu.vn' in text.lower() or 'fpt university' in text.lower()
        
        # Check for LO/CLO table
        has_lo_table = bool(re.search(r'\d+\s+LO\(s\)', text, re.IGNORECASE))
        
        # New format detection (MAE101 style)
        if has_syllabus_header and has_subject_code_table:
            return True
        
        if has_session_table and has_assessment_table:
            return True
        
        if has_fpt_marker and (has_session_table or has_assessment_table):
            return True
        
        if has_lo_table and has_session_table:
            return True
    
    return False
