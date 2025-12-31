"""
Admin API endpoints for document management.

Endpoints:
- POST /api/admin/upload - Upload document (PDF, MD, IPYNB) WITH ROLLBACK - ADMIN ONLY
- GET /api/admin/documents - List documents with pagination - ADMIN ONLY

Supported file types:
- .pdf - PDF documents (processed via Textract)
- .md - Markdown files (direct text parsing)
- .ipynb - Jupyter Notebooks (JSON parsing)

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 11.1, 11.2, 11.3, 11.4
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError

from app.services.document.document_status_manager import (
    DocumentStatusManager,
    DocumentStatus
)
from app.services.auth.auth_service import (
    CurrentUser,
    get_current_user,
    require_admin,
)
from app.services.document.file_processors import SUPPORTED_FILE_TYPES, ProcessorFactory


# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Configuration
S3_BUCKET = os.getenv("S3_BUCKET", "arc-chatbot-documents-427995028618")
SQS_QUEUE_URL = os.getenv(
    "SQS_QUEUE_URL",
    "https://sqs.ap-southeast-1.amazonaws.com/427995028618/arc-chatbot-dev-document-processing"
)
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")


# Response models
class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    status: str
    message: str


def validate_file_type(filename: str) -> tuple[str, dict]:
    """
    Validate file type and return extension with config.
    
    Args:
        filename: Original filename
        
    Returns:
        Tuple of (extension, config dict)
        
    Raises:
        HTTPException: If file type not supported
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Extract extension
    ext = ""
    if "." in filename:
        ext = "." + filename.lower().rsplit(".", 1)[-1]
    
    if ext not in SUPPORTED_FILE_TYPES:
        supported = ", ".join(SUPPORTED_FILE_TYPES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {supported}"
        )
    
    return ext, SUPPORTED_FILE_TYPES[ext]


class DocumentItem(BaseModel):
    doc_id: str
    filename: str
    file_type: Optional[str] = ".pdf"  # Default for backward compatibility
    status: str
    uploaded_at: str
    uploaded_by: str
    page_count: Optional[int] = None
    chunk_count: Optional[int] = None
    error_message: Optional[str] = None


class DocumentStats(BaseModel):
    total: int = 0
    completed: int = 0
    processing: int = 0
    failed: int = 0
    uploaded: int = 0


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]
    total: int
    page: int
    page_size: int
    has_more: bool
    next_cursor: Optional[str] = None  # Cursor for next page (base64 encoded)
    stats: Optional[DocumentStats] = None  # Overall stats across all documents


# Initialize AWS clients
def get_s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def get_sqs_client():
    return boto3.client("sqs", region_name=AWS_REGION)


