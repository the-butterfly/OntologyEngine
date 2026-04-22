"""LLM-based semantic extraction for unstructured content.

Usage — constructor injection (preferred)::

    from ontology_engine.engine.extraction.llm_protocol import LLMClientProtocol
    extractor = LLMExtractor(llm_client=my_llm_client)

Usage — config.yaml / env-var fallback (no explicit client)::

    extractor = LLMExtractor()          # auto-loads from config.yaml / env
    # or
    extractor = LLMExtractor(config_path="/path/to/config.yaml")

When neither a client nor a valid config is available ``_call_llm`` returns
empty results and a warning is logged, so the pipeline degrades gracefully
rather than crashing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ontology_engine.engine.extraction.llm_protocol import (
    LLMClientProtocol,
    LLMProviderError,
    build_llm_client_from_config,
)

logger = logging.getLogger(__name__)

# Shared UUID namespace for deterministic entity IDs (RFC 4122 DNS namespace)
ENTITY_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass
class LLMEntity:
    name: str
    fact_object: str
    attributes: dict[str, Any]
    confidence: float
    confidence_label: str
    evidence_text: str


@dataclass
class LLMRelation:
    from_entity: str
    to_entity: str
    relation_name: str
    edge_text: str
    confidence: float
    confidence_label: str
    evidence_text: str


@dataclass
class LLMCategory:
    entity_name: str
    dimension_name: str
    value_code: str
    confidence: float
    confidence_label: str


@dataclass
class LLMExtractionResult:
    entities: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    categories: list[dict[str, Any]] = field(default_factory=list)
    supported_by_edges: list[dict[str, Any]] = field(default_factory=list)


# ─────────────────────── System prompt ───────────────────────────────────────

_EXTRACTION_SYSTEM_PROMPT_BASE = """You are a knowledge-graph extraction assistant.
Given a document fragment, extract:
1. Named entities: each with name, fact_object (e.g. "finance:Counterparty"),
   attributes (dict), confidence (0-1), confidence_label (EXTRACTED|INFERRED|AMBIGUOUS),
   and evidence_text (the exact quote that supports the extraction).
2. Relations between entities: from_entity, to_entity, relation_name, edge_text,
   confidence, confidence_label.

Return a JSON object with keys "entities" and "relations".
Only return valid JSON, no markdown fences."""

# Template used when the caller injects schema context (fact_object names + definitions).
# {schema_definitions} is replaced at call time with a compact YAML-like listing.
_EXTRACTION_SYSTEM_PROMPT_WITH_SCHEMA = """{base_prompt}

