"""
Task #17: Text Chunking Service

Chia text thành các chunks với configurable size và overlap.
Preserve context bằng cách split theo paragraph/sentence boundaries.

Enhanced with Row-based Chunking + Header Injection for tables.
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TextChunk:
    """Một chunk của text."""
    index: int
    text: str
    char_count: int
    token_estimate: int  # Ước tính tokens (~4 chars/token)
    start_char: int      # Vị trí bắt đầu trong original text
    end_char: int        # Vị trí kết thúc trong original text
    is_table: bool = False  # Flag để identify table chunks
    table_name: str = ""    # Tên/context của table


@dataclass
class TableData:
    """Structured table data for chunking."""
    name: str                    # Table name/title
    headers: List[str]           # Header row
    rows: List[List[str]]        # Data rows
    page_number: int = 1


# Default settings
# Cohere embed model has 2048 char limit, so chunk_size * CHARS_PER_TOKEN < 2048
# OPTIMIZED FOR DOCUMENTS WITH TABLES AND COMPLEX STRUCTURES
DEFAULT_CHUNK_SIZE = 500       # tokens (~2000 chars) - Increased for tables
DEFAULT_OVERLAP = 100          # tokens - Increased to preserve table context
CHARS_PER_TOKEN = 4            # Ước tính trung bình
DEFAULT_TABLE_ROWS_PER_CHUNK = 10  # Increased from 5 to 10 for better table context


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    respect_boundaries: bool = True
) -> List[TextChunk]:
    """
    Chia text thành các chunks.
    
    Args:
        text: Text cần chia
        chunk_size: Kích thước mỗi chunk (tokens)
        overlap: Số tokens overlap giữa các chunks
        respect_boundaries: Có cố gắng split theo paragraph/sentence không
        
    Returns:
        List các TextChunk
    """
    if not text or not text.strip():
        return []
    
    # Convert token size to char size
    chunk_chars = chunk_size * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN
    
    # Validate parameters
    if chunk_chars <= overlap_chars:
        raise ValueError("chunk_size must be greater than overlap")
    
    if respect_boundaries:
        return _chunk_with_boundaries(text, chunk_chars, overlap_chars)
    else:
        return _chunk_simple(text, chunk_chars, overlap_chars)


def _chunk_simple(
    text: str,
    chunk_chars: int,
    overlap_chars: int
) -> List[TextChunk]:
    """Simple chunking - cắt theo character count."""
    chunks = []
    start = 0
    index = 0
    
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunk_text = text[start:end]
        
        chunks.append(TextChunk(
            index=index,
            text=chunk_text,
            char_count=len(chunk_text),
            token_estimate=len(chunk_text) // CHARS_PER_TOKEN,
            start_char=start,
            end_char=end
        ))
        
        # Move start position (với overlap)
        start = end - overlap_chars
        if start >= len(text) - overlap_chars:
            break
        index += 1
    
    return chunks


def _chunk_with_boundaries(
    text: str,
    chunk_chars: int,
    overlap_chars: int
) -> List[TextChunk]:
    """
    Chunking với respect cho paragraph/sentence boundaries.
    Cố gắng không cắt giữa câu.
    """
    chunks = []
    start = 0
    index = 0
    
    # Nếu text ngắn hơn chunk size, trả về 1 chunk
    if len(text) <= chunk_chars:
        return [TextChunk(
            index=0,
            text=text.strip(),
            char_count=len(text.strip()),
            token_estimate=len(text.strip()) // CHARS_PER_TOKEN,
            start_char=0,
            end_char=len(text)
        )]
    
    while start < len(text):
        # Tính end position
        end = min(start + chunk_chars, len(text))
        
        # Nếu chưa hết text, tìm boundary tốt nhất
        if end < len(text):
            end = _find_best_boundary(text, start, end, chunk_chars)
        
        chunk_text_content = text[start:end].strip()
        
        if chunk_text_content:  # Chỉ add chunk nếu có content
            chunks.append(TextChunk(
                index=index,
                text=chunk_text_content,
                char_count=len(chunk_text_content),
                token_estimate=len(chunk_text_content) // CHARS_PER_TOKEN,
                start_char=start,
                end_char=end
            ))
            index += 1
        
        # Nếu đã đến cuối text, dừng
        if end >= len(text):
            break
        
        # Tính start position cho chunk tiếp theo (với overlap)
        step = chunk_chars - overlap_chars
        start = start + step
        
        # Đảm bảo không vượt quá text length
        if start >= len(text):
            break
    
    return chunks


def _find_best_boundary(
    text: str,
    start: int,
    end: int,
    chunk_chars: int
) -> int:
    """
    Tìm vị trí boundary tốt nhất để cắt chunk.
    Ưu tiên: paragraph > sentence > word
    """
    search_start = max(start, end - chunk_chars // 4)  # Tìm trong 25% cuối
    search_text = text[search_start:end]
    
    # 1. Tìm paragraph break (double newline)
    para_match = list(re.finditer(r'\n\n+', search_text))
    if para_match:
        return search_start + para_match[-1].end()
    
    # 2. Tìm sentence break
    sentence_match = list(re.finditer(r'[.!?]\s+', search_text))
    if sentence_match:
        return search_start + sentence_match[-1].end()
    
    # 3. Tìm word break
    word_match = list(re.finditer(r'\s+', search_text))
    if word_match:
        return search_start + word_match[-1].start()
    
    # 4. Fallback: cắt tại end
    return end


def _find_overlap_boundary(
    text: str,
    overlap_start: int,
    end: int
) -> int:
    """
    Tìm vị trí bắt đầu overlap tốt (đầu câu hoặc paragraph).
    """
    search_text = text[overlap_start:end]
    
    # Tìm đầu paragraph
    para_match = re.search(r'\n\n+', search_text)
    if para_match:
        return overlap_start + para_match.end()
    
    # Tìm đầu câu
    sentence_match = re.search(r'[.!?]\s+', search_text)
    if sentence_match:
        return overlap_start + sentence_match.end()
    
    return overlap_start


def chunk_text_simple(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP
) -> List[str]:
    """
    Convenience function - chỉ trả về list text strings.
    """
    chunks = chunk_text(text, chunk_size, overlap)
    return [c.text for c in chunks]


def estimate_tokens(text: str) -> int:
    """Ước tính số tokens trong text."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def get_chunk_stats(chunks: List[TextChunk]) -> dict:
    """Lấy thống kê về chunks."""
    if not chunks:
        return {
            "total_chunks": 0,
            "total_chars": 0,
            "total_tokens_estimate": 0,
            "avg_chunk_size": 0,
            "min_chunk_size": 0,
            "max_chunk_size": 0
        }
    
    char_counts = [c.char_count for c in chunks]
    token_counts = [c.token_estimate for c in chunks]
    
    return {
        "total_chunks": len(chunks),
        "total_chars": sum(char_counts),
        "total_tokens_estimate": sum(token_counts),
        "avg_chunk_size": sum(token_counts) // len(chunks),
        "min_chunk_size": min(token_counts),
        "max_chunk_size": max(token_counts)
    }


