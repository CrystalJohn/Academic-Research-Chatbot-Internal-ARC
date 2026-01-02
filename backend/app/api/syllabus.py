"""
Syllabus API endpoints for structured syllabus data.

Endpoints:
- GET /api/syllabus/{subject_code} - Get latest syllabus version
- GET /api/syllabus/{subject_code}/versions - List all versions
- GET /api/syllabus/{subject_code}/sessions - Get sessions (optionally filter by CLO)
- GET /api/syllabus/{subject_code}/assessments - Get assessments
- GET /api/syllabus/{subject_code}/clos - Get CLOs
- GET /api/syllabus/{subject_code}/materials - Get materials

Supports FPT University syllabus markdown files parsed by SyllabusMarkdownParser.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.services.syllabus.entity_repository import SyllabusEntityRepository
from app.services.auth.auth_service import CurrentUser, get_current_user
from app.models.syllabus_entities import (
    CourseInfo,
    CLOEntity,
    SessionEntity,
    AssessmentEntity,
    MaterialEntity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/syllabus", tags=["syllabus"])


# Response Models
class CourseInfoResponse(BaseModel):
    """Course information response."""
    subject_code: str
    course_name: str
    credits: int
    decision_no: str
    department: Optional[str] = None
    instructor: Optional[str] = None
    approved_date: str
    version_status: str


class CLOResponse(BaseModel):
    """CLO response."""
    clo_id: str
    description: str
    plo_mapping: List[str] = []
    bloom_level: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response."""
    session_number: int
    topics: List[str]
    clo_coverage: List[str] = []
    mode: Optional[str] = None
    session_type: Optional[str] = None
    materials: Optional[str] = None
    activities: Optional[str] = None


class AssessmentResponse(BaseModel):
    """Assessment response."""
    category: str
    assessment_type: Optional[str] = None
    part: Optional[int] = None
    weight_percentage: float
    completion_criteria: Optional[str] = None
    duration: Optional[str] = None
    clo_mapping: List[str] = []
    question_type: Optional[str] = None
    no_question: Optional[str] = None
    knowledge_and_skill: Optional[str] = None
    grading_guide: Optional[str] = None
    note: Optional[str] = None


class MaterialResponse(BaseModel):
    """Material response."""
    material_id: str
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[str] = None
    edition: Optional[str] = None
    isbn: Optional[str] = None
    is_main_material: bool = False
    is_hard_copy: bool = False
    is_online: bool = False
    note: Optional[str] = None


class VersionInfo(BaseModel):
    """Version info response."""
    approved_date: str
    decision_no: str


class SyllabusResponse(BaseModel):
    """Full syllabus response."""
    course_info: Optional[CourseInfoResponse] = None
    clos: List[CLOResponse] = []
    sessions: List[SessionResponse] = []
    assessments: List[AssessmentResponse] = []
    materials: List[MaterialResponse] = []
    total_sessions: int = 0
    total_assessments: int = 0
    total_weight: float = 0.0


class SessionListResponse(BaseModel):
    """Session list response."""
    subject_code: str
    approved_date: Optional[str] = None
    sessions: List[SessionResponse]
    total: int
    filtered_by_clo: Optional[str] = None


class AssessmentListResponse(BaseModel):
    """Assessment list response."""
    subject_code: str
    approved_date: Optional[str] = None
    assessments: List[AssessmentResponse]
    total: int
    total_weight: float


class CLOListResponse(BaseModel):
    """CLO list response."""
    subject_code: str
    approved_date: Optional[str] = None
    clos: List[CLOResponse]
    total: int


class MaterialListResponse(BaseModel):
    """Material list response."""
    subject_code: str
    approved_date: Optional[str] = None
    materials: List[MaterialResponse]
    total: int


class VersionListResponse(BaseModel):
    """Version list response."""
    subject_code: str
    versions: List[VersionInfo]
    total: int


# Dependency
def get_syllabus_repository() -> SyllabusEntityRepository:
    """Get syllabus entity repository instance."""
    return SyllabusEntityRepository()


# Helper functions
def _course_info_to_response(entity: CourseInfo) -> CourseInfoResponse:
    """Convert CourseInfo entity to response."""
    return CourseInfoResponse(
        subject_code=entity.subject_code,
        course_name=entity.course_name,
        credits=entity.credits,
        decision_no=entity.decision_no,
        department=entity.department,
        instructor=entity.instructor,
        approved_date=entity.approved_date,
        version_status=entity.version_status.value if hasattr(entity.version_status, 'value') else str(entity.version_status),
    )


