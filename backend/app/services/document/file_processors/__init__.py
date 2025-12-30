"""
File Processors Module

Provides processors for different file types:
- PDF: Uses Textract for extraction
- Markdown: Direct text parsing with section splitting
- Jupyter Notebook: JSON parsing with cell extraction
"""

from .base import BaseFileProcessor, ProcessedContent
from .markdown_processor import MarkdownProcessor
from .jupyter_processor import JupyterProcessor

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
        "processor": "markdown"
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
        # PDF uses Textract, handled separately in sqs_worker
    }
    
    @classmethod
    def get_processor(cls, file_type: str) -> BaseFileProcessor:
        """Get processor instance for file type."""
        processor_class = cls._processors.get(file_type.lower())
        if not processor_class:
            raise ValueError(f"No processor for file type: {file_type}")
        return processor_class()
    
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
    "ProcessorFactory",
    "SUPPORTED_FILE_TYPES",
]