# ============ ROW-BASED TABLE CHUNKING WITH HEADER INJECTION ============
# Layer 1: Preserve Table Structure + Semantic Description
# Layer 2: Smart Table Chunking with Context

def table_to_semantic_description(
    table: List[List[str]],
    table_name: str = "Table"
) -> str:
    """
    Layer 1: Convert table to semantic natural language description.
    
    Thay vì flatten table thành text vô nghĩa, tạo mô tả có ý nghĩa.
    
    Example:
    Input: [["Grade", "Score", "GPA"], ["A+", "9-10", "4.0"]]
    Output: "This table shows Grade information:
             - Grade A+: Score is 9-10, GPA is 4.0"
    """
    if not table or len(table) < 2:
        return ""
    
    headers = [str(h).strip() for h in table[0]]
    data_rows = table[1:]
    
    lines = [f"This table shows {table_name} information:"]
    
    for row in data_rows:
        if len(row) >= len(headers):
            # Create semantic description for each row
            # Use first column as the main identifier
            main_value = str(row[0]).strip()
            attributes = []
            
            for i, (header, cell) in enumerate(zip(headers[1:], row[1:]), 1):
                cell_value = str(cell).strip()
                if cell_value:
                    attributes.append(f"{header} is {cell_value}")
            
            if attributes:
                lines.append(f"- {headers[0]} {main_value}: {', '.join(attributes)}")
            else:
                lines.append(f"- {headers[0]}: {main_value}")
    
    return "\n".join(lines)


