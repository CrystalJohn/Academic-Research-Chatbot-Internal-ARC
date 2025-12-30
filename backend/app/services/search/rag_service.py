"""
Task #27: RAG Prompt Template with Citations

Provides RAG orchestration with context injection and citation formatting.
Combines vector search, prompt building, and Claude inference.

Layer 3: Hybrid Retrieval (BM25 + Vector Search) for improved relevance.

IMPROVEMENTS APPLIED:
1. ✅ System prompts focus on specific question
2. ✅ Query template reordered (question first)
3. ✅ Adaptive hybrid weights for technical queries
4. ✅ Increased top_k and better defaults
"""

import logging
import re
from typing import List, Dict, Any, Optional, Generator, Set
from dataclasses import dataclass, field
from enum import Enum

from app.services.search.qdrant_client import (
    QdrantVectorStore,
    SearchFilter,
    RAGContext,
)
from app.services.ai.embedding_service import CohereEmbeddingService as EmbeddingService
from app.services.ai.claude_service import (
    ClaudeService,
    ClaudeResponse,
    StreamChunk,
    TokenUsage,
)
from app.services.search.bm25_search import BM25Index, HybridRetriever, BM25Result
from app.services.document.document_status_manager import DocumentStatusManager
from app.services.common.language_context import (
    LanguageContext,
    get_language_context,
    get_language_instruction,
    get_language_switch_message,
    detect_query_language,
)

logger = logging.getLogger(__name__)


class PromptTemplate(Enum):
    """Available prompt templates."""
    DEFAULT = "default"
    ACADEMIC = "academic"
    CONCISE = "concise"
    DETAILED = "detailed"


# Vietnamese character set for language detection
VIETNAMESE_CHARS = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')

# Greeting patterns for detection
GREETING_PATTERNS = {
    "vi": [
        "xin chào", "chào bạn", "chào", "hello", "hi", "hey",
        "xin hỏi", "cho mình hỏi", "cho tôi hỏi", "mình muốn hỏi",
        "bạn ơi", "alo", "chào buổi sáng", "chào buổi chiều", "chào buổi tối"
    ],
    "en": [
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "greetings", "howdy", "what's up", "sup"
    ]
}

# Greeting responses - friendly and informative
GREETING_RESPONSES = {
    "vi": """Xin chào! 👋 Tôi là ARC Chatbot - trợ lý nghiên cứu tài liệu của bạn.

Tôi có thể giúp bạn:
📚 Tìm kiếm thông tin trong các tài liệu đã upload
📝 Trả lời câu hỏi dựa trên nội dung tài liệu
🔍 Trích dẫn nguồn chính xác với số trang

Bạn muốn hỏi về vấn đề gì trong tài liệu? Hãy đặt câu hỏi cụ thể để tôi hỗ trợ tốt nhất nhé! 😊""",

    "en": """Hello! 👋 I'm ARC Chatbot - your research document assistant.

I can help you:
📚 Search information in uploaded documents
📝 Answer questions based on document content
🔍 Cite sources accurately with page numbers

What would you like to know about your documents? Feel free to ask specific questions! 😊"""
}


def is_greeting(text: str) -> tuple[bool, str]:
    """
    Check if text is a greeting message.
    
    Args:
        text: Input text to check
        
    Returns:
        Tuple of (is_greeting, detected_language)
    """
    if not text:
        return False, "en"
    
    text_lower = text.lower().strip()
    
    # Remove punctuation for matching
    text_clean = ''.join(c for c in text_lower if c.isalnum() or c.isspace())
    
    # Detect language first based on Vietnamese characters
    has_vietnamese = any(c in text_lower for c in VIETNAMESE_CHARS)
    
    # Vietnamese-specific greetings (only in Vietnamese)
    vi_only_greetings = ["xin chào", "chào bạn", "chào", "xin hỏi", "cho mình hỏi", 
                         "cho tôi hỏi", "mình muốn hỏi", "bạn ơi", "alo",
                         "chào buổi sáng", "chào buổi chiều", "chào buổi tối"]
    
    for pattern in vi_only_greetings:
        if pattern in text_clean or text_clean == pattern:
            return True, "vi"
    
    # English-specific greetings
    en_only_greetings = ["good morning", "good afternoon", "good evening",
                         "greetings", "howdy", "what's up", "sup"]
    
    for pattern in en_only_greetings:
        if pattern in text_clean or text_clean == pattern:
            return True, "en"
    
    # Universal greetings - detect language based on context
    universal_greetings = ["hello", "hi", "hey"]
    
    for pattern in universal_greetings:
        if text_clean == pattern or text_clean.startswith(pattern + " "):
            # If has Vietnamese chars elsewhere, respond in Vietnamese
            if has_vietnamese:
                return True, "vi"
            # Default to Vietnamese for this Vietnamese-focused app
            return True, "vi"
    
    # Short messages that might be greetings
    if len(text_clean.split()) <= 2:
        short_greetings = ["hi", "hello", "hey"]
        if text_clean in short_greetings:
            return True, "vi"  # Default to Vietnamese
    
    return False, "en"


def detect_language(text: str) -> str:
    """
    Detect if text is Vietnamese or English.
    
    Args:
        text: Input text to analyze
        
    Returns:
        "vi" for Vietnamese, "en" for English
    """
    if not text:
        return "en"
    
    text_lower = text.lower()
    vi_char_count = sum(1 for c in text_lower if c in VIETNAMESE_CHARS)
    
    # If more than 2% Vietnamese characters, consider it Vietnamese
    # This threshold works well for mixed text
    return "vi" if vi_char_count / len(text) > 0.02 else "en"


