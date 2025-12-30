"""
Jupyter Notebook Processor

Processes .ipynb files by extracting markdown and code cells.
"""

import json
from typing import List
from .base import BaseFileProcessor, ProcessedContent


class JupyterProcessor(BaseFileProcessor):
    """Processor for Jupyter Notebook files."""
    
    def get_supported_extensions(self) -> List[str]:
        return [".ipynb"]
    
    def process(self, content: bytes, filename: str) -> ProcessedContent:
        """
        Process Jupyter notebook content.
        
        Args:
            content: Raw notebook JSON bytes
            filename: Original filename
            
        Returns:
            ProcessedContent with cells as pages
        """
        # Parse JSON
        try:
            text_content = content.decode("utf-8")
            notebook = json.loads(text_content)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return ProcessedContent(
                text="",
                metadata={
                    "filename": filename,
                    "file_type": ".ipynb",
                    "processor": "jupyter",
                    "error": f"Failed to parse notebook: {str(e)}"
                },
                pages=[]
            )
        
        cells = notebook.get("cells", [])
        extracted_text = []
        pages = []
        
        markdown_count = 0
        code_count = 0
        
        for idx, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "")
            source = self._get_cell_source(cell)
            
            if cell_type == "markdown":
                markdown_count += 1
                extracted_text.append(source)
                pages.append({
                    "index": idx,
                    "type": "markdown",
                    "content": source
                })
                
            elif cell_type == "code":
                code_count += 1
                # Format code with markdown code block
                language = self._get_kernel_language(notebook)
                code_text = f"```{language}\n{source}\n```"
                extracted_text.append(code_text)
                
                # Extract outputs
                outputs = self._extract_outputs(cell.get("outputs", []))
                if outputs:
                    extracted_text.append(f"Output:\n{outputs}")
                
                pages.append({
                    "index": idx,
                    "type": "code",
                    "content": source,
                    "language": language,
                    "outputs": outputs
                })
            
            elif cell_type == "raw":
                # Include raw cells as-is
                extracted_text.append(source)
                pages.append({
                    "index": idx,
                    "type": "raw",
                    "content": source
                })
        
        # Extract notebook title
        title = self._extract_title(notebook, pages, filename)
        
        # Get kernel info
        kernel_info = notebook.get("metadata", {}).get("kernelspec", {})
        
        return ProcessedContent(
            text="\n\n".join(extracted_text),
            metadata={
                "filename": filename,
                "file_type": ".ipynb",
                "processor": "jupyter",
                "title": title,
                "cell_count": len(cells),
                "markdown_cells": markdown_count,
                "code_cells": code_count,
                "kernel_name": kernel_info.get("name", "unknown"),
                "kernel_display_name": kernel_info.get("display_name", "Unknown"),
                "language": self._get_kernel_language(notebook),
            },
            pages=pages
        )
    
    def _get_cell_source(self, cell: dict) -> str:
        """Extract source text from cell."""
        source = cell.get("source", [])
        if isinstance(source, list):
            return "".join(source)
        return str(source)
    
    def _get_kernel_language(self, notebook: dict) -> str:
        """Get programming language from kernel info."""
        metadata = notebook.get("metadata", {})
        
        # Try kernelspec
        kernelspec = metadata.get("kernelspec", {})
        language = kernelspec.get("language", "")
        if language:
            return language.lower()
        
        # Try language_info
        lang_info = metadata.get("language_info", {})
        language = lang_info.get("name", "")
        if language:
            return language.lower()
        
        # Default to python
        return "python"
    
    def _extract_title(self, notebook: dict, pages: List[dict], filename: str) -> str:
        """Extract title from first markdown cell H1 or filename."""
        # Check first markdown cell for H1
        for page in pages:
            if page.get("type") == "markdown":
                content = page.get("content", "")
                lines = content.split("\n")
                for line in lines:
                    if line.startswith("# "):
                        return line[2:].strip()
                break
        
        # Fallback to filename without extension
        return filename.rsplit(".", 1)[0] if "." in filename else filename
    
    def _extract_outputs(self, outputs: list) -> str:
        """Extract text from cell outputs."""
        result = []
        
        for output in outputs:
            output_type = output.get("output_type", "")
            
            if output_type == "stream":
                # stdout/stderr
                text = output.get("text", [])
                if isinstance(text, list):
                    result.append("".join(text))
                else:
                    result.append(str(text))
                    
            elif output_type in ["execute_result", "display_data"]:
                # Rich output
                data = output.get("data", {})
                
                # Prefer plain text
                if "text/plain" in data:
                    text = data["text/plain"]
                    if isinstance(text, list):
                        result.append("".join(text))
                    else:
                        result.append(str(text))
                        
            elif output_type == "error":
                # Error output
                ename = output.get("ename", "Error")
                evalue = output.get("evalue", "")
                result.append(f"{ename}: {evalue}")
        
        return "\n".join(result)
