"""
Test Query Enhancement Service

Chạy test:
    python backend/test_query_enhancement.py
"""

import asyncio
import logging
from app.services.ai.query_enhancement_service import get_query_enhancement_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_query_enhancement():
    """Test query enhancement với các câu hỏi mẫu."""
    
    service = get_query_enhancement_service()
    
    test_queries = [
        # Câu hỏi kém chất lượng
        "What is cloud computing?",
        "Tell me about AI",
        "How does it work?",
        
        # Câu hỏi trung bình
        "What are the benefits of cloud computing?",
        "Explain machine learning algorithms",
        
        # Câu hỏi tốt
        "What are the specific security implications and risks of hybrid cloud computing models for enterprise data protection in regulated industries?",
    ]
    
    for query in test_queries:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing query: {query}")
        logger.info(f"{'='*80}")
        
        try:
            result = service.analyze_query(query)
            
            logger.info(f"Quality Score: {result.quality_score:.2f}")
            logger.info(f"Is Good Quality: {result.is_good_quality}")
            
            if result.suggestions:
                logger.info(f"\nSuggestions ({len(result.suggestions)}):")
                for i, suggestion in enumerate(result.suggestions, 1):
                    logger.info(f"\n  {i}. Category: {suggestion.category}")
                    logger.info(f"     Suggestion: {suggestion.suggestion}")
                    logger.info(f"     Improved: {suggestion.improved_query}")
            
            if result.improved_query:
                logger.info(f"\nBest Improved Query:")
                logger.info(f"  {result.improved_query}")
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)


if __name__ == "__main__":
    test_query_enhancement()
