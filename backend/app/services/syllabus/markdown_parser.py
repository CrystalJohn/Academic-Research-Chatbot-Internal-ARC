"""
Parse file .md
Simple Markdown Syllabus Parser

Parses markdown files exported from FPT University syllabus system.
Extracts sessions, assessments, CLOs, and materials from markdown tables.

Supports FPT University syllabus format with:
- Metadata table (Subject Code, Syllabus Name, NoCredit, etc.)
- Materials table
- CLO/LO table
- Sessions table (60 sessions format)
- Assessments table
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ParsedSession:
    """Parsed session data from markdown."""
    session_number: int
    topic: str
    mode: str  # Offline/Online (Learning-Teaching Type)
    clos: List[str]  # LO column
    itu: str  # ITU column
    materials: str  # Student Materials
    tasks: str  # Student's Tasks
    urls: str = ""  # URLs column
    download: str = ""  # S-Download column


@dataclass
class ParsedAssessment:
    """Parsed assessment data from markdown."""
    category: str
    type: str
    part: Optional[int]
    weight: float
    completion_criteria: str
    duration: str
    clos: List[str]
    question_type: str
    no_question: str
    knowledge_skill: str
    grading_guide: str
    note: str


@dataclass
class ParsedCLO:
    """Parsed CLO/LO data from markdown."""
    clo_number: int
    clo_id: str
    clo_details: str
    lo_details: str


@dataclass
class ParsedMaterial:
    """Parsed material data from markdown."""
    material_id: str
    title: str
    author: str = ""
    publisher: str = ""
    published_date: str = ""
    edition: str = ""
    isbn: str = ""
    is_main_material: bool = False
    is_hard_copy: bool = False
    is_online: bool = False
    note: str = ""


@dataclass
class ParsedSyllabus:
    """Complete parsed syllabus."""
    subject_code: str
    subject_name: str
    source_url: Optional[str]
    sessions: List[ParsedSession]
    assessments: List[ParsedAssessment]
    clos: List[ParsedCLO] = field(default_factory=list)
    materials: List[ParsedMaterial] = field(default_factory=list)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


class SyllabusMarkdownParser:
    """
    Parser for FPT University syllabus markdown files.
    
    Expected format:
    - Metadata table with Subject Code, Syllabus Name, NoCredit, etc.
    - Materials table
    - CLO/LO table with columns: CLO Name, CLO Details, LO Details
    - Session table with columns: Session, Topic, Learning-Teaching Type, LO, ITU, etc.
    - Assessment table with columns: Category, Type, Part, Weight, etc.
    """
    
    def __init__(self):
        self.subject_code_pattern = re.compile(r'\(([A-Z]{2,5}\d{2,4})\)')
    
    def parse(self, markdown_content: str) -> ParsedSyllabus:
        """Parse markdown content into structured syllabus data."""
        # Extract metadata
        metadata = self._parse_frontmatter(markdown_content)
        metadata.update(self._parse_metadata_table(markdown_content))
        
        # Extract subject code and name
        subject_code, subject_name = self._extract_subject_info(markdown_content, metadata)
        
        # Parse all tables
        tables = self._extract_tables(markdown_content)
        
        sessions = []
        assessments = []
        clos = []
        materials = []
        
        for table in tables:
            table_type = self._identify_table_type(table)
            
            if table_type == 'session':
                sessions = self._parse_session_table(table)
            elif table_type == 'assessment':
                assessments = self._parse_assessment_table(table)
            elif table_type == 'clo':
                clos = self._parse_clo_table(table)
            elif table_type == 'material':
                materials = self._parse_material_table(table)
        
        return ParsedSyllabus(
            subject_code=subject_code,
            subject_name=subject_name,
            source_url=metadata.get('source'),
            sessions=sessions,
            assessments=assessments,
            clos=clos,
            materials=materials,
            raw_metadata=metadata
        )

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter metadata."""
        metadata = {}
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if match:
            frontmatter = match.group(1)
            for line in frontmatter.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
        return metadata
    
    def _parse_metadata_table(self, content: str) -> Dict[str, Any]:
        """Extract metadata from the key-value table format."""
        metadata = {}
        patterns = [
            (r'\|\s*Subject\s*Code:\s*\|\s*([^|]+)\s*\|', 'subject_code'),
            (r'\|\s*Syllabus\s*Name:\s*\|\s*([^|]+)\s*\|', 'syllabus_name'),
            (r'\|\s*NoCredit:\s*\|\s*([^|]+)\s*\|', 'credits'),
            (r'\|\s*Degree\s*Level:\s*\|\s*([^|]+)\s*\|', 'degree_level'),
            (r'\|\s*Time\s*Allocation:\s*\|\s*([^|]+)\s*\|', 'time_allocation'),
            (r'\|\s*Pre-Requisite:\s*\|\s*([^|]+)\s*\|', 'pre_requisite'),
            (r'\|\s*Description:\s*\|\s*([^|]+)\s*\|', 'description'),
            (r'\|\s*StudentTasks:\s*\|\s*([^|]+)\s*\|', 'student_tasks'),
            (r'\|\s*Scoring\s*Scale:\s*\|\s*([^|]+)\s*\|', 'scoring_scale'),
            (r'\|\s*DecisionNo[^:]*:\s*\|\s*([^|]+)\s*\|', 'decision_no'),
            (r'\|\s*MinAvgMarkToPass:\s*\|\s*([^|]+)\s*\|', 'min_avg_mark'),
            (r'\|\s*ApprovedDate:\s*\|\s*([^|]+)\s*\|', 'approved_date'),
            (r'\|\s*Syllabus\s*ID:\s*\|\s*([^|]+)\s*\|', 'syllabus_id'),
        ]
        for pattern, key in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()
        return metadata
    
    def _extract_subject_info(self, content: str, metadata: Dict[str, Any] = None) -> tuple:
        """Extract subject code and name from markdown."""
        metadata = metadata or {}
        subject_code = metadata.get('subject_code', 'UNKNOWN')
        subject_name = metadata.get('syllabus_name', 'Unknown Course')
        
        if subject_code and subject_code != 'UNKNOWN':
            subject_code = subject_code.upper().strip()
        
        if subject_code == 'UNKNOWN':
            match = self.subject_code_pattern.search(content)
            if match:
                subject_code = match.group(1)
            else:
                title_match = re.search(r'^#\s+[^(]+\(([A-Z]{2,5}\d{2,4})\)', content, re.MULTILINE)
                if title_match:
                    subject_code = title_match.group(1)
        
        if subject_name == 'Unknown Course':
            title_match = re.search(r'^#\s+(.+?)(?:\s*\([A-Z]{2,5}\d{2,4}\))?$', content, re.MULTILINE)
            if title_match:
                subject_name = title_match.group(1).strip()
        
        return subject_code, subject_name

    def _extract_tables(self, content: str) -> List[List[List[str]]]:
        """Extract all markdown tables from content."""
        tables = []
        current_table = []
        lines = content.split('\n')
        merged_lines = []
        current_line = ''
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|'):
                if current_line:
                    merged_lines.append(current_line)
                current_line = stripped
            elif current_line and stripped:
                current_line = current_line.rstrip('|') + ' ' + stripped
                if not current_line.endswith('|'):
                    current_line += '|'
            else:
                if current_line:
                    merged_lines.append(current_line)
                    current_line = ''
                merged_lines.append(stripped)
        
        if current_line:
            merged_lines.append(current_line)
        
        for line in merged_lines:
            if re.match(r'^\d+\s+[\w\s]+\(', line, re.IGNORECASE):
                if current_table:
                    tables.append(current_table)
                    current_table = []
                continue
            
            if not line.startswith('|') or not line.endswith('|'):
                continue
            
            is_separator = all(c in '-|: ' for c in line)
            if is_separator:
                continue
            
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            first_cell = cells[0] if cells else ''
            is_header = not first_cell.isdigit() and any(
                h in first_cell.lower() for h in ['session', 'category', 'clo name', 'materialdescription']
            )
            
            if is_header and current_table:
                tables.append(current_table)
                current_table = []
            
            current_table.append(cells)
        
        if current_table:
            tables.append(current_table)
        
        return tables
    
    def _identify_table_type(self, table: List[List[str]]) -> str:
        """Identify the type of table based on headers."""
        if not table:
            return 'unknown'
        
        header = [h.lower() for h in table[0]]
        header_str = ' '.join(header)
        
        # Skip Constructive Questions table
        if 'name' in header and 'details' in header and 'session' in header_str:
            return 'constructive'
        
        if 'session' in header and 'topic' in header:
            return 'session'
        
        if 'category' in header and 'weight' in header:
            return 'assessment'
        
        if 'clo name' in header_str or ('clo' in header and 'details' in header_str):
            return 'clo'
        
        if 'materialdescription' in header_str or ('author' in header and 'publisher' in header):
            return 'material'
        
        return 'unknown'

    def _parse_session_table(self, table: List[List[str]]) -> List[ParsedSession]:
        """Parse session table into ParsedSession objects."""
        if len(table) < 2:
            return []
        
        header = [h.lower().strip() for h in table[0]]
        sessions = []
        
        col_map = {}
        for i, h in enumerate(header):
            if 'session' in h:
                col_map['session'] = i
            elif 'topic' in h:
                col_map['topic'] = i
            elif 'learning' in h or 'type' in h:
                col_map['mode'] = i
            elif h in ('lo', 'clo'):
                col_map['clo'] = i
            elif 'itu' in h:
                col_map['itu'] = i
            elif 'material' in h and 'student' in h:
                col_map['materials'] = i
            elif 'task' in h:
                col_map['tasks'] = i
            elif 'url' in h:
                col_map['urls'] = i
            elif 'download' in h:
                col_map['download'] = i
        
        for row in table[1:]:
            if len(row) < 2:
                continue
            
            try:
                session_num = int(row[col_map.get('session', 0)])
            except (ValueError, IndexError):
                continue
            
            clo_str = row[col_map.get('clo', 3)] if col_map.get('clo', 3) < len(row) else ''
            clos = self._parse_clos(clo_str)
            
            session = ParsedSession(
                session_number=session_num,
                topic=row[col_map.get('topic', 1)] if col_map.get('topic', 1) < len(row) else '',
                mode=row[col_map.get('mode', 2)] if col_map.get('mode', 2) < len(row) else 'Offline',
                clos=clos,
                itu=row[col_map.get('itu', 4)] if col_map.get('itu', 4) < len(row) else 'TU',
                materials=row[col_map.get('materials', 5)] if col_map.get('materials', 5) < len(row) else '',
                tasks=row[col_map.get('tasks', 7)] if col_map.get('tasks', 7) < len(row) else '',
                urls=row[col_map.get('urls', 8)] if col_map.get('urls', 8) < len(row) else '',
                download=row[col_map.get('download', 6)] if col_map.get('download', 6) < len(row) else ''
            )
            sessions.append(session)
        
        return sessions

    def _parse_assessment_table(self, table: List[List[str]]) -> List[ParsedAssessment]:
        """Parse assessment table into ParsedAssessment objects."""
        if len(table) < 2:
            return []
        
        header = [h.lower().strip() for h in table[0]]
        assessments = []
        
        col_map = {}
        for i, h in enumerate(header):
            if 'category' in h:
                col_map['category'] = i
            elif h == 'type':
                col_map['type'] = i
            elif 'part' in h:
                col_map['part'] = i
            elif 'weight' in h:
                col_map['weight'] = i
            elif 'completion' in h or 'criteria' in h:
                col_map['criteria'] = i
            elif 'duration' in h:
                col_map['duration'] = i
            elif h in ('clo', 'lo'):
                col_map['clo'] = i
            elif 'question type' in h:
                col_map['question_type'] = i
            elif 'no question' in h:
                col_map['no_question'] = i
            elif 'knowledge' in h:
                col_map['knowledge'] = i
            elif 'grading' in h:
                col_map['grading'] = i
            elif 'note' in h:
                col_map['note'] = i
        
        for row in table[1:]:
            if len(row) < 4:
                continue
            
            weight_str = row[col_map.get('weight', 3)] if col_map.get('weight', 3) < len(row) else '0'
            weight = self._parse_weight(weight_str)
            
            part_str = row[col_map.get('part', 2)] if col_map.get('part', 2) < len(row) else ''
            part = self._parse_part(part_str)
            
            clo_str = row[col_map.get('clo', 6)] if col_map.get('clo', 6) < len(row) else ''
            clos = self._parse_clos(clo_str)
            
            assessment = ParsedAssessment(
                category=row[col_map.get('category', 0)] if col_map.get('category', 0) < len(row) else '',
                type=row[col_map.get('type', 1)] if col_map.get('type', 1) < len(row) else '',
                part=part,
                weight=weight,
                completion_criteria=row[col_map.get('criteria', 4)] if col_map.get('criteria', 4) < len(row) else '',
                duration=row[col_map.get('duration', 5)] if col_map.get('duration', 5) < len(row) else '',
                clos=clos,
                question_type=row[col_map.get('question_type', 7)] if col_map.get('question_type', 7) < len(row) else '',
                no_question=row[col_map.get('no_question', 8)] if col_map.get('no_question', 8) < len(row) else '',
                knowledge_skill=row[col_map.get('knowledge', 9)] if col_map.get('knowledge', 9) < len(row) else '',
                grading_guide=row[col_map.get('grading', 10)] if col_map.get('grading', 10) < len(row) else '',
                note=row[col_map.get('note', 11)] if col_map.get('note', 11) < len(row) else ''
            )
            assessments.append(assessment)
        
        return assessments

    def _parse_clo_table(self, table: List[List[str]]) -> List[ParsedCLO]:
        """Parse CLO/LO table into ParsedCLO objects."""
        if len(table) < 2:
            return []
        
        header = [h.lower().strip() for h in table[0]]
        clos = []
        
        col_map = {}
        for i, h in enumerate(header):
            if 'clo name' in h or h == 'clo':
                col_map['clo_name'] = i
            elif 'clo details' in h:
                col_map['clo_details'] = i
            elif 'lo details' in h:
                col_map['lo_details'] = i
        
        for row in table[1:]:
            if len(row) < 2:
                continue
            
            try:
                clo_num = int(row[col_map.get('clo_name', 0)])
            except (ValueError, IndexError):
                continue
            
            clo = ParsedCLO(
                clo_number=clo_num,
                clo_id=f"CLO{clo_num}",
                clo_details=row[col_map.get('clo_details', 1)] if col_map.get('clo_details', 1) < len(row) else '',
                lo_details=row[col_map.get('lo_details', 2)] if col_map.get('lo_details', 2) < len(row) else ''
            )
            clos.append(clo)
        
        return clos
    
    def _parse_material_table(self, table: List[List[str]]) -> List[ParsedMaterial]:
        """Parse material table into ParsedMaterial objects."""
        if len(table) < 2:
            return []
        
        header = [h.lower().strip() for h in table[0]]
        materials = []
        
        col_map = {}
        for i, h in enumerate(header):
            if 'material' in h or 'description' in h:
                col_map['title'] = i
            elif 'author' in h:
                col_map['author'] = i
            elif 'publisher' in h:
                col_map['publisher'] = i
            elif 'date' in h:
                col_map['date'] = i
            elif 'edition' in h:
                col_map['edition'] = i
            elif 'isbn' in h:
                col_map['isbn'] = i
            elif 'main' in h:
                col_map['main'] = i
            elif 'hard' in h:
                col_map['hard'] = i
            elif 'online' in h:
                col_map['online'] = i
            elif 'note' in h:
                col_map['note'] = i
        
        for idx, row in enumerate(table[1:]):
            if len(row) < 1:
                continue
            
            title = row[col_map.get('title', 0)] if col_map.get('title', 0) < len(row) else ''
            if not title:
                continue
            
            material = ParsedMaterial(
                material_id=f"mat_{idx+1}",
                title=title,
                author=row[col_map.get('author', 1)] if col_map.get('author', 1) < len(row) else '',
                publisher=row[col_map.get('publisher', 2)] if col_map.get('publisher', 2) < len(row) else '',
                published_date=row[col_map.get('date', 3)] if col_map.get('date', 3) < len(row) else '',
                edition=row[col_map.get('edition', 4)] if col_map.get('edition', 4) < len(row) else '',
                isbn=row[col_map.get('isbn', 5)] if col_map.get('isbn', 5) < len(row) else '',
                is_main_material=self._parse_bool(row[col_map.get('main', 6)] if col_map.get('main', 6) < len(row) else ''),
                is_hard_copy=self._parse_bool(row[col_map.get('hard', 7)] if col_map.get('hard', 7) < len(row) else ''),
                is_online=self._parse_bool(row[col_map.get('online', 8)] if col_map.get('online', 8) < len(row) else ''),
                note=row[col_map.get('note', 9)] if col_map.get('note', 9) < len(row) else ''
            )
            materials.append(material)
        
        return materials

    def _parse_clos(self, clo_str: str) -> List[str]:
        """Parse CLO/LO string into list of IDs."""
        if not clo_str:
            return []
        
        clo_str = clo_str.upper().strip()
        
        if 'ALL' in clo_str:
            return ['All CLOs']
        
        # Find all CLO or LO references
        clos = re.findall(r'CLO\d+', clo_str)
        if not clos:
            los = re.findall(r'LO\d+', clo_str)
            clos = los  # Keep as LO format
        
        return clos if clos else [clo_str] if clo_str else []
    
    def _parse_weight(self, weight_str: str) -> float:
        """Parse weight percentage string to float."""
        if not weight_str:
            return 0.0
        weight_str = weight_str.replace('%', '').strip()
        try:
            return float(weight_str)
        except ValueError:
            return 0.0
    
    def _parse_part(self, part_str: str) -> Optional[int]:
        """Parse part number string to int."""
        if not part_str:
            return None
        try:
            return int(part_str)
        except ValueError:
            return None
    
    def _parse_bool(self, val: str) -> bool:
        """Parse boolean value from string."""
        if not val:
            return False
        val = val.lower().strip()
        return val in ('true', 'yes', '1', 'x', '✓')


