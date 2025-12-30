# DynamoDB Module - Document Metadata and Chat History

# DocumentMetadata Table
resource "aws_dynamodb_table" "document_metadata" {
  name         = "${var.project_name}-${var.environment}-document-metadata"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "doc_id"
  range_key    = "sk"

  attribute {
    name = "doc_id"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "uploaded_at"
    type = "S"
  }

  # GSI for querying by status
  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "uploaded_at"
    projection_type = "ALL"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-document-metadata"
  }
}

# ChatHistory Table
resource "aws_dynamodb_table" "chat_history" {
  name         = "${var.project_name}-${var.environment}-chat-history"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "sk"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "conversation_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  # GSI for querying by conversation
  global_secondary_index {
    name            = "conversation-index"
    hash_key        = "conversation_id"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-chat-history"
  }
}

# SyllabusEntities Table
resource "aws_dynamodb_table" "syllabus_entities" {
  name         = "${var.project_name}-${var.environment}-syllabus-entities"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "GSI1PK"
    type = "S"
  }

  attribute {
    name = "GSI1SK"
    type = "S"
  }

  attribute {
    name = "GSI2PK"
    type = "S"
  }

  attribute {
    name = "GSI2SK"
    type = "S"
  }

  # GSI1: entity-type-index
  # Use: Query all entities of specific type for a syllabus version
  # Note: GSI1PK uses date prefix to allow querying by date even with timestamp in SK
  global_secondary_index {
    name            = "entity-type-index"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"
  }

  # GSI2: clo-session-index
  # Use: Find sessions covering specific CLO
  global_secondary_index {
    name            = "clo-session-index"
    hash_key        = "GSI2PK"
    range_key       = "GSI2SK"
    projection_type = "ALL"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-syllabus-entities"
    Description = "Stores structured syllabus entities with versioning support"
  }
}
