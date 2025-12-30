"""
Demo Query Enhancement - Không cần authentication

Chạy demo:
    python backend/demo_query_enhancement.py
"""

import asyncio
import logging
from app.services.ai.query_enhancement_service import get_query_enhancement_service

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def demo_query_enhancement():
    """Demo tính năng query enhancement với UI đẹp."""
    
    service = get_query_enhancement_service()
    
    print("\n" + "="*80)
    print("🔍 DEMO: Tính năng Đánh giá và Cải thiện Câu hỏi")
    print("="*80 + "\n")
    
    test_cases = [
        {
            "query": "What is cloud computing?",
            "description": "Câu hỏi quá chung chung"
        },
        {
            "query": "Tell me about AI",
            "description": "Câu hỏi thiếu cụ thể"
        },
        {
            "query": "What are the benefits of cloud computing?",
            "description": "Câu hỏi khá tốt"
        },
        {
            "query": "What are the specific security implications and risks of hybrid cloud computing models for enterprise data protection in regulated industries?",
            "description": "Câu hỏi rất tốt"
        },
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        query = test_case["query"]
        description = test_case["description"]
        
        print(f"\n{'─'*80}")
        print(f"📝 Test Case {i}: {description}")
        print(f"{'─'*80}")
        print(f"\n❓ Câu hỏi gốc:")
        print(f"   \"{query}\"")
        
        try:
            result = service.analyze_query(query)
            
            # Quality score
            score_emoji = "🟢" if result.quality_score >= 0.7 else "🟡" if result.quality_score >= 0.5 else "🔴"
            print(f"\n{score_emoji} Điểm chất lượng: {result.quality_score:.0%}")
            
            if result.is_good_quality:
                print("✅ Câu hỏi đã tốt, không cần cải thiện!")
            else:
                print("⚠️  Câu hỏi cần cải thiện")
            
            # Suggestions
            if result.suggestions:
                print(f"\n💡 Gợi ý cải thiện ({len(result.suggestions)}):")
                for j, suggestion in enumerate(result.suggestions, 1):
                    category_emoji = {
                        "specificity": "🎯",
                        "comparative_approach": "⚖️",
                        "impact_assessment": "📊",
                        "context": "🌍",
                        "scope": "📏",
                        "general": "💬"
                    }.get(suggestion.category, "💡")
                    
                    print(f"\n   {category_emoji} {j}. {suggestion.category.upper()}")
                    print(f"      → {suggestion.suggestion}")
                    print(f"      ✨ \"{suggestion.improved_query}\"")
            
            # Best improved query
            if result.improved_query and not result.is_good_quality:
                print(f"\n🌟 Câu hỏi đề xuất tốt nhất:")
                print(f"   \"{result.improved_query}\"")
            
        except Exception as e:
            print(f"❌ Lỗi: {e}")
    
    print("\n" + "="*80)
    print("✅ Demo hoàn thành!")
    print("="*80 + "\n")


if __name__ == "__main__":
    demo_query_enhancement()
