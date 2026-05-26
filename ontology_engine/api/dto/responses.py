# ontology_engine/api/dto/responses.py
"""Unified API response models."""

from datetime import datetime
from enum import Enum
from typing import Any
import uuid

from fastapi.responses import JSONResponse


_ERROR_CODE_TO_HTTP_STATUS: dict[str, int] = {
    "NOT_FOUND": 404,
    "SPACE_NOT_FOUND": 404,
    "ENTITY_NOT_FOUND": 404,
    "VIEW_NOT_FOUND": 404,
    "DATASET_NOT_FOUND": 404,
    "CONCEPT_NOT_FOUND": 404,
    "NODE_NOT_FOUND": 404,
    "CONFLICT": 409,
    "SPACE_CONFLICT": 409,
    "DUPLICATE_NAME": 409,
    "INVALID_TRANSITION": 409,
    "PRECONDITION_FAILED": 412,
    "VALIDATION_ERROR": 422,
    "SCHEMA_NOT_LOADED": 422,
    "MISSING_PARAMETER": 422,
    "INVALID_REQUEST": 422,
    "FACT_OBJECT_REQUIRED": 422,
    "FILE_NOT_FOUND": 422,
    "SCHEMA_LOAD_ERROR": 422,
    "SCHEMA_CONVERT_ERROR": 422,
    "INSTANCE_LOAD_ERROR": 422,
    "SPACE_LOAD_ERROR": 422,
    "QUERY_ERROR": 400,
    "ANALYSIS_ERROR": 500,
    "INTERNAL_ERROR": 500,
    "STORAGE_ERROR": 500,
    "SNAPSHOT_ERROR": 500,
    "ROLLBACK_ERROR": 500,
    "INGESTION_ERROR": 500,
    # Cognitive memory errors
    "DB_LOCK_ERROR": 503,
    "STATS_ERROR": 503,
    "TYPES_ERROR": 503,
    "REMEMBER_ERROR": 500,
    "RECALL_ERROR": 500,
    "REFLECT_ERROR": 500,
    "APPROVE_ERROR": 500,
    "CONSOLIDATE_ERROR": 500,
    "FORGET_ERROR": 500,
    "GET_NODE_ERROR": 500,
    "CONTRADICTIONS_ERROR": 500,
    "CORRECTIONS_ERROR": 500,
    "DREAM_ERROR": 500,
    "AUDIT_ERROR": 500,
    "LIST_NODES_ERROR": 500,
    "EVIDENCE_ERROR": 500,
    "CORRECT_ERROR": 500,
}


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
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
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


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    suggestion: str | None = None,
    status_code: int | None = None,
) -> JSONResponse:
    """Create an error response with correct HTTP status code.

    Args:
        code: Structured error code (e.g., "SPACE_NOT_FOUND")
        message: Human-readable error message in English
        details: Optional structured context about the error
        suggestion: Optional suggestion for how to fix the error
        status_code: Override HTTP status code. If not provided,
                     looked up from ERROR_CODE_TO_HTTP_STATUS mapping.
                     Defaults to 500 if code is not in the mapping.

    Returns:
        JSONResponse with correct HTTP status code and structured error body.
    """
    if status_code is None:
        status_code = _ERROR_CODE_TO_HTTP_STATUS.get(code, 500)

    error_obj: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error_obj["details"] = details
    if suggestion is not None:
        error_obj["suggestion"] = suggestion

    body = {
        "success": False,
        "data": None,
        "error": error_obj,
        "meta": create_response_meta(),
    }

    return JSONResponse(status_code=status_code, content=body)
