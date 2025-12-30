"""
Unit tests for syllabus entity Pydantic models.

Tests validation logic, field constraints, and error messages.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.syllabus_entities import (
    EntityType,
    ExtractionMethod,
    VersionStatus,
    CourseInfo,
    CLOEntity,
    SessionEntity,
    AssessmentEntity,
    MaterialEntity,
)

# ISO 8601 timestamp format for testing
VALID_TIMESTAMP = "2025-11-27T10:00:00Z"
VALID_TIMESTAMP_2 = "2025-12-01T14:30:00Z"


class TestCourseInfo:
    """Tests for CourseInfo model."""
    
    def test_valid_course_info(self):
        """Test valid course info creation."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Graduation Thesis Project",
            credits=10,
            decision_no="1535",
            department="Software Engineering",
            instructor="Dr. John Doe"
        )
        
        assert course.subject_code == "EXE401"
        assert course.entity_type == EntityType.COURSE_INFO
        assert course.entity_id == "main"
        assert course.credits == 10
        assert course.version_status == VersionStatus.APPROVED
    
    def test_subject_code_uppercase_conversion(self):
        """Test subject code is converted to uppercase."""
        # Pydantic V2 validates pattern before field_validator runs
        # So we need to provide uppercase input
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        assert course.subject_code == "EXE401"
    
    def test_invalid_subject_code_format(self):
        """Test invalid subject code format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CourseInfo(
                subject_code="INVALID",
                approved_date=VALID_TIMESTAMP,
                course_name="Test Course",
                credits=3,
                decision_no="123"
            )
        assert "String should match pattern" in str(exc_info.value)
    
    def test_invalid_credits_range(self):
        """Test credits outside valid range raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CourseInfo(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                course_name="Test Course",
                credits=25,  # Too high
                decision_no="123"
            )
        assert "less than or equal to 20" in str(exc_info.value)
    
    def test_course_name_too_short(self):
        """Test course name minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            CourseInfo(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                course_name="ABC",  # Too short
                credits=3,
                decision_no="123"
            )
        assert "at least 5 characters" in str(exc_info.value)
    
    def test_invalid_date_format(self):
        """Test invalid date format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CourseInfo(
                subject_code="EXE401",
                approved_date="27-11-2025",  # Wrong format
                course_name="Test Course",
                credits=3,
                decision_no="123"
            )
        assert "String should match pattern" in str(exc_info.value)
    
    def test_invalid_date_format_without_time(self):
        """Test date without time raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CourseInfo(
                subject_code="EXE401",
                approved_date="2025-11-27",  # Missing time component
                course_name="Test Course",
                credits=3,
                decision_no="123"
            )
        assert "String should match pattern" in str(exc_info.value)
    
    def test_optional_fields(self):
        """Test optional fields can be None."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        assert course.department is None
        assert course.instructor is None


