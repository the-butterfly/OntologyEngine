"""Core type definitions and shared utilities."""

from __future__ import annotations

import copy
from typing import Any


def apply_overrides(
    entity_data: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> None:
    """Apply override values to entity data in-place.

    Supports nested paths using dot notation:
      - "registered_capital.value" → entity_data["registered_capital"]["value"]
      - "industry" → entity_data["industry"]

    When a nested path is used and intermediate dicts don't exist,
    they are created automatically. If an intermediate value exists
    but is not a dict, a TypeError is raised to prevent data corruption.

    Note: This function modifies entity_data in-place. Callers should
    pass a deep copy if the original data must be preserved.

    Args:
        entity_data: The entity data dict to modify in-place.
        overrides: Dict of key→value overrides. Keys may use dot notation
                   for nested access. None or empty dict is a no-op.

    Raises:
        TypeError: If an intermediate path value is not a dict.
        ValueError: If a key contains empty segments (e.g., "a..b").
    """
    if not overrides:
        return

    for key, value in overrides.items():
        if "." in key:
            parts = key.split(".")
            if not all(parts):
                raise ValueError(
                    f"Override key '{key}' contains empty segments"
                )
            target = entity_data
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                    target = target[part]
                elif isinstance(target[part], dict):
                    target = target[part]
                else:
                    raise TypeError(
                        f"Cannot apply nested override '{key}': "
                        f"intermediate value at '{part}' is "
                        f"{type(target[part]).__name__}, expected dict"
                    )
            target[parts[-1]] = value
        else:
            entity_data[key] = value


def deep_copy_entity_data(data: dict[str, Any]) -> dict[str, Any]:
    """Create a deep copy of entity data for safe override application."""
    return copy.deepcopy(data)
