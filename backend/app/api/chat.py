"""
Task #28: POST /api/chat endpoint
Task #29: Chat history storage in DynamoDB
Task #30: Rate limiting for Claude API calls
Task #31: Fallback to Claude Haiku on budget limit

Chat API for RAG-based question answering with citations.
Includes conversation history storage and retrieval for context.
Includes rate limiting to prevent API abuse.
Includes automatic model fallback based on budget.
"""

import logging
import os
import uuid
import time
import json
from hashlib import sha256
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.search.rag_service import RAGService, PromptTemplate, RAGResponse, is_greeting, GREETING_RESPONSES
from app.services.search.qdrant_client import SearchFilter
from app.services.chat.chat_history_manager import (
    ChatHistoryManager,
    CachedChatHistoryManager,
    ChatMessage,
    MessageRole,
    create_chat_history_manager,
)
from app.services.common.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    get_rate_limiter,
)
from app.services.common.budget_manager import get_budget_manager
from app.services.auth.auth_service import (
    CurrentUser,
    get_current_user,
    get_current_user_optional,
)
from app.services.ai.query_enhancement_service import (
    get_query_enhancement_service,
    QueryAnalysis,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# Custom Exceptions for better error handling
class ChatError(Exception):
    """Base exception for chat errors."""
    pass


class ContextRetrievalError(ChatError):
    """Failed to retrieve contexts from vector store."""
    pass


class LLMGenerationError(ChatError):
    """LLM generation failed."""
    pass


class HistoryError(ChatError):
    """Failed to access chat history."""
    pass


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request payload."""
    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for history")
    user_id: Optional[str] = Field("anonymous", description="User ID for history tracking")
    doc_ids: Optional[List[str]] = Field(None, description="Filter by specific documents")
    template: Optional[str] = Field("default", description="Prompt template: default, academic, concise, detailed")
    top_k: Optional[int] = Field(3, ge=1, le=10, description="Number of context chunks (max 3 for best quality)")
    stream: Optional[bool] = Field(False, description="Enable streaming response")
    include_history: Optional[bool] = Field(True, description="Include conversation history in context")
    language: Optional[str] = Field("auto", description="Response language: 'vi', 'en', or 'auto' for automatic detection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the main data structures discussed?",
                "conversation_id": None,
                "user_id": "anonymous",
                "doc_ids": None,
                "template": "default",
                "top_k": 5,
                "stream": False,
                "include_history": True
            }
        }


class CitationResponse(BaseModel):
    """Citation in response."""
    id: int
    doc_id: str
    page: int
    text_snippet: str
    score: float
    filename: str = ""  # Original filename for display


class UsageResponse(BaseModel):
    """Token usage in response."""
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    """Chat response payload."""
    answer: str
    citations: List[CitationResponse]
    conversation_id: str
    usage: UsageResponse
    model: str
    contexts_used: int
    query: str
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Based on [1], the main data structures are...",
                "citations": [
                    {"id": 1, "doc_id": "doc-123", "page": 5, "text_snippet": "Arrays are...", "score": 0.85}
                ],
                "conversation_id": "conv-abc123",
                "usage": {"input_tokens": 500, "output_tokens": 200, "total_tokens": 700},
                "model": "sonnet",
                "contexts_used": 3,
                "query": "What are the main data structures?",
                "timestamp": "2025-12-04T10:30:00Z"
            }
        }


# Global service instances (lazy initialization)
_rag_service: Optional[RAGService] = None
_chat_history_manager: Optional[ChatHistoryManager] = None
_response_cache: Optional["ResponseCache"] = None


class ResponseCache:
    """
    Cache for identical RAG queries to avoid redundant LLM calls.
    
    Benefits:
    - Save tokens and cost (no duplicate Claude calls)
    - Reduce latency for repeated queries
    - TTL-based expiration (default 1 hour)
    
    Cache key is based on: query + doc_ids + top_k
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 500):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, tuple] = {}  # key -> (response_dict, timestamp)
        logger.info(f"ResponseCache initialized: TTL={ttl_seconds}s, max_size={max_size}")
    
    def _generate_key(self, query: str, doc_ids: Optional[List[str]], top_k: int) -> str:
        """Generate cache key from query parameters."""
        cache_input = {
            "query": query.lower().strip(),
            "doc_ids": sorted(doc_ids) if doc_ids else [],
            "top_k": top_k,
        }
        return sha256(json.dumps(cache_input, sort_keys=True).encode()).hexdigest()[:16]
    
    def get(self, query: str, doc_ids: Optional[List[str]], top_k: int) -> Optional[Dict]:
        """Get cached response if valid."""
        key = self._generate_key(query, doc_ids, top_k)
        
        if key not in self._cache:
            return None
        
        response, timestamp = self._cache[key]
        age = time.time() - timestamp
        
        if age > self.ttl_seconds:
            del self._cache[key]
            logger.debug(f"Response cache EXPIRED: {key}")
            return None
        
        logger.info(f"Response cache HIT: {key} (age={age:.0f}s)")
        return response
    
    def set(self, query: str, doc_ids: Optional[List[str]], top_k: int, response: Dict) -> None:
        """Cache response."""
        # Evict oldest if full
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        key = self._generate_key(query, doc_ids, top_k)
        self._cache[key] = (response, time.time())
        logger.debug(f"Response cache SET: {key}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = time.time()
        valid = sum(1 for _, (_, ts) in self._cache.items() if now - ts < self.ttl_seconds)
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid,
            "ttl_seconds": self.ttl_seconds,
            "max_size": self.max_size,
        }


