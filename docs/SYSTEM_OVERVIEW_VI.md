# 📚 ARC Chatbot - Tài Liệu Tổng Quan Hệ Thống

## 1. Giới Thiệu Hệ Thống

### 1.1 Tổng Quan
**ARC (Academic Research Chatbot)** là một hệ thống chatbot thông minh dựa trên RAG (Retrieval-Augmented Generation) được thiết kế để hỗ trợ nghiên cứu tài liệu học thuật. Hệ thống cho phép người dùng tải lên tài liệu và đặt câu hỏi, nhận câu trả lời chính xác kèm trích dẫn nguồn.

| Thông Tin | Chi Tiết |
|-----------|----------|
| **Loại dự án** | AWS Internship Project |
| **Team** | 4 interns (Tech Lead, Backend+IDP, Frontend, DevOps) |
| **Timeline** | 20 ngày |
| **Budget** | ~$65/tháng |
| **Users** | 50 researchers |
| **Documents** | 750 academic papers |

### 1.2 Core Value / Điểm Quan Trọng Của Hệ Thống

1. **RAG-based Q&A với Citations**: Trả lời câu hỏi dựa trên nội dung tài liệu thực tế, kèm trích dẫn nguồn chính xác (trang, tài liệu)
2. **Intelligent Document Processing (IDP)**: Xử lý tự động PDF, Markdown, Jupyter Notebook với OCR cho tài liệu scan
3. **Multilingual Support**: Hỗ trợ tiếng Việt và 100+ ngôn ngữ nhờ Cohere Embed Multilingual v3
4. **Cost-Optimized Architecture**: Thiết kế tối ưu chi phí (~$65/tháng) với self-hosted Qdrant thay vì managed services
5. **Enterprise Security**: Authentication qua Cognito, EC2 trong private subnet, IAM least-privilege

---

## 2. Kiến Trúc Hệ Thống

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND LAYER                                  │
│  Route 53 → CloudFront → Amplify (React + Vite) → Cognito (Auth)           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND LAYER                                   │
│  ALB → EC2 t3.small (Private Subnet)                                        │
│  ├── FastAPI (REST API)                                                     │
│  ├── Qdrant (Vector Database - Self-hosted)                                 │
│  └── SQS Worker (Document Processing)                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AI/ML LAYER                                     │
│  AWS Bedrock:                                                               │
│  ├── Claude 3.5 Sonnet (LLM - Answer Generation)                           │
│  ├── Cohere Embed Multilingual v3 (Embeddings - 1024 dims)                 │
│  └── Textract (OCR + Table Extraction)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ├── S3 (Document Storage)                                                  │
│  ├── DynamoDB (Metadata, Chat History)                                      │
│  └── SQS (Message Queue for IDP Pipeline)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 VPC Architecture

```
VPC (10.0.0.0/16)
├── Public Subnet (10.0.1.0/24)
│   ├── ALB (Application Load Balancer)
│   ├── NAT Gateway
│   └── Internet Gateway
│
├── Private Subnet (10.0.2.0/24)
│   └── EC2 t3.small
│       ├── FastAPI Server (:8000)
│       ├── Qdrant Container (:6333, :6334)
│       └── SQS Worker Process
│
└── VPC Endpoints (Gateway)
    ├── S3 Endpoint (FREE)
    └── DynamoDB Endpoint (FREE)
```

---

## 3. Các Flow Chính

### 3.1 Flow 1: Document Upload & IDP Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Admin   │───▶│  Amplify │───▶│  FastAPI │───▶│    S3    │
│  Upload  │    │  (Auth)  │    │  /upload │    │ (Store)  │
└──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                      │
                                                      ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Qdrant  │◀───│ Cohere   │◀───│ Textract │◀───│   SQS    │
│ (Vector) │    │ Embed    │    │ (Extract)│    │ (Queue)  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │
                                                      ▼
                                               ┌──────────┐
                                               │ DynamoDB │
                                               │ (Status) │
                                               └──────────┘