# ✅ OPTIMIZED SYSTEM PROMPTS - SMART CITATION (not spam)
SYSTEM_PROMPTS = {
    PromptTemplate.DEFAULT: """You are an expert research assistant for academic documents.

CORE TASK:
1. READ the user's question carefully
2. ANSWER directly using ONLY the provided document context
3. If context lacks the answer: "The provided documents do not contain information about [topic]"

⚠️ CITATION CONTRACT:
- You may ONLY cite using IDs from the provided list: [1], [2], [3], etc.
- DO NOT create new citation IDs beyond what is provided
- DO NOT cite sources not in the provided list

📌 SMART CITATION RULES (IMPORTANT):
- Cite only KEY CLAIMS: definitions, regulations, statistics, conclusions, comparisons
- Maximum 1-2 citations per sentence
- Do NOT cite unrelated sources just to "use all citations"
- Quality over quantity - cite what matters, not everything

RESPONSE FORMAT (REQUIRED - 4 SECTIONS):

## Answer
2-4 sentences directly answering the question. Each sentence max 1 citation at the end.

## Evidence
- Key point 1 [1] (p.X)
- Key point 2 [2] (p.Y)
- Key point 3 [3] (p.Z)

## Limitations
What the documents do NOT cover (1 sentence).

## Next Steps
1 suggestion for follow-up question or action.

Remember: Answer the SPECIFIC question. Do not summarize everything.""",

    PromptTemplate.ACADEMIC: """You are an academic research assistant for scholarly content.

CORE TASK:
1. UNDERSTAND the research question
2. ANSWER using ONLY the provided document context
3. Use formal academic language

⚠️ CITATION CONTRACT:
- Only cite from provided IDs [1..N]
- Do NOT invent new citation numbers

📌 SMART CITATION RULES:
- Cite only KEY CLAIMS: definitions, findings, methodology, conclusions
- Max 1-2 citations per sentence
- Do NOT force citations on every phrase
- Academic credibility = precise citations, not many citations

RESPONSE FORMAT (REQUIRED):

## Answer
Direct answer in 2-4 academic sentences. Cite key claims only.

## Evidence
- Finding 1 [1] (p.X)
- Finding 2 [2] (p.Y)

## Limitations
Gaps in the provided sources.

## Next Steps
Suggested follow-up research direction.

If context lacks information: "The provided academic sources do not address [topic]." """,

    PromptTemplate.CONCISE: """You are a concise research assistant.

RULES:
1. Answer the SPECIFIC question
2. Use ONLY provided context
3. Maximum 2-3 sentences

⚠️ CITATION: Only use IDs [1..N] provided. Cite key facts only, max 1 per sentence.

FORMAT:
**Answer:** [1-2 sentences with key citation]
**Source:** [1] p.X - [brief quote]""",

    PromptTemplate.DETAILED: """You are a thorough research assistant.

CORE TASK:
1. IDENTIFY what user is asking
2. EXTRACT relevant information from context
3. ORGANIZE logically with clear structure

⚠️ CITATION CONTRACT:
- Only cite from [1..N] provided
- Do NOT create new IDs

📌 SMART CITATION RULES:
- Cite KEY CLAIMS: definitions, data, conclusions, comparisons
- Max 2 citations per sentence
- Do NOT spam citations - quality over quantity

RESPONSE FORMAT (REQUIRED):

## Answer
Comprehensive answer in 3-5 sentences. Cite key claims.

## Evidence
Detailed bullet points with citations:
- Point 1 [1] (p.X): explanation
- Point 2 [2] (p.Y): explanation
- Point 3 [3] (p.Z): explanation

## Limitations
What is NOT covered in the documents.

## Next Steps
2-3 suggested follow-up questions or actions.

If context insufficient: State what IS available and what is missing.""",
}

