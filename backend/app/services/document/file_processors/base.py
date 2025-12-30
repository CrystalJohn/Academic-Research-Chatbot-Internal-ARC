"""
Base File Processor

Abstract base class for all file processors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProcessedContent:
    """Result of file processing."""
    
    text: str  # Full extracted text
    metadata: dict = field(default_factory=dict)  # File metadata
    pages: List[dict] = field(default_factory=list)  # Logical sections/pages
    
    @property
    def page_count(self) -> int:
        """Number of pages/sections."""
        return len(self.pages)
    
    def get_text_by_page(self, page_index: int) -> Optional[str]:
        """Get text content for a specific page/section."""
        if 0 <= page_index < len(self.pages):
            return self.pages[page_index].get("content", "")
        return None


class BaseFileProcessor(ABC):
    """Abstract base class for file processors."""
    
    @abstractmethod
    def process(self, content: bytes, filename: str) -> ProcessedContent:
        """
        Process file content and return extracted text.
        
        Args:
            content: Raw file bytes
            filename: Original filename
            
        Returns:
            ProcessedContent with extracted text and metadata
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions (e.g., ['.md', '.markdown'])."""
        pass
    
    def can_process(self, filename: str) -> bool:
        """Check if this processor can handle the file."""
        if not filename:
            return False
        ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        return ext in self.get_supported_extensions()
