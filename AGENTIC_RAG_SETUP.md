# Agentic RAG Setup Checklist

## ✅ Bước 1: Update boto3

```bash
cd backend
pip install --upgrade boto3>=1.35.0
```

**Verify:**
```bash
python test_converse_api.py
```

Phải thấy: `✅ converse() method is available`

---

## ✅ Bước 2: Verify Bedrock permissions

Check IAM role/user có permissions:
- `bedrock:InvokeModel` ✅ (đã có)
- `bedrock:Converse` ← **CẦN THÊM**

**Update IAM policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:Converse"
      ],
      "Resource": [
        "arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:ap-southeast-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0",
        "arn:aws:bedrock:ap-southeast-1::foundation-model/cohere.embed-multilingual-v3"
      ]
    }
  ]
}
```

---

## ✅ Bước 3: Restart backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Check logs:**
- `Initialized ClaudeConverseService with model: ...` ✅
- `Initialized RAGWithToolsService` ✅
- No import errors ✅

---

## ✅ Bước 4: Test health endpoint

```bash
curl http://localhost:8000/api/chat/agentic/health
```

**Expected:**
```json
{
  "status": "healthy",
  "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "tools_available": ...
}
```

---

## ✅ Bước 5: Test simple query

```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Xin chào",
    "user_id": "test-user"
  }'
```

**Expected:**
- No tool calls (greeting doesn't need search)
- Answer: Vietnamese greeting
- Status 200

---

## ✅ Bước 6: Test search query

```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tìm thông tin về thuật toán Dijkstra",
    "user_id": "test-user"
  }'
```

**Expected:**
- 1-2 tool calls (search_documents)
- Citations with [1], [2], etc.
- Answer with relevant info
- Status 200

---

## ✅ Bước 7: Test complex query

```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "So sánh độ phức tạp của QuickSort và MergeSort",
    "user_id": "test-user"
  }'
```

**Expected:**
- 2-3 tool calls (multiple searches)
- Citations from multiple sources
- Comparison answer
- Status 200

---

## ✅ Bước 8: Run full test suite

```bash
cd samples
python test_agentic_rag.py
```

**Expected:**
- All 4 test scenarios pass
- Tool calls logged
- Reasoning steps shown
- Citations displayed

---

## 🐛 Troubleshooting

### Error: "converse() method not found"
**Solution:** Upgrade boto3
```bash
pip install --upgrade boto3>=1.35.0
```

### Error: "AccessDeniedException"
**Solution:** Add `bedrock:Converse` permission to IAM

### Error: "ModelNotFoundException"
**Solution:** Check model ID is correct:
- Sonnet: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- Haiku: `anthropic.claude-3-5-haiku-20241022-v1:0`

### Error: "Max tool iterations reached"
**Solution:** 
- Check tool descriptions are clear
- Verify search is returning results
- May need to increase MAX_TOOL_ITERATIONS

### Error: Import errors
**Solution:**
```bash
cd backend
pip install -r requirements.txt
```

---

## 📊 Compare with Simple RAG

### Test both endpoints:

**Simple RAG:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "So sánh QuickSort và MergeSort",
    "top_k": 5
  }'
```

**Agentic RAG:**
```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{
    "query": "So sánh QuickSort và MergeSort"
  }'
```

**Compare:**
- Answer quality
- Citation accuracy
- Response time
- Token usage
- Cost

---

## ✅ Success Criteria

- [ ] boto3 >= 1.35.0 installed
- [ ] IAM has `bedrock:Converse` permission
- [ ] Backend starts without errors
- [ ] Health endpoint returns healthy
- [ ] Greeting query works (no tools)
- [ ] Search query works (1-2 tools)
- [ ] Complex query works (2-3 tools)
- [ ] Test suite passes
- [ ] Better quality than simple RAG

---

## 🚀 Next Steps

Once all tests pass:

1. **Update frontend** to use `/api/chat/agentic`
2. **Monitor costs** - Should be ~3x simple RAG
3. **Collect feedback** - Is quality improvement worth cost?
4. **Tune tools** - Improve descriptions if needed
5. **Add more tools** - search_by_similarity, get_summary, etc.

---

**Ready to test?** Start with Bước 1! 🎯