# Vietnamese system prompts - OPTIMIZED
SYSTEM_PROMPTS_VI = {
    PromptTemplate.DEFAULT: """Bạn là trợ lý nghiên cứu chuyên nghiệp cho tài liệu học thuật.

NHIỆM VỤ CHÍNH:
1. ĐỌC câu hỏi của người dùng cẩn thận
2. TRẢ LỜI trực tiếp chỉ dựa trên ngữ cảnh tài liệu được cung cấp
3. Nếu không có thông tin: "Tài liệu không chứa thông tin về [chủ đề]"

⚠️ HỢP ĐỒNG TRÍCH DẪN:
- Chỉ được dùng ID trích dẫn từ danh sách: [1], [2], [3], v.v.
- KHÔNG tạo ID mới ngoài danh sách
- KHÔNG trích dẫn nguồn không có trong danh sách

📌 QUY TẮC TRÍCH DẪN THÔNG MINH (QUAN TRỌNG):
- Chỉ cite cho CLAIM QUAN TRỌNG: định nghĩa, quy định, số liệu, kết luận, so sánh
- Tối đa 1-2 citations mỗi câu
- KHÔNG cite nguồn không liên quan chỉ để "dùng hết citations"
- Chất lượng hơn số lượng - cite cái quan trọng, không phải mọi thứ

ĐỊNH DẠNG TRẢ LỜI (BẮT BUỘC - 4 PHẦN):

## Trả lời
2-4 câu trả lời trực tiếp câu hỏi. Mỗi câu tối đa 1 citation ở cuối.

## Bằng chứng
- Điểm chính 1 [1] (tr.X)
- Điểm chính 2 [2] (tr.Y)
- Điểm chính 3 [3] (tr.Z)

## Giới hạn
Những gì tài liệu KHÔNG đề cập (1 câu).

## Bước tiếp theo
1 gợi ý câu hỏi hoặc hành động tiếp theo.

Nhớ: Trả lời câu hỏi CỤ THỂ. Không tóm tắt mọi thứ.""",

    PromptTemplate.ACADEMIC: """Bạn là trợ lý nghiên cứu học thuật chuyên về nội dung khoa học.

NHIỆM VỤ CHÍNH:
1. HIỂU câu hỏi nghiên cứu
2. TRẢ LỜI chỉ dựa trên ngữ cảnh tài liệu
3. Sử dụng ngôn ngữ học thuật trang trọng

⚠️ HỢP ĐỒNG TRÍCH DẪN:
- Chỉ cite từ ID [1..N] được cung cấp
- KHÔNG tạo số trích dẫn mới

📌 QUY TẮC TRÍCH DẪN THÔNG MINH:
- Chỉ cite CLAIM QUAN TRỌNG: định nghĩa, phát hiện, phương pháp, kết luận
- Tối đa 1-2 citations mỗi câu
- KHÔNG ép citation vào mọi cụm từ
- Uy tín học thuật = citations chính xác, không phải nhiều citations

ĐỊNH DẠNG TRẢ LỜI (BẮT BUỘC):

## Trả lời
Trả lời trực tiếp trong 2-4 câu học thuật. Chỉ cite claim quan trọng.

## Bằng chứng
- Phát hiện 1 [1] (tr.X)
- Phát hiện 2 [2] (tr.Y)

## Giới hạn
Khoảng trống trong nguồn được cung cấp.

## Bước tiếp theo
Hướng nghiên cứu tiếp theo được đề xuất.

Nếu thiếu thông tin: "Nguồn học thuật không đề cập đến [chủ đề]." """,

    PromptTemplate.CONCISE: """Bạn là trợ lý nghiên cứu ngắn gọn.

QUY TẮC:
1. Trả lời câu hỏi CỤ THỂ
2. Chỉ dùng ngữ cảnh được cung cấp
3. Tối đa 2-3 câu

⚠️ TRÍCH DẪN: Chỉ dùng ID [1..N]. Cite fact quan trọng, tối đa 1 mỗi câu.

ĐỊNH DẠNG:
**Trả lời:** [1-2 câu với citation quan trọng]
**Nguồn:** [1] tr.X - [trích dẫn ngắn]""",

    PromptTemplate.DETAILED: """Bạn là trợ lý nghiên cứu kỹ lưỡng.

NHIỆM VỤ CHÍNH:
1. XÁC ĐỊNH người dùng đang hỏi gì
2. TRÍCH XUẤT thông tin liên quan từ ngữ cảnh
3. TỔ CHỨC logic với cấu trúc rõ ràng

⚠️ HỢP ĐỒNG TRÍCH DẪN:
- Chỉ cite từ [1..N] được cung cấp
- KHÔNG tạo ID mới

📌 QUY TẮC TRÍCH DẪN THÔNG MINH:
- Cite CLAIM QUAN TRỌNG: định nghĩa, dữ liệu, kết luận, so sánh
- Tối đa 2 citations mỗi câu
- KHÔNG spam citations - chất lượng hơn số lượng

ĐỊNH DẠNG TRẢ LỜI (BẮT BUỘC):

## Trả lời
Trả lời toàn diện trong 3-5 câu. Cite claim quan trọng.

## Bằng chứng
Bullet points chi tiết với citations:
- Điểm 1 [1] (tr.X): giải thích
- Điểm 2 [2] (tr.Y): giải thích
- Điểm 3 [3] (tr.Z): giải thích

## Giới hạn
Những gì KHÔNG được đề cập trong tài liệu.

## Bước tiếp theo
2-3 câu hỏi hoặc hành động tiếp theo được đề xuất.

Nếu ngữ cảnh không đủ: Nêu rõ thông tin NÀO có sẵn và thiếu gì.""",
}


@dataclass
class Citation:
    """Citation reference in response."""
    id: int  # [1], [2], etc.
    doc_id: str
    page: int
    text_snippet: str  # First 100 chars of source
    score: float
    filename: str = ""  # Original filename for display


@dataclass
class RAGResponse:
    """Response from RAG pipeline."""
    answer: str
    citations: List[Citation]
    usage: TokenUsage
    model: str
    contexts_used: int
    query: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": [
                {
                    "id": c.id,
                    "doc_id": c.doc_id,
                    "page": c.page,
                    "text_snippet": c.text_snippet,
                    "score": c.score,
                }
                for c in self.citations
            ],
            "usage": self.usage.to_dict(),
            "model": self.model,
            "contexts_used": self.contexts_used,
            "query": self.query,
        }


