"""
Pydantic models for syllabus structured entities.

These models validate and normalize syllabus data extracted from HTML/API or PDF sources.
Each entity type represents a structured component of a university syllabus.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Optional, Literal, Union
from datetime import datetime, timezone
from enum import Enum


class EntityType(str, Enum):
    """Types of syllabus entities."""
    COURSE_INFO = "course_info"
    CLO = "clo"
    SESSION = "session"
    ASSESSMENT = "assessment"
    MATERIAL = "material"


class ExtractionMethod(str, Enum):
    """Methods used to extract entity data."""
    HTML_PARSER = "html_parser"
    TEXTRACT = "textract"
    LLM = "llm"
    LLM_PDF = "llm_pdf"
    MANUAL = "manual"


class VersionStatus(str, Enum):
    """Status of syllabus version."""
    DRAFT = "draft"
    APPROVED = "approved"
    ARCHIVED = "archived"


class SyllabusEntityBase(BaseModel):
    """
    Base model for all syllabus entities.
    
    Contains common fields shared across all entity types.
    """
    model_config = ConfigDict(use_enum_values=True)
    
    subject_code: str = Field(
        ..., 
        pattern=r"^[A-Z]{3}\d{3}$",
        description="Course code e.g. EXE401, SWR302"
    )
    approved_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        description="Version timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)"
    )
    entity_type: EntityType
    entity_id: str = Field(..., description="Unique identifier within entity type")
    extraction_method: ExtractionMethod = Field(
        default=ExtractionMethod.HTML_PARSER,
        description="Method used to extract this entity"
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in extraction accuracy (0-1)"
    )
    source_doc_id: Optional[str] = Field(
        None,
        description="Reference to source document in S3/DynamoDB"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Entity creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Entity last update timestamp"
    )

    @field_validator('subject_code')
    @classmethod
    def validate_subject_code(cls, v: str) -> str:
        """Validate subject code format."""
        if not v:
            raise ValueError("subject_code cannot be empty")
        v = v.upper().strip()
        if not v[0:3].isalpha() or not v[3:6].isdigit():
            raise ValueError(
                f"subject_code must be 3 letters + 3 digits (e.g. EXE401), got: {v}"
            )
        return v

    @field_validator('approved_date')
    @classmethod
    def validate_approved_date(cls, v: str) -> str:
        """Validate ISO 8601 timestamp format and range."""
        try:
            # Parse ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
            date_obj = datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
            # Check reasonable date range (2000-2100)
            if date_obj.year < 2000 or date_obj.year > 2100:
                raise ValueError(f"approved_date year must be between 2000-2100, got: {date_obj.year}")
            return v
        except ValueError as e:
            raise ValueError(f"approved_date must be ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ): {e}")

    def to_llm_text(self) -> str:
        """
        Convert entity to optimized text format for LLM context.
        
        Override in subclasses for entity-specific formatting.
        Returns a concise, human-readable string optimized for LLM consumption.
        """
        return f"{self.entity_type}: {self.entity_id} ({self.subject_code})"
    
    def get_display_date(self) -> str:
        """Get human-readable date from ISO timestamp."""
        try:
            dt = datetime.strptime(self.approved_date, "%Y-%m-%dT%H:%M:%SZ")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return self.approved_date


class CourseInfo(SyllabusEntityBase):
    """
    Course information entity.
    
    Contains basic course metadata like name, credits, decision number, etc.
    """
    entity_type: Literal[EntityType.COURSE_INFO] = EntityType.COURSE_INFO
    entity_id: Literal["main"] = "main"
    
    course_name: str = Field(..., min_length=5, description="Full course name")
    credits: int = Field(..., ge=1, le=20, description="Number of credits")
    decision_no: str = Field(..., description="Official decision/approval number")
    department: Optional[str] = Field(None, description="Department offering the course")
    instructor: Optional[str] = Field(None, description="Primary instructor name")
    version_status: VersionStatus = Field(
        default=VersionStatus.APPROVED,
        description="Status of this syllabus version"
    )

    @field_validator('course_name')
    @classmethod
    def validate_course_name(cls, v: str) -> str:
        """Validate course name."""
        v = v.strip()
        if len(v) < 5:
            raise ValueError("course_name must be at least 5 characters")
        return v

    @field_validator('decision_no')
    @classmethod
    def validate_decision_no(cls, v: str) -> str:
        """Validate decision number."""
        v = v.strip()
        if not v:
            raise ValueError("decision_no cannot be empty")
        return v

    def to_llm_text(self) -> str:
        """Convert CourseInfo to LLM-optimized text."""
        lines = [
            f"Course: {self.course_name} ({self.subject_code})",
            f"Credits: {self.credits}",
            f"Decision No: {self.decision_no}",
            f"Version: {self.get_display_date()} ({self.version_status})",
        ]
        if self.department:
            lines.append(f"Department: {self.department}")
        if self.instructor:
            lines.append(f"Instructor: {self.instructor}")
        return "\n".join(lines)


class CLOEntity(SyllabusEntityBase):
    """
    Course Learning Outcome (CLO) entity.
    
    Represents a specific learning objective students should achieve.
    """
    entity_type: Literal[EntityType.CLO] = EntityType.CLO
    
    clo_id: str = Field(
        ...,
        pattern=r"^CLO\d+$",
        description="CLO identifier e.g. CLO1, CLO2"
    )
    description: str = Field(
        ...,
        min_length=10,
        description="Detailed description of learning outcome"
    )
    plo_mapping: List[str] = Field(
        default_factory=list,
        description="Program Learning Outcomes this CLO maps to"
    )
    bloom_level: Optional[str] = Field(
        None,
        description="Bloom's taxonomy level (e.g. Remember, Understand, Apply)"
    )
    
    @model_validator(mode='before')
    @classmethod
    def set_entity_id(cls, values):
        """Auto-set entity_id from clo_id."""
        if isinstance(values, dict):
            if 'entity_id' not in values or not values['entity_id']:
                values['entity_id'] = values.get('clo_id', '')
        return values

    @field_validator('clo_id')
    @classmethod
    def validate_clo_id(cls, v: str) -> str:
        """Validate CLO ID format."""
        v = v.upper().strip()
        if not v.startswith('CLO'):
            raise ValueError(f"clo_id must start with 'CLO', got: {v}")
        try:
            num = int(v[3:])
            if num < 1 or num > 20:
                raise ValueError(f"CLO number must be 1-20, got: {num}")
        except ValueError:
            raise ValueError(f"clo_id must be CLO followed by number (e.g. CLO1), got: {v}")
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("description must be at least 10 characters")
        return v

    @field_validator('plo_mapping')
    @classmethod
    def validate_plo_mapping(cls, v: List[str]) -> List[str]:
        """Validate PLO mapping format."""
        validated = []
        for plo in v:
            plo = plo.upper().strip()
            if not plo.startswith('PLO'):
                raise ValueError(f"PLO must start with 'PLO', got: {plo}")
            validated.append(plo)
        return validated

    def to_llm_text(self) -> str:
        """Convert CLOEntity to LLM-optimized text."""
        lines = [f"{self.clo_id}: {self.description}"]
        if self.plo_mapping:
            lines.append(f"Maps to: {', '.join(self.plo_mapping)}")
        if self.bloom_level:
            lines.append(f"Bloom Level: {self.bloom_level}")
        return "\n".join(lines)


class SessionEntity(SyllabusEntityBase):
    """
    Session/class meeting entity.
    
    Represents a single class session with topics, activities, and materials.
    """
    entity_type: Literal[EntityType.SESSION] = EntityType.SESSION
    
    session_number: int = Field(
        ...,
        ge=1,
        le=20,
        description="Session number in sequence"
    )
    topics: List[str] = Field(
        ...,
        min_length=1,
        description="Topics covered in this session"
    )
    clo_coverage: List[str] = Field(
        default_factory=list,
        description="CLOs addressed in this session"
    )
    activities: Optional[str] = Field(
        None,
        description="Learning activities for this session"
    )
    materials_ref: List[str] = Field(
        default_factory=list,
        description="References to materials used (material_ids)"
    )
    
    @model_validator(mode='before')
    @classmethod
    def set_entity_id(cls, values):
        """Auto-set entity_id from session_number."""
        if isinstance(values, dict):
            if 'entity_id' not in values or not values['entity_id']:
                session_num = values.get('session_number')
                values['entity_id'] = str(session_num) if session_num else ''
        return values

    @field_validator('topics')
    @classmethod
    def validate_topics(cls, v: List[str]) -> List[str]:
        """Validate topics list."""
        if not v:
            raise ValueError("topics cannot be empty")
        validated = []
        for topic in v:
            topic = topic.strip()
            if topic:
                validated.append(topic)
        if not validated:
            raise ValueError("topics must contain at least one non-empty topic")
        return validated

    @field_validator('clo_coverage')
    @classmethod
    def validate_clo_coverage(cls, v: List[str]) -> List[str]:
        """Validate CLO coverage format."""
        validated = []
        for clo in v:
            clo = clo.upper().strip()
            if not clo.startswith('CLO'):
                raise ValueError(f"CLO must start with 'CLO', got: {clo}")
            validated.append(clo)
        return validated

    def to_llm_text(self) -> str:
        """Convert SessionEntity to LLM-optimized text."""
        lines = [f"Session {self.session_number}:"]
        lines.append(f"Topics: {', '.join(self.topics)}")
        if self.clo_coverage:
            lines.append(f"CLOs: {', '.join(self.clo_coverage)}")
        if self.activities:
            lines.append(f"Activities: {self.activities}")
        return "\n".join(lines)


class AssessmentEntity(SyllabusEntityBase):
    """
    Assessment component entity.
    
    Represents a graded component with weight percentage and CLO mapping.
    """
    entity_type: Literal[EntityType.ASSESSMENT] = EntityType.ASSESSMENT
    
    assessment_type: str = Field(
        ...,
        min_length=3,
        description="Type of assessment (e.g. Final Exam, Assignment)"
    )
    weight_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Weight as percentage of total grade"
    )
    clo_mapping: List[str] = Field(
        default_factory=list,
        description="CLOs assessed by this component"
    )
    duration: Optional[str] = Field(
        None,
        description="Duration or timing (e.g. Week 5, On-going)"
    )
    completion_criteria: Optional[str] = Field(
        None,
        description="Criteria for completion (e.g. Formative, Summative)"
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description of assessment"
    )

    @field_validator('assessment_type')
    @classmethod
    def validate_assessment_type(cls, v: str) -> str:
        """Validate assessment type."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("assessment_type must be at least 3 characters")
        return v

    @field_validator('weight_percentage')
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Validate weight percentage."""
        if v < 0 or v > 100:
            raise ValueError(f"weight_percentage must be 0-100, got: {v}")
        # Round to 2 decimal places
        return round(v, 2)

    @field_validator('clo_mapping')
    @classmethod
    def validate_clo_mapping(cls, v: List[str]) -> List[str]:
        """Validate CLO mapping format."""
        validated = []
        for clo in v:
            clo = clo.upper().strip()
            if not clo.startswith('CLO'):
                raise ValueError(f"CLO must start with 'CLO', got: {clo}")
            validated.append(clo)
        return validated

    @model_validator(mode='before')
    @classmethod
    def validate_entity_id(cls, values):
        """Auto-generate entity_id from assessment_type if not provided."""
        if isinstance(values, dict):
            if 'entity_id' not in values or not values['entity_id']:
                assessment_type = values.get('assessment_type', '')
                # Convert to snake_case for entity_id
                entity_id = assessment_type.lower().replace(' ', '_').replace('-', '_')
                # Remove special characters
                entity_id = ''.join(c for c in entity_id if c.isalnum() or c == '_')
                values['entity_id'] = entity_id
        return values

    def to_llm_text(self) -> str:
        """Convert AssessmentEntity to LLM-optimized text."""
        lines = [f"{self.assessment_type}: {self.weight_percentage}%"]
        if self.clo_mapping:
            lines.append(f"Assesses: {', '.join(self.clo_mapping)}")
        if self.duration:
            lines.append(f"Duration: {self.duration}")
        if self.completion_criteria:
            lines.append(f"Criteria: {self.completion_criteria}")
        if self.description:
            lines.append(f"Description: {self.description}")
        return "\n".join(lines)


class MaterialEntity(SyllabusEntityBase):
    """
    Learning material entity.
    
    Represents textbooks, slides, readings, or other course materials.
    """
    entity_type: Literal[EntityType.MATERIAL] = EntityType.MATERIAL
    
    material_id: str = Field(..., description="Unique material identifier")
    title: str = Field(..., min_length=2, description="Material title")
    type: Optional[Literal["textbook", "slide", "reading", "video", "other"]] = Field(
        None,
        description="Type of material"
    )
    author: Optional[str] = Field(None, description="Author or creator")
    session_refs: List[int] = Field(
        default_factory=list,
        description="Session numbers where this material is used"
    )
    is_main_material: bool = Field(
        default=False,
        description="Whether this is a main/required material"
    )
    
    @model_validator(mode='before')
    @classmethod
    def set_entity_id(cls, values):
        """Auto-set entity_id from material_id."""
        if isinstance(values, dict):
            if 'entity_id' not in values or not values['entity_id']:
                values['entity_id'] = values.get('material_id', '')
        return values

    @field_validator('material_id')
    @classmethod
    def validate_material_id(cls, v: str) -> str:
        """Validate material ID."""
        v = v.strip()
        if not v:
            raise ValueError("material_id cannot be empty")
        return v

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("title must be at least 2 characters")
        return v

    @field_validator('session_refs')
    @classmethod
    def validate_session_refs(cls, v: List[int]) -> List[int]:
        """Validate session references."""
        validated = []
        for session_num in v:
            if session_num < 1 or session_num > 20:
                raise ValueError(f"session_refs must be 1-20, got: {session_num}")
            validated.append(session_num)
        return sorted(list(set(validated)))  # Remove duplicates and sort

    def to_llm_text(self) -> str:
        """Convert MaterialEntity to LLM-optimized text."""
        material_type = f" ({self.type})" if self.type else ""
        main_marker = " [Main]" if self.is_main_material else ""
        lines = [f"{self.title}{material_type}{main_marker}"]
        if self.author:
            lines.append(f"Author: {self.author}")
        if self.session_refs:
            sessions = ", ".join(str(s) for s in self.session_refs)
            lines.append(f"Used in sessions: {sessions}")
        return "\n".join(lines)


# Union type for all entities
SyllabusEntity = Union[CourseInfo, CLOEntity, SessionEntity, AssessmentEntity, MaterialEntity]
