"""
Language Context Service for Bilingual RAG System

Handles:
- Language detection for queries
- Conversation language tracking
- Response language control
- Language switching detection
"""

from typing import List, Dict, Optional, Literal
from dataclasses import dataclass

# Vietnamese character set for language detection
VIETNAMESE_CHARS = set(
    'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    'ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ'
)

# Vietnamese keywords (common words that indicate Vietnamese)
VI_KEYWORDS = {
    'là', 'của', 'và', 'có', 'được', 'trong', 'cho', 'với', 'này', 'đó',
    'các', 'những', 'như', 'để', 'khi', 'về', 'giải', 'thích', 'làm', 'sao',
    'gì', 'ai', 'đâu', 'nào', 'tại', 'vì', 'nếu', 'thì', 'mà', 'nhưng',
    'hoặc', 'hay', 'cũng', 'đã', 'sẽ', 'đang', 'rồi', 'chưa', 'không',
    'bạn', 'tôi', 'chúng', 'họ', 'nó', 'anh', 'chị', 'em'
}

# English keywords
EN_KEYWORDS = {
    'what', 'how', 'why', 'when', 'where', 'who', 'which',
    'is', 'are', 'was', 'were', 'the', 'a', 'an', 'this', 'that', 'these',
    'explain', 'describe', 'tell', 'show', 'give', 'define', 'list',
    'can', 'could', 'would', 'should', 'will', 'do', 'does', 'did',
    'please', 'help', 'need', 'want', 'like', 'know', 'think', 'understand'
}

# Translation/follow-up request patterns
TRANSLATION_PATTERNS_VI = [
    'dịch sang tiếng việt', 'dịch sang tiếng anh', 'dịch lại',
    'nói bằng tiếng việt', 'nói bằng tiếng anh', 'trả lời bằng tiếng việt',
    'trả lời bằng tiếng anh', 'chuyển sang tiếng việt', 'chuyển sang tiếng anh',
    'viết lại bằng tiếng việt', 'viết lại bằng tiếng anh'
]

TRANSLATION_PATTERNS_EN = [
    'translate to vietnamese', 'translate to english', 'translate it',
    'say it in vietnamese', 'say it in english', 'respond in vietnamese',
    'respond in english', 'switch to vietnamese', 'switch to english',
    'rewrite in vietnamese', 'rewrite in english', 'in vietnamese please',
    'in english please'
]


@dataclass
class LanguageContext:
    """Track language context throughout conversation"""
    query_language: str  # Detected from current query
    response_language: str  # Language to respond in
    conversation_language: Optional[str] = None  # Primary language of conversation
    user_preference: Optional[str] = None  # Explicit user preference
    language_switched: bool = False  # Whether language was switched
    is_translation_request: bool = False  # Whether this is a translation/follow-up request
    target_language: Optional[str] = None  # Target language for translation


def is_translation_request(text: str) -> tuple[bool, Optional[str]]:
    """
    Check if query is a translation/language switch request.
    
    Args:
        text: Query text to analyze
        
    Returns:
        Tuple of (is_translation, target_language)
    """
    text_lower = text.lower().strip()
    
    # Check Vietnamese patterns
    for pattern in TRANSLATION_PATTERNS_VI:
        if pattern in text_lower:
            if 'tiếng anh' in text_lower or 'english' in text_lower:
                return True, "en"
            elif 'tiếng việt' in text_lower or 'vietnamese' in text_lower:
                return True, "vi"
            return True, "vi"  # Default to Vietnamese for Vietnamese patterns
    
    # Check English patterns
    for pattern in TRANSLATION_PATTERNS_EN:
        if pattern in text_lower:
            if 'vietnamese' in text_lower or 'tiếng việt' in text_lower:
                return True, "vi"
            elif 'english' in text_lower or 'tiếng anh' in text_lower:
                return True, "en"
            return True, "en"  # Default to English for English patterns
    
    return False, None


