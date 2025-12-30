"""
Task #15 & #16: PDF Text Extraction

- Digital PDFs: PyPDF2 extraction
- Scanned PDFs: AWS Textract extraction
"""

import io
import re
import time
import logging
from typing import Union, List, Optional
from pathlib import Path
from dataclasses import dataclass, field

import PyPDF2
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Content của một trang PDF."""
    page_number: int
    text: str
    char_count: int
    tables: List[List[List[str]]] = field(default_factory=list)  # List of tables, each table is 2D array
    is_scanned: bool = False


@dataclass
class PDFContent:
    """Kết quả extract từ PDF."""
    total_pages: int
    pages: List[PageContent]
    full_text: str
    total_chars: int
    metadata: dict
    errors: List[str]
    extraction_method: str = "pypdf2"  # "pypdf2" or "textract"


def extract_text_from_pdf(
    file_input: Union[str, Path, bytes, io.BytesIO],
    max_pages: Optional[int] = None,
    clean_text: bool = True
) -> PDFContent:
    """
    Extract text từ digital PDF.
    
    Args:
        file_input: Đường dẫn file, bytes, hoặc BytesIO
        max_pages: Giới hạn số trang extract (None = tất cả)
        clean_text: Có clean text không (remove extra whitespace)
        
    Returns:
        PDFContent với text từ tất cả các trang
    """
    pages = []
    errors = []
    metadata = {}
    
    try:
        reader = _get_pdf_reader(file_input)
        
        if reader is None:
            return PDFContent(
                total_pages=0,
                pages=[],
                full_text="",
                total_chars=0,
                metadata={},
                errors=["Cannot read PDF file"]
            )
        
        # Extract metadata
        metadata = _extract_metadata(reader)
        
        total_pages = len(reader.pages)
        pages_to_extract = total_pages if max_pages is None else min(max_pages, total_pages)
        
        for i in range(pages_to_extract):
            try:
                page = reader.pages[i]
                text = page.extract_text() or ""
                
                if clean_text:
                    text = _clean_text(text)
                
                pages.append(PageContent(
                    page_number=i + 1,
                    text=text,
                    char_count=len(text)
                ))
            except Exception as e:
                errors.append(f"Error extracting page {i + 1}: {str(e)}")
                pages.append(PageContent(
                    page_number=i + 1,
                    text="",
                    char_count=0
                ))
        
        # Combine all text
        full_text = "\n\n".join([p.text for p in pages if p.text])
        total_chars = sum(p.char_count for p in pages)
        
        return PDFContent(
            total_pages=total_pages,
            pages=pages,
            full_text=full_text,
            total_chars=total_chars,
            metadata=metadata,
            errors=errors
        )
        
    except Exception as e:
        return PDFContent(
            total_pages=0,
            pages=[],
            full_text="",
            total_chars=0,
            metadata={},
            errors=[f"Failed to process PDF: {str(e)}"]
        )


def extract_text_simple(
    file_input: Union[str, Path, bytes, io.BytesIO]
) -> str:
    """
    Extract text đơn giản - chỉ trả về full text.
    
    Args:
        file_input: Đường dẫn file, bytes, hoặc BytesIO
        
    Returns:
        Full text từ PDF hoặc empty string nếu lỗi
    """
    result = extract_text_from_pdf(file_input)
    return result.full_text


def extract_text_by_page(
    file_input: Union[str, Path, bytes, io.BytesIO]
) -> List[str]:
    """
    Extract text theo từng trang.
    
    Args:
        file_input: Đường dẫn file, bytes, hoặc BytesIO
        
    Returns:
        List text của từng trang
    """
    result = extract_text_from_pdf(file_input)
    return [p.text for p in result.pages]


def _get_pdf_reader(
    file_input: Union[str, Path, bytes, io.BytesIO]
) -> Optional[PyPDF2.PdfReader]:
    """Tạo PdfReader từ nhiều loại input."""
    try:
        if isinstance(file_input, (str, Path)):
            return PyPDF2.PdfReader(str(file_input))
        elif isinstance(file_input, bytes):
            return PyPDF2.PdfReader(io.BytesIO(file_input))
        elif isinstance(file_input, io.BytesIO):
            file_input.seek(0)
            return PyPDF2.PdfReader(file_input)
        else:
            raise ValueError(f"Unsupported input type: {type(file_input)}")
    except Exception as e:
        print(f"Error creating PDF reader: {e}")
        return None


def _extract_metadata(reader: PyPDF2.PdfReader) -> dict:
    """Extract metadata từ PDF."""
    metadata = {}
    try:
        if reader.metadata:
            meta = reader.metadata
            metadata = {
                "title": meta.get("/Title", ""),
                "author": meta.get("/Author", ""),
                "subject": meta.get("/Subject", ""),
                "creator": meta.get("/Creator", ""),
                "producer": meta.get("/Producer", ""),
                "creation_date": str(meta.get("/CreationDate", "")),
                "modification_date": str(meta.get("/ModDate", ""))
            }
            # Clean None values
            metadata = {k: v for k, v in metadata.items() if v}
    except Exception:
        pass
    return metadata


def _clean_text(text: str) -> str:
    """
    Clean extracted text:
    - Remove excessive whitespace
    - Fix common encoding issues
    - Normalize line breaks
    - Fix Vietnamese encoding issues
    """
    if not text:
        return ""
    
    # Ensure text is properly decoded as UTF-8
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = text.decode('latin-1')
            except Exception:
                text = text.decode('utf-8', errors='ignore')
    
    # Normalize Unicode (NFC form for Vietnamese)
    import unicodedata
    text = unicodedata.normalize('NFC', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Fix common ligatures using Unicode code points
    ligature_map = {
        '\ufb01': 'fi',  # fi ligature
        '\ufb02': 'fl',  # fl ligature
        '\ufb00': 'ff',  # ff ligature
        '\ufb03': 'ffi', # ffi ligature
        '\ufb04': 'ffl', # ffl ligature
    }
    for lig, replacement in ligature_map.items():
        text = text.replace(lig, replacement)
    
    # Remove null characters and other control characters
    text = text.replace('\x00', '')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Strip final result
    return text.strip()


def get_page_count(file_input: Union[str, Path, bytes, io.BytesIO]) -> int:
    """Lấy số trang của PDF."""
    try:
        reader = _get_pdf_reader(file_input)
        if reader:
            return len(reader.pages)
    except Exception:
        pass
    return 0


# ============ TEXTRACT EXTRACTOR (Task #16) ============

class TextractExtractor:
    """
    Extract text từ scanned PDFs sử dụng AWS Textract.
    
    Supports:
    - Single page: Sync API (DetectDocumentText, AnalyzeDocument)
    - Multi-page: Async API (StartDocumentAnalysis)
    - Tables and Forms extraction
    """
    
    def __init__(self, region: str = "ap-southeast-1"):
        self.region = region
        self.client = boto3.client("textract", region_name=region)
        logger.info(f"Initialized TextractExtractor (region: {region})")
    
    def extract_from_bytes(
        self,
        pdf_bytes: bytes,
        extract_tables: bool = True
    ) -> PDFContent:
        """
        Extract text từ PDF bytes (single page only for sync API).
        
        Args:
            pdf_bytes: PDF file content as bytes
            extract_tables: Whether to extract tables (uses AnalyzeDocument)
            
        Returns:
            PDFContent with extracted text and tables
        """
        try:
            if extract_tables:
                return self._analyze_document_bytes(pdf_bytes)
            else:
                return self._detect_text_bytes(pdf_bytes)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Textract API error: {error_code} - {e}")
            return PDFContent(
                total_pages=0,
                pages=[],
                full_text="",
                total_chars=0,
                metadata={},
                errors=[f"Textract error: {error_code}"],
                extraction_method="textract"
            )
        except Exception as e:
            logger.error(f"Error extracting with Textract: {e}")
            return PDFContent(
                total_pages=0,
                pages=[],
                full_text="",
                total_chars=0,
                metadata={},
                errors=[str(e)],
                extraction_method="textract"
            )
    
    def extract_from_s3(
        self,
        bucket: str,
        key: str,
        extract_tables: bool = True,
        wait_for_completion: bool = True,
        poll_interval: int = 5,
        max_wait_time: int = 300
    ) -> PDFContent:
        """
        Extract text từ PDF trong S3 (supports multi-page).
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            extract_tables: Whether to extract tables
            wait_for_completion: Wait for async job to complete
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait
            
        Returns:
            PDFContent with extracted text and tables
        """
        try:
            # Start async job
            if extract_tables:
                job_id = self._start_document_analysis(bucket, key)
            else:
                job_id = self._start_text_detection(bucket, key)
            
            logger.info(f"Started Textract job: {job_id}")
            
            if not wait_for_completion:
                return PDFContent(
                    total_pages=0,
                    pages=[],
                    full_text="",
                    total_chars=0,
                    metadata={"job_id": job_id, "status": "IN_PROGRESS"},
                    errors=[],
                    extraction_method="textract"
                )
            
            # Poll for completion
            return self._wait_for_job(job_id, extract_tables, poll_interval, max_wait_time)
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Textract API error: {error_code} - {e}")
            return PDFContent(
                total_pages=0,
                pages=[],
                full_text="",
                total_chars=0,
                metadata={},
                errors=[f"Textract error: {error_code}"],
                extraction_method="textract"
            )
    
    def _detect_text_bytes(self, pdf_bytes: bytes) -> PDFContent:
        """Sync text detection from bytes."""
        response = self.client.detect_document_text(
            Document={"Bytes": pdf_bytes}
        )
        return self._parse_response([response], extract_tables=False)
    
    def _analyze_document_bytes(self, pdf_bytes: bytes) -> PDFContent:
        """Sync document analysis from bytes (with tables/forms)."""
        response = self.client.analyze_document(
            Document={"Bytes": pdf_bytes},
            FeatureTypes=["TABLES", "FORMS"]
        )
        return self._parse_response([response], extract_tables=True)
    
    def _start_text_detection(self, bucket: str, key: str) -> str:
        """Start async text detection job."""
        response = self.client.start_document_text_detection(
            DocumentLocation={
                "S3Object": {"Bucket": bucket, "Name": key}
            }
        )
        return response["JobId"]
    
    def _start_document_analysis(self, bucket: str, key: str) -> str:
        """Start async document analysis job."""
        response = self.client.start_document_analysis(
            DocumentLocation={
                "S3Object": {"Bucket": bucket, "Name": key}
            },
            FeatureTypes=["TABLES", "FORMS"]
        )
        return response["JobId"]
    
    def _wait_for_job(
        self,
        job_id: str,
        extract_tables: bool,
        poll_interval: int,
        max_wait_time: int
    ) -> PDFContent:
        """Poll for job completion and return results."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            if extract_tables:
                response = self.client.get_document_analysis(JobId=job_id)
            else:
                response = self.client.get_document_text_detection(JobId=job_id)
            
            status = response["JobStatus"]
            
            if status == "SUCCEEDED":
                # Collect all pages (handle pagination)
                all_responses = [response]
                while "NextToken" in response:
                    if extract_tables:
                        response = self.client.get_document_analysis(
                            JobId=job_id, NextToken=response["NextToken"]
                        )
                    else:
                        response = self.client.get_document_text_detection(
                            JobId=job_id, NextToken=response["NextToken"]
                        )
                    all_responses.append(response)
                
                return self._parse_response(all_responses, extract_tables)
            
            elif status == "FAILED":
                error_msg = response.get("StatusMessage", "Unknown error")
                return PDFContent(
                    total_pages=0,
                    pages=[],
                    full_text="",
                    total_chars=0,
                    metadata={"job_id": job_id},
                    errors=[f"Job failed: {error_msg}"],
                    extraction_method="textract"
                )
            
            logger.info(f"Job {job_id} status: {status}, waiting...")
            time.sleep(poll_interval)
        
        return PDFContent(
            total_pages=0,
            pages=[],
            full_text="",
            total_chars=0,
            metadata={"job_id": job_id},
            errors=[f"Job timed out after {max_wait_time}s"],
            extraction_method="textract"
        )
    
    def _parse_response(
        self,
        responses: List[dict],
        extract_tables: bool
    ) -> PDFContent:
        """Parse Textract response into PDFContent."""
        # Collect all blocks
        all_blocks = []
        for response in responses:
            all_blocks.extend(response.get("Blocks", []))
        
        # Build block map
        block_map = {block["Id"]: block for block in all_blocks}
        
        # Group by page
        pages_data = {}
        max_page = 1
        
        for block in all_blocks:
            page_num = block.get("Page", 1)
            max_page = max(max_page, page_num)
            
            if page_num not in pages_data:
                pages_data[page_num] = {"lines": [], "tables": []}
            
            if block["BlockType"] == "LINE":
                pages_data[page_num]["lines"].append(block["Text"])
            
            elif block["BlockType"] == "TABLE" and extract_tables:
                table = self._extract_table(block, block_map)
                if table:
                    pages_data[page_num]["tables"].append(table)
        
        # Build PageContent list
        pages = []
        for page_num in range(1, max_page + 1):
            data = pages_data.get(page_num, {"lines": [], "tables": []})
            text = "\n".join(data["lines"])
            text = _clean_text(text)
            
            pages.append(PageContent(
                page_number=page_num,
                text=text,
                char_count=len(text),
                tables=data["tables"],
                is_scanned=True
            ))
        
        # Combine all text
        full_text = "\n\n".join([p.text for p in pages if p.text])
        total_chars = sum(p.char_count for p in pages)
        
        return PDFContent(
            total_pages=max_page,
            pages=pages,
            full_text=full_text,
            total_chars=total_chars,
            metadata={},
            errors=[],
            extraction_method="textract"
        )
    
    def _extract_table(self, table_block: dict, block_map: dict) -> List[List[str]]:
        """Extract table as 2D array."""
        rows = {}
        
        if "Relationships" not in table_block:
            return []
        
        for rel in table_block["Relationships"]:
            if rel["Type"] == "CHILD":
                for cell_id in rel["Ids"]:
                    cell = block_map.get(cell_id, {})
                    if cell.get("BlockType") == "CELL":
                        row_idx = cell["RowIndex"]
                        col_idx = cell["ColumnIndex"]
                        cell_text = self._get_text_from_children(cell, block_map)
                        
                        if row_idx not in rows:
                            rows[row_idx] = {}
                        rows[row_idx][col_idx] = cell_text
        
        # Convert to 2D array
        table = []
        for row_idx in sorted(rows.keys()):
            row = []
            for col_idx in sorted(rows[row_idx].keys()):
                row.append(rows[row_idx][col_idx])
            table.append(row)
        
        return table
    
    def _get_text_from_children(self, block: dict, block_map: dict) -> str:
        """Get text from child WORD blocks."""
        if "Relationships" not in block:
            return ""
        
        text_parts = []
        for rel in block["Relationships"]:
            if rel["Type"] == "CHILD":
                for child_id in rel["Ids"]:
                    child = block_map.get(child_id, {})
                    if child.get("BlockType") == "WORD":
                        text_parts.append(child.get("Text", ""))
        
        return " ".join(text_parts)