```

**Chi tiết các bước:**

1. **Admin Upload** → Frontend gửi file qua `/api/admin/upload`
2. **S3 Storage** → File được lưu vào S3 bucket với key: `uploads/{doc_id}/{filename}`
3. **DynamoDB Record** → Tạo record với status `UPLOADED`
4. **SQS Message** → Gửi message để trigger worker
5. **Worker Processing**:
   - Download file từ S3
   - Detect file type (PDF/MD/IPYNB)
   - Extract text (PyPDF2 cho digital PDF, Textract cho scanned)
   - Chunk text (1000 tokens, 200 overlap)
   - Generate embeddings (Cohere Embed v3)
   - Store vectors trong Qdrant
6. **Status Update** → DynamoDB: `UPLOADED` → `IDP_RUNNING` → `EMBEDDING_DONE`

### 3.2 Flow 2: RAG Chat Query

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│   User   │───▶│  Amplify │───▶│  FastAPI │
│  Query   │    │  (Auth)  │    │  /chat   │
└──────────┘    └──────────┘    └────┬─────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              ┌──────────┐    ┌──────────┐    ┌──────────┐
              │  Cohere  │    │  Qdrant  │    │ DynamoDB │
              │  Embed   │───▶│  Search  │    │ (History)│
              │ (Query)  │    │ (Top-K)  │    └──────────┘
              └──────────┘    └────┬─────┘
                                   │
                                   ▼
                            ┌──────────┐    ┌──────────┐
                            │  Claude  │───▶│ Response │
                            │  3.5     │    │ + Cites  │
                            └──────────┘    └──────────┘
```

**Chi tiết các bước:**

1. **User Query** → Frontend gửi câu hỏi qua `/api/chat` hoặc `/api/chat/stream`
2. **Rate Limiting** → Kiểm tra rate limit per user
3. **Query Embedding** → Cohere Embed với `input_type="search_query"`
4. **Vector Search** → Qdrant search top-k contexts (default: 3)
5. **Context Ranking** → Sort by score, assign citation IDs [1], [2], [3]
6. **Prompt Building** → Inject contexts vào RAG prompt template
7. **LLM Generation** → Claude 3.5 Sonnet generate answer với citations
8. **History Storage** → Lưu conversation vào DynamoDB
9. **Response** → Return answer + citations + usage stats

---

## 4. Tách Biệt Frontend / Backend / Data Management

### 4.1 Frontend (React + Vite)

**Location:** `src/`

```
src/
├── components/          # Reusable UI components
│   ├── AnswerWithCitations.jsx   # Render answer với inline citations
│   ├── CitationBadge.jsx         # Badge hiển thị citation [1], [2]
│   ├── DocumentViewerModal.jsx   # Modal xem document gốc
│   ├── Navbar.jsx
│   ├── ProtectedRoute.jsx        # Auth guard
│   └── Sidebar.jsx
├── pages/
│   ├── ChatPage.jsx              # Main chat interface
│   ├── AdminPage.jsx             # Document management
│   ├── LoginPage.jsx
│   └── ProcessingHistoryPage.jsx
├── services/
│   ├── authService.js            # Cognito authentication
│   ├── chatService.js            # Chat API calls
│   └── adminService.js           # Admin API calls
└── App.jsx                       # Router configuration
```

**Tech Stack:**
- React 19 + Vite 7
- TailwindCSS + HeroUI
- Framer Motion (animations)
- React Router v7
- AWS Amplify SDK (Auth)

**Key Features:**
- Streaming responses (SSE)
- Inline citation badges với popover
- Dark mode support
- Conversation history
- Multi-file upload (PDF, MD, IPYNB)

### 4.2 Backend (FastAPI)

**Location:** `backend/`

```
backend/
├── app/
│   ├── api/
│   │   ├── chat.py               # POST /api/chat, /api/chat/stream
│   │   ├── admin.py              # POST /api/admin/upload, GET /documents
│   │   └── auth.py               # Welcome email endpoint
│   ├── services/
│   │   ├── rag_service.py        # RAG orchestration
│   │   ├── claude_service.py     # Bedrock Claude wrapper
│   │   ├── embedding_service.py  # Cohere Embed wrapper
│   │   ├── qdrant_client.py      # Vector store client
│   │   ├── sqs_worker.py         # Document processing worker
│   │   ├── pdf_extractor.py      # PDF text extraction
│   │   ├── text_chunker.py       # Text chunking logic
│   │   ├── chat_history_manager.py
│   │   ├── document_status_manager.py
│   │   ├── rate_limiter.py       # Per-user rate limiting
│   │   ├── budget_manager.py     # Cost tracking & model fallback
│   │   └── auth_service.py       # Cognito JWT validation
│   └── main.py                   # FastAPI app entry
├── run_worker.py                 # SQS worker entry point
└── requirements.txt
```

**API Endpoints:**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/chat` | POST | User | RAG query (sync) |
| `/api/chat/stream` | POST | User | RAG query (streaming) |
| `/api/chat/history` | GET | User | List conversations |
| `/api/chat/history/{id}` | GET | User | Get conversation |
| `/api/admin/upload` | POST | Admin | Upload document |
| `/api/admin/documents` | GET | Admin | List documents |
| `/health` | GET | None | Health check |

### 4.3 Data Management

**DynamoDB Tables:**

1. **Document Metadata Table** (`arc-chatbot-dev-document-metadata`)
```
PK: doc_id (String)
SK: "METADATA"
Attributes:
  - status: UPLOADED | IDP_RUNNING | EMBEDDING_DONE | FAILED
  - filename: String
  - uploaded_by: String
  - uploaded_at: ISO timestamp
  - file_type: .pdf | .md | .ipynb
  - page_count: Number
  - chunk_count: Number
  - error_message: String (optional)