def get_status_manager():
    return DocumentStatusManager(region_name=AWS_REGION)


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    admin_user: CurrentUser = Depends(require_admin),  # ✅ Require admin role
):
    """
    Upload a document for processing WITH ROLLBACK SUPPORT.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    
    Supported file types:
    - .pdf - PDF documents (processed via Textract)
    - .md - Markdown files (direct text parsing)
    - .ipynb - Jupyter Notebooks (JSON parsing)
    
    Flow:
    - Validates file type is supported
    - Uploads to S3 with unique doc_id
    - Creates DynamoDB record with UPLOADED status
    - Sends message to SQS for processing
    - ROLLBACK: Cleans up S3 and DynamoDB if any step fails
    
    Requirements: 10.1, 10.2, 10.3, 10.4
    """
    # Get uploader from authenticated user
    uploaded_by = admin_user.email or admin_user.user_id
    
    # Validate file type (supports .pdf, .md, .ipynb)
    file_ext, file_config = validate_file_type(file.filename)
    
    # Generate unique document ID
    doc_id = str(uuid.uuid4())
    
    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file not allowed"
        )
    
    # S3 key path
    s3_key = f"uploads/{doc_id}/{file.filename}"
    
    # Track what succeeded for rollback
    s3_uploaded = False
    dynamo_created = False
    
    # Initialize clients
    s3_client = get_s3_client()
    status_manager = get_status_manager()
    
    try:
        # Step 1: Upload to S3
        logger.info(f"Starting S3 upload: doc_id={doc_id}, filename={file.filename}, type={file_ext}, size={len(content)} bytes")
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=content,
            ContentType=file_config["content_type"],
            Metadata={
                "doc_id": doc_id,
                "uploaded_by": uploaded_by,
                "file_type": file_ext,
                "processor": file_config["processor"]
            }
        )
        s3_uploaded = True
        logger.info(f"S3 upload successful: s3://{S3_BUCKET}/{s3_key}")
        
        # Step 2: Create DynamoDB record
        logger.info(f"Creating DynamoDB record: doc_id={doc_id}")
        status_manager.create_document(
            doc_id=doc_id,
            filename=file.filename,
            uploaded_by=uploaded_by,
            file_type=file_ext,
            processor=file_config["processor"]
        )
        dynamo_created = True
        logger.info(f"DynamoDB record created: doc_id={doc_id}, file_type={file_ext}, status=UPLOADED")
        
        # Step 3: Send SQS message
        logger.info(f"Sending SQS message: doc_id={doc_id}")
        sqs_client = get_sqs_client()
        message_body = json.dumps({
            "Records": [{
                "s3": {
                    "bucket": {"name": S3_BUCKET},
                    "object": {"key": s3_key}
                }
            }],
            "doc_id": doc_id
        })
        
        sqs_response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_body
        )
        logger.info(f"SQS message sent: doc_id={doc_id}, message_id={sqs_response.get('MessageId')}")
        
        # Success - return response
        return UploadResponse(
            doc_id=doc_id,
            filename=file.filename,
            file_type=file_ext,
            status=DocumentStatus.UPLOADED.value,
            message=f"Document uploaded successfully ({file_ext}). Processing will begin shortly."
        )
        
    except Exception as e:
        # Log the error
        logger.error(
            f"Upload failed: doc_id={doc_id}, error={str(e)}, "
            f"s3_uploaded={s3_uploaded}, dynamo_created={dynamo_created}"
        )
        
        # ROLLBACK: Clean up in REVERSE order
        rollback_errors = []
        
        # Rollback DynamoDB (if created)
        if dynamo_created:
            try:
                logger.info(f"Rolling back DynamoDB: doc_id={doc_id}")
                status_manager._client.delete_item(
                    TableName=status_manager.table_name,
                    Key={
                        "doc_id": {"S": doc_id},
                        "sk": {"S": "METADATA"}
                    }
                )
                logger.info(f"DynamoDB rollback successful: doc_id={doc_id}")
            except ClientError as rollback_error:
                error_msg = f"DynamoDB rollback failed: {str(rollback_error)}"
                logger.error(error_msg)
                rollback_errors.append(error_msg)
        
        # Rollback S3 (if uploaded)
        if s3_uploaded:
            try:
                logger.info(f"Rolling back S3: s3://{S3_BUCKET}/{s3_key}")
                s3_client.delete_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key
                )
                logger.info(f"S3 rollback successful: s3://{S3_BUCKET}/{s3_key}")
            except ClientError as rollback_error:
                error_msg = f"S3 rollback failed: {str(rollback_error)}"
                logger.error(error_msg)
                rollback_errors.append(error_msg)
        
        # Construct error message
        error_detail = f"Upload failed: {str(e)}"
        if rollback_errors:
            error_detail += f" | Rollback issues: {'; '.join(rollback_errors)}"
        else:
            error_detail += " | All changes rolled back successfully."
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    admin_user: CurrentUser = Depends(require_admin),  # ✅ Require admin role
):
    """
    List documents with page-based pagination.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    
    Documents are sorted by uploaded_at descending (newest first).
    
    Filter by status: UPLOADED, IDP_RUNNING, EMBEDDING_DONE, FAILED
    
    Requirements: 11.1, 11.2, 11.3, 11.4
    """
    status_manager = get_status_manager()
    
    # Validate status filter
    status_filter = None
    if status:
        try:
            status_filter = DocumentStatus(status.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {[s.value for s in DocumentStatus]}"
            )
    
    # Query with page-based pagination (sorted by uploaded_at desc)
    result = status_manager.list_documents(
        status=status_filter,
        page_size=page_size,
        page=page,
    )
    
    # Convert to response items
    items = [
        DocumentItem(
            doc_id=doc.get("doc_id", ""),
            filename=doc.get("filename", ""),
            file_type=doc.get("file_type", ".pdf"),
            status=doc.get("status", ""),
            uploaded_at=doc.get("uploaded_at", ""),
            uploaded_by=doc.get("uploaded_by", ""),
            page_count=doc.get("page_count"),
            chunk_count=doc.get("chunk_count"),
            error_message=doc.get("error_message")
        )
        for doc in result["items"]
    ]
    
    # Build stats from result
    stats_data = result.get("stats", {})
    stats = DocumentStats(
        total=stats_data.get("total", 0),
        completed=stats_data.get("completed", 0),
        processing=stats_data.get("processing", 0),
        failed=stats_data.get("failed", 0),
        uploaded=stats_data.get("uploaded", 0),
    )
    
    return DocumentListResponse(
        items=items,
        total=result.get("total", len(items)),
        page=page,
        page_size=page_size,
        has_more=result.get("has_more", False),
        next_cursor=None,  # Not used with page-based pagination
        stats=stats,
    )


