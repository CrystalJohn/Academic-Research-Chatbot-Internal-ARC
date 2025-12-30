"""
Task #29: Chat History Storage in DynamoDB

Manages chat message storage and retrieval for conversation context.
Stores messages with conversation_id, retrieves history for RAG context.

Table schema (arc-chatbot-dev-chat-history):
- user_id (PK): User identifier
- sk (SK): Sort key format "CONV#{conversation_id}#MSG#{timestamp}"
- conversation_id: Conversation identifier (GSI hash key)
- created_at: Message timestamp (GSI range key)
- role: "user" or "assistant"
- content: Message content
- citations: List of citation references (for assistant messages)
- usage: Token usage info (for assistant messages)
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Message role in conversation."""
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """Chat message data structure."""
    conversation_id: str
    role: MessageRole
    content: str
    created_at: str
    user_id: str = "anonymous"
    message_id: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "conversation_id": self.conversation_id,
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "created_at": self.created_at,
            "user_id": self.user_id,
        }
        if self.message_id:
            result["message_id"] = self.message_id
        if self.citations:
            result["citations"] = self.citations
        if self.usage:
            result["usage"] = self.usage
        if self.model:
            result["model"] = self.model
        return result


@dataclass
class Conversation:
    """Conversation metadata."""
    conversation_id: str
    user_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
        }


