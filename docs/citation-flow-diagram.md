# Citation Links Flow Diagram

## Task #37: Display Citations with Document Links

---

## 📊 Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ChatPage.jsx                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Messages Array                                        │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  User Message                                    │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Assistant Message                               │ │ │
│  │  │  ├─ Answer Text                                  │ │ │
│  │  │  └─ Citations Array                              │ │ │
│  │  │     ├─ CitationCard [1] ──┐                      │ │ │
│  │  │     ├─ CitationCard [2]   │                      │ │ │
│  │  │     └─ CitationCard [3]   │                      │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│                                  │                           │
│                                  │ onClick "View Document"   │
│                                  ▼                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  selectedCitation State                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                  │                           │
│                                  ▼                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  DocumentViewerModal                                   │ │
│  │  ├─ Citation Context (highlighted)                     │ │
│  │  ├─ Document Metadata                                  │ │
│  │  └─ Action Buttons                                     │ │
│  │     ├─ Download PDF ──────────────┐                    │ │
│  │     └─ Open in S3                 │                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                         │
                                         │ API Call
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  GET /api/admin/documents/{doc_id}                     │ │
│  │  └─ Returns: metadata, status, filename, etc.          │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  GET /api/admin/documents/{doc_id}/download            │ │
│  │  └─ Returns: presigned S3 URL (1-hour expiry)          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      AWS Services                            │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │   DynamoDB     │  │       S3       │  │   Presigned   │ │
│  │   Metadata     │  │   PDF Files    │  │      URL      │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 User Interaction Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: User asks question                                  │
│  "What are the main data structures?"                        │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: RAG API returns answer with citations               │
│  Answer: "Based on [1] and [2], the main structures are..." │
│  Citations: [                                                │
│    {id: 1, doc_id: "abc", page: 5, snippet: "...", ...},    │
│    {id: 2, doc_id: "def", page: 12, snippet: "...", ...}    │
│  ]                                                           │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Citations displayed as cards                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [1] Arrays are fundamental data structures...        │   │
│  │ 📄 abc-123... | Page: 5 | 🟢 85% match              │   │
│  │ [📖 View Document] [📋 Copy Text]                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ User clicks "View Document"
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Modal opens with loading state                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Document Details                              [×]   │   │
│  │  ─────────────────────────────────────────────────   │   │
│  │  🔄 Loading document info...                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ API: GET /api/admin/documents/{doc_id}
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Document metadata displayed                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Document Details                              [×]   │   │
│  │  ─────────────────────────────────────────────────   │   │
│  │  📚 Citation Context                                 │   │
│  │  "Arrays are fundamental data structures..."        │   │
│  │  📄 Page 5 | 🎯 85% relevance                        │   │
│  │                                                      │   │
│  │  Document ID: abc-123-def-456                        │   │
│  │  Filename: data-structures.pdf                       │   │
│  │  Status: 🟢 EMBEDDING_DONE                           │   │
│  │  Pages: 326 | Chunks: 310                            │   │
│  │  Uploaded: 2025-12-03                                │   │
│  │                                                      │   │
│  │  [📥 Download PDF] [🔗 Open in S3]                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ User clicks "Download PDF"
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: Generate presigned URL                              │
│  API: GET /api/admin/documents/{doc_id}/download            │
│  Response: {                                                 │
│    download_url: "https://s3.amazonaws.com/...",            │
│    expires_in: 3600                                          │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7: Browser downloads PDF from S3                       │
│  New tab opens → S3 presigned URL → PDF download starts     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Citation Card States

```
┌─────────────────────────────────────────────────────────────┐
│  Normal State (Collapsed)                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [1] Arrays are fundamental data structures that...  │   │
│  │     store elements in contiguous memory...          │   │
│  │     ▶ Show more                                      │   │
│  │ 📄 abc-123... | Page: 5 | 🟢 85% match              │   │
│  │ [📖 View Document] [📋 Copy Text]                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Expanded State                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [1] Arrays are fundamental data structures that      │   │
│  │     store elements in contiguous memory locations.   │   │
│  │     They provide O(1) access time for indexed        │   │
│  │     operations and are the basis for many other      │   │
│  │     data structures like stacks and queues.          │   │
│  │     ▼ Show less                                       │   │
│  │ 📄 abc-123... | Page: 5 | 🟢 85% match              │   │
│  │ [📖 View Document] [📋 Copy Text]                    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Hover State                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [1] Arrays are fundamental data structures...        │   │
│  │ 📄 abc-123... | Page: 5 | 🟢 85% match              │   │
│  │ [📖 View Document] [📋 Copy Text]                    │   │
│  └──────────────────────────────────────────────────────┘   │
│  Border changes to blue ──────────────────────────────────▲ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 Security Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend Request                                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  GET /api/admin/documents/{doc_id}/download            │ │
│  │  Headers: {                                            │ │
│  │    Authorization: "Bearer eyJhbGc..."                  │ │
│  │  }                                                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend Validation                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  1. Verify JWT token (Cognito)                         │ │
│  │  2. Check document exists (DynamoDB)                   │ │
│  │  3. Verify user has access (optional)                  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  S3 Presigned URL Generation                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  s3_client.generate_presigned_url(                     │ │
│  │    'get_object',                                       │ │
│  │    Params={                                            │ │
│  │      'Bucket': 'arc-chatbot-documents-...',            │ │
│  │      'Key': 'uploads/{doc_id}/{filename}'              │ │
│  │    },                                                  │ │
│  │    ExpiresIn=3600  # 1 hour                            │ │
│  │  )                                                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Temporary URL (1-hour expiry)                               │
│  https://s3.amazonaws.com/arc-chatbot-documents-...?         │
│  X-Amz-Algorithm=AWS4-HMAC-SHA256&                           │
│  X-Amz-Credential=...&                                       │
│  X-Amz-Date=20251204T100000Z&                                │
│  X-Amz-Expires=3600&                                         │
│  X-Amz-Signature=...                                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  User downloads PDF securely                                 │
│  ✅ No AWS credentials exposed                               │
│  ✅ Time-limited access                                      │
│  ✅ Specific document only                                   │
└─────────────────────────────────────────────────────────────┘
```

---

*Diagram created: December 4, 2025*
