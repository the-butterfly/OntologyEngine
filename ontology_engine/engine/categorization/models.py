# ontology_engine/engine/categorization/models.py
"""Category models for L2 categorization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ontology_engine.storage.base import CategoryTag


class CategoryTags:
    """L2 categorization tags for an entity.

    Internally stores a list of CategoryTag records, preserving
    full metadata (assigned_at, assigned_by, confidence).

    Aligned with docs/02-design/schema/instance-layer.md CategoryTag.
    """

    def __init__(
        self,
        entity_id: str,
        tags: dict[str, str] | list[CategoryTag] | None = None,
    ):
        self.entity_id = entity_id
        self._records: list[CategoryTag] = []

        if tags is None:
            pass
        elif isinstance(tags, list):
            if tags and not isinstance(tags[0], CategoryTag):
                raise TypeError(
                    f"Expected list[CategoryTag], got list[{type(tags[0]).__name__}]"
                )
            self._records = list(tags)
        elif isinstance(tags, dict):
            now = datetime.now(timezone.utc)
            for dim_name, value_code in tags.items():
                self._records.append(CategoryTag(
                    entity_id=entity_id,
                    dimension_name=dim_name,
                    value_code=value_code,
                    assigned_at=now,
                    assigned_by="rule",
                    confidence=1.0,
                ))

    @property
    def tags(self) -> dict[str, str]:
        """Backward-compatible dict view: dimension_name -> value_code."""
        return {r.dimension_name: r.value_code for r in self._records}

    def set(self, dimension: str, value: str, *, assigned_by: str = "rule", confidence: float = 1.0) -> None:
        """Set a category value for a dimension.

        If a tag for this dimension already exists, it is replaced.

        Args:
            dimension: The dimension name (e.g., "industry", "risk_level")
            value: The category value
            assigned_by: Source of the assignment ("rule", "manual", "llm")
            confidence: Confidence score for the assignment
        """
        self._records = [r for r in self._records if r.dimension_name != dimension]
        self._records.append(CategoryTag(
            entity_id=self.entity_id,
            dimension_name=dimension,
            value_code=value,
            assigned_at=datetime.now(timezone.utc),
            assigned_by=assigned_by,
            confidence=confidence,
        ))

    def add_tag(self, tag: CategoryTag) -> None:
        """Add a fully-specified CategoryTag record.

        Replaces any existing tag for the same dimension.

        Args:
            tag: Complete CategoryTag with metadata
        """
        self._records = [r for r in self._records if r.dimension_name != tag.dimension_name]
        self._records.append(tag)

    def get(self, dimension: str) -> str | None:
        """Get the category value for a dimension.

        Args:
            dimension: The dimension name

        Returns:
            The category value or None if not set
        """
        for r in self._records:
            if r.dimension_name == dimension:
                return r.value_code
        return None

    def get_tag(self, dimension: str) -> CategoryTag | None:
        """Get the full CategoryTag record for a dimension.

        Args:
            dimension: The dimension name

        Returns:
            The CategoryTag record or None if not set
        """
        for r in self._records:
            if r.dimension_name == dimension:
                return r
        return None

    def get_records(self) -> list[CategoryTag]:
        """Return all CategoryTag records."""
        return list(self._records)

    def matches(self, required: dict[str, str | list[str]]) -> bool:
        """Check if these tags match required category constraints.

        Used by L4 rules to check applies_to conditions.

        Args:
            required: Dict mapping dimension to required value(s).
                     Value can be a single string or list of acceptable values.

        Returns:
            True if all required dimensions match, False otherwise.
        """
        tags_dict = self.tags
        for dim, required_value in required.items():
            actual = tags_dict.get(dim)
            if actual is None:
                return False
            if isinstance(required_value, list):
                if actual not in required_value:
                    return False
            elif actual != required_value:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation (backward-compatible)."""
        return {
            "entity_id": self.entity_id,
            "tags": self.tags,
        }

    def __repr__(self) -> str:
        return f"CategoryTags(entity_id={self.entity_id!r}, tags={self.tags!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CategoryTags):
            return False
        return self.entity_id == other.entity_id and self.tags == other.tags
