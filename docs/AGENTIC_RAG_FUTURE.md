# Agentic RAG - Future Enhancement (Post-MVP)

## 🎯 Status: DISABLED for MVP

**Reason:** Cost constraint - Agentic RAG costs ~3x Simple RAG

**Current approach:** Simple RAG (retrieve → generate) is sufficient for MVP

---

## 📊 Cost Analysis

| Approach | Cost per Query | Quality | Use Case |
|----------|---------------|---------|----------|
| **Simple RAG** | $0.01 | 70% | MVP, straightforward questions |
| **Agentic RAG** | $0.03 | 90% | Post-MVP, complex questions |

**MVP Budget:** $60/month → Simple RAG is better fit

---

## 🚀 When to Enable

Enable Agentic RAG when:

1. ✅ **MVP validated** - Users love the product
2. ✅ **Budget increased** - Can afford 3x cost
3. ✅ **User feedback** - Need better quality for complex questions
4. ✅ **Scale achieved** - More users = justify higher per-query cost

---

## 📁 Implementation Files (Ready but Disabled)

All code is ready, just commented out:

### Backend
- ✅ `backend/app/services/ai/claude_converse_service.py` - Converse API client
- ✅ `backend/app/services/search/rag_with_tools_service.py` - Agentic RAG orchestration
- ✅ `backend/app/api/chat_agentic.py` - API endpoint (commented out in main.py)

### Tests
- ✅ `samples/test_agentic_rag.py` - Test script
- ✅ `backend/test_converse_api.py` - API verification

### Documentation
- ✅ `docs/AGENTIC_RAG.md` - Full architecture guide
- ✅ `docs/UPDATE_IAM_FOR_CONVERSE.md` - IAM setup guide
- ✅ `AGENTIC_RAG_SETUP.md` - Setup checklist
- ✅ `QUICK_START_AGENTIC_RAG.md` - Quick start guide

---

## 🔄 How to Enable (Post-MVP)

### Step 1: Update boto3
```bash
cd backend
pip install --upgrade boto3>=1.35.0
```

### Step 2: Update IAM
```bash
cd terraform
./update-bedrock-permissions.sh
```

### Step 3: Enable endpoint
In `backend/app/main.py`:
```python
# Uncomment these lines:
from app.api.chat_agentic import router as chat_agentic_router
app.include_router(chat_agentic_router)
```

### Step 4: Restart backend
```bash
uvicorn app.main:app --reload
```

### Step 5: Test
```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{"query": "So sánh QuickSort và MergeSort"}'
```

---

## 💡 Benefits (When Enabled)

1. **Better query understanding** - Claude reformulates ambiguous questions
2. **Multi-step reasoning** - Can search multiple times for complex questions
3. **Smart filtering** - Auto-applies doc_ids, page ranges, table filters
4. **Adaptive context** - Only searches when needed (saves cost on greetings)
5. **Improved citations** - Better context awareness

---

## 📈 Metrics to Track (Post-MVP)

Before enabling, track these metrics:

- **User satisfaction** - Are users happy with Simple RAG?
- **Query complexity** - How many questions need multi-step reasoning?
- **Budget headroom** - Can we afford 3x cost?
- **User growth** - More users = justify higher per-query cost

**Decision threshold:**
- If >30% queries are complex → Enable Agentic RAG
- If budget allows 3x cost → Enable Agentic RAG
- If user satisfaction <70% → Enable Agentic RAG

---

## 🎓 Learning Resources

- [AWS Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
- [Claude Tool Use Guide](https://docs.anthropic.com/claude/docs/tool-use)
- [Agentic RAG Patterns](https://www.anthropic.com/research/agentic-rag)

---

## 📝 Notes for Future Team

**Why we built it but disabled:**
- Wanted to be ready for scale
- Code is production-ready
- Just need to flip a switch when budget allows

**What to test when enabling:**
1. Compare quality: Simple vs Agentic RAG
2. Monitor costs: Track actual 3x multiplier
3. User feedback: Is quality improvement worth cost?
4. Performance: Response time impact

**Recommendation:**
- Start with A/B test: 10% traffic to Agentic RAG
- Measure quality improvement vs cost increase
- Scale up if ROI is positive

---

**Status:** Ready for future, disabled for MVP cost optimization

**Last Updated:** December 2024
