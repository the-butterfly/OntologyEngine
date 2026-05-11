"""Cognitive engine errors."""

from __future__ import annotations

from enum import Enum
from typing import Any

from ontology_engine.engine.errors import OntologyError


class CognitiveErrorCode(str, Enum):
    MEMORY_NOT_READY = "MEMORY_NOT_READY"
    CONSOLIDATION_IN_PROGRESS = "CONSOLIDATION_IN_PROGRESS"
    PROTECTED_MEMORY = "PROTECTED_MEMORY"
    REFLECT_TIMEOUT = "REFLECT_TIMEOUT"
    MEMORY_STALE = "MEMORY_STALE"
    INVALID_MEMORY_TYPE = "INVALID_MEMORY_TYPE"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    NODE_CONFLICT = "NODE_CONFLICT"
    INVALID_BELIEF_TRANSITION = "INVALID_BELIEF_TRANSITION"
    PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
    INVALID_VISIBILITY = "INVALID_VISIBILITY"
    EMPTY_INPUT = "EMPTY_INPUT"


COGNITIVE_ERROR_HTTP_MAP: dict[CognitiveErrorCode, int] = {
    CognitiveErrorCode.MEMORY_NOT_READY: 503,
    CognitiveErrorCode.CONSOLIDATION_IN_PROGRESS: 409,
    CognitiveErrorCode.PROTECTED_MEMORY: 403,
    CognitiveErrorCode.REFLECT_TIMEOUT: 504,
    CognitiveErrorCode.MEMORY_STALE: 200,
    CognitiveErrorCode.INVALID_MEMORY_TYPE: 422,
    CognitiveErrorCode.NODE_NOT_FOUND: 404,
    CognitiveErrorCode.NODE_CONFLICT: 409,
    CognitiveErrorCode.INVALID_BELIEF_TRANSITION: 422,
    CognitiveErrorCode.PROFILE_NOT_FOUND: 404,
    CognitiveErrorCode.INVALID_VISIBILITY: 422,
    CognitiveErrorCode.EMPTY_INPUT: 422,
}


class CognitiveError(OntologyError):

    def __init__(self, message: str, code: CognitiveErrorCode | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = COGNITIVE_ERROR_HTTP_MAP.get(code, 500) if code else 500

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "error_code": self.code.value if self.code else "UNKNOWN",
            "message": str(self),
            "http_status": self.http_status,
        }
        if hasattr(self, "diagnostics"):
            data["diagnostics"] = self.diagnostics
        return data


class HallucinationError(CognitiveError):
    """Reflection output references IDs not in the available set."""

    def __init__(self, message: str, offending_ids: list[str] | None = None,
                 available_ids: set[str] | None = None):
        super().__init__(message, CognitiveErrorCode.NODE_NOT_FOUND)
        self.offending_ids = offending_ids or []
        self.available_ids = available_ids or set()
        self.diagnostics = {
            "offending_ids": self.offending_ids,
            "available_count": len(self.available_ids),
        }


class DirectiveViolationError(CognitiveError):
    """A reflection Directives hard rule was violated."""

    def __init__(self, message: str, directive_id: str, violating_action: str):
        super().__init__(message, CognitiveErrorCode.PROTECTED_MEMORY)
        self.directive_id = directive_id
        self.violating_action = violating_action
        self.diagnostics = {
            "directive_id": directive_id,
            "violating_action": violating_action,
        }


class CognitiveNodeNotFoundError(CognitiveError):

    def __init__(self, message: str = "Cognitive node not found"):
        super().__init__(message, CognitiveErrorCode.NODE_NOT_FOUND)


class CognitiveNodeConflictError(CognitiveError):

    def __init__(self, message: str = "Optimistic concurrency check failed"):
        super().__init__(message, CognitiveErrorCode.NODE_CONFLICT)


class OCCVersionConflict(CognitiveError):

    def __init__(
        self,
        node_id: str,
        expected_version: int,
        actual_version: int,
    ):
        self.node_id = node_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        message = (
            f"OCC version conflict for node {node_id}: "
            f"expected {expected_version}, actual {actual_version}"
        )
        super().__init__(message, CognitiveErrorCode.NODE_CONFLICT)


class DispositionProfileNotFoundError(CognitiveError):

    def __init__(self, message: str = "Disposition profile not found"):
        super().__init__(message, CognitiveErrorCode.PROFILE_NOT_FOUND)


class InvalidBeliefTransitionError(CognitiveError):

    def __init__(self, message: str = "Invalid belief state transition"):
        super().__init__(message, CognitiveErrorCode.INVALID_BELIEF_TRANSITION)


class MemoryNotReadyError(CognitiveError):

    def __init__(self, message: str = "Memory system not initialized"):
        super().__init__(message, CognitiveErrorCode.MEMORY_NOT_READY)


class ConsolidationInProgressError(CognitiveError):

    def __init__(self, message: str = "Consolidation task is running"):
        super().__init__(message, CognitiveErrorCode.CONSOLIDATION_IN_PROGRESS)


class ProtectedMemoryError(CognitiveError):

    def __init__(self, message: str = "Protected memory cannot be forgotten"):
        super().__init__(message, CognitiveErrorCode.PROTECTED_MEMORY)


class ReflectTimeoutError(CognitiveError):

    def __init__(self, message: str = "Reflection timeout"):
        super().__init__(message, CognitiveErrorCode.REFLECT_TIMEOUT)


class MemoryStaleError(CognitiveError):

    def __init__(self, message: str = "Memory expired but still returned"):
        super().__init__(message, CognitiveErrorCode.MEMORY_STALE)


class InvalidMemoryTypeError(CognitiveError):

    def __init__(self, memory_type: str, valid_types: set[str] | None = None):
        msg = f"Invalid memory_type: {memory_type}"
        if valid_types:
            msg += f". Must be one of {valid_types}"
        super().__init__(msg, CognitiveErrorCode.INVALID_MEMORY_TYPE)


class InvalidVisibilityError(CognitiveError):

    def __init__(self, visibility: str, valid_visibilities: set[str] | None = None):
        msg = f"Invalid visibility: {visibility}"
        if valid_visibilities:
            msg += f". Must be one of {valid_visibilities}"
        super().__init__(msg, CognitiveErrorCode.INVALID_VISIBILITY)
