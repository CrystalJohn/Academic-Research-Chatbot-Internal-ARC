# Agentic RAG with Tool Use (Bedrock Converse API)

## Tổng quan

Thay vì RAG đơn giản (retrieve → generate), **Agentic RAG** cho phép Claude tự quyết định:
- Khi nào cần search documents
- Query nào tối ưu nhất
- Filter gì cần áp dụng (doc_ids, pages, tables)
- Có cần search thêm không
- Cách tổng hợp thông tin tốt nhất

## So sánh với RAG thông thường

| Aspect | Simple RAG | Agentic RAG |
|--------|-----------|-------------|
| **Query** | User query trực tiếp | Claude reformulate query tối ưu |
| **Search** | 1 lần search | Nhiều lần search nếu cần |
| **Filter** | User chỉ định | Claude tự quyết định |
| **Reasoning** | Không có | Multi-step reasoning |
| **Context** | Fixed top-k | Adaptive based on need |
| **Quality** | Phụ thuộc user query | Claude optimize query |

## Architecture

```
User Question
    ↓
Claude Analyze
    ↓
┌─────────────────────────────────┐
│  Tool Decision Loop             │
│  (max 5 iterations)             │
│                                 │
│  1. Decide which tool to use    │
│  2. Execute tool                │
│  3. Analyze results             │
│  4. Need more info? → Loop      │
│  5. Enough info? → Generate     │
└─────────────────────────────────┘
    ↓
Final Answer + Citations
```

## Available Tools

### 1. search_documents
Tìm kiếm semantic trong documents.

**Parameters:**
- `query` (required): Search query
- `top_k` (optional): Number of results (default: 5, max: 20)
- `doc_ids` (optional): Filter by document IDs
- `page_min`, `page_max` (optional): Page range filter
- `include_tables` (optional): Include table content (default: true)

**Example:**
```json
{
  "query": "thuật toán Dijkstra",
  "top_k": 5,
  "doc_ids": ["doc-123"],
  "page_min": 10,
  "page_max": 50
}
```

### 2. list_available_documents
Liệt kê tất cả documents có sẵn.

**Parameters:**
- `status` (optional): Filter by status (EMBEDDING_DONE, UPLOADED, etc.)

**Use cases:**
- User hỏi "có những tài liệu nào?"
- Claude cần biết doc_ids để filter
- Check xem có documents nào available

### 3. get_document_info
Lấy thông tin chi tiết về 1 document.

**Parameters:**
- `doc_id` (required): Document ID

**Returns:**
- filename, page_count, chunk_count, status, uploaded_at

## Example Scenarios

### Scenario 1: Simple Question
**User:** "Thuật toán Dijkstra là gì?"

**Claude's actions:**
1. Tool: `search_documents(query="thuật toán Dijkstra", top_k=3)`
2. Analyze results
3. Generate answer with citations

**Tool calls:** 1
**Reasoning:** Straightforward question, 1 search enough

---

### Scenario 2: Comparison Question
**User:** "So sánh độ phức tạp của QuickSort và MergeSort"

**Claude's actions:**
1. Tool: `search_documents(query="QuickSort độ phức tạp", top_k=3)`
2. Tool: `search_documents(query="MergeSort độ phức tạp", top_k=3)`
3. Analyze both results
4. Generate comparison with citations

**Tool calls:** 2
**Reasoning:** Need separate searches for each algorithm

---

### Scenario 3: Document Discovery
**User:** "Có những tài liệu nào về cấu trúc dữ liệu?"

**Claude's actions:**
1. Tool: `list_available_documents(status="EMBEDDING_DONE")`
2. Tool: `search_documents(query="cấu trúc dữ liệu", top_k=10)`
3. Match search results with document list
4. Generate summary of relevant documents

**Tool calls:** 2
**Reasoning:** Need to list docs first, then search to find relevant ones

---

### Scenario 4: Specific Page Range
**User:** "Tìm thông tin về heap trong trang 20-30 của tài liệu X"

**Claude's actions:**
1. Tool: `list_available_documents()` (to find doc_id for "tài liệu X")
2. Tool: `search_documents(query="heap", doc_ids=["doc-X"], page_min=20, page_max=30)`
3. Generate answer with citations

**Tool calls:** 2
**Reasoning:** Need doc_id first, then filtered search

---

### Scenario 5: Table Search
**User:** "Tìm bảng so sánh độ phức tạp các thuật toán"

**Claude's actions:**
1. Tool: `search_documents(query="bảng độ phức tạp thuật toán", top_k=5, include_tables=true)`
2. Filter results to only tables (is_table=true)
3. Generate answer highlighting table content

**Tool calls:** 1
**Reasoning:** Single search with table filter

## API Usage

### Endpoint
```
POST /api/chat/agentic
```

### Request
```json
{
  "query": "Tìm thông tin về thuật toán Dijkstra",
  "conversation_id": "conv-abc123",
  "user_id": "user@example.com",
  "max_tokens": 4096
}
```