GSI: status-index (for filtering by status)
```

2. **Chat History Table** (same table, different SK pattern)
```
PK: conversation_id
SK: message#{timestamp}
Attributes:
  - role: user | assistant
  - content: String
  - user_id: String
  - citations: List (for assistant messages)
  - usage: Map (token counts)
```

**S3 Bucket Structure:**
```
arc-chatbot-documents-{account_id}/
├── uploads/
│   └── {doc_id}/
│       └── {filename}
```

**Qdrant Collection:**
```
Collection: documents
Vector Size: 1024 (Cohere Embed v3)
Distance: Cosine
Quantization: Binary (32x memory reduction)
Payload Fields:
  - doc_id (indexed)
  - page (indexed)
  - is_table (indexed)
  - file_type (indexed)
  - text
  - chunk_index
  - filename
  - section_title
```

---

## 5. Services Sử Dụng & Chi Phí

### 5.1 AWS Services

| Service | Mục đích | Chi phí/tháng |
|---------|----------|---------------|
| **EC2 t3.small** | Backend + Qdrant + Worker | $10.08 |
| **EBS gp3 30GB** | Storage cho EC2 | $2.40 |
| **NAT Gateway** | Outbound internet (updates) | $21.60 |
| **Bedrock Claude 3.5 Sonnet** | LLM generation (~500 queries) | $25.00 |
| **Bedrock Cohere Embed v3** | Embeddings (~10K) | $1.00 |
| **Textract** | OCR (100 pages free tier) | $0.00 |
| **S3 Standard** | Document storage (5GB) | $0.12 |
| **DynamoDB** | Metadata + Chat history | Free Tier |
| **SQS** | Message queue | Free Tier |
| **CloudFront** | CDN (50GB transfer) | Free Tier |
| **Amplify** | Frontend hosting | Free Tier |
| **Cognito** | Authentication (50 MAU) | Free Tier |
| **CloudWatch** | Logs + Metrics | $1.90 |
| **SNS** | Email alerts | Free Tier |

**Tổng chi phí: ~$62-65/tháng**

### 5.2 Self-Hosted Services

| Service | Mục đích | Lý do self-host |
|---------|----------|-----------------|
| **Qdrant** | Vector database | Tiết kiệm ~$90/tháng so với OpenSearch Serverless |

---

## 6. Bottleneck Analysis

### 6.1 Identified Bottlenecks

#### 🔴 Critical: Single Point of Failure (EC2)
```
Location: backend/run_worker.py, backend/app/main.py
Issue: Tất cả services (FastAPI, Qdrant, Worker) chạy trên 1 EC2 instance
Impact: Nếu EC2 down → toàn bộ hệ thống down
Mitigation hiện tại: CloudWatch alarm + auto-restart
Recommendation: 
  - Tách Qdrant ra ECS/EKS riêng
  - Auto Scaling Group cho EC2
  - Multi-AZ deployment
```

#### 🟠 High: Bedrock API Throttling
```
Location: backend/app/services/claude_service.py:invoke_with_retry()
         backend/app/services/embedding_service.py:_invoke_with_retry()
Issue: Bedrock có rate limits, đặc biệt với Claude Sonnet
Impact: Requests bị reject khi traffic cao
Mitigation hiện tại:
  - Exponential backoff retry (max 5 retries)
  - Budget manager với fallback to Haiku
  - Response cache (1 hour TTL)
Recommendation:
  - Request quota increase từ AWS
  - Implement request queuing
```

#### 🟠 High: Memory Constraint (2GB RAM)
```
Location: EC2 t3.small configuration
Issue: 
  - FastAPI: ~200MB
  - Qdrant: ~400MB (7,500 vectors)
  - Worker: ~100MB
  - Total: ~700MB, còn ~1.3GB buffer
Impact: Khi scale documents lên, Qdrant có thể OOM
Mitigation hiện tại: Binary Quantization (32x memory reduction)
Recommendation:
  - Upgrade to t3.medium (4GB) khi cần
  - Monitor memory usage via CloudWatch
```

#### 🟡 Medium: Synchronous Document Processing
```
Location: backend/app/services/sqs_worker.py:_process_document()
Issue: Worker xử lý tuần tự, 1 document tại 1 thời điểm
Impact: Upload nhiều documents → queue backlog
Mitigation hiện tại: SQS visibility timeout 300s
Recommendation:
  - Parallel processing với multiple workers
  - Batch embedding calls (Cohere supports 96 texts/batch)
