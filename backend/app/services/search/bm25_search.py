"""
Layer 3: BM25 Search for Hybrid Retrieval

BM25 (Best Matching 25) provides keyword-based search to complement
vector semantic search. This helps with:
- Exact term matching (e.g., "A+" grade)
- Acronyms and specific terminology
- Cases where semantic similarity fails

Combined with vector search = Hybrid Retrieval
"""

import re
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class BM25Result:
    """Result from BM25 search."""
    chunk_id: str
    text: str
    score: float
    doc_id: str
    metadata: Dict


class BM25Index:
    """
    BM25 index for keyword-based search.
    
    BM25 formula:
    score(D,Q) = Σ IDF(qi) * (f(qi,D) * (k1 + 1)) / (f(qi,D) + k1 * (1 - b + b * |D|/avgdl))
    
    Where:
    - f(qi,D) = term frequency of qi in document D
    - |D| = length of document D
    - avgdl = average document length
    - k1, b = tuning parameters (typically k1=1.5, b=0.75)
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 index.
        
        Args:
            k1: Term frequency saturation parameter (1.2-2.0)
            b: Length normalization parameter (0-1, typically 0.75)
        """
        self.k1 = k1
        self.b = b
        
        # Index data
        self.documents: Dict[str, Dict] = {}  # chunk_id -> {text, doc_id, metadata}
        self.doc_lengths: Dict[str, int] = {}  # chunk_id -> token count
        self.avg_doc_length: float = 0
        self.doc_count: int = 0
        self.total_length: int = 0  # Running total for O(1) avg calculation
        
        # Inverted index: term -> {chunk_id: term_frequency}
        self.inverted_index: Dict[str, Dict[str, int]] = {}
        
        # Document frequency: term -> number of docs containing term
        self.doc_freq: Dict[str, int] = {}
        
        # IDF cache: term -> pre-computed IDF score
        self.idf_cache: Dict[str, float] = {}
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing.
        
        - Lowercase
        - Split on whitespace and punctuation
        - Keep alphanumeric tokens
        - Preserve special terms like "A+", "GPA", numbers
        """
        # Lowercase
        text = text.lower()
        
        # Special handling for grade notations (A+, B-, etc.)
        # Replace + and - in grade context to preserve them
        text = re.sub(r'\b([a-f])([+-])\b', r'\1_PLUS' if '+' else r'\1_MINUS', text)
        text = re.sub(r'\b([a-f])\+', r'\1_plus', text)
        text = re.sub(r'\b([a-f])-', r'\1_minus', text)
        
        # Split on non-alphanumeric (except underscore)
        tokens = re.findall(r'[a-z0-9_]+(?:\.[0-9]+)?', text)
        
        # Restore grade notations
        tokens = [t.replace('_plus', '+').replace('_minus', '-') for t in tokens]
        
        # Filter very short tokens (except grades like "a+")
        tokens = [t for t in tokens if len(t) > 1 or t in ['a', 'b', 'c', 'd', 'f']]
        
        return tokens
    
    def add_document(
        self,
        chunk_id: str,
        text: str,
        doc_id: str = "",
        metadata: Optional[Dict] = None,
        defer_stats: bool = False
    ) -> None:
        """
        Add a document (chunk) to the index.
        
        Args:
            chunk_id: Unique identifier for the chunk
            text: Text content
            doc_id: Parent document ID
            metadata: Additional metadata
            defer_stats: If True, skip avg_doc_length calculation (for batch operations)
        """
        tokens = self.tokenize(text)
        
        # Store document (tokens not stored - already in inverted_index)
        self.documents[chunk_id] = {
            "text": text,
            "doc_id": doc_id,
            "metadata": metadata or {}
        }
        
        # Update document length
        self.doc_lengths[chunk_id] = len(tokens)
        self.doc_count += 1
        self.total_length += len(tokens)
        
        # Update average document length - O(1) instead of O(n)
        # Skip if defer_stats=True (for batch operations)
        if not defer_stats:
            self.avg_doc_length = self.total_length / self.doc_count
            # Update IDF cache for single document add
            self._update_idf_cache()
        
        # Count term frequencies
        term_freq = Counter(tokens)
        
        # Update inverted index and document frequency
        for term, freq in term_freq.items():
            if term not in self.inverted_index:
                self.inverted_index[term] = {}
                self.doc_freq[term] = 0
            
            if chunk_id not in self.inverted_index[term]:
                self.doc_freq[term] += 1
            
            self.inverted_index[term][chunk_id] = freq
    
    def add_documents(
        self,
        documents: List[Dict]
    ) -> None:
        """
        Add multiple documents to the index (optimized batch operation).
        
        Args:
            documents: List of {chunk_id, text, doc_id, metadata}
        """
        # Batch add with deferred stats calculation
        for doc in documents:
            self.add_document(
                chunk_id=doc.get("chunk_id", str(len(self.documents))),
                text=doc["text"],
                doc_id=doc.get("doc_id", ""),
                metadata=doc.get("metadata", {}),
                defer_stats=True  # Defer avg calculation
            )
        
        # Calculate average once at the end - O(1) instead of O(n)
        if self.doc_count > 0:
            self.avg_doc_length = self.total_length / self.doc_count
        
        # Pre-compute IDF cache for fast search
        self._update_idf_cache()
        
        logger.info(f"Indexed {len(documents)} documents. Total: {self.doc_count}")
    
    def _update_idf_cache(self) -> None:
        """
        Pre-compute IDF scores for all terms.
        Called after batch indexing to eliminate log() calculations during search.
        """
        self.idf_cache.clear()
        for term, df in self.doc_freq.items():
            # IDF formula with smoothing
            self.idf_cache[term] = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
    
    def _idf(self, term: str) -> float:
        """
        Get pre-computed IDF (Inverse Document Frequency) for a term.
        Returns cached value for O(1) lookup.
        """
        return self.idf_cache.get(term, 0.0)
    
    def _score_document(self, chunk_id: str, query_tokens: List[str]) -> float:
        """Calculate BM25 score for a document given query tokens."""
        if chunk_id not in self.documents:
            return 0
        
        doc_length = self.doc_lengths[chunk_id]
        score = 0
        
        for term in query_tokens:
            if term not in self.inverted_index:
                continue
            
            if chunk_id not in self.inverted_index[term]:
                continue
            
            # Term frequency in document
            tf = self.inverted_index[term][chunk_id]
            
            # IDF
            idf = self._idf(term)
            
            # BM25 score component
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
            
            score += idf * (numerator / denominator)
        
        return score
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        score_threshold: float = 0.0
    ) -> List[BM25Result]:
        """
        Search for documents matching the query.
        
        Args:
            query: Search query
            top_k: Number of results to return
            score_threshold: Minimum score threshold
            
        Returns:
            List of BM25Result sorted by score descending
        """
        query_tokens = self.tokenize(query)
        
        if not query_tokens:
            return []
        
        # Find candidate documents (those containing at least one query term)
        candidates = set()
        for term in query_tokens:
            if term in self.inverted_index:
                candidates.update(self.inverted_index[term].keys())
        
        # Score all candidates
        results = []
        for chunk_id in candidates:
            score = self._score_document(chunk_id, query_tokens)
            
            if score >= score_threshold:
                doc = self.documents[chunk_id]
                results.append(BM25Result(
                    chunk_id=chunk_id,
                    text=doc["text"],
                    score=score,
                    doc_id=doc["doc_id"],
                    metadata=doc["metadata"]
                ))
        
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:top_k]
    
    def get_tokens(self, chunk_id: str) -> List[str]:
        """
        Reconstruct tokens from document text.
        Helper method if tokens are needed after indexing.
        """
        if chunk_id not in self.documents:
            return []
        return self.tokenize(self.documents[chunk_id]["text"])
    
    def clear(self) -> None:
        """Clear the index."""
        self.documents.clear()
        self.doc_lengths.clear()
        self.inverted_index.clear()
        self.doc_freq.clear()
        self.idf_cache.clear()
        self.avg_doc_length = 0
        self.doc_count = 0
        self.total_length = 0


class HybridRetriever:
    """
    Hybrid retrieval combining BM25 and Vector search.
    
    Strategy:
    1. Run BM25 search (keyword matching)
    2. Run Vector search (semantic similarity)
    3. Combine scores using Reciprocal Rank Fusion (RRF)
    
    RRF formula: score = Σ 1/(k + rank_i)
    Where k is a constant (typically 60) and rank_i is the rank in each result list
    """
    
    def __init__(
        self,
        bm25_index: BM25Index,
        vector_search_fn,  # Function: (query, top_k) -> List[{chunk_id, score, ...}]
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid retriever.
        
        Args:
            bm25_index: BM25Index instance
            vector_search_fn: Function to perform vector search
            bm25_weight: Weight for BM25 scores (0-1)
            vector_weight: Weight for vector scores (0-1)
            rrf_k: RRF constant (higher = more emphasis on top results)
        """
        self.bm25_index = bm25_index
        self.vector_search_fn = vector_search_fn
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        bm25_top_k: int = 20,
        vector_top_k: int = 20
    ) -> List[Dict]:
        """
        Perform hybrid search.
        
        Args:
            query: Search query
            top_k: Final number of results
            bm25_top_k: Number of BM25 results to consider
            vector_top_k: Number of vector results to consider
            
        Returns:
            List of results with combined scores
        """
        # 1. BM25 search
        bm25_results = self.bm25_index.search(query, top_k=bm25_top_k)
        
        # 2. Vector search
        vector_results = self.vector_search_fn(query, vector_top_k)
        
        # 3. Build rank maps
        bm25_ranks = {r.chunk_id: i + 1 for i, r in enumerate(bm25_results)}
        vector_ranks = {r.get("chunk_id", r.get("id", str(i))): i + 1 
                       for i, r in enumerate(vector_results)}
        
        # 4. Collect all unique chunk IDs
        all_chunks = set(bm25_ranks.keys()) | set(vector_ranks.keys())
        
        # 5. Calculate RRF scores
        combined_scores = {}
        for chunk_id in all_chunks:
            rrf_score = 0
            
            # BM25 contribution
            if chunk_id in bm25_ranks:
                rrf_score += self.bm25_weight * (1 / (self.rrf_k + bm25_ranks[chunk_id]))
            
            # Vector contribution
            if chunk_id in vector_ranks:
                rrf_score += self.vector_weight * (1 / (self.rrf_k + vector_ranks[chunk_id]))
            
            combined_scores[chunk_id] = rrf_score
        
        # 6. Sort by combined score
        sorted_chunks = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 7. Build result list with metadata
        results = []
        bm25_map = {r.chunk_id: r for r in bm25_results}
        vector_map = {r.get("chunk_id", r.get("id", str(i))): r 
                     for i, r in enumerate(vector_results)}
        
        for chunk_id, combined_score in sorted_chunks[:top_k]:
            # Get metadata from either source
            if chunk_id in bm25_map:
                bm25_r = bm25_map[chunk_id]
                result = {
                    "chunk_id": chunk_id,
                    "text": bm25_r.text,
                    "doc_id": bm25_r.doc_id,
                    "metadata": bm25_r.metadata,
                    "combined_score": combined_score,
                    "bm25_rank": bm25_ranks.get(chunk_id),
                    "vector_rank": vector_ranks.get(chunk_id),
                }
            elif chunk_id in vector_map:
                vec_r = vector_map[chunk_id]
                result = {
                    "chunk_id": chunk_id,
                    "text": vec_r.get("text", ""),
                    "doc_id": vec_r.get("doc_id", ""),
                    "metadata": vec_r.get("metadata", {}),
                    "combined_score": combined_score,
                    "bm25_rank": bm25_ranks.get(chunk_id),
                    "vector_rank": vector_ranks.get(chunk_id),
                }
            else:
                continue
            
            results.append(result)
        
        logger.info(f"Hybrid search: BM25={len(bm25_results)}, Vector={len(vector_results)}, Combined={len(results)}")
        
        return results
