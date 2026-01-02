"""
import các models để lưu vào DynamoDB
Syllabus Entity Repository

Manages CRUD operations for syllabus entities in DynamoDB.
Supports all access patterns defined in the design document.

Access Patterns:
- AP1: Get latest syllabus by subject_code
- AP2: Get all entities for syllabus version
- AP3: Get assessments by syllabus version
- AP4: Find sessions covering specific CLO
- AP5: Compare two syllabus versions
- AP6: List all versions of a subject
- AP7: Query assessments by weight range
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from app.models.syllabus_entities import (
    SyllabusEntity,
    CourseInfo,
    CLOEntity,
    SessionEntity,
    AssessmentEntity,
    MaterialEntity,
    EntityType,
)


class SyllabusEntityRepository:
    """
    Repository for syllabus entity operations in DynamoDB.
    
    Table schema:
    - PK: SUBJECT#{subject_code}
    - SK: VERSION#{approved_date}#ENTITY#{entity_type}#{entity_id}
    - GSI1PK: SUBJECT#{subject_code}#VERSION#{approved_date}
    - GSI1SK: ENTITY#{entity_type}#{entity_id}
    - GSI2PK: SUBJECT#{subject_code}#CLO#{clo_id}
    - GSI2SK: SESSION#{session_number}
    """
    
    # DynamoDB batch write limit
    BATCH_WRITE_LIMIT = 25
    
    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_client=None,
        region_name: Optional[str] = None
    ):
        """
        Initialize the repository.
        
        Args:
            table_name: DynamoDB table name. Defaults to env var.
            dynamodb_client: Optional boto3 DynamoDB client for testing.
            region_name: AWS region. Defaults to env var or ap-southeast-1.
        """
        self.table_name = table_name or os.getenv(
            "SYLLABUS_ENTITIES_TABLE_NAME",
            "arc-chatbot-dev-syllabus-entities"
        )
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-southeast-1")
        
        if dynamodb_client:
            self._client = dynamodb_client
        else:
            self._client = boto3.client(
                "dynamodb",
                region_name=self.region_name
            )
    
    def put_entity(self, entity: SyllabusEntity) -> Dict[str, Any]:
        """
        Store a single syllabus entity.
        
        Args:
            entity: Syllabus entity to store
            
        Returns:
            dict: Stored entity data
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        item = self._entity_to_dynamodb_item(entity)
        
        self._client.put_item(
            TableName=self.table_name,
            Item=item
        )
        
        return entity.model_dump()
    
    def put_entities_batch(self, entities: List[SyllabusEntity]) -> Dict[str, Any]:
        """
        Store multiple entities in batches.
        
        Handles DynamoDB's 25-item batch limit by splitting into multiple requests.
        
        Args:
            entities: List of entities to store
            
        Returns:
            dict: Summary with success_count and failed_items
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        if not entities:
            return {"success_count": 0, "failed_items": []}
        
        success_count = 0
        failed_items = []
        
        # Process in batches of 25
        for i in range(0, len(entities), self.BATCH_WRITE_LIMIT):
            batch = entities[i:i + self.BATCH_WRITE_LIMIT]
            
            # Build batch write request
            request_items = []
            for entity in batch:
                item = self._entity_to_dynamodb_item(entity)
                request_items.append({
                    "PutRequest": {"Item": item}
                })
            
            try:
                response = self._client.batch_write_item(
                    RequestItems={
                        self.table_name: request_items
                    }
                )
                
                # Handle unprocessed items
                unprocessed = response.get("UnprocessedItems", {}).get(self.table_name, [])
                success_count += len(batch) - len(unprocessed)
                
                if unprocessed:
                    failed_items.extend([
                        req["PutRequest"]["Item"]["SK"]["S"]
                        for req in unprocessed
                    ])
            except ClientError as e:
                # Log error and continue with next batch
                failed_items.extend([
                    f"{entity.entity_type}#{entity.entity_id}"
                    for entity in batch
                ])
        
        return {
            "success_count": success_count,
            "failed_items": failed_items
        }
    
    def get_latest_version(self, subject_code: str) -> Optional[Dict[str, List[SyllabusEntity]]]:
        """
        Get latest version of syllabus with all entities (AP1).
        
        Args:
            subject_code: Course code (e.g., EXE401)
            
        Returns:
            dict: {
                "course_info": CourseInfo,
                "clos": List[CLOEntity],
                "sessions": List[SessionEntity],
                "assessments": List[AssessmentEntity],
                "materials": List[MaterialEntity]
            } or None if not found
        """
        # Query for latest version by sorting SK descending
        response = self._client.query(
            TableName=self.table_name,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": {"S": f"SUBJECT#{subject_code}"},
                ":sk_prefix": {"S": "VERSION#"}
            },
            ScanIndexForward=False,  # Sort descending to get latest first
            Limit=100  # Get enough items to cover one full syllabus
        )
        
        items = response.get("Items", [])
        if not items:
            return None
        
        # Extract the latest version date from first item
        first_sk = items[0]["SK"]["S"]
        # SK format: VERSION#{approved_date}#ENTITY#{entity_type}#{entity_id}
        version_date = first_sk.split("#")[1]
        
        # Filter items for this version only
        version_items = [
            item for item in items
            if f"VERSION#{version_date}#" in item["SK"]["S"]
        ]
        
        return self._group_entities_by_type(version_items)
    
    def get_entities_by_version(
        self,
        subject_code: str,
        approved_date: str
    ) -> Dict[str, List[SyllabusEntity]]:
        """
        Get all entities for a specific syllabus version (AP2).
        
        Args:
            subject_code: Course code (e.g., EXE401)
            approved_date: Version timestamp (ISO 8601 format)
            
        Returns:
            dict: Grouped entities by type
        """
        response = self._client.query(
            TableName=self.table_name,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": {"S": f"SUBJECT#{subject_code}"},
                ":sk_prefix": {"S": f"VERSION#{approved_date}#ENTITY#"}
            }
        )
        
        items = response.get("Items", [])
        return self._group_entities_by_type(items)
    
    def get_assessments(
        self,
        subject_code: str,
        approved_date: str,
        min_weight: Optional[float] = None
    ) -> List[AssessmentEntity]:
        """
        Get assessments for a specific syllabus version (AP3).
        
        Args:
            subject_code: Course code
            approved_date: Version timestamp
            min_weight: Optional minimum weight filter
            
        Returns:
            List of assessment entities
        """
        # Use GSI1 for efficient entity type filtering
        response = self._client.query(
            TableName=self.table_name,
            IndexName="entity-type-index",
            KeyConditionExpression="GSI1PK = :gsi1pk AND begins_with(GSI1SK, :gsi1sk_prefix)",
            ExpressionAttributeValues={
                ":gsi1pk": {"S": f"SUBJECT#{subject_code}#VERSION#{approved_date}"},
                ":gsi1sk_prefix": {"S": f"ENTITY#{EntityType.ASSESSMENT.value}#"}
            }
        )
        
        items = response.get("Items", [])
        assessments = [
            self._dynamodb_item_to_entity(item)
            for item in items
        ]
        
        # Apply weight filter if specified
        if min_weight is not None:
            assessments = [
                a for a in assessments
                if isinstance(a, AssessmentEntity) and a.weight_percentage >= min_weight
            ]
        
        return assessments
    
    def get_sessions_by_clo(
        self,
        subject_code: str,
        clo_id: str,
        approved_date: Optional[str] = None
    ) -> List[SessionEntity]:
        """
        Find sessions covering a specific CLO (AP4).
        
        Args:
            subject_code: Course code
            clo_id: CLO identifier (e.g., CLO1)
            approved_date: Optional version filter (uses latest if not specified)
            
        Returns:
            List of session entities
        """
        # Use GSI2 for CLO-to-session mapping
        response = self._client.query(
            TableName=self.table_name,
            IndexName="clo-session-index",
            KeyConditionExpression="GSI2PK = :gsi2pk",
            ExpressionAttributeValues={
                ":gsi2pk": {"S": f"SUBJECT#{subject_code}#CLO#{clo_id}"}
            }
        )
        
        items = response.get("Items", [])
        sessions = [
            self._dynamodb_item_to_entity(item)
            for item in items
        ]
        
        # Filter by version if specified
        if approved_date:
            sessions = [
                s for s in sessions
                if isinstance(s, SessionEntity) and s.approved_date == approved_date
            ]
        
        return sessions
    
    def list_versions(self, subject_code: str) -> List[Dict[str, str]]:
        """
        List all versions of a subject (AP6).
        
        Args:
            subject_code: Course code
            
        Returns:
            List of version info dicts with approved_date and decision_no
        """
        response = self._client.query(
            TableName=self.table_name,
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": {"S": f"SUBJECT#{subject_code}"},
                ":sk_prefix": {"S": "VERSION#"}
            },
            ProjectionExpression="SK, decision_no, approved_date",
            ScanIndexForward=False  # Latest first
        )
        
        items = response.get("Items", [])
        
        # Extract unique versions (one per approved_date)
        versions = {}
        for item in items:
            sk = item["SK"]["S"]
            # Extract approved_date from SK
            approved_date = sk.split("#")[1]
            
            if approved_date not in versions:
                versions[approved_date] = {
                    "approved_date": approved_date,
                    "decision_no": item.get("decision_no", {}).get("S", "")
                }
        
        return list(versions.values())
    
    def _entity_to_dynamodb_item(self, entity: SyllabusEntity) -> Dict[str, Any]:
        """
        Convert Pydantic entity to DynamoDB item format.
        
        Args:
            entity: Syllabus entity
            
        Returns:
            DynamoDB item dict
        """
        # Build primary key
        # Convert enum values to strings
        entity_type_str = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
        
        pk = f"SUBJECT#{entity.subject_code}"
        sk = f"VERSION#{entity.approved_date}#ENTITY#{entity_type_str}#{entity.entity_id}"
        
        # Build GSI1 keys
        gsi1pk = f"SUBJECT#{entity.subject_code}#VERSION#{entity.approved_date}"
        gsi1sk = f"ENTITY#{entity_type_str}#{entity.entity_id}"
        
        # Start with base item
        # Convert enum values to strings
        entity_type_str = entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type)
        extraction_method_str = entity.extraction_method.value if hasattr(entity.extraction_method, 'value') else str(entity.extraction_method)
        
        item = {
            "PK": {"S": pk},
            "SK": {"S": sk},
            "GSI1PK": {"S": gsi1pk},
            "GSI1SK": {"S": gsi1sk},
            "entity_type": {"S": entity_type_str},
            "entity_id": {"S": entity.entity_id},
            "subject_code": {"S": entity.subject_code},
            "approved_date": {"S": entity.approved_date},
            "extraction_method": {"S": extraction_method_str},
            "confidence_score": {"N": str(entity.confidence_score)},
            "created_at": {"S": entity.created_at.isoformat().replace("+00:00", "Z")},
            "updated_at": {"S": entity.updated_at.isoformat().replace("+00:00", "Z")},
        }
        
        # Add optional source_doc_id
        if entity.source_doc_id:
            item["source_doc_id"] = {"S": entity.source_doc_id}
        
        # Add entity-specific fields
        entity_dict = entity.model_dump(exclude={"created_at", "updated_at"})
        
        for key, value in entity_dict.items():
            if key in ["PK", "SK", "GSI1PK", "GSI1SK", "entity_type", "entity_id",
                      "subject_code", "approved_date", "extraction_method",
                      "confidence_score", "source_doc_id"]:
                continue  # Already added
            
            if value is None:
                continue  # Skip None values
            
            # Convert Python types to DynamoDB types
            # Check bool BEFORE int/float since bool is subclass of int
            if isinstance(value, bool):
                item[key] = {"BOOL": value}
            elif isinstance(value, str):
                item[key] = {"S": value}
            elif isinstance(value, (int, float)):
                item[key] = {"N": str(value)}
            elif isinstance(value, list):
                if not value:
                    continue  # Skip empty lists
                # Convert list to DynamoDB list
                if all(isinstance(v, str) for v in value):
                    item[key] = {"SS": value}  # String set
                elif all(isinstance(v, (int, float)) for v in value):
                    item[key] = {"NS": [str(v) for v in value]}  # Number set
                else:
                    # Mixed types - use list
                    item[key] = {"L": [self._python_to_dynamodb(v) for v in value]}
        
        # Add GSI2 keys for SessionEntity with CLO coverage
        if isinstance(entity, SessionEntity) and entity.clo_coverage:
            # Create one GSI2 entry per CLO for efficient querying
            # Note: DynamoDB doesn't support multiple GSI2 values per item
            # We'll use the first CLO for the GSI2 key
            # For complete CLO-to-session mapping, we'd need separate items or denormalization
            if entity.clo_coverage:
                first_clo = entity.clo_coverage[0]
                item["GSI2PK"] = {"S": f"SUBJECT#{entity.subject_code}#CLO#{first_clo}"}
                item["GSI2SK"] = {"S": f"SESSION#{entity.session_number}"}
        
        return item
    
    def _dynamodb_item_to_entity(self, item: Dict[str, Any]) -> SyllabusEntity:
        """
        Convert DynamoDB item to Pydantic entity.
        
        Args:
            item: DynamoDB item dict
            
        Returns:
            Syllabus entity instance
        """
        # Parse basic fields
        parsed = {}
        for key, value in item.items():
            if key in ["PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK"]:
                continue  # Skip key fields
            
            if "S" in value:
                parsed[key] = value["S"]
            elif "N" in value:
                # Try to parse as int first, then float
                try:
                    parsed[key] = int(value["N"])
                except ValueError:
                    parsed[key] = float(value["N"])
            elif "BOOL" in value:
                parsed[key] = value["BOOL"]
            elif "SS" in value:
                parsed[key] = value["SS"]
            elif "NS" in value:
                parsed[key] = [int(n) if "." not in n else float(n) for n in value["NS"]]
            elif "L" in value:
                parsed[key] = [self._dynamodb_to_python(v) for v in value["L"]]
        
        # Parse timestamps
        if "created_at" in parsed:
            parsed["created_at"] = datetime.fromisoformat(parsed["created_at"].replace("Z", "+00:00"))
        if "updated_at" in parsed:
            parsed["updated_at"] = datetime.fromisoformat(parsed["updated_at"].replace("Z", "+00:00"))
        
        # Determine entity type and create appropriate instance
        entity_type = parsed.get("entity_type")
        
        if entity_type == EntityType.COURSE_INFO.value:
            return CourseInfo(**parsed)
        elif entity_type == EntityType.CLO.value:
            return CLOEntity(**parsed)
        elif entity_type == EntityType.SESSION.value:
            return SessionEntity(**parsed)
        elif entity_type == EntityType.ASSESSMENT.value:
            return AssessmentEntity(**parsed)
        elif entity_type == EntityType.MATERIAL.value:
            return MaterialEntity(**parsed)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")
    
    def _group_entities_by_type(self, items: List[Dict[str, Any]]) -> Dict[str, List[SyllabusEntity]]:
        """
        Group DynamoDB items by entity type.
        
        Args:
            items: List of DynamoDB items
            
        Returns:
            dict: Entities grouped by type
        """
        result = {
            "course_info": None,
            "clos": [],
            "sessions": [],
            "assessments": [],
            "materials": []
        }
        
        for item in items:
            entity = self._dynamodb_item_to_entity(item)
            
            if isinstance(entity, CourseInfo):
                result["course_info"] = entity
            elif isinstance(entity, CLOEntity):
                result["clos"].append(entity)
            elif isinstance(entity, SessionEntity):
                result["sessions"].append(entity)
            elif isinstance(entity, AssessmentEntity):
                result["assessments"].append(entity)
            elif isinstance(entity, MaterialEntity):
                result["materials"].append(entity)
        
        # Sort lists for consistent ordering
        result["clos"].sort(key=lambda x: x.clo_id)
        result["sessions"].sort(key=lambda x: x.session_number)
        result["assessments"].sort(key=lambda x: x.weight_percentage, reverse=True)
        result["materials"].sort(key=lambda x: x.material_id)
        
        return result
    
    def _python_to_dynamodb(self, value: Any) -> Dict[str, Any]:
        """Convert Python value to DynamoDB attribute value."""
        if isinstance(value, str):
            return {"S": value}
        elif isinstance(value, (int, float)):
            return {"N": str(value)}
        elif isinstance(value, bool):
            return {"BOOL": value}
        elif isinstance(value, list):
            return {"L": [self._python_to_dynamodb(v) for v in value]}
        elif isinstance(value, dict):
            return {"M": {k: self._python_to_dynamodb(v) for k, v in value.items()}}
        else:
            return {"S": str(value)}
    
    def _dynamodb_to_python(self, value: Dict[str, Any]) -> Any:
        """Convert DynamoDB attribute value to Python value."""
        if "S" in value:
            return value["S"]
        elif "N" in value:
            try:
                return int(value["N"])
            except ValueError:
                return float(value["N"])
        elif "BOOL" in value:
            return value["BOOL"]
        elif "L" in value:
            return [self._dynamodb_to_python(v) for v in value["L"]]
        elif "M" in value:
            return {k: self._dynamodb_to_python(v) for k, v in value["M"].items()}
        else:
            return None
