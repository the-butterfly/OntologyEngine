from __future__ import annotations

import pytest

from ontology_engine.core.semantic_space.models import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SemanticSpaceLayers,
    L4BusinessLogic,
)


def _make_space(
    status: SpaceStatus = SpaceStatus.DRAFT,
    has_l1: bool = False,
    has_l4: bool = False,
) -> SemanticSpace:
    space = SemanticSpace(
        metadata=SpaceMetadata(id="test-space", name="Test", status=status),
        layers=SemanticSpaceLayers(),
    )
    if has_l1:
        space.layers.L1_fact_objects = [{"id": "fo1", "name": "TestFactObject"}]
    if has_l4:
        space.layers.L4_business_logic = L4BusinessLogic(
            rule_definitions=[{"id": "rd1", "name": "TestRule"}],
        )
    return space


class TestStateMachineTransitions:
    @pytest.mark.asyncio
    async def test_draft_activate_with_l1_and_l4(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.DRAFT, has_l1=True, has_l4=True)
        result = await sm.transition(space, "activate")
        assert result.metadata.status == SpaceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_draft_activate_without_l1_fails(self):
        from ontology_engine.core.semantic_space.state_machine import (
            InvalidTransitionError,
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.DRAFT, has_l1=False, has_l4=True)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(space, "activate")

    @pytest.mark.asyncio
    async def test_draft_activate_without_l4_fails(self):
        from ontology_engine.core.semantic_space.state_machine import (
            InvalidTransitionError,
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.DRAFT, has_l1=True, has_l4=False)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(space, "activate")

    @pytest.mark.asyncio
    async def test_active_deactivate(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.ACTIVE)
        result = await sm.transition(space, "deactivate")
        assert result.metadata.status == SpaceStatus.DRAFT

    @pytest.mark.asyncio
    async def test_active_archive(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.ACTIVE)
        result = await sm.transition(space, "archive")
        assert result.metadata.status == SpaceStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_archived_reactivate(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.ARCHIVED)
        result = await sm.transition(space, "reactivate")
        assert result.metadata.status == SpaceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self):
        from ontology_engine.core.semantic_space.state_machine import (
            InvalidTransitionError,
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.DRAFT)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(space, "archive")

    @pytest.mark.asyncio
    async def test_can_transition(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        assert sm.can_transition(SpaceStatus.DRAFT, "activate") is True
        assert sm.can_transition(SpaceStatus.DRAFT, "archive") is False
        assert sm.can_transition(SpaceStatus.ACTIVE, "deactivate") is True
        assert sm.can_transition(SpaceStatus.ARCHIVED, "reactivate") is True

    @pytest.mark.asyncio
    async def test_get_valid_actions(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        assert "activate" in sm.get_valid_actions(SpaceStatus.DRAFT)
        assert "deactivate" in sm.get_valid_actions(SpaceStatus.ACTIVE)
        assert "archive" in sm.get_valid_actions(SpaceStatus.ACTIVE)
        assert "reactivate" in sm.get_valid_actions(SpaceStatus.ARCHIVED)

    @pytest.mark.asyncio
    async def test_draft_activate_without_l1_and_l4_fails(self):
        from ontology_engine.core.semantic_space.state_machine import (
            InvalidTransitionError,
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.DRAFT, has_l1=False, has_l4=False)
        with pytest.raises(InvalidTransitionError):
            await sm.transition(space, "activate")

    @pytest.mark.asyncio
    async def test_published_activate(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.PUBLISHED)
        result = await sm.transition(space, "activate")
        assert result.metadata.status == SpaceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_published_rollback(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.PUBLISHED)
        result = await sm.transition(space, "rollback")
        assert result.metadata.status == SpaceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_active_publish(self):
        from ontology_engine.core.semantic_space.state_machine import (
            SemanticSpaceStateMachine,
        )

        sm = SemanticSpaceStateMachine()
        space = _make_space(SpaceStatus.ACTIVE, has_l1=True)
        result = await sm.transition(space, "publish")
        assert result.metadata.status == SpaceStatus.PUBLISHED
