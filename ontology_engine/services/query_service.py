# ontology_engine/services/query_service.py
"""Query service for pattern matching and graph traversal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.services.dto import (
    SearchResultResponse,
)
from ontology_engine.storage.base import StorageBackend

if TYPE_CHECKING:
    from ontology_engine.engine.rule import RuleExecutor


class QueryService:
    """Query service.

    Handles pattern matching, graph traversal, and rule tracing.
    """

    def __init__(
        self,
        storage: StorageBackend,
        rule_executor: RuleExecutor | None = None,
    ):
        """Initialize QueryService.

        Args:
            storage: DuckDBStorage instance
            rule_executor: Optional RuleExecutor for rule tracing
        """
        self.storage = storage
        self.rule_executor = rule_executor

    async def pattern_match(
        self,
        concept: str,
        patterns: dict[str, Any] | None = None
    ) -> list[SearchResultResponse]:
        """Pattern match entities by concept and attribute patterns.

        Args:
            concept: Concept type to match
            patterns: Attribute patterns to match (supports exact match)

        Returns:
            List of matching SearchResultResponse
        """
        entities = await self.storage.query_entities(
            concept=concept,
            filters=patterns
        )

        return [
            SearchResultResponse(
                entity_id=e.entity_id,
                concept_type=e.concept,
                score=1.0,
                attributes=e.data
            )
            for e in entities
        ]

    async def graph_traverse(
        self,
        entity_id: str,
        relation_type: str,
        direction: str = "outgoing",
        depth: int = 1
    ) -> list[SearchResultResponse]:
        """Traverse graph from entity via relations.

        Args:
            entity_id: Starting entity ID
            relation_type: Relation type to traverse
            direction: "outgoing" or "incoming"
            depth: Traversal depth (max 2 in Phase 1)

        Returns:
            List of traversed entities with relations
        """
        if depth > 2:
            raise ValueError("Phase 1 maximum depth is 2")

        results = []
        visited = set()
        current_level = [(entity_id, None)]

        for _ in range(depth):
            next_level = []
            for current_id, rel_data in current_level:
                neighbors = await self.storage.get_neighbors(
                    entity_id=current_id,
                    relation_type=relation_type,
                    direction=direction
                )

                for entity, relation in neighbors:
                    if entity.entity_id not in visited:
                        visited.add(entity.entity_id)
                        results.append(SearchResultResponse(
                            entity_id=entity.entity_id,
                            concept_type=entity.concept,
                            score=1.0,
                            attributes={
                                **entity.data,
                                "_relation_type": relation.relation_type,
                                "_related_from": current_id
                            }
                        ))
                        next_level.append((entity.entity_id, relation.data))

            current_level = next_level

        return results

    async def trace_rule(
        self,
        entity_id: str,
        rule_id: str | None = None
    ) -> list[dict]:
        """Trace rule execution history for an entity.

        Args:
            entity_id: Entity to trace
            rule_id: Optional specific rule to trace

        Returns:
            List of rule execution records
        """
        # This would query the rule_execution_log table
        # For now, return empty list as log_rule_execution is the write side
        self.storage._ensure_initialized()

        if rule_id:
            cursor = await self.storage._conn.execute(
                """SELECT entity_id, rule_id, result, executed_at
                   FROM rule_execution_log
                   WHERE entity_id = ? AND rule_id = ?
                   ORDER BY executed_at DESC""",
                [entity_id, rule_id]
            )
        else:
            cursor = await self.storage._conn.execute(
                """SELECT entity_id, rule_id, result, executed_at
                   FROM rule_execution_log
                   WHERE entity_id = ?
                   ORDER BY executed_at DESC""",
                [entity_id]
            )

        results = cursor.fetchall()
        return [
            {
                "entity_id": row[0],
                "rule_id": row[1],
                "result": row[2],
                "executed_at": str(row[3])
            }
            for row in results
        ]

    async def find_path(
        self,
        from_entity_id: str,
        to_entity_id: str,
        max_depth: int = 3
    ) -> list[list[str]]:
        """Find paths between two entities.

        Args:
            from_entity_id: Start entity
            to_entity_id: Target entity
            max_depth: Maximum path depth

        Returns:
            List of paths, each path is a list of entity IDs
        """
        if max_depth > 3:
            raise ValueError("Phase 1 maximum path depth is 3")

        paths = []
        visited = set()

        async def dfs(current: str, target: str, path: list[str]) -> None:
            if current == target:
                paths.append(path.copy())
                return
            if len(path) >= max_depth:
                return

            visited.add(current)
            neighbors = await self.storage.get_neighbors(
                entity_id=current,
                relation_type="has_invoice",  # Default relation
                direction="outgoing"
            )

            for entity, _ in neighbors:
                if entity.entity_id not in visited:
                    path.append(entity.entity_id)
                    await dfs(entity.entity_id, target, path)
                    path.pop()

            visited.remove(current)

        await dfs(from_entity_id, to_entity_id, [from_entity_id])
        return paths