class RAGPromptBuilder:
    """
    Builds RAG prompts with context injection and citation formatting.
    """
    
    CONTEXT_TEMPLATE = """[{citation_id}] (Document: {doc_id}, Page {page})
{text}"""
    
    # ✅ OPTIMIZED QUERY TEMPLATE - SMART CITATION
    QUERY_TEMPLATE = """USER QUESTION: {query}

Answer using ONLY the document context below.

=== AVAILABLE CITATIONS ===
{citations_json}

⚠️ CITATION CONTRACT:
- You may ONLY cite using IDs: {citation_range}
- DO NOT create new citation IDs beyond this range

📌 SMART CITATION RULES:
- Cite only KEY CLAIMS (definitions, data, conclusions)
- Max 1-2 citations per sentence
- Do NOT cite unrelated sources
- Do NOT try to use all citations - quality over quantity

=== DOCUMENT CONTEXT ===
{context_section}
=== END CONTEXT ===

RESPOND IN THIS FORMAT:

## Answer
[2-4 sentences answering the question. Max 1 citation per sentence at the end.]

## Evidence
[Bullet list with citations and page numbers]
- Key point [N] (p.X)

## Limitations
[1 sentence: what the documents do NOT cover]

## Next Steps
[1 suggestion for follow-up]

YOUR RESPONSE:"""
    
    @classmethod
    def build_context_section(cls, contexts: List[RAGContext]) -> str:
        """Build formatted context section from RAGContext list."""
        if not contexts:
            return "No relevant context found."
        
        parts = []
        for ctx in contexts:
            part = cls.CONTEXT_TEMPLATE.format(
                citation_id=ctx.citation_id,
                doc_id=ctx.doc_id,
                page=ctx.page,
                text=ctx.text.strip(),
            )
            parts.append(part)
        
        return "\n\n---\n\n".join(parts)
    
    @classmethod
    def build_prompt(
        cls,
        query: str,
        contexts: List[RAGContext],
    ) -> str:
        """Build complete RAG prompt with context and query."""
        # Rank contexts by score before building prompt
        # This ensures [1] is always the most relevant
        ranked_contexts = cls.rank_contexts_by_score(contexts)
        context_section = cls.build_context_section(ranked_contexts)
        
        # Build citations JSON for contract enforcement
        citations_list = []
        for ctx in ranked_contexts:
            citations_list.append({
                "id": ctx.citation_id,
                "doc_id": ctx.doc_id[:20] + "..." if len(ctx.doc_id) > 20 else ctx.doc_id,
                "page": ctx.page,
                "snippet": ctx.text[:100] + "..." if len(ctx.text) > 100 else ctx.text
            })
        
        import json
        citations_json = json.dumps(citations_list, ensure_ascii=False, indent=2)
        citation_range = f"[1..{len(ranked_contexts)}]" if ranked_contexts else "[none]"
        
        return cls.QUERY_TEMPLATE.format(
            query=query,
            citations_json=citations_json,
            citation_range=citation_range,
            context_section=context_section,
        )
    
    @classmethod
    def rank_contexts_by_score(cls, contexts: List[RAGContext], force_rerank: bool = False) -> List[RAGContext]:
        """
        Rank contexts by score and assign citation IDs accordingly.
        
        This ensures:
        - [1] = highest score (most relevant)
        - [2] = second highest
        - etc.
        
        Args:
            contexts: List of RAGContext objects
            force_rerank: Force re-ranking even if already ranked
            
        Returns:
            Sorted contexts with reassigned citation IDs
        """
        if not contexts:
            return contexts
        
        # Check if already properly ranked (skip if [1] has highest score)
        if not force_rerank and len(contexts) > 1:
            is_sorted = all(
                contexts[i].score >= contexts[i+1].score 
                for i in range(len(contexts)-1)
            )
            if is_sorted and contexts[0].citation_id == 1:
                logger.debug("Contexts already ranked by score, skipping re-rank")
                return contexts
        
        # Sort by score descending (highest first)
        sorted_contexts = sorted(contexts, key=lambda x: x.score, reverse=True)
        
        # Reassign citation IDs based on rank
        for idx, context in enumerate(sorted_contexts, 1):
            context.citation_id = idx
        
        # Log ranking for debugging
        logger.info(
            f"✅ Citation ranking by score: "
            f"{[(c.citation_id, f'{c.score:.1f}%', c.doc_id[:20] if c.doc_id else 'unknown') for c in sorted_contexts]}"
        )
        
        return sorted_contexts
    
    @classmethod
    def extract_citations(cls, contexts: List[RAGContext]) -> List[Citation]:
        """Extract citation objects from contexts with full text for highlighting."""
        # Ensure contexts are ranked by score before extracting
        ranked_contexts = cls.rank_contexts_by_score(contexts)
        
        # Lookup filenames from DynamoDB (batch for efficiency)
        doc_ids = list(set(ctx.doc_id for ctx in ranked_contexts))
        filename_map = cls._get_filenames_for_docs(doc_ids)
        
        return [
            Citation(
                id=ctx.citation_id,
                doc_id=ctx.doc_id,
                page=ctx.page,
                # Return full text (up to 1000 chars) for comprehensive citation display
                text_snippet=ctx.text[:1000] + "..." if len(ctx.text) > 1000 else ctx.text,
                score=ctx.score,
                filename=filename_map.get(ctx.doc_id, ""),
            )
            for ctx in ranked_contexts
        ]
    
    @staticmethod
    def _get_filenames_for_docs(doc_ids: List[str]) -> Dict[str, str]:
        """Lookup filenames from DynamoDB for given doc_ids."""
        if not doc_ids:
            return {}
        
        try:
            status_manager = DocumentStatusManager()
            filename_map = {}
            for doc_id in doc_ids:
                doc = status_manager.get_document(doc_id)
                if doc:
                    filename_map[doc_id] = doc.get("filename", "")
            return filename_map
        except Exception as e:
            logger.warning(f"Failed to lookup filenames: {e}")
            return {}


