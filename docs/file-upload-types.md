# File Upload Types - Implementation Guide

## 📋 Overview

Mở rộng hệ thống upload để hỗ trợ thêm các định dạng file ngoài PDF:
- `.pdf` - PDF documents (hiện tại)
- `.md` - Markdown files (mới)
- `.ipynb` - Jupyter Notebooks (mới)

---

## 🎯 Current Implementation (PDF Only)

### Backend Validation
```python
# backend/app/api/admin.py
if not file.filename or not file.filename.lower().endswith(".pdf"):
    raise HTTPException(status_code=400, detail="Only PDF files are allowed")
```

### Frontend Validation
```jsx
// src/pages/AdminPage.jsx
<input type="file" accept=".pdf" multiple />

// Filter logic
const pdfFiles = files.filter(
  (f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
)
```

### S3 Storage
```
uploads/{doc_id}/{filename}.pdf
```

### Processing Pipeline
```
S3 Upload → SQS → Textract (PDF only) → Chunking → Embedding → Qdrant
```

---

## 🚀 New Implementation Plan

### 1. Supported File Types

| Extension | MIME Type | Content Type | Processing Method |
|-----------|-----------|--------------|-------------------|
| `.pdf` | `application/pdf` | PDF Document | Textract |
| `.md` | `text/markdown` | Markdown | Direct text parsing |
| `.ipynb` | `application/json` | Jupyter Notebook | JSON parsing + cell extraction |

### 2. Backend Changes

#### 2.1 Update File Validation (`backend/app/api/admin.py`)

```python
# Supported file types configuration
SUPPORTED_FILE_TYPES = {
    ".pdf": {
        "mime_types": ["application/pdf"],
        "content_type": "application/pdf",
        "processor": "textract"
    },
    ".md": {
        "mime_types": ["text/markdown", "text/plain"],
        "content_type": "text/markdown",
        "processor": "markdown"
    },
    ".ipynb": {
        "mime_types": ["application/json", "application/x-ipynb+json"],
        "content_type": "application/json",
        "processor": "jupyter"
    }
}

def validate_file_type(filename: str) -> tuple[str, dict]:
    """Validate and return file extension and config."""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    ext = os.path.splitext(filename.lower())[1]
    if ext not in SUPPORTED_FILE_TYPES:
        supported = ", ".join(SUPPORTED_FILE_TYPES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {supported}"
        )
    
    return ext, SUPPORTED_FILE_TYPES[ext]
```

#### 2.2 Update Upload Endpoint

```python
@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    admin_user: CurrentUser = Depends(require_admin),
):
    # Validate file type
    ext, file_config = validate_file_type(file.filename)
    
    # ... rest of upload logic
    
    # Store file type in metadata
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=content,
        ContentType=file_config["content_type"],
        Metadata={
            "doc_id": doc_id,
            "uploaded_by": uploaded_by,
            "file_type": ext,
            "processor": file_config["processor"]
        }
    )
```

#### 2.3 Update DynamoDB Schema

```python
# Add file_type field to document record
status_manager.create_document(
    doc_id=doc_id,
    filename=file.filename,
    uploaded_by=uploaded_by,
    file_type=ext,  # NEW: .pdf, .md, .ipynb
    processor=file_config["processor"]  # NEW: textract, markdown, jupyter
)
```

### 3. Processing Pipeline Changes

#### 3.1 Create File Processors (`backend/app/services/file_processors/`)

```
backend/app/services/file_processors/
├── __init__.py
├── base.py          # Abstract base class
├── pdf_processor.py # Textract processing
├── markdown_processor.py
└── jupyter_processor.py
```

#### 3.2 Base Processor Interface

```python
# backend/app/services/file_processors/base.py
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class ProcessedContent:
    text: str
    metadata: dict
    pages: List[dict]  # For PDF: actual pages, for others: logical sections

class BaseFileProcessor(ABC):
    @abstractmethod
    async def process(self, content: bytes, filename: str) -> ProcessedContent:
        """Process file content and return extracted text."""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        pass
```

#### 3.3 Markdown Processor

