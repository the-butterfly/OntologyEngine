# ontology_engine/engine/categorization/models.py
"""Category models for L2 categorization."""

from __future__ import annotations

from typing import Any


class CategoryTags:
    """L2 categorization tags for an entity.

    Attributes:
        entity_id: The entity ID these tags belong to
        tags: Dict mapping dimension name to category value
    """

    def __init__(
        self,
        entity_id: str,
        tags: dict[str, str] | None = None
    ):
        """Initialize CategoryTags.

        Args:
            entity_id: The entity ID
            tags: Optional initial tags dict
        """
        self.entity_id = entity_id
        self.tags: dict[str, str] = tags if tags else {}

    def set(self, dimension: str, value: str) -> None:
        """Set a category value for a dimension.

        Args:
            dimension: The dimension name (e.g., "industry", "risk_level")
            value: The category value
        """
        self.tags[dimension] = value

    def get(self, dimension: str) -> str | None:
        """Get the category value for a dimension.

        Args:
            dimension: The dimension name

        Returns:
            The category value or None if not set
        """
        return self.tags.get(dimension)

    def matches(self, required: dict[str, str | list[str]]) -> bool:
        """Check if these tags match required category constraints.

        Used by L4 rules to check applies_to conditions.

        Args:
            required: Dict mapping dimension to required value(s).
                     Value can be a single string or list of acceptable values.

        Returns:
            True if all required dimensions match, False otherwise.
        """
        for dim, required_value in required.items():
            actual = self.tags.get(dim)
            if actual is None:
                return False
            if isinstance(required_value, list):
                if actual not in required_value:
                    return False
            elif actual != required_value:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "entity_id": self.entity_id,
            "tags": self.tags
        }

    def __repr__(self) -> str:
        return f"CategoryTags(entity_id={self.entity_id!r}, tags={self.tags!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CategoryTags):
            return False
        return self.entity_id == other.entity_id and self.tags == other.tags
