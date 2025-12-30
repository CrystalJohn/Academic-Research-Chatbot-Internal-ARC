# Citation Contract Enforcement

## 📋 Overview

Đã implement **Smart Citation** - một cơ chế citation thông minh, tránh spam và đảm bảo chất lượng.

## 🎯 Problems Solved

**Trước đây:**
- ❌ "Cite EVERY piece of information" → spam [1][2][3] khó đọc
- ❌ "Use ALL citations" → model nhét citation không liên quan
- ❌ Mất trust vì "cite cho có"
- ❌ Không có format chuẩn

**Bây giờ:**
- ✅ "Cite only KEY CLAIMS" → chỉ cite định nghĩa, số liệu, kết luận
- ✅ "Max 1-2 citations per sentence" → dễ đọc
- ✅ "Do NOT try to use all citations" → chất lượng hơn số lượng
- ✅ Format 4 phần: Answer/Evidence/Limitations/Next Steps

## 🔧 Implementation

### 1. Smart Citation Rules

```
📌 SMART CITATION RULES:
- Cite only KEY CLAIMS (definitions, data, conclusions)
- Max 1-2 citations per sentence
- Do NOT cite unrelated sources
- Do NOT try to use all citations - quality over quantity
```

### 2. Structured Response Format (4 Sections)

```markdown
## Answer
2-4 sentences answering the question. Max 1 citation per sentence.

## Evidence
- Key point 1 [1] (p.X)
- Key point 2 [2] (p.Y)

## Limitations
What the documents do NOT cover (1 sentence).

## Next Steps
1 suggestion for follow-up.
```

### 3. Citation Contract (Unchanged)

```
⚠️ CITATION CONTRACT:
- You may ONLY cite using IDs: [1..N]
- DO NOT create new citation IDs beyond this range
```

## 📊 Before vs After

### ❌ BEFORE (Spam Citations)

```
OOP là một mô hình lập trình [1] dựa trên các đối tượng [1]. 
Các đặc điểm chính [2] bao gồm encapsulation [2], inheritance [2], 
và polymorphism [2]. Classes [3] là bản thiết kế [3] để tạo objects [3].
```

**Problems:**
- 9 citations trong 3 câu
- Khó đọc, spam
- Không có cấu trúc

### ✅ AFTER (Smart Citations)

```markdown
## Answer
OOP là một mô hình lập trình dựa trên các đối tượng [1]. 
Các đặc điểm chính bao gồm encapsulation, inheritance, và polymorphism [2].

## Evidence
- Định nghĩa OOP [1] (p.5)
- Các đặc điểm chính [2] (p.6)
- Classes và objects [3] (p.12)

## Limitations
Tài liệu không đề cập đến ví dụ code cụ thể.

## Next Steps
Hỏi về cách implement OOP trong ngôn ngữ cụ thể.
```

**Benefits:**
- 2 citations trong Answer (dễ đọc)
- Evidence section cho chi tiết
- Cấu trúc rõ ràng
- Actionable next steps

## 📝 Code Changes

### Modified Files

**`backend/app/services/search/rag_service.py`**

1. **SYSTEM_PROMPTS** (English) - 4 templates updated
2. **SYSTEM_PROMPTS_VI** (Vietnamese) - 4 templates updated  
3. **QUERY_TEMPLATE** - simplified with 4-section format

### Key Changes

**Old rules:**
```
- ALWAYS cite sources for EVERY piece of information
- Use ALL provided citations when possible
```

**New rules:**
```
- Cite only KEY CLAIMS (definitions, data, conclusions)
- Max 1-2 citations per sentence
- Do NOT cite unrelated sources
- Do NOT try to use all citations - quality over quantity
```

## ✅ Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Citations per sentence | 3-5 (spam) | 1-2 (clean) |
| Readability | Low | High |
| Academic trust | Low | High |
| Structure | None | 4 sections |
| Citation density | Answer | Evidence section |

## 🧪 Testing

```bash
cd backend
python test_citation_contract.py
```

## 📚 Related

- [System Overview](./SYSTEM_OVERVIEW_VI.md)
- [RAG Service](../backend/app/services/search/rag_service.py)

---

**Status**: ✅ Implemented & Tested  
**Date**: December 25, 2024  
**Version**: 2.0.0 (Smart Citation)
