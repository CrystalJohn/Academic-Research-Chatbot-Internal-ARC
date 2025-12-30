"""
Claude Service with Converse API and Tool Use (Function Calling)

Enables Claude to intelligently decide:
- When to search documents
- What query to use
- Which filters to apply (doc_ids, pages, tables)
- How to combine multiple searches

Benefits over simple RAG:
- Better query understanding and reformulation
- Multi-step reasoning (search → analyze → search again)
- Adaptive filtering based on user intent
- More natural conversation flow
"""

import json
import logging
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .bedrock_retry import (
    RetryConfig,
    RetryableBedrockClient,
    BedrockError,
    with_retry,
)

logger = logging.getLogger(__name__)


class ToolName(str, Enum):
    """Available tools for Claude."""
    SEARCH_DOCUMENTS = "search_documents"
    LIST_DOCUMENTS = "list_available_documents"
    GET_DOCUMENT_INFO = "get_document_info"


@dataclass
class ToolDefinition:
    """Tool definition for Claude."""
    name: str
    description: str
    input_schema: Dict[str, Any]


# Tool definitions
TOOLS = [
    ToolDefinition(
        name=ToolName.SEARCH_DOCUMENTS,
        description="""Search through uploaded documents using semantic search.
        
Use this tool when user asks questions about document content.
The search will find relevant text chunks and return them with citations.

Tips:
- Use specific, focused queries for better results
- Include key terms and concepts from the user's question
- You can search multiple times with different queries
- Results include doc_id, page number, and relevance score""",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - be specific and include key terms"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 20)",
                    "default": 5
                },
                "doc_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: Filter by specific document IDs"
                },
                "page_min": {
                    "type": "integer",
                    "description": "Optional: Minimum page number to search"
                },
                "page_max": {
                    "type": "integer",
                    "description": "Optional: Maximum page number to search"
                },
                "include_tables": {
                    "type": "boolean",
                    "description": "Whether to include table content (default: true)",
                    "default": True
                }
            },
            "required": ["query"]
        }
    ),
    
    ToolDefinition(
        name=ToolName.LIST_DOCUMENTS,
        description="""List all available documents that can be searched.
        
Use this when:
- User asks "what documents do you have?"
- User wants to know available sources
- You need to see document IDs for filtering

Returns: List of documents with id, filename, page_count, status""",
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["UPLOADED", "IDP_RUNNING", "EMBEDDING_DONE", "FAILED"],
                    "description": "Filter by document status (default: EMBEDDING_DONE)"
                }
            }
        }
    ),
    
    ToolDefinition(
        name=ToolName.GET_DOCUMENT_INFO,
        description="""Get detailed information about a specific document.
        
Use this when:
- User asks about a specific document
- You need metadata (page count, upload date, etc.)

Returns: Document metadata including filename, pages, chunks, upload date""",
        input_schema={
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "Document ID to get info for"
                }
            },
            "required": ["doc_id"]
        }
    ),
]


@dataclass
class ConverseMessage:
    """Message in Converse API format."""
    role: str  # "user" or "assistant"
    content: List[Dict[str, Any]]  # Can be text or tool_use/tool_result


@dataclass
class TokenUsage:
    """Token usage statistics."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


class ClaudeConverseService:
    """
    Claude service using Converse API with Tool Use.
    
    Features:
    - Tool calling (function calling) for intelligent search
    - Multi-turn tool execution loop
    - Automatic tool result handling
    - Streaming support
    """
    
    # Model configurations
    MODELS = {
        "sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "haiku": "anthropic.claude-3-5-haiku-20241022-v1:0",
    }
    
    def __init__(
        self,
        model: str = "sonnet",
        region_name: str = "ap-southeast-1",
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize Claude Converse service.
        
        Args:
            model: Model tier ("sonnet" or "haiku")
            region_name: AWS region
            retry_config: Retry configuration
        """
        self.model_id = self.MODELS.get(model, self.MODELS["sonnet"])
        self.region_name = region_name
        self.retry_config = retry_config or RetryConfig()
        
        # Create Bedrock client with retry
        config = Config(
            region_name=region_name,
            retries={"max_attempts": 0},  # We handle retries ourselves
            read_timeout=300,
            connect_timeout=60,
        )
        
        base_client = boto3.client("bedrock-runtime", config=config)
        self.client = RetryableBedrockClient(
            client=base_client,
            retry_config=self.retry_config,
        )
        
        logger.info(f"Initialized ClaudeConverseService with model: {self.model_id}")
    
    def switch_model(self, model: str) -> None:
        """Switch to different model tier."""
        if model in self.MODELS:
            self.model_id = self.MODELS[model]
            logger.info(f"Switched to model: {self.model_id}")
        else:
            raise ValueError(f"Unknown model: {model}. Use 'sonnet' or 'haiku'")
    
    def converse(
        self,
        messages: List[ConverseMessage],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: Optional[List[ToolDefinition]] = None,
    ) -> Dict[str, Any]:
        """
        Call Converse API.
        
        Args:
            messages: Conversation messages
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            tools: Available tools for Claude
            
        Returns:
            Converse API response
        """
        # Build request
        request = {
            "modelId": self.model_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in messages
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            }
        }
        
        if system:
            request["system"] = [{"text": system}]
        
        if tools:
            request["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": {"json": tool.input_schema}
                        }
                    }
                    for tool in tools
                ]
            }
        
        # Call API with retry
        try:
            response = self.client.converse(**request)
            return response
        except ClientError as e:
            logger.error(f"Converse API error: {e}")
            raise
    
    def extract_text_response(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract text from Converse response."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        
        for block in content:
            if "text" in block:
                return block["text"]
        
        return None
    
    def extract_tool_use(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool use requests from Converse response."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        
        tool_uses = []
        for block in content:
            if "toolUse" in block:
                tool_uses.append(block["toolUse"])
        
        return tool_uses
    
    def get_usage(self, response: Dict[str, Any]) -> TokenUsage:
        """Extract token usage from response."""
        usage = response.get("usage", {})
        return TokenUsage(
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
        )


def create_converse_service(
    model: str = "sonnet",
    region_name: str = "ap-southeast-1",
) -> ClaudeConverseService:
    """Factory function to create Claude Converse service."""
    return ClaudeConverseService(
        model=model,
        region_name=region_name,
    )
