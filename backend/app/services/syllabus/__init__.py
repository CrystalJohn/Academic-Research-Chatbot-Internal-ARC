"""
Syllabus structured ingestion services.

This package contains services for extracting, storing, and querying
structured syllabus entities from markdown files.
"""

from .entity_repository import SyllabusEntityRepository
from .markdown_parser import (
    SyllabusMarkdownParser,
    ParsedSyllabus,
    ParsedSession,
    ParsedAssessment,
    parse_syllabus_file,
    convert_to_entities,
)

__all__ = [
    "SyllabusEntityRepository",
    "SyllabusMarkdownParser",
    "ParsedSyllabus",
    "ParsedSession",
    "ParsedAssessment",
    "parse_syllabus_file",
    "convert_to_entities",
]
