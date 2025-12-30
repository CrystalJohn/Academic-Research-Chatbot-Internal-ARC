"""
Task #19: Qdrant Vector Database Client
Task #25: Enhanced Vector Search for RAG

Provides interface for storing and searching document embeddings.
Collection: documents | Dimensions: 1024 | Metric: Cosine
"""

import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
    PayloadSchemaType,
    BinaryQuantization,
    BinaryQuantizationConfig,
    ScalarQuantization,
    ScalarQuantizationConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result from Qdrant."""
    id: str
    score: float
    doc_id: str
    chunk_index: int
    page: int
    text: str
    is_table: bool
    # New metadata fields
    filename: str = ""
    file_type: str = ""
    title: str = ""
    section_title: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "score": self.score,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "text": self.text,
            "is_table": self.is_table,
            "filename": self.filename,
            "file_type": self.file_type,
            "title": self.title,
            "section_title": self.section_title,
        }


@dataclass
class RAGContext:
    """Context chunk for RAG with citation info."""
    text: str
    doc_id: str
    page: int
    chunk_index: int
    score: float
    citation_id: int = 0  # [1], [2], etc.
    is_table: bool = False
    # New metadata fields
    filename: str = ""
    file_type: str = ""
    title: str = ""
    section_title: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "doc_id": self.doc_id,
            "page": self.page,
            "chunk_index": self.chunk_index,
            "score": self.score,
            "citation_id": self.citation_id,
            "is_table": self.is_table,
            "filename": self.filename,
            "file_type": self.file_type,
            "title": self.title,
            "section_title": self.section_title,
        }


@dataclass 
class SearchFilter:
    """Filter options for vector search."""
    doc_ids: Optional[List[str]] = None  # Filter by multiple doc IDs
    page_min: Optional[int] = None  # Minimum page number
    page_max: Optional[int] = None  # Maximum page number
    is_table: Optional[bool] = None  # Filter tables only or text only
    exclude_doc_ids: Optional[List[str]] = None  # Exclude specific docs
    file_types: Optional[List[str]] = None  # Filter by file type (.pdf, .md, .ipynb)


class QdrantVectorStore:
    """
    Qdrant vector store for document embeddings.
    
    Requirements:
    - 6.1: Collection with 1536-dim vectors (Titan) and cosine similarity
    - 6.2: Payload indexing for doc_id, page, is_table
    - 6.3: Persist vectors to disk
    - 6.4: Recover vectors after restart
    """
    
    COLLECTION_NAME = "documents"
    VECTOR_SIZE = 1024  # Cohere Embed Multilingual v3 output size
    
    # Binary Quantization settings for Cohere Embed v3
    # Cohere v3 is specifically designed to work well with BQ
    # Benefits: 32x memory reduction, 40x faster search, ~96-98% recall
    USE_BINARY_QUANTIZATION = True
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        grpc_port: int = 6334,
        prefer_grpc: bool = False,
    ):
        """
        Initialize Qdrant client.
        
        Args:
            host: Qdrant server host
            port: Qdrant REST API port
            grpc_port: Qdrant gRPC port
            prefer_grpc: Use gRPC instead of REST
        """
        self.host = host
        self.port = port
        self.grpc_port = grpc_port
        
        self.client = QdrantClient(
            host=host,
            port=port,
            grpc_port=grpc_port,
            prefer_grpc=prefer_grpc,
        )
        
        logger.info(f"Connected to Qdrant at {host}:{port}")
    
    def ensure_collection(self) -> bool:
        """
        Ensure collection exists with correct configuration.
        Creates collection if it doesn't exist.
        
        Returns:
            True if collection exists or was created
        """
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.COLLECTION_NAME in collection_names:
                logger.info(f"Collection '{self.COLLECTION_NAME}' already exists")
                return True
            
            # Create collection with 1024-dim vectors and cosine similarity
            # Binary Quantization for Cohere Embed v3:
            # - 32x memory reduction (4KB -> 128 bytes per vector)
            # - 40x faster search with minimal recall loss (~96-98%)
            # - Cohere v3 is specifically optimized for BQ via Matryoshka training
            quantization_config = None
            if self.USE_BINARY_QUANTIZATION:
                quantization_config = BinaryQuantization(
                    binary=BinaryQuantizationConfig(
                        always_ram=True,  # Keep quantized vectors in RAM for speed
                    )
                )
                logger.info("Binary Quantization enabled for Cohere Embed v3")
            
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
                quantization_config=quantization_config,
            )
            
            # Create payload indexes for filtering
            self._create_payload_indexes()
            
            logger.info(f"Created collection '{self.COLLECTION_NAME}'")
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")
            return False
    
    def _create_payload_indexes(self):
        """Create payload indexes for efficient filtering."""
        try:
            # Index for doc_id (keyword for exact match)
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="doc_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            
            # Index for page (integer)
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="page",
                field_schema=PayloadSchemaType.INTEGER,
            )
            
            # Index for is_table (bool as keyword)
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="is_table",
                field_schema=PayloadSchemaType.BOOL,
            )
            
            # Index for file_type (keyword for filtering by .pdf, .md, .ipynb)
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="file_type",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            
            # Index for filename (keyword for exact match)
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="filename",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            
            logger.info("Created payload indexes")
            
        except Exception as e:
            logger.warning(f"Error creating indexes (may already exist): {e}")
    
    def upsert_vectors(
        self,
        doc_id: str,
        texts: List[str],
        vectors: List[List[float]],
        pages: Optional[List[int]] = None,
        is_tables: Optional[List[bool]] = None,
        # New metadata fields
        filename: Optional[str] = None,
        file_type: Optional[str] = None,
        title: Optional[str] = None,
        section_titles: Optional[List[str]] = None,
    ) -> int:
        """
        Upsert document vectors to Qdrant.
        
        Args:
            doc_id: Document ID
            texts: List of chunk texts
            vectors: List of embedding vectors (1024-dim each)
            pages: Optional list of page numbers
            is_tables: Optional list of is_table flags
            filename: Original filename (stored in all chunks for filtering)
            file_type: File extension (.pdf, .md, .ipynb)
            title: Document title
            section_titles: Optional list of section titles per chunk
            
        Returns:
            Number of vectors upserted
        """
        if len(texts) != len(vectors):
            raise ValueError("texts and vectors must have same length")
        
        if not vectors:
            return 0
        
        # Validate vector dimensions
        for i, vec in enumerate(vectors):
            if len(vec) != self.VECTOR_SIZE:
                raise ValueError(
                    f"Vector {i} has {len(vec)} dimensions, expected {self.VECTOR_SIZE}"
                )
        
        # Default values
        if pages is None:
            pages = [1] * len(texts)
        if is_tables is None:
            is_tables = [False] * len(texts)
        if section_titles is None:
            section_titles = [""] * len(texts)
        
        # Create points
        points = []
        for i, (text, vector, page, is_table) in enumerate(
            zip(texts, vectors, pages, is_tables)
        ):
            point_id = str(uuid.uuid4())
            
            # Build payload with all metadata
            payload = {
                "doc_id": doc_id,
                "chunk_index": i,
                "page": page,
                "text": text,
                "is_table": is_table,
            }
            
            # Add optional metadata if provided
            if filename:
                payload["filename"] = filename
            if file_type:
                payload["file_type"] = file_type
            if title:
                payload["title"] = title
            if section_titles and i < len(section_titles) and section_titles[i]:
                payload["section_title"] = section_titles[i]
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )
        
        # Upsert in batches
        batch_size = 100
        total_upserted = 0
        
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=batch,
                wait=True,  # Wait for persistence
            )
            total_upserted += len(batch)
        
        logger.info(f"Upserted {total_upserted} vectors for doc_id={doc_id}")
        return total_upserted
    
    def _build_filter(
        self,
        search_filter: Optional[SearchFilter] = None,
        doc_id: Optional[str] = None,
    ) -> Optional[Filter]:
        """
        Build Qdrant filter from SearchFilter or simple doc_id.
        
        Args:
            search_filter: Advanced filter options
            doc_id: Simple single doc_id filter (legacy support)
            
        Returns:
            Qdrant Filter object or None
        """
        must_conditions = []
        must_not_conditions = []
        
        # Legacy single doc_id support
        if doc_id and not search_filter:
            return Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id),
                    )
                ]
            )
        
        if not search_filter:
            return None
        
        # Multiple doc_ids filter
        if search_filter.doc_ids:
            if len(search_filter.doc_ids) == 1:
                must_conditions.append(
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=search_filter.doc_ids[0]),
                    )
                )
            else:
                must_conditions.append(
                    FieldCondition(
                        key="doc_id",
                        match=MatchAny(any=search_filter.doc_ids),
                    )
                )
        
        # Exclude doc_ids
        if search_filter.exclude_doc_ids:
            for exclude_id in search_filter.exclude_doc_ids:
                must_not_conditions.append(
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=exclude_id),
                    )
                )
        
        # Page range filter
        if search_filter.page_min is not None or search_filter.page_max is not None:
            must_conditions.append(
                FieldCondition(
                    key="page",
                    range=Range(
                        gte=search_filter.page_min,
                        lte=search_filter.page_max,
                    ),
                )
            )
        
        # Table filter
        if search_filter.is_table is not None:
            must_conditions.append(
                FieldCondition(
                    key="is_table",
                    match=MatchValue(value=search_filter.is_table),
                )
            )
        
        # File type filter
        if search_filter.file_types:
            if len(search_filter.file_types) == 1:
                must_conditions.append(
                    FieldCondition(
                        key="file_type",
                        match=MatchValue(value=search_filter.file_types[0]),
                    )
                )
            else:
                must_conditions.append(
                    FieldCondition(
                        key="file_type",
                        match=MatchAny(any=search_filter.file_types),
                    )
                )
        
        if not must_conditions and not must_not_conditions:
            return None
        
        return Filter(
            must=must_conditions if must_conditions else None,
            must_not=must_not_conditions if must_not_conditions else None,
        )

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        doc_id: Optional[str] = None,
        score_threshold: float = 0.0,
        search_filter: Optional[SearchFilter] = None,
    ) -> List[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector (1024-dim)
            top_k: Number of results to return
            doc_id: Optional filter by document ID (legacy, use search_filter instead)
            score_threshold: Minimum similarity score (0.0 to 1.0 for cosine)
            search_filter: Advanced filter options
            
        Returns:
            List of SearchResult objects sorted by score descending
        """
        if len(query_vector) != self.VECTOR_SIZE:
            raise ValueError(
                f"Query vector has {len(query_vector)} dimensions, "
                f"expected {self.VECTOR_SIZE}"
            )
        
        # Build filter
        query_filter = self._build_filter(search_filter, doc_id)
        
        # Search using query_points (qdrant-client >= 1.7)
        # With Binary Quantization: use oversampling + rescore for better accuracy
        # - First pass: fast BQ search with 2x candidates
        # - Second pass: rescore with original vectors for precision
        search_params = None
        if self.USE_BINARY_QUANTIZATION:
            search_params = models.SearchParams(
                quantization=models.QuantizationSearchParams(
                    rescore=True,  # Rescore with original vectors
                    oversampling=2.0,  # Fetch 2x candidates before rescoring
                )
            )
        
        results = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
            search_params=search_params,
        )
        
        # Convert to SearchResult
        search_results = []
        for hit in results.points:
            payload = hit.payload or {}
            search_results.append(
                SearchResult(
                    id=str(hit.id),
                    score=hit.score,
                    doc_id=payload.get("doc_id", ""),
                    chunk_index=payload.get("chunk_index", 0),
                    page=payload.get("page", 1),
                    text=payload.get("text", ""),
                    is_table=payload.get("is_table", False),
                    filename=payload.get("filename", ""),
                    file_type=payload.get("file_type", ""),
                    title=payload.get("title", ""),
                    section_title=payload.get("section_title", ""),
                )
            )
        
        return search_results
    
    def search_for_rag(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: float = 0.3,
        search_filter: Optional[SearchFilter] = None,
        deduplicate: bool = True,
    ) -> List[RAGContext]:
        """
        Search optimized for RAG context retrieval.
        
        Returns results formatted for RAG with citation IDs and deduplication.
        
        Args:
            query_vector: Query embedding vector (1024-dim)
            top_k: Number of context chunks to return
            score_threshold: Minimum relevance score (default 0.3 for quality)
            search_filter: Filter options
            deduplicate: Remove duplicate/overlapping chunks from same doc
            
        Returns:
            List of RAGContext objects with citation IDs [1], [2], etc.
        """
        # Get more results if deduplicating
        fetch_k = top_k * 2 if deduplicate else top_k
        
        results = self.search(
            query_vector=query_vector,
            top_k=fetch_k,
            score_threshold=score_threshold,
            search_filter=search_filter,
        )
        
        if deduplicate:
            results = self._deduplicate_results(results)
        
        # Limit to top_k after deduplication
        results = results[:top_k]
        
        # Convert to RAGContext with citation IDs
        # Score is converted to percentage (0.56 -> 56.0) for frontend display
        rag_contexts = []
        for i, result in enumerate(results):
            rag_contexts.append(
                RAGContext(
                    text=result.text,
                    doc_id=result.doc_id,
                    page=result.page,
                    chunk_index=result.chunk_index,
                    score=result.score * 100,  # Convert to percentage for display
                    citation_id=i + 1,  # 1-indexed for [1], [2], etc.
                    is_table=result.is_table,
                    filename=result.filename,
                    file_type=result.file_type,
                    title=result.title,
                    section_title=result.section_title,
                )
            )
        
        return rag_contexts
    
    def _deduplicate_results(
        self,
        results: List[SearchResult],
        overlap_threshold: int = 1,
        similarity_threshold: float = 0.7,
    ) -> List[SearchResult]:
        """
        Remove overlapping chunks from same document with text similarity check.
        
        Improved deduplication that:
        1. Sorts by score first (process high-score chunks first)
        2. Checks chunk proximity AND text similarity
        3. Only removes if both conditions are met
        
        Args:
            results: Search results to deduplicate
            overlap_threshold: Max chunk_index difference to consider overlap
            similarity_threshold: Min text similarity (0-1) to consider duplicate
            
        Returns:
            Deduplicated results
        """
        from difflib import SequenceMatcher
        
        if not results:
            return results
        
        # Sort by score descending (process high-score first)
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
        
        deduplicated = []
        
        for result in sorted_results:
            is_duplicate = False
            
            for existing in deduplicated:
                # Only check chunks from same document
                if result.doc_id != existing.doc_id:
                    continue
                
                # Check chunk proximity
                chunk_distance = abs(result.chunk_index - existing.chunk_index)
                if chunk_distance > overlap_threshold:
                    continue
                
                # ✅ FIX: Check text similarity before marking as duplicate
                # Compare first 500 chars for efficiency
                similarity = SequenceMatcher(
                    None,
                    result.text[:500],
                    existing.text[:500]
                ).ratio()
                
                if similarity > similarity_threshold:
                    # True duplicate - similar text in adjacent chunks
                    is_duplicate = True
                    logger.debug(
                        f"Removing duplicate: chunk {result.chunk_index} "
                        f"(score {result.score:.2f}) similar to {existing.chunk_index} "
                        f"(score {existing.score:.2f}), similarity: {similarity:.2f}"
                    )
                    break
            
            if not is_duplicate:
                deduplicated.append(result)
        
        return deduplicated
    
    def get_context_window(
        self,
        doc_id: str,
        chunk_index: int,
        window_size: int = 1,
    ) -> List[SearchResult]:
        """
        Get surrounding chunks for expanded context.
        
        Useful for getting more context around a relevant chunk.
        
        Args:
            doc_id: Document ID
            chunk_index: Center chunk index
            window_size: Number of chunks before/after to include
            
        Returns:
            List of chunks in order (before, center, after)
        """
        # Calculate range
        start_idx = max(0, chunk_index - window_size)
        end_idx = chunk_index + window_size
        
        # Scroll through all chunks for this doc
        results = []
        offset = None
        
        while True:
            scroll_result = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id),
                        ),
                        FieldCondition(
                            key="chunk_index",
                            range=Range(gte=start_idx, lte=end_idx),
                        ),
                    ]
                ),
                limit=100,
                offset=offset,
                with_payload=True,
            )
            
            points, offset = scroll_result
            
            for point in points:
                payload = point.payload or {}
                results.append(
                    SearchResult(
                        id=str(point.id),
                        score=1.0,  # No score for scroll
                        doc_id=payload.get("doc_id", ""),
                        chunk_index=payload.get("chunk_index", 0),
                        page=payload.get("page", 1),
                        text=payload.get("text", ""),
                        is_table=payload.get("is_table", False),
                    )
                )
            
            if offset is None:
                break
        
        # Sort by chunk_index
        results.sort(key=lambda x: x.chunk_index)
        return results
    
    def delete_document(self, doc_id: str) -> int:
        """
        Delete all vectors for a document.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            Number of points deleted
        """
        # Get count before delete
        count_before = self.get_document_count(doc_id)
        
        # Delete by filter
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
        
        logger.info(f"Deleted {count_before} vectors for doc_id={doc_id}")
        return count_before
    
    def get_document_count(self, doc_id: str) -> int:
        """Get number of vectors for a document."""
        result = self.client.count(
            collection_name=self.COLLECTION_NAME,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id),
                    )
                ]
            ),
        )
        return result.count
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "name": self.COLLECTION_NAME,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value,
                "vector_size": self.VECTOR_SIZE,
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {}
    
    def get_all_points(self, limit: int = 10000) -> List[Dict]:
        """
        Get all points from collection for BM25 indexing.
        
        Layer 3: Hybrid Retrieval support.
        
        Args:
            limit: Maximum number of points to retrieve
            
        Returns:
            List of points with id and payload
        """
        try:
            all_points = []
            offset = None
            
            while len(all_points) < limit:
                batch_limit = min(100, limit - len(all_points))
                
                scroll_result = self.client.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=batch_limit,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,  # Don't need vectors for BM25
                )
                
                points, offset = scroll_result
                
                for point in points:
                    all_points.append({
                        "id": str(point.id),
                        "payload": point.payload or {}
                    })
                
                if offset is None or len(points) == 0:
                    break
            
            logger.info(f"Retrieved {len(all_points)} points for BM25 indexing")
            return all_points
            
        except Exception as e:
            logger.error(f"Error getting all points: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check if Qdrant is healthy."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
    
    def enable_binary_quantization(self) -> bool:
        """
        Enable Binary Quantization on existing collection.
        
        Use this to migrate an existing collection to use BQ.
        This will quantize existing vectors in-place.
        
        Benefits for Cohere Embed v3:
        - 32x memory reduction
        - 40x faster search
        - ~96-98% recall (minimal loss)
        
        Returns:
            True if successful
        """
        try:
            self.client.update_collection(
                collection_name=self.COLLECTION_NAME,
                quantization_config=BinaryQuantization(
                    binary=BinaryQuantizationConfig(
                        always_ram=True,
                    )
                ),
            )
            logger.info(f"Binary Quantization enabled on collection '{self.COLLECTION_NAME}'")
            return True
        except Exception as e:
            logger.error(f"Failed to enable Binary Quantization: {e}")
            return False
    
    def get_quantization_info(self) -> Dict[str, Any]:
        """Get current quantization configuration."""
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            quant_config = info.config.quantization_config
            
            if quant_config is None:
                return {"enabled": False, "type": None}
            
            # Check type of quantization
            if hasattr(quant_config, 'binary'):
                return {
                    "enabled": True,
                    "type": "binary",
                    "always_ram": quant_config.binary.always_ram if quant_config.binary else False,
                }
            elif hasattr(quant_config, 'scalar'):
                return {
                    "enabled": True,
                    "type": "scalar",
                }
            
            return {"enabled": True, "type": "unknown"}
            
        except Exception as e:
            logger.error(f"Error getting quantization info: {e}")
            return {"enabled": False, "error": str(e)}


# Convenience function for creating store
def create_qdrant_store(
    host: str = "localhost",
    port: int = 6333,
) -> QdrantVectorStore:
    """Create and initialize Qdrant vector store."""
    store = QdrantVectorStore(host=host, port=port)
    store.ensure_collection()
    return store
