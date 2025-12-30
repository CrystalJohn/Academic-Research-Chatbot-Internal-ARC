#!/usr/bin/env python3
"""
RAG Evaluation Script

Chạy đánh giá RAG pipeline với RAGAs metrics.

Usage:
    # Đánh giá với test questions mặc định
    python run_evaluation.py
    
    # Đánh giá với custom test file
    python run_evaluation.py --test-file evaluation/my_tests.json
    
    # Đánh giá với ground truths
    python run_evaluation.py --with-ground-truth
    
    # Lưu kết quả
    python run_evaluation.py --output evaluation/results.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.ragas_evaluator import (
    RAGEvaluator,
    create_test_dataset,
    load_test_dataset,
)
from app.services.rag_service import RAGService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Default test questions (Vietnamese + English)
DEFAULT_TEST_QUESTIONS = [
    # Vietnamese
    "OOP là gì?",
    "Giải thích các nguyên tắc SOLID trong lập trình",
    "Design pattern là gì và có những loại nào?",
    "Sự khác nhau giữa abstract class và interface?",
    
    # English
    "What is machine learning?",
    "Explain the difference between SQL and NoSQL databases",
    "What are microservices?",
    "How does REST API work?",
]

# Optional ground truths (for context_recall metric)
DEFAULT_GROUND_TRUTHS = [
    "OOP (Object-Oriented Programming) là phương pháp lập trình dựa trên khái niệm đối tượng, bao gồm 4 tính chất: đóng gói, kế thừa, đa hình, trừu tượng.",
    "SOLID gồm 5 nguyên tắc: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.",
    "Design pattern là các giải pháp tái sử dụng cho các vấn đề phổ biến trong thiết kế phần mềm. Có 3 loại chính: Creational, Structural, Behavioral.",
    "Abstract class có thể có implementation, interface chỉ định nghĩa contract. Class chỉ kế thừa 1 abstract class nhưng implement nhiều interface.",
    "Machine learning is a subset of AI that enables systems to learn from data and improve without explicit programming.",
    "SQL databases are relational with structured schemas, NoSQL are non-relational with flexible schemas for unstructured data.",
    "Microservices is an architectural style where applications are built as small, independent services that communicate via APIs.",
    "REST API uses HTTP methods (GET, POST, PUT, DELETE) to perform CRUD operations on resources identified by URLs.",
]


def run_evaluation(
    test_file: str = None,
    with_ground_truth: bool = False,
    output_file: str = None,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    delay: float = 2.0,
):
    """
    Chạy evaluation pipeline.
    
    Args:
        test_file: Path to test dataset JSON file
        with_ground_truth: Include ground truths in evaluation
        output_file: Path to save results
        qdrant_host: Qdrant server host
        qdrant_port: Qdrant server port
    """
    # Load test data
    if test_file and Path(test_file).exists():
        logger.info(f"Loading test dataset from {test_file}")
        data = load_test_dataset(test_file)
        questions = data["questions"]
        ground_truths = data.get("ground_truths") if with_ground_truth else None
    else:
        logger.info("Using default test questions")
        questions = DEFAULT_TEST_QUESTIONS
        ground_truths = DEFAULT_GROUND_TRUTHS if with_ground_truth else None
    
    logger.info(f"Evaluating {len(questions)} questions (ground_truth={with_ground_truth})")
    
    # Initialize services
    logger.info("Initializing RAG service...")
    rag_service = RAGService(
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
    )
    
    logger.info("Initializing RAGAs evaluator...")
    evaluator = RAGEvaluator()
    
    # Run evaluation
    logger.info("Starting evaluation...")
    results = evaluator.evaluate_rag_service(
        rag_service=rag_service,
        test_questions=questions,
        ground_truths=ground_truths,
        delay_between_questions=delay,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 RAG EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total questions: {results.total_questions}")
    print(f"Successful: {results.successful_evaluations}")
    print(f"Failed: {results.failed_evaluations}")
    print("-" * 60)
    print(f"📈 Faithfulness:       {results.avg_faithfulness:.2%}")
    print(f"📈 Answer Relevancy:   {results.avg_answer_relevancy:.2%}")
    print(f"📈 Context Precision:  {results.avg_context_precision:.2%}")
    if with_ground_truth:
        print(f"📈 Context Recall:     {results.avg_context_recall:.2%}")
    print("=" * 60)
    
    # Print individual results
    print("\n📋 Individual Results:")
    print("-" * 60)
    for r in results.results:
        print(f"\nQ: {r.question[:60]}...")
        print(f"   Faithfulness: {r.faithfulness:.2%}" if r.faithfulness else "   Faithfulness: N/A")
        print(f"   Relevancy: {r.answer_relevancy:.2%}" if r.answer_relevancy else "   Relevancy: N/A")
        if r.error:
            print(f"   ⚠️ Error: {r.error}")
    
    # Save results
    if output_file:
        results.save_to_file(output_file)
        print(f"\n✅ Results saved to {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="RAG Evaluation with RAGAs")
    parser.add_argument(
        "--test-file",
        type=str,
        help="Path to test dataset JSON file",
    )
    parser.add_argument(
        "--with-ground-truth",
        action="store_true",
        help="Include ground truths for context_recall metric",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation/results.json",
        help="Path to save evaluation results",
    )
    parser.add_argument(
        "--qdrant-host",
        type=str,
        default="localhost",
        help="Qdrant server host",
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=6333,
        help="Qdrant server port",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay (seconds) between questions to avoid Bedrock throttling",
    )
    parser.add_argument(
        "--create-test-file",
        type=str,
        help="Create a sample test dataset file at specified path",
    )
    
    args = parser.parse_args()
    
    # Create test file if requested
    if args.create_test_file:
        create_test_dataset(
            questions=DEFAULT_TEST_QUESTIONS,
            ground_truths=DEFAULT_GROUND_TRUTHS,
            output_path=args.create_test_file,
        )
        print(f"✅ Created test dataset at {args.create_test_file}")
        return
    
    # Run evaluation
    run_evaluation(
        test_file=args.test_file,
        with_ground_truth=args.with_ground_truth,
        output_file=args.output,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
