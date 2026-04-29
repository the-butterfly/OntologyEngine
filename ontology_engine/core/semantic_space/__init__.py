# ontology_engine/core/semantic_space/__init__.py
"""Semantic space management module.

A semantic space is a versioned, self-contained knowledge graph that packages:
- Schema declaration (L1-L4 layers)
- Instance data (entities and relations)
- Rule definitions and logics (separated)
- Version snapshots

Usage:
    from ontology_engine.core.semantic_space import SemanticSpace

    space = SemanticSpace(
        metadata=SpaceMetadata(id="space1", name="Test Space"),
        ...
    )
"""

from ontology_engine.core.semantic_space.models import (
    SemanticSpace,
    SpaceMetadata,
    SpaceVersion,
    SpaceStatus,
    SpaceType,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    Authorization,
    ConsumptionView,
)

from ontology_engine.core.semantic_space.rule_models import (
    TargetObject,
    InputElement,
    OutputElement,
    ApplicableScope,
    RuleDefinition,
    ApplicableCondition,
    RuleWhen,
    RuleAction,
    RuleLogic,
)

from ontology_engine.core.schema.models import (
    RuleDefinitionDeclaration,
    RuleLogicDeclaration,
    StepDeclaration,
    StepAction,
    StepCondition,
)

from ontology_engine.core.semantic_space.storage import (
    SemanticSpaceStorage,
    SemanticSpaceStorageError,
)

from ontology_engine.core.semantic_space.state_machine import (
    SemanticSpaceStateMachine,
    InvalidTransitionError,
    transition_space,
)

from ontology_engine.core.semantic_space.loader import (
    SpaceLoader,
    SpaceLoaderError,
)

__all__ = [
    # Core models
    "SemanticSpace",
    "SpaceMetadata",
    "SpaceVersion",
    "SpaceStatus",
    "SpaceType",
    "SemanticSpaceLayers",
    "L4BusinessLogic",
    "SpaceInstances",
    "Authorization",
    "ConsumptionView",
    # Rule models (legacy - use V3 models below)
    "TargetObject",
    "InputElement",
    "OutputElement",
    "ApplicableScope",
    "RuleDefinition",
    "ApplicableCondition",
    "RuleWhen",
    "RuleAction",
    "RuleLogic",
    # V3 Rule models (preferred)
    "RuleDefinitionDeclaration",
    "RuleLogicDeclaration",
    "StepDeclaration",
    "StepAction",
    "StepCondition",
    # Storage
    "SemanticSpaceStorage",
    "SemanticSpaceStorageError",
    # State machine (ADR-010)
    "SemanticSpaceStateMachine",
    "InvalidTransitionError",
    "transition_space",
    # Loader
    "SpaceLoader",
    "SpaceLoaderError",
]
