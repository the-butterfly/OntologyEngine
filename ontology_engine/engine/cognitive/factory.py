"""MemoryAPI factory — centralized initialization of all cognitive dependencies.

Provides a single entry point for creating a fully-initialized MemoryAPI
with all required wiring (consolidation engine, entity resolver, query router,
reflect agent, forgetting engine, dream cycle, correction propagation,
cognitive vector index).

LLM Configuration:
    LLM calls for consolidation and reflection are configured via:
    1. Constructor parameter: llm_config dict
    2. Environment variables: OE_LLM_BASE_URL, OE_LLM_API_KEY, OE_LLM_MODEL
    3. config.yaml: llm section
    When not configured, engines fall back to rule-based heuristics.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from ontology_engine.engine.cognitive.cognitive_vector_index import CognitiveVectorIndex, EmbeddingConfig
from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.consolidation_types import Fragment, CreateAction, UpdateAction, DeleteAction
from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.base import CognitiveStorageBackend
from ontology_engine.storage.cognitive.store import CognitiveStore
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore

logger = logging.getLogger(__name__)


def _load_llm_config() -> dict[str, Any]:
    """Load LLM configuration from environment variables and config.yaml.

    Priority: environment variables > config.yaml > defaults (disabled).

    Returns:
        Dict with keys: provider, base_url, api_key, model, enabled.
    """
    config: dict[str, Any] = {"enabled": False}

    base_url = os.environ.get("OE_LLM_BASE_URL")
    api_key = os.environ.get("OE_LLM_API_KEY")
    model = os.environ.get("OE_LLM_MODEL")

    try:
        import yaml

        config_path = os.environ.get(
            "OE_CONFIG_PATH",
            os.path.expanduser("~/.ontology_engine/config.yaml"),
        )
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            llm_raw = raw.get("llm", {})
            base_url = base_url or llm_raw.get("base_url")
            api_key = api_key or llm_raw.get("api_key")
            model = model or llm_raw.get("model")
    except Exception as e:
        logger.debug("Failed to load LLM config from yaml: %s", e)

    if base_url:
        config["enabled"] = True
        config["base_url"] = base_url
        config["api_key"] = api_key or ""
        config["model"] = model or "default"

    return config


async def _create_llm_call_fn(llm_config: dict[str, Any]) -> Any:
    """Create an LLM call function from configuration.

    The returned function has signature:
        async def llm_call_fn(prompt: str, system: str = "") -> str

    Uses httpx to call an OpenAI-compatible chat completions API.
    """
    if not llm_config.get("enabled"):
        return None

    import httpx

    base_url = llm_config["base_url"].rstrip("/")
    api_key = llm_config.get("api_key", "")
    model = llm_config.get("model", "default")

    async def llm_call_fn(prompt: str, system: str = "") -> str:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "temperature": 0.3},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    return llm_call_fn


def _build_consolidation_adapter(llm_call_fn):
    """Wrap llm_call_fn(prompt, system) into ConsolidationEngine's expected signature.

    ConsolidationEngine._consolidate_batch_with_llm calls:
        await self._llm_consolidate(fragments, existing)
    where fragments is list[Fragment] and existing is list[CognitiveNode].

    The raw llm_call_fn accepts (str, str) -> str and cannot handle dataclass
    arguments directly (httpx json.dumps fails on non-serializable types).

    This adapter:
    1. Serializes Fragment/CognitiveNode to dicts
    2. Builds a consolidation prompt
    3. Calls the original llm_call_fn
    4. Parses the JSON response into action objects
    5. Falls back to empty list on any error (ConsolidationEngine uses rule-based fallback)
    """
    import json

    SYSTEM_PROMPT = (
        "You are a cognitive consolidation engine. "
        "Analyze unconsolidated memory fragments and existing observations, "
        "then produce consolidation actions as JSON. "
        "Output ONLY a JSON object with an 'actions' array. No other text."
    )

    async def adapter(
        fragments: list[Fragment],
        existing_nodes: list[CognitiveNode],
    ) -> list[CreateAction | UpdateAction | DeleteAction]:
        frag_dicts = [
            {
                "id": f.id,
                "content": f.content,
                "tags": f.tags,
                "space_id": f.space_id,
                "version": f.version,
                "created_at": f.created_at,
            }
            for f in fragments
        ]
        node_dicts = [n.to_dict() for n in existing_nodes]

        prompt = json.dumps(
            {
                "task": "consolidate_memories",
                "fragments": frag_dicts,
                "existing_observations": node_dicts,
                "instructions": (
                    "Analyze the fragments and existing observations. "
                    "Produce consolidation actions:\n"
                    '- "create": new coherent observation from fragments. '
                    'Fields: type, text, memory_type (observation/entity), tags, confidence (0-1), source_fragment_ids\n'
                    '- "update": extend an existing observation with new fragments. '
                    'Fields: type, target_id, updated_text, updated_tags, confidence (0-1), source_fragment_ids\n'
                    '- "delete": supersede an outdated/contradicted observation. '
                    'Fields: type, target_id, replacement_id (optional), reason\n'
                    "Return ONLY: {\"actions\": [...]}"
                ),
            },
            indent=2,
            ensure_ascii=False,
        )

        try:
            response = await llm_call_fn(prompt, SYSTEM_PROMPT)
            result = json.loads(response)
            actions_data = result.get("actions", [])
        except Exception as e:
            logger.warning(
                "LLM consolidation response parsing failed, falling back to rule-based: %s",
                e,
            )
            return []

        frag_map = {f.id: f for f in fragments}
        actions: list[CreateAction | UpdateAction | DeleteAction] = []

        for a in actions_data:
            try:
                atype = a.get("type", "")
                frag_ids = a.get("source_fragment_ids", [])
                source_frags = [frag_map[fid] for fid in frag_ids if fid in frag_map]

                if atype == "create":
                    actions.append(
                        CreateAction(
                            text=a.get("text", ""),
                            memory_type=a.get("memory_type", "observation"),
                            tags=a.get("tags", []),
                            confidence=float(a.get("confidence", 0.7)),
                            source_fragments=source_frags,
                        )
                    )
                elif atype == "update":
                    actions.append(
                        UpdateAction(
                            target_id=a.get("target_id", ""),
                            updated_text=a.get("updated_text", ""),
                            updated_tags=a.get("updated_tags", []),
                            confidence=float(a.get("confidence", 0.7)),
                            new_source_fragments=source_frags,
                        )
                    )
                elif atype == "delete":
                    actions.append(
                        DeleteAction(
                            target_id=a.get("target_id", ""),
                            replacement_id=a.get("replacement_id"),
                            reason=a.get("reason", "superseded_by_consolidation"),
                        )
                    )
            except Exception as e:
                logger.warning("Failed to parse consolidation action: %s", e)
                continue

        return actions

    return adapter


async def create_memory_api(
    db_path: str | None = None,
    daily_token_budget: int = 20000,
    llm_config: dict[str, Any] | None = None,
) -> tuple[MemoryAPI, CognitiveStorageBackend]:
    """Create a fully-initialized MemoryAPI with all dependencies wired.

    Args:
        db_path: Kuzu database path. Defaults to ~/.ontology_engine/cognitive_db.
        daily_token_budget: Token budget for CompilationScheduler.
        llm_config: Optional LLM configuration dict. When provided, overrides
            environment variables and config.yaml. Keys: base_url, api_key, model.

    Returns:
        Tuple of (initialized MemoryAPI, CognitiveStorageBackend) so the caller
        can close the storage on shutdown.
    """
    path = db_path or os.path.expanduser("~/.ontology_engine/cognitive_db")

    effective_llm_config = llm_config or _load_llm_config()
    if llm_config and "enabled" not in effective_llm_config:
        effective_llm_config["enabled"] = bool(effective_llm_config.get("base_url"))
    llm_call_fn = await _create_llm_call_fn(effective_llm_config)

    if llm_call_fn:
        logger.info("LLM integration enabled: model=%s", effective_llm_config.get("model"))
    else:
        logger.info("LLM integration disabled: using rule-based fallbacks")

    graph_store = KuzuGraphStore()
    await graph_store.initialize(path)
    cognitive_store = CognitiveStore(graph_store)
    repo = CognitiveRepository(cognitive_store)

    vector_index = CognitiveVectorIndex(
        repository=repo,
        config=EmbeddingConfig.from_yaml(),
    )
    await vector_index.initialize()

    consolidation = ConsolidationEngine(
        repository=repo,
        llm_consolidate_fn=_build_consolidation_adapter(llm_call_fn) if llm_call_fn else None,
    )
    resolver = EntityResolver(repository=repo, llm_call_fn=llm_call_fn)
    rrf = RRFFusionEngine(
        repository=repo,
        vector_search_fn=vector_index.vector_search,
        bm25_search_fn=vector_index.bm25_search,
    )
    router = QueryRouter(rrf_engine=rrf, repository=repo)
    reflect = ReflectAgent(
        repository=repo,
        query_router=router,
        llm_call_fn=llm_call_fn,
    )
    forgetting = ForgettingEngine(repository=repo)
    dream = DreamCycle(repository=repo, forgetting_engine=forgetting)
    correction = CorrectionPropagation(repository=repo)

    from ontology_engine.engine.cognitive.ingestion_service import CognitiveIngestionService, CognitiveExtractionPipeline
    pipeline = CognitiveExtractionPipeline(repository=repo, llm_call=llm_call_fn)
    ingestion = CognitiveIngestionService(
        repository=repo,
        extraction_pipeline=pipeline,
        vector_index=vector_index,
    )

    from ontology_engine.engine.cognitive.query_understanding_layer import QueryUnderstandingLayer
    qul = QueryUnderstandingLayer(repository=repo, llm_call=llm_call_fn)

    return MemoryAPI(
        repository=repo,
        consolidation_engine=consolidation,
        entity_resolver=resolver,
        query_router=router,
        reflect_agent=reflect,
        forgetting_engine=forgetting,
        dream_cycle=dream,
        correction_propagation=correction,
        vector_index=vector_index,
        ingestion_service=ingestion,
        qul=qul,
    ), cognitive_store


class MemoryAPISingleton:
    """Application-level singleton for MemoryAPI.

    Creates the MemoryAPI once on first access and reuses it.
    Thread-safe via asyncio.Lock — suitable for multi-coroutine ASGI apps.
    For multi-worker deployments (gunicorn -w N), each worker gets its own
    process and thus its own singleton instance; KuzuDB file locking is
    handled by retry with exponential backoff in KuzuGraphStore.initialize().
    """

    _instance: MemoryAPI | None = None
    _db_path: str | None = None
    _storage: CognitiveStorageBackend | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_or_create(cls, db_path: str | None = None) -> MemoryAPI:
        async with cls._lock:
            if cls._instance is None or cls._db_path != db_path:
                if cls._storage is not None:
                    await cls._storage.close()
                cls._instance, cls._storage = await create_memory_api(db_path)
                cls._db_path = db_path
            return cls._instance

    @classmethod
    async def close(cls) -> None:
        async with cls._lock:
            if cls._storage is not None:
                await cls._storage.close()
                cls._storage = None
            cls._instance = None
            cls._db_path = None
