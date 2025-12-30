"""
Task #18: SQS Worker for Document Processing Pipeline

Worker polls SQS queue và xử lý documents:
S3 Event → SQS → Worker → Extract → Chunk → Embeddings → Qdrant

Supported file types:
- .pdf - PDF documents (Textract/PyPDF2)
- .md - Markdown files (direct text parsing)
- .ipynb - Jupyter Notebooks (JSON parsing)
"""

import json
import time
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from .pdf_detector import detect_pdf_type, PDFType
from .pdf_extractor import extract_text_from_pdf, extract_pdf_auto, TextractExtractor
from app.services.search.text_chunker import chunk_text, chunk_text_with_tables, TextChunk
from .file_processors import ProcessorFactory, SUPPORTED_FILE_TYPES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # For scanned PDFs when Textract not available
    ALREADY_DONE = "already_done"  # Idempotency - already processed


@dataclass
class ProcessingResult:
    """Result of document processing."""
    document_id: str
    status: ProcessingStatus
    chunks_count: int
    total_chars: int
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SQSWorker:
    """
    Worker để process documents từ SQS queue.
    
    Flow:
    1. Receive message từ SQS
    2. Parse S3 event notification
    3. Download PDF từ S3
    4. Detect PDF type (digital/scanned)
    5. Extract text
    6. Chunk text
    7. Generate embeddings (callback)
    8. Store vectors (callback)
    9. Update document status
    10. Delete message từ SQS
    """
    
    def __init__(
        self,
        queue_url: str,
        documents_bucket: str,
        region: str = "ap-southeast-1",
        visibility_timeout: int = 300,
        max_messages: int = 1,
        wait_time: int = 20,
        # Callbacks for embeddings and vector storage
        embeddings_callback: Optional[Callable[[str], list]] = None,
        store_vectors_callback: Optional[Callable[[str, list, list, dict], bool]] = None,
        update_status_callback: Optional[Callable[[str, str, dict], bool]] = None,
    ):
        """
        Initialize SQS Worker.
        
        Args:
            queue_url: SQS queue URL
            documents_bucket: S3 bucket name for documents
            region: AWS region
            visibility_timeout: Message visibility timeout
            max_messages: Max messages to receive per poll
            wait_time: Long polling wait time
            embeddings_callback: Function to generate embeddings (text -> vector)
            store_vectors_callback: Function to store vectors (doc_id, chunks, vectors, metadata)
            update_status_callback: Function to update document status (doc_id, status, metadata)
        """
        self.queue_url = queue_url
        self.documents_bucket = documents_bucket
        self.region = region
        self.visibility_timeout = visibility_timeout
        self.max_messages = max_messages
        self.wait_time = wait_time
        
        # AWS clients
        self.sqs = boto3.client('sqs', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        
        # Callbacks
        self.embeddings_callback = embeddings_callback
        self.store_vectors_callback = store_vectors_callback
        self.update_status_callback = update_status_callback
        
        # Callback to check document status (for idempotency)
        self.get_status_callback: Optional[Callable[[str], Optional[str]]] = None
        
        # Callback to acquire processing lock (for race condition prevention)
        self.acquire_lock_callback: Optional[Callable[[str, str], bool]] = None
        
        # Worker state
        self.running = False
        self.processed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        
        # Worker ID for distributed locking
        import uuid
        self.worker_id = str(uuid.uuid4())[:8]
        logger.info(f"Worker ID: {self.worker_id}")
    
    def start(self, max_iterations: Optional[int] = None):
        """
        Start worker loop.
        
        Args:
            max_iterations: Max iterations (None = infinite)
        """
        self.running = True
        iteration = 0
        
        logger.info(f"Starting SQS Worker for queue: {self.queue_url}")
        
        while self.running:
            if max_iterations and iteration >= max_iterations:
                logger.info(f"Reached max iterations: {max_iterations}")
                break
            
            try:
                messages = self._receive_messages()
                
                if not messages:
                    logger.debug("No messages received, waiting...")
                    continue
                
                for message in messages:
                    self._process_message(message)
                
                iteration += 1
                
            except KeyboardInterrupt:
                logger.info("Received interrupt, stopping worker...")
                self.stop()
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                self.error_count += 1
                time.sleep(5)  # Back off on error
        
        logger.info(f"Worker stopped. Processed: {self.processed_count}, Skipped: {self.skipped_count}, Errors: {self.error_count}")
    
    def stop(self):
        """Stop worker loop."""
        self.running = False
    
    def _receive_messages(self) -> list:
        """Receive messages from SQS queue."""
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=self.max_messages,
                WaitTimeSeconds=self.wait_time,
                VisibilityTimeout=self.visibility_timeout,
                MessageAttributeNames=['All']
            )
            return response.get('Messages', [])
        except ClientError as e:
            logger.error(f"Error receiving messages: {e}")
            return []
    
    def _process_message(self, message: dict):
        """Process a single SQS message."""
        receipt_handle = message['ReceiptHandle']
        
        try:
            # Parse S3 event from message body
            body = json.loads(message['Body'])
            s3_event = self._parse_s3_event(body)
            
            if not s3_event:
                logger.warning("Invalid S3 event, skipping message")
                self._delete_message(receipt_handle)
                return
            
            bucket = s3_event['bucket']
            key = s3_event['key']
            document_id = self._extract_document_id(key, s3_event.get('doc_id'))
            
            logger.info(f"Processing document: {document_id} from s3://{bucket}/{key}")
            
            # IDEMPOTENCY CHECK: Skip if already processed, allow retry from FAILED
            if self.get_status_callback:
                current_status = self.get_status_callback(document_id)
                if current_status in ["EMBEDDING_DONE", "completed"]:
                    logger.info(f"Document {document_id} already processed (status={current_status}), skipping")
                    self._delete_message(receipt_handle)
                    self.skipped_count += 1
                    return
                elif current_status == "FAILED":
                    # Allow retry from FAILED state - reset to allow processing
                    logger.info(f"Document {document_id} was FAILED, retrying...")
            
            # RACE CONDITION PREVENTION: Try to acquire lock
            if self.acquire_lock_callback:
                lock_acquired = self.acquire_lock_callback(document_id, self.worker_id)
                if not lock_acquired:
                    logger.info(f"Document {document_id} is being processed by another worker, skipping")
                    # Don't delete message - let it become visible again for retry
                    self.skipped_count += 1
                    return
            
            # Update status to PROCESSING (valid from UPLOADED, IDP_RUNNING, or FAILED)
            self._update_status(document_id, ProcessingStatus.PROCESSING)
            
            # Process the document
            result = self._process_document(bucket, key, document_id)
            
            # Update final status
            self._update_status(
                document_id, 
                result.status,
                {
                    "chunks_count": result.chunks_count,
                    "total_chars": result.total_chars,
                    "error_message": result.error_message
                }
            )
            
            # Delete message on success
            if result.status in [ProcessingStatus.COMPLETED, ProcessingStatus.SKIPPED]:
                self._delete_message(receipt_handle)
                self.processed_count += 1
            else:
                # Don't delete on failure - let it retry or go to DLQ
                self.error_count += 1
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self.error_count += 1
    
    def _parse_s3_event(self, body: dict) -> Optional[dict]:
        """Parse S3 event notification from SQS message body."""
        try:
            # Handle SNS wrapped messages
            if 'Records' not in body and 'Message' in body:
                body = json.loads(body['Message'])
            
            if 'Records' not in body:
                return None
            
            record = body['Records'][0]
            if 's3' not in record:
                return None
            
            return {
                'bucket': record['s3']['bucket']['name'],
                'key': record['s3']['object']['key'],
                'size': record['s3']['object'].get('size', 0),
                'event_time': record.get('eventTime'),
                'doc_id': body.get('doc_id')  # Get doc_id from message if provided
            }
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing S3 event: {e}")
            return None
    
    def _extract_document_id(self, key: str, doc_id: Optional[str] = None) -> str:
        """Extract document ID from S3 key or use provided doc_id."""
        # Use provided doc_id if available (from admin upload)
        if doc_id:
            return doc_id
        
        # Fallback: try to extract UUID from key format: uploads/{uuid}/{filename}.pdf
        parts = key.split('/')
        if len(parts) >= 2 and parts[0] == 'uploads':
            # Check if second part looks like a UUID
            potential_uuid = parts[1]
            if len(potential_uuid) == 36 and potential_uuid.count('-') == 4:
                return potential_uuid
        
        # Last fallback: use filename without extension
        filename = key.split('/')[-1]
        return filename.rsplit('.', 1)[0]
    
    def _get_file_type(self, key: str, s3_metadata: dict = None) -> str:
        """Determine file type from S3 key or metadata."""
        # Try metadata first (set during upload)
        if s3_metadata and s3_metadata.get("file_type"):
            return s3_metadata["file_type"]
        
        # Fallback to extension from key
        if "." in key:
            ext = "." + key.lower().rsplit(".", 1)[-1]
            if ext in SUPPORTED_FILE_TYPES:
                return ext
        
        # Default to PDF for backward compatibility
        return ".pdf"
    
    def _process_document(
        self, 
        bucket: str, 
        key: str, 
        document_id: str
    ) -> ProcessingResult:
        """
        Process a document: download, extract, chunk, embed, store.
        Supports PDF, Markdown, and Jupyter Notebook files.
        """
        try:
            # 1. Download file from S3
            logger.info(f"Downloading from s3://{bucket}/{key}")
            file_bytes, s3_metadata = self._download_from_s3_with_metadata(bucket, key)
            
            if not file_bytes:
                return ProcessingResult(
                    document_id=document_id,
                    status=ProcessingStatus.FAILED,
                    chunks_count=0,
                    total_chars=0,
                    error_message="Failed to download file from S3"
                )
            
            # 2. Determine file type
            file_type = self._get_file_type(key, s3_metadata)
            logger.info(f"File type: {file_type}")
            
            # 3. Route to appropriate processor
            if file_type == ".pdf":
                return self._process_pdf(file_bytes, bucket, key, document_id)
            elif file_type in [".md", ".ipynb"]:
                return self._process_text_file(file_bytes, file_type, bucket, key, document_id)
            else:
                return ProcessingResult(
                    document_id=document_id,
                    status=ProcessingStatus.FAILED,
                    chunks_count=0,
                    total_chars=0,
                    error_message=f"Unsupported file type: {file_type}"
                )
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            return ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.FAILED,
                chunks_count=0,
                total_chars=0,
                error_message=str(e)
            )
    
    def _process_text_file(
        self,
        file_bytes: bytes,
        file_type: str,
        bucket: str,
        key: str,
        document_id: str
    ) -> ProcessingResult:
        """Process Markdown or Jupyter Notebook files."""
        try:
            # Get processor for file type
            processor = ProcessorFactory.get_processor(file_type)
            filename = key.split("/")[-1]
            
            # Process file
            logger.info(f"Processing {file_type} file with {processor.__class__.__name__}...")
            result = processor.process(file_bytes, filename)
            
            if not result.text:
                return ProcessingResult(
                    document_id=document_id,
                    status=ProcessingStatus.FAILED,
                    chunks_count=0,
                    total_chars=0,
                    error_message=f"No text extracted from {file_type} file"
                )
            
            logger.info(f"Extracted {len(result.text)} chars, {result.page_count} sections")
            
            # Chunk text (use pages/sections as natural boundaries)
            chunks = chunk_text_with_tables(
                text=result.text,
                tables=None,
                rows_per_chunk=5
            )
            logger.info(f"Created {len(chunks)} chunks")
            
            # Generate embeddings
            vectors = []
            if self.embeddings_callback and chunks:
                logger.info("Generating embeddings...")
                for chunk in chunks:
                    try:
                        vector = self.embeddings_callback(chunk.text)
                        vectors.append(vector)
                    except Exception as e:
                        logger.error(f"Error generating embedding: {e}")
                        vectors.append(None)
            
            # Store vectors
            if self.store_vectors_callback and vectors:
                logger.info("Storing vectors...")
                
                chunk_data = []
                for i, chunk in enumerate(chunks):
                    # Map chunk to section/page - improved mapping
                    # For text files, try to find the best matching section
                    section_idx = 0
                    section_title = ""
                    
                    if result.pages:
                        # Find section that contains this chunk based on content overlap
                        # Simple heuristic: use chunk index ratio to estimate section
                        if len(chunks) > 0 and len(result.pages) > 0:
                            ratio = i / len(chunks)
                            section_idx = min(int(ratio * len(result.pages)), len(result.pages) - 1)
                        section_title = result.pages[section_idx].get("title", "")
                    
                    chunk_data.append({
                        "text": chunk.text,
                        "page": section_idx + 1,
                        "section_title": section_title,
                        "is_table": chunk.is_table,
                        "chunk_index": i
                    })
                
                metadata = {
                    "document_id": document_id,
                    "bucket": bucket,
                    "key": key,
                    "file_type": file_type,
                    "total_pages": result.page_count,
                    "file_metadata": result.metadata,  # Contains title, kernel info, etc.
                    "chunk_data": chunk_data
                }
                self.store_vectors_callback(document_id, chunk_data, vectors, metadata)
            
            return ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.COMPLETED,
                chunks_count=len(chunks),
                total_chars=len(result.text),
                metadata={
                    "file_type": file_type,
                    "total_sections": result.page_count,
                    "vectors_generated": len([v for v in vectors if v])
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing {file_type} file: {e}")
            return ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.FAILED,
                chunks_count=0,
                total_chars=0,
                error_message=str(e)
            )
    
    def _process_pdf(
        self,
        pdf_bytes: bytes,
        bucket: str,
        key: str,
        document_id: str
    ) -> ProcessingResult:
        """Process PDF files (original logic)."""
        # 2. Detect PDF type
        pdf_type = detect_pdf_type(pdf_bytes)
        logger.info(f"PDF type detected: {pdf_type}")
        
        if pdf_type == PDFType.UNKNOWN:
            return ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.FAILED,
                chunks_count=0,
                total_chars=0,
                error_message="Unknown PDF type - cannot process"
            )
        
        # 3. Extract text (auto-detect: PyPDF2 for digital, Textract for scanned)
        logger.info("Extracting text from PDF...")
        pdf_content = extract_pdf_auto(
            pdf_bytes, 
            use_textract_for_scanned=True,
            textract_region=self.region
        )
        logger.info(f"Extraction method: {pdf_content.extraction_method}")
        
        if not pdf_content.full_text:
            return ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.FAILED,
                chunks_count=0,
                total_chars=0,
                error_message="No text extracted from PDF"
            )
        
        # 4. Chunk text with table handling
        logger.info("Chunking text with table detection...")
        
        # Collect tables from all pages
        all_tables = []
        table_names = []
        for page in pdf_content.pages:
            if page.tables:
                for i, table in enumerate(page.tables):
                    all_tables.append(table)
                    table_names.append(f"Table (Page {page.page_number}, #{i+1})")
        
        if all_tables:
            logger.info(f"Found {len(all_tables)} tables, using row-based chunking with header injection")
            chunks = chunk_text_with_tables(
                text=pdf_content.full_text,
                tables=all_tables,
                table_names=table_names,
                rows_per_chunk=5  # 5 rows per table chunk
            )
        else:
            # No tables from extractor, try to detect in text
            chunks = chunk_text_with_tables(
                text=pdf_content.full_text,
                tables=None,  # Will auto-detect
                rows_per_chunk=5
            )
        
        # Count table vs text chunks
        table_chunks = [c for c in chunks if c.is_table]
        text_chunks = [c for c in chunks if not c.is_table]
        logger.info(f"Created {len(chunks)} chunks ({len(table_chunks)} table, {len(text_chunks)} text)")
        
        # 5. Generate embeddings (if callback provided)
        vectors = []
        if self.embeddings_callback and chunks:
            logger.info("Generating embeddings...")
            for chunk in chunks:
                try:
                    vector = self.embeddings_callback(chunk.text)
                    vectors.append(vector)
                except Exception as e:
                    logger.error(f"Error generating embedding: {e}")
                    vectors.append(None)
        
        # 6. Store vectors (if callback provided)
        if self.store_vectors_callback and vectors:
            logger.info("Storing vectors...")
            
            # Build chunk data with page info
            chunk_data = []
            for i, chunk in enumerate(chunks):
                # Estimate page from character position
                # Assume ~3000 chars per page for digital PDFs
                estimated_page = (chunk.start_char // 3000) + 1 if chunk.start_char > 0 else 1
                estimated_page = min(estimated_page, pdf_content.total_pages)
                
                chunk_data.append({
                    "text": chunk.text,
                    "page": estimated_page,
                    "is_table": chunk.is_table,
                    "chunk_index": i
                })
            
            metadata = {
                "document_id": document_id,
                "bucket": bucket,
                "key": key,
                "file_type": ".pdf",
                "total_pages": pdf_content.total_pages,
                "pdf_metadata": pdf_content.metadata,
                "chunk_data": chunk_data  # Include page info
            }
            self.store_vectors_callback(document_id, chunk_data, vectors, metadata)
        
        return ProcessingResult(
            document_id=document_id,
            status=ProcessingStatus.COMPLETED,
            chunks_count=len(chunks),
            total_chars=pdf_content.total_chars,
            metadata={
                "file_type": ".pdf",
                "total_pages": pdf_content.total_pages,
                "vectors_generated": len([v for v in vectors if v])
            }
        )
    
    def _download_from_s3(self, bucket: str, key: str) -> Optional[bytes]:
        """Download file from S3."""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
            return None
    
    def _download_from_s3_with_metadata(self, bucket: str, key: str) -> tuple[Optional[bytes], dict]:
        """Download file from S3 with metadata."""
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read()
            metadata = response.get('Metadata', {})
            return content, metadata
        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
            return None, {}
    
    def _delete_message(self, receipt_handle: str):
        """Delete message from SQS queue."""
        try:
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
        except ClientError as e:
            logger.error(f"Error deleting message: {e}")
    
    def _update_status(
        self, 
        document_id: str, 
        status: ProcessingStatus,
        metadata: Optional[dict] = None
    ):
        """Update document status via callback."""
        if self.update_status_callback:
            try:
                self.update_status_callback(document_id, status.value, metadata or {})
            except Exception as e:
                logger.error(f"Error updating status: {e}")


def process_single_document(
    bucket: str,
    key: str,
    region: str = "ap-southeast-1"
) -> ProcessingResult:
    """
    Process a single document without SQS.
    Useful for testing or manual processing.
    """
    worker = SQSWorker(
        queue_url="",  # Not used
        documents_bucket=bucket,
        region=region
    )
    
    document_id = worker._extract_document_id(key)
    return worker._process_document(bucket, key, document_id)