def get_response_cache() -> ResponseCache:
    """Get or create ResponseCache instance."""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache(
            ttl_seconds=3600,  # 1 hour
            max_size=500,
        )
    return _response_cache


def get_rag_service() -> RAGService:
    """Get or create RAG service instance."""
    global _rag_service
    if _rag_service is None:
        # Use environment variable to configure model, default to sonnet for better quality
        model = os.getenv("CLAUDE_MODEL", "sonnet")  # Claude 3.5 Sonnet for better responses
        _rag_service = RAGService(
            qdrant_host="localhost",
            qdrant_port=6333,
            region_name="ap-southeast-1",
            model=model,
            use_hybrid=False,  # Disabled - BM25 init issue, vector-only works well
            # TODO: Fix BM25 initialization before enabling hybrid
            # bm25_weight=0.3,
            # vector_weight=0.7,
        )
    return _rag_service


def get_chat_history_manager() -> ChatHistoryManager:
    """
    Get or create ChatHistoryManager instance with caching.
    
    Uses CachedChatHistoryManager to reduce DynamoDB queries.
    Cache TTL: 5 minutes, auto-invalidated on write.
    """
    global _chat_history_manager
    if _chat_history_manager is None:
        _chat_history_manager = create_chat_history_manager(
            use_cache=True,  # ✅ Enable caching to reduce N+1 queries
            cache_ttl_seconds=300,  # 5 minutes
        )
    return _chat_history_manager


