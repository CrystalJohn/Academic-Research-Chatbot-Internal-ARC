"""
CloudWatch Metrics Service for RAG Chatbot

Publishes metrics to CloudWatch for monitoring:
- Query latency and success/failure rates
- Embedding performance
- Search metrics
- Cost tracking
"""

import os
import logging
import time
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class MetricDatum:
    """Single metric data point."""
    name: str
    value: float
    unit: str
    dimensions: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CloudWatchMetrics:
    """
    CloudWatch metrics publisher with batching support.
    
    Features:
    - Automatic batching (CloudWatch limit: 1000 metrics per request)
    - Graceful degradation when CloudWatch unavailable
    - Environment-based enable/disable
    """
    
    BATCH_SIZE = 20  # Publish in batches of 20
    
    def __init__(
        self,
        namespace: str = None,
        region: str = None,
        enabled: bool = None,
    ):
        """
        Initialize CloudWatch metrics.
        
        Args:
            namespace: CloudWatch namespace (default: from env or "ARC-Chatbot")
            region: AWS region (default: from env or "ap-southeast-1")
            enabled: Enable metrics (default: from env CLOUDWATCH_METRICS_ENABLED)
        """
        self.namespace = namespace or os.getenv("CLOUDWATCH_NAMESPACE", "ARC-Chatbot")
        self.region = region or os.getenv("AWS_REGION", "ap-southeast-1")
        
        # Check if enabled
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.getenv("CLOUDWATCH_METRICS_ENABLED", "false").lower() == "true"
        
        self._buffer: List[MetricDatum] = []
        self._client = None
        
        if self.enabled:
            try:
                self._client = boto3.client("cloudwatch", region_name=self.region)
                logger.info(f"CloudWatch metrics enabled (namespace: {self.namespace})")
            except Exception as e:
                logger.warning(f"Failed to initialize CloudWatch client: {e}")
                self.enabled = False
        else:
            logger.info("CloudWatch metrics disabled")
    
    def _publish_batch(self, metrics: List[MetricDatum]) -> bool:
        """Publish a batch of metrics to CloudWatch."""
        if not self.enabled or not self._client or not metrics:
            return False
        
        try:
            metric_data = []
            for m in metrics:
                datum = {
                    "MetricName": m.name,
                    "Value": m.value,
                    "Unit": m.unit,
                    "Timestamp": m.timestamp,
                }
                if m.dimensions:
                    datum["Dimensions"] = [
                        {"Name": k, "Value": str(v)} for k, v in m.dimensions.items()
                    ]
                metric_data.append(datum)
            
            self._client.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            return True
            
        except ClientError as e:
            logger.warning(f"Failed to publish metrics: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error publishing metrics: {e}")
            return False
    
    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: Dict[str, str] = None,
        immediate: bool = False
    ) -> bool:
        """
        Add a metric to the buffer or publish immediately.
        
        Args:
            name: Metric name
            value: Metric value
            unit: CloudWatch unit (Count, Seconds, Milliseconds, etc.)
            dimensions: Optional dimensions dict
            immediate: If True, publish immediately
            
        Returns:
            True if successful
        """
        if not self.enabled:
            return True  # Silently succeed when disabled
        
        metric = MetricDatum(
            name=name,
            value=value,
            unit=unit,
            dimensions=dimensions or {},
        )
        
        if immediate:
            return self._publish_batch([metric])
        
        self._buffer.append(metric)
        
        # Auto-flush when buffer is full
        if len(self._buffer) >= self.BATCH_SIZE:
            return self.flush()
        
        return True
    
    def flush(self) -> bool:
        """Flush all buffered metrics to CloudWatch."""
        if not self._buffer:
            return True
        
        metrics = self._buffer
        self._buffer = []
        
        success = True
        for i in range(0, len(metrics), self.BATCH_SIZE):
            batch = metrics[i:i + self.BATCH_SIZE]
            if not self._publish_batch(batch):
                success = False
        
        return success
    
    def increment(
        self,
        name: str,
        value: float = 1.0,
        dimensions: Dict[str, str] = None
    ) -> bool:
        """Increment a counter metric."""
        return self.put_metric(name, value, "Count", dimensions)
    
    def track_latency(
        self,
        name: str,
        latency_ms: float,
        dimensions: Dict[str, str] = None
    ) -> bool:
        """Track latency in milliseconds."""
        return self.put_metric(name, latency_ms, "Milliseconds", dimensions)
    
    def track_cost(
        self,
        name: str,
        cost_usd: float,
        dimensions: Dict[str, str] = None
    ) -> bool:
        """Track cost in USD."""
        return self.put_metric(name, cost_usd, "None", dimensions)  # USD not a standard unit


# Global singleton instance
_metrics_instance: Optional[CloudWatchMetrics] = None


def get_metrics() -> CloudWatchMetrics:
    """Get or create the global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = CloudWatchMetrics()
    return _metrics_instance


def track_query_metrics(
    user_id: str,
    query_latency_ms: float,
    contexts_used: int,
    model: str,
    cost_usd: float = 0.0,
    success: bool = True,
) -> None:
    """
    Track RAG query metrics.
    
    Args:
        user_id: User identifier
        query_latency_ms: Query latency in milliseconds
        contexts_used: Number of contexts used in response
        model: Model used (sonnet/haiku)
        cost_usd: Estimated cost in USD
        success: Whether query succeeded
    """
    metrics = get_metrics()
    dimensions = {"UserId": user_id, "Model": model}
    
    metrics.track_latency("QueryLatency", query_latency_ms, dimensions)
    metrics.increment("ContextsUsed", contexts_used, dimensions)
    
    if cost_usd > 0:
        metrics.track_cost("QueryCost", cost_usd, dimensions)
    
    if success:
        metrics.increment("QuerySuccess", 1, dimensions)
    else:
        metrics.increment("QueryFailure", 1, dimensions)


def track_embedding_metrics(
    batch_size: int,
    latency_ms: float,
    success: bool = True,
) -> None:
    """
    Track embedding generation metrics.
    
    Args:
        batch_size: Number of texts embedded
        latency_ms: Embedding latency in milliseconds
        success: Whether embedding succeeded
    """
    metrics = get_metrics()
    
    metrics.track_latency("EmbeddingLatency", latency_ms)
    metrics.increment("EmbeddingRequests", batch_size)
    
    if success:
        metrics.increment("EmbeddingSuccess", batch_size)
    else:
        metrics.increment("EmbeddingFailure", batch_size)


def track_search_metrics(
    query_type: str,  # "vector", "bm25", "hybrid"
    latency_ms: float,
    results_count: int,
) -> None:
    """
    Track search metrics.
    
    Args:
        query_type: Type of search (vector, bm25, hybrid)
        latency_ms: Search latency in milliseconds
        results_count: Number of results returned
    """
    metrics = get_metrics()
    dimensions = {"QueryType": query_type}
    
    metrics.track_latency("SearchLatency", latency_ms, dimensions)
    metrics.increment("SearchResults", results_count, dimensions)
    metrics.increment("SearchRequests", 1, dimensions)
