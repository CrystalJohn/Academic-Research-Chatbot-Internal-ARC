"""
Task #32: Error Handling & Retry Logic for Bedrock

Provides robust error handling and retry mechanisms for AWS Bedrock API calls.
Features:
- Custom exceptions for different error types
- Exponential backoff with jitter
- Error classification (retryable vs non-retryable)
- Graceful error messages for users
"""

import time
import random
import logging
import functools
from typing import Optional, Callable, Any, Type, Tuple
from dataclasses import dataclass
from enum import Enum

from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)


class BedrockErrorType(Enum):
    """Classification of Bedrock errors."""
    THROTTLING = "throttling"
    SERVICE_UNAVAILABLE = "service_unavailable"
    MODEL_ERROR = "model_error"
    VALIDATION = "validation"
    ACCESS_DENIED = "access_denied"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# Error codes that are retryable
RETRYABLE_ERROR_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelStreamErrorException",
    "ModelTimeoutException",
    "ServiceException",
    "RequestTimeout",
    "ProvisionedThroughputExceededException",
}

# Error codes that should NOT be retried
NON_RETRYABLE_ERROR_CODES = {
    "ValidationException",
    "AccessDeniedException",
    "ResourceNotFoundException",
    "ModelNotReadyException",
    "ModelErrorException",
}


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 5
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return delay


class BedrockError(Exception):
    """Base exception for Bedrock errors."""
    
    def __init__(
        self,
        message: str,
        error_type: BedrockErrorType = BedrockErrorType.UNKNOWN,
        error_code: Optional[str] = None,
        retryable: bool = False,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.error_code = error_code
        self.retryable = retryable
        self.original_error = original_error
    
    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "error_type": self.error_type.value,
            "error_code": self.error_code,
            "retryable": self.retryable,
        }
    
    @property
    def user_message(self) -> str:
        """Get user-friendly error message."""
        return ERROR_MESSAGES.get(self.error_type, self.message)


class BedrockThrottlingError(BedrockError):
    """Raised when API is throttled."""
    
    def __init__(self, message: str = "API rate limit exceeded", **kwargs):
        super().__init__(
            message=message,
            error_type=BedrockErrorType.THROTTLING,
            retryable=True,
            **kwargs
        )


class BedrockServiceError(BedrockError):
    """Raised when Bedrock service is unavailable."""
    
    def __init__(self, message: str = "Service temporarily unavailable", **kwargs):
        super().__init__(
            message=message,
            error_type=BedrockErrorType.SERVICE_UNAVAILABLE,
            retryable=True,
            **kwargs
        )


class BedrockModelError(BedrockError):
    """Raised when model returns an error."""
    
    def __init__(self, message: str = "Model processing error", **kwargs):
        super().__init__(
            message=message,
            error_type=BedrockErrorType.MODEL_ERROR,
            retryable=False,
            **kwargs
        )


class BedrockValidationError(BedrockError):
    """Raised for validation errors (bad input)."""
    
    def __init__(self, message: str = "Invalid request", **kwargs):
        super().__init__(
            message=message,
            error_type=BedrockErrorType.VALIDATION,
            retryable=False,
            **kwargs
        )


class BedrockAccessError(BedrockError):
    """Raised for access/permission errors."""
    
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message=message,
            error_type=BedrockErrorType.ACCESS_DENIED,
            retryable=False,
            **kwargs
        )


class BedrockTimeoutError(BedrockError):
    """Raised when request times out."""
    
    def __init__(self, message: str = "Request timed out", **kwargs):
        super().__init__(
            message=message,
            error_type=BedrockErrorType.TIMEOUT,
            retryable=True,
            **kwargs
        )


# User-friendly error messages
ERROR_MESSAGES = {
    BedrockErrorType.THROTTLING: (
        "The AI service is currently busy. Please wait a moment and try again."
    ),
    BedrockErrorType.SERVICE_UNAVAILABLE: (
        "The AI service is temporarily unavailable. Please try again in a few minutes."
    ),
    BedrockErrorType.MODEL_ERROR: (
        "There was an issue processing your request. Please try rephrasing your question."
    ),
    BedrockErrorType.VALIDATION: (
        "Your request couldn't be processed. Please check your input and try again."
    ),
    BedrockErrorType.ACCESS_DENIED: (
        "Access to the AI service is not available. Please contact support."
    ),
    BedrockErrorType.TIMEOUT: (
        "The request took too long to process. Please try a shorter question."
    ),
    BedrockErrorType.UNKNOWN: (
        "An unexpected error occurred. Please try again later."
    ),
}


