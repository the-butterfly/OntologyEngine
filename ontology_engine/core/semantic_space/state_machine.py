# ontology_engine/core/semantic_space/state_machine.py
"""Semantic Space State Machine - ADR-010 implementation."""

from __future__ import annotations

from typing import Any

from ontology_engine.core.semantic_space.models import (
    SemanticSpace,
    SpaceStatus,
)


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class SemanticSpaceStateMachine:
    """
    State machine for Semantic Space lifecycle.

    Implements the state transitions defined in ADR-010:
    - DRAFT → ACTIVE: activate()
    - ACTIVE → PUBLISHED: publish()
    - ACTIVE → ARCHIVED: archive()
    - PUBLISHED → ACTIVE: activate() or rollback()

    Transitions:
        DRAFT --activate()--> ACTIVE
        ACTIVE --publish()--> PUBLISHED
        ACTIVE --archive()--> ARCHIVED
        PUBLISHED --activate()--> ACTIVE (new branch)
        PUBLISHED --rollback()--> ACTIVE (restore snapshot)
    """

    # Define valid transitions: current_state -> {action: new_state}
    TRANSITIONS: dict[SpaceStatus, dict[str, SpaceStatus]] = {
        SpaceStatus.DRAFT: {
            "activate": SpaceStatus.ACTIVE,
        },
        SpaceStatus.ACTIVE: {
            "publish": SpaceStatus.PUBLISHED,
            "archive": SpaceStatus.ARCHIVED,
            "deactivate": SpaceStatus.DRAFT,
        },
        SpaceStatus.PUBLISHED: {
            "activate": SpaceStatus.ACTIVE,
            "rollback": SpaceStatus.ACTIVE,
        },
        SpaceStatus.ARCHIVED: {
            "reactivate": SpaceStatus.ACTIVE,
        },
    }

    # Preconditions for each transition
    PRECONDITIONS: dict[tuple[SpaceStatus, str], list[str]] = {
        (SpaceStatus.DRAFT, "activate"): ["has_l1_definitions"],
        (SpaceStatus.ACTIVE, "publish"): ["has_content"],
        (SpaceStatus.ACTIVE, "archive"): ["no_active_connections"],
    }

    async def transition(
        self,
        space: SemanticSpace,
        action: str,
        **kwargs: Any,
    ) -> SemanticSpace:
        """
        Execute a state transition on a semantic space.

        Args:
            space: The semantic space to transition
            action: The action to perform (activate, publish, archive, rollback)
            **kwargs: Additional parameters (e.g., created_by for publish)

        Returns:
            The updated semantic space

        Raises:
            InvalidTransitionError: If the transition is not valid
        """
        current_status = space.metadata.status

        # Check if transition is valid
        if current_status not in self.TRANSITIONS:
            raise InvalidTransitionError(f"Unknown current status: {current_status}")

        transitions = self.TRANSITIONS[current_status]
        if action not in transitions:
            valid_actions = list(transitions.keys())
            raise InvalidTransitionError(
                f"Cannot {action} from status {current_status.value}. "
                f"Valid actions: {valid_actions}"
            )

        new_status = transitions[action]

        # Check preconditions
        await self._validate_preconditions(space, current_status, action)

        # Execute the transition
        await self._execute_transition(space, current_status, new_status, action, **kwargs)

        return space

    async def _validate_preconditions(
        self,
        space: SemanticSpace,
        current_status: SpaceStatus,
        action: str,
    ) -> None:
        """Validate preconditions for a transition."""
        precondition_key = (current_status, action)
        if precondition_key not in self.PRECONDITIONS:
            return

        for precondition in self.PRECONDITIONS[precondition_key]:
            if precondition == "has_l1_definitions":
                if not space.layers.L1_fact_objects:
                    raise InvalidTransitionError(
                        "Cannot activate: at least one L1 definition required"
                    )
            elif precondition == "has_content":
                if not space.layers.L1_fact_objects and not space.instances.entities:
                    raise InvalidTransitionError(
                        "Cannot publish: space has no content"
                    )
            elif precondition == "no_active_connections":
                # Phase 2 check - for now, allow archive
                pass

    async def _execute_transition(
        self,
        space: SemanticSpace,
        current_status: SpaceStatus,
        new_status: SpaceStatus,
        action: str,
        **kwargs: Any,
    ) -> None:
        """Execute the state transition."""
        from datetime import datetime

        space.metadata.status = new_status
        space.metadata.updated_at = datetime.utcnow()

        if action == "publish":
            # Create a snapshot version
            await self._create_publish_snapshot(space, **kwargs)
        elif action == "rollback":
            # Restore from snapshot - handled by caller
            pass

    async def _create_publish_snapshot(
        self,
        space: SemanticSpace,
        **kwargs: Any,
    ) -> None:
        """Create a snapshot when publishing."""
        from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage

        # Import here to avoid circular imports
        storage = SemanticSpaceStorage()
        created_by = kwargs.get("created_by")
        description = kwargs.get("description", "Published snapshot")

        await storage.create_snapshot(
            space=space,
            description=description,
            created_by=created_by,
        )

    def get_valid_actions(self, status: SpaceStatus) -> list[str]:
        """Get list of valid actions for a given status."""
        if status not in self.TRANSITIONS:
            return []
        return list(self.TRANSITIONS[status].keys())

    def can_transition(self, status: SpaceStatus, action: str) -> bool:
        """Check if a transition is valid."""
        if status not in self.TRANSITIONS:
            return False
        return action in self.TRANSITIONS[status]


# Convenience function
async def transition_space(
    space: SemanticSpace,
    action: str,
    **kwargs: Any,
) -> SemanticSpace:
    """Transition a semantic space to a new state."""
    sm = SemanticSpaceStateMachine()
    return await sm.transition(space, action, **kwargs)