def chunk_table_with_headers(
    table: List[List[str]],
    table_name: str = "Table",
    rows_per_chunk: int = DEFAULT_TABLE_ROWS_PER_CHUNK,
    page_number: int = 1,
    start_index: int = 0,
    include_semantic: bool = True
) -> List[TextChunk]:
    """
    Layer 2: Chunk table theo rows với header injection + semantic context.
    
    Mỗi chunk sẽ có format:
    "Table: {table_name}
    Context: This table shows {description}...
    
    {header_row}
    {data_row_1}
    {data_row_2}
    ...
    
    Summary: {semantic description of rows in this chunk}"
    
    Args:
        table: 2D array của table (first row = headers)
        table_name: Tên/context của table
        rows_per_chunk: Số data rows mỗi chunk
        page_number: Số trang chứa table
        start_index: Index bắt đầu cho chunks
        include_semantic: Include semantic description
        
    Returns:
        List các TextChunk với is_table=True
    """
    if not table or len(table) < 2:
        return []
    
    chunks = []
    headers = [str(h).strip() for h in table[0]]
    data_rows = table[1:]
    
    # Format header row
    header_text = " | ".join(headers)
    
    # Chunk data rows
    for i in range(0, len(data_rows), rows_per_chunk):
        chunk_rows = data_rows[i:i + rows_per_chunk]
        
        # Build chunk text với header injection
        lines = []
        
        # 1. Table title with context
        lines.append(f"=== {table_name} ===")
        lines.append(f"(Page {page_number}, Rows {i+1}-{i+len(chunk_rows)} of {len(data_rows)})")
        lines.append("")
        
        # 2. Structured table format (for exact matching)
        lines.append("Table Data:")
        lines.append(header_text)
        lines.append("-" * len(header_text))
        
        for row in chunk_rows:
            row_values = [str(cell).strip() for cell in row]
            # Pad row if needed
            while len(row_values) < len(headers):
                row_values.append("")
            row_text = " | ".join(row_values[:len(headers)])
            lines.append(row_text)
        
        # 3. Semantic description (for semantic search)
        if include_semantic:
            lines.append("")
            lines.append("Summary:")
            for row in chunk_rows:
                row_values = [str(cell).strip() for cell in row]
                if len(row_values) >= len(headers):
                    main_value = row_values[0]
                    attributes = []
                    for j, (header, cell) in enumerate(zip(headers[1:], row_values[1:]), 1):
                        if cell:
                            attributes.append(f"{header}={cell}")
                    if attributes:
                        lines.append(f"  • {headers[0]} '{main_value}': {', '.join(attributes)}")
        
        chunk_text = "\n".join(lines)
        
        chunks.append(TextChunk(
            index=start_index + len(chunks),
            text=chunk_text,
            char_count=len(chunk_text),
            token_estimate=len(chunk_text) // CHARS_PER_TOKEN,
            start_char=0,  # Not applicable for table chunks
            end_char=0,
            is_table=True,
            table_name=table_name
        ))
    
    return chunks