def _clo_to_response(entity: CLOEntity) -> CLOResponse:
    """Convert CLOEntity to response."""
    return CLOResponse(
        clo_id=entity.clo_id,
        description=entity.description,
        plo_mapping=entity.plo_mapping,
        bloom_level=entity.bloom_level,
    )


def _session_to_response(entity: SessionEntity) -> SessionResponse:
    """Convert SessionEntity to response."""
    return SessionResponse(
        session_number=entity.session_number,
        topics=entity.topics,
        clo_coverage=entity.clo_coverage,
        mode=entity.mode,
        session_type=entity.session_type,
        materials=entity.materials,
        activities=entity.activities,
    )


def _assessment_to_response(entity: AssessmentEntity) -> AssessmentResponse:
    """Convert AssessmentEntity to response."""
    return AssessmentResponse(
        category=entity.category,
        assessment_type=entity.assessment_type,
        part=entity.part,
        weight_percentage=entity.weight_percentage,
        completion_criteria=entity.completion_criteria,
        duration=entity.duration,
        clo_mapping=entity.clo_mapping,
        question_type=entity.question_type,
        no_question=entity.no_question,
        knowledge_and_skill=entity.knowledge_and_skill,
        grading_guide=entity.grading_guide,
        note=entity.note,
    )


def _material_to_response(entity: MaterialEntity) -> MaterialResponse:
    """Convert MaterialEntity to response."""
    return MaterialResponse(
        material_id=entity.material_id,
        title=entity.title,
        author=entity.author,
        publisher=entity.publisher,
        published_date=entity.published_date,
        edition=entity.edition,
        isbn=entity.isbn,
        is_main_material=entity.is_main_material,
        is_hard_copy=entity.is_hard_copy,
        is_online=entity.is_online,
        note=entity.note,
    )


# Endpoints
@router.get("/health")
async def syllabus_health():
    """Health check for syllabus API."""
    return {"status": "healthy", "service": "syllabus"}


