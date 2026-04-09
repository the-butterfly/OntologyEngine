# ontology_engine/engine/categorization/engine.py
"""L2 CategorizationEngine.

Design Decision #6: CategorizationEngine reuses the L4 RuleEngine
for derived categorization types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.engine.categorization.models import CategoryTags
from ontology_engine.storage.duckdb import DuckDBStorage

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema
    from ontology_engine.engine.rule.executor import RuleExecutor
    from ontology_engine.storage.duckdb import EntityInstance


class CategorizationEngine:
    """L2 Categorization Engine.

    Provides three types of categorization:
    - hierarchical: Direct attribute mapping
    - derived: Rule-based using RuleExecutor
    - tags: Simple condition matching

    The engine categorizes entities into business dimensions (industry,
    company_scale, risk_level, etc.) and persists results.
    """

    def __init__(
        self,
        schema: "KGMLSchema",
        storage: DuckDBStorage,
        rule_executor: "RuleExecutor",
    ):
        """Initialize CategorizationEngine.

        Args:
            schema: KGMLSchema with concept definitions
            storage: DuckDBStorage for persistence
            rule_executor: RuleExecutor for derived categorization
        """
        self.schema = schema
        self.storage = storage
        self.rule_executor = rule_executor

        # Build dimension definitions from concepts
        self._dimension_defs = self._build_dimension_defs()

    def _build_dimension_defs(self) -> dict[str, dict[str, Any]]:
        """Build dimension definitions from schema concepts.

        Returns:
            Dict mapping dimension name to dimension config
        """
        dims: dict[str, dict[str, Any]] = {}

        # Look for dimension attributes in concepts
        for concept in self.schema.concepts:
            if not concept.attributes:
                continue

            for attr in concept.attributes:
                attr_name = attr.name if hasattr(attr, 'name') else str(attr)

                # Check for known dimension-like attributes
                if attr_name in ("industry", "industry_type", "company_scale",
                                 "risk_level", "risk_rating", "credit_rating"):
                    if attr_name not in dims:
                        dims[attr_name] = {
                            "type": "hierarchical",
                            "concept": concept.name,
                            "attribute": attr_name,
                            "values": None  # Would come from schema
                        }

        return dims

    async def categorize(
        self,
        entity: "EntityInstance",
        dimensions: list[str] | None = None,
    ) -> CategoryTags:
        """Categorize an entity into L2 dimensions.

        Args:
            entity: The entity to categorize
            dimensions: Optional list of dimension names. If None, uses all.

        Returns:
            CategoryTags with all applicable categorizations
        """
        tags = CategoryTags(entity_id=entity.entity_id)

        target_dims = dimensions if dimensions else list(self._dimension_defs.keys())

        for dim_name in target_dims:
            dim_def = self._dimension_defs.get(dim_name)
            if not dim_def:
                # Try to categorize even without pre-defined dims
                value = self._categorize_hierarchical(entity, dim_name)
            else:
                dim_type = dim_def.get("type", "hierarchical")
                if dim_type == "hierarchical":
                    value = self._categorize_hierarchical(entity, dim_name)
                elif dim_type == "tags":
                    value = self._categorize_tags(entity, dim_name)
                elif dim_type == "derived":
                    value = await self._categorize_derived(entity, dim_name, dim_def)
                else:
                    continue

            if value is not None:
                tags.set(dim_name, value)
                # Persist to storage
                await self.storage.save_category_tags(entity.entity_id, tags.to_dict()["tags"])

        return tags

    async def get_tags(self, entity_id: str) -> CategoryTags | None:
        """Get existing category tags for an entity.

        Args:
            entity_id: The entity ID

        Returns:
            CategoryTags if found, None otherwise
        """
        stored = await self.storage.get_category_tags(entity_id)
        if stored is None:
            return None
        return CategoryTags(entity_id=entity_id, tags=stored)

    def _categorize_hierarchical(
        self,
        entity: "EntityInstance",
        dimension: str,
    ) -> str | None:
        """Hierarchical categorization - direct attribute mapping.

        Args:
            entity: The entity to categorize
            dimension: The dimension name

        Returns:
            The category value or None
        """
        data = entity.data if hasattr(entity, 'data') else {}

        # Common attribute name mappings for dimensions
        attr_mappings = {
            "industry": ["industry", "industry_type", "industry_category", "industry_code"],
            "company_scale": ["company_scale", "company_size", "scale", "enterprise_scale"],
            "risk_level": ["risk_level", "risk_grade", "risk_rating", "credit_rating"],
        }

        # Try mapped attribute names first
        mapped_names = attr_mappings.get(dimension, [dimension])
        for attr_name in mapped_names:
            if attr_name in data:
                value = data[attr_name]
                if isinstance(value, dict) and "value" in value:
                    value = value["value"]
                return str(value)

        # Try direct lookup
        if dimension in data:
            value = data[dimension]
            if isinstance(value, dict) and "value" in value:
                return str(value["value"])
            return str(value)

        return None

    async def _categorize_derived(
        self,
        entity: "EntityInstance",
        dimension: str,
        dim_def: dict[str, Any],
    ) -> str | None:
        """Derived categorization - rule-based using RuleExecutor.

        Args:
            entity: The entity to categorize
            dimension: The dimension name
            dim_def: The dimension definition

        Returns:
            The category value or None
        """
        # Build entity data dict
        entity_data = dict(entity.data) if hasattr(entity, 'data') else {}
        entity_data["_concept"] = entity.concept

        # Execute rules with L2_ prefix dimension
        l2_dimension = f"L2_{dimension}"

        try:
            result = await self.rule_executor.execute_dimension(
                dimension=l2_dimension,
                entity_id=entity.entity_id,
                entity_data=entity_data
            )

            # Extract category value from rule results
            for rule_result in result.rule_results:
                if rule_result.output:
                    if "category_value" in rule_result.output:
                        return str(rule_result.output["category_value"])
                    if "eligible" in rule_result.output:
                        return "ELIGIBLE" if rule_result.output["eligible"] else "INELIGIBLE"

            # Fallback: check computed metrics
            if dimension in result.computed_metrics:
                return str(result.computed_metrics[dimension])

        except Exception:
            # If rule execution fails, fall back to hierarchical
            pass

        return None

    def _categorize_tags(
        self,
        entity: "EntityInstance",
        dimension: str,
    ) -> str | None:
        """Tags-based categorization - simple condition matching.

        Args:
            entity: The entity to categorize
            dimension: The dimension name

        Returns:
            The category value or None
        """
        # For Phase 1, tags categorization is same as hierarchical
        return self._categorize_hierarchical(entity, dimension)
