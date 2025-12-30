"""
Markdown File Processor

Processes .md files by extracting text and splitting into sections by headers.
"""

import re
from typing import List
from .base import BaseFileProcessor, ProcessedContent


class MarkdownProcessor(BaseFileProcessor):
    """Processor for Markdown files."""
    
    def get_supported_extensions(self) -> List[str]:
        return [".md", ".markdown"]
    
    def process(self, content: bytes, filename: str) -> ProcessedContent:
        """
        Process markdown file content.
        
        Args:
            content: Raw markdown bytes
            filename: Original filename
            
        Returns:
            ProcessedContent with text split into sections by headers
        """
        # Decode content
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
        
        # Extract sections by headers
        sections = self._split_by_headers(text)
        
        # Extract title from first H1 or filename
        title = self._extract_title(text, filename)
        
        return ProcessedContent(
            text=text,
            metadata={
                "filename": filename,
                "file_type": ".md",
                "processor": "markdown",
                "title": title,
                "section_count": len(sections),
                "char_count": len(text),
                "word_count": len(text.split()),
            },
            pages=sections
        )
    
    def _extract_title(self, text: str, filename: str) -> str:
        """Extract title from first H1 header or use filename."""
        match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        # Fallback to filename without extension
        return filename.rsplit(".", 1)[0] if "." in filename else filename
    
    def _split_by_headers(self, text: str) -> List[dict]:
        """
        Split markdown content by headers.
        
        Returns list of sections with:
        - index: Section index
        - title: Header text
        - level: Header level (1-6)
        - content: Section content
        """
        sections = []
        current_section = {
            "index": 0,
            "title": "Introduction",
            "level": 0,
            "content": ""
        }
        
        lines = text.split("\n")
        
        for line in lines:
            # Check for ATX-style headers (# Header)
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if header_match:
                # Save current section if it has content
                if current_section["content"].strip():
                    sections.append(current_section)
                
                # Start new section
                current_section = {
                    "index": len(sections),
                    "title": header_match.group(2).strip(),
                    "level": len(header_match.group(1)),
                    "content": ""
                }
            else:
                current_section["content"] += line + "\n"
        
        # Don't forget the last section
        if current_section["content"].strip():
            sections.append(current_section)
        
        # If no sections found, create one with all content
        if not sections:
            sections.append({
                "index": 0,
                "title": "Content",
                "level": 0,
                "content": text
            })
        
        return sections