# ============ UNIFIED EXTRACTOR ============

def extract_pdf_auto(
    file_input: Union[str, Path, bytes, io.BytesIO],
    use_textract_for_scanned: bool = True,
    textract_region: str = "ap-southeast-1"
) -> PDFContent:
    """
    Auto-detect PDF type and extract text using appropriate method.
    
    Args:
        file_input: PDF file (path, bytes, or BytesIO)
        use_textract_for_scanned: Use Textract for scanned PDFs
        textract_region: AWS region for Textract
        
    Returns:
        PDFContent with extracted text
    """
    # First try PyPDF2
    result = extract_text_from_pdf(file_input)
    
    # Check if extraction was successful (has meaningful text)
    avg_chars_per_page = result.total_chars / max(result.total_pages, 1)
    
    if avg_chars_per_page >= 50:
        # Digital PDF - PyPDF2 worked well
        return result
    
    # Scanned PDF - try Textract if enabled
    if use_textract_for_scanned:
        logger.info("Low text content detected, using Textract for scanned PDF")
        
        # Convert input to bytes
        if isinstance(file_input, (str, Path)):
            with open(file_input, "rb") as f:
                pdf_bytes = f.read()
        elif isinstance(file_input, bytes):
            pdf_bytes = file_input
        elif isinstance(file_input, io.BytesIO):
            file_input.seek(0)
            pdf_bytes = file_input.read()
        else:
            return result
        
        extractor = TextractExtractor(region=textract_region)
        return extractor.extract_from_bytes(pdf_bytes, extract_tables=True)
    
    return result
