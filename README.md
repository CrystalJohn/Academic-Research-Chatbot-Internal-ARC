# Academic Research Chatbot (ARC)

RAG-based chatbot for academic research papers using AWS infrastructure.

## 📋 Project Overview

- **Type**: AWS Internship Project
- **Team**: 4 interns (Tech Lead, Backend+IDP, Frontend, DevOps)
- **Timeline**: 20 days
- **Budget**: ~$65/month
- **Users**: 50 researchers
- **Documents**: 750 academic papers

## 🏗️ Architecture

```
Frontend:     Route 53 → CloudFront → Amplify (React + Vite) → Cognito
Backend:      ALB → EC2 t3.small (FastAPI + Qdrant + Worker)
AI/ML:        Bedrock Claude 3.5 Sonnet + Cohere Embed Multilingual v3
IDP:          SQS → EC2 Worker → Textract → Embeddings → Qdrant
Data:         S3 (documents) + DynamoDB (metadata, chat history)
```

## 📁 Project Structure

```
ARC-project/
├── terraform/              # Infrastructure as Code
│   └── modules/
│       ├── vpc/           # VPC, subnets, NAT Gateway
│       ├── iam/           # IAM roles and policies
│       ├── ec2/           # EC2 instance for backend
│       ├── s3/            # S3 buckets for documents
│       ├── dynamodb/      # DynamoDB tables
│       ├── cognito/       # User authentication
│       ├── sqs/           # Message queue for IDP
│       ├── amplify/       # Frontend hosting
│       └── cicd/          # CI/CD pipeline
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── api/          # API endpoints (chat, admin, auth)
│   │   ├── services/     # Business logic services
│   │   └── tests/        # Unit tests
│   ├── run_worker.py     # SQS worker for IDP pipeline
│   └── requirements.txt
├── src/                   # React frontend (Vite)
│   ├── components/       # Reusable UI components
│   ├── pages/            # Page components
│   ├── services/         # API service clients
│   └── App.jsx
├── docs/                  # Documentation
├── samples/               # AWS service sample code
└── scripts/               # Utility scripts
```

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Check Command |
|------|---------|---------------|
| AWS CLI | >= 2.0 | `aws --version` |
| Terraform | >= 1.0 | `terraform --version` |
| Docker | >= 20.0 | `docker --version` |
| Node.js | >= 18 | `node --version` |
| Python | >= 3.11 | `python --version` |
| npm | >= 9 | `npm --version` |

### Step 1: Clone & Configure Environment

```bash
# Clone repository
git clone <repository-url>
cd ARC-project

# Copy environment template
cp .env.example .env

# Edit .env with your AWS values
# Required variables:
#   VITE_AWS_REGION=ap-southeast-1
#   VITE_COGNITO_POOL_ID=<your-cognito-pool-id>
#   VITE_COGNITO_CLIENT_ID=<your-cognito-client-id>
#   VITE_API_URL=<your-alb-endpoint>
```

### Step 2: Deploy AWS Infrastructure (Optional - if not already deployed)

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

See [terraform/README.md](terraform/README.md) for detailed instructions.

### Step 3: Start Qdrant (Vector Database)

```bash
# Pull and run Qdrant container
docker run -d --name arc-qdrant \
  -p 6333:6333 -p 6334:6334 \
  qdrant/qdrant

# Verify Qdrant is running
curl http://localhost:6333/collections
```

### Step 4: Setup Backend

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Verify backend is running
curl http://localhost:8000/health
# Expected: {"status": "healthy", "service": "arc-chatbot-api"}
```

### Step 5: Start SQS Worker (separate terminal)

```bash
cd backend
python run_worker.py
```

### Step 6: Setup Frontend

```bash
# From project root
npm install

# Start development server
npm run dev

# Frontend will be available at http://localhost:5173
```

### Quick Start (Windows PowerShell)

```powershell
# Start all services with one command
.\start-full-stack.ps1

