# ontology_engine/api/dto/responses.py
"""Unified API response models."""

from datetime import datetime
from typing import Any
import uuid


def create_response_meta() -> dict[str, Any]:
    """Create response metadata dict."""
    return {
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat()
    }


def success_response(data: Any = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a successful response dict."""
    response_meta = create_response_meta()
    if meta:
        response_meta.update(meta)
    return {
        "success": True,
        "data": data,
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


# Keep Pydantic models for documentation purposes (not used in routes)
class ResponseMeta:
    """Response metadata - kept for type hints and documentation."""
    pass


class ErrorDetail:
    """Error details - kept for type hints and documentation."""
    pass


class APIResponse:
    """Unified API response format - kept for type hints and documentation."""
    pass
