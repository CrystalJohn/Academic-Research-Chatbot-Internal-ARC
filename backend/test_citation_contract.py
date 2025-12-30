"""
Test Citation Contract Enforcement

Verify that the model only cites within the provided citation range.
"""

from app.services.search.rag_service import RAGPromptBuilder
from app.services.search.qdrant_client import RAGContext


def test_citation_contract_in_prompt():
    """Test that prompt includes citation contract with JSON list."""
    
    # Create sample contexts
    contexts = [
        RAGContext(
            text="Object-oriented programming is a programming paradigm based on objects.",
            doc_id="doc-123",
            page=5,
            chunk_index=0,
            score=95.5,
            citation_id=1,
        ),
        RAGContext(
            text="Key features include encapsulation, inheritance, and polymorphism.",
            doc_id="doc-123",
            page=6,
            chunk_index=1,
            score=88.2,
            citation_id=2,
        ),
        RAGContext(
            text="Classes are blueprints for creating objects.",
            doc_id="doc-456",
            page=12,
            chunk_index=0,
            score=82.1,
            citation_id=3,
        ),
    ]
    
    # Build prompt
    query = "What is object-oriented programming?"
    prompt = RAGPromptBuilder.build_prompt(query, contexts)
    
    # Verify contract enforcement
    print("=" * 80)
    print("PROMPT WITH CITATION CONTRACT:")
    print("=" * 80)
    print(prompt)
    print("=" * 80)
    
    # Check key elements
    assert "AVAILABLE CITATIONS" in prompt
    assert "[1..3]" in prompt
    assert "CITATION CONTRACT" in prompt
    assert "DO NOT create new citation IDs beyond this range" in prompt
    assert '"id": 1' in prompt
    assert '"id": 2' in prompt
    assert '"id": 3' in prompt
    assert "doc-123" in prompt
    assert "page" in prompt
    
    print("\n✅ Citation contract successfully enforced in prompt!")
    print("   - Citations JSON list: ✓")
    print("   - Citation range [1..3]: ✓")
    print("   - Contract rules: ✓")
    print("   - Document metadata: ✓")


def test_citation_range_with_different_counts():
    """Test citation range with different numbers of contexts."""
    
    test_cases = [
        (1, "[1..1]"),
        (2, "[1..2]"),
        (5, "[1..5]"),
        (10, "[1..10]"),
    ]
    
    for count, expected_range in test_cases:
        contexts = [
            RAGContext(
                text=f"Context {i}",
                doc_id=f"doc-{i}",
                page=i,
                chunk_index=i-1,
                score=100 - i,
                citation_id=i,
            )
            for i in range(1, count + 1)
        ]
        
        prompt = RAGPromptBuilder.build_prompt("test query", contexts)
        assert expected_range in prompt
        print(f"✓ Citation range {expected_range} correctly set for {count} contexts")


def test_empty_contexts():
    """Test prompt with no contexts."""
    prompt = RAGPromptBuilder.build_prompt("test query", [])
    assert "[none]" in prompt
    print("✓ Empty contexts handled correctly with [none]")


if __name__ == "__main__":
    print("\n🧪 Testing Citation Contract Enforcement\n")
    
    test_citation_contract_in_prompt()
    print()
    test_citation_range_with_different_counts()
    print()
    test_empty_contexts()
    
    print("\n✅ All citation contract tests passed!")