def _convert_rag_response(
    rag_response: RAGResponse,
    conversation_id: str,
) -> ChatResponse:
    """Convert RAGResponse to ChatResponse."""
    return ChatResponse(
        answer=rag_response.answer,
        citations=[
            CitationResponse(
                id=c.id,
                doc_id=c.doc_id,
                page=c.page,
                text_snippet=c.text_snippet,
                score=c.score,
                filename=getattr(c, 'filename', ''),
            )
            for c in rag_response.citations
        ],
        conversation_id=conversation_id,
        usage=UsageResponse(
            input_tokens=rag_response.usage.input_tokens,
            output_tokens=rag_response.usage.output_tokens,
            total_tokens=rag_response.usage.total_tokens,
        ),
        model=rag_response.model,
        contexts_used=rag_response.contexts_used,
        query=rag_response.query,
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),  # ✅ Require authentication
):
    """
    Send a chat message and get RAG-based response with citations.
    
    REQUIRES: Authentication (valid Cognito token)
    
    The endpoint retrieves relevant document chunks from the vector database,
    builds a prompt with context, and generates an answer using Claude.
    Conversation history is stored in DynamoDB and used for context.
    Rate limiting is applied per user and globally.
    
    - **query**: The user's question (required)
    - **conversation_id**: Optional ID to continue a conversation
    - **doc_ids**: Optional list of document IDs to search within
    - **template**: Prompt template style (default, academic, concise, detailed)
    - **top_k**: Number of context chunks to retrieve (1-20)
    - **include_history**: Include conversation history in context (default: true)
    """
    try:
        rag_service = get_rag_service()
        history_manager = get_chat_history_manager()
        rate_limiter = get_rate_limiter()
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
        # Use authenticated user ID instead of request parameter
        user_id = current_user.user_id or current_user.email or "anonymous"
        
        # Estimate tokens for rate limiting (~4 chars per token)
        estimated_tokens = len(request.query) // 4 + 2000  # query + context + response
        
        # Check and acquire rate limit
        try:
            rate_limiter.acquire(
                user_id=user_id,
                estimated_tokens=estimated_tokens,
                wait=False
            )
        except RateLimitExceeded as e:
            # Add rate limit headers
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["Retry-After"] = str(int(e.retry_after))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. {str(e)}",
                headers={"Retry-After": str(int(e.retry_after))}
            )
        
        # Add rate limit headers
        status = rate_limiter.check_rate_limit(user_id)
        response.headers["X-RateLimit-Remaining"] = str(status.requests_remaining)
        response.headers["X-RateLimit-Reset"] = str(int(status.reset_at))
        
        # Set template if specified
        if request.template:
            try:
                template = PromptTemplate(request.template)
                rag_service.set_template(template)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid template: {request.template}. Use: default, academic, concise, detailed"
                )
        
        # Build search filter
        search_filter = None
        if request.doc_ids:
            search_filter = SearchFilter(doc_ids=request.doc_ids)
        
        # Check response cache (only for queries without history context)
        # Queries with history are unique per conversation, so not cached
        response_cache = get_response_cache()
        use_cache = not request.include_history or not request.conversation_id
        
        if use_cache:
            cached_response = response_cache.get(
                query=request.query,
                doc_ids=request.doc_ids,
                top_k=request.top_k or 3,
            )
            if cached_response:
                # Return cached response with new conversation_id
                cached_response["conversation_id"] = conversation_id
                cached_response["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                return ChatResponse(**cached_response)
        
        # Get conversation history for context
        history = None
        if request.include_history and request.conversation_id:
            try:
                history = history_manager.get_history_for_context(
                    conversation_id=conversation_id,
                    max_messages=10,
                )
                logger.debug(f"Loaded {len(history)} messages from history")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
                history = None
        
        # Save user message to history
        try:
            history_manager.save_user_message(
                conversation_id=conversation_id,
                content=request.query,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")
        
        # Determine language preference
        language_pref = None
        if request.language and request.language != "auto":
            language_pref = request.language
        
        # Execute RAG query with history and language preference
        rag_response = rag_service.query(
            query=request.query,
            top_k=request.top_k or 3,
            search_filter=search_filter,
            history=history,
            stream=False,
            language_preference=language_pref,
        )
        
        # Save assistant response to history
        try:
            history_manager.save_assistant_message(
                conversation_id=conversation_id,
                content=rag_response.answer,
                user_id=user_id,
                citations=[c.__dict__ if hasattr(c, '__dict__') else c for c in rag_response.citations] if rag_response.citations else None,
                usage=rag_response.usage.to_dict() if rag_response.usage else None,
                model=rag_response.model,
            )
        except Exception as e:
            logger.warning(f"Failed to save assistant message: {e}")
        
        # Record actual token usage for rate limiter
        if rag_response.usage:
            rate_limiter.record_usage(user_id, rag_response.usage.total_tokens)
        
        # Convert to response
        chat_response = _convert_rag_response(rag_response, conversation_id)
        
        # Cache response for identical future queries (only if no history used)
        if use_cache:
            response_cache.set(
                query=request.query,
                doc_ids=request.doc_ids,
                top_k=request.top_k or 3,
                response=chat_response.model_dump(),
            )
        
        return chat_response
        
    except HTTPException:
        raise
    except ContextRetrievalError as e:
        logger.error(f"Context retrieval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve relevant information. Please try again later."
        )
    except LLMGenerationError as e:
        logger.error(f"LLM generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to generate response. Please try again later."
        )
    except ChatError as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request. Please try again."
        )
    except Exception as e:
        # Log full error but don't expose internal details to client
        logger.error(f"Unexpected chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please contact support if this persists."
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),  # ✅ Require authentication
):
    """
    Send a chat message and get streaming RAG-based response.
    
    REQUIRES: Authentication (valid Cognito token)
    
    Returns Server-Sent Events (SSE) stream with text chunks.
    Includes rate limiting, history saving, and proper error handling.
    """
    # Get services
    rag_service = get_rag_service()
    history_manager = get_chat_history_manager()
    rate_limiter = get_rate_limiter()
    
    # Get user info
    user_id = current_user.user_id or current_user.email or "anonymous"
    conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    
    # ✅ Rate limiting (same as main endpoint)
    estimated_tokens = len(request.query) // 4 + 2000
    try:
        rate_limiter.acquire(
            user_id=user_id,
            estimated_tokens=estimated_tokens,
            wait=False
        )
    except RateLimitExceeded as e:
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["Retry-After"] = str(int(e.retry_after))
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. {str(e)}",
            headers={"Retry-After": str(int(e.retry_after))}
        )
    
    # Add rate limit headers
    status = rate_limiter.check_rate_limit(user_id)
    response.headers["X-RateLimit-Remaining"] = str(status.requests_remaining)
    
    try:
        # Set template
        if request.template:
            try:
                template = PromptTemplate(request.template)
                rag_service.set_template(template)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid template: {request.template}")
        
        # Build search filter
        search_filter = None
        if request.doc_ids:
            search_filter = SearchFilter(doc_ids=request.doc_ids)
        
        # ✅ Get conversation history (same as main endpoint)
        history = None
        if request.include_history and request.conversation_id:
            try:
                history = history_manager.get_history_for_context(
                    conversation_id=conversation_id,
                    max_messages=10,
                )
            except Exception as e:
                logger.warning(f"Failed to load history for stream: {e}")
        
        # ✅ Save user message to history
        try:
            history_manager.save_user_message(
                conversation_id=conversation_id,
                content=request.query,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")
        
        # ✅ Check for greeting - respond friendly without RAG search
        greeting_detected, greeting_lang = is_greeting(request.query)
        if greeting_detected:
            logger.info(f"Greeting detected in stream (lang={greeting_lang}): {request.query}")
            greeting_response = GREETING_RESPONSES.get(greeting_lang, GREETING_RESPONSES["en"])
            
            async def greeting_stream():
                import json
                # Encode newlines for SSE
                encoded_text = greeting_response.replace('\n', '\\n')
                yield f"data: {encoded_text}\n\n"
                yield f"data: [CITATIONS]{json.dumps([])}\n\n"  # Empty citations
                yield f"data: [CONV_ID]{conversation_id}\n\n"
                yield "data: [DONE]\n\n"
                
                # Save greeting response to history
                try:
                    history_manager.save_assistant_message(
                        conversation_id=conversation_id,
                        content=greeting_response,
                        user_id=user_id,
                        citations=[],
                    )
                except Exception as e:
                    logger.warning(f"Failed to save greeting response: {e}")
            
            return StreamingResponse(
                greeting_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Conversation-ID": conversation_id,
                }
            )
        
        # Retrieve contexts
        try:
            contexts = rag_service.retrieve_contexts(
                query=request.query,
                top_k=request.top_k or 5,
                search_filter=search_filter,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve contexts: {e}")
            raise HTTPException(status_code=503, detail=f"Search service unavailable: {str(e)[:50]}")
        
        # Build citations directly from contexts
        logger.info(f"Retrieved {len(contexts)} contexts for citations")
        
        # Get filenames for doc_ids
        from app.services.document.document_status_manager import DocumentStatusManager
        status_manager = DocumentStatusManager()
        filename_map = {}
        doc_ids = list(set(ctx.doc_id for ctx in contexts))
        for doc_id in doc_ids:
            try:
                doc = status_manager.get_document(doc_id)
                if doc:
                    filename_map[doc_id] = doc.get("filename", "")
            except Exception:
                pass
        
        citations_data = []
        for i, ctx in enumerate(contexts, 1):
            # Score is already 0-100 percentage from Qdrant, don't multiply
            score = ctx.score if ctx.score <= 100 else ctx.score / 100
            citations_data.append({
                "id": i,
                "doc_id": ctx.doc_id,
                "page": ctx.page,
                "text_snippet": ctx.text[:200] + "..." if len(ctx.text) > 200 else ctx.text,
                "score": round(score, 1),
                "filename": filename_map.get(ctx.doc_id, ""),
            })
        logger.info(f"Built {len(citations_data)} citations from contexts")
        
        # Generate streaming response with history saving
        async def generate():
            import json
            full_answer = ""
            sent_done = False
            try:
                for chunk in rag_service.generate_answer_stream(
                    query=request.query,
                    contexts=contexts,
                    history=history,
                ):
                    if chunk.text:
                        full_answer += chunk.text
                        # Encode newlines to preserve them in SSE
                        encoded_text = chunk.text.replace('\n', '\\n')
                        yield f"data: {encoded_text}\n\n"
                    if chunk.is_final:
                        # Send citations as JSON before [DONE]
                        logger.info(f"Stream complete, sending {len(citations_data)} citations")
                        yield f"data: [CITATIONS]{json.dumps(citations_data)}\n\n"
                        yield f"data: [CONV_ID]{conversation_id}\n\n"
                        yield "data: [DONE]\n\n"
                        sent_done = True
                
                # Fallback: send citations if not sent yet
                if not sent_done:
                    logger.info(f"Fallback: sending {len(citations_data)} citations after loop")
                    yield f"data: [CITATIONS]{json.dumps(citations_data)}\n\n"
                    yield f"data: [CONV_ID]{conversation_id}\n\n"
                    yield "data: [DONE]\n\n"
                
                # ✅ Save assistant message after streaming completes
                if full_answer:
                    try:
                        history_manager.save_assistant_message(
                            conversation_id=conversation_id,
                            content=full_answer,
                            user_id=user_id,
                            citations=citations_data,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save assistant message: {e}")
                        
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                yield f"data: [ERROR] An error occurred generating the response.\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Conversation-ID": conversation_id,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream chat error: {e}", exc_info=True)
        # Check if it's a throttling error
        error_msg = str(e).lower()
        if "throttl" in error_msg or "too many" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Service is busy. Please wait a moment and try again."
            )
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)[:100]}"
        )


