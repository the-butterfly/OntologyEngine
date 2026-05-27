"""Async clients for LOCOMO benchmark.

Exposes a uniform interface so the same pipeline can run against either
OntologyEngine (OE) or Mem0 without code changes.

  client.add(messages, user_id, timestamp=...)
  client.search(query, user_id, top_k=...)
  client.delete_user(user_id)

OE uses KuzuDB (embedded) — serialise writes to avoid file-lock errors.
Mem0 uses REST (OSS server on localhost:8888 by default).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================

def _format_search_results(search_results: list[dict]) -> tuple[list[dict], dict | None]:
    """Normalise search results into a clean format for benchmark output."""
    if not search_results:
        return [], None

    query_debug = None
    if isinstance(search_results, dict):
        query_debug = search_results.get("query_debug")
        search_results = search_results.get("results", [])

    sorted_results = sorted(search_results, key=lambda x: x.get("score", 0), reverse=True)
    formatted = []
    for r in sorted_results:
        entry: dict[str, Any] = {
            "memory": r.get("memory", ""),
            "score": r.get("score", 0),
            "id": r.get("id", ""),
        }
        if r.get("created_at"):
            entry["created_at"] = r["created_at"]
        if r.get("updated_at"):
            entry["updated_at"] = r["updated_at"]
        if r.get("score_debug"):
            entry["score_debug"] = r["score_debug"]
        formatted.append(entry)
    return formatted, query_debug


# =============================================================================
# OE Client
# =============================================================================

class OEClient:
    """Async OntologyEngine client compatible with the benchmark pipeline."""

    def __init__(
        self,
        db_path: str | None = None,
        llm_config: dict[str, Any] | None = None,
        embedding_config: dict[str, Any] | None = None,
    ):
        self._db_path = db_path
        self._llm_config = llm_config
        self._embedding_config = embedding_config
        self._api: Any = None
        self._storage: Any = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        # Lazy import so the example can be inspected without OE installed
        from ontology_engine.engine.cognitive.factory import create_memory_api

        self._api, self._storage = await create_memory_api(
            db_path=self._db_path,
            llm_config=self._llm_config,
            embedding_config=self._embedding_config,
        )
        self._initialized = True

    async def add(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        observation_date: str | None = None,
        timestamp: int | None = None,
        custom_instructions: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        """Ingest a conversation chunk into OE."""
        await self._ensure_init()

        lines = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if content.strip():
                lines.append(f"{role}: {content}")
        if not lines:
            return {"results": []}

        text = "\n".join(lines)
        oe_tags: dict[str, str | list[str]] = {"source": "locomo"}
        if metadata:
            oe_tags.update(metadata)

        occurred_at: str | None = None
        if timestamp is not None:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            occurred_at = dt.isoformat()

        async with self._lock:
            try:
                response = await self._api.remember(
                    content=text,
                    space_id=user_id,
                    memory_type="observation",
                    visibility="shared",
                    created_by=user_id,
                    tags=oe_tags,
                    occurred_at=occurred_at,
                    source_pipeline="locomo_benchmark",
                    confidence=1.0,
                )
            except Exception as exc:
                logger.warning("OE remember failed (user=%s): %s", user_id, exc)
                return None

        data = response.get("data", response) if isinstance(response, dict) else response
        memory_id = None
        if isinstance(data, dict):
            memory_id = data.get("memory_id") or data.get("node_id")

        results = []
        if memory_id:
            results.append({
                "memory": text,
                "id": str(memory_id),
                "event": "ADD",
                "user_id": user_id,
            })
        return {"results": results}

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 200,
        rerank: bool = False,
        score_debug: bool = False,
    ) -> list[dict]:
        """Search memories via OE recall."""
        await self._ensure_init()

        try:
            response = await self._api.recall(
                query=query,
                space_id=user_id,
                max_results=top_k,
                include_evidence=False,
                min_confidence=0.0,
            )
        except Exception as exc:
            logger.warning("OE recall failed (user=%s, query=%s): %s", user_id, query[:80], exc)
            return []

        data = response.get("data", response) if isinstance(response, dict) else response
        raw_results = []
        if isinstance(data, dict):
            raw_results = data.get("results", [])
        elif isinstance(data, list):
            raw_results = data
        if not isinstance(raw_results, list):
            raw_results = []

        normalised = []
        for r in raw_results:
            if not isinstance(r, dict):
                continue
            entry: dict[str, Any] = {
                "memory": r.get("text", r.get("content", "")),
                "score": r.get("score", 0),
                "id": r.get("id", ""),
            }
            if r.get("created_by"):
                entry["created_by"] = r["created_by"]
            if r.get("created_at"):
                entry["created_at"] = r["created_at"]
            if r.get("updated_at"):
                entry["updated_at"] = r["updated_at"]
            if r.get("memory_type"):
                entry["memory_type"] = r["memory_type"]
            if r.get("confidence"):
                entry["confidence"] = r["confidence"]
            normalised.append(entry)

        normalised.sort(key=lambda x: x.get("score", 0), reverse=True)
        return normalised

    async def delete_user(self, user_id: str) -> bool:
        return True

    async def close(self) -> None:
        if self._storage is not None:
            await self._storage.close()
            self._storage = None
        self._api = None
        self._initialized = False

    async def __aenter__(self) -> OEClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


# =============================================================================
# Mem0 Client
# =============================================================================

class Mem0Client:
    """Async Mem0 OSS client."""

    def __init__(
        self,
        host: str | None = None,
        max_retries: int = 5,
        retry_delay: float = 5.0,
        timeout: float = 300.0,
    ):
        self.host = (host or os.getenv("MEM0_HOST", "http://localhost:8888")).rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=0)
            self._session = aiohttp.ClientSession(
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
                connector=connector,
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> Mem0Client:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def add(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        observation_date: str | None = None,
        timestamp: int | None = None,
        custom_instructions: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        session = await self._get_session()
        payload: dict[str, Any] = {"messages": messages, "user_id": user_id}
        if timestamp is not None:
            payload["timestamp"] = timestamp
        elif observation_date is not None:
            try:
                d = datetime.strptime(observation_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                payload["timestamp"] = int(d.timestamp())
            except ValueError:
                pass
        if custom_instructions:
            payload["custom_instructions"] = custom_instructions
        if metadata:
            payload["metadata"] = metadata

        for attempt in range(self.max_retries):
            try:
                async with session.post(f"{self.host}/memories", json=payload) as resp:
                    if resp.status >= 500:
                        raise aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=resp.status
                        )
                    resp.raise_for_status()
                    data = await resp.json()
                if isinstance(data, dict) and "results" in data:
                    return data
                if isinstance(data, list):
                    return {"results": data}
                return {"results": []}
            except Exception as exc:
                logger.warning(
                    "Mem0 ADD attempt %d/%d failed (user=%s): %s",
                    attempt + 1, self.max_retries, user_id, str(exc)[:200],
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error("Mem0 ADD failed after %d attempts for user=%s", self.max_retries, user_id)
                    return None
        return None

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 200,
        rerank: bool = False,
        score_debug: bool = False,
    ) -> list[dict]:
        session = await self._get_session()
        payload: dict[str, Any] = {
            "query": query,
            "user_id": user_id,
            "limit": top_k,
        }
        if rerank:
            payload["rerank"] = True

        for attempt in range(self.max_retries):
            try:
                async with session.post(f"{self.host}/search", json=payload) as resp:
                    if resp.status >= 500:
                        raise aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=resp.status
                        )
                    resp.raise_for_status()
                    data = await resp.json()

                results = data.get("results", data) if isinstance(data, dict) else data
                if not isinstance(results, list):
                    results = []

                normalised = []
                for r in results:
                    entry: dict[str, Any] = {
                        "memory": r.get("memory", r.get("data", "")),
                        "score": r.get("score", 0),
                        "id": r.get("id", ""),
                    }
                    if r.get("created_at"):
                        entry["created_at"] = r["created_at"]
                    if r.get("updated_at"):
                        entry["updated_at"] = r["updated_at"]
                    breakdown = r.get("score_breakdown") or r.get("score_debug")
                    if breakdown:
                        entry["score_debug"] = {
                            "combined_score": r.get("score", 0),
                            "semantic_score": breakdown.get("semantic", 0),
                            "bm25_score": breakdown.get("bm25", 0),
                            "entity_boost": breakdown.get("entity_boost", 0),
                        }
                    normalised.append(entry)

                normalised.sort(key=lambda x: x.get("score", 0), reverse=True)
                return normalised

            except Exception as exc:
                logger.warning(
                    "Mem0 SEARCH attempt %d/%d failed (user=%s): %s",
                    attempt + 1, self.max_retries, user_id, str(exc)[:200],
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error("Mem0 SEARCH failed after %d attempts for user=%s", self.max_retries, user_id)
                    return []
        return []

    async def delete_user(self, user_id: str) -> bool:
        session = await self._get_session()
        try:
            async with session.delete(
                f"{self.host}/memories",
                params={"user_id": user_id},
            ) as resp:
                resp.raise_for_status()
            logger.info("Deleted memories for user %s", user_id)
            return True
        except Exception as exc:
            logger.warning("Failed to delete user %s: %s", user_id, exc)
            return False