```python
# backend/app/services/file_processors/markdown_processor.py
import re
from .base import BaseFileProcessor, ProcessedContent

class MarkdownProcessor(BaseFileProcessor):
    def get_supported_extensions(self) -> list[str]:
        return [".md"]
    
    async def process(self, content: bytes, filename: str) -> ProcessedContent:
        text = content.decode("utf-8")
        
        # Extract sections by headers
        sections = self._split_by_headers(text)
        
        return ProcessedContent(
            text=text,
            metadata={
                "filename": filename,
                "type": "markdown",
                "section_count": len(sections)
            },
            pages=sections
        )
    
    def _split_by_headers(self, text: str) -> list[dict]:
        """Split markdown by headers (##, ###, etc.)"""
        sections = []
        current_section = {"title": "Introduction", "content": "", "level": 0}
        
        for line in text.split("\n"):
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                if current_section["content"].strip():
                    sections.append(current_section)
                current_section = {
                    "title": header_match.group(2),
                    "content": "",
                    "level": len(header_match.group(1))
                }
            else:
                current_section["content"] += line + "\n"
        
        if current_section["content"].strip():
            sections.append(current_section)
        
        return sections
```

#### 3.4 Jupyter Notebook Processor

```python
# backend/app/services/file_processors/jupyter_processor.py
import json
from .base import BaseFileProcessor, ProcessedContent

class JupyterProcessor(BaseFileProcessor):
    def get_supported_extensions(self) -> list[str]:
        return [".ipynb"]
    
    async def process(self, content: bytes, filename: str) -> ProcessedContent:
        notebook = json.loads(content.decode("utf-8"))
        
        cells = notebook.get("cells", [])
        extracted_text = []
        pages = []
        
        for idx, cell in enumerate(cells):
            cell_type = cell.get("cell_type", "")
            source = "".join(cell.get("source", []))
            
            if cell_type == "markdown":
                extracted_text.append(source)
                pages.append({
                    "index": idx,
                    "type": "markdown",
                    "content": source
                })
            elif cell_type == "code":
                # Include code with context
                code_text = f"```python\n{source}\n```"
                extracted_text.append(code_text)
                
                # Include outputs if available
                outputs = self._extract_outputs(cell.get("outputs", []))
                if outputs:
                    extracted_text.append(f"Output:\n{outputs}")
                
                pages.append({
                    "index": idx,
                    "type": "code",
                    "content": source,
                    "outputs": outputs
                })
        
        return ProcessedContent(
            text="\n\n".join(extracted_text),
            metadata={
                "filename": filename,
                "type": "jupyter",
                "cell_count": len(cells),
                "kernel": notebook.get("metadata", {}).get("kernelspec", {}).get("name", "unknown")
            },
            pages=pages
        )
    
    def _extract_outputs(self, outputs: list) -> str:
        """Extract text from cell outputs."""
        result = []
        for output in outputs:
            if output.get("output_type") == "stream":
                result.append("".join(output.get("text", [])))
            elif output.get("output_type") in ["execute_result", "display_data"]:
                data = output.get("data", {})
                if "text/plain" in data:
                    result.append("".join(data["text/plain"]))
        return "\n".join(result)
```

#### 3.5 Processor Factory

```python
# backend/app/services/file_processors/__init__.py
from .base import BaseFileProcessor, ProcessedContent
from .pdf_processor import PDFProcessor
from .markdown_processor import MarkdownProcessor
from .jupyter_processor import JupyterProcessor

class ProcessorFactory:
    _processors = {
        ".pdf": PDFProcessor,
        ".md": MarkdownProcessor,
        ".ipynb": JupyterProcessor,
    }
    
    @classmethod
    def get_processor(cls, file_type: str) -> BaseFileProcessor:
        processor_class = cls._processors.get(file_type)
        if not processor_class:
            raise ValueError(f"No processor for file type: {file_type}")
        return processor_class()
    
    @classmethod
    def get_supported_types(cls) -> list[str]:
        return list(cls._processors.keys())
```

### 4. Frontend Changes

#### 4.1 Update File Input (`src/pages/AdminPage.jsx`)

