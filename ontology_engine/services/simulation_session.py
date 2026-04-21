"""Simulation Session Management for multi-round what-if analysis."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class SessionNotFoundError(KeyError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


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
    """In-memory session manager."""

    def __init__(self):
        self._sessions: dict[str, SimulationSession] = {}

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
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
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