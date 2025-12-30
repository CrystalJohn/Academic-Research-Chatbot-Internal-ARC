# Services module - Re-exports for backward compatibility
#
# New structure:
#   services/ai/       - AI/LLM services (Claude, Bedrock, Embeddings)
#   services/search/   - Search & RAG (Qdrant, BM25, RAG)
#   services/document/ - Document processing (PDF, SQS worker)
#   services/chat/     - Chat history management
#   services/auth/     - Authentication
#   services/common/   - Shared utilities (rate limiter, monitoring, etc.)
#
# You can import directly from submodules:
#   from app.services.ai import ClaudeService
#   from app.services.search import RAGService
#
# Or use legacy imports (backward compatible):
#   from app.services import ClaudeService

# AI Services
from .ai.claude_service import *
from .ai.claude_converse_service import *
from .ai.bedrock_retry import *
from .ai.embedding_service import *
from .ai.ragas_evaluator import *

# Search Services
from .search.rag_service import *
from .search.rag_with_tools_service import *
from .search.bm25_search import *
from .search.qdrant_client import *
from .search.text_chunker import *

# Document Services
from .document.document_status_manager import *
from .document.pdf_detector import *
from .document.pdf_extractor import *
from .document.sqs_worker import *

# Chat Services
from .chat.chat_history_manager import *

# Auth Services
from .auth.auth_service import *

# Common Services
from .common.rate_limiter import *
from .common.budget_manager import *
from .common.monitoring_service import *
from .common.email_service import *
from .common.language_context import *
