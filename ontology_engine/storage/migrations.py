"""Storage-layer data migrations.

Each migration function transforms a dict from an older schema version
to the current format.  Migrations are applied by ``CognitiveNode.from_dict``
before field filtering.

To add a new migration:
1. Write a ``_migrate_X`` function below.
2. Add it to ``MIGRATE_COGNITIVE_NODE`` list (order matters: oldest first).
3. Add a unit test in ``tests/unit/storage/test_migrations.py``.
"""

from __future__ import annotations

from typing import Any


def _migrate_tags_list_to_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Migration: tags as list[str] → dict[str, str | list[str]].

    Old format: ``["domain:finance", "source:report"]``
    New format: ``{"domain": "finance", "source": "report"}``

    Tags without a colon go into ``{"_legacy": [...]}``.
    """
    tags = data.get("tags")
    if not isinstance(tags, list):
        return data

    data = dict(data)
    migrated: dict[str, str | list[str]] = {}
    for t in tags:
        if ":" in t:
            k, v = t.split(":", 1)
            migrated[k] = v
        else:
            migrated.setdefault("_legacy", []).append(t)  # type: ignore[union-attr]
    data["tags"] = migrated
    return data


def _migrate_model_domain_to_tags(data: dict[str, Any]) -> dict[str, Any]:
    """Migration: model_domain (removed field) → tags["model"].

    The ``model_domain`` field was removed from CognitiveNode in favour
    of storing it inside ``tags``.  This migration preserves old data.
    """
    model_domain = data.get("model_domain")
    if not model_domain:
        return data

    data = dict(data)
    tags = data.get("tags")
    if tags is None or not isinstance(tags, dict):
        data["tags"] = tags = {}
    if "model" not in tags:
        tags["model"] = model_domain
    return data


MIGRATE_COGNITIVE_NODE = [
    _migrate_tags_list_to_dict,
    _migrate_model_domain_to_tags,
]


def apply_cognitive_node_migrations(data: dict[str, Any]) -> dict[str, Any]:
    """Apply all registered migrations to a CognitiveNode dict.

    Migrations are applied in order; each receives the output of the
    previous one.  The input dict is not mutated.
    """
    for migrate_fn in MIGRATE_COGNITIVE_NODE:
        data = migrate_fn(data)
    return data
