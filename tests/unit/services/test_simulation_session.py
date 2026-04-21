import pytest
from ontology_engine.services.simulation_session import SimulationSession, SessionManager


def test_session_creation():
    session = SimulationSession(
        session_id="test-123",
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    assert session.session_id == "test-123"
    assert session.current_inputs == {}


def test_session_manager_create():
    manager = SessionManager()
    session = manager.create_session(
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    assert session.session_id is not None
    assert len(manager._sessions) == 1


def test_session_manager_get():
    manager = SessionManager()
    created = manager.create_session(
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    retrieved = manager.get_session(created.session_id)
    assert retrieved is not None
    assert retrieved.session_id == created.session_id


def test_session_manager_update_inputs():
    manager = SessionManager()
    session = manager.create_session(
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    manager.update_inputs(session.session_id, {"credit_score": 80})
    assert session.current_inputs["credit_score"] == 80


def test_session_manager_delete():
    manager = SessionManager()
    session = manager.create_session(
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    manager.delete_session(session.session_id)
    assert manager.get_session(session.session_id) is None