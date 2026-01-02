"""
Syllabus Upload API

Dedicated endpoint for uploading FPT University syllabus markdown files.

DUAL STORAGE APPROACH:
1. DynamoDB - Structured entities for precise queries (sessions, assessments, CLOs)
2. Qdrant - Chunked embeddings for RAG search (natural language questions)

Flow:
- Parse markdown → Store entities in DynamoDB (immediate)
- Upload to S3 → Send to SQS → Worker chunks + embeds → Qdrant (async)

This enables both:
- Structured queries: "Get all assessments for SWD392"
- RAG queries: "What topics are covered in week 5 of SWD392?"
"""

import os
import uuid
import json
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError

from app.services.syllabus.markdown_parser import SyllabusMarkdownParser
from app.services.syllabus.entity_repository import SyllabusEntityRepository
from app.services.auth.auth_service import CurrentUser, require_admin
from app.services.document.document_status_manager import DocumentStatusManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/syllabus", tags=["syllabus"])

# Configuration
S3_BUCKET = os.getenv("S3_BUCKET", "arc-chatbot-documents-427995028618")
SQS_QUEUE_URL = os.getenv(
    "SQS_QUEUE_URL",
    "https://sqs.ap-southeast-1.amazonaws.com/427995028618/arc-chatbot-dev-document-processing"
)
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")


# Response models
class SyllabusUploadResponse(BaseModel):
    """Response for syllabus upload."""
    subject_code: str
    course_name: str
    approved_date: str
    entities_stored: int
    sessions_count: int
    assessments_count: int
    clos_count: int
    materials_count: int
    s3_key: str
    message: str


def get_s3_client():
    """Get S3 client."""
    return boto3.client("s3", region_name=AWS_REGION)


@router.post("/upload", response_model=SyllabusUploadResponse)
async def upload_syllabus(
    file: UploadFile = File(...),
    admin_user: CurrentUser = Depends(require_admin),
):
    """
    Upload and process a syllabus markdown file.
    
    This endpoint implements DUAL STORAGE:
    1. Validates the file is a markdown file
    2. Parses the syllabus structure
    3. Stores entities in DynamoDB (for structured queries)
    4. Uploads original file to S3
    5. Tracks document in DocumentStatusManager
    6. Sends to SQS for chunking and embedding in Qdrant (for RAG search)
    
    **Requirements:**
    - Admin role required
    - File must be .md or .markdown
    - File must contain valid FPT University syllabus structure
    
    **Returns:**
    - Subject code and course info
    - Count of entities stored
    - S3 location of original file
    
    **Note:** Structured data is available immediately. RAG search capability
    will be available after SQS worker processes the file (typically 1-2 minutes).
    """
    import traceback
    
    logger.info("=" * 50)
    logger.info("SYLLABUS UPLOAD STARTED")
    logger.info(f"User: {admin_user.email or admin_user.user_id}")
    
    # Validate file extension
    if not file.filename:
        logger.error("No filename provided")
        raise HTTPException(status_code=400, detail="Filename is required")
    
    filename = file.filename
    logger.info(f"Filename: {filename}")
    
    file_ext = ""
    if "." in filename:
        file_ext = "." + filename.lower().rsplit(".", 1)[-1]
    
    if file_ext not in [".md", ".markdown"]:
        logger.error(f"Invalid file type: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_ext}'. Only .md and .markdown files are supported for syllabus upload."
        )
    
    try:
        # Read file content
        logger.info(f"[STEP 1] Reading syllabus file: {filename}")
        content_bytes = await file.read()
        logger.info(f"File size: {len(content_bytes)} bytes")
        
        # Decode as UTF-8
        try:
            content_text = content_bytes.decode('utf-8')
            logger.info(f"[STEP 2] Decoded UTF-8 successfully, {len(content_text)} chars")
        except UnicodeDecodeError as e:
            logger.error(f"UTF-8 decode error: {e}")
            raise HTTPException(
                status_code=400,
                detail="File must be UTF-8 encoded"
            )
        
        # Parse syllabus
        logger.info(f"[STEP 3] Parsing syllabus...")
        parser = SyllabusMarkdownParser()
        
        try:
            parsed = parser.parse(content_text)
            logger.info(f"[STEP 3] Parse successful!")
            logger.info(f"  - Subject code: {parsed.subject_code}")
            logger.info(f"  - Subject name: {parsed.subject_name}")
            logger.info(f"  - Sessions: {len(parsed.sessions)}")
            logger.info(f"  - Assessments: {len(parsed.assessments)}")
            logger.info(f"  - CLOs: {len(parsed.clos)}")
            logger.info(f"  - Materials: {len(parsed.materials)}")
            logger.info(f"  - Metadata: {parsed.raw_metadata}")
        except Exception as e:
            logger.error(f"[STEP 3] Parse failed: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse syllabus: {str(e)}"
            )
        
        if not parsed.subject_code or parsed.subject_code == "UNKNOWN":
            logger.error(f"[STEP 3] No subject code found")
            raise HTTPException(
                status_code=400,
                detail="Failed to extract subject code from syllabus. Please check file format."
            )
        
        # Convert to entities
        logger.info(f"[STEP 4] Converting to entities...")
        from app.models.syllabus_entities import (
            CourseInfo, SessionEntity, AssessmentEntity, CLOEntity,
            ExtractionMethod, VersionStatus
        )
        from datetime import datetime, timezone
        
        # Generate approved_date from metadata or use current time
        raw_date = parsed.raw_metadata.get('approved_date') or parsed.raw_metadata.get('created')
        if raw_date:
            # Try to parse various date formats
            try:
                # Format: 8/22/2025 or M/D/YYYY
                if '/' in raw_date:
                    parts = raw_date.split('/')
                    if len(parts) == 3:
                        month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                        approved_date = f"{year}-{month:02d}-{day:02d}T00:00:00Z"
                    else:
                        approved_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                elif raw_date.endswith('Z'):
                    approved_date = raw_date
                else:
                    dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                    approved_date = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                approved_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            approved_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Extract credits from metadata
        credits = 3  # Default
        try:
            credits_str = parsed.raw_metadata.get('credits', '3')
            credits = int(credits_str)
        except (ValueError, TypeError):
            credits = 3
        
        logger.info(f"  - Approved date: {approved_date}")
        logger.info(f"  - Credits: {credits}")
        
        # Create CourseInfo
        logger.info(f"[STEP 4a] Creating CourseInfo...")
        try:
            course_info = CourseInfo(
                subject_code=parsed.subject_code,
                approved_date=approved_date,
                course_name=parsed.subject_name,
                credits=credits,
                decision_no=parsed.raw_metadata.get('decision_no', 'N/A'),
                extraction_method=ExtractionMethod.HTML_PARSER,
            )
            logger.info(f"[STEP 4a] CourseInfo created: {course_info.subject_code}")
        except Exception as e:
            logger.error(f"[STEP 4a] Failed to create CourseInfo: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # Convert sessions
        logger.info(f"[STEP 4b] Converting {len(parsed.sessions)} sessions...")
        sessions = []
        for idx, ps in enumerate(parsed.sessions):
            try:
                session = SessionEntity(
                    subject_code=parsed.subject_code,
                    approved_date=approved_date,
                    session_number=ps.session_number,
                    topics=[ps.topic] if ps.topic else [],
                    clo_coverage=ps.clos,
                    mode=ps.mode,
                    session_type=ps.itu,
                    materials=ps.materials,
                    activities=ps.tasks,
                    extraction_method=ExtractionMethod.HTML_PARSER,
                )
                sessions.append(session)
            except Exception as e:
                logger.warning(f"[STEP 4b] Skipping session {ps.session_number}: {e}")
                continue
        logger.info(f"[STEP 4b] Created {len(sessions)} sessions")
        
        # Convert assessments
        logger.info(f"[STEP 4c] Converting {len(parsed.assessments)} assessments...")
        assessments = []
        for pa in parsed.assessments:
            try:
                assessment = AssessmentEntity(
                    subject_code=parsed.subject_code,
                    approved_date=approved_date,
                    category=pa.category,
                    assessment_type=pa.type,
                    part=pa.part,
                    weight_percentage=pa.weight,
                    completion_criteria=pa.completion_criteria,
                    duration=pa.duration,
                    clo_mapping=pa.clos,
                    question_type=pa.question_type,
                    no_question=pa.no_question,
                    knowledge_and_skill=pa.knowledge_skill,
                    grading_guide=pa.grading_guide,
                    note=pa.note,
                    extraction_method=ExtractionMethod.HTML_PARSER,
                )
                assessments.append(assessment)
            except Exception as e:
                logger.warning(f"[STEP 4c] Skipping assessment {pa.category}: {e}")
                continue
        logger.info(f"[STEP 4c] Created {len(assessments)} assessments")
        
        # Convert CLOs from parsed data
        logger.info(f"[STEP 4d] Converting {len(parsed.clos)} CLOs...")
        from app.models.syllabus_entities import CLOEntity, MaterialEntity
        clos = []
        for pc in parsed.clos:
            try:
                clo = CLOEntity(
                    subject_code=parsed.subject_code,
                    approved_date=approved_date,
                    clo_id=pc.clo_id,
                    description=pc.clo_details or pc.lo_details or f"CLO {pc.clo_number}",
                    clo_details=pc.clo_details,
                    lo_details=pc.lo_details,
                    extraction_method=ExtractionMethod.HTML_PARSER,
                )
                clos.append(clo)
            except Exception as e:
                logger.warning(f"[STEP 4d] Skipping CLO {pc.clo_id}: {e}")
                continue
        logger.info(f"[STEP 4d] Created {len(clos)} CLOs")
        
        # Convert Materials from parsed data
        logger.info(f"[STEP 4e] Converting {len(parsed.materials)} materials...")
        materials = []
        for pm in parsed.materials:
            try:
                material = MaterialEntity(
                    subject_code=parsed.subject_code,
                    approved_date=approved_date,
                    material_id=pm.material_id,
                    title=pm.title,
                    author=pm.author or None,
                    publisher=pm.publisher or None,
                    published_date=pm.published_date or None,
                    edition=pm.edition or None,
                    isbn=pm.isbn or None,
                    is_main_material=pm.is_main_material,
                    is_hard_copy=pm.is_hard_copy,
                    is_online=pm.is_online,
                    note=pm.note or None,
                    extraction_method=ExtractionMethod.HTML_PARSER,
                )
                materials.append(material)
            except Exception as e:
                logger.warning(f"[STEP 4e] Skipping material {pm.title}: {e}")
                continue
        logger.info(f"[STEP 4e] Created {len(materials)} materials")
        
        logger.info(f"[STEP 4] Entity conversion complete: {len(sessions)} sessions, {len(assessments)} assessments, {len(clos)} CLOs, {len(materials)} materials")
        
        # Generate document ID
        doc_id = f"syllabus-{course_info.subject_code.lower()}-{uuid.uuid4().hex[:8]}"
        logger.info(f"[STEP 5] Generated doc_id: {doc_id}")
        
        # Upload to S3 - use subject_code as filename for consistency
        normalized_filename = f"{course_info.subject_code}.md"
        s3_key = f"syllabi/{course_info.subject_code}/{normalized_filename}"
        logger.info(f"[STEP 6] Uploading to S3: {s3_key} (original: {filename})")
        
        s3_client = get_s3_client()
        try:
            # S3 metadata only accepts ASCII - encode Unicode to base64 or remove non-ASCII
            import urllib.parse
            safe_course_name = urllib.parse.quote(course_info.course_name, safe='')
            
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=content_bytes,
                ContentType="text/markdown",
                Metadata={
                    "subject_code": course_info.subject_code,
                    "course_name": safe_course_name,  # URL-encoded for Unicode support
                    "uploaded_by": admin_user.email or admin_user.user_id,
                    "doc_id": doc_id,
                }
            )
            logger.info(f"[STEP 6] S3 upload successful: s3://{S3_BUCKET}/{s3_key}")
        except ClientError as e:
            logger.error(f"[STEP 6] S3 upload failed: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to S3: {str(e)}"
            )
        
        # Set source_doc_id for all entities
        course_info.source_doc_id = doc_id
        for entity in clos + sessions + assessments + materials:
            entity.source_doc_id = doc_id
        
        # Store entities in DynamoDB
        entities_to_store = [course_info] + clos + sessions + assessments + materials
        
        logger.info(f"[STEP 7] Storing {len(entities_to_store)} entities to DynamoDB...")
        repository = SyllabusEntityRepository()
        
        try:
            batch_result = repository.put_entities_batch(entities_to_store)
            
            success_count = batch_result.get("success_count", 0)
            failed_items = batch_result.get("failed_items", [])
            
            if failed_items:
                logger.warning(f"[STEP 7] Failed items: {failed_items}")
            
            logger.info(f"[STEP 7] DynamoDB stored {success_count}/{len(entities_to_store)} entities")
            
            if success_count == 0:
                logger.error("[STEP 7] No entities stored!")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store entities to DynamoDB"
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[STEP 7] DynamoDB error: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store syllabus data: {str(e)}"
            )
        
        # Track document in DocumentStatusManager for RAG processing
        logger.info(f"[STEP 8] Creating document tracking record: doc_id={doc_id}")
        status_manager = DocumentStatusManager()
        try:
            status_manager.create_document(
                doc_id=doc_id,
                filename=filename,
                uploaded_by=admin_user.email or admin_user.user_id,
                file_type=file_ext,
                processor="syllabus_markdown"
            )
            logger.info(f"[STEP 8] Document tracking record created")
        except Exception as e:
            logger.warning(f"[STEP 8] Failed to create tracking record (non-fatal): {e}")
        
        # Send to SQS for chunking and embedding (RAG search capability)
        logger.info(f"[STEP 9] Sending SQS message for RAG processing...")
        sqs_client = boto3.client("sqs", region_name=AWS_REGION)
        try:
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
            logger.info(f"[STEP 9] SQS message sent: message_id={sqs_response.get('MessageId')}")
        except Exception as e:
            logger.warning(f"[STEP 9] SQS failed (non-fatal): {e}")
        
        # Return success response
        logger.info(f"[STEP 10] UPLOAD COMPLETE - {course_info.subject_code}")
        logger.info("=" * 50)
        
        return SyllabusUploadResponse(
            subject_code=course_info.subject_code,
            course_name=course_info.course_name,
            approved_date=course_info.approved_date,
            entities_stored=success_count,
            sessions_count=len(sessions),
            assessments_count=len(assessments),
            clos_count=len(clos),
            materials_count=len(materials),
            s3_key=s3_key,
            message=f"Successfully processed syllabus for {course_info.subject_code}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error: {e}")
        logger.error(traceback.format_exc())
        
        # Create user-friendly error message
        error_str = str(e)
        if "validation error" in error_str.lower():
            user_message = f"Validation error: {error_str}"
        elif "decode" in error_str.lower() or "utf" in error_str.lower():
            user_message = "File encoding error. Please save the file as UTF-8."
        elif "parse" in error_str.lower():
            user_message = f"Parse error: {error_str}"
        else:
            user_message = f"Error: {error_str}"
        
        raise HTTPException(
            status_code=500,
            detail=user_message
        )