def classify_error(error: Exception) -> Tuple[BedrockErrorType, bool, str]:
    """
    Classify an exception into error type, retryability, and error code.
    
    Args:
        error: The exception to classify
        
    Returns:
        Tuple of (error_type, is_retryable, error_code)
    """
    error_code = "Unknown"
    
    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "Unknown")
        error_message = error.response.get("Error", {}).get("Message", str(error))
        
        # Check for throttling
        if error_code in {"ThrottlingException", "ProvisionedThroughputExceededException"}:
            return BedrockErrorType.THROTTLING, True, error_code
        
        # Check for service errors
        if error_code in {"ServiceUnavailableException", "InternalServerException", "ServiceException"}:
            return BedrockErrorType.SERVICE_UNAVAILABLE, True, error_code
        
        # Check for timeout
        if error_code in {"ModelTimeoutException", "RequestTimeout"}:
            return BedrockErrorType.TIMEOUT, True, error_code
        
        # Check for model errors
        if error_code in {"ModelErrorException", "ModelStreamErrorException"}:
            return BedrockErrorType.MODEL_ERROR, error_code == "ModelStreamErrorException", error_code
        
        # Check for validation errors
        if error_code == "ValidationException":
            return BedrockErrorType.VALIDATION, False, error_code
        
        # Check for access errors
        if error_code in {"AccessDeniedException", "ResourceNotFoundException"}:
            return BedrockErrorType.ACCESS_DENIED, False, error_code
        
        # Check if it's in retryable set
        if error_code in RETRYABLE_ERROR_CODES:
            return BedrockErrorType.SERVICE_UNAVAILABLE, True, error_code
    
    elif isinstance(error, BotoCoreError):
        error_code = type(error).__name__
        # Most BotoCoreErrors are connection issues, which are retryable
        return BedrockErrorType.SERVICE_UNAVAILABLE, True, error_code
    
    elif isinstance(error, TimeoutError):
        return BedrockErrorType.TIMEOUT, True, "TimeoutError"
    
    # Unknown error
    return BedrockErrorType.UNKNOWN, False, error_code


def create_bedrock_error(error: Exception) -> BedrockError:
    """
    Create appropriate BedrockError subclass from an exception.
    
    Args:
        error: The original exception
        
    Returns:
        Appropriate BedrockError subclass
    """
    error_type, retryable, error_code = classify_error(error)
    
    # Get original message
    if isinstance(error, ClientError):
        message = error.response.get("Error", {}).get("Message", str(error))
    else:
        message = str(error)
    
    # Create appropriate error class
    error_classes = {
        BedrockErrorType.THROTTLING: BedrockThrottlingError,
        BedrockErrorType.SERVICE_UNAVAILABLE: BedrockServiceError,
        BedrockErrorType.MODEL_ERROR: BedrockModelError,
        BedrockErrorType.VALIDATION: BedrockValidationError,
        BedrockErrorType.ACCESS_DENIED: BedrockAccessError,
        BedrockErrorType.TIMEOUT: BedrockTimeoutError,
    }
    
    error_class = error_classes.get(error_type, BedrockError)
    
    return error_class(
        message=message,
        error_code=error_code,
        original_error=error,
    )


