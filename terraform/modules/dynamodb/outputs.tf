# DynamoDB Module Outputs

output "document_metadata_table_name" {
  description = "Name of the DocumentMetadata table"
  value       = aws_dynamodb_table.document_metadata.name
}

output "document_metadata_table_arn" {
  description = "ARN of the DocumentMetadata table"
  value       = aws_dynamodb_table.document_metadata.arn
}

output "chat_history_table_name" {
  description = "Name of the ChatHistory table"
  value       = aws_dynamodb_table.chat_history.name
}

output "chat_history_table_arn" {
  description = "ARN of the ChatHistory table"
  value       = aws_dynamodb_table.chat_history.arn
}

output "syllabus_entities_table_name" {
  description = "Name of the SyllabusEntities table"
  value       = aws_dynamodb_table.syllabus_entities.name
}

output "syllabus_entities_table_arn" {
  description = "ARN of the SyllabusEntities table"
  value       = aws_dynamodb_table.syllabus_entities.arn
}