@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    admin_user: CurrentUser = Depends(require_admin),  # ✅ Require admin role
):
    """
    Generate presigned URL for document download.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    
    Returns a temporary URL (valid for 1 hour) to download the PDF.
    """
    try:
        status_manager = get_status_manager()
        doc = status_manager.get_document(doc_id)
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )
        
        s3_client = get_s3_client()
        s3_key = f"uploads/{doc_id}/{doc['filename']}"
        
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': s3_key
            },
            ExpiresIn=3600
        )
        
        return {
            "doc_id": doc_id,
            "filename": doc["filename"],
            "download_url": presigned_url,
            "expires_in": 3600
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    admin_user: CurrentUser = Depends(require_admin),  # ✅ Require admin role
):
    """
    Get a single document by ID.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    """
    status_manager = get_status_manager()
    doc = status_manager.get_document(doc_id)
    
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )
    
    return DocumentItem(
        doc_id=doc.get("doc_id", ""),
        filename=doc.get("filename", ""),
        file_type=doc.get("file_type", ".pdf"),
        status=doc.get("status", ""),
        uploaded_at=doc.get("uploaded_at", ""),
        uploaded_by=doc.get("uploaded_by", ""),
        page_count=doc.get("page_count"),
        chunk_count=doc.get("chunk_count"),
        error_message=doc.get("error_message")
    )


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    admin_user: CurrentUser = Depends(require_admin),
):
    """
    Delete a document and all associated resources.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    
    This will:
    1. Delete the document record from DynamoDB
    2. Delete the file from S3
    3. Delete embeddings from Qdrant (if any)
    """
    status_manager = get_status_manager()
    s3_client = get_s3_client()
    
    # Get document first
    doc = status_manager.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )
    
    errors = []
    
    # 1. Delete from S3
    try:
        s3_key = f"uploads/{doc_id}/{doc['filename']}"
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"Deleted S3 object: s3://{S3_BUCKET}/{s3_key}")
    except ClientError as e:
        error_msg = f"Failed to delete S3 object: {str(e)}"
        logger.warning(error_msg)
        errors.append(error_msg)
    
    # 2. Delete embeddings from Qdrant
    try:
        from app.services.search.qdrant_client import QdrantVectorStore
        qdrant = QdrantVectorStore()
        deleted_count = qdrant.delete_document(doc_id)
        logger.info(f"Deleted {deleted_count} embeddings from Qdrant for doc_id={doc_id}")
    except Exception as e:
        error_msg = f"Failed to delete Qdrant embeddings: {str(e)}"
        logger.warning(error_msg)
        errors.append(error_msg)
    
    # 3. Delete from DynamoDB
    try:
        status_manager._client.delete_item(
            TableName=status_manager.table_name,
            Key={
                "doc_id": {"S": doc_id},
                "sk": {"S": "METADATA"}
            }
        )
        logger.info(f"Deleted DynamoDB record: doc_id={doc_id}")
    except ClientError as e:
        logger.error(f"Failed to delete DynamoDB record: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document record: {str(e)}"
        )
    
    return {
        "doc_id": doc_id,
        "message": "Document deleted successfully",
        "warnings": errors if errors else None
    }