def create_table_overview_chunk(
    table: List[List[str]],
    table_name: str = "Table",
    page_number: int = 1,
    start_index: int = 0
) -> TextChunk:
    """
    Create an overview chunk for the entire table.
    
    This chunk contains:
    - Table name and description
    - Column headers explanation
    - Summary of all values (for retrieval)
    """
    if not table or len(table) < 2:
        return None
    
    headers = [str(h).strip() for h in table[0]]
    data_rows = table[1:]
    
    lines = []
    lines.append(f"=== {table_name} - Overview ===")
    lines.append(f"Location: Page {page_number}")
    lines.append(f"Structure: {len(data_rows)} rows, {len(headers)} columns")
    lines.append("")
    
    # Column descriptions
    lines.append(f"Columns: {', '.join(headers)}")
    lines.append("")
    
    # Collect unique values per column for searchability
    lines.append("Contains the following data:")
    for col_idx, header in enumerate(headers):
        values = set()
        for row in data_rows:
            if col_idx < len(row):
                val = str(row[col_idx]).strip()
                if val:
                    values.add(val)
        if values:
            # Limit to first 10 unique values
            sample_values = list(values)[:10]
            lines.append(f"  • {header}: {', '.join(sample_values)}")
    
    # Full semantic description
    lines.append("")
    lines.append("Detailed content:")
    semantic = table_to_semantic_description(table, table_name)
    lines.append(semantic)
    
    chunk_text = "\n".join(lines)
    
    return TextChunk(
        index=start_index,
        text=chunk_text,
        char_count=len(chunk_text),
        token_estimate=len(chunk_text) // CHARS_PER_TOKEN,
        start_char=0,
        end_char=0,
        is_table=True,
        table_name=f"{table_name} (Overview)"
    )


def detect_table_in_text(text: str) -> List[Tuple[int, int, str]]:
    """
    Detect table-like structures trong text.
    
    Returns:
        List of (start_pos, end_pos, table_text) tuples
    """
    tables = []
    
    # Pattern 1: Markdown-style tables (| col1 | col2 |)
    md_table_pattern = r'(\|[^\n]+\|\n)+'
    for match in re.finditer(md_table_pattern, text):
        tables.append((match.start(), match.end(), match.group()))
    
    # Pattern 2: Tab-separated or multiple-space separated rows
    # Look for consecutive lines with similar structure
    lines = text.split('\n')
    table_start = None
    table_lines = []
    
    for i, line in enumerate(lines):
        # Check if line looks like table row (has multiple columns)
        if re.search(r'\t|  {2,}|\|', line) and len(line.strip()) > 10:
            if table_start is None:
                table_start = sum(len(l) + 1 for l in lines[:i])
            table_lines.append(line)
        else:
            if len(table_lines) >= 3:  # At least header + 2 rows
                table_text = '\n'.join(table_lines)
                table_end = table_start + len(table_text)
                tables.append((table_start, table_end, table_text))
            table_start = None
            table_lines = []
    
    # Handle table at end of text
    if len(table_lines) >= 3:
        table_text = '\n'.join(table_lines)
        table_end = table_start + len(table_text)
        tables.append((table_start, table_end, table_text))
    
    return tables


def parse_text_table(table_text: str) -> List[List[str]]:
    """
    Parse text-based table thành 2D array.
    
    Args:
        table_text: Table as text string
        
    Returns:
        2D array of cells
    """
    rows = []
    lines = table_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Try different separators
        if '|' in line:
            # Markdown style
            cells = [c.strip() for c in line.split('|') if c.strip()]
        elif '\t' in line:
            # Tab separated
            cells = [c.strip() for c in line.split('\t')]
        else:
            # Multiple spaces
            cells = [c.strip() for c in re.split(r'  +', line)]
        
        if cells:
            rows.append(cells)
    
    return rows


