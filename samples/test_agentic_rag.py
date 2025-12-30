#!/usr/bin/env python3
"""
Test Agentic RAG with Tool Use

Demonstrates Claude's ability to:
- Intelligently search documents
- Apply smart filters
- Multi-step reasoning
- Better query understanding
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.search.rag_with_tools_service import create_rag_with_tools_service


def test_agentic_rag():
    """Test agentic RAG with various queries."""
    
    print("🤖 Testing Agentic RAG with Tool Use")
    print("=" * 60)
    
    # Create service
    print("\n1️⃣  Initializing agentic RAG service...")
    rag_service = create_rag_with_tools_service(model="sonnet")
    print("✅ Service initialized")
    
    # Test queries
    test_queries = [
        {
            "query": "Tìm thông tin về thuật toán Dijkstra",
            "description": "Simple search query"
        },
        {
            "query": "So sánh độ phức tạp của các thuật toán sắp xếp",
            "description": "Multi-step reasoning (search multiple algorithms)"
        },
        {
            "query": "Có bao nhiêu tài liệu đã upload? Liệt kê tên các tài liệu",
            "description": "List documents tool"
        },
        {
            "query": "Tìm các bảng (table) về độ phức tạp thuật toán",
            "description": "Filter by table content"
        },
    ]
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {test['description']}")
        print(f"Query: {test['query']}")
        print(f"{'='*60}")
        
        try:
            result = rag_service.query(
                question=test['query'],
                conversation_history=None,
                max_tokens=2000,
            )
            
            print(f"\n📊 Results:")
            print(f"  - Tool calls: {len(result.tool_calls)}")
            print(f"  - Citations: {len(result.citations)}")
            print(f"  - Tokens: {result.usage['total_tokens']}")
            
            print(f"\n🔧 Tool Calls:")
            for j, tool_call in enumerate(result.tool_calls, 1):
                print(f"  {j}. {tool_call['name']}")
                print(f"     Input: {tool_call['input']}")
                if 'results_count' in tool_call['result']:
                    print(f"     Results: {tool_call['result']['results_count']}")
            
            print(f"\n🧠 Reasoning Steps:")
            for step in result.reasoning_steps:
                print(f"  - {step}")
            
            print(f"\n💬 Answer:")
            print(f"  {result.answer[:300]}...")
            
            if result.citations:
                print(f"\n📚 Citations:")
                for citation in result.citations[:3]:
                    print(f"  [{citation['citation_id']}] {citation['doc_id']} (page {citation['page']}, score: {citation['score']:.3f})")
                    print(f"      {citation['text'][:100]}...")
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("✅ Agentic RAG testing complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    test_agentic_rag()