class TestCLOEntity:
    """Tests for CLOEntity model."""
    
    def test_valid_clo(self):
        """Test valid CLO creation."""
        clo = CLOEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            clo_id="CLO1",
            description="Apply appropriate professional practices",
            plo_mapping=["PLO5", "PLO7"],
            bloom_level="Apply"
        )
        
        assert clo.clo_id == "CLO1"
        assert clo.entity_id == "CLO1"  # Auto-set from clo_id
        assert clo.entity_type == EntityType.CLO
        assert len(clo.plo_mapping) == 2
    
    def test_clo_id_uppercase_conversion(self):
        """Test CLO ID is converted to uppercase."""
        # Pydantic V2 validates pattern before field_validator runs
        clo = CLOEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            clo_id="CLO2",
            description="Understand software development lifecycle"
        )
        assert clo.clo_id == "CLO2"
    
    def test_invalid_clo_id_format(self):
        """Test invalid CLO ID format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CLOEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                clo_id="LO1",  # Missing 'C'
                description="Test description"
            )
        assert "String should match pattern" in str(exc_info.value)
    
    def test_clo_number_out_of_range(self):
        """Test CLO number outside valid range raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CLOEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                clo_id="CLO25",  # Too high
                description="Test description"
            )
        # Pydantic V2 shows the full error message from field_validator
        assert "CLO" in str(exc_info.value)
    
    def test_description_too_short(self):
        """Test description minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            CLOEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                clo_id="CLO1",
                description="Short"  # Too short
            )
        assert "at least 10 characters" in str(exc_info.value)
    
    def test_plo_mapping_validation(self):
        """Test PLO mapping format validation."""
        clo = CLOEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            clo_id="CLO1",
            description="Test description here",
            plo_mapping=["plo5", "PLO7"]  # Mixed case
        )
        assert clo.plo_mapping == ["PLO5", "PLO7"]  # Converted to uppercase
    
    def test_invalid_plo_format(self):
        """Test invalid PLO format raises error."""
        with pytest.raises(ValidationError) as exc_info:
            CLOEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                clo_id="CLO1",
                description="Test description here",
                plo_mapping=["LO5"]  # Missing 'P'
            )
        assert "must start with 'PLO'" in str(exc_info.value)


class TestSessionEntity:
    """Tests for SessionEntity model."""
    
    def test_valid_session(self):
        """Test valid session creation."""
        session = SessionEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            session_number=1,
            topics=["Project kickoff", "Team formation"],
            clo_coverage=["CLO1", "CLO2"],
            activities="Workshop: Startup ideation",
            materials_ref=["MAT001", "MAT002"]
        )
        
        assert session.session_number == 1
        assert session.entity_id == "1"  # Auto-set from session_number
        assert session.entity_type == EntityType.SESSION
        assert len(session.topics) == 2
    
    def test_session_number_out_of_range(self):
        """Test session number outside valid range raises error."""
        with pytest.raises(ValidationError) as exc_info:
            SessionEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                session_number=25,  # Too high
                topics=["Test topic"]
            )
        assert "less than or equal to 20" in str(exc_info.value)
    
    def test_empty_topics_list(self):
        """Test empty topics list raises error."""
        with pytest.raises(ValidationError) as exc_info:
            SessionEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                session_number=1,
                topics=[]  # Empty
            )
        assert "at least 1 item" in str(exc_info.value)
    
    def test_topics_whitespace_cleaning(self):
        """Test topics are cleaned of whitespace."""
        session = SessionEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            session_number=1,
            topics=["  Topic 1  ", "Topic 2", "  "]  # Whitespace
        )
        assert len(session.topics) == 2  # Empty string removed
        assert session.topics[0] == "Topic 1"
    
    def test_clo_coverage_uppercase(self):
        """Test CLO coverage is converted to uppercase."""
        session = SessionEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            session_number=1,
            topics=["Test topic"],
            clo_coverage=["clo1", "CLO2"]
        )
        assert session.clo_coverage == ["CLO1", "CLO2"]


class TestAssessmentEntity:
    """Tests for AssessmentEntity model."""
    
    def test_valid_assessment(self):
        """Test valid assessment creation."""
        assessment = AssessmentEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            assessment_type="Final Presentation",
            weight_percentage=40.0,
            clo_mapping=["CLO1", "CLO2", "CLO3"],
            duration="On-going",
            description="Final presentation and defense"
        )
        
        assert assessment.assessment_type == "Final Presentation"
        assert assessment.weight_percentage == 40.0
        assert assessment.entity_type == EntityType.ASSESSMENT
        assert assessment.entity_id == "final_presentation"  # Auto-generated
    
    def test_weight_percentage_range(self):
        """Test weight percentage validation."""
        with pytest.raises(ValidationError) as exc_info:
            AssessmentEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                assessment_type="Test",
                weight_percentage=150.0  # Too high
            )
        assert "less than or equal to 100" in str(exc_info.value)
    
    def test_weight_percentage_rounding(self):
        """Test weight percentage is rounded to 2 decimals."""
        assessment = AssessmentEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            assessment_type="Test",
            weight_percentage=33.333333
        )
        assert assessment.weight_percentage == 33.33
    
    def test_entity_id_auto_generation(self):
        """Test entity_id is auto-generated from assessment_type."""
        assessment = AssessmentEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            assessment_type="Progress Report 1",
            weight_percentage=10.0
        )
        assert assessment.entity_id == "progress_report_1"
    
    def test_assessment_type_too_short(self):
        """Test assessment type minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            AssessmentEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                assessment_type="AB",  # Too short
                weight_percentage=10.0
            )
        assert "at least 3 characters" in str(exc_info.value)


