"""
RAGAs Evaluation Module for RAG Pipeline

Đánh giá chất lượng RAG pipeline sử dụng RAGAs metrics:
- Faithfulness: Câu trả lời có trung thực với context không?
- Answer Relevancy: Câu trả lời có liên quan đến câu hỏi không?
- Context Precision: Context retrieve có chính xác không?
- Context Recall: Context có đầy đủ thông tin không? (cần ground_truth)

Usage:
    from app.services.ragas_evaluator import RAGEvaluator
    
    evaluator = RAGEvaluator()
    
    # Đánh giá single query
    result = evaluator.evaluate_single(
        question="OOP là gì?",
        answer="OOP là lập trình hướng đối tượng [1]",
        contexts=["OOP (Object-Oriented Programming) là..."],
        ground_truth="OOP là paradigm lập trình..."  # optional
    )
    
    # Đánh giá batch
    results = evaluator.evaluate_batch(test_dataset)
    
    # Tích hợp với RAG service
    results = evaluator.evaluate_rag_service(rag_service, test_questions)
"""

import logging
import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Kết quả đánh giá một query."""
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None
    
    # RAGAs metrics (0-1 scale)
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    answer_correctness: Optional[float] = None
    
    # Metadata
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def average_score(self) -> float:
        """Tính điểm trung bình của các metrics có giá trị."""
        scores = [
            self.faithfulness,
            self.answer_relevancy,
            self.context_precision,
            self.context_recall,
        ]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0


@dataclass
class BatchEvaluationResult:
    """Kết quả đánh giá batch."""
    results: List[EvaluationResult]
    
    # Aggregate metrics
    avg_faithfulness: float = 0.0
    avg_answer_relevancy: float = 0.0
    avg_context_precision: float = 0.0
    avg_context_recall: float = 0.0
    
    total_questions: int = 0
    successful_evaluations: int = 0
    failed_evaluations: int = 0
    
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_questions": self.total_questions,
                "successful": self.successful_evaluations,
                "failed": self.failed_evaluations,
                "avg_faithfulness": round(self.avg_faithfulness, 4),
                "avg_answer_relevancy": round(self.avg_answer_relevancy, 4),
                "avg_context_precision": round(self.avg_context_precision, 4),
                "avg_context_recall": round(self.avg_context_recall, 4),
            },
            "results": [r.to_dict() for r in self.results],
            "evaluated_at": self.evaluated_at,
        }
    
    def save_to_file(self, filepath: str) -> None:
        """Lưu kết quả ra file JSON."""
        import math
        
        def clean_nan(obj):
            """Replace NaN with None for JSON serialization."""
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return None
            return obj
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(clean_nan(self.to_dict()), f, ensure_ascii=False, indent=2)
        logger.info(f"Saved evaluation results to {filepath}")


class RAGEvaluator:
    """
    RAGAs-based evaluator cho RAG pipeline.
    
    Sử dụng AWS Bedrock Claude làm LLM cho RAGAs evaluation.
    """
    
    def __init__(
        self,
        region_name: str = "ap-southeast-1",
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
    ):
        """
        Initialize evaluator.
        
        Args:
            region_name: AWS region cho Bedrock
            model_id: Model ID cho evaluation (recommend Haiku để tiết kiệm cost)
        """
        self.region_name = region_name
        self.model_id = model_id
        self._ragas_initialized = False
        self._llm = None
        self._embeddings = None
        
    def _init_ragas(self) -> bool:
        """Lazy initialization của RAGAs với Bedrock."""
        if self._ragas_initialized:
            return True
            
        try:
            # Import RAGAs
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            
            # Import Bedrock LLM wrapper cho RAGAs
            from langchain_aws import ChatBedrock
            from langchain_aws import BedrockEmbeddings
            
            # Initialize Bedrock LLM
            self._llm = ChatBedrock(
                model_id=self.model_id,
                region_name=self.region_name,
                model_kwargs={"temperature": 0.0},
            )
            
            # Initialize Bedrock Embeddings (dùng Titan)
            self._embeddings = BedrockEmbeddings(
                model_id="amazon.titan-embed-text-v2:0",
                region_name=self.region_name,
            )
            
            self._ragas_initialized = True
            logger.info(f"RAGAs initialized with Bedrock model: {self.model_id}")
            return True
            
        except ImportError as e:
            logger.error(
                f"Missing dependencies for RAGAs: {e}\n"
                "Install with: pip install ragas langchain-aws datasets"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize RAGAs: {e}")
            return False
    
    def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Đánh giá một query đơn lẻ.
        
        Args:
            question: Câu hỏi
            answer: Câu trả lời từ RAG
            contexts: List các context đã retrieve
            ground_truth: Câu trả lời đúng (optional)
            
        Returns:
            EvaluationResult với các metrics
        """
        result = EvaluationResult(
            question=question,
            answer=answer,
            contexts=contexts,
            ground_truth=ground_truth,
        )
        
        if not self._init_ragas():
            result.error = "Failed to initialize RAGAs"
            return result
        
        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
            )
            from datasets import Dataset
            
            # Prepare data
            data = {
                "question": [question],
                "answer": [answer],
                "contexts": [contexts],
            }
            
            # Select metrics based on ground_truth availability
            metrics = [faithfulness, answer_relevancy, context_precision]
            if ground_truth:
                data["ground_truth"] = [ground_truth]
                metrics.append(context_recall)
            
            dataset = Dataset.from_dict(data)
            
            # Run evaluation
            eval_result = evaluate(
                dataset,
                metrics=metrics,
                llm=self._llm,
                embeddings=self._embeddings,
            )
            
            # Extract scores
            result.faithfulness = eval_result.get("faithfulness", None)
            result.answer_relevancy = eval_result.get("answer_relevancy", None)
            result.context_precision = eval_result.get("context_precision", None)
            if ground_truth:
                result.context_recall = eval_result.get("context_recall", None)
            
            logger.info(
                f"Evaluation complete: faithfulness={result.faithfulness:.2f}, "
                f"relevancy={result.answer_relevancy:.2f}"
            )
            
        except Exception as e:
            result.error = str(e)
            logger.error(f"Evaluation failed: {e}")
        
        return result
    
    def evaluate_batch(
        self,
        questions: List[str],
        answers: List[str],
        contexts: List[List[str]],
        ground_truths: Optional[List[str]] = None,
    ) -> BatchEvaluationResult:
        """
        Đánh giá batch nhiều queries.
        
        Args:
            questions: List câu hỏi
            answers: List câu trả lời
            contexts: List[List[str]] - contexts cho mỗi câu hỏi
            ground_truths: List câu trả lời đúng (optional)
            
        Returns:
            BatchEvaluationResult với aggregate metrics
        """
        if not self._init_ragas():
            return BatchEvaluationResult(
                results=[],
                total_questions=len(questions),
                failed_evaluations=len(questions),
            )
        
        results = []
        
        try:
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
            )
            from datasets import Dataset
            
            # RAGAs v0.1+ uses 'reference' instead of 'ground_truth'
            # and 'user_input' instead of 'question' for some metrics
            # context_precision requires 'reference' column
            
            # Prepare data with RAGAs v0.1+ column names
            data = {
                "user_input": questions,  # RAGAs v0.1+ naming
                "response": answers,      # RAGAs v0.1+ naming  
                "retrieved_contexts": contexts,  # RAGAs v0.1+ naming
            }
            
            # Only use metrics that don't require ground_truth by default
            # faithfulness and answer_relevancy work without reference
            metrics = [faithfulness, answer_relevancy]
            
            if ground_truths:
                data["reference"] = ground_truths  # RAGAs v0.1+ uses 'reference'
                # Add context_precision and context_recall only when we have reference
                from ragas.metrics import context_precision, context_recall
                metrics.extend([context_precision, context_recall])
            
            dataset = Dataset.from_dict(data)
            
            # Run batch evaluation
            logger.info(f"Starting batch evaluation of {len(questions)} questions...")
            logger.info(f"Metrics: {[m.name for m in metrics]}")
            
            eval_result = evaluate(
                dataset,
                metrics=metrics,
                llm=self._llm,
                embeddings=self._embeddings,
            )
            
            # Convert to DataFrame for easier processing
            df = eval_result.to_pandas()
            
            # Create individual results
            for idx in range(len(questions)):
                row = df.iloc[idx]
                result = EvaluationResult(
                    question=questions[idx],
                    answer=answers[idx],
                    contexts=contexts[idx],
                    ground_truth=ground_truths[idx] if ground_truths else None,
                    faithfulness=row.get("faithfulness") if "faithfulness" in row else None,
                    answer_relevancy=row.get("answer_relevancy") if "answer_relevancy" in row else None,
                    context_precision=row.get("context_precision") if "context_precision" in row else None,
                    context_recall=row.get("context_recall") if "context_recall" in row else None,
                )
                results.append(result)
            
            # Calculate aggregates
            batch_result = BatchEvaluationResult(
                results=results,
                total_questions=len(questions),
                successful_evaluations=len(results),
                avg_faithfulness=df["faithfulness"].mean() if "faithfulness" in df.columns else 0,
                avg_answer_relevancy=df["answer_relevancy"].mean() if "answer_relevancy" in df.columns else 0,
                avg_context_precision=df["context_precision"].mean() if "context_precision" in df.columns else 0,
                avg_context_recall=df["context_recall"].mean() if "context_recall" in df.columns else 0,
            )
            
            logger.info(
                f"Batch evaluation complete: "
                f"faithfulness={batch_result.avg_faithfulness:.2f}, "
                f"relevancy={batch_result.avg_answer_relevancy:.2f}"
            )
            
            return batch_result
            
        except Exception as e:
            logger.error(f"Batch evaluation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return BatchEvaluationResult(
                results=results,
                total_questions=len(questions),
                successful_evaluations=len(results),
                failed_evaluations=len(questions) - len(results),
            )
    
    def evaluate_rag_service(
        self,
        rag_service: "RAGService",
        test_questions: List[str],
        ground_truths: Optional[List[str]] = None,
        top_k: int = 3,
        delay_between_questions: float = 2.0,
    ) -> BatchEvaluationResult:
        """
        Đánh giá trực tiếp RAG service với test questions.
        
        Args:
            rag_service: Instance của RAGService
            test_questions: List câu hỏi test
            ground_truths: List câu trả lời đúng (optional)
            top_k: Số contexts để retrieve
            delay_between_questions: Delay (seconds) giữa các câu hỏi để tránh throttling
            
        Returns:
            BatchEvaluationResult
        """
        import time
        
        logger.info(f"Evaluating RAG service with {len(test_questions)} questions...")
        logger.info(f"Using {delay_between_questions}s delay between questions to avoid throttling")
        
        answers = []
        all_contexts = []
        
        for idx, question in enumerate(test_questions):
            try:
                # Add delay between questions to avoid Bedrock throttling
                if idx > 0:
                    logger.info(f"Waiting {delay_between_questions}s before next question...")
                    time.sleep(delay_between_questions)
                
                logger.info(f"Processing question {idx + 1}/{len(test_questions)}: {question[:50]}...")
                
                # Retrieve contexts
                contexts = rag_service.retrieve_contexts(
                    query=question,
                    top_k=top_k,
                )
                
                # Generate answer
                response = rag_service.generate_answer(
                    query=question,
                    contexts=contexts,
                )
                
                answers.append(response.answer)
                all_contexts.append([ctx.text for ctx in contexts])
                
            except Exception as e:
                logger.error(f"Failed to process question '{question[:50]}...': {e}")
                answers.append("")
                all_contexts.append([])
        
        # Add delay before RAGAs evaluation to let rate limit reset
        logger.info("Waiting 5s before RAGAs evaluation...")
        time.sleep(5)
        
        return self.evaluate_batch(
            questions=test_questions,
            answers=answers,
            contexts=all_contexts,
            ground_truths=ground_truths,
        )


def create_test_dataset(
    questions: List[str],
    ground_truths: Optional[List[str]] = None,
    output_path: str = "evaluation/test_dataset.json",
) -> None:
    """
    Tạo test dataset file cho evaluation.
    
    Args:
        questions: List câu hỏi test
        ground_truths: List câu trả lời đúng (optional)
        output_path: Đường dẫn file output
    """
    data = {
        "questions": questions,
        "ground_truths": ground_truths or [],
        "created_at": datetime.now().isoformat(),
    }
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Created test dataset at {output_path}")


def load_test_dataset(filepath: str) -> Dict[str, Any]:
    """Load test dataset từ file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