### Response
```json
{
  "answer": "Thuật toán Dijkstra là...",
  "citations": [
    {
      "citation_id": "[1]",
      "text": "...",
      "doc_id": "doc-123",
      "page": 45,
      "score": 0.89
    }
  ],
  "tool_calls": [
    {
      "name": "search_documents",
      "input": {"query": "thuật toán Dijkstra", "top_k": 5},
      "result": {"results_count": 5, "results": [...]}
    }
  ],
  "reasoning_steps": [
    "Using search_documents: {'query': 'thuật toán Dijkstra', 'top_k': 5}"
  ],
  "conversation_id": "conv-abc123",
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  },
  "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "timestamp": "2024-12-06T10:30:00Z"
}
```

## Benefits

### 1. Better Query Understanding
Claude có thể reformulate user query thành search query tối ưu hơn.

**Example:**
- User: "Cái thuật toán tìm đường đi ngắn nhất đó là gì nhỉ?"
- Claude search: "thuật toán đường đi ngắn nhất Dijkstra"

### 2. Multi-Step Reasoning
Claude có thể search nhiều lần để tìm đủ thông tin.

**Example:**
- User: "So sánh 3 thuật toán sắp xếp"
- Claude: Search 3 lần cho từng thuật toán

### 3. Smart Filtering
Claude tự quyết định filter nào cần áp dụng.

**Example:**
- User: "Tìm trong tài liệu về OOP"
- Claude: List docs → Find OOP doc_id → Search with filter

### 4. Adaptive Context
Claude chỉ search khi cần, không waste tokens.

**Example:**
- User: "Xin chào"
- Claude: Không search, trả lời greeting trực tiếp

### 5. Better Citations
Claude biết context của từng search result, cite chính xác hơn.

## Cost Comparison

### Simple RAG
- 1 embedding call: ~$0.0001
- 1 Claude call: ~$0.01
- **Total: ~$0.0101 per query**

### Agentic RAG
- 2-3 embedding calls: ~$0.0003
- 2-3 Claude calls (tool loop): ~$0.03
- **Total: ~$0.0303 per query**

**Trade-off:** 3x cost, but significantly better quality and accuracy.

## When to Use

### Use Agentic RAG when:
- ✅ User questions are complex or ambiguous
- ✅ Need multi-step reasoning
- ✅ Want best possible answer quality
- ✅ Budget allows 3x cost
- ✅ User expects intelligent behavior

### Use Simple RAG when:
- ✅ User questions are straightforward
- ✅ Single search is enough
- ✅ Cost is critical concern
- ✅ Speed is priority
- ✅ Simple retrieve → generate is sufficient

## Configuration

### Model Selection
```python
# Use Sonnet for best quality
rag_service = create_rag_with_tools_service(model="sonnet")

# Use Haiku for cost savings (may reduce tool use quality)
rag_service = create_rag_with_tools_service(model="haiku")
```

### Max Tool Iterations
```python
# In rag_with_tools_service.py
MAX_TOOL_ITERATIONS = 5  # Prevent infinite loops
```

Increase if you need more complex multi-step reasoning, but watch costs.

### Tool Definitions
Edit `TOOLS` in `claude_converse_service.py` to:
- Add new tools
- Modify tool descriptions
- Change input schemas

## Testing

### Local Test
```bash
cd samples
python test_agentic_rag.py
```

### API Test
```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tìm thông tin về thuật toán Dijkstra",
    "user_id": "test-user"
  }'
```

## Monitoring

### Key Metrics
- **Tool calls per query**: Average 1-3, max 5
- **Token usage**: 2-3x simple RAG
- **Response time**: 3-5 seconds (vs 1-2s simple RAG)
- **Citation accuracy**: Significantly better

### Logs
```python
logger.info(f"Tool iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}")
logger.info(f"Claude requested {len(tool_uses)} tool(s)")
logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
```

## Future Enhancements

### Potential New Tools
1. **search_by_similarity**: Find similar documents
2. **get_document_summary**: Get document overview
3. **search_citations**: Find papers that cite a specific paper
4. **search_authors**: Find papers by author
5. **search_date_range**: Filter by publication date

### Advanced Features
1. **Tool chaining**: Automatic tool dependency resolution
2. **Parallel tool execution**: Run multiple tools simultaneously
3. **Tool result caching**: Cache frequent tool results
4. **Custom tool definitions**: User-defined tools
5. **Tool usage analytics**: Track which tools are most useful

## Troubleshooting

### Issue: Too many tool iterations
**Solution:** Improve tool descriptions, add more specific examples

### Issue: Claude not using tools
**Solution:** Check system prompt, ensure tools are properly defined

### Issue: Wrong tool selection
**Solution:** Improve tool descriptions, add negative examples

### Issue: High costs
**Solution:** Switch to Haiku, reduce MAX_TOOL_ITERATIONS, use simple RAG for simple queries

## References

- [AWS Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Claude Tool Use Guide](https://docs.anthropic.com/claude/docs/tool-use)
- [Agentic RAG Patterns](https://www.anthropic.com/research/agentic-rag)

---

**Last Updated:** December 2024
