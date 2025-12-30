"""
Task #30: Rate Limiting for Claude API Calls

Implements rate limiting to prevent API abuse and manage costs.
Uses sliding window algorithm for accurate rate limiting.

Features:
- Requests per minute (RPM) limiting
- Tokens per minute (TPM) limiting
- Per-user rate limiting
- Global rate limiting
- Queue mechanism for burst handling
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Deque
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: float = 60.0):
        super().__init__(message)
        self.retry_after = retry_after


class LimitType(str, Enum):
    """Type of rate limit."""
    REQUESTS = "requests"
    TOKENS = "tokens"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60  # RPM limit
    tokens_per_minute: int = 100000  # TPM limit (Claude Sonnet: ~100K TPM)
    burst_multiplier: float = 1.5  # Allow burst up to 1.5x normal rate
    queue_timeout: float = 30.0  # Max wait time in queue (seconds)
    per_user_rpm: int = 20  # Per-user RPM limit
    per_user_tpm: int = 50000  # Per-user TPM limit


@dataclass
class RateLimitStatus:
    """Current rate limit status."""
    requests_remaining: int
    tokens_remaining: int
    reset_at: float  # Unix timestamp
    is_limited: bool
    retry_after: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "requests_remaining": self.requests_remaining,
            "tokens_remaining": self.tokens_remaining,
            "reset_at": self.reset_at,
            "is_limited": self.is_limited,
            "retry_after": self.retry_after,
        }


class SlidingWindowCounter:
    """
    Sliding window rate limiter.
    
    Uses a deque to track timestamps of requests within the window.
    More accurate than fixed window counters.
    """
    
    def __init__(self, limit: int, window_seconds: float = 60.0):
        """
        Initialize sliding window counter.
        
        Args:
            limit: Maximum count within window
            window_seconds: Window duration in seconds
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self.timestamps: Deque[float] = deque()
        self.values: Deque[int] = deque()  # For token counting
        self._lock = threading.Lock()
    
    def _cleanup(self, now: float) -> None:
        """Remove expired entries."""
        cutoff = now - self.window_seconds
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
            if self.values:
                self.values.popleft()
    
    def try_acquire(self, count: int = 1) -> bool:
        """
        Try to acquire capacity.
        
        Args:
            count: Amount to acquire (1 for requests, token count for tokens)
            
        Returns:
            True if acquired, False if limit exceeded
        """
        now = time.time()
        
        with self._lock:
            self._cleanup(now)
            
            current_total = sum(self.values) if self.values else len(self.timestamps)
            
            if current_total + count > self.limit:
                return False
            
            self.timestamps.append(now)
            self.values.append(count)
            return True
    
    def get_remaining(self) -> int:
        """Get remaining capacity."""
        now = time.time()
        
        with self._lock:
            self._cleanup(now)
            current_total = sum(self.values) if self.values else len(self.timestamps)
            return max(0, self.limit - current_total)
    
    def get_reset_time(self) -> float:
        """Get time when oldest entry expires."""
        with self._lock:
            if self.timestamps:
                return self.timestamps[0] + self.window_seconds
            return time.time()
    
    def reset(self) -> None:
        """Reset the counter."""
        with self._lock:
            self.timestamps.clear()
            self.values.clear()