def validate_citations(answer: str, contexts: List[RAGContext]) -> Dict[str, Any]:
    """
    Validate citation quality in the generated answer.
    
    Checks:
    - Which citations were actually used
    - Whether high-score contexts were cited
    - Citation coverage percentage
    
    Args:
        answer: Generated answer text
        contexts: List of contexts provided to LLM
        
    Returns:
        Dictionary with validation metrics and warnings
    """
    if not contexts:
        return {
            "cited_ids": set(),
            "citation_coverage": 0,
            "high_score_usage": 1.0,
            "warnings": []
        }
    
    # Extract citation IDs from answer [1], [2], etc.
    cited_ids: Set[int] = set(map(int, re.findall(r'\[(\d+)\]', answer)))
    
    # Find high-score contexts (>= 60%)
    high_score_threshold = 60.0
    high_score_contexts = [c for c in contexts if c.score >= high_score_threshold]
    high_score_cited = [c for c in high_score_contexts if c.citation_id in cited_ids]
    
    # Calculate metrics
    citation_coverage = len(cited_ids) / len(contexts) if contexts else 0
    high_score_usage = len(high_score_cited) / len(high_score_contexts) if high_score_contexts else 1.0
    
    # Generate warnings
    warnings = []
    
    # Warning if [1] (highest score) not cited
    if contexts and 1 not in cited_ids:
        warnings.append(f"⚠️ Citation [1] (highest score: {contexts[0].score:.1f}%) not used in answer")
    
    # Warning if high-score contexts not used
    if high_score_usage < 1.0:
        unused = [c.citation_id for c in high_score_contexts if c.citation_id not in cited_ids]
        warnings.append(f"⚠️ High-score contexts not cited: {unused}")
    
    # Log validation results
    logger.info(
        f"📊 Citation validation: cited={sorted(cited_ids)}, "
        f"coverage={citation_coverage:.0%}, high_score_usage={high_score_usage:.0%}"
    )
    
    return {
        "cited_ids": cited_ids,
        "citation_coverage": citation_coverage,
        "high_score_usage": high_score_usage,
        "warnings": warnings
    }