```

#### 🟡 Medium: N+1 Query Pattern
```
Location: backend/app/services/rag_service.py:RAGPromptBuilder._get_filenames_for_docs()
Issue: Lookup filename từ DynamoDB cho mỗi citation riêng lẻ
Impact: Latency tăng khi có nhiều citations
Mitigation hiện tại: Batch lookup by doc_ids
Recommendation: Cache filename mapping in memory
```

#### 🟢 Low: BM25 Index Initialization
```
Location: backend/app/services/rag_service.py:_init_bm25_from_qdrant()
Issue: BM25 index được build từ Qdrant data mỗi lần khởi động
Impact: Startup time chậm khi có nhiều documents
Current Status: Hybrid search DISABLED do issue này
Recommendation:
  - Persist BM25 index to disk
  - Lazy initialization
```

### 6.2 Performance Metrics (Estimated)

| Metric | Current | Target |
|--------|---------|--------|
| Chat response latency (p50) | ~3-5s | <3s |
| Chat response latency (p99) | ~8-10s | <5s |
| Document processing time | ~30-60s/doc | <30s |
| Concurrent users | ~10 | 50 |
| Vector search latency | ~50ms | <100ms |

---

## 7. Security Architecture

### 7.1 Authentication & Authorization

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Cognito   │────▶│   JWT       │────▶│   FastAPI   │
│  User Pool  │     │   Token     │     │   Auth      │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              ┌──────────┐            ┌──────────┐            ┌──────────┐
              │  Public  │            │   User   │            │  Admin   │
              │ Endpoints│            │ Endpoints│            │ Endpoints│
              │ /health  │            │ /api/chat│            │/api/admin│
              └──────────┘            └──────────┘            └──────────┘
```

**Cognito Groups:**
- `admin`: Full access (upload, manage documents)
- `researcher`: Chat access only

### 7.2 Network Security

- EC2 trong Private Subnet (không có public IP)
- ALB trong Public Subnet (HTTPS only)
- Security Groups:
  - ALB: Inbound 443 from anywhere
  - EC2: Inbound 8000 from ALB only
- VPC Endpoints cho S3, DynamoDB (traffic không ra internet)

### 7.3 Data Security

- S3: Server-side encryption (SSE-S3)
- S3: Block public access enabled
- DynamoDB: Encryption at rest
- Cognito: Password policy enforced

---

## 8. Monitoring & Observability

### 8.1 CloudWatch Alarms

| Alarm | Threshold | Action |
|-------|-----------|--------|
| EC2 CPU High | >80% for 5 min | SNS notification |
| EC2 Status Check | Failed | Auto-restart |
| ALB 5xx Errors | >10/min | SNS notification |
| DynamoDB Throttle | >0 | SNS notification |

### 8.2 Logging

```
CloudWatch Log Groups:
├── /aws/ec2/arc-chatbot/fastapi
├── /aws/ec2/arc-chatbot/worker
├── /aws/ec2/arc-chatbot/qdrant
└── /aws/alb/arc-chatbot
```

---

## 9. CI/CD Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  GitLab  │───▶│CodePipeline│──▶│CodeBuild │───▶│CodeDeploy│
│  Push    │    │ (Trigger) │   │ (Build)  │    │ (Deploy) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                      │
                    ┌─────────────────────────────────┼─────────────────┐
                    ▼                                 ▼                 ▼
              ┌──────────┐                    ┌──────────┐      ┌──────────┐
              │ Frontend │                    │ Backend  │      │  Amplify │
              │  S3/CF   │                    │   EC2    │      │  (Auto)  │
              └──────────┘                    └──────────┘      └──────────┘
```

---

## 10. Kết Luận

### 10.1 Điểm Mạnh
- ✅ Cost-optimized architecture (~$65/tháng)
- ✅ Multilingual support (Vietnamese + 100 languages)
- ✅ Accurate citations với page numbers
- ✅ Streaming responses cho UX tốt
- ✅ Enterprise security (Cognito, private subnet)

### 10.2 Điểm Cần Cải Thiện
- ⚠️ Single point of failure (EC2)
- ⚠️ Limited scalability (1 worker)
- ⚠️ No disaster recovery plan
- ⚠️ Manual scaling required

### 10.3 Roadmap Đề Xuất
1. **Short-term**: Enable hybrid search (BM25 + Vector)
2. **Medium-term**: Multi-worker processing, Auto Scaling
3. **Long-term**: Multi-AZ deployment, Managed Qdrant

---

*Tài liệu được tạo: December 2024*
*Version: 1.0*
