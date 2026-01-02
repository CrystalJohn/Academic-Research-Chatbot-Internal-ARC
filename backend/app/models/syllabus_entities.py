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
    Flexible validation to support various syllabus formats from FPT University.
    """
    model_config = ConfigDict(use_enum_values=True)
    
    subject_code: str = Field(
        ..., 
        description="Course code e.g. EXE401, SWR302, MAE101"
    )
    approved_date: str = Field(
        ...,
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
        """Validate subject code format - flexible to support various formats."""
        if not v:
            raise ValueError("subject_code cannot be empty")
        v = v.upper().strip()
        # Accept formats like: ABC123, AB1234, ABCD12, etc.
        # Just ensure it's alphanumeric and reasonable length
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError(f"subject_code must be alphanumeric, got: {v}")
        if len(v) < 3 or len(v) > 20:
            raise ValueError(f"subject_code length must be 3-20 chars, got: {len(v)}")
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
    Flexible to support various FPT University syllabus formats.
    """
    entity_type: Literal[EntityType.COURSE_INFO] = EntityType.COURSE_INFO
    entity_id: Literal["main"] = "main"
    
    course_name: str = Field(..., min_length=3, description="Full course name")
    credits: int = Field(default=3, ge=0, le=30, description="Number of credits")
    decision_no: str = Field(default="N/A", description="Official decision/approval number")
    department: Optional[str] = Field(None, description="Department offering the course")
    instructor: Optional[str] = Field(None, description="Primary instructor name")
    version_status: VersionStatus = Field(
        default=VersionStatus.APPROVED,
        description="Status of this syllabus version"
    )
    # Additional fields from FPT syllabus
    degree_level: Optional[str] = Field(None, description="Degree level: Bachelor, Master, etc.")
    time_allocation: Optional[str] = Field(None, description="Time allocation description")
    pre_requisite: Optional[str] = Field(None, description="Pre-requisite courses")
    description: Optional[str] = Field(None, description="Course description")
    student_tasks: Optional[str] = Field(None, description="Student tasks/requirements")
    scoring_scale: Optional[int] = Field(None, description="Scoring scale (e.g., 10)")
    min_avg_mark_to_pass: Optional[float] = Field(None, description="Minimum average mark to pass")

    @field_validator('course_name')
    @classmethod
    def validate_course_name(cls, v: str) -> str:
        """Validate course name."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("course_name must be at least 3 characters")
        return v

    @field_validator('decision_no')
    @classmethod
    def validate_decision_no(cls, v: str) -> str:
        """Validate decision number - allow empty/N/A."""
        if v is None:
            return "N/A"
        v = v.strip()
        return v if v else "N/A"

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
    Supports both CLO and LO formats from FPT University syllabi.
    """
    entity_type: Literal[EntityType.CLO] = EntityType.CLO
    
    clo_id: str = Field(
        ...,
        description="CLO/LO identifier e.g. CLO1, LO1"
    )
    description: str = Field(
        ...,
        min_length=5,
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
    # Additional fields from FPT syllabus
    clo_details: Optional[str] = Field(None, description="CLO details/summary")
    lo_details: Optional[str] = Field(None, description="Detailed LO breakdown")
    
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
        """Validate CLO/LO ID format - flexible to support CLO1, LO1, etc."""
        v = v.upper().strip()
        # Accept CLO1, LO1, CLO01, etc.
        if not (v.startswith('CLO') or v.startswith('LO')):
            # Try to normalize - if it's just a number, prefix with CLO
            if v.isdigit():
                v = f"CLO{v}"
            else:
                raise ValueError(f"clo_id must start with 'CLO' or 'LO', got: {v}")
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description - flexible length."""
        v = v.strip()
        if len(v) < 5:
            raise ValueError("description must be at least 5 characters")
        return v

    @field_validator('plo_mapping')
    @classmethod
    def validate_plo_mapping(cls, v: List[str]) -> List[str]:
        """Validate PLO mapping format - flexible."""
        validated = []
        for plo in v:
            plo = plo.upper().strip()
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
    Based on FPT syllabus structure: Session, Topic, Learning-Teaching Type, LO, ITU, 
    Student Materials, S-Download, Student's Tasks, URLs
    """
    entity_type: Literal[EntityType.SESSION] = EntityType.SESSION
    
    session_number: int = Field(
        ...,
        ge=1,
        le=200,  # Increased limit for longer courses
        description="Session number in sequence"
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Topics covered in this session"
    )
    clo_coverage: List[str] = Field(
        default_factory=list,
        description="CLOs/LOs addressed in this session (e.g. CLO1, LO1)"
    )
    mode: Optional[str] = Field(
        None,
        description="Session mode: Offline, Online, etc. (Learning-Teaching Type)"
    )
    session_type: Optional[str] = Field(
        None,
        description="Session type: TU, IT, ITU, U, LEC, LAB, etc."
    )
    materials: Optional[str] = Field(
        None,
        description="Student Materials for this session"
    )
    activities: Optional[str] = Field(
        None,
        description="Student's Tasks/Activities"
    )
    # Additional fields from FPT syllabus
    urls: Optional[str] = Field(None, description="Related URLs")
    download_link: Optional[str] = Field(None, description="S-Download link")
    
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
        """Validate topics list - allow empty for review/test sessions."""
        if not v:
            return []
        validated = []
        for topic in v:
            topic = topic.strip()
            if topic:
                validated.append(topic)
        return validated

    @field_validator('clo_coverage')
    @classmethod
    def validate_clo_coverage(cls, v: List[str]) -> List[str]:
        """Validate CLO/LO coverage format - flexible to support various formats."""
        validated = []
        for clo in v:
            clo = clo.upper().strip()
            if not clo:
                continue
            # Allow "All CLOs", "All LOs" or specific references
            if 'ALL' in clo:
                validated.append("All CLOs")
            else:
                # Keep as-is: CLO1, LO1, LO1,LO2, etc.
                validated.append(clo)
        return validated

    def to_llm_text(self) -> str:
        """Convert SessionEntity to LLM-optimized text."""
        lines = [f"Session {self.session_number}:"]
        lines.append(f"Topics: {', '.join(self.topics)}")
        if self.clo_coverage:
            lines.append(f"CLOs: {', '.join(self.clo_coverage)}")
        if self.mode:
            lines.append(f"Mode: {self.mode}")
        if self.session_type:
            lines.append(f"Type: {self.session_type}")
        if self.materials:
            lines.append(f"Materials: {self.materials}")
        if self.activities:
            lines.append(f"Activities: {self.activities}")
        return "\n".join(lines)


class AssessmentEntity(SyllabusEntityBase):
    """
    Assessment component entity.
    
    Based on actual syllabus structure:
    Category, Type, Part, Weight, Completion Criteria, Duration, CLO, 
    Question Type, No-Question, Knowledge and Skill, Grading Guide, Note
    """
    entity_type: Literal[EntityType.ASSESSMENT] = EntityType.ASSESSMENT
    
    category: str = Field(
        ...,
        min_length=2,
        description="Assessment category (e.g. On-going Project, Final Exam, Practical Exam)"
    )
    assessment_type: Optional[str] = Field(
        None,
        description="Type: on-going, Final exam, etc."
    )
    part: Optional[int] = Field(
        None,
        ge=1,
        description="Part number if multiple parts"
    )
    weight_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Weight as percentage of total grade"
    )
    completion_criteria: Optional[str] = Field(
        None,
        description="Completion criteria (e.g. >=, <)"
    )
    duration: Optional[str] = Field(
        None,
        description="Duration (e.g. 145 minutes, 60')"
    )
    clo_mapping: List[str] = Field(
        default_factory=list,
        description="CLOs assessed (e.g. All CLOs, CLO1, CLO2)"
    )
    question_type: Optional[str] = Field(
        None,
        description="Question type (e.g. Multiple Choices, Constructive Approach)"
    )
    no_question: Optional[str] = Field(
        None,
        description="Number of questions or N/A"
    )
    knowledge_and_skill: Optional[str] = Field(
        None,
        description="Knowledge and skills assessed"
    )
    grading_guide: Optional[str] = Field(
        None,
        description="Grading guide (e.g. In class by Instructor, by Exam Board)"
    )
    note: Optional[str] = Field(
        None,
        description="Additional notes about the assessment"
    )

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate assessment category."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("category must be at least 2 characters")
        return v

    @field_validator('weight_percentage')
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Validate weight percentage."""
        if v < 0 or v > 100:
            raise ValueError(f"weight_percentage must be 0-100, got: {v}")
        return round(v, 2)

    @field_validator('clo_mapping')
    @classmethod
    def validate_clo_mapping(cls, v: List[str]) -> List[str]:
        """Validate CLO mapping format."""
        validated = []
        for clo in v:
            clo = clo.upper().strip()
            # Allow "All CLOs" or specific CLO references
            if clo == "ALL CLOS" or clo == "ALL":
                validated.append("All CLOs")
            elif clo.startswith('CLO'):
                validated.append(clo)
            else:
                validated.append(clo)  # Keep as-is for flexibility
        return validated

    @model_validator(mode='before')
    @classmethod
    def validate_entity_id(cls, values):
        """Auto-generate entity_id from category and part if not provided."""
        if isinstance(values, dict):
            if 'entity_id' not in values or not values['entity_id']:
                category = values.get('category', '')
                part = values.get('part', '')
                entity_id = category.lower().replace(' ', '_').replace('-', '_')
                entity_id = ''.join(c for c in entity_id if c.isalnum() or c == '_')
                if part:
                    entity_id = f"{entity_id}_part{part}"
                values['entity_id'] = entity_id
        return values

    def to_llm_text(self) -> str:
        """Convert AssessmentEntity to LLM-optimized text."""
        part_str = f" (Part {self.part})" if self.part else ""
        lines = [f"{self.category}{part_str}: {self.weight_percentage}%"]
        if self.clo_mapping:
            lines.append(f"CLOs: {', '.join(self.clo_mapping)}")
        if self.duration:
            lines.append(f"Duration: {self.duration}")
        if self.question_type:
            lines.append(f"Question Type: {self.question_type}")
        if self.grading_guide:
            lines.append(f"Grading: {self.grading_guide}")
        if self.note:
            lines.append(f"Note: {self.note}")
        return "\n".join(lines)


class MaterialEntity(SyllabusEntityBase):
    """
    Learning material entity.
    
    Based on actual syllabus structure:
    Material Description, Author, Publisher, Published Date, Edition, ISBN, 
    IsMainMaterial, IsHardCopy, IsOnline, Note
    """
    entity_type: Literal[EntityType.MATERIAL] = EntityType.MATERIAL
    
    material_id: str = Field(..., description="Unique material identifier")
    title: str = Field(..., min_length=2, description="Material description/title")
    author: Optional[str] = Field(None, description="Author(s)")
    publisher: Optional[str] = Field(None, description="Publisher name")
    published_date: Optional[str] = Field(None, description="Publication year/date")
    edition: Optional[str] = Field(None, description="Edition (e.g. 3rd edition)")
    isbn: Optional[str] = Field(None, description="ISBN number")
    is_main_material: bool = Field(
        default=False,
        description="Whether this is a main/required material"
    )
    is_hard_copy: bool = Field(
        default=False,
        description="Available as hard copy"
    )
    is_online: bool = Field(
        default=False,
        description="Available online"
    )
    note: Optional[str] = Field(None, description="Additional notes or URL")
    
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

    def to_llm_text(self) -> str:
        """Convert MaterialEntity to LLM-optimized text."""
        main_marker = " [Main]" if self.is_main_material else ""
        lines = [f"{self.title}{main_marker}"]
        if self.author:
            lines.append(f"Author: {self.author}")
        if self.publisher:
            lines.append(f"Publisher: {self.publisher}")
        if self.published_date:
            lines.append(f"Published: {self.published_date}")
        if self.edition:
            lines.append(f"Edition: {self.edition}")
        if self.isbn:
            lines.append(f"ISBN: {self.isbn}")
        availability = []
        if self.is_hard_copy:
            availability.append("Hard Copy")
        if self.is_online:
            availability.append("Online")
        if availability:
            lines.append(f"Available: {', '.join(availability)}")
        if self.note:
            lines.append(f"Note: {self.note}")
        return "\n".join(lines)


# Union type for all entities
SyllabusEntity = Union[CourseInfo, CLOEntity, SessionEntity, AssessmentEntity, MaterialEntity]
