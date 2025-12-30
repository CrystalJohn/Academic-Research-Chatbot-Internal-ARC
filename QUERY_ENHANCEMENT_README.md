# Tính năng Đánh giá và Cải thiện Câu hỏi

## Mô tả

Tính năng này tự động phân tích câu hỏi của user và đề xuất cách cải thiện để có kết quả tìm kiếm tốt hơn.

## Demo

![Query Enhancement Demo](docs/query-enhancement-demo.png)

## Cách sử dụng

### 1. Từ giao diện Chat

1. Gõ câu hỏi vào ô input
2. Click nút 💡 (bóng đèn) bên cạnh nút Send
3. Xem các gợi ý cải thiện:
   - **Category tags**: Specificity, Comparative, Impact, Context, Scope
   - **Suggestions**: Các gợi ý cụ thể với câu hỏi mẫu
   - **Best query**: Câu hỏi tổng hợp tốt nhất (highlighted)
4. Click vào câu hỏi mẫu để áp dụng ngay

### 2. Từ API

```bash
curl -X POST http://localhost:8000/api/chat/enhance-query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "What is cloud computing?"
  }'
```

**Response**:
```json
{
  "original_query": "What is cloud computing?",
  "quality_score": 0.4,
  "is_good_quality": false,
  "suggestions": [
    {
      "category": "specificity",
      "suggestion": "Thêm chi tiết về loại cloud hoặc use case cụ thể",
      "improved_query": "What are the key characteristics and deployment models of cloud computing?"
    }
  ],
  "improved_query": "What are the key characteristics, deployment models, and business benefits of cloud computing?"
}
```

## Tiêu chí đánh giá

1. **Specificity**: Câu hỏi có đủ cụ thể không?
2. **Comparative approach**: Có thể thêm yếu tố so sánh?
3. **Impact assessment**: Có thể hỏi về tác động, hệ quả?
4. **Context**: Cần thêm ngữ cảnh (thời gian, địa điểm, đối tượng)?
5. **Scope**: Phạm vi câu hỏi có phù hợp không?

## Ví dụ

### Câu hỏi kém → Câu hỏi tốt

❌ **Kém**: "What is cloud computing?"
- Quá chung chung, thiếu context

✅ **Tốt**: "What are the key characteristics, deployment models, and business benefits of cloud computing compared to traditional on-premises infrastructure?"
- Cụ thể, có so sánh, hỏi về lợi ích

---

❌ **Kém**: "Tell me about AI"
- Quá rộng, không rõ mục đích

✅ **Tốt**: "What are the main types of artificial intelligence algorithms and their practical applications in healthcare?"
- Có phạm vi rõ ràng, use case cụ thể

## Cấu hình

### Backend

File: `backend/app/services/ai/query_enhancement_service.py`

```python
QueryEnhancementService(
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0",  # Model
    region_name="ap-southeast-1"  # AWS region
)
```

### Frontend

File: `src/components/QueryEnhancement.jsx`

```javascript
// Tự động hiển thị khi câu hỏi dài > 10 ký tự
if (input.length > 10) {
  setShowEnhancement(true)
}
```

## Testing

### Test backend service

```bash
cd backend
python test_query_enhancement.py
```

### Test API endpoint

```bash
# Start backend
cd backend
uvicorn app.main:app --reload

# Test endpoint
curl -X POST http://localhost:8000/api/chat/enhance-query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "What is cloud computing?"}'
```

### Test frontend

```bash
# Start frontend
npm run dev

# Mở browser: http://localhost:5173
# Gõ câu hỏi và click nút 💡
```

## Lợi ích

✅ **Cải thiện kết quả**: Câu hỏi tốt hơn → kết quả chính xác hơn
✅ **Giáo dục user**: Học cách đặt câu hỏi hiệu quả
✅ **Tiết kiệm thời gian**: Ít phải hỏi lại
✅ **Tăng trải nghiệm**: UX tốt hơn với gợi ý thông minh

## Roadmap

- [ ] Cache kết quả phân tích
- [ ] Hỗ trợ tiếng Việt
- [ ] Analytics: track số lần áp dụng gợi ý
- [ ] A/B testing hiệu quả
- [ ] Học từ search history

## Tài liệu chi tiết

Xem: [docs/QUERY_ENHANCEMENT_FEATURE.md](docs/QUERY_ENHANCEMENT_FEATURE.md)
