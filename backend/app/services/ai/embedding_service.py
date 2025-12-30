"""
Embedding Service using Cohere Embed via AWS Bedrock
Task #32: Error Handling & Retry Logic for Bedrock

Generates embeddings for text chunks using Cohere Embed English v3 model.
Features:
- Exponential backoff retry for transient errors
- Graceful error handling
"""
import json
import logging
import time
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from .bedrock_retry import (
    RetryConfig,
    BedrockError,
    create_bedrock_error,
    classify_error,
    BedrockErrorType,
)
from app.services.common.monitoring_service import track_embedding_metrics

logger = logging.getLogger(__name__)


class CohereEmbeddingService:
    """
    Embedding service using Cohere Embed Multilingual v3 via Bedrock.
    
    Model: cohere.embed-multilingual-v3 (1024 dimensions)
    Supports Vietnamese and 100+ languages.
    
    Features:
    - Automatic retry with exponential backoff
    - Graceful error handling
    
    IMPORTANT: All documents MUST be embedded with the same model.
    If you change the model, you MUST re-process all documents.
    """
    
    MODEL_ID = "cohere.embed-multilingual-v3"  # Supports Vietnamese and 100+ languages
    VECTOR_SIZE = 1024  # Cohere outputs 1024 dimensions
    BATCH_SIZE = 96  # Cohere supports batch processing up to 96 texts
    
    def __init__(
        self,
        region: str = "ap-southeast-1",
        region_name: str = None,  # Alias for backward compatibility
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize Cohere Embedding Service.
        
        Args:
            region: AWS region (preferred parameter)
            region_name: AWS region (alias for compatibility)
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
        """
        # Support both region and region_name parameters
        if region_name is not None:
            region = region_name
        
        """
        Initialize embedding service.
        
        Args:
            region: AWS region for Bedrock
            max_retries: Maximum retry attempts for transient errors
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
        """
        self.bedrock_region = region
        self.region = region
        self.retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
        
        # Configure client with timeouts
        config = Config(
            region_name=region,
            connect_timeout=30,
            read_timeout=60,
            retries={"max_attempts": 2, "mode": "standard"},
        )
        self.client = boto3.client("bedrock-runtime", config=config)
        logger.info(f"Initialized Cohere Embedding Service (Bedrock: {self.bedrock_region}, max_retries: {max_retries})")
    
    def _invoke_with_retry(self, body: str) -> dict:
        """
        Invoke Bedrock with retry logic.
        
        Args:
            body: JSON body for the request
            
        Returns:
            Parsed response dict
            
        Raises:
            BedrockError: On non-retryable or exhausted retries
        """
        last_error = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                response = self.client.invoke_model(
                    modelId=self.MODEL_ID,
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                return json.loads(response["body"].read())
                
            except (ClientError, BotoCoreError) as e:
                last_error = e
                error_type, retryable, error_code = classify_error(e)
                
                logger.warning(
                    f"Embedding API error (attempt {attempt + 1}/{self.retry_config.max_retries + 1}): "
                    f"{error_code} - {str(e)[:200]}"
                )
                
                if not retryable:
                    logger.error(f"Non-retryable error: {error_code}")
                    raise create_bedrock_error(e)
                
                if attempt >= self.retry_config.max_retries:
                    logger.error(f"Max retries ({self.retry_config.max_retries}) exceeded")
                    raise create_bedrock_error(e)
                
                delay = self.retry_config.get_delay(attempt)
                logger.info(f"Retrying embedding in {delay:.2f}s...")
                time.sleep(delay)
        
        if last_error:
            raise create_bedrock_error(last_error)
    
    def embed_text(self, text: str, input_type: str = "search_document") -> Optional[List[float]]:
        """
        Generate embedding for a single text with automatic retry.
        
        Args:
            text: Text to embed
            input_type: "search_document" for indexing, "search_query" for searching
            
        Returns:
            List of floats (1024 dimensions) or None on error
        """
        try:
            # Truncate text if too long (Cohere limit is ~512 tokens)
            if len(text) > 2000:
                text = text[:2000]
            
            body = json.dumps({
                "texts": [text],
                "input_type": input_type
            })
            
            result = self._invoke_with_retry(body)
            embeddings = result.get("embeddings", [])
            
            return embeddings[0] if embeddings else None
            
        except BedrockError as e:
            logger.error(f"Bedrock error generating embedding: {e.error_type.value} - {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            return None
    
    def embed_texts(self, texts: List[str], input_type: str = "search_document") -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts (batch processing) with automatic retry.
        
        Args:
            texts: List of texts to embed
            input_type: "search_document" for indexing, "search_query" for searching
            
        Returns:
            List of embeddings (1024 dimensions each)
        """
        if not texts:
            return []
        
        all_embeddings = []
        start_time = time.time()
        
        # Process in batches of BATCH_SIZE
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i:i + self.BATCH_SIZE]
            batch_num = i // self.BATCH_SIZE + 1
            total_batches = (len(texts) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            
            # Truncate texts if too long
            batch = [t[:2000] if len(t) > 2000 else t for t in batch]
            batch_start = time.time()
            
            try:
                body = json.dumps({
                    "texts": batch,
                    "input_type": input_type
                })
                
                result = self._invoke_with_retry(body)
                embeddings = result.get("embeddings", [])
                all_embeddings.extend(embeddings)
                
                # Track metrics for successful batch
                batch_latency_ms = (time.time() - batch_start) * 1000
                track_embedding_metrics(len(batch), batch_latency_ms, success=True)
                
                logger.debug(f"Embedded batch {batch_num}/{total_batches} ({len(batch)} texts)")
                
            except BedrockError as e:
                logger.error(f"Bedrock error in batch {batch_num}: {e.error_type.value} - {e.message}")
                # Track metrics for failed batch
                batch_latency_ms = (time.time() - batch_start) * 1000
                track_embedding_metrics(len(batch), batch_latency_ms, success=False)
                # Return None for failed batch
                all_embeddings.extend([None] * len(batch))
            except Exception as e:
                logger.error(f"Unexpected error in batch {batch_num}: {e}")
                batch_latency_ms = (time.time() - batch_start) * 1000
                track_embedding_metrics(len(batch), batch_latency_ms, success=False)
                all_embeddings.extend([None] * len(batch))
        
        return all_embeddings


def create_embedding_callback(region: str = "ap-southeast-1"):
    """
    Create embedding callback function for SQS Worker.
    
    Returns:
        Function that takes text and returns embedding vector
    """
    service = CohereEmbeddingService(region=region)
    
    def callback(text: str) -> Optional[List[float]]:
        return service.embed_text(text)
    
    return callback
