# GitHub Actions CI/CD

## Workflows

### Frontend (`frontend.yml`)
- **Trigger**: Push/PR to `main`, `develop` on `src/`, `public/` changes
- **Jobs**: Lint → Build → Deploy to S3 + CloudFront invalidation
- **Deploy**: Only on push to `main`

### Backend (`backend.yml`)
- **Trigger**: Push/PR to `main`, `develop` on `backend/` changes
- **Jobs**: Test → Build → Deploy via CodeDeploy
- **Deploy**: Only on push to `main`

### Amplify (`amplify.yml`)
- **Trigger**: Push/PR to `main` on `amplify/` changes
- **Jobs**: TypeScript validation

## Required Secrets

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `S3_BUCKET` | Frontend S3 bucket name |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID (optional) |
| `DEPLOY_BUCKET` | S3 bucket for deployment artifacts |
| `CODEDEPLOY_APP` | CodeDeploy application name |
| `CODEDEPLOY_GROUP` | CodeDeploy deployment group name |

## Environment

Create a `production` environment in **Settings → Environments** for deployment protection rules.
