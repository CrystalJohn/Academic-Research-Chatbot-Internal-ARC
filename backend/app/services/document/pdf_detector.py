"""
Task #14: PDF Detection - Digital vs Scanned

Phân biệt PDF digital (có text) và scanned (ảnh) để chọn
phương pháp extract text phù hợp:
- Digital: PyPDF2 (nhanh, miễn phí)
- Scanned: Textract OCR (chậm, tốn tiền)
"""

import io
from enum import Enum
from typing import Union
from pathlib import Path

import PyPDF2


class PDFType(str, Enum):
    """Loại PDF"""
    DIGITAL = "digital"    # Text có thể extract bằng PyPDF2
    SCANNED = "scanned"    # Cần OCR (Textract)
    UNKNOWN = "unknown"    # Không xác định được


# Ngưỡng tối thiểu characters/page để coi là digital PDF
MIN_CHARS_PER_PAGE = 50

# Số trang sample để kiểm tra (không cần check hết)
SAMPLE_PAGES = 3


def detect_pdf_type(
    file_input: Union[str, Path, bytes, io.BytesIO],
    min_chars_per_page: int = MIN_CHARS_PER_PAGE,
    sample_pages: int = SAMPLE_PAGES
) -> PDFType:
    """
    Phát hiện loại PDF: digital hay scanned.
    
    Args:
        file_input: Đường dẫn file, bytes, hoặc BytesIO
        min_chars_per_page: Ngưỡng tối thiểu chars/page
        sample_pages: Số trang để sample check
        
    Returns:
        PDFType.DIGITAL nếu có extractable text
        PDFType.SCANNED nếu không có text (cần OCR)
        PDFType.UNKNOWN nếu có lỗi
    """
    try:
        # Mở PDF reader
        reader = _get_pdf_reader(file_input)
        
        if reader is None:
            return PDFType.UNKNOWN
        
        total_pages = len(reader.pages)
        if total_pages == 0:
            return PDFType.UNKNOWN
        
        # Sample một số trang để check
        pages_to_check = min(sample_pages, total_pages)
        total_chars = 0
        
        for i in range(pages_to_check):
            page = reader.pages[i]
            text = page.extract_text() or ""
            # Loại bỏ whitespace để đếm chars thực
            text = text.strip()
            total_chars += len(text)
        
        # Tính trung bình chars/page
        avg_chars_per_page = total_chars / pages_to_check
        
        if avg_chars_per_page >= min_chars_per_page:
            return PDFType.DIGITAL
        else:
            return PDFType.SCANNED
            
    except Exception as e:
        print(f"Error detecting PDF type: {e}")
        return PDFType.UNKNOWN


def _get_pdf_reader(
    file_input: Union[str, Path, bytes, io.BytesIO]
) -> PyPDF2.PdfReader:
    """
    Tạo PdfReader từ nhiều loại input khác nhau.
    """
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


def get_pdf_info(file_input: Union[str, Path, bytes, io.BytesIO]) -> dict:
    """
    Lấy thông tin chi tiết về PDF.
    
    Returns:
        dict với các thông tin:
        - pdf_type: digital/scanned/unknown
        - total_pages: số trang
        - avg_chars_per_page: trung bình chars/page
        - sample_text: text mẫu từ trang đầu
    """
    result = {
        "pdf_type": PDFType.UNKNOWN,
        "total_pages": 0,
        "avg_chars_per_page": 0,
        "sample_text": "",
        "error": None
    }
    
    try:
        reader = _get_pdf_reader(file_input)
        if reader is None:
            result["error"] = "Cannot read PDF file"
            return result
        
        total_pages = len(reader.pages)
        result["total_pages"] = total_pages
        
        if total_pages == 0:
            result["error"] = "PDF has no pages"
            return result
        
        # Extract text từ trang đầu
        first_page_text = reader.pages[0].extract_text() or ""
        result["sample_text"] = first_page_text[:500]  # Lấy 500 chars đầu
        
        # Tính avg chars
        pages_to_check = min(SAMPLE_PAGES, total_pages)
        total_chars = 0
        
        for i in range(pages_to_check):
            text = reader.pages[i].extract_text() or ""
            total_chars += len(text.strip())
        
        avg_chars = total_chars / pages_to_check
        result["avg_chars_per_page"] = round(avg_chars, 2)
        
        # Xác định loại
        if avg_chars >= MIN_CHARS_PER_PAGE:
            result["pdf_type"] = PDFType.DIGITAL
        else:
            result["pdf_type"] = PDFType.SCANNED
            
    except Exception as e:
        result["error"] = str(e)
        result["pdf_type"] = PDFType.UNKNOWN
    
    return result


# Convenience function
def is_digital_pdf(file_input: Union[str, Path, bytes, io.BytesIO]) -> bool:
    """Kiểm tra nhanh PDF có phải digital không."""
    return detect_pdf_type(file_input) == PDFType.DIGITAL


def is_scanned_pdf(file_input: Union[str, Path, bytes, io.BytesIO]) -> bool:
    """Kiểm tra nhanh PDF có phải scanned không."""
    return detect_pdf_type(file_input) == PDFType.SCANNED
