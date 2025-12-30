# MVP Technical Decisions

## 🎯 Project Context

**Project:** ARC Chatbot - Academic Research Assistant  
**Timeline:** 20 days  
**Budget:** $60/month  
**Team:** 4 interns  
**Goal:** MVP for 50 researchers, 750 documents

---

## ✅ Decisions Made

### 1. **Simple RAG over Agentic RAG**

**Decision:** Use simple retrieve → generate approach

**Rationale:**
- Cost: $0.01/query vs $0.03/query (3x cheaper)
- Budget: $60/month can't afford 3x cost
- Quality: 70% satisfaction is acceptable for MVP
- Complexity: Simpler to maintain for intern team

**Trade-off:**
- ❌ Lower quality for complex questions
- ✅ 3x cost savings
- ✅ Faster response time
- ✅ Simpler codebase

**Future:** Enable Agentic RAG post-MVP when budget allows

---

### 2. **Qdrant (self-hosted) over OpenSearch Serverless**

**Decision:** Run Qdrant in Docker on EC2

**Rationale:**
- Cost: Free vs $90/month (OpenSearch minimum)
- Scale: 7,500 vectors fits in 400MB RAM
- Performance: Good enough for 50 users

**Trade-off:**
- ❌ Manual scaling needed
- ❌ No managed backups
- ✅ $90/month savings
- ✅ Full control

---

### 3. **EC2 Worker over Lambda**

**Decision:** Run document processing on EC2

**Rationale:**
- No timeout limits (Lambda 15min max)
- Direct Qdrant access (no network overhead)
- Simpler architecture for interns

**Trade-off:**
- ❌ Always running (even when idle)
- ✅ No timeout issues
- ✅ Simpler code
- ✅ Direct DB access

---

### 4. **NAT Gateway over NAT Instance**

**Decision:** Use managed NAT Gateway

**Rationale:**
- Simpler for intern team
- Managed service (no maintenance)
- Only $21.60/month (acceptable)

**Trade-off:**
- ❌ $18/month more than NAT Instance
- ✅ Zero maintenance
- ✅ Better reliability
- ✅ Simpler for interns

---

### 5. **Hybrid IDP: PyPDF2 + Textract**

**Decision:** Use PyPDF2 for digital PDFs, Textract for scanned

**Rationale:**
- Cost: PyPDF2 is free, Textract only when needed
- Quality: PyPDF2 good for digital, Textract for scanned
- Budget: 100 pages/month free tier

**Trade-off:**
- ❌ More complex logic
- ✅ Significant cost savings
- ✅ Good quality for both types

---

### 6. **Claude 3.5 Sonnet with Haiku Fallback**

**Decision:** Use Sonnet by default, fallback to Haiku on budget

**Rationale:**
- Quality: Sonnet best for research questions
- Cost: Haiku 12x cheaper for fallback
- Budget: Rate limiting + fallback keeps costs down

**Trade-off:**
- ❌ Complex budget management
- ✅ Best quality when possible
- ✅ Cost protection

---

### 7. **Cohere Embed Multilingual v3**

**Decision:** Use Cohere over Titan Embeddings

**Rationale:**
- Quality: Better for Vietnamese + English
- Dimensions: 1024 (good balance)
- Cost: ~$0.0001/1K tokens (acceptable)

**Trade-off:**
- ✅ Better multilingual support
- ✅ Good quality
- ✅ Reasonable cost

---

## 💰 Cost Breakdown (MVP)

| Service | Monthly Cost | Justification |
|---------|--------------|---------------|
| EC2 t3.small | $10.08 | Runs backend + Qdrant + worker |
| EBS 30GB | $2.40 | Storage for app + vectors |
| NAT Gateway | $21.60 | Managed, simpler for interns |
| Claude Sonnet | $25.00 | Best quality for research |
| Cohere Embed | $0.75 | Multilingual embeddings |
| CloudWatch | $1.90 | Monitoring + logs |
| **TOTAL** | **~$60** | Within budget ✅ |

**Savings from decisions:**
- OpenSearch avoided: +$90/month
- Agentic RAG avoided: +$50/month (3x Claude cost)
- NAT Instance avoided: +$18/month maintenance time

**Total potential cost:** $218/month  
**Actual cost:** $60/month  
**Savings:** $158/month (72% reduction)

---

## 🚀 Post-MVP Enhancements

When budget increases or MVP validates:

### Phase 1: Quality Improvements ($120/month)
1. ✅ Enable Agentic RAG (+$50/month)
2. ✅ Increase Claude budget (+$25/month)
3. ✅ Add more Textract pages (+$15/month)

### Phase 2: Scale ($200/month)
1. ✅ Upgrade to t3.medium (+$10/month)
2. ✅ Add RDS for metadata (+$15/month)
3. ✅ Multi-AZ deployment (+$30/month)

### Phase 3: Production ($500/month)
1. ✅ OpenSearch Serverless (+$90/month)
2. ✅ Auto-scaling EC2 (+$50/month)
3. ✅ CloudFront + WAF (+$30/month)

---

## 📊 Success Metrics (MVP)

Track these to decide on enhancements:

### User Satisfaction
- Target: >70% positive feedback
- Measure: User surveys, chat ratings
- Decision: If <70%, enable Agentic RAG

### Cost per User
- Target: <$1.20/user/month (50 users)
- Measure: CloudWatch + Bedrock costs
- Decision: If under budget, increase quality

### Query Success Rate
- Target: >80% queries answered correctly
- Measure: Citation accuracy, user feedback
- Decision: If <80%, improve RAG quality

### Response Time
- Target: <3 seconds average
- Measure: API latency logs
- Decision: If >3s, optimize or scale

---

## 🎓 Lessons for Team

### What Worked
1. ✅ Simple RAG is good enough for MVP
2. ✅ Self-hosted Qdrant saves significant cost
3. ✅ Hybrid IDP balances cost and quality
4. ✅ Budget management prevents overspend

### What to Watch
1. ⚠️ Qdrant scaling (manual process)
2. ⚠️ EC2 single point of failure
3. ⚠️ NAT Gateway cost (always running)
4. ⚠️ Claude budget limits (may frustrate users)

### Future Considerations
1. 💡 A/B test Agentic RAG on 10% traffic
2. 💡 Monitor which queries fail with Simple RAG
3. 💡 Track cost per query type
4. 💡 Collect user feedback on quality

---

## 📝 Decision Log

| Date | Decision | Reason | Impact |
|------|----------|--------|--------|
| Dec 2024 | Disable Agentic RAG | Cost (3x) | -$50/month |
| Dec 2024 | Use Qdrant self-hosted | Cost | -$90/month |
| Dec 2024 | Hybrid IDP | Cost + Quality | -$30/month |
| Dec 2024 | NAT Gateway | Simplicity | +$18/month |

**Net savings:** $152/month from smart decisions

---

**Conclusion:** MVP is optimized for $60/month budget while maintaining acceptable quality. Post-MVP enhancements are documented and ready to enable when budget allows.

**Last Updated:** December 2024