def detect_query_language(text: str) -> str:
    """
    Improved language detection with keyword analysis.
    
    Args:
        text: Query text to analyze
        
    Returns:
        "vi" for Vietnamese, "en" for English
    """
    if not text or len(text) < 3:
        return "en"
    
    text_lower = text.lower()
    
    # Count Vietnamese characters
    vi_char_count = sum(1 for c in text_lower if c in VIETNAMESE_CHARS)
    ratio = vi_char_count / len(text) if len(text) > 0 else 0
    
    # Count keywords
    words = set(text_lower.split())
    vi_keyword_count = len(words & VI_KEYWORDS)
    en_keyword_count = len(words & EN_KEYWORDS)
    
    # Decision logic (priority order)
    
    # 1. High Vietnamese character ratio (>15%)
    if ratio > 0.15:
        return "vi"
    
    # 2. Multiple Vietnamese keywords (>=2)
    if vi_keyword_count >= 2:
        return "vi"
    
    # 3. English keywords with no Vietnamese
    if en_keyword_count >= 2 and vi_keyword_count == 0 and ratio < 0.02:
        return "en"
    
    # 4. Some Vietnamese characters with Vietnamese keywords
    if ratio > 0.05 and vi_keyword_count > 0:
        return "vi"
    
    # 5. Single Vietnamese keyword with some Vietnamese chars
    if vi_keyword_count >= 1 and ratio > 0.02:
        return "vi"
    
    # Default to English
    return "en"


def detect_conversation_language(history: List[Dict[str, str]]) -> str:
    """
    Detect primary language from conversation history.
    
    Args:
        history: List of conversation messages
        
    Returns:
        Primary language of conversation
    """
    if not history:
        return "en"
    
    # Analyze last 3 messages for recent language trend
    recent_messages = history[-3:]
    vi_count = 0
    en_count = 0
    
    for msg in recent_messages:
        content = msg.get("content", "")
        lang = detect_query_language(content)
        if lang == "vi":
            vi_count += 1
        else:
            en_count += 1
    
    return "vi" if vi_count > en_count else "en"


def get_language_context(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_language_preference: Optional[str] = None
) -> LanguageContext:
    """
    Intelligent language detection with conversation context.
    
    Priority:
    1. Translation request detection (highest priority)
    2. Explicit user preference (if set)
    3. Conversation language (from history)
    4. Current query language
    
    Args:
        query: Current user query
        history: Conversation history
        user_language_preference: Explicit user preference ("vi", "en", or None for auto)
        
    Returns:
        LanguageContext with detected and response languages
    """
    # Detect current query language
    query_lang = detect_query_language(query)
    
    # ✅ Check for translation request FIRST
    is_trans, target_lang = is_translation_request(query)
    if is_trans and target_lang:
        return LanguageContext(
            query_language=query_lang,
            response_language=target_lang,
            conversation_language=target_lang,
            language_switched=True,
            is_translation_request=True,
            target_language=target_lang
        )
    
    # Check user preference
    if user_language_preference and user_language_preference in ("vi", "en"):
        return LanguageContext(
            query_language=query_lang,
            response_language=user_language_preference,
            user_preference=user_language_preference,
            language_switched=False,
            is_translation_request=False
        )
    
    # Analyze conversation history
    if history and len(history) > 0:
        conversation_lang = detect_conversation_language(history)
        
        # If user switches language explicitly, respect it
        if query_lang != conversation_lang:
            return LanguageContext(
                query_language=query_lang,
                response_language=query_lang,  # Switch to new language
                conversation_language=query_lang,
                language_switched=True,
                is_translation_request=False
            )
        
        # Continue in conversation language
        return LanguageContext(
            query_language=query_lang,
            response_language=conversation_lang,
            conversation_language=conversation_lang,
            language_switched=False,
            is_translation_request=False
        )
    
    # First message: use query language
    return LanguageContext(
        query_language=query_lang,
        response_language=query_lang,
        conversation_language=query_lang,
        language_switched=False,
        is_translation_request=False
    )


def get_language_instruction(lang_context: LanguageContext) -> str:
    """
    Generate explicit language instruction for LLM.
    
    Args:
        lang_context: Language context
        
    Returns:
        Language instruction string to include in prompt
    """
    if lang_context.response_language == "vi":
        return """
⚠️ LANGUAGE REQUIREMENT: You MUST respond in Vietnamese (Tiếng Việt).
- Trả lời hoàn toàn bằng tiếng Việt
- Thuật ngữ kỹ thuật giữ nguyên tiếng Anh trong ngoặc nếu cần
"""
    else:
        return """
⚠️ LANGUAGE REQUIREMENT: You MUST respond in English.
- Respond entirely in English
- Define technical terms when first mentioned
"""


def get_language_switch_message(lang_context: LanguageContext) -> Optional[str]:
    """
    Generate message when language switch is detected.
    
    Args:
        lang_context: Language context
        
    Returns:
        Switch notification message or None
    """
    if not lang_context.language_switched:
        return None
    
    if lang_context.response_language == "vi":
        return "ℹ️ Tôi nhận thấy bạn chuyển sang tiếng Việt. Tôi sẽ trả lời bằng tiếng Việt."
    else:
        return "ℹ️ I noticed you switched to English. I'll respond in English."
