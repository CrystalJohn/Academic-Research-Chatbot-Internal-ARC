# Amplify Module - Frontend Hosting

# Note: This is a placeholder. Amplify app typically requires a Git repository connection
# which should be configured manually or via AWS Console initially.

# Amplify App
resource "aws_amplify_app" "main" {
  name       = "${var.project_name}-${var.environment}-frontend"
  repository = var.repository_url  # Git repository URL

  # Build settings for Vite
  build_spec = <<-EOT
    version: 1
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci
        build:
          commands:
            - npm run build
      artifacts:
        baseDirectory: dist
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
  EOT

  # Environment variables (Vite uses VITE_ prefix)
  environment_variables = {
    VITE_API_URL           = var.api_url
    VITE_COGNITO_POOL_ID   = var.cognito_pool_id
    VITE_COGNITO_CLIENT_ID = var.cognito_client_id
    VITE_AWS_REGION        = var.aws_region
  }

  # Custom rules for SPA routing
  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|ttf)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-amplify-app"
  }
}

# Amplify Branch (main branch)
resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.main.id
  branch_name = "main"

  enable_auto_build = true

  framework = "React"
  stage     = "PRODUCTION"
}