@router.get("/{subject_code}", response_model=SyllabusResponse)
async def get_syllabus(
    subject_code: str,
    version: Optional[str] = Query(None, description="Specific version (approved_date). If not provided, returns latest."),
    current_user: CurrentUser = Depends(get_current_user),
    repo: SyllabusEntityRepository = Depends(get_syllabus_repository),
):
    """
    Get syllabus data for a subject.
    
    Returns the latest version by default, or a specific version if provided.
    Includes course info, CLOs, sessions, assessments, and materials.
    """
    subject_code = subject_code.upper()
    
    try:
        if version:
            # Get specific version
            data = repo.get_entities_by_version(subject_code, version)
        else:
            # Get latest version
            data = repo.get_latest_version(subject_code)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Syllabus not found for subject: {subject_code}"
            )
        
        # Convert entities to response
        course_info = None
        if data.get("course_info"):
            course_info = _course_info_to_response(data["course_info"])
        
        clos = [_clo_to_response(c) for c in data.get("clos", [])]
        sessions = [_session_to_response(s) for s in data.get("sessions", [])]
        assessments = [_assessment_to_response(a) for a in data.get("assessments", [])]
        materials = [_material_to_response(m) for m in data.get("materials", [])]
        
        total_weight = sum(a.weight_percentage for a in assessments)
        
        return SyllabusResponse(
            course_info=course_info,
            clos=clos,
            sessions=sessions,
            assessments=assessments,
            materials=materials,
            total_sessions=len(sessions),
            total_assessments=len(assessments),
            total_weight=total_weight,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching syllabus for {subject_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch syllabus: {str(e)}"
        )


@router.get("/{subject_code}/versions", response_model=VersionListResponse)
async def list_versions(
    subject_code: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: SyllabusEntityRepository = Depends(get_syllabus_repository),
):
    """
    List all versions of a syllabus.
    
    Returns list of approved_date and decision_no for each version.
    """
    subject_code = subject_code.upper()
    
    try:
        versions = repo.list_versions(subject_code)
        
        return VersionListResponse(
            subject_code=subject_code,
            versions=[VersionInfo(**v) for v in versions],
            total=len(versions),
        )
        
    except Exception as e:
        logger.error(f"Error listing versions for {subject_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list versions: {str(e)}"
        )


@router.get("/{subject_code}/sessions", response_model=SessionListResponse)
async def get_sessions(
    subject_code: str,
    version: Optional[str] = Query(None, description="Specific version (approved_date)"),
    clo: Optional[str] = Query(None, description="Filter by CLO (e.g., CLO1)"),
    current_user: CurrentUser = Depends(get_current_user),
    repo: SyllabusEntityRepository = Depends(get_syllabus_repository),
):
    """
    Get sessions for a syllabus.
    
    Optionally filter by CLO to find sessions covering specific learning outcomes.
    """
    subject_code = subject_code.upper()
    
    try:
        if clo:
            # Filter by CLO
            clo = clo.upper()
            sessions = repo.get_sessions_by_clo(subject_code, clo, version)
            session_responses = [_session_to_response(s) for s in sessions]
            
            return SessionListResponse(
                subject_code=subject_code,
                approved_date=version,
                sessions=session_responses,
                total=len(session_responses),
                filtered_by_clo=clo,
            )
        else:
            # Get all sessions
            if version:
                data = repo.get_entities_by_version(subject_code, version)
            else:
                data = repo.get_latest_version(subject_code)
            
            if not data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Syllabus not found for subject: {subject_code}"
                )
            
            sessions = data.get("sessions", [])
            session_responses = [_session_to_response(s) for s in sessions]
            
            approved_date = version
            if not approved_date and data.get("course_info"):
                approved_date = data["course_info"].approved_date
            
            return SessionListResponse(
                subject_code=subject_code,
                approved_date=approved_date,
                sessions=session_responses,
                total=len(session_responses),
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sessions for {subject_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch sessions: {str(e)}"
        )


@router.get("/{subject_code}/assessments", response_model=AssessmentListResponse)
async def get_assessments(
    subject_code: str,
    version: Optional[str] = Query(None, description="Specific version (approved_date)"),
    min_weight: Optional[float] = Query(None, ge=0, le=100, description="Minimum weight percentage"),
    current_user: CurrentUser = Depends(get_current_user),
    repo: SyllabusEntityRepository = Depends(get_syllabus_repository),
):
    """
    Get assessments for a syllabus.
    
    Optionally filter by minimum weight percentage.
    """
    subject_code = subject_code.upper()
    
    try:
        if version:
            assessments = repo.get_assessments(subject_code, version, min_weight)
        else:
            # Get latest version first
            data = repo.get_latest_version(subject_code)
            if not data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Syllabus not found for subject: {subject_code}"
                )
            
            assessments = data.get("assessments", [])
            if min_weight is not None:
                assessments = [a for a in assessments if a.weight_percentage >= min_weight]
            
            version = data["course_info"].approved_date if data.get("course_info") else None
        
        assessment_responses = [_assessment_to_response(a) for a in assessments]
        total_weight = sum(a.weight_percentage for a in assessment_responses)
        
        return AssessmentListResponse(
            subject_code=subject_code,
            approved_date=version,
            assessments=assessment_responses,
            total=len(assessment_responses),
            total_weight=total_weight,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching assessments for {subject_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch assessments: {str(e)}"
        )


@router.get("/{subject_code}/clos", response_model=CLOListResponse)
async def get_clos(
    subject_code: str,
    version: Optional[str] = Query(None, description="Specific version (approved_date)"),
    current_user: CurrentUser = Depends(get_current_user),
    repo: SyllabusEntityRepository = Depends(get_syllabus_repository),
):
    """
    Get CLOs (Course Learning Outcomes) for a syllabus.
    """
    subject_code = subject_code.upper()
    
    try:
        if version:
            data = repo.get_entities_by_version(subject_code, version)
        else:
            data = repo.get_latest_version(subject_code)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Syllabus not found for subject: {subject_code}"
            )
        
        clos = data.get("clos", [])
        clo_responses = [_clo_to_response(c) for c in clos]
        
        approved_date = version
        if not approved_date and data.get("course_info"):
            approved_date = data["course_info"].approved_date
        
        return CLOListResponse(
            subject_code=subject_code,
            approved_date=approved_date,
            clos=clo_responses,
            total=len(clo_responses),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching CLOs for {subject_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch CLOs: {str(e)}"
        )


@router.get("/{subject_code}/materials", response_model=MaterialListResponse)
async def get_materials(
    subject_code: str,
    version: Optional[str] = Query(None, description="Specific version (approved_date)"),
    current_user: CurrentUser = Depends(get_current_user),
    repo: SyllabusEntityRepository = Depends(get_syllabus_repository),
):
    """
    Get materials for a syllabus.
    """
    subject_code = subject_code.upper()
    
    try:
        if version:
            data = repo.get_entities_by_version(subject_code, version)
        else:
            data = repo.get_latest_version(subject_code)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Syllabus not found for subject: {subject_code}"
            )
        
        materials = data.get("materials", [])
        material_responses = [_material_to_response(m) for m in materials]
        
        approved_date = version
        if not approved_date and data.get("course_info"):
            approved_date = data["course_info"].approved_date
        
        return MaterialListResponse(
            subject_code=subject_code,
            approved_date=approved_date,
            materials=material_responses,
            total=len(material_responses),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching materials for {subject_code}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch materials: {str(e)}"
        )
