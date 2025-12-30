"""
Agentic Chat API with Tool Use (Bedrock Converse API)

New endpoint: POST /api/chat/agentic

Enables Claude to intelligently:
- Decide when to search documents
- Choose optimal search queries
- Apply smart filters (doc_ids, pages, tables)
- Multi-step reasoning
- Better context understanding
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.search.rag_with_tools_service import (
    RAGWithToolsService,
    AgenticRAGResponse,
    create_rag_with_tools_service,
)
from app.services.chat.chat_history_manager import (
    create_chat_history_manager,
    MessageRole,
)
from app.services.auth.auth_service import (
    CurrentUser,
    get_current_user_optional,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat - Agentic"])


# Request/Response Models
class AgenticChatRequest(BaseModel):
    """Agentic chat request."""
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = Field(None)
    user_id: Optional[str] = Field("anonymous")
    max_tokens: Optional[int] = Field(4096, ge=100, le=8000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Tìm thông tin về thuật toán Dijkstra trong tài liệu",
                "conversation_id": None,
                "user_id": "anonymous",
                "max_tokens": 4096
            }
        }


class AgenticChatResponse(BaseModel):
    """Agentic chat response."""
    answer: str
    citations: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    reasoning_steps: List[str]
    conversation_id: str
    usage: Dict[str, int]
    model: str
    timestamp: str


# Singleton service instance
_rag_service: Optional[RAGWithToolsService] = None


def get_rag_service() -> RAGWithToolsService:
    """Get or create RAG service instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = create_rag_with_tools_service(model="sonnet")
    return _rag_service


@router.post("/agentic", response_model=AgenticChatResponse)
async def chat_agentic(
    request: AgenticChatRequest,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
):
    """
    Agentic chat with Tool Use (Converse API).
    
    Claude can intelligently:
    - Search documents with optimal queries
    - Filter by doc_ids, pages, tables
    - Multi-step reasoning
    - Adaptive search strategies
    
    Benefits over simple RAG:
    - Better query understanding
    - More accurate filtering
    - Multi-turn tool execution
    - Improved citation quality
    """
    try:
        # Get services
        rag_service = get_rag_service()
        history_manager = create_chat_history_manager(use_cache=True)
        
        # Get user ID
        user_id = current_user.username if current_user else request.user_id
        
        # Generate conversation ID if needed
        conversation_id = request.conversation_id
        if not conversation_id:
            import uuid
            conversation_id = f"conv-{uuid.uuid4().hex[:12]}"
        
        # Load conversation history
        conversation_history = []
        if request.conversation_id:
            try:
                history = history_manager.get_history_for_context(
                    conversation_id=request.conversation_id,
                    max_messages=10,
                )
                conversation_history = history
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
        
        # Save user message
        try:
            history_manager.save_user_message(
                conversation_id=conversation_id,
                content=request.query,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(f"Failed to save user message: {e}")
        
        # Execute agentic RAG
        logger.info(f"Agentic RAG query: {request.query}")
        result: AgenticRAGResponse = rag_service.query(
            question=request.query,
            conversation_history=conversation_history,
            max_tokens=request.max_tokens,
        )
        
        # Save assistant message
        try:
            history_manager.save_assistant_message(
                conversation_id=conversation_id,
                content=result.answer,
                user_id=user_id,
                citations=[
                    {
                        "citation_id": c["citation_id"],
                        "doc_id": c["doc_id"],
                        "page": c["page"],
                        "text": c["text"][:200],  # Truncate for storage
                        "score": c["score"],
                    }
                    for c in result.citations
                ],
                usage=result.usage,
                model=result.model,
            )
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")
        
        # Build response
        return AgenticChatResponse(
            answer=result.answer,
            citations=result.citations,
            tool_calls=result.tool_calls,
            reasoning_steps=result.reasoning_steps,
            conversation_id=conversation_id,
            usage=result.usage,
            model=result.model,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    
    except Exception as e:
        logger.error(f"Agentic chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agentic chat failed: {str(e)}"
        )


@router.get("/agentic/health")
async def agentic_health():
    """Health check for agentic chat."""
    try:
        rag_service = get_rag_service()
        return {
            "status": "healthy",
            "model": rag_service.claude.model_id,
            "tools_available": len(rag_service.claude.converse.__code__.co_varnames),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
