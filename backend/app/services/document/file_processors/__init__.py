"""
File Processors Module

Provides processors for different file types:
- PDF: Uses Textract for extraction
- Markdown: Direct text parsing with section splitting
- Syllabus: Semantic chunking for FPT University syllabi
- Jupyter Notebook: JSON parsing with cell extraction
"""

from .base import BaseFileProcessor, ProcessedContent
from .markdown_processor import MarkdownProcessor
from .jupyter_processor import JupyterProcessor
from .syllabus_processor import SyllabusProcessor, is_syllabus_file

# Supported file types configuration
SUPPORTED_FILE_TYPES = {
    ".pdf": {
        "mime_types": ["application/pdf"],
        "content_type": "application/pdf",
        "processor": "textract"
    },
    ".md": {
        "mime_types": ["text/markdown", "text/plain", "text/x-markdown"],
        "content_type": "text/markdown",
        "processor": "markdown"  # Will auto-detect syllabus
    },
    ".ipynb": {
        "mime_types": ["application/json", "application/x-ipynb+json"],
        "content_type": "application/json",
        "processor": "jupyter"
    }
}


class ProcessorFactory:
    """Factory for creating file processors."""
    
    _processors = {
        ".md": MarkdownProcessor,
        ".ipynb": JupyterProcessor,
        "syllabus": SyllabusProcessor,  # Special processor for syllabi
        # PDF uses Textract, handled separately in sqs_worker
    }
    
    @classmethod
    def get_processor(cls, file_type: str, filename: str = None, content: bytes = None) -> BaseFileProcessor:
        """
        Get processor instance for file type.
        
        For .md files, auto-detects if it's a syllabus and uses SyllabusProcessor.
        """
        file_type_lower = file_type.lower()
        
        # Auto-detect syllabus for markdown files
        if file_type_lower == ".md" and (filename or content):
            if is_syllabus_file(filename or "", content):
                return cls._processors["syllabus"]()
        
        processor_class = cls._processors.get(file_type_lower)
        if not processor_class:
            raise ValueError(f"No processor for file type: {file_type}")
        return processor_class()
    
    @classmethod
    def get_syllabus_processor(cls) -> SyllabusProcessor:
        """Get syllabus processor directly."""
        return SyllabusProcessor()
    
    @classmethod
    def get_supported_types(cls) -> list[str]:
        """Get list of all supported file extensions."""
        return list(SUPPORTED_FILE_TYPES.keys())
    
    @classmethod
    def is_supported(cls, filename: str) -> bool:
        """Check if file type is supported."""
        if not filename:
            return False
        ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        return ext in SUPPORTED_FILE_TYPES
    
    @classmethod
    def get_file_config(cls, filename: str) -> dict | None:
        """Get configuration for file type."""
        if not filename:
            return None
        ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        return SUPPORTED_FILE_TYPES.get(ext)


__all__ = [
    "BaseFileProcessor",
    "ProcessedContent", 
    "MarkdownProcessor",
    "JupyterProcessor",
    "SyllabusProcessor",
    "ProcessorFactory",
    "SUPPORTED_FILE_TYPES",
    "is_syllabus_file",
]