# This will:
# 1. Start Qdrant (Docker)
# 2. Start Backend API (port 8000)
# 3. Start SQS Worker
# 4. Start Frontend (port 5173)
# 5. Open browser automatically
```

### Verify Setup

| Service | URL | Expected Response |
|---------|-----|-------------------|
| Qdrant | http://localhost:6333/collections | `{"result":{"collections":[...]}}` |
| Backend | http://localhost:8000/health | `{"status":"healthy"}` |
| Frontend | http://localhost:5173 | Login page |

## 📚 Documentation

- [Infrastructure Setup](terraform/README.md)
- [Project Knowledge Base](knowledge-project.md)
- [Frontend-Backend Contract](docs/FRONTEND_BACKEND_CONTRACT.md)
- [Full Stack Testing Guide](docs/full-stack-testing-guide.md)
- [Use Case Scenarios](docs/use-case-scenarios.md)
- [Sample Queries](docs/sample-queries.md)

## 💰 Cost Breakdown (~$65/month)

### Compute & Storage
| Service | Specs | Cost/Month |
|---------|-------|------------|
| EC2 t3.small | 2 vCPU, 2GB RAM, 480h | $10.08 |
| EBS gp3 | 30GB | $2.40 |
| NAT Gateway | 480h | $21.60 |

### AI/ML (Bedrock)
| Service | Usage | Cost/Month |
|---------|-------|------------|
| Claude 3.5 Sonnet | ~500 queries | $25.00 |
| Cohere Embed Multilingual v3 | ~10K embeddings | $1.00 |
| Textract | 100 pages (free tier) | $0.00 |

### Storage & Database
| Service | Usage | Cost/Month |
|---------|-------|------------|
| S3 Standard | 5GB documents | $0.12 |
| DynamoDB | On-demand, <25GB | Free Tier |
| SQS | <1M requests | Free Tier |

### Frontend & CDN
| Service | Usage | Cost/Month |
|---------|-------|------------|
| CloudFront | 50GB transfer | $0.00 (free tier) |
| Amplify Hosting | Build + Hosting | $0.00 (free tier) |
| Cognito | 50 MAU | Free Tier |

### Monitoring
| Service | Usage | Cost/Month |
|---------|-------|------------|
| CloudWatch | Logs + Metrics | $1.90 |
| SNS | Email alerts | Free Tier |

### Total
| Category | Cost |
|----------|------|
| Compute | $34.08 |
| AI/ML | $26.00 |
| Storage | $0.12 |
| Frontend | $0.00 |
| Monitoring | $1.90 |
| **TOTAL** | **~$62-65** |

> **Note**: Costs assume 50 researchers, ~500 queries/month, 750 documents. Free tier benefits apply for first 12 months.

## 🔧 Tech Stack

**Infrastructure:**
- AWS (VPC, EC2, S3, DynamoDB, Cognito, Amplify, SQS, CloudFront)
- Terraform (IaC)

**Backend:**
- FastAPI (Python 3.11+)
- Qdrant (Vector DB - self-hosted on EC2)
- AWS Bedrock Claude 3.5 Sonnet (LLM)
- AWS Bedrock Cohere Embed Multilingual v3 (Embeddings - 1024 dims)
- AWS Textract (OCR + Table Extraction)
- SQS (Message Queue)

**Frontend:**
- React 19 + Vite
- TailwindCSS + HeroUI
- AWS Amplify (Hosting)
- AWS Cognito (Auth)

## 🔄 Main Flows

### Flow 1: Document Upload & IDP
```
Admin Upload → S3 → SQS → Worker → Textract → Cohere Embed → Qdrant
```

### Flow 2: RAG Chat
```
User Query → Cohere Embed → Qdrant Search → Claude 3.5 → Response + Citations
```

## 👥 Team Roles

| Role | Responsibilities |
|------|------------------|
| Tech Lead | Architecture, EC2, FastAPI, Textract |
| Backend+IDP | Bedrock, Qdrant, IDP pipeline |
| Frontend | React, Amplify, Cognito |
| DevOps | Terraform, CI/CD, CloudWatch |

## 📅 Milestones

- **M0** (Days 1-5): Infrastructure Setup ✅
- **M1** (Days 6-10): IDP & Ingestion Pipeline ✅
- **M2** (Days 11-15): RAG Chat API ✅
- **M3** (Days 16-20): Frontend & Monitoring ✅

## 🔐 Security

- EC2 in private subnet
- S3 buckets with encryption and blocked public access
- IAM least-privilege policies
- Cognito for authentication
- VPC endpoints for AWS services
- JWT token validation

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.11+

# Check AWS credentials
aws sts get-caller-identity

# Check environment variables
cat .env
```

### Qdrant connection failed
```bash
# Check if container is running
docker ps | grep qdrant

# Restart container
docker restart arc-qdrant

# Check logs
docker logs arc-qdrant
```

### Frontend build errors
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

## 📝 License

This project is for educational purposes as part of an AWS internship program.

## 🤝 Contributing

This is an internship project. For questions or issues, contact the team lead.
