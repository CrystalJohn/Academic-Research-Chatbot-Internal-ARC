"""
DynamoDB Document Status Manager

Manages document processing status tracking in DynamoDB.
Supports status transitions: UPLOADED → IDP_RUNNING → EMBEDDING_DONE/FAILED

Requirements: 9.1, 9.2, 9.3, 9.4
"""

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import boto3
from botocore.exceptions import ClientError


class DocumentStatus(str, Enum):
    """Document processing status values."""
    UPLOADED = "UPLOADED"
    IDP_RUNNING = "IDP_RUNNING"
    EMBEDDING_DONE = "EMBEDDING_DONE"
    FAILED = "FAILED"


# Valid status transitions
# FAILED can transition to IDP_RUNNING for retry support
VALID_TRANSITIONS = {
    DocumentStatus.UPLOADED: [DocumentStatus.IDP_RUNNING, DocumentStatus.FAILED],
    DocumentStatus.IDP_RUNNING: [DocumentStatus.EMBEDDING_DONE, DocumentStatus.FAILED],
    DocumentStatus.EMBEDDING_DONE: [],  # Terminal state - no changes allowed
    DocumentStatus.FAILED: [DocumentStatus.IDP_RUNNING, DocumentStatus.UPLOADED],  # Allow retry
}


