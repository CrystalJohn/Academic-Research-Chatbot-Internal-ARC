"""
Query Enhancement Service

Đánh giá chất lượng câu hỏi của user và đề xuất cải thiện.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


@dataclass
class QuerySuggestion:
    """Gợi ý cải thiện câu hỏi."""
    category: str  # "specificity", "comparative_approach", "impact_assessment", etc.
    suggestion: str  # Nội dung gợi ý
    improved_query: str  # Câu hỏi đã cải thiện


@dataclass
class QueryAnalysis:
    """Kết quả phân tích câu hỏi."""
    original_query: str
    quality_score: float  # 0-1, càng cao càng tốt
    is_good_quality: bool  # True nếu không cần cải thiện
    suggestions: List[QuerySuggestion]
    improved_query: Optional[str]  # Câu hỏi tổng hợp đã cải thiện


class QueryEnhancementService:
    """
    Service đánh giá và cải thiện câu hỏi của user.
    
    Sử dụng Claude để:
    - Đánh giá độ rõ ràng, cụ thể của câu hỏi
    - Đề xuất cách cải thiện (thêm context, so sánh, đánh giá tác động)
    - Tạo câu hỏi mẫu tốt hơn
    """
    
    SYSTEM_PROMPT = """Bạn là chuyên gia đánh giá và cải thiện câu hỏi nghiên cứu.

Nhiệm vụ: Phân tích câu hỏi của user và đề xuất cách cải thiện để có kết quả tìm kiếm tốt hơn.

Tiêu chí đánh giá:
1. **Specificity (Tính cụ thể)**: Câu hỏi có đủ chi tiết không? Có từ khóa rõ ràng?
2. **Comparative approach (So sánh)**: Có thể thêm yếu tố so sánh không?
3. **Impact assessment (Đánh giá tác động)**: Có thể hỏi về ảnh hưởng, hệ quả không?
4. **Context (Ngữ cảnh)**: Có cần thêm phạm vi, thời gian, đối tượng?
5. **Scope (Phạm vi)**: Câu hỏi có quá rộng hay quá hẹp?

Đầu ra JSON:
{
  "quality_score": 0.7,  // 0-1, >0.7 là tốt
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

Lưu ý:
- Nếu quality_score > 0.7, trả về is_good_quality=true và suggestions=[]
- Chỉ đề xuất 2-3 cải thiện quan trọng nhất
- improved_query phải tự nhiên, dễ hiểu
- Giữ nguyên ngôn ngữ của câu hỏi gốc"""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region_name: str = "ap-southeast-1",
    ):
        """
        Initialize service.
        
        Args:
            model_id: Bedrock model ID (dùng Haiku cho nhanh và rẻ)
            region_name: AWS region
        """
        self.model_id = model_id
        
        config = Config(
            region_name=region_name,
            read_timeout=60,
            connect_timeout=30,
        )
        
        self.client = boto3.client("bedrock-runtime", config=config)
        logger.info(f"Initialized QueryEnhancementService with model: {model_id}")
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Phân tích và đề xuất cải thiện câu hỏi.
        
        Args:
            query: Câu hỏi gốc của user
            
        Returns:
            QueryAnalysis với gợi ý cải thiện
        """
        try:
            # Gọi Claude để phân tích
            response = self.client.converse(
                modelId=self.model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": f"Phân tích câu hỏi này:\n\n{query}\n\nTrả về JSON theo format đã định."
                            }
                        ]
                    }
                ],
                system=[{"text": self.SYSTEM_PROMPT}],
                inferenceConfig={
                    "maxTokens": 1024,
                    "temperature": 0.3,  # Thấp để ổn định
                }
            )
            
            # Parse response
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            
            text_response = None
            for block in content:
                if "text" in block:
                    text_response = block["text"]
                    break
            
            if not text_response:
                logger.warning("No text response from Claude")
                return self._create_fallback_analysis(query)
            
            # Parse JSON
            import json
            # Tìm JSON trong response (có thể có text xung quanh)
            start_idx = text_response.find("{")
            end_idx = text_response.rfind("}") + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("No JSON found in response")
                return self._create_fallback_analysis(query)
            
            json_str = text_response[start_idx:end_idx]
            result = json.loads(json_str)
            
            # Convert to QueryAnalysis
            suggestions = [
                QuerySuggestion(
                    category=s.get("category", "general"),
                    suggestion=s.get("suggestion", ""),
                    improved_query=s.get("improved_query", "")
                )
                for s in result.get("suggestions", [])
            ]
            
            return QueryAnalysis(
                original_query=query,
                quality_score=result.get("quality_score", 0.5),
                is_good_quality=result.get("is_good_quality", False),
                suggestions=suggestions,
                improved_query=result.get("improved_query")
            )
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)
            return self._create_fallback_analysis(query)
    
    def _create_fallback_analysis(self, query: str) -> QueryAnalysis:
        """Tạo phân tích mặc định khi có lỗi."""
        return QueryAnalysis(
            original_query=query,
            quality_score=0.6,
            is_good_quality=True,  # Không hiển thị gợi ý nếu có lỗi
            suggestions=[],
            improved_query=None
        )


# Singleton instance
_service_instance: Optional[QueryEnhancementService] = None


def get_query_enhancement_service() -> QueryEnhancementService:
    """Get or create singleton instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = QueryEnhancementService()
    return _service_instance