class ChatHistoryManager:
    """
    Manages chat history storage in DynamoDB.
    
    Supports:
    - Storing user and assistant messages
    - Retrieving conversation history for context
    - Listing user conversations
    - Conversation metadata management
    """
    
    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_client=None,
        region_name: Optional[str] = None,
    ):
        """
        Initialize chat history manager.
        
        Args:
            table_name: DynamoDB table name. Defaults to env var.
            dynamodb_client: Optional boto3 client for testing.
            region_name: AWS region.
        """
        self.table_name = table_name or os.getenv(
            "CHAT_HISTORY_TABLE_NAME",
            "arc-chatbot-dev-chat-history"
        )
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-southeast-1")
        
        if dynamodb_client:
            self._client = dynamodb_client
        else:
            self._client = boto3.client(
                "dynamodb",
                region_name=self.region_name
            )
        
        logger.info(f"Initialized ChatHistoryManager with table: {self.table_name}")

    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        return f"msg-{uuid.uuid4().hex[:12]}"
    
    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def _build_sk(self, conversation_id: str, timestamp: str) -> str:
        """Build sort key for message."""
        return f"CONV#{conversation_id}#MSG#{timestamp}"
    
    def _build_conv_sk(self, conversation_id: str) -> str:
        """Build sort key for conversation metadata."""
        return f"CONV#{conversation_id}#META"

    def save_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        user_id: str = "anonymous",
        citations: Optional[List[Dict[str, Any]]] = None,
        usage: Optional[Dict[str, int]] = None,
        model: Optional[str] = None,
    ) -> ChatMessage:
        """
        Save a chat message to DynamoDB.
        
        Args:
            conversation_id: Conversation identifier
            role: Message role (user/assistant)
            content: Message content
            user_id: User identifier
            citations: Citation references (for assistant)
            usage: Token usage info (for assistant)
            model: Model used (for assistant)
            
        Returns:
            ChatMessage: Saved message object
        """
        timestamp = self._get_timestamp()
        message_id = self._generate_message_id()
        sk = self._build_sk(conversation_id, timestamp)
        
        item = {
            "user_id": {"S": user_id},
            "sk": {"S": sk},
            "conversation_id": {"S": conversation_id},
            "created_at": {"S": timestamp},
            "message_id": {"S": message_id},
            "role": {"S": role.value if isinstance(role, MessageRole) else role},
            "content": {"S": content},
        }
        
        # Add optional fields for assistant messages
        if citations:
            item["citations"] = {"S": self._serialize_json(citations)}
        if usage:
            item["usage"] = {"M": {
                "input_tokens": {"N": str(usage.get("input_tokens", 0))},
                "output_tokens": {"N": str(usage.get("output_tokens", 0))},
                "total_tokens": {"N": str(usage.get("total_tokens", 0))},
            }}
        if model:
            item["model"] = {"S": model}
        
        try:
            self._client.put_item(
                TableName=self.table_name,
                Item=item,
            )
            
            logger.debug(f"Saved message {message_id} to conversation {conversation_id}")
            
            return ChatMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
                created_at=timestamp,
                user_id=user_id,
                message_id=message_id,
                citations=citations,
                usage=usage,
                model=model,
            )
        except ClientError as e:
            logger.error(f"Failed to save message: {e}")
            raise

    def save_user_message(
        self,
        conversation_id: str,
        content: str,
        user_id: str = "anonymous",
    ) -> ChatMessage:
        """Save a user message."""
        return self.save_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            user_id=user_id,
        )

    def save_assistant_message(
        self,
        conversation_id: str,
        content: str,
        user_id: str = "anonymous",
        citations: Optional[List[Dict[str, Any]]] = None,
        usage: Optional[Dict[str, int]] = None,
        model: Optional[str] = None,
    ) -> ChatMessage:
        """Save an assistant message with metadata."""
        return self.save_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            user_id=user_id,
            citations=citations,
            usage=usage,
            model=model,
        )

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 20,
        ascending: bool = True,
    ) -> List[ChatMessage]:
        """
        Get messages for a conversation.
        
        Uses GSI (conversation-index) to query by conversation_id.
        
        Args:
            conversation_id: Conversation identifier
            limit: Maximum messages to return
            ascending: Sort order (True = oldest first)
            
        Returns:
            List of ChatMessage objects
        """
        try:
            response = self._client.query(
                TableName=self.table_name,
                IndexName="conversation-index",
                KeyConditionExpression="conversation_id = :conv_id",
                ExpressionAttributeValues={
                    ":conv_id": {"S": conversation_id}
                },
                Limit=limit,
                ScanIndexForward=ascending,
            )
            
            messages = []
            for item in response.get("Items", []):
                messages.append(self._parse_message(item))
            
            logger.debug(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages
            
        except ClientError as e:
            logger.error(f"Failed to get conversation history: {e}")
            raise

    def get_history_for_context(
        self,
        conversation_id: str,
        max_messages: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for Claude context.
        
        Returns messages in the format expected by Claude's messages API:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        
        Args:
            conversation_id: Conversation identifier
            max_messages: Maximum messages to include
            
        Returns:
            List of message dicts for Claude
        """
        messages = self.get_conversation_history(
            conversation_id=conversation_id,
            limit=max_messages,
            ascending=True,  # Oldest first for context
        )
        
        return [
            {"role": msg.role.value if isinstance(msg.role, MessageRole) else msg.role, 
             "content": msg.content}
            for msg in messages
        ]

    def list_conversations(
        self,
        user_id: str,
        limit: int = 20,
        last_evaluated_key: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        List conversations for a user with title and message count.
        
        Args:
            user_id: User identifier
            limit: Maximum conversations to return
            last_evaluated_key: Pagination token
            
        Returns:
            Dict with conversations and pagination info
        """
        try:
            # Get all messages for user to group by conversation
            params = {
                "TableName": self.table_name,
                "KeyConditionExpression": "user_id = :uid AND begins_with(sk, :prefix)",
                "ExpressionAttributeValues": {
                    ":uid": {"S": user_id},
                    ":prefix": {"S": "CONV#"},
                },
                "ScanIndexForward": False,  # Newest first
            }
            
            if last_evaluated_key:
                params["ExclusiveStartKey"] = last_evaluated_key
            
            response = self._client.query(**params)
            
            # Group messages by conversation_id
            conv_messages: Dict[str, List[ChatMessage]] = {}
            for item in response.get("Items", []):
                conv_id = item.get("conversation_id", {}).get("S")
                if conv_id:
                    msg = self._parse_message(item)
                    if conv_id not in conv_messages:
                        conv_messages[conv_id] = []
                    conv_messages[conv_id].append(msg)
            
            # Build conversation list with title and message_count
            conversations = []
            for conv_id, messages in conv_messages.items():
                # Sort messages by created_at ascending to find first user message
                messages.sort(key=lambda m: m.created_at)
                
                # Find first user message for title
                first_user_msg = next(
                    (m for m in messages if (m.role == MessageRole.USER or m.role == "user")),
                    None
                )
                title = "New conversation"
                if first_user_msg:
                    # Use first 50 chars of first user message as title
                    title = first_user_msg.content[:50]
                    if len(first_user_msg.content) > 50:
                        title += "..."
                
                # Get last message info
                last_msg = messages[-1] if messages else None
                
                conversations.append({
                    "conversation_id": conv_id,
                    "user_id": user_id,
                    "title": title,
                    "message_count": len(messages),
                    "last_message": last_msg.content[:100] + "..." if last_msg and len(last_msg.content) > 100 else (last_msg.content if last_msg else ""),
                    "last_message_at": last_msg.created_at if last_msg else "",
                    "last_role": last_msg.role.value if last_msg and isinstance(last_msg.role, MessageRole) else (last_msg.role if last_msg else ""),
                })
                
                if len(conversations) >= limit:
                    break
            
            # Sort by last_message_at descending
            conversations.sort(key=lambda c: c.get("last_message_at", ""), reverse=True)
            
            return {
                "conversations": conversations[:limit],
                "last_evaluated_key": response.get("LastEvaluatedKey"),
                "has_more": len(conversations) > limit or response.get("LastEvaluatedKey") is not None,
            }
            
        except ClientError as e:
            logger.error(f"Failed to list conversations: {e}")
            raise

    def delete_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> int:
        """
        Delete all messages in a conversation.
        
        Args:
            conversation_id: Conversation to delete
            user_id: User identifier
            
        Returns:
            Number of messages deleted
        """
        messages = self.get_conversation_history(conversation_id, limit=100)
        deleted = 0
        
        for msg in messages:
            try:
                sk = self._build_sk(conversation_id, msg.created_at)
                self._client.delete_item(
                    TableName=self.table_name,
                    Key={
                        "user_id": {"S": user_id},
                        "sk": {"S": sk},
                    }
                )
                deleted += 1
            except ClientError as e:
                logger.error(f"Failed to delete message: {e}")
        
        logger.info(f"Deleted {deleted} messages from conversation {conversation_id}")
        return deleted

    def _parse_message(self, item: Dict) -> ChatMessage:
        """Parse DynamoDB item to ChatMessage."""
        role_str = item.get("role", {}).get("S", "user")
        try:
            role = MessageRole(role_str)
        except ValueError:
            role = role_str
        
        # Parse usage if present
        usage = None
        if "usage" in item:
            usage_map = item["usage"].get("M", {})
            usage = {
                "input_tokens": int(usage_map.get("input_tokens", {}).get("N", 0)),
                "output_tokens": int(usage_map.get("output_tokens", {}).get("N", 0)),
                "total_tokens": int(usage_map.get("total_tokens", {}).get("N", 0)),
            }
        
        # Parse citations if present
        citations = None
        if "citations" in item:
            citations_str = item["citations"].get("S")
            if citations_str:
                citations = self._deserialize_json(citations_str)
        
        return ChatMessage(
            conversation_id=item.get("conversation_id", {}).get("S", ""),
            role=role,
            content=item.get("content", {}).get("S", ""),
            created_at=item.get("created_at", {}).get("S", ""),
            user_id=item.get("user_id", {}).get("S", "anonymous"),
            message_id=item.get("message_id", {}).get("S"),
            citations=citations,
            usage=usage,
            model=item.get("model", {}).get("S"),
        )

    def _serialize_json(self, data: Any) -> str:
        """Serialize data to JSON string."""
        import json
        return json.dumps(data)
    
    def _deserialize_json(self, data: str) -> Any:
        """Deserialize JSON string to data."""
        import json
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None


class CachedChatHistoryManager:
    """
    Caching wrapper for ChatHistoryManager.
    
    Reduces DynamoDB queries by caching conversation history.
    Cache is invalidated when new messages are saved.
    
    Benefits:
    - Reduces N+1 query problem (history loaded on every chat request)
    - TTL-based cache expiration
    - Automatic invalidation on write
    """
    
    def __init__(
        self,
        history_manager: ChatHistoryManager,
        cache_ttl_seconds: int = 300,  # 5 minutes default
        max_cache_size: int = 1000,
    ):
        """
        Initialize cached history manager.
        
        Args:
            history_manager: Underlying ChatHistoryManager
            cache_ttl_seconds: Cache TTL in seconds
            max_cache_size: Maximum cache entries
        """
        self.history_manager = history_manager
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, tuple] = {}  # key -> (data, timestamp)
        
        logger.info(f"Initialized CachedChatHistoryManager with TTL={cache_ttl_seconds}s")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache:
            return False
        _, timestamp = self._cache[cache_key]
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        return age < self.cache_ttl_seconds
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get value from cache if valid."""
        if self._is_cache_valid(cache_key):
            data, _ = self._cache[cache_key]
            logger.debug(f"Cache HIT: {cache_key}")
            return data
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set cache value with current timestamp."""
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_cache_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[cache_key] = (data, datetime.now(timezone.utc))
    
    def _invalidate_cache(self, conversation_id: str) -> None:
        """Invalidate all cache entries for a conversation."""
        keys_to_delete = [k for k in self._cache if k.startswith(f"history:{conversation_id}:")]
        for key in keys_to_delete:
            del self._cache[key]
        if keys_to_delete:
            logger.debug(f"Cache invalidated for conversation {conversation_id}")
    
    def get_history_for_context(
        self,
        conversation_id: str,
        max_messages: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Get conversation history with caching.
        
        Args:
            conversation_id: Conversation identifier
            max_messages: Maximum messages to include
            
        Returns:
            List of message dicts for Claude
        """
        cache_key = f"history:{conversation_id}:{max_messages}"
        
        # Try cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Cache miss - fetch from DynamoDB
        history = self.history_manager.get_history_for_context(
            conversation_id=conversation_id,
            max_messages=max_messages,
        )
        
        # Store in cache
        self._set_cache(cache_key, history)
        return history
    
    def save_message(self, *args, **kwargs) -> ChatMessage:
        """Save message and invalidate cache."""
        result = self.history_manager.save_message(*args, **kwargs)
        self._invalidate_cache(result.conversation_id)
        return result
    
    def save_user_message(self, conversation_id: str, *args, **kwargs) -> ChatMessage:
        """Save user message and invalidate cache."""
        result = self.history_manager.save_user_message(conversation_id, *args, **kwargs)
        self._invalidate_cache(conversation_id)
        return result
    
    def save_assistant_message(self, conversation_id: str, *args, **kwargs) -> ChatMessage:
        """Save assistant message and invalidate cache."""
        result = self.history_manager.save_assistant_message(conversation_id, *args, **kwargs)
        self._invalidate_cache(conversation_id)
        return result
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> int:
        """Delete conversation and invalidate cache."""
        result = self.history_manager.delete_conversation(conversation_id, user_id)
        self._invalidate_cache(conversation_id)
        return result
    
    # Delegate other methods directly
    def get_conversation_history(self, *args, **kwargs):
        return self.history_manager.get_conversation_history(*args, **kwargs)
    
    def list_conversations(self, *args, **kwargs):
        return self.history_manager.list_conversations(*args, **kwargs)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        valid_entries = sum(1 for k in self._cache if self._is_cache_valid(k))
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._cache) - valid_entries,
            "max_size": self.max_cache_size,
            "ttl_seconds": self.cache_ttl_seconds,
        }


# Convenience function
def create_chat_history_manager(
    table_name: Optional[str] = None,
    region_name: Optional[str] = None,
    use_cache: bool = True,
    cache_ttl_seconds: int = 300,
) -> ChatHistoryManager:
    """
    Create ChatHistoryManager instance.
    
    Args:
        table_name: DynamoDB table name
        region_name: AWS region
        use_cache: Enable caching (recommended for production)
        cache_ttl_seconds: Cache TTL
        
    Returns:
        ChatHistoryManager or CachedChatHistoryManager
    """
    base_manager = ChatHistoryManager(
        table_name=table_name,
        region_name=region_name,
    )
    
    if use_cache:
        return CachedChatHistoryManager(
            history_manager=base_manager,
            cache_ttl_seconds=cache_ttl_seconds,
        )
    
    return base_manager