@router.get("/health")
async def chat_health():
    """Check health of chat service components."""
    try:
        rag_service = get_rag_service()
        health = rag_service.health_check()
        
        all_healthy = all(health.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "components": health,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@router.get("/document/{doc_id}")
async def get_document_info(
    doc_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get document info for citation display.
    
    REQUIRES: Authentication (any logged-in user)
    
    This endpoint allows regular users to view document metadata
    for citations without requiring admin access.
    """
    from app.services.document.document_status_manager import DocumentStatusManager
    
    try:
        status_manager = DocumentStatusManager()
        doc = status_manager.get_document(doc_id)
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {doc_id} not found"
            )
        
        return {
            "doc_id": doc.get("doc_id", ""),
            "filename": doc.get("filename", ""),
            "status": doc.get("status", ""),
            "uploaded_at": doc.get("uploaded_at", ""),
            "page_count": doc.get("page_count"),
            "chunk_count": doc.get("chunk_count"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate-limit")
async def get_rate_limit_status(
    user_id: str = Query("anonymous", description="User ID to check"),
):
    """
    Get current rate limit status for a user.
    
    Returns remaining requests/tokens and reset time.
    """
    try:
        rate_limiter = get_rate_limiter()
        status = rate_limiter.check_rate_limit(user_id)
        stats = rate_limiter.get_stats()
        
        return {
            "user_id": user_id,
            "status": status.to_dict(),
            "global_stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get rate limit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget")
async def get_budget_status(
    user_id: str = Query("anonymous", description="User ID to check"),
):
    """
    Get current budget status and model recommendation.
    
    Returns spending info and whether Haiku fallback is active.
    """
    try:
        budget_manager = get_budget_manager()
        status = budget_manager.get_status(user_id)
        user_spending = budget_manager.get_user_spending(user_id)
        stats = budget_manager.get_stats()
        
        return {
            "user_id": user_id,
            "status": status.to_dict(),
            "user_spending": user_spending,
            "global_stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get budget status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Chat History Endpoints ==============

class ConversationListResponse(BaseModel):
    """Response for listing conversations."""
    conversations: List[Dict[str, Any]]
    has_more: bool


class ConversationHistoryResponse(BaseModel):
    """Response for conversation history."""
    conversation_id: str
    messages: List[Dict[str, Any]]
    total: int


@router.get("/history", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100, description="Max conversations to return"),
    current_user: CurrentUser = Depends(get_current_user),  # ✅ Require authentication
):
    """
    List conversations for the authenticated user.
    
    REQUIRES: Authentication (valid Cognito token)
    Returns only conversations belonging to the current user.
    """
    try:
        history_manager = get_chat_history_manager()
        user_id = current_user.user_id or current_user.email or "anonymous"
        
        result = history_manager.list_conversations(
            user_id=user_id,
            limit=limit,
        )
        
        return ConversationListResponse(
            conversations=result["conversations"],
            has_more=result.get("last_evaluated_key") is not None,
        )
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max messages to return"),
    current_user: CurrentUser = Depends(get_current_user),  # ✅ Require authentication
):
    """
    Get messages for a specific conversation.
    
    REQUIRES: Authentication (valid Cognito token)
    Only the owner of the conversation can view it.
    Returns messages in chronological order (oldest first).
    """
    try:
        history_manager = get_chat_history_manager()
        user_id = current_user.user_id or current_user.email or "anonymous"
        
        # ✅ Verify ownership: Check if conversation belongs to current user
        conversations = history_manager.list_conversations(user_id=user_id, limit=100)
        conversation_ids = [c.get("conversation_id") for c in conversations.get("conversations", [])]
        
        if conversation_id not in conversation_ids:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to view this conversation."
            )
        
        messages = history_manager.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit,
            ascending=True,
        )
        
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=[msg.to_dict() for msg in messages],
            total=len(messages),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),  # ✅ Require authentication
):
    """
    Delete a conversation and all its messages.
    
    REQUIRES: Authentication (valid Cognito token)
    Only the owner of the conversation can delete it.
    """
    try:
        history_manager = get_chat_history_manager()
        user_id = current_user.user_id or current_user.email or "anonymous"
        
        # ✅ Verify ownership: Check if conversation belongs to current user
        conversations = history_manager.list_conversations(user_id=user_id, limit=100)
        conversation_ids = [c.get("conversation_id") for c in conversations.get("conversations", [])]
        
        if conversation_id not in conversation_ids:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this conversation. You can only delete your own conversations."
            )
        
        deleted = history_manager.delete_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )
        
        return {
            "conversation_id": conversation_id,
            "deleted_messages": deleted,
            "status": "deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============== Query Enhancement Endpoint ==============

class QueryEnhancementRequest(BaseModel):
    """Request for query enhancement."""
    query: str = Field(..., min_length=1, max_length=2000, description="User query to analyze")


class QuerySuggestionResponse(BaseModel):
    """Suggestion for query improvement."""
    category: str
    suggestion: str
    improved_query: str


class QueryEnhancementResponse(BaseModel):
    """Response with query analysis and suggestions."""
    original_query: str
    quality_score: float
    is_good_quality: bool
    suggestions: List[QuerySuggestionResponse]
    improved_query: Optional[str]


@router.post("/enhance-query", response_model=QueryEnhancementResponse)
async def enhance_query(
    request: QueryEnhancementRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Đánh giá chất lượng câu hỏi và đề xuất cải thiện.
    
    REQUIRES: Authentication (valid Cognito token)
    
    Phân tích câu hỏi theo các tiêu chí:
    - Specificity: Tính cụ thể
    - Comparative approach: Yếu tố so sánh
    - Impact assessment: Đánh giá tác động
    - Context: Ngữ cảnh
    - Scope: Phạm vi
    
    Trả về:
    - quality_score: Điểm chất lượng (0-1)
    - is_good_quality: True nếu không cần cải thiện
    - suggestions: Danh sách gợi ý cải thiện
    - improved_query: Câu hỏi đã cải thiện tổng hợp
    """
    try:
        enhancement_service = get_query_enhancement_service()
        
        # Phân tích query
        analysis = enhancement_service.analyze_query(request.query)
        
        # Convert to response
        return QueryEnhancementResponse(
            original_query=analysis.original_query,
            quality_score=analysis.quality_score,
            is_good_quality=analysis.is_good_quality,
            suggestions=[
                QuerySuggestionResponse(
                    category=s.category,
                    suggestion=s.suggestion,
                    improved_query=s.improved_query
                )
                for s in analysis.suggestions
            ],
            improved_query=analysis.improved_query
        )
        
    except Exception as e:
        logger.error(f"Failed to enhance query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Unable to analyze query. Please try again."
        )
