# Tính năng Đánh giá và Cải thiện Câu hỏi (Query Enhancement)

## Tổng quan

Tính năng này giúp user cải thiện chất lượng câu hỏi để nhận được kết quả tìm kiếm tốt hơn từ hệ thống RAG.

## Cách hoạt động

### 1. Backend Service

**File**: `backend/app/services/ai/query_enhancement_service.py`

Service sử dụng Claude Haiku để phân tích câu hỏi theo các tiêu chí:

- **Specificity (Tính cụ thể)**: Câu hỏi có đủ chi tiết không?
- **Comparative approach (So sánh)**: Có thể thêm yếu tố so sánh?
- **Impact assessment (Đánh giá tác động)**: Có thể hỏi về ảnh hưởng, hệ quả?
- **Context (Ngữ cảnh)**: Cần thêm phạm vi, thời gian, đối tượng?
- **Scope (Phạm vi)**: Câu hỏi có quá rộng hay quá hẹp?

**Output**:
```json
{
  "quality_score": 0.7,
  "is_good_quality": false,
  "suggestions": [
    {
      "category": "specificity",
      "suggestion": "Thêm ngữ cảnh cụ thể về...",
      "improved_query": "Câu hỏi cải thiện..."
    }
  ],
  "improved_query": "Câu hỏi tổng hợp tốt nhất"
}
```

### 2. API Endpoint

**Endpoint**: `POST /api/chat/enhance-query`

**Request**:
```json
{
  "query": "What are the security implications of hybrid cloud computing models for enterprise data protection?"
}
```

**Response**:
```json
{
  "original_query": "...",
  "quality_score": 0.6,
  "is_good_quality": false,
  "suggestions": [
    {
      "category": "specificity",
      "suggestion": "Thêm ngữ cảnh về loại doanh nghiệp hoặc ngành công nghiệp cụ thể",
      "improved_query": "What are the security implications of hybrid cloud computing models for enterprise data protection in the financial services industry?"
    },
    {
      "category": "comparative_approach",
      "suggestion": "So sánh với các mô hình cloud khác",
      "improved_query": "What are the security implications of hybrid cloud computing models compared to public or private cloud for enterprise data protection?"
    }
  ],
  "improved_query": "What are the specific security implications and risks of hybrid cloud computing models for enterprise data protection in regulated industries, compared to traditional on-premises or public cloud solutions?"
}
```

### 3. Frontend Component

**File**: `src/components/QueryEnhancement.jsx`

Component hiển thị:
- Nút trigger để phân tích câu hỏi
- Panel với các gợi ý cải thiện
- Category tags (Specificity, Comparative, Impact, etc.)
- Các câu hỏi mẫu có thể click để áp dụng
- Câu hỏi đề xuất tốt nhất (highlighted)

**Tích hợp vào ChatPage**:
- Tự động hiển thị khi user gõ câu hỏi dài (>10 ký tự)
- Nút toggle bên cạnh nút Send
- Ẩn khi user gửi câu hỏi

## Sử dụng

### Từ UI

1. Gõ câu hỏi vào input box
2. Click nút 💡 (lightbulb) bên cạnh nút Send
3. Xem các gợi ý cải thiện
4. Click vào câu hỏi mẫu để áp dụng
5. Hoặc click "Sử dụng câu hỏi này" cho câu hỏi đề xuất tốt nhất

### Từ API

```bash
curl -X POST http://localhost:8000/api/chat/enhance-query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "What is cloud computing?"}'
```

## Lợi ích

1. **Cải thiện kết quả tìm kiếm**: Câu hỏi rõ ràng hơn → kết quả chính xác hơn
2. **Giáo dục user**: Học cách đặt câu hỏi tốt hơn
3. **Tăng trải nghiệm**: Giảm số lần phải hỏi lại
4. **Tiết kiệm token**: Ít phải retry hơn

## Cấu hình

### Model

Mặc định sử dụng **Claude Haiku** (nhanh và rẻ):
```python
QueryEnhancementService(
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0"
)
```

### Threshold

Chỉ hiển thị gợi ý nếu `quality_score < 0.7`:
```python
if analysis.quality_score < 0.7:
    # Show suggestions
```

## Tối ưu hóa

1. **Cache**: Có thể cache kết quả phân tích cho các câu hỏi giống nhau
2. **Debounce**: Chỉ gọi API sau khi user ngừng gõ 1-2 giây
3. **Async**: Không block UI khi đang phân tích
4. **Fallback**: Nếu API lỗi, không hiển thị gì (graceful degradation)

## Testing

```bash
# Test backend service
cd backend
python -c "
from app.services.ai.query_enhancement_service import get_query_enhancement_service
service = get_query_enhancement_service()
result = service.analyze_query('What is cloud computing?')
print(result)
"

# Test API endpoint
curl -X POST http://localhost:8000/api/chat/enhance-query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query": "What is cloud computing?"}'
```

## Ví dụ

### Câu hỏi kém chất lượng

**Input**: "What is cloud computing?"

**Suggestions**:
- Specificity: "What are the key characteristics and deployment models of cloud computing?"
- Comparative: "What is cloud computing and how does it differ from traditional on-premises infrastructure?"
- Impact: "What is cloud computing and what are its benefits for businesses?"

**Best**: "What are the key characteristics, deployment models, and business benefits of cloud computing compared to traditional on-premises infrastructure?"

### Câu hỏi tốt

**Input**: "What are the specific security implications and risks of hybrid cloud computing models for enterprise data protection in regulated industries, compared to traditional on-premises or public cloud solutions?"

**Output**: `is_good_quality: true`, không hiển thị gợi ý

## Roadmap

- [ ] Thêm cache cho kết quả phân tích
- [ ] Hỗ trợ nhiều ngôn ngữ (tiếng Việt)
- [ ] Tích hợp với search history để học pattern
- [ ] A/B testing để đo lường hiệu quả
- [ ] Analytics: track số lần user áp dụng gợi ý