Domain schema (use these fact_object names when classifying entities):
{schema_definitions}"""


def _build_system_prompt(schema_context: dict[str, Any] | None) -> str:
    """Assemble the system prompt, optionally injecting schema definitions.

    Args:
        schema_context: Optional dict mapping fact_object name → description.
            Example: {"finance:Counterparty": "A legal entity that participates
            in a financial transaction", ...}
            When None or empty, the base prompt is returned unchanged.
    """
    if not schema_context:
        return _EXTRACTION_SYSTEM_PROMPT_BASE

    lines = []
    for name, desc in schema_context.items():
        if desc:
            lines.append(f"  - {name}: {desc}")
        else:
            lines.append(f"  - {name}")
    schema_block = "\n".join(lines) if lines else "  (no schema definitions provided)"

    return _EXTRACTION_SYSTEM_PROMPT_WITH_SCHEMA.format(
        base_prompt=_EXTRACTION_SYSTEM_PROMPT_BASE,
        schema_definitions=schema_block,
    )


class LLMExtractor:
    """Pass 2: LLM semantic extraction from unstructured content.

    Constructor arguments
    ─────────────────────
    llm_client : LLMClientProtocol | None
        Pre-built LLM client to use.  If ``None``, the extractor tries to
        build one automatically from ``config.yaml`` / environment variables.
    config_path : str | Path | None
        Path to ``config.yaml`` used when ``llm_client`` is ``None``.
        Defaults to project-root ``config.yaml`` or
        ``~/.ontology_engine/config.yaml`` (first found).
    """

    def __init__(
        self,
        llm_client: LLMClientProtocol | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        if llm_client is not None:
            # Caller explicitly injected a client — use it directly
            if not isinstance(llm_client, LLMClientProtocol):
                raise TypeError(
                    f"llm_client must implement LLMClientProtocol, got {type(llm_client)}"
                )
            self._client: LLMClientProtocol | None = llm_client
        else:
            # Try to build from config.yaml / env vars
            self._client = build_llm_client_from_config(config_path)
            if self._client is None:
                logger.warning(
                    "LLMExtractor: no LLM client configured. "
                    "Pass 2 (LLM extraction) will be skipped. "
                    "Provide an llm_client or set OE_LLM_API_KEY / config.yaml."
                )

    # ─────────────────────── Public API ──────────────────────────────────────

    def extract(
        self,
        uncached_fragments: list[dict[str, Any]],
        schema_context: dict[str, Any] | None = None,
    ) -> LLMExtractionResult:
        """Extract entities and relations from uncached document fragments.

        Args:
            uncached_fragments: List of dicts with keys ``id`` and ``text``.
            schema_context: Optional mapping of fact_object name → description
                loaded from the project's SchemaLoader.  When supplied the LLM
                system prompt is augmented with the domain schema so that
                fact_object names in extracted entities align with the project's
                type system.  When omitted the extractor falls back to a generic
                prompt (Phase 1 compatibility mode).

        Returns:
            Merged LLMExtractionResult across all fragments.
        """
        if not uncached_fragments:
            return LLMExtractionResult()

        all_entities: list[dict[str, Any]] = []
        all_edges: list[dict[str, Any]] = []
        all_categories: list[dict[str, Any]] = []
        all_supported_by: list[dict[str, Any]] = []

        for fragment in uncached_fragments:
            result = self._extract_single(fragment, schema_context=schema_context)
            all_entities.extend(result.entities)
            all_edges.extend(result.edges)
            all_categories.extend(result.categories)
            all_supported_by.extend(result.supported_by_edges)

        return LLMExtractionResult(
            entities=all_entities,
            edges=all_edges,
            categories=all_categories,
            supported_by_edges=all_supported_by,
        )

    def detect_semantic_similarity(
        self,
        entity_a: dict[str, Any],
        entity_b: dict[str, Any],
    ) -> dict[str, Any]:
        """Ask the LLM whether two entities refer to the same real-world object."""
        if self._client is None:
            return {
                "is_same_entity": False,
                "confidence": 0.0,
                "confidence_label": "AMBIGUOUS",
                "reasoning": "LLM integration not configured",
            }

        prompt = (
            f"Entity A: {entity_a}\n\nEntity B: {entity_b}\n\n"
            "Do these two entities refer to the same real-world object?\n"
            'Return JSON: {"is_same_entity": bool, "confidence": float, '
            '"confidence_label": "EXTRACTED|INFERRED|AMBIGUOUS", "reasoning": str}'
        )
        try:
            import json
            raw = self._client.chat_complete(prompt, temperature=0.0)
            return dict(json.loads(raw))
        except Exception as exc:
            logger.debug("detect_semantic_similarity failed: %s", exc)
            return {
                "is_same_entity": False,
                "confidence": 0.0,
                "confidence_label": "AMBIGUOUS",
                "reasoning": f"LLM call failed: {exc}",
            }

    def classify_entity(
        self,
        entity_name: str,
        entity_attributes: dict[str, Any],
        available_dimensions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Ask the LLM to classify an entity into available categorisation dimensions."""
        if self._client is None:
            return []

        prompt = (
            f"Entity: {entity_name}\nAttributes: {entity_attributes}\n"
            f"Dimensions: {available_dimensions}\n"
            "Classify the entity into as many dimensions as applicable.\n"
            "Return JSON array of {dimension_name, value_code, confidence}."
        )
        try:
            import json
            raw = self._client.chat_complete(prompt, temperature=0.0)
            result = json.loads(raw)
            if isinstance(result, list):
                return result
            return []
        except Exception as exc:
            logger.debug("classify_entity failed: %s", exc)
            return []

    # ─────────────────────── Internal helpers ────────────────────────────────

    def _extract_single(
        self,
        fragment: dict[str, Any],
        schema_context: dict[str, Any] | None = None,
    ) -> LLMExtractionResult:
        text = fragment.get("text", "")
        fragment_id = fragment.get("id", "")

        entities: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        categories: list[dict[str, Any]] = []
        supported_by: list[dict[str, Any]] = []

        llm_result = self._call_llm(text, schema_context=schema_context)

        for llm_entity in llm_result.get("entities", []):
            entity_id = str(uuid.uuid5(ENTITY_NAMESPACE, llm_entity.get("name", "")))
            confidence = llm_entity.get("confidence", 0.5)
            confidence_label = llm_entity.get("confidence_label", "INFERRED")

            entities.append({
                "entity_id": entity_id,
                "_fact_object": llm_entity.get("fact_object", "domain:Unknown"),
                "attributes": llm_entity.get("attributes", {}),
                "confidence": confidence,
                "confidence_label": confidence_label,
                "source_pipeline": "llm_extraction",
                "source_fragment_id": fragment_id,
            })

            supported_by.append({
                "from_id": fragment_id,
                "to_id": entity_id,
                "edge_type": "SUPPORTED_BY",
                "confidence": confidence,
            })

        for llm_rel in llm_result.get("relations", []):
            from_id = str(uuid.uuid5(ENTITY_NAMESPACE, llm_rel.get("from_entity", "")))
            to_id = str(uuid.uuid5(ENTITY_NAMESPACE, llm_rel.get("to_entity", "")))
            edges.append({
                "from_id": from_id,
                "to_id": to_id,
                "relation_name": llm_rel.get("relation_name", "related_to"),
                "edge_text": llm_rel.get("edge_text", ""),
                "confidence": llm_rel.get("confidence", 0.5),
                "confidence_label": llm_rel.get("confidence_label", "INFERRED"),
                "source_pipeline": "llm_extraction",
            })

        return LLMExtractionResult(
            entities=entities,
            edges=edges,
            categories=categories,
            supported_by_edges=supported_by,
        )

    def _call_llm(
        self,
        text: str,
        schema_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call the configured LLM client and parse the JSON response.

        Args:
            text: The document fragment text to extract from.
            schema_context: Optional schema definitions injected into the
                system prompt.  See ``_build_system_prompt`` for the format.

        Returns an empty-result dict when:
        - No client is configured (graceful degradation).
        - The response is not parseable JSON.
        - The provider returns an error.
        """
        if self._client is None:
            return {"entities": [], "relations": []}

        system_prompt = _build_system_prompt(schema_context)
        prompt = (
            f"Document fragment:\n\n{text}\n\n"
            "Extract all entities and relations as described."
        )
        try:
            import json
            raw = self._client.chat_complete(
                prompt,
                system_prompt=system_prompt,
                temperature=0.0,
            )
            result = json.loads(raw)
            if isinstance(result, dict):
                return result
            return {"entities": [], "relations": []}
        except LLMProviderError as exc:
            logger.warning("LLM provider error during extraction: %s", exc)
            return {"entities": [], "relations": []}
        except Exception as exc:
            logger.debug("LLM extraction parsing failed: %s", exc)
            return {"entities": [], "relations": []}