def chunk_text_with_tables(
    text: str,
    tables: List[List[List[str]]] = None,
    table_names: List[str] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    rows_per_chunk: int = DEFAULT_TABLE_ROWS_PER_CHUNK,
    include_overview: bool = True
) -> List[TextChunk]:
    """
    Layer 1 + Layer 2: Chunk text với special handling cho tables.
    
    Tables được chunk riêng với:
    - Overview chunk (full semantic description for retrieval)
    - Row-based chunks với header injection
    - Semantic summary trong mỗi chunk
    
    Args:
        text: Full text content
        tables: List of tables (2D arrays) từ PDF extractor
        table_names: Optional names for each table
        chunk_size: Token size cho text chunks
        overlap: Overlap tokens cho text chunks
        rows_per_chunk: Rows per table chunk
        include_overview: Include overview chunk for each table
        
    Returns:
        Combined list of text chunks and table chunks
    """
    all_chunks = []
    chunk_index = 0
    
    # 1. Chunk tables first (if provided from PDF extractor)
    if tables:
        for i, table in enumerate(tables):
            name = table_names[i] if table_names and i < len(table_names) else f"Table {i+1}"
            
            # Create overview chunk first (for better retrieval)
            if include_overview and len(table) >= 2:
                overview = create_table_overview_chunk(
                    table=table,
                    table_name=name,
                    page_number=1,
                    start_index=chunk_index
                )
                if overview:
                    all_chunks.append(overview)
                    chunk_index += 1
            
            # Create row-based chunks with header injection
            table_chunks = chunk_table_with_headers(
                table=table,
                table_name=name,
                rows_per_chunk=rows_per_chunk,
                start_index=chunk_index,
                include_semantic=True
            )
            all_chunks.extend(table_chunks)
            chunk_index += len(table_chunks)
    
    # 2. Detect and chunk tables in text (if no tables provided)
    if not tables:
        detected_tables = detect_table_in_text(text)
        
        # Remove table regions from text and chunk them separately
        text_without_tables = text
        offset = 0
        
        for i, (start, end, table_text) in enumerate(detected_tables):
            # Infer table name from context
            inferred_name = infer_table_name(text, start)
            table_name = inferred_name if inferred_name != "Data Table" else f"Table {i+1}"
            
            # Parse and chunk the table
            parsed_table = parse_text_table(table_text)
            if len(parsed_table) >= 2:  # Has header + data
                # Create overview chunk
                if include_overview:
                    overview = create_table_overview_chunk(
                        table=parsed_table,
                        table_name=table_name,
                        start_index=chunk_index
                    )
                    if overview:
                        all_chunks.append(overview)
                        chunk_index += 1
                
                # Create row-based chunks
                table_chunks = chunk_table_with_headers(
                    table=parsed_table,
                    table_name=table_name,
                    rows_per_chunk=rows_per_chunk,
                    start_index=chunk_index,
                    include_semantic=True
                )
                all_chunks.extend(table_chunks)
                chunk_index += len(table_chunks)
                
                # Remove table from text
                adjusted_start = start - offset
                adjusted_end = end - offset
                text_without_tables = (
                    text_without_tables[:adjusted_start] + 
                    f"\n[See {table_name} for details]\n" +
                    text_without_tables[adjusted_end:]
                )
                offset += (end - start) - len(f"\n[See {table_name} for details]\n")
        
        text = text_without_tables
    
    # 3. Chunk remaining text
    text_chunks = chunk_text(text, chunk_size, overlap)
    
    # Re-index text chunks
    for chunk in text_chunks:
        chunk.index = chunk_index
        chunk_index += 1
    
    all_chunks.extend(text_chunks)
    
    return all_chunks


def infer_table_name(text: str, table_position: int, max_lookback: int = 200) -> str:
    """
    Infer table name từ context xung quanh.
    
    Tìm heading hoặc caption gần table.
    """
    # Look back for heading/caption
    lookback_text = text[max(0, table_position - max_lookback):table_position]
    
    # Pattern 1: "Table X: Name" or "Table X. Name"
    table_caption = re.search(r'Table\s+\d+[.:]\s*([^\n]+)', lookback_text, re.IGNORECASE)
    if table_caption:
        return table_caption.group(1).strip()
    
    # Pattern 2: Heading before table (line ending with :)
    heading = re.search(r'([^\n]+):\s*$', lookback_text)
    if heading:
        return heading.group(1).strip()
    
    # Pattern 3: Last non-empty line before table
    lines = [l.strip() for l in lookback_text.split('\n') if l.strip()]
    if lines:
        last_line = lines[-1]
        if len(last_line) < 100:  # Likely a heading
            return last_line
    
    return "Data Table"