```jsx
// Supported file types
const SUPPORTED_EXTENSIONS = ['.pdf', '.md', '.ipynb'];
const ACCEPT_STRING = SUPPORTED_EXTENSIONS.join(',');

// Update input
<input 
  type="file" 
  accept={ACCEPT_STRING}  // ".pdf,.md,.ipynb"
  multiple 
  onChange={handleFileInput} 
/>

// Update filter logic
const handleFiles = async (files) => {
  const validFiles = files.filter((f) => {
    const ext = f.name.toLowerCase().split('.').pop();
    return SUPPORTED_EXTENSIONS.includes(`.${ext}`);
  });
  
  if (validFiles.length === 0) {
    return alert(`Please select valid files: ${SUPPORTED_EXTENSIONS.join(', ')}`);
  }
  // ... rest of upload logic
};
```

#### 4.2 Update UI Text

```jsx
// Upload area text
<p className="text-gray-800 font-medium mb-1">
  Drag & drop files here
</p>
<p className="text-sm text-gray-500 mb-4">
  Supports: PDF, Markdown (.md), Jupyter Notebooks (.ipynb). Max: 50MB
</p>

// Empty state
<p className="text-sm text-gray-400 mt-1">
  Upload PDF, Markdown, or Jupyter files to get started
</p>
```

#### 4.3 File Type Icons

```jsx
const getFileIcon = (filename) => {
  const ext = filename.toLowerCase().split('.').pop();
  switch (ext) {
    case 'pdf':
      return <PDFIcon className="text-red-600" />;
    case 'md':
      return <MarkdownIcon className="text-blue-600" />;
    case 'ipynb':
      return <JupyterIcon className="text-orange-500" />;
    default:
      return <FileIcon className="text-gray-400" />;
  }
};
```

### 5. SQS Worker Updates

```python
# backend/app/services/sqs_worker.py

async def process_document(self, s3_key: str, doc_id: str):
    # Get file from S3
    response = self.s3_client.get_object(Bucket=self.bucket, Key=s3_key)
    content = response["Body"].read()
    metadata = response.get("Metadata", {})
    
    # Determine processor based on file type
    file_type = metadata.get("file_type", ".pdf")
    processor = ProcessorFactory.get_processor(file_type)
    
    # Process file
    result = await processor.process(content, s3_key.split("/")[-1])
    
    # Continue with chunking and embedding
    chunks = self.chunker.chunk(result.text, result.pages)
    embeddings = await self.embedder.embed(chunks)
    await self.qdrant.store(doc_id, chunks, embeddings)
```

---

## 📁 Files Modified

### Backend ✅ DONE
- [x] `backend/app/api/admin.py` - Updated validation & upload for .pdf, .md, .ipynb
- [x] `backend/app/services/document_status_manager.py` - Added file_type, processor fields
- [x] `backend/app/services/sqs_worker.py` - Routes to correct processor based on file type
- [x] `backend/app/services/file_processors/` - Created directory with:
  - `__init__.py` - ProcessorFactory, SUPPORTED_FILE_TYPES
  - `base.py` - BaseFileProcessor, ProcessedContent
  - `markdown_processor.py` - MarkdownProcessor
  - `jupyter_processor.py` - JupyterProcessor

### Frontend ✅ DONE
- [x] `src/pages/AdminPage.jsx` - Updated:
  - Accept types: `.pdf,.md,.ipynb`
  - File type badges with colors (PDF=red, MD=blue, IPYNB=orange)
  - Updated UI text and empty state
  - File validation for supported types
- [x] `src/services/adminService.js` - No changes needed

### Infrastructure
- [ ] `terraform/modules/s3/main.tf` - Update S3 event filter (optional)

---

## 🧪 Testing Checklist

- [ ] Upload PDF - should work as before
- [ ] Upload .md file - should extract text correctly
- [ ] Upload .ipynb file - should extract markdown + code cells
- [ ] Upload unsupported file (.txt, .docx) - should reject
- [ ] Large file handling (>10MB)
- [ ] Unicode filename support
- [ ] Search results include new file types

---

## 🔮 Future Extensions

Potential additional file types:
- `.txt` - Plain text files
- `.docx` - Word documents (requires python-docx)
- `.html` - HTML pages (requires BeautifulSoup)
- `.csv` / `.xlsx` - Spreadsheets (requires pandas)
- `.json` - JSON data files
