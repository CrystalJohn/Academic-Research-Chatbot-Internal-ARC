# 🚀 Quick Start: Agentic RAG

## ⚡ TL;DR - 3 Commands

```bash
# 1. Update IAM (choose one method)
cd terraform && ./update-bedrock-permissions.sh

# 2. Update boto3
cd backend && pip install --upgrade boto3>=1.35.0

# 3. Restart backend
uvicorn app.main:app --reload --port 8000
```

---

## 📋 Step-by-Step

### 1️⃣ Update IAM Permissions

**Option A: Terraform (Recommended)**
```bash
cd terraform
./update-bedrock-permissions.sh
```

**Option B: AWS Console**
- Go to IAM → Roles → `arc-chatbot-dev-ec2-role`
- Edit `arc-chatbot-dev-ec2-bedrock-policy`
- Add: `bedrock:Converse`, `bedrock:ConverseStream`

**Option C: AWS CLI**
```bash
aws iam put-role-policy \
  --role-name arc-chatbot-dev-ec2-role \
  --policy-name arc-chatbot-dev-ec2-bedrock-policy \
  --policy-document file://terraform/modules/iam/bedrock-policy.json
```

**Verify:**
```bash
aws iam get-role-policy \
  --role-name arc-chatbot-dev-ec2-role \
  --policy-name arc-chatbot-dev-ec2-bedrock-policy \
  | grep Converse
```

---

### 2️⃣ Update boto3

```bash
cd backend
pip install --upgrade boto3>=1.35.0
```

**Verify:**
```bash
python test_converse_api.py
```

**Expected:**
```
✅ boto3 version: 1.35.x
✅ converse() method is available
✅ Converse API is ready!
```

---

### 3️⃣ Restart Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Check logs for:**
- `Initialized ClaudeConverseService` ✅
- `Initialized RAGWithToolsService` ✅
- No import errors ✅

---

### 4️⃣ Test Endpoints

**Health check:**
```bash
curl http://localhost:8000/api/chat/agentic/health
```

**Simple query (no tools):**
```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{"query": "Xin chào", "user_id": "test"}'
```

**Search query (with tools):**
```bash
curl -X POST http://localhost:8000/api/chat/agentic \
  -H "Content-Type: application/json" \
  -d '{"query": "Tìm thông tin về thuật toán Dijkstra", "user_id": "test"}'
```

---

## 🎯 Success Checklist

- [ ] IAM policy updated (Converse permission added)
- [ ] boto3 >= 1.35.0 installed
- [ ] `test_converse_api.py` passes
- [ ] Backend starts without errors
- [ ] Health endpoint returns 200
- [ ] Greeting query works (no tools)
- [ ] Search query works (1-2 tools)
- [ ] Citations displayed correctly

---

## 📚 Full Documentation

- **Setup Guide:** `AGENTIC_RAG_SETUP.md`
- **IAM Update:** `docs/UPDATE_IAM_FOR_CONVERSE.md`
- **Architecture:** `docs/AGENTIC_RAG.md`

---

## 🐛 Common Issues

### "AccessDeniedException"
→ IAM policy chưa update. Run step 1 again.

### "converse() not found"
→ boto3 quá cũ. Run step 2 again.

### "Max tool iterations reached"
→ Check documents đã upload chưa. Upload test docs first.

### Import errors
→ `pip install -r backend/requirements.txt`

---

## 💡 Tips

1. **Test locally first** before deploying to EC2
2. **Monitor costs** - Agentic RAG ~3x simple RAG
3. **Compare quality** - Use both endpoints to see difference
4. **Tune tools** - Edit tool descriptions if needed

---

**Ready?** Start with Step 1! 🚀
