"""Simulation Session Management for multi-round what-if analysis."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SimulationSession:
    """Simulation session state."""

    session_id: str
    schema_id: str
    entity_id: str
    target_output: str
    execution_tree: dict[str, Any]
    current_inputs: dict[str, Any] = field(default_factory=dict)
    current_result: dict[str, Any] | None = None
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class SessionManager:
    """In-memory session manager with TTL support."""

    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: dict[str, SimulationSession] = {}
        self._ttl = ttl_seconds

    def create_session(
        self,
        schema_id: str,
        entity_id: str,
        target_output: str,
        execution_tree: dict[str, Any],
    ) -> SimulationSession:
        session_id = str(uuid.uuid4())
        session = SimulationSession(
            session_id=session_id,
            schema_id=schema_id,
            entity_id=entity_id,
            target_output=target_output,
            execution_tree=execution_tree,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SimulationSession | None:
        return self._sessions.get(session_id)

    def update_inputs(
        self,
        session_id: str,
        inputs: dict[str, Any],
        partial: bool = True,
    ) -> SimulationSession:
        session = self._sessions[session_id]
        if partial:
            session.current_inputs.update(inputs)
        else:
            session.current_inputs = inputs
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False