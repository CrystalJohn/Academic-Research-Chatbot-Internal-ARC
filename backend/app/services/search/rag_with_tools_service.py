"""
RAG Service with Tool Use (Agentic RAG)

Instead of simple retrieve → generate, Claude can:
1. Analyze user question
2. Decide which tools to use (search, filter, etc.)
3. Execute tools and get results
4. Reason about results and decide next steps
5. Generate final answer with proper citations

This enables:
- Multi-step reasoning
- Adaptive search strategies
- Better query understanding
- More accurate filtering
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.services.ai.claude_converse_service import (
    ClaudeConverseService,
    ConverseMessage,
    ToolDefinition,
    ToolName,
    TOOLS,
)
from app.services.search.qdrant_client import (
    QdrantVectorStore,
    SearchFilter,
    RAGContext,
)
from app.services.ai.embedding_service import CohereEmbeddingService
from app.services.document.document_status_manager import (
    DocumentStatusManager,
    DocumentStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class AgenticRAGResponse:
    """Response from agentic RAG."""
    answer: str
    citations: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]  # Track what tools were used
    reasoning_steps: List[str]  # Track Claude's reasoning
    usage: Dict[str, int]
    model: str


class RAGWithToolsService:
    """
    RAG service with Tool Use for intelligent document search.
    
    Flow:
    1. User asks question
    2. Claude analyzes and decides which tools to use
    3. Execute tools (search, filter, etc.)
    4. Claude processes results and may call more tools
    5. Claude generates final answer with citations
    """
    
    MAX_TOOL_ITERATIONS = 5  # Prevent infinite loops
    
    def __init__(
        self,
        claude_service: ClaudeConverseService,
        vector_store: QdrantVectorStore,
        embedding_service: CohereEmbeddingService,
        document_manager: DocumentStatusManager,
    ):
        """Initialize agentic RAG service."""
        self.claude = claude_service
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.document_manager = document_manager
        
        logger.info("Initialized RAGWithToolsService")
    
    def query(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 4096,
    ) -> AgenticRAGResponse:
        """
        Answer question using agentic RAG with tools.
        
        Args:
            question: User question
            conversation_history: Previous messages
            max_tokens: Max tokens for response
            
        Returns:
            AgenticRAGResponse with answer and metadata
        """
        # Build system prompt
        system_prompt = self._build_system_prompt()
        
        # Build conversation messages
        messages = []
        
        # Add history if provided
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append(ConverseMessage(
                    role=msg["role"],
                    content=[{"text": msg["content"]}]
                ))
        
        # Add current question
        messages.append(ConverseMessage(
            role="user",
            content=[{"text": question}]
        ))
        
        # Tool execution loop
        tool_calls = []
        reasoning_steps = []
        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        
        for iteration in range(self.MAX_TOOL_ITERATIONS):
            logger.info(f"Tool iteration {iteration + 1}/{self.MAX_TOOL_ITERATIONS}")
            
            # Call Claude with tools
            response = self.claude.converse(
                messages=messages,
                system=system_prompt,
                max_tokens=max_tokens,
                tools=TOOLS,
            )
            
            # Track usage
            usage = self.claude.get_usage(response)
            total_usage["input_tokens"] += usage.input_tokens
            total_usage["output_tokens"] += usage.output_tokens
            total_usage["total_tokens"] += usage.total_tokens
            
            # Check stop reason
            stop_reason = response.get("stopReason")
            logger.info(f"Stop reason: {stop_reason}")
            
            if stop_reason == "end_turn":
                # Claude finished, extract answer
                answer = self.claude.extract_text_response(response)
                if answer:
                    # Extract citations from tool results
                    citations = self._extract_citations_from_tool_calls(tool_calls)
                    
                    return AgenticRAGResponse(
                        answer=answer,
                        citations=citations,
                        tool_calls=tool_calls,
                        reasoning_steps=reasoning_steps,
                        usage=total_usage,
                        model=self.claude.model_id,
                    )
            
            elif stop_reason == "tool_use":
                # Claude wants to use tools
                tool_uses = self.claude.extract_tool_use(response)
                logger.info(f"Claude requested {len(tool_uses)} tool(s)")
                
                # Add assistant message with tool requests
                assistant_content = response["output"]["message"]["content"]
                messages.append(ConverseMessage(
                    role="assistant",
                    content=assistant_content
                ))
                
                # Execute tools
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use["name"]
                    tool_input = tool_use["input"]
                    tool_use_id = tool_use["toolUseId"]
                    
                    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
                    reasoning_steps.append(f"Using {tool_name}: {tool_input}")
                    
                    # Execute tool
                    result = self._execute_tool(tool_name, tool_input)
                    
                    # Track tool call
                    tool_calls.append({
                        "name": tool_name,
                        "input": tool_input,
                        "result": result,
                    })
                    
                    # Build tool result for Claude
                    tool_results.append({
                        "toolUseId": tool_use_id,
                        "content": [{"json": result}]
                    })
                
                # Add tool results to conversation
                messages.append(ConverseMessage(
                    role="user",
                    content=[{"toolResult": tr} for tr in tool_results]
                ))
                
                # Continue loop for next iteration
                continue
            
            else:
                # Unexpected stop reason
                logger.warning(f"Unexpected stop reason: {stop_reason}")
                break
        
        # Max iterations reached
        logger.warning(f"Max tool iterations ({self.MAX_TOOL_ITERATIONS}) reached")
        return AgenticRAGResponse(
            answer="Xin lỗi, tôi không thể tìm thấy câu trả lời phù hợp. Vui lòng thử đặt câu hỏi khác.",
            citations=[],
            tool_calls=tool_calls,
            reasoning_steps=reasoning_steps,
            usage=total_usage,
            model=self.claude.model_id,
        )
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for agentic RAG."""
        return """Bạn là ARC Chatbot - trợ lý nghiên cứu tài liệu thông minh.

Nhiệm vụ của bạn:
1. Phân tích câu hỏi của người dùng
2. Quyết định cần tìm kiếm thông tin gì
3. Sử dụng tools để tìm kiếm tài liệu
4. Phân tích kết quả và quyết định có cần tìm kiếm thêm không
5. Tổng hợp thông tin và trả lời với trích dẫn chính xác

Nguyên tắc:
- Luôn trích dẫn nguồn với [1], [2], [3]... khi trả lời
- Nếu không tìm thấy thông tin, hãy nói rõ
- Có thể search nhiều lần với queries khác nhau để tìm đủ thông tin
- Ưu tiên độ chính xác hơn là trả lời dài

Format trích dẫn:
- Sử dụng [1], [2], [3]... trong câu trả lời
- Mỗi số tương ứng với một kết quả search
- Đặt số trích dẫn ngay sau thông tin được trích dẫn

Ví dụ:
"Theo tài liệu, thuật toán Dijkstra có độ phức tạp O(V²) [1]. Tuy nhiên, khi sử dụng heap, độ phức tạp có thể giảm xuống O((V+E)logV) [2]."
"""
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result."""
        try:
            if tool_name == ToolName.SEARCH_DOCUMENTS:
                return self._tool_search_documents(tool_input)
            
            elif tool_name == ToolName.LIST_DOCUMENTS:
                return self._tool_list_documents(tool_input)
            
            elif tool_name == ToolName.GET_DOCUMENT_INFO:
                return self._tool_get_document_info(tool_input)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}
    
    def _tool_search_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search_documents tool."""
        query = params["query"]
        top_k = params.get("top_k", 5)
        doc_ids = params.get("doc_ids")
        page_min = params.get("page_min")
        page_max = params.get("page_max")
        include_tables = params.get("include_tables", True)
        
        # Generate embedding
        embeddings = self.embedding_service.embed_texts([query])
        query_vector = embeddings[0]
        
        # Build filter
        search_filter = SearchFilter(
            doc_ids=doc_ids,
            page_min=page_min,
            page_max=page_max,
            is_table=None if include_tables else False,
        )
        
        # Search
        contexts = self.vector_store.search_for_rag(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=0.3,
            search_filter=search_filter,
        )
        
        # Format results
        results = []
        for ctx in contexts:
            results.append({
                "citation_id": ctx.citation_id,
                "text": ctx.text,
                "doc_id": ctx.doc_id,
                "page": ctx.page,
                "score": ctx.score,
                "is_table": ctx.is_table,
            })
        
        return {
            "query": query,
            "results_count": len(results),
            "results": results,
        }
    
    def _tool_list_documents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute list_documents tool."""
        status = params.get("status", "EMBEDDING_DONE")
        
        # Get documents
        response = self.document_manager.list_documents(
            page=1,
            page_size=50,
            status=status if status else None,
        )
        
        # Format results
        documents = []
        for doc in response["items"]:
            documents.append({
                "doc_id": doc["doc_id"],
                "filename": doc["filename"],
                "page_count": doc.get("page_count", 0),
                "status": doc["status"],
                "uploaded_at": doc["uploaded_at"],
            })
        
        return {
            "total": response["total"],
            "documents": documents,
        }
    
    def _tool_get_document_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute get_document_info tool."""
        doc_id = params["doc_id"]
        
        # Get document
        doc = self.document_manager.get_document(doc_id)
        
        if not doc:
            return {"error": f"Document {doc_id} not found"}
        
        return {
            "doc_id": doc["doc_id"],
            "filename": doc["filename"],
            "page_count": doc.get("page_count", 0),
            "chunk_count": doc.get("chunk_count", 0),
            "status": doc["status"],
            "uploaded_at": doc["uploaded_at"],
        }
    
    def _extract_citations_from_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract citations from tool call results."""
        citations = []
        
        for tool_call in tool_calls:
            if tool_call["name"] == ToolName.SEARCH_DOCUMENTS:
                result = tool_call["result"]
                if "results" in result:
                    for item in result["results"]:
                        citations.append({
                            "citation_id": item["citation_id"],
                            "text": item["text"],
                            "doc_id": item["doc_id"],
                            "page": item["page"],
                            "score": item["score"],
                        })
        
        return citations


def create_rag_with_tools_service(
    model: str = "sonnet",
    region_name: str = "ap-southeast-1",
) -> RAGWithToolsService:
    """Factory function to create agentic RAG service."""
    from app.services.ai.claude_converse_service import create_converse_service
    from app.services.search.qdrant_client import create_qdrant_store
    from app.services.ai.embedding_service import CohereEmbeddingService
    from app.services.document.document_status_manager import DocumentStatusManager
    
    claude = create_converse_service(model=model, region_name=region_name)
    vector_store = create_qdrant_store()
    embedding_service = CohereEmbeddingService(region_name=region_name)
    document_manager = DocumentStatusManager()
    
    return RAGWithToolsService(
        claude_service=claude,
        vector_store=vector_store,
        embedding_service=embedding_service,
        document_manager=document_manager,
    )