class RAGService:
    """
    RAG orchestration service.
    
    Combines vector search, prompt building, and Claude inference
    into a complete RAG pipeline.
    
    Layer 3: Supports Hybrid Retrieval (BM25 + Vector) for better relevance.
    """
    
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        region_name: str = "ap-southeast-1",
        model: str = "sonnet",
        template: PromptTemplate = PromptTemplate.DEFAULT,
        use_hybrid: bool = True,
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
    ):
        """
        Initialize RAG service.
        
        Args:
            qdrant_host: Qdrant server host
            qdrant_port: Qdrant server port
            region_name: AWS region for Bedrock
            model: Claude model alias (sonnet/haiku)
            template: Prompt template to use
            use_hybrid: Enable hybrid retrieval (BM25 + Vector)
            bm25_weight: Weight for BM25 in hybrid search
            vector_weight: Weight for vector search in hybrid
        """
        self.vector_store = QdrantVectorStore(host=qdrant_host, port=qdrant_port)
        self.embedding_service = EmbeddingService(region_name=region_name)
        self.claude_service = ClaudeService(region_name=region_name, model=model)
        self.template = template
        self.prompt_builder = RAGPromptBuilder()
        
        # Layer 3: Hybrid Retrieval
        self.use_hybrid = use_hybrid
        self.bm25_index = BM25Index() if use_hybrid else None
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self._bm25_initialized = False
        
        logger.info(f"Initialized RAG service with model={model}, template={template.value}, hybrid={use_hybrid}")
    
    def set_template(self, template: PromptTemplate) -> None:
        """Change prompt template."""
        self.template = template
        logger.info(f"Changed template to: {template.value}")
    
    def set_model(self, model: str) -> None:
        """Change Claude model."""
        self.claude_service.switch_model(model)
    
    def _init_bm25_from_qdrant(self) -> None:
        """Initialize BM25 index from Qdrant data."""
        if not self.use_hybrid or self._bm25_initialized:
            return
        
        try:
            # Get all documents from Qdrant
            all_points = self.vector_store.get_all_points(limit=10000)
            
            if not all_points:
                logger.warning("No documents in Qdrant for BM25 indexing")
                return
            
            # Index documents in BM25
            for point in all_points:
                payload = point.get("payload", {})
                self.bm25_index.add_document(
                    chunk_id=str(point.get("id", "")),
                    text=payload.get("text", ""),
                    doc_id=payload.get("doc_id", ""),
                    metadata=payload
                )
            
            self._bm25_initialized = True
            logger.info(f"BM25 index initialized with {len(all_points)} documents")
            
        except Exception as e:
            logger.error(f"Failed to initialize BM25 index: {e}")
    
    def _vector_search_fn(self, query: str, top_k: int) -> List[Dict]:
        """Vector search function for hybrid retriever."""
        # IMPORTANT: Use input_type="search_query" for queries (not "search_document")
        # Cohere Embed v3 optimizes vectors differently for queries vs documents
        query_embedding = self.embedding_service.embed_text(query, input_type="search_query")
        
        results = self.vector_store.search(
            query_vector=query_embedding,
            top_k=top_k,
            score_threshold=0.0  # Get all results, filter later
        )
        
        # SearchResult has direct attributes, not payload dict
        return [
            {
                "chunk_id": str(r.id),
                "text": r.text,
                "doc_id": r.doc_id,
                "score": r.score,
                "metadata": {
                    "page": r.page,
                    "chunk_index": r.chunk_index,
                    "is_table": r.is_table,
                }
            }
            for r in results
        ]
    # Retrieve Context
    # ✅ FIX #3: ADAPTIVE HYBRID WEIGHTS FOR TECHNICAL QUERIES (Thread-safe)
    def retrieve_contexts(
        self,
        query: str,
        top_k: int = 3,  # Only top 3 most relevant results
        score_threshold: float = 0.3,  # 30% minimum - balanced for recall
        search_filter: Optional[SearchFilter] = None,
    ) -> List[RAGContext]:
        """
        Retrieve relevant contexts for a query.
        
        Uses Hybrid Retrieval (BM25 + Vector) if enabled.
        With adaptive weighting for technical queries.
        
        THREAD-SAFE: Uses local variables for weights to avoid race conditions.
        
        Args:
            query: User query
            top_k: Number of contexts to retrieve
            score_threshold: Minimum relevance score (default 0.3 = 30%)
            search_filter: Optional filter for documents
            
        Returns:
            List of RAGContext objects sorted by score with citation IDs
        """
        # ✅ FIX: Detect technical queries for adaptive weighting
        technical_keywords = [
            'là gì', 'định nghĩa', 'khái niệm', 'công thức', 'phương pháp',
            'what is', 'definition', 'formula', 'method', 'concept'
        ]
        is_technical = any(kw in query.lower() for kw in technical_keywords)
        
        # ✅ FIX #1: Use LOCAL variables instead of mutating instance state (thread-safe)
        bm25_w = 0.5 if is_technical else self.bm25_weight
        vector_w = 0.5 if is_technical else self.vector_weight
        
        if is_technical and self.use_hybrid:
            logger.info(f"Technical query detected: '{query[:50]}...' - Using balanced weights (BM25=0.5, Vector=0.5)")
        
        contexts = []
        
        # Try hybrid retrieval first
        if self.use_hybrid:
            try:
                # Initialize BM25 if needed
                self._init_bm25_from_qdrant()
                
                if self._bm25_initialized and self.bm25_index.doc_count > 0:
                    # ✅ FIX: Create hybrid retriever with LOCAL weights (thread-safe)
                    hybrid = HybridRetriever(
                        bm25_index=self.bm25_index,
                        vector_search_fn=lambda q, k: self._vector_search_fn(q, k),
                        bm25_weight=bm25_w,  # ✅ Local variable
                        vector_weight=vector_w  # ✅ Local variable
                    )
                    
                    # Perform hybrid search (fetch more for better filtering)
                    results = hybrid.search(
                        query=query,
                        top_k=top_k * 2,  # Fetch 2x for filtering
                        bm25_top_k=top_k * 3,
                        vector_top_k=top_k * 3
                    )
                    
                    # Filter by score threshold
                    filtered_results = [
                        r for r in results 
                        if r.get("combined_score", 0) * 100 >= score_threshold * 100
                    ]
                    results = filtered_results[:top_k]
                    
                    # Convert to RAGContext (citation_id will be reassigned after sorting)
                    for r in results:
                        metadata = r.get("metadata", {})
                        contexts.append(RAGContext(
                            citation_id=0,  # Will be assigned after sorting
                            doc_id=r.get("doc_id", ""),
                            page=metadata.get("page", 1),
                            text=r.get("text", ""),
                            score=r.get("combined_score", 0) * 100,  # Scale to percentage
                            metadata=metadata
                        ))
                    
                    logger.info(
                        f"Hybrid retrieval: {len(contexts)} contexts "
                        f"(score >= {score_threshold*100}%) for query: {query[:50]}..."
                    )
                    
            except Exception as e:
                logger.warning(f"Hybrid retrieval failed, falling back to vector: {e}")
                contexts = []  # Reset for fallback
        
        # Fallback to vector-only search if hybrid failed or not enabled
        if not contexts:
            query_embedding = self.embedding_service.embed_text(query, input_type="search_query")
            
            contexts = self.vector_store.search_for_rag(
                query_vector=query_embedding,
                top_k=top_k,
                score_threshold=score_threshold,
                search_filter=search_filter,
            )
            
            logger.info(
                f"Vector retrieval: {len(contexts)} contexts "
                f"(score >= {score_threshold*100}%) for query: {query[:50]}..."
            )
        
        # ✅ FIX #2: Sort by score and assign citation IDs BEFORE returning
        if contexts:
            # Sort by score descending (highest first)
            contexts = sorted(contexts, key=lambda x: x.score, reverse=True)
            
            # Assign citation IDs based on rank: [1] = highest score
            for idx, ctx in enumerate(contexts, 1):
                ctx.citation_id = idx
            
            logger.info(
                f"✅ Citations ranked by score: "
                f"{[(c.citation_id, f'{c.score:.1f}%') for c in contexts]}"
            )
        
        return contexts
    
    def generate_answer(
        self,
        query: str,
        contexts: List[RAGContext],
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        language_preference: Optional[str] = None,
    ) -> RAGResponse:
        """
        Generate answer using Claude with retrieved contexts.
        
        Args:
            query: User query
            contexts: Retrieved contexts
            history: Optional conversation history
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            language_preference: Explicit language preference ("vi", "en", or None for auto)
            
        Returns:
            RAGResponse with answer and citations
        """
        # Get language context with conversation awareness
        lang_context = get_language_context(
            query=query,
            history=history,
            user_language_preference=language_preference
        )
        
        # Build prompt with improved template
        prompt = self.prompt_builder.build_prompt(query, contexts)
        
        # Select appropriate system prompt based on response language
        if lang_context.response_language == "vi":
            system_prompt = SYSTEM_PROMPTS_VI[self.template]
            logger.debug(f"Using Vietnamese prompt for query: {query[:50]}...")
        else:
            system_prompt = SYSTEM_PROMPTS[self.template]
        
        # Add explicit language instruction
        language_instruction = get_language_instruction(lang_context)
        system_prompt = system_prompt + "\n" + language_instruction
        
        # Generate response
        response = self.claude_service.invoke(
            prompt=prompt,
            system_prompt=system_prompt,
            history=history,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        # Add language switch notification if needed
        answer = response.text
        switch_msg = get_language_switch_message(lang_context)
        if switch_msg:
            answer = switch_msg + "\n\n" + answer
        
        # Validate citation quality
        validation = validate_citations(answer, contexts)
        if validation["warnings"]:
            for warning in validation["warnings"]:
                logger.warning(f"Citation quality: {warning}")
            logger.info(
                f"Citation metrics: coverage={validation['citation_coverage']:.0%}, "
                f"high_score_usage={validation['high_score_usage']:.0%}, "
                f"cited={validation['cited_ids']}"
            )
        
        # Extract citations
        citations = self.prompt_builder.extract_citations(contexts)
        
        return RAGResponse(
            answer=answer,
            citations=citations,
            usage=response.usage,
            model=response.model,
            contexts_used=len(contexts),
            query=query,
        )
    
    def generate_answer_stream(
        self,
        query: str,
        contexts: List[RAGContext],
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Generator[StreamChunk, None, None]:
        """
        Generate streaming answer using Claude.
        
        Args:
            query: User query
            contexts: Retrieved contexts
            history: Optional conversation history
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            
        Yields:
            StreamChunk objects with text fragments
        """
        prompt = self.prompt_builder.build_prompt(query, contexts)
        
        # Detect language and select appropriate system prompt
        lang = detect_language(query)
        if lang == "vi":
            system_prompt = SYSTEM_PROMPTS_VI[self.template]
            logger.debug(f"Using Vietnamese prompt (stream) for query: {query[:50]}...")
        else:
            system_prompt = SYSTEM_PROMPTS[self.template]
        
        # Always add format reminder to ensure line breaks in output
        format_reminder = "\n\n[FORMAT: PHẢI xuống dòng (\\n) sau mỗi câu/ý quan trọng. Dùng - cho danh sách. **bold** cho từ khóa.]"
        prompt = prompt + format_reminder
        
        yield from self.claude_service.invoke_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            history=history,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    def _handle_translation_request(
        self,
        query: str,
        history: List[Dict[str, str]],
        lang_context: LanguageContext,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> RAGResponse:
        """
        Handle translation/language switch requests.
        
        Instead of searching RAG, uses the last assistant response
        and translates it to the target language.
        
        Args:
            query: User's translation request
            history: Conversation history
            lang_context: Language context with target language
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            stream: Whether to stream response
            
        Returns:
            RAGResponse with translated content
        """
        # Find last assistant message to translate
        last_assistant_msg = None
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg.get("content", "")
                break
        
        if not last_assistant_msg:
            # No previous response to translate
            if lang_context.target_language == "vi":
                return RAGResponse(
                    answer="Không có câu trả lời trước đó để dịch.",
                    citations=[],
                    usage=TokenUsage(input_tokens=0, output_tokens=0),
                    model=self.claude_service.model_alias,
                    contexts_used=0,
                    query=query,
                )
            else:
                return RAGResponse(
                    answer="No previous response to translate.",
                    citations=[],
                    usage=TokenUsage(input_tokens=0, output_tokens=0),
                    model=self.claude_service.model_alias,
                    contexts_used=0,
                    query=query,
                )
        
        # Build translation prompt
        if lang_context.target_language == "vi":
            system_prompt = """Bạn là trợ lý dịch thuật chuyên nghiệp.
Dịch nội dung sau sang tiếng Việt một cách tự nhiên và chính xác.
Giữ nguyên format, citations [1], [2], và thuật ngữ kỹ thuật quan trọng."""
            prompt = f"Dịch nội dung sau sang tiếng Việt:\n\n{last_assistant_msg}"
        else:
            system_prompt = """You are a professional translation assistant.
Translate the following content to English naturally and accurately.
Preserve the format, citations [1], [2], and important technical terms."""
            prompt = f"Translate the following to English:\n\n{last_assistant_msg}"
        
        # Generate translation
        response = self.claude_service.invoke(
            prompt=prompt,
            system_prompt=system_prompt,
            history=None,  # Don't include history for translation
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        # Add language switch notification
        if lang_context.target_language == "vi":
            prefix = "📝 **Bản dịch tiếng Việt:**\n\n"
        else:
            prefix = "📝 **English translation:**\n\n"
        
        return RAGResponse(
            answer=prefix + response.text,
            citations=[],  # No new citations for translation
            usage=response.usage,
            model=response.model,
            contexts_used=0,
            query=query,
        )
    
    # ✅ OPTIMIZED FOR PRECISION
    def query(
        self,
        query: str,
        top_k: int = 3,  # Only top 3 most relevant results
        score_threshold: float = 0.3,  # 30% minimum - balanced for recall
        search_filter: Optional[SearchFilter] = None,
        history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stream: bool = False,
        language_preference: Optional[str] = None,
    ):
        """
        Complete RAG query: retrieve + generate.
        
        OPTIMIZED FOR PRECISION:
        - top_k=3 for focused, high-quality results
        - score_threshold=0.3 (30%) balanced for recall
        - Only returns results that are truly relevant to the query
        - Bilingual support with conversation-aware language detection
        - Translation request handling (uses history instead of RAG search)
        - Greeting detection for friendly responses
        
        Args:
            query: User query
            top_k: Number of contexts to retrieve (default 3)
            score_threshold: Minimum relevance score (default 0.5 = 50%)
            search_filter: Optional document filter
            history: Optional conversation history
            max_tokens: Maximum output tokens
            temperature: Sampling temperature
            stream: Whether to stream response
            language_preference: Explicit language preference ("vi", "en", or None for auto)
            
        Returns:
            RAGResponse or Generator[StreamChunk] if streaming
        """
        # ✅ Check for greeting FIRST - respond friendly without RAG search
        greeting_detected, greeting_lang = is_greeting(query)
        if greeting_detected:
            logger.info(f"Greeting detected (lang={greeting_lang}): {query}")
            greeting_response = GREETING_RESPONSES.get(greeting_lang, GREETING_RESPONSES["en"])
            
            # For streaming, yield the greeting response
            if stream:
                def greeting_stream():
                    yield StreamChunk(
                        text=greeting_response,
                        is_final=True,
                        usage=TokenUsage(input_tokens=0, output_tokens=0),
                    )
                return greeting_stream()
            
            return RAGResponse(
                answer=greeting_response,
                citations=[],  # No citations for greetings
                usage=TokenUsage(input_tokens=0, output_tokens=0),
                model=self.claude_service.model_alias,
                contexts_used=0,
                query=query,
            )
        
        # ✅ Check for translation request
        lang_context = get_language_context(
            query=query,
            history=history,
            user_language_preference=language_preference
        )
        
        if lang_context.is_translation_request and history:
            logger.info(f"Translation request detected: translating to {lang_context.target_language}")
            return self._handle_translation_request(
                query=query,
                history=history,
                lang_context=lang_context,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
            )
        
        # Retrieve contexts with improved settings
        contexts = self.retrieve_contexts(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            search_filter=search_filter,
        )
        
        if not contexts:
            logger.warning(f"No contexts found for query (threshold={score_threshold}): {query[:50]}...")
            
            # Return empty context feedback with language-aware message
            lang_context = get_language_context(
                query=query,
                history=history,
                user_language_preference=language_preference
            )
            
            if lang_context.response_language == "vi":
                empty_message = (
                    "⚠️ Không tìm thấy thông tin liên quan trong tài liệu.\n\n"
                    "Vui lòng thử:\n"
                    "- Đặt câu hỏi cụ thể hơn\n"
                    "- Sử dụng từ khóa khác\n"
                    "- Kiểm tra xem tài liệu đã được upload chưa"
                )
            else:
                empty_message = (
                    "⚠️ No relevant information found in the documents.\n\n"
                    "Please try:\n"
                    "- Asking a more specific question\n"
                    "- Using different keywords\n"
                    "- Checking if documents have been uploaded"
                )
            
            return RAGResponse(
                answer=empty_message,
                citations=[],
                usage=TokenUsage(input_tokens=0, output_tokens=0),
                model=self.claude_service.model_alias,
                contexts_used=0,
                query=query,
            )
        
        # CRITICAL: Sort contexts by score and reassign citation IDs
        # This ensures [1] = highest score, [2] = second highest, etc.
        contexts = self.prompt_builder.rank_contexts_by_score(contexts)
        
        logger.info(
            f"Retrieved {len(contexts)} contexts (sorted by score): "
            f"{[(c.citation_id, f'{c.score:.1f}%') for c in contexts]}"
        )
        
        # Generate answer with language awareness
        if stream:
            return self.generate_answer_stream(
                query=query,
                contexts=contexts,
                history=history,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        else:
            return self.generate_answer(
                query=query,
                contexts=contexts,
                history=history,
                max_tokens=max_tokens,
                temperature=temperature,
                language_preference=language_preference,
            )
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all components."""
        return {
            "qdrant": self.vector_store.health_check(),
            "claude": self.claude_service.health_check(),
            "embeddings": True,  # Embedding service doesn't have health check
        }


# Convenience function
def create_rag_service(
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    region_name: str = "ap-southeast-1",
    model: str = "sonnet",
    template: str = "default",
) -> RAGService:
    """Create RAG service instance."""
    template_enum = PromptTemplate(template)
    return RAGService(
        qdrant_host=qdrant_host,
        qdrant_port=qdrant_port,
        region_name=region_name,
        model=model,
        template=template_enum,
    )
