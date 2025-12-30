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
