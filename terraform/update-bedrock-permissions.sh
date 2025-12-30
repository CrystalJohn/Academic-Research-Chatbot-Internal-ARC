#!/bin/bash
# Update IAM policies to add Bedrock Converse API permissions

echo "🔐 Updating IAM policies for Bedrock Converse API"
echo "=" * 60

# Check if terraform is initialized
if [ ! -d ".terraform" ]; then
    echo "❌ Terraform not initialized. Run 'terraform init' first."
    exit 1
fi

# Show what will change
echo ""
echo "📋 Planning changes..."
terraform plan -target=module.iam.aws_iam_role_policy.ec2_bedrock_policy \
               -target=module.iam.aws_iam_user_policy.backend_idp_policy \
               -target=module.iam.aws_iam_user_policy.tech_lead_policy

echo ""
read -p "Apply these changes? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted"
    exit 0
fi

# Apply changes
echo ""
echo "🚀 Applying changes..."
terraform apply -target=module.iam.aws_iam_role_policy.ec2_bedrock_policy \
                -target=module.iam.aws_iam_user_policy.backend_idp_policy \
                -target=module.iam.aws_iam_user_policy.tech_lead_policy \
                -auto-approve

if [ $? -eq 0 ]; then
    echo ""
    echo "=" * 60
    echo "✅ IAM policies updated successfully!"
    echo "=" * 60
    echo ""
    echo "New permissions added:"
    echo "  - bedrock:Converse"
    echo "  - bedrock:ConverseStream"
    echo ""
    echo "Applied to:"
    echo "  - EC2 Role: arc-chatbot-dev-ec2-role"
    echo "  - IAM User: arc-chatbot-backend-idp"
    echo "  - IAM User: arc-chatbot-tech-lead"
    echo ""
    echo "Next steps:"
    echo "1. Update boto3: cd backend && pip install --upgrade boto3>=1.35.0"
    echo "2. Verify: python backend/test_converse_api.py"
    echo "3. Restart backend: uvicorn app.main:app --reload"
else
    echo ""
    echo "❌ Failed to apply changes"
    exit 1
fi
