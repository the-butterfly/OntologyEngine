"""Dedup strategy for Pass 3 of the extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ontology_engine.engine.extraction.ast_extractor import ASTExtractionResult
from ontology_engine.engine.extraction.llm_extractor import LLMExtractionResult


@dataclass
class ContradictionReport:
    entity_id: str
    attribute: str
    existing_value: Any
    new_value: Any
    existing_source: str
    new_source: str
    severity: str


@dataclass
class DedupResult:
    unique_entities: list[dict[str, Any]] = field(default_factory=list)
    unique_edges: list[dict[str, Any]] = field(default_factory=list)
    extracted_from_edges: list[dict[str, Any]] = field(default_factory=list)
    supported_by_edges: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[ContradictionReport] = field(default_factory=list)


class DedupStrategy:
    """Pass 3: Dedup and mutual-index edge creation."""

    def dedup_and_index(
        self,
        ast_results: ASTExtractionResult,
        llm_results: LLMExtractionResult,
        fragments: list[dict[str, Any]],
    ) -> DedupResult:
        all_entities = list(ast_results.entities) + list(llm_results.entities)
        all_edges = list(ast_results.edges) + list(llm_results.edges)

        unique_entities = self.dedup_entities(all_entities)
        unique_edges = self.dedup_edges(all_edges)
        contradictions = self.detect_contradictions(all_entities, unique_entities)

        extracted_from = list(ast_results.extracted_from_edges)
        supported_by = list(llm_results.supported_by_edges)

        return DedupResult(
            unique_entities=unique_entities,
            unique_edges=unique_edges,
            extracted_from_edges=extracted_from,
            supported_by_edges=supported_by,
            contradictions=contradictions,
        )

    def dedup_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for entity in entities:
            eid = entity.get("entity_id", "")
            if eid not in seen:
                seen[eid] = entity
            else:
                existing = seen[eid]
                existing_conf = existing.get("confidence", 0.0)
                new_conf = entity.get("confidence", 0.0)
                if new_conf > existing_conf:
                    seen[eid] = entity
                else:
                    existing_attrs = existing.get("attributes", {})
                    new_attrs = entity.get("attributes", {})
                    for k, v in new_attrs.items():
                        if k not in existing_attrs:
                            existing_attrs[k] = v
        return list(seen.values())

    def dedup_edges(self, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[tuple[str, ...], dict[str, Any]] = {}
        for edge in edges:
            from_id = edge.get("from_id", "")
            to_id = edge.get("to_id", "")
            rel = edge.get("relation_name", "")
            source = edge.get("source_pipeline", "")
            key = (from_id, to_id, rel, source)
            if key not in seen:
                seen[key] = edge
            else:
                existing_conf = seen[key].get("confidence", 0.0)
                new_conf = edge.get("confidence", 0.0)
                if new_conf > existing_conf:
                    seen[key] = edge
        return list(seen.values())

    def detect_contradictions(
        self,
        all_entities: list[dict[str, Any]],
        unique_entities: list[dict[str, Any]],
    ) -> list[ContradictionReport]:
        reports: list[ContradictionReport] = []
        by_id: dict[str, list[dict[str, Any]]] = {}
        for e in all_entities:
            eid = e.get("entity_id", "")
            by_id.setdefault(eid, []).append(e)

        for eid, versions in by_id.items():
            if len(versions) < 2:
                continue
            base = versions[0]
            for other in versions[1:]:
                base_attrs = base.get("attributes", {})
                other_attrs = other.get("attributes", {})
                for key in set(base_attrs) & set(other_attrs):
                    if base_attrs[key] != other_attrs[key]:
                        severity = "high" if (
                            base.get("confidence", 0) >= 0.8 and other.get("confidence", 0) >= 0.8
                        ) else "medium"
                        reports.append(ContradictionReport(
                            entity_id=eid,
                            attribute=key,
                            existing_value=base_attrs[key],
                            new_value=other_attrs[key],
                            existing_source=base.get("source_pipeline", ""),
                            new_source=other.get("source_pipeline", ""),
                            severity=severity,
                        ))
        return reports