def with_retry(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    Decorator for adding retry logic to Bedrock API calls.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        on_retry: Optional callback called before each retry
                  Signature: (attempt, error, delay) -> None
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @with_retry(max_retries=3, base_delay=1.0)
        def call_bedrock():
            return client.invoke_model(...)
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except (ClientError, BotoCoreError, TimeoutError) as e:
                    last_error = e
                    error_type, retryable, error_code = classify_error(e)
                    
                    # Log the error
                    logger.warning(
                        f"Bedrock API error (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{error_code} - {str(e)[:200]}"
                    )
                    
                    # Don't retry non-retryable errors
                    if not retryable:
                        logger.error(f"Non-retryable error, giving up: {error_code}")
                        raise create_bedrock_error(e)
                    
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded")
                        raise create_bedrock_error(e)
                    
                    # Calculate delay
                    delay = config.get_delay(attempt)
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt, e, delay)
                    
                    logger.info(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    
                except Exception as e:
                    # Unexpected error, wrap and raise
                    logger.error(f"Unexpected error in Bedrock call: {type(e).__name__}: {e}")
                    raise create_bedrock_error(e)
            
            # Should not reach here, but just in case
            if last_error:
                raise create_bedrock_error(last_error)
        
        return wrapper
    
    return decorator


class RetryableBedrockClient:
    """
    Wrapper for Bedrock client with built-in retry logic.
    
    Provides invoke_model and invoke_model_with_response_stream
    methods with automatic retry on transient errors.
    """
    
    def __init__(
        self,
        client,
        retry_config: Optional[RetryConfig] = None,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    ):
        """
        Initialize retryable client.
        
        Args:
            client: boto3 bedrock-runtime client
            retry_config: Optional retry configuration
            on_retry: Optional callback for retry events
        """
        self.client = client
        self.config = retry_config or RetryConfig()
        self.on_retry = on_retry
    
    def invoke_model(self, **kwargs) -> dict:
        """
        Invoke model with retry logic.
        
        Args:
            **kwargs: Arguments to pass to invoke_model
            
        Returns:
            Response from invoke_model
            
        Raises:
            BedrockError: On non-retryable or exhausted retries
        """
        @with_retry(
            max_retries=self.config.max_retries,
            base_delay=self.config.base_delay,
            max_delay=self.config.max_delay,
            exponential_base=self.config.exponential_base,
            jitter=self.config.jitter,
            on_retry=self.on_retry,
        )
        def _invoke():
            return self.client.invoke_model(**kwargs)
        
        return _invoke()
    
    def invoke_model_with_response_stream(self, **kwargs) -> dict:
        """
        Invoke model with streaming and retry logic.
        
        Note: Retry only applies to initial connection.
        Stream errors during iteration are not retried.
        
        Args:
            **kwargs: Arguments to pass to invoke_model_with_response_stream
            
        Returns:
            Response with streaming body
            
        Raises:
            BedrockError: On non-retryable or exhausted retries
        """
        @with_retry(
            max_retries=self.config.max_retries,
            base_delay=self.config.base_delay,
            max_delay=self.config.max_delay,
            exponential_base=self.config.exponential_base,
            jitter=self.config.jitter,
            on_retry=self.on_retry,
        )
        def _invoke():
            return self.client.invoke_model_with_response_stream(**kwargs)
        
        return _invoke()
    
    def converse(self, **kwargs) -> dict:
        """
        Call Converse API with retry logic.
        
        Args:
            **kwargs: Arguments to pass to converse
            
        Returns:
            Response from converse API
            
        Raises:
            BedrockError: On non-retryable or exhausted retries
        """
        @with_retry(
            max_retries=self.config.max_retries,
            base_delay=self.config.base_delay,
            max_delay=self.config.max_delay,
            exponential_base=self.config.exponential_base,
            jitter=self.config.jitter,
            on_retry=self.on_retry,
        )
        def _invoke():
            return self.client.converse(**kwargs)
        
        return _invoke()


# Convenience function for creating retry decorator with logging
def bedrock_retry(
    max_retries: int = 5,
    base_delay: float = 1.0,
    operation_name: str = "Bedrock API",
):
    """
    Create retry decorator with logging for Bedrock operations.
    
    Args:
        max_retries: Maximum retry attempts
        base_delay: Initial delay between retries
        operation_name: Name for logging purposes
        
    Returns:
        Configured retry decorator
    """
    def log_retry(attempt: int, error: Exception, delay: float):
        logger.warning(
            f"{operation_name} retry {attempt + 1}/{max_retries}: "
            f"waiting {delay:.1f}s after {type(error).__name__}"
        )
    
    return with_retry(
        max_retries=max_retries,
        base_delay=base_delay,
        on_retry=log_retry,
    )
