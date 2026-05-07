"""Cognitive vector index for semantic search over CognitiveNode content.

Bridges the gap between the CognitiveNode graph model and vector search.
Provides a four-tier embedding strategy with graceful degradation:

1. OpenAI-compatible API (LMStudio, vLLM, OpenAI, etc.)
2. sentence-transformers local model
3. BM25 TF-IDF scoring (always available, no model needed)
4. Content substring matching (last resort)

Persistence:
- When persist_dir is configured, vectors are stored in ChromaDB
  (PersistentClient) under a ``cognitive_node`` collection.
- When persist_dir is not set, vectors are held in LocalVectorStore
  (in-memory, lost on restart).

Model versioning:
- Each vector is tagged with a ``model_signature`` metadata field
  (format: ``provider:model:dimension``).
- On query, if the stored signature does not match the current config,
  the index is considered stale and a warning is logged. The caller
  should trigger a re-index.

Configuration is loaded from config.yaml (embedding section) or
environment variables (OE_EMBEDDING_* prefix).

Expected config.yaml structure::

    embedding:
      provider: openai_compatible
      base_url: http://127.0.0.1:7852/v1
      api_key: ~
      model: text-embedding-qwen3-embedding-4b
      dimension: 2560
      persist_dir: ~/.ontology_engine/data/cognitive_vectors

Environment variable overrides::

    OE_EMBEDDING_PROVIDER   → embedding.provider
    OE_EMBEDDING_BASE_URL   → embedding.base_url
    OE_EMBEDDING_API_KEY    → embedding.api_key
    OE_EMBEDDING_MODEL      → embedding.model
    OE_EMBEDDING_DIMENSION  → embedding.dimension
    OE_EMBEDDING_PERSIST_DIR → embedding.persist_dir
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.rrf_types import RetrievalResult
from ontology_engine.storage.vector.local_vector_store import LocalVectorStore

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)

DEFAULT_ST_MODEL = "all-MiniLM-L6-v2"
DEFAULT_ST_DIMENSION = 384
COGNITIVE_COLLECTION = "cognitive_node"


@dataclass
class EmbeddingConfig:
    """Embedding configuration with multi-source loading.

    Model signature (provider:model:dimension) is managed as a unit.
    If any component changes, the stored vectors are considered stale.
    """
    provider: str = "bm25"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    dimension: int = DEFAULT_ST_DIMENSION
    persist_dir: str | None = None

    @property
    def model_signature(self) -> str:
        return f"{self.provider}:{self.model or 'none'}:{self.dimension}"

    @classmethod
    def from_yaml(cls, config_path: str | Path | None = None) -> "EmbeddingConfig":
        import yaml

        raw: dict[str, Any] = {}
        candidates: list[Path] = []

        if config_path is not None:
            candidates.append(Path(config_path))

        env_path = os.environ.get("OE_CONFIG_PATH")
        if env_path:
            candidates.append(Path(env_path))

        here = Path(__file__).parent
        for _ in range(10):
            candidate = here / "config.yaml"
            if candidate.exists():
                candidates.append(candidate)
                break
            here = here.parent

        candidates.append(Path.home() / ".ontology_engine" / "config.yaml")

        for path in candidates:
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                    if isinstance(data, dict) and "embedding" in data:
                        raw = data["embedding"]
                        break
                except Exception:
                    continue

        return cls(
            provider=raw.get("provider") or os.environ.get("OE_EMBEDDING_PROVIDER", "bm25"),
            base_url=raw.get("base_url") or os.environ.get("OE_EMBEDDING_BASE_URL"),
            api_key=raw.get("api_key") or os.environ.get("OE_EMBEDDING_API_KEY"),
            model=raw.get("model") or os.environ.get("OE_EMBEDDING_MODEL"),
            dimension=int(raw.get("dimension") or os.environ.get("OE_EMBEDDING_DIMENSION", DEFAULT_ST_DIMENSION)),
            persist_dir=raw.get("persist_dir") or os.environ.get("OE_EMBEDDING_PERSIST_DIR"),
        )


def _enrich_content(content: str, memory_type: str, tags: list[str]) -> str:
    parts = []
    if memory_type:
        parts.append(f"[{memory_type}]")
    if tags:
        parts.append(" ".join(tags))
    return " ".join(parts) + " | " + content if parts else content


def _simple_tokenize(text: str) -> list[str]:
    import re
    ascii_tokens = re.findall(r'[a-zA-Z0-9_]+', text.lower())
    cjk_with_pos = [(m.group(), m.start()) for m in re.finditer(r'[\u4e00-\u9fff\u3400-\u4dbf]', text)]
    cjk_chars = [c for c, _ in cjk_with_pos]
    cjk_bigrams = []
    for i in range(len(cjk_with_pos) - 1):
        if cjk_with_pos[i][1] + 1 == cjk_with_pos[i + 1][1]:
            cjk_bigrams.append(cjk_with_pos[i][0] + cjk_with_pos[i + 1][0])
    return ascii_tokens + cjk_chars + cjk_bigrams


class CognitiveVectorIndex:
    """Vector index for CognitiveNode content with automatic embedding.

    Persistence:
        - ChromaDB PersistentClient when persist_dir is configured
        - LocalVectorStore (in-memory) otherwise

    Model versioning:
        - model_signature stored in vector metadata
        - Signature mismatch triggers warning and re-index suggestion
    """

    def __init__(
        self,
        repository: "CognitiveRepository",
        config: EmbeddingConfig | None = None,
    ) -> None:
        self._repo = repository
        self._config = config or EmbeddingConfig()
        self._vector_store: LocalVectorStore | Any = None
        self._chroma_collection: Any | None = None
        self._embedding_fn: Any | None = None
        self._api_client: Any | None = None
        self._doc_freq: Counter[str] = Counter()
        self._total_docs = 0
        self._initialized = False
        self._effective_dimension = self._config.dimension
        self._use_chroma = False
        self._signature_valid: bool | None = None

    async def initialize(self) -> None:
        provider = self._config.provider

        if provider == "openai_compatible":
            self._init_openai_compatible()
        elif provider == "sentence_transformers":
            self._init_sentence_transformers()
        else:
            logger.info("Using BM25-only search (no embedding model)")

        has_embedding = self._embedding_fn is not None or self._api_client is not None

        if has_embedding:
            persist_dir = self._config.persist_dir
            if persist_dir:
                self._use_chroma = self._init_chroma(persist_dir)
            if not self._use_chroma:
                self._vector_store = LocalVectorStore()
                await self._vector_store.initialize(self._effective_dimension)

        self._initialized = True
        logger.info(
            "CognitiveVectorIndex initialized (provider=%s, dim=%d, persist=%s, signature=%s)",
            provider,
            self._effective_dimension,
            self._use_chroma,
            self._config.model_signature,
        )

    def _init_chroma(self, persist_dir: str) -> bool:
        try:
            import chromadb
            expanded = os.path.expanduser(persist_dir)
            os.makedirs(expanded, exist_ok=True)
            client = chromadb.PersistentClient(path=expanded)
            self._chroma_collection = client.get_or_create_collection(
                name=COGNITIVE_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._use_chroma = True
            self._check_signature()
            logger.info("ChromaDB cognitive_node collection initialized at %s", expanded)
            return True
        except ImportError:
            logger.info("chromadb not installed, using in-memory vector store")
            return False
        except Exception as e:
            logger.warning("ChromaDB init failed: %s, using in-memory store", e)
            return False

    def _check_signature(self) -> None:
        if self._chroma_collection is None:
            return
        try:
            peek = self._chroma_collection.peek(limit=1)
            metas = peek.get("metadatas", [])
            if metas and len(metas) > 0:
                stored_sig = metas[0].get("model_signature", "")
                current_sig = self._config.model_signature
                if stored_sig and stored_sig != current_sig:
                    logger.warning(
                        "Model signature mismatch! stored=%s, current=%s. "
                        "Stored vectors may be incompatible. Consider re-indexing.",
                        stored_sig,
                        current_sig,
                    )
                    self._signature_valid = False
                else:
                    self._signature_valid = True
            else:
                self._signature_valid = True
        except Exception:
            self._signature_valid = None

    def _init_openai_compatible(self) -> None:
        base_url = self._config.base_url
        model = self._config.model
        if not base_url or not model:
            logger.warning(
                "openai_compatible provider requires base_url and model, "
                "falling back to BM25"
            )
            return

        try:
            import httpx
            self._api_client = httpx.AsyncClient(
                base_url=base_url.rstrip("/"),
                timeout=httpx.Timeout(10.0, connect=5.0),
                headers={
                    "Content-Type": "application/json",
                    **({"Authorization": f"Bearer {self._config.api_key}"} if self._config.api_key else {}),
                },
            )
            logger.info(
                "OpenAI-compatible embedding client initialized: %s, model=%s",
                base_url,
                model,
            )
        except ImportError:
            logger.warning(
                "httpx not installed, cannot use openai_compatible provider, "
                "falling back to BM25"
            )

    def _init_sentence_transformers(self) -> None:
        model = self._config.model or DEFAULT_ST_MODEL
        try:
            from sentence_transformers import SentenceTransformer
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(SentenceTransformer, model)
                self._embedding_fn = future.result(timeout=30)

            self._effective_dimension = self._config.dimension or DEFAULT_ST_DIMENSION
            logger.info("Loaded sentence-transformers model: %s", model)
        except ImportError:
            logger.info("sentence-transformers not installed, using BM25 fallback")
        except concurrent.futures.TimeoutError:
            logger.warning("sentence-transformers model load timed out (30s), using BM25 fallback")
        except Exception as e:
            logger.warning("sentence-transformers model load failed: %s, using BM25 fallback", e)

    async def _compute_embedding_api(self, text: str) -> list[float] | None:
        if self._api_client is None:
            return None
        payload = {"model": self._config.model, "input": text}
        try:
            resp = await self._api_client.post("/embeddings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            embedding = data["data"][0]["embedding"]
            if self._effective_dimension == 0:
                self._effective_dimension = len(embedding)
            return embedding
        except Exception as e:
            logger.warning("Embedding API call failed: %s", e)
            return None

    async def _compute_embedding_local(self, text: str) -> list[float] | None:
        if self._embedding_fn is None:
            return None
        try:
            return self._embedding_fn.encode(text).tolist()
        except Exception as e:
            logger.warning("Local embedding computation failed: %s", e)
            return None

    async def _compute_embedding(self, text: str) -> list[float] | None:
        if self._api_client is not None:
            result = await self._compute_embedding_api(text)
            if result is not None:
                return result
        if self._embedding_fn is not None:
            result = await self._compute_embedding_local(text)
            if result is not None:
                return result
        return None

    async def index_node(
        self,
        node_id: str,
        content: str,
        memory_type: str,
        tags: list[str],
        space_id: str,
    ) -> None:
        if not self._initialized:
            return

        enriched = _enrich_content(content, memory_type, tags)
        vector = await self._compute_embedding(enriched)

        if vector is not None:
            meta = {
                "space_id": space_id,
                "memory_type": memory_type,
                "model_signature": self._config.model_signature,
            }
            if self._use_chroma and self._chroma_collection is not None:
                try:
                    await asyncio.to_thread(
                        self._chroma_collection.upsert,
                        ids=[node_id],
                        embeddings=[vector],
                        metadatas=[meta],
                    )
                except Exception as e:
                    logger.warning("Failed to store embedding in ChromaDB for %s: %s", node_id, e)
            elif self._vector_store is not None:
                try:
                    await self._vector_store.add_vectors(
                        ids=[node_id],
                        vectors=[vector],
                        metadata=[meta],
                    )
                except Exception as e:
                    logger.warning("Failed to store embedding for %s: %s", node_id, e)

        tokens = _simple_tokenize(enriched)
        for token in set(tokens):
            self._doc_freq[token] += 1
        self._total_docs += 1

    async def vector_search(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        if not self._initialized:
            return []

        query_vector = await self._compute_embedding(query)
        if query_vector is not None:
            return await self._vector_search_embedding(query_vector, space_id, top_k)

        return await self._bm25_search(query, space_id, top_k)

    async def _vector_search_embedding(
        self,
        query_vector: list[float],
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        try:
            if self._use_chroma and self._chroma_collection is not None:
                return await self._chroma_search(query_vector, space_id, top_k)

            if self._vector_store is not None:
                results = await self._vector_store.search(
                    query_vector=query_vector,
                    top_k=top_k * 2,
                    filters={"space_id": space_id},
                )
                return await self._results_to_retrieval(results, top_k)

            return []
        except Exception as e:
            logger.warning("Vector search failed: %s", e)
            return []

    async def _chroma_search(
        self,
        query_vector: list[float],
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        try:
            chroma_results = await asyncio.to_thread(
                self._chroma_collection.query,
                query_embeddings=[query_vector],
                n_results=top_k * 2,
                where={"space_id": space_id},
                include=["metadatas", "distances"],
            )

            results = []
            if chroma_results and chroma_results.get("ids") and chroma_results["ids"][0]:
                ids = chroma_results["ids"][0]
                distances = chroma_results["distances"][0] if chroma_results.get("distances") else [0.0] * len(ids)
                for i, vid in enumerate(ids):
                    distance = distances[i] if i < len(distances) else 0.0
                    score = 1.0 - distance
                    results.append(type("R", (), {"id": vid, "score": score, "metadata": {}})())

            return await self._results_to_retrieval(results, top_k)
        except Exception as e:
            logger.warning("ChromaDB search failed: %s", e)
            return []

    async def _results_to_retrieval(
        self,
        results: list[Any],
        top_k: int,
    ) -> list[RetrievalResult]:
        retrieval_results: list[RetrievalResult] = []
        for r in results:
            node = await self._repo.get_node(r.id)
            if node is None:
                continue
            if node.belief_status in ("superseded", "rejected"):
                continue
            retrieval_results.append(RetrievalResult(
                doc_id=node.id,
                content=node.content,
                source="layer_r",
                memory_type=node.memory_type,
                cognitive_layer=node.cognitive_layer,
                occurred_at=node.occurred_at,
                created_at=node.created_at,
                score=r.score,
            ))
        return retrieval_results[:top_k]

    async def _bm25_search(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        if self._total_docs == 0:
            await self._rebuild_bm25_stats(space_id)

        nodes = await self._repo.query_nodes(domain_id=space_id, limit=200)
        query_tokens = _simple_tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[float, Any]] = []
        for node in nodes:
            if node.belief_status in ("superseded", "rejected"):
                continue
            enriched = _enrich_content(node.content, node.memory_type, node.tags)
            doc_tokens = _simple_tokenize(enriched)
            doc_token_freq = Counter(doc_tokens)

            score = 0.0
            for qt in query_tokens:
                tf = doc_token_freq.get(qt, 0)
                if tf == 0:
                    continue
                df = self._doc_freq.get(qt, 0)
                idf = math.log(1 + (self._total_docs - df + 0.5) / (df + 0.5))
                tf_norm = (tf * 2.5) / (tf + 1.5)
                score += idf * tf_norm

            if score > 0:
                scored.append((score, node))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RetrievalResult(
                doc_id=node.id,
                content=node.content,
                source="layer_r",
                memory_type=node.memory_type,
                cognitive_layer=node.cognitive_layer,
                occurred_at=node.occurred_at,
                created_at=node.created_at,
                score=score,
            )
            for score, node in scored[:top_k]
        ]

    async def bm25_search(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        return await self._bm25_search(query, space_id, top_k)

    async def _rebuild_bm25_stats(self, space_id: str) -> None:
        """Rebuild BM25 document frequency stats from repository.

        Called on cold start when _total_docs == 0 to ensure
        BM25 search works even after restart.
        """
        try:
            nodes = await self._repo.query_nodes(domain_id=space_id, limit=5000)
            self._doc_freq.clear()
            self._total_docs = 0
            for node in nodes:
                enriched = _enrich_content(node.content, node.memory_type, node.tags)
                tokens = _simple_tokenize(enriched)
                for token in set(tokens):
                    self._doc_freq[token] += 1
                self._total_docs += 1
            logger.info("Rebuilt BM25 stats: %d docs, %d unique tokens", self._total_docs, len(self._doc_freq))
        except Exception as e:
            logger.warning("Failed to rebuild BM25 stats: %s", e)

    @property
    def signature_valid(self) -> bool | None:
        return self._signature_valid

    @property
    def model_signature(self) -> str:
        return self._config.model_signature

    @property
    def vector_count(self) -> int:
        if self._use_chroma and self._chroma_collection is not None:
            return self._chroma_collection.count()
        if self._vector_store is not None:
            return len(self._vector_store._vectors)
        return 0

    async def close(self) -> None:
        if self._vector_store is not None and not self._use_chroma:
            await self._vector_store.close()
        if self._api_client is not None:
            await self._api_client.aclose()
        self._chroma_collection = None
        self._initialized = False
