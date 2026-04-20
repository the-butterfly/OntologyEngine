# ontology_engine/api/dto/responses.py
"""Unified API response models."""

from datetime import datetime
from typing import Any
import uuid


def _serialize_data(obj: Any) -> Any:
    """Recursively serialize data for JSON compatibility.

    Handles DTO objects with to_dict(), lists, dicts, and primitives.
    """
    if obj is None:
        return None
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if isinstance(obj, list):
        return [_serialize_data(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize_data(v) for k, v in obj.items()}
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return obj


def create_response_meta() -> dict[str, Any]:
    """Create response metadata dict."""
    return {
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat()
    }


def success_response(data: Any = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a successful response dict.

    Automatically serializes DTO objects via to_dict() if present.
    """
    response_meta = create_response_meta()
    if meta:
        response_meta.update(meta)
    return {
        "success": True,
        "data": _serialize_data(data),
        "error": None,
        "meta": response_meta,
    }


def error_response(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create an error response dict."""
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message, "details": details},
        "meta": create_response_meta()
    }