class RateLimiter:
    """
    Rate limiter for Claude API calls.
    
    Supports both global and per-user rate limiting.
    Uses sliding window algorithm for accuracy.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        
        # Global limiters
        self._global_rpm = SlidingWindowCounter(
            limit=self.config.requests_per_minute,
            window_seconds=60.0
        )
        self._global_tpm = SlidingWindowCounter(
            limit=self.config.tokens_per_minute,
            window_seconds=60.0
        )
        
        # Per-user limiters
        self._user_rpm: Dict[str, SlidingWindowCounter] = {}
        self._user_tpm: Dict[str, SlidingWindowCounter] = {}
        self._user_lock = threading.Lock()
        
        # Queue for burst handling
        self._queue: Deque[threading.Event] = deque()
        self._queue_lock = threading.Lock()
        
        logger.info(f"Initialized RateLimiter: RPM={self.config.requests_per_minute}, TPM={self.config.tokens_per_minute}")
    
    def _get_user_limiter(
        self,
        user_id: str,
        limiter_type: LimitType
    ) -> SlidingWindowCounter:
        """Get or create per-user limiter."""
        with self._user_lock:
            if limiter_type == LimitType.REQUESTS:
                if user_id not in self._user_rpm:
                    self._user_rpm[user_id] = SlidingWindowCounter(
                        limit=self.config.per_user_rpm,
                        window_seconds=60.0
                    )
                return self._user_rpm[user_id]
            else:
                if user_id not in self._user_tpm:
                    self._user_tpm[user_id] = SlidingWindowCounter(
                        limit=self.config.per_user_tpm,
                        window_seconds=60.0
                    )
                return self._user_tpm[user_id]
    
    def check_rate_limit(
        self,
        user_id: str = "anonymous",
        estimated_tokens: int = 0
    ) -> RateLimitStatus:
        """
        Check current rate limit status without consuming.
        
        Args:
            user_id: User identifier
            estimated_tokens: Estimated tokens for the request
            
        Returns:
            RateLimitStatus with current limits
        """
        # Check global limits
        global_rpm_remaining = self._global_rpm.get_remaining()
        global_tpm_remaining = self._global_tpm.get_remaining()
        
        # Check user limits
        user_rpm = self._get_user_limiter(user_id, LimitType.REQUESTS)
        user_tpm = self._get_user_limiter(user_id, LimitType.TOKENS)
        user_rpm_remaining = user_rpm.get_remaining()
        user_tpm_remaining = user_tpm.get_remaining()
        
        # Use minimum of global and user limits
        requests_remaining = min(global_rpm_remaining, user_rpm_remaining)
        tokens_remaining = min(global_tpm_remaining, user_tpm_remaining)
        
        # Check if limited
        is_limited = requests_remaining <= 0 or (
            estimated_tokens > 0 and tokens_remaining < estimated_tokens
        )
        
        # Calculate retry_after
        retry_after = 0.0
        if is_limited:
            reset_times = [
                self._global_rpm.get_reset_time(),
                self._global_tpm.get_reset_time(),
                user_rpm.get_reset_time(),
                user_tpm.get_reset_time(),
            ]
            retry_after = max(0, min(reset_times) - time.time())
        
        return RateLimitStatus(
            requests_remaining=requests_remaining,
            tokens_remaining=tokens_remaining,
            reset_at=time.time() + 60.0,
            is_limited=is_limited,
            retry_after=retry_after,
        )
    
    def acquire(
        self,
        user_id: str = "anonymous",
        estimated_tokens: int = 1000,
        wait: bool = False
    ) -> bool:
        """
        Acquire rate limit capacity.
        
        Args:
            user_id: User identifier
            estimated_tokens: Estimated tokens for request
            wait: Whether to wait in queue if limited
            
        Returns:
            True if acquired, False if rejected
            
        Raises:
            RateLimitExceeded: If limit exceeded and wait=False
        """
        # Check status first
        status = self.check_rate_limit(user_id, estimated_tokens)
        
        if status.is_limited:
            if not wait:
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Retry after {status.retry_after:.1f}s",
                    retry_after=status.retry_after
                )
            
            # Wait in queue
            if not self._wait_in_queue(status.retry_after):
                raise RateLimitExceeded(
                    "Queue timeout exceeded",
                    retry_after=status.retry_after
                )
        
        # Try to acquire global limits
        if not self._global_rpm.try_acquire(1):
            raise RateLimitExceeded("Global RPM limit exceeded", retry_after=60.0)
        
        if estimated_tokens > 0:
            if not self._global_tpm.try_acquire(estimated_tokens):
                raise RateLimitExceeded("Global TPM limit exceeded", retry_after=60.0)
        
        # Try to acquire user limits
        user_rpm = self._get_user_limiter(user_id, LimitType.REQUESTS)
        user_tpm = self._get_user_limiter(user_id, LimitType.TOKENS)
        
        user_rpm.try_acquire(1)
        if estimated_tokens > 0:
            user_tpm.try_acquire(estimated_tokens)
        
        return True
    
    def _wait_in_queue(self, max_wait: float) -> bool:
        """Wait in queue for capacity."""
        wait_time = min(max_wait, self.config.queue_timeout)
        event = threading.Event()
        
        with self._queue_lock:
            self._queue.append(event)
        
        try:
            # Wait for signal or timeout
            result = event.wait(timeout=wait_time)
            return result
        finally:
            with self._queue_lock:
                if event in self._queue:
                    self._queue.remove(event)
    
    def release_queue(self) -> None:
        """Signal next item in queue."""
        with self._queue_lock:
            if self._queue:
                event = self._queue.popleft()
                event.set()
    
    def record_usage(
        self,
        user_id: str,
        actual_tokens: int
    ) -> None:
        """
        Record actual token usage after request completes.
        
        This can be used to adjust estimates for future requests.
        
        Args:
            user_id: User identifier
            actual_tokens: Actual tokens used
        """
        # For now, just log the usage
        # Could be extended to track usage patterns
        logger.debug(f"User {user_id} used {actual_tokens} tokens")
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "global_rpm_remaining": self._global_rpm.get_remaining(),
            "global_tpm_remaining": self._global_tpm.get_remaining(),
            "config": {
                "requests_per_minute": self.config.requests_per_minute,
                "tokens_per_minute": self.config.tokens_per_minute,
                "per_user_rpm": self.config.per_user_rpm,
                "per_user_tpm": self.config.per_user_tpm,
            },
            "queue_size": len(self._queue),
        }
    
    def reset(self, user_id: Optional[str] = None) -> None:
        """
        Reset rate limits.
        
        Args:
            user_id: Reset specific user, or all if None
        """
        if user_id:
            with self._user_lock:
                if user_id in self._user_rpm:
                    self._user_rpm[user_id].reset()
                if user_id in self._user_tpm:
                    self._user_tpm[user_id].reset()
        else:
            self._global_rpm.reset()
            self._global_tpm.reset()
            with self._user_lock:
                self._user_rpm.clear()
                self._user_tpm.clear()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def configure_rate_limiter(config: RateLimitConfig) -> RateLimiter:
    """Configure and return rate limiter."""
    global _rate_limiter
    _rate_limiter = RateLimiter(config)
    return _rate_limiter