class DocumentStatusManager:
    """
    Manages document status tracking in DynamoDB.
    
    Table schema:
    - doc_id (PK): Document unique identifier
    - sk (SK): Sort key, always "METADATA" for document records
    - status: Current processing status
    - filename: Original filename
    - uploaded_by: User who uploaded
    - uploaded_at: Upload timestamp (ISO format)
    - page_count: Number of pages (set after extraction)
    - chunk_count: Number of chunks (set after embedding)
    - error_message: Error details (set on failure)
    """
    
    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_client=None,
        region_name: Optional[str] = None
    ):
        """
        Initialize the status manager.
        
        Args:
            table_name: DynamoDB table name. Defaults to env var.
            dynamodb_client: Optional boto3 DynamoDB client for testing.
            region_name: AWS region. Defaults to env var or us-east-1.
        """
        self.table_name = table_name or os.getenv(
            "DYNAMODB_TABLE_NAME",
            "arc-chatbot-dev-document-metadata"
        )
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-southeast-1")
        
        if dynamodb_client:
            self._client = dynamodb_client
        else:
            self._client = boto3.client(
                "dynamodb",
                region_name=self.region_name
            )

    def create_document(
        self,
        doc_id: str,
        filename: str,
        uploaded_by: str,
        file_type: str = ".pdf",
        processor: str = "textract"
    ) -> dict:
        """
        Create a new document record with UPLOADED status.
        
        Args:
            doc_id: Unique document identifier (UUID)
            filename: Original filename
            uploaded_by: User ID who uploaded the document
            file_type: File extension (e.g., '.pdf', '.md', '.ipynb')
            processor: Processing method ('textract', 'markdown', 'jupyter')
            
        Returns:
            dict: Created document record
            
        Raises:
            ClientError: If DynamoDB operation fails
            
        Requirements: 9.1
        """
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        item = {
            "doc_id": {"S": doc_id},
            "sk": {"S": "METADATA"},
            "status": {"S": DocumentStatus.UPLOADED.value},
            "filename": {"S": filename},
            "uploaded_by": {"S": uploaded_by},
            "uploaded_at": {"S": timestamp},
            "file_type": {"S": file_type},
            "processor": {"S": processor},
        }
        
        self._client.put_item(
            TableName=self.table_name,
            Item=item,
            ConditionExpression="attribute_not_exists(doc_id)"
        )
        
        return {
            "doc_id": doc_id,
            "status": DocumentStatus.UPLOADED.value,
            "filename": filename,
            "uploaded_by": uploaded_by,
            "uploaded_at": timestamp,
            "file_type": file_type,
            "processor": processor,
        }

    def update_status(
        self,
        doc_id: str,
        new_status: DocumentStatus,
        page_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
        validate_transition: bool = True
    ) -> dict:
        """
        Update document status with optional metadata.
        
        Args:
            doc_id: Document identifier
            new_status: New status value
            page_count: Number of pages (for EMBEDDING_DONE)
            chunk_count: Number of chunks (for EMBEDDING_DONE)
            error_message: Error details (for FAILED)
            validate_transition: If True, validate status transition is allowed
            
        Returns:
            dict: Updated document record
            
        Raises:
            ValueError: If status transition is invalid
            ClientError: If DynamoDB operation fails
            
        Requirements: 9.2, 9.3, 9.4
        """
        # Validate status transition if enabled
        if validate_transition:
            current_doc = self.get_document(doc_id)
            if current_doc:
                current_status_str = current_doc.get("status", "")
                try:
                    current_status = DocumentStatus(current_status_str)
                    allowed_transitions = VALID_TRANSITIONS.get(current_status, [])
                    
                    if new_status not in allowed_transitions:
                        # Allow same status (idempotent)
                        if current_status == new_status:
                            return current_doc
                        raise ValueError(
                            f"Invalid status transition: {current_status.value} → {new_status.value}. "
                            f"Allowed: {[s.value for s in allowed_transitions]}"
                        )
                except ValueError as e:
                    if "Invalid status transition" in str(e):
                        raise
                    # Unknown current status, allow update
                    pass
        
        # Build update expression dynamically
        update_parts = ["#status = :new_status", "#updated_at = :updated_at"]
        expression_names = {
            "#status": "status",
            "#updated_at": "updated_at"
        }
        expression_values = {
            ":new_status": {"S": new_status.value},
            ":updated_at": {"S": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        }
        
        if page_count is not None:
            update_parts.append("#page_count = :page_count")
            expression_names["#page_count"] = "page_count"
            expression_values[":page_count"] = {"N": str(page_count)}
        
        if chunk_count is not None:
            update_parts.append("#chunk_count = :chunk_count")
            expression_names["#chunk_count"] = "chunk_count"
            expression_values[":chunk_count"] = {"N": str(chunk_count)}
        
        if error_message is not None:
            update_parts.append("#error_message = :error_message")
            expression_names["#error_message"] = "error_message"
            expression_values[":error_message"] = {"S": error_message}
        
        update_expression = "SET " + ", ".join(update_parts)
        
        response = self._client.update_item(
            TableName=self.table_name,
            Key={
                "doc_id": {"S": doc_id},
                "sk": {"S": "METADATA"}
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW"
        )
        
        return self._parse_item(response.get("Attributes", {}))

    def get_document(self, doc_id: str) -> Optional[dict]:
        """
        Get document by ID.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            dict: Document record or None if not found
        """
        response = self._client.get_item(
            TableName=self.table_name,
            Key={
                "doc_id": {"S": doc_id},
                "sk": {"S": "METADATA"}
            }
        )
        
        item = response.get("Item")
        if not item:
            return None
        
        return self._parse_item(item)

    def list_documents(
        self,
        status: Optional[DocumentStatus] = None,
        page_size: int = 20,
        page: int = 1
    ) -> dict:
        """
        List documents with in-memory pagination and proper sorting.
        
        Fetches all documents, sorts by uploaded_at descending, then paginates.
        Suitable for datasets < 1000 documents.
        
        Args:
            status: Filter by status (optional)
            page_size: Items per page (default 20)
            page: Page number (1-indexed, default 1)
            
        Returns:
            dict: {items: [...], total: int, has_more: bool}
            
        Requirements: 11.1, 11.2
        """
        # Fetch all documents (with pagination for large datasets)
        all_items = []
        last_key = None
        
        while True:
            if status:
                # Use GSI for status filtering
                params = {
                    "TableName": self.table_name,
                    "IndexName": "status-index",
                    "KeyConditionExpression": "#status = :status",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {":status": {"S": status.value}},
                }
            else:
                # Scan all METADATA records
                params = {
                    "TableName": self.table_name,
                    "FilterExpression": "sk = :sk",
                    "ExpressionAttributeValues": {":sk": {"S": "METADATA"}},
                }
            
            if last_key:
                params["ExclusiveStartKey"] = last_key
            
            if status:
                response = self._client.query(**params)
            else:
                response = self._client.scan(**params)
            
            items = [self._parse_item(item) for item in response.get("Items", [])]
            all_items.extend(items)
            
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
        
        # Sort by uploaded_at descending (newest first)
        all_items.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
        
        # Calculate stats from ALL items (before filtering by status)
        stats = {
            "total": len(all_items),
            "completed": sum(1 for d in all_items if d.get("status") == "EMBEDDING_DONE"),
            "processing": sum(1 for d in all_items if d.get("status") == "IDP_RUNNING"),
            "failed": sum(1 for d in all_items if d.get("status") == "FAILED"),
            "uploaded": sum(1 for d in all_items if d.get("status") == "UPLOADED"),
        }
        
        # Calculate pagination
        total = len(all_items)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = all_items[start_idx:end_idx]
        
        return {
            "items": page_items,
            "total": total,
            "has_more": end_idx < total,
            "stats": stats,
        }

    def _parse_item(self, item: dict) -> dict:
        """Parse DynamoDB item to plain dict."""
        result = {}
        for key, value in item.items():
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                result[key] = int(value["N"])
            elif "BOOL" in value:
                result[key] = value["BOOL"]
        return result