def parse_syllabus_file(file_path: str) -> ParsedSyllabus:
    """Convenience function to parse a syllabus markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    parser = SyllabusMarkdownParser()
    return parser.parse(content)


def convert_to_entities(parsed: ParsedSyllabus, approved_date: Optional[str] = None) -> Dict[str, Any]:
    """Convert ParsedSyllabus to entity dictionaries ready for storage."""
    if not approved_date:
        approved_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    sessions = []
    for s in parsed.sessions:
        sessions.append({
            'subject_code': parsed.subject_code,
            'approved_date': approved_date,
            'session_number': s.session_number,
            'topics': [s.topic] if s.topic else [],
            'clo_coverage': s.clos,
            'mode': s.mode,
            'session_type': s.itu,
            'materials': s.materials,
            'activities': s.tasks
        })
    
    assessments = []
    for a in parsed.assessments:
        assessments.append({
            'subject_code': parsed.subject_code,
            'approved_date': approved_date,
            'category': a.category,
            'assessment_type': a.type,
            'part': a.part,
            'weight_percentage': a.weight,
            'completion_criteria': a.completion_criteria,
            'duration': a.duration,
            'clo_mapping': a.clos,
            'question_type': a.question_type,
            'no_question': a.no_question,
            'knowledge_and_skill': a.knowledge_skill,
            'grading_guide': a.grading_guide,
            'note': a.note
        })
    
    return {
        'subject_code': parsed.subject_code,
        'subject_name': parsed.subject_name,
        'source_url': parsed.source_url,
        'approved_date': approved_date,
        'sessions': sessions,
        'assessments': assessments
    }
