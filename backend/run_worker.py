"""
Run SQS Worker for IDP Pipeline

Usage: python run_worker.py [max_iterations]

Full pipeline:
1. Receive SQS message
2. Download PDF from S3
3. Extract text (PyPDF2 for digital, skip scanned)
4. Chunk text
5. Generate embeddings (Cohere via Bedrock)
6. Store vectors in Qdrant
7. Update status in DynamoDB
"""
import os
import sys
import logging

# Set default region
os.environ.setdefault("AWS_REGION", "ap-southeast-1")

from app.services.sqs_worker import SQSWorker
from app.services.embedding_service import CohereEmbeddingService
from app.services.qdrant_client import QdrantVectorStore
from app.services.document_status_manager import DocumentStatusManager, DocumentStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
QUEUE_URL = os.getenv(
    "SQS_QUEUE_URL",
    "https://sqs.ap-southeast-1.amazonaws.com/427995028618/arc-chatbot-dev-document-processing"
)
BUCKET = os.getenv("S3_BUCKET", "arc-chatbot-documents-427995028618")
REGION = os.getenv("AWS_REGION", "ap-southeast-1")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))


def create_callbacks():
    """Create callback functions for the worker."""
    
    # Initialize services
    embedding_service = CohereEmbeddingService(region=REGION)
    qdrant_store = QdrantVectorStore(host=QDRANT_HOST, port=QDRANT_PORT)
    status_manager = DocumentStatusManager(region_name=REGION)
    
    # Ensure Qdrant collection exists
    qdrant_store.ensure_collection()
    
    def embeddings_callback(text: str):
        """Generate embedding for text."""
        return embedding_service.embed_text(text)
    
    def store_vectors_callback(doc_id: str, chunks: list, vectors: list, metadata: dict):
        """Store vectors in Qdrant with page metadata and document metadata."""
        # Filter out None vectors
        valid_data = [(c, v) for c, v in zip(chunks, vectors) if v is not None]
        if not valid_data:
            logger.warning(f"No valid vectors to store for {doc_id}")
            return False
        
        valid_chunks, valid_vectors = zip(*valid_data)
        
        # Extract texts, pages, and is_table flags from chunk data
        if isinstance(valid_chunks[0], dict):
            # New format with page info
            texts = [c["text"] for c in valid_chunks]
            pages = [c.get("page", 1) for c in valid_chunks]
            is_tables = [c.get("is_table", False) for c in valid_chunks]
            section_titles = [c.get("section_title", "") for c in valid_chunks]
        else:
            # Legacy format (just strings)
            texts = list(valid_chunks)
            pages = None
            is_tables = None
            section_titles = None
        
        # Extract document-level metadata
        file_type = metadata.get("file_type", "")
        s3_key = metadata.get("key", "")
        filename = s3_key.split("/")[-1] if s3_key else ""
        
        # Get title from file_metadata (for .md, .ipynb) or pdf_metadata
        file_metadata = metadata.get("file_metadata", {}) or metadata.get("pdf_metadata", {})
        title = file_metadata.get("title", "") if isinstance(file_metadata, dict) else ""
        
        try:
            count = qdrant_store.upsert_vectors(
                doc_id=doc_id,
                texts=texts,
                vectors=list(valid_vectors),
                pages=pages,
                is_tables=is_tables,
                # New metadata fields
                filename=filename,
                file_type=file_type,
                title=title,
                section_titles=section_titles,
            )
            logger.info(f"Stored {count} vectors for {doc_id} (file_type={file_type}, filename={filename})")
            return True
        except Exception as e:
            logger.error(f"Error storing vectors: {e}")
            return False
    
    def update_status_callback(doc_id: str, status: str, metadata: dict):
        """Update document status in DynamoDB."""
        try:
            # Map worker status to DocumentStatus enum
            status_map = {
                "processing": DocumentStatus.IDP_RUNNING,
                "completed": DocumentStatus.EMBEDDING_DONE,
                "failed": DocumentStatus.FAILED,
                "skipped": DocumentStatus.FAILED  # Scanned PDFs without Textract
            }
            db_status = status_map.get(status, DocumentStatus.FAILED)
            
            # For retry from FAILED, we need to skip validation
            # Only skip validation for FAILED → IDP_RUNNING transition (retry)
            validate = True
            current_doc = status_manager.get_document(doc_id)
            if current_doc and current_doc.get("status") == "FAILED":
                if status == "processing":  # Maps to IDP_RUNNING
                    validate = False  # Skip validation for retry
                    logger.info(f"Retrying from FAILED state for {doc_id}")
                else:
                    # For other transitions from FAILED, keep validation
                    logger.warning(f"Blocked invalid transition from FAILED to {status}")
            
            status_manager.update_status(
                doc_id=doc_id,
                new_status=db_status,
                chunk_count=metadata.get("chunks_count"),
                error_message=metadata.get("error_message") if db_status == DocumentStatus.FAILED else None,
                validate_transition=validate
            )
            logger.info(f"Updated status for {doc_id}: {db_status.value}")
            return True
        except ValueError as e:
            # Invalid transition - log but don't crash
            logger.warning(f"Status transition blocked for {doc_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            return False
    
    def get_status_callback(doc_id: str) -> str:
        """Get current document status for idempotency check."""
        try:
            doc = status_manager.get_document(doc_id)
            if doc:
                return doc.get("status", "")
            return ""
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return ""
    
    def acquire_lock_callback(doc_id: str, worker_id: str) -> bool:
        """
        Try to acquire processing lock using conditional DynamoDB update.
        Returns True if lock acquired, False if another worker has it.
        """
        try:
            # Use conditional update to prevent race condition
            status_manager._client.update_item(
                TableName=status_manager.table_name,
                Key={
                    "doc_id": {"S": doc_id},
                    "sk": {"S": "METADATA"}
                },
                UpdateExpression="SET worker_id = :wid, lock_time = :lt",
                ConditionExpression="attribute_not_exists(worker_id) OR worker_id = :wid OR #s IN (:done, :failed)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":wid": {"S": worker_id},
                    ":lt": {"S": __import__('datetime').datetime.utcnow().isoformat()},
                    ":done": {"S": "EMBEDDING_DONE"},
                    ":failed": {"S": "FAILED"}
                }
            )
            logger.info(f"Lock acquired for {doc_id} by worker {worker_id}")
            return True
        except status_manager._client.exceptions.ConditionalCheckFailedException:
            logger.info(f"Lock NOT acquired for {doc_id} - another worker processing")
            return False
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return True  # On error, allow processing (fail-open)
    
    return (embeddings_callback, store_vectors_callback, update_status_callback, 
            get_status_callback, acquire_lock_callback)


def main():
    print("=" * 60)
    print("IDP Pipeline - SQS Worker")
    print("=" * 60)
    print(f"Queue URL: {QUEUE_URL}")
    print(f"Bucket: {BUCKET}")
    print(f"Region: {REGION}")
    print(f"Qdrant: {QDRANT_HOST}:{QDRANT_PORT}")
    print("-" * 60)
    
    # Create callbacks
    embeddings_cb, store_cb, status_cb, get_status_cb, lock_cb = create_callbacks()
    
    # Initialize worker with callbacks
    worker = SQSWorker(
        queue_url=QUEUE_URL,
        documents_bucket=BUCKET,
        region=REGION,
        embeddings_callback=embeddings_cb,
        store_vectors_callback=store_cb,
        update_status_callback=status_cb
    )
    
    # Add idempotency and race condition callbacks
    worker.get_status_callback = get_status_cb
    worker.acquire_lock_callback = lock_cb
    
    # Process messages (max iterations from CLI arg, None for infinite)
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if max_iter:
        print(f"Processing up to {max_iter} iterations...")
    else:
        print("Processing indefinitely (Ctrl+C to stop)...")
    
    worker.start(max_iterations=max_iter)


if __name__ == "__main__":
    main()