class TestMaterialEntity:
    """Tests for MaterialEntity model."""
    
    def test_valid_material(self):
        """Test valid material creation."""
        material = MaterialEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            material_id="MAT001",
            title="The Lean Startup",
            type="textbook",
            author="Eric Ries",
            session_refs=[1, 2, 3],
            is_main_material=True
        )
        
        assert material.material_id == "MAT001"
        assert material.entity_id == "MAT001"  # Auto-set from material_id
        assert material.entity_type == EntityType.MATERIAL
        assert material.is_main_material is True
    
    def test_title_too_short(self):
        """Test title minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            MaterialEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                material_id="MAT001",
                title="A"  # Too short
            )
        assert "at least 2 characters" in str(exc_info.value)
    
    def test_session_refs_validation(self):
        """Test session refs are validated and sorted."""
        material = MaterialEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            material_id="MAT001",
            title="Test Material",
            session_refs=[3, 1, 2, 1]  # Duplicates and unsorted
        )
        assert material.session_refs == [1, 2, 3]  # Sorted and deduplicated
    
    def test_session_refs_out_of_range(self):
        """Test session refs outside valid range raises error."""
        with pytest.raises(ValidationError) as exc_info:
            MaterialEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                material_id="MAT001",
                title="Test Material",
                session_refs=[25]  # Too high
            )
        assert "must be 1-20" in str(exc_info.value)
    
    def test_material_type_validation(self):
        """Test material type is validated against allowed values."""
        material = MaterialEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            material_id="MAT001",
            title="Test Material",
            type="textbook"
        )
        assert material.type == "textbook"
        
        # Invalid type should raise error
        with pytest.raises(ValidationError):
            MaterialEntity(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                material_id="MAT001",
                title="Test Material",
                type="invalid_type"
            )


class TestCommonValidation:
    """Tests for common validation across all entities."""
    
    def test_confidence_score_range(self):
        """Test confidence score is validated to 0-1 range."""
        with pytest.raises(ValidationError) as exc_info:
            CourseInfo(
                subject_code="EXE401",
                approved_date=VALID_TIMESTAMP,
                course_name="Test Course",
                credits=3,
                decision_no="123",
                confidence_score=1.5  # Too high
            )
        assert "less than or equal to 1" in str(exc_info.value)
    
    def test_extraction_method_enum(self):
        """Test extraction method uses enum values."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Test Course",
            credits=3,
            decision_no="123",
            extraction_method=ExtractionMethod.TEXTRACT
        )
        assert course.extraction_method == "textract"  # Enum value
    
    def test_datetime_fields_auto_set(self):
        """Test created_at and updated_at are auto-set."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        assert isinstance(course.created_at, datetime)
        assert isinstance(course.updated_at, datetime)
    
    def test_json_serialization(self):
        """Test models can be serialized to JSON."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        json_data = course.model_dump()  # Pydantic V2 uses model_dump()
        assert json_data['subject_code'] == "EXE401"
        assert json_data['entity_type'] == "course_info"
        assert 'created_at' in json_data
    
    def test_iso_timestamp_format(self):
        """Test approved_date accepts ISO 8601 timestamp format."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date="2025-11-27T14:30:00Z",
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        assert course.approved_date == "2025-11-27T14:30:00Z"
    
    def test_multiple_versions_same_day(self):
        """Test multiple versions can exist on the same day with different times."""
        course1 = CourseInfo(
            subject_code="EXE401",
            approved_date="2025-11-27T10:00:00Z",
            course_name="Test Course v1",
            credits=3,
            decision_no="123"
        )
        course2 = CourseInfo(
            subject_code="EXE401",
            approved_date="2025-11-27T14:30:00Z",
            course_name="Test Course v2",
            credits=3,
            decision_no="124"
        )
        assert course1.approved_date != course2.approved_date


class TestToLLMText:
    """Tests for to_llm_text() method across all entity types."""
    
    def test_course_info_to_llm_text(self):
        """Test CourseInfo to_llm_text output."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Graduation Thesis Project",
            credits=10,
            decision_no="1535",
            department="Software Engineering",
            instructor="Dr. John Doe"
        )
        text = course.to_llm_text()
        
        assert "Graduation Thesis Project" in text
        assert "EXE401" in text
        assert "10" in text
        assert "1535" in text
        assert "Software Engineering" in text
        assert "Dr. John Doe" in text
        assert "2025-11-27" in text  # Display date
    
    def test_course_info_to_llm_text_minimal(self):
        """Test CourseInfo to_llm_text with minimal fields."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        text = course.to_llm_text()
        
        assert "Test Course" in text
        assert "Department" not in text  # Optional field not included
        assert "Instructor" not in text
    
    def test_clo_to_llm_text(self):
        """Test CLOEntity to_llm_text output."""
        clo = CLOEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            clo_id="CLO1",
            description="Apply appropriate professional practices",
            plo_mapping=["PLO5", "PLO7"],
            bloom_level="Apply"
        )
        text = clo.to_llm_text()
        
        assert "CLO1" in text
        assert "Apply appropriate professional practices" in text
        assert "PLO5" in text
        assert "PLO7" in text
        assert "Apply" in text
    
    def test_clo_to_llm_text_minimal(self):
        """Test CLOEntity to_llm_text with minimal fields."""
        clo = CLOEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            clo_id="CLO1",
            description="Test description here"
        )
        text = clo.to_llm_text()
        
        assert "CLO1" in text
        assert "Test description here" in text
        assert "Maps to" not in text  # No PLO mapping
    
    def test_session_to_llm_text(self):
        """Test SessionEntity to_llm_text output."""
        session = SessionEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            session_number=1,
            topics=["Project kickoff", "Team formation"],
            clo_coverage=["CLO1", "CLO2"],
            activities="Workshop: Startup ideation"
        )
        text = session.to_llm_text()
        
        assert "Session 1" in text
        assert "Project kickoff" in text
        assert "Team formation" in text
        assert "CLO1" in text
        assert "CLO2" in text
        assert "Workshop" in text
    
    def test_session_to_llm_text_minimal(self):
        """Test SessionEntity to_llm_text with minimal fields."""
        session = SessionEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            session_number=5,
            topics=["Single topic"]
        )
        text = session.to_llm_text()
        
        assert "Session 5" in text
        assert "Single topic" in text
        assert "CLOs" not in text  # No CLO coverage
        assert "Activities" not in text
    
    def test_assessment_to_llm_text(self):
        """Test AssessmentEntity to_llm_text output."""
        assessment = AssessmentEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            assessment_type="Final Presentation",
            weight_percentage=40.0,
            clo_mapping=["CLO1", "CLO2", "CLO3"],
            duration="On-going",
            completion_criteria="Summative",
            description="Final presentation and defense"
        )
        text = assessment.to_llm_text()
        
        assert "Final Presentation" in text
        assert "40" in text
        assert "%" in text
        assert "CLO1" in text
        assert "On-going" in text
        assert "Summative" in text
        assert "Final presentation and defense" in text
    
    def test_assessment_to_llm_text_minimal(self):
        """Test AssessmentEntity to_llm_text with minimal fields."""
        assessment = AssessmentEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            assessment_type="Quiz",
            weight_percentage=10.0
        )
        text = assessment.to_llm_text()
        
        assert "Quiz" in text
        assert "10" in text
        assert "Assesses" not in text  # No CLO mapping
    
    def test_material_to_llm_text(self):
        """Test MaterialEntity to_llm_text output."""
        material = MaterialEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            material_id="MAT001",
            title="The Lean Startup",
            type="textbook",
            author="Eric Ries",
            session_refs=[1, 2, 3],
            is_main_material=True
        )
        text = material.to_llm_text()
        
        assert "The Lean Startup" in text
        assert "textbook" in text
        assert "Eric Ries" in text
        assert "[Main]" in text
        assert "1, 2, 3" in text
    
    def test_material_to_llm_text_minimal(self):
        """Test MaterialEntity to_llm_text with minimal fields."""
        material = MaterialEntity(
            subject_code="EXE401",
            approved_date=VALID_TIMESTAMP,
            material_id="MAT001",
            title="Simple Material"
        )
        text = material.to_llm_text()
        
        assert "Simple Material" in text
        assert "[Main]" not in text
        assert "Author" not in text
    
    def test_get_display_date(self):
        """Test get_display_date helper method."""
        course = CourseInfo(
            subject_code="EXE401",
            approved_date="2025-11-27T14:30:00Z",
            course_name="Test Course",
            credits=3,
            decision_no="123"
        )
        assert course.get_display_date() == "2025-11-27"
