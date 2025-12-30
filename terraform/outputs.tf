# Outputs for ARC Chatbot Infrastructure

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = module.vpc.public_subnet_id
}

output "private_subnet_id" {
  description = "ID of the private subnet"
  value       = module.vpc.private_subnet_id
}

# EC2 Outputs
output "ec2_instance_id" {
  description = "ID of the EC2 instance"
  value       = module.ec2.instance_id
}

output "ec2_private_ip" {
  description = "Private IP of the EC2 instance"
  value       = module.ec2.private_ip
}

# ALB output - commented out until AWS enables ELB service
# output "alb_dns_name" {
#   description = "DNS name of the Application Load Balancer"
#   value       = module.ec2.alb_dns_name
# }

# S3 Outputs
output "documents_bucket_name" {
  description = "Name of the S3 bucket for documents"
  value       = module.s3.documents_bucket_name
}

output "documents_bucket_arn" {
  description = "ARN of the S3 bucket for documents"
  value       = module.s3.documents_bucket_arn
}

# DynamoDB Outputs
output "document_metadata_table_name" {
  description = "Name of the DocumentMetadata DynamoDB table"
  value       = module.dynamodb.document_metadata_table_name
}

output "chat_history_table_name" {
  description = "Name of the ChatHistory DynamoDB table"
  value       = module.dynamodb.chat_history_table_name
}

output "syllabus_entities_table_name" {
  description = "Name of the SyllabusEntities DynamoDB table"
  value       = module.dynamodb.syllabus_entities_table_name
}

# Cognito Outputs
output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "ID of the Cognito App Client"
  value       = module.cognito.app_client_id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = module.cognito.user_pool_arn
}

# Amplify Outputs
# Amplify outputs - commented out until module is enabled
# output "amplify_app_id" {
#   description = "ID of the Amplify app"
#   value       = module.amplify.app_id
# }

# output "amplify_default_domain" {
#   description = "Default domain of the Amplify app"
#   value       = module.amplify.default_domain
# }

# IAM Outputs
output "ec2_role_arn" {
  description = "ARN of the EC2 IAM role"
  value       = module.iam.ec2_role_arn
}

# SQS Outputs
output "sqs_queue_url" {
  description = "URL of the document processing SQS queue"
  value       = module.sqs.queue_url
}

output "sqs_queue_arn" {
  description = "ARN of the document processing SQS queue"
  value       = module.sqs.queue_arn
}

output "sqs_dlq_url" {
  description = "URL of the dead letter queue"
  value       = module.sqs.dlq_url
}

# CI/CD Outputs
output "pipeline_name" {
  description = "Name of the CodePipeline"
  value       = module.cicd.pipeline_name
}

output "pipeline_arn" {
  description = "ARN of the CodePipeline"
  value       = module.cicd.pipeline_arn
}

output "artifacts_bucket" {
  description = "S3 bucket for pipeline artifacts"
  value       = module.cicd.artifacts_bucket
}

output "gitlab_connection_arn" {
  description = "CodeStar GitLab connection ARN (needs manual approval)"
  value       = module.cicd.gitlab_connection_arn
}

output "gitlab_connection_status" {
  description = "GitLab connection status"
  value       = module.cicd.gitlab_connection_status
}

# Frontend Hosting Outputs
output "frontend_bucket_name" {
  description = "Name of the frontend S3 bucket"
  value       = module.s3.frontend_bucket_name
}

output "frontend_website_endpoint" {
  description = "Frontend website endpoint"
  value       = module.s3.frontend_bucket_website_endpoint
}