class UpdateDocumentRequest(BaseModel):
    """Request body for updating document metadata."""
    filename: Optional[str] = None
    status: Optional[str] = None


@router.patch("/documents/{doc_id}")
async def update_document(
    doc_id: str,
    request: UpdateDocumentRequest,
    admin_user: CurrentUser = Depends(require_admin),
):
    """
    Update document metadata.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    
    Updatable fields:
    - filename: Rename the document
    - status: Change status (for retry failed documents)
    """
    status_manager = get_status_manager()
    
    # Get document first
    doc = status_manager.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )
    
    # Build update expression
    update_parts = []
    expression_names = {}
    expression_values = {}
    
    if request.filename:
        update_parts.append("#filename = :filename")
        expression_names["#filename"] = "filename"
        expression_values[":filename"] = {"S": request.filename}
    
    if request.status:
        # Validate status
        try:
            new_status = DocumentStatus(request.status.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {[s.value for s in DocumentStatus]}"
            )
        update_parts.append("#status = :status")
        expression_names["#status"] = "status"
        expression_values[":status"] = {"S": new_status.value}
    
    if not update_parts:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )
    
    # Add updated_at timestamp
    update_parts.append("#updated_at = :updated_at")
    expression_names["#updated_at"] = "updated_at"
    expression_values[":updated_at"] = {"S": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    
    update_expression = "SET " + ", ".join(update_parts)
    
    try:
        response = status_manager._client.update_item(
            TableName=status_manager.table_name,
            Key={
                "doc_id": {"S": doc_id},
                "sk": {"S": "METADATA"}
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW"
        )
        
        updated_doc = status_manager._parse_item(response.get("Attributes", {}))
        
        return DocumentItem(
            doc_id=updated_doc.get("doc_id", ""),
            filename=updated_doc.get("filename", ""),
            file_type=updated_doc.get("file_type", ".pdf"),
            status=updated_doc.get("status", ""),
            uploaded_at=updated_doc.get("uploaded_at", ""),
            uploaded_by=updated_doc.get("uploaded_by", ""),
            page_count=updated_doc.get("page_count"),
            chunk_count=updated_doc.get("chunk_count"),
            error_message=updated_doc.get("error_message")
        )
        
    except ClientError as e:
        logger.error(f"Failed to update document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update document: {str(e)}"
        )


@router.post("/documents/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: str,
    admin_user: CurrentUser = Depends(require_admin),
):
    """
    Reprocess a failed document.
    
    REQUIRES: Admin role (Cognito 'admin' group)
    
    This will:
    1. Reset status to UPLOADED
    2. Send a new SQS message for processing
    """
    status_manager = get_status_manager()
    
    # Get document first
    doc = status_manager.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )
    
    # Only allow reprocessing of FAILED documents
    if doc.get("status") not in ["FAILED", "UPLOADED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only reprocess FAILED or UPLOADED documents. Current status: {doc.get('status')}"
        )
    
    # Reset status to UPLOADED
    status_manager.update_status(
        doc_id=doc_id,
        new_status=DocumentStatus.UPLOADED,
        validate_transition=False  # Allow any transition for reprocessing
    )
    
    # Send SQS message
    try:
        sqs_client = get_sqs_client()
        s3_key = f"uploads/{doc_id}/{doc['filename']}"
        
        message_body = json.dumps({
            "Records": [{
                "s3": {
                    "bucket": {"name": S3_BUCKET},
                    "object": {"key": s3_key}
                }
            }],
            "doc_id": doc_id
        })
        
        sqs_response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_body
        )
        logger.info(f"Reprocess SQS message sent: doc_id={doc_id}, message_id={sqs_response.get('MessageId')}")
        
    except Exception as e:
        logger.error(f"Failed to send reprocess SQS message: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue document for reprocessing: {str(e)}"
        )
    
    return {
        "doc_id": doc_id,
        "message": "Document queued for reprocessing",
        "status": "UPLOADED"
    }
