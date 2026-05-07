"""Compilation layer for Entity Page and Topic Page generation.

Pre-compiles high-access entities and topics into structured summaries
for fast retrieval. Implements:

- EntityPage / TopicPage structured summaries
- CompilationDebouncer for rapid-change protection
- Cost-aware compilation scheduling
- CompilationCache with LRU eviction
- Consistency checking (stale detection)

Design decisions (from memory-lifecycle.md §8):
- Hot-precompile: entities with access_count > 10/week
- On-demand: first query triggers compilation for cold entities
- Event-triggered: attribute changes mark compiled_at as stale
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)

ENTITY_PAGE_ESTIMATED_TOKENS = 5000
TOPIC_PAGE_ESTIMATED_TOKENS = 3000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EntityPage:
    node_id: str
    entity_name: str
    summary: str
    timeline: list[dict[str, str]] = field(default_factory=list)
    key_metrics: dict[str, Any] = field(default_factory=dict)
    compiled_at: str = ""
    source_node_ids: list[str] = field(default_factory=list)
    related_observations: list[str] = field(default_factory=list)


@dataclass
class TopicPage:
    topic_id: str
    topic_name: str
    synthesis: str
    entity_relations: list[dict[str, str]] = field(default_factory=list)
    compiled_at: str = ""
    source_entity_ids: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class CompilationResult:
    entity_pages: list[EntityPage] = field(default_factory=list)
    topic_pages: list[TopicPage] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


class CompilationCache:
    """In-memory LRU cache for compiled pages."""

    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict[str, EntityPage | TopicPage] = OrderedDict()
        self._max_size = max_size

    def get(self, page_id: str) -> EntityPage | TopicPage | None:
        if page_id in self._cache:
            self._cache.move_to_end(page_id)
            return self._cache[page_id]
        return None

    def set(self, page_id: str, page: EntityPage | TopicPage):
        if page_id in self._cache:
            self._cache.move_to_end(page_id)
            self._cache[page_id] = page
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[page_id] = page

    def invalidate(self, page_id: str):
        self._cache.pop(page_id, None)


_compilation_cache = CompilationCache()


def get_compilation_cache() -> CompilationCache:
    return _compilation_cache


async def compile_entity_page(
    repository: "CognitiveRepository",
    node_id: str,
) -> EntityPage:
    """Compile an EntityPage from an entity node and its related observations.

    Args:
        repository: CognitiveRepository for node queries.
        node_id: ID of the entity node to compile.

    Returns:
        Compiled EntityPage.
    """
    node = await repository.get_node(node_id)

    timeline: list[dict[str, str]] = []
    for entry in (node.history or []):
        ts = entry.get("changed_at", "")
        reason = entry.get("change_reason", "")
        if ts:
            timeline.append({"date": ts[:10], "event": reason})

    related = await repository.query_nodes(
        domain_id=node.space_id,
        limit=50,
    )
    related_obs_nodes = [
        n for n in related
        if n.id != node_id and n.content and n.memory_type == "observation"
    ]
    node_words = set((node.content or "").lower().split())
    if node_words:
        related_obs_nodes.sort(
            key=lambda n: len(node_words & set(n.content.lower().split())),
            reverse=True,
        )
    related_obs_nodes = related_obs_nodes[:10]

    related_texts = [n.content for n in related_obs_nodes[:5]]

    summary_sections = []
    if node.content:
        summary_sections.append(f"[Overview] {node.content}")
    if related_texts:
        combined = "; ".join(related_texts)
        summary_sections.append(f"[Related Facts] {combined}")
    summary = "\n".join(summary_sections)

    key_metrics: dict[str, Any] = {
        "memory_type": node.memory_type,
        "cognitive_layer": node.cognitive_layer,
        "belief_status": node.belief_status,
        "access_count": node.access_count,
        "feedback_weight": node.feedback_weight,
        "source_fragment_count": len(node.source_fragment_ids),
    }

    source_ids = [node_id]
    source_ids.extend(n.id for n in related_obs_nodes)

    related_obs_ids = [n.id for n in related_obs_nodes]

    entity_name = node.content[:60] if node.content else node_id

    return EntityPage(
        node_id=node_id,
        entity_name=entity_name,
        summary=summary,
        timeline=timeline,
        key_metrics=key_metrics,
        compiled_at=_now_iso(),
        source_node_ids=source_ids[:20],
        related_observations=related_obs_ids,
    )


async def compile_topic_page(
    repository: "CognitiveRepository",
    topic: str,
    entity_ids: list[str],
) -> TopicPage:
    """Compile a TopicPage from multiple entity nodes.

    Args:
        repository: CognitiveRepository for node queries.
        topic: Topic name for the page.
        entity_ids: List of entity node IDs to synthesize.

    Returns:
        Compiled TopicPage.
    """
    summaries: list[str] = []
    relations: list[dict[str, str]] = []
    seen_ids: list[str] = []
    findings: list[str] = []
    questions: list[str] = []

    for eid in entity_ids[:10]:
        try:
            node = await repository.get_node(eid)
            if node.content:
                summaries.append(node.content[:200])
            seen_ids.append(eid)

            if node.memory_type == "entity" and node.content:
                findings.append(node.content[:150])
            if node.belief_status == "pending_review" and node.content:
                questions.append(f"Pending review: {node.content[:100]}")
            if node.memory_type == "mental_model" and node.belief_status == "accepted":
                questions.append(f"Model assumption: {node.content[:100]}")
        except Exception as e:
            logger.debug("Failed to fetch entity %s for topic page: %s", eid, e)

    synthesis_sections = []
    synthesis_sections.append(f"Topic: {topic}")
    if summaries:
        synthesis_sections.append("Entities: " + " | ".join(summaries))
    synthesis = "\n".join(synthesis_sections) if summaries else topic

    for i in range(len(seen_ids) - 1):
        relations.append({
            "from": seen_ids[i],
            "to": seen_ids[i + 1],
            "relation_type": "RELATES_TO",
        })

    return TopicPage(
        topic_id=f"topic:{topic}",
        topic_name=topic,
        synthesis=synthesis,
        entity_relations=relations,
        compiled_at=_now_iso(),
        source_entity_ids=seen_ids,
        key_findings=findings[:10],
        open_questions=questions[:5],
    )


async def check_compilation_consistency(
    repository: "CognitiveRepository",
    node_id: str,
) -> str:
    """Check if a node's compiled page is stale.

    Args:
        repository: CognitiveRepository for node queries.
        node_id: Node ID to check.

    Returns:
        "CURRENT" if compiled_at >= updated_at, "STALE" otherwise.
    """
    try:
        node = await repository.get_node(node_id)
    except Exception:
        return "STALE"

    compiled_str = getattr(node, "compiled_at", None)
    if not compiled_str:
        return "STALE"

    updated_str = node.updated_at or ""
    if not updated_str:
        return "CURRENT"

    try:
        compiled_dt = datetime.fromisoformat(compiled_str.replace("Z", "+00:00"))
        updated_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "STALE"

    if compiled_dt < updated_dt:
        return "STALE"
    return "CURRENT"


class CompilationDebouncer:
    """Prevents rapid successive compilations for the same node."""

    def __init__(self, debounce_seconds: float = 300):
        self._debounce_seconds = debounce_seconds
        self._pending: dict[str, asyncio.Task[None]] = {}
        self._repository: "CognitiveRepository | None" = None

    def set_repository(self, repository: "CognitiveRepository"):
        self._repository = repository

    def schedule_recompilation(self, node_id: str):
        if node_id in self._pending:
            self._pending[node_id].cancel()
        self._pending[node_id] = asyncio.create_task(self._debounced_compile(node_id))

    async def _debounced_compile(self, node_id: str):
        await asyncio.sleep(self._debounce_seconds)
        if self._repository:
            try:
                await compile_entity_page(self._repository, node_id)
            except Exception as e:
                logger.warning("Debounced compilation failed for %s: %s", node_id, e)
        self._pending.pop(node_id, None)


def estimate_compilation_cost(memory_type: str) -> int:
    if memory_type in ("entity", "observation"):
        return ENTITY_PAGE_ESTIMATED_TOKENS
    if memory_type == "mental_model":
        return TOPIC_PAGE_ESTIMATED_TOKENS
    return TOPIC_PAGE_ESTIMATED_TOKENS


class CompilationScheduler:
    """Cost-aware compilation scheduler with token budget control."""

    def __init__(
        self,
        repository: "CognitiveRepository",
        daily_token_budget: int = 5000000,
    ):
        self._repo = repository
        self._daily_token_budget = daily_token_budget

    async def compile_with_budget(self, space_id: str) -> CompilationResult:
        """Compile high-access entities within the daily token budget.

        Args:
            space_id: Space to compile entities for.

        Returns:
            CompilationResult with compiled pages.
        """
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=500)
        candidates = [n for n in nodes if n.memory_type in ("entity", "observation", "mental_model")]
        candidates.sort(key=lambda n: int(n.access_count), reverse=True)

        result = CompilationResult()
        total_cost = 0

        for node in candidates:
            cost = estimate_compilation_cost(node.memory_type)
            if total_cost + cost > self._daily_token_budget:
                break

            try:
                if node.memory_type == "mental_model":
                    page = await compile_topic_page(
                        self._repo,
                        node.content[:50] or node.id,
                        [node.id],
                    )
                    result.topic_pages.append(page)
                else:
                    page = await compile_entity_page(self._repo, node.id)
                    result.entity_pages.append(page)
                total_cost += cost
            except Exception as e:
                logger.warning("Compilation failed for %s: %s", node.id, e)
                result.errors.append({
                    "node_id": node.id,
                    "error": str(e),
                })

        return result
