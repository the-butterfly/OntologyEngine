"""Cognitive engine package.

Provides high-level memory management operations for the Agent Memory system.

Modules:
    models: CognitiveNode, DispositionProfile, CognitiveEdge dataclasses
    errors: Cognitive engine error types
    repository: High-level CRUD operations wrapping KuzuGraphStore
    consolidation_engine: Fragment-to-knowledge consolidation
    consolidation_types: Consolidation action types and constants
    entity_resolver: Entity disambiguation with dual-strategy
    entity_resolver_types: Resolution context and result types
    rrf_fusion: Four-path RRF fusion engine
    rrf_types: RRF constants and retrieval result types
"""

from ontology_engine.engine.cognitive.models import (
    CognitiveNode,
    CognitiveEdge,
    DispositionProfile,
    MemoryHeat,
    BeliefRevisionRule,
    DEFAULT_BELIEF_REVISION_RULES,
    apply_dynamic_weight,
    detect_rule_conflicts,
    append_history_entry,
    HISTORY_MAX_ENTRIES,
)
from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveNodeNotFoundError,
    DispositionProfileNotFoundError,
)
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.consolidation_types import (
    Fragment,
    CreateAction,
    UpdateAction,
    DeleteAction,
    ConsolidationResult,
)
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.entity_resolver_types import (
    ResolutionContext,
    ResolutionResult,
)
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.engine.cognitive.rrf_types import (
    RetrievalResult,
    TemporalConstraint,
)
from ontology_engine.engine.cognitive.lifecycle import (
    ForgettingEngine,
    DreamCycle,
    DreamCycleResult,
    compute_memory_strength,
    enforce_version_limit,
)
from ontology_engine.engine.cognitive.compilation import (
    EntityPage,
    TopicPage,
    CompilationResult,
    CompilationCache,
    CompilationDebouncer,
    CompilationScheduler,
    compile_entity_page,
    compile_topic_page,
    check_compilation_consistency,
)

__all__ = [
    "CognitiveNode",
    "CognitiveEdge",
    "DispositionProfile",
    "MemoryHeat",
    "BeliefRevisionRule",
    "DEFAULT_BELIEF_REVISION_RULES",
    "apply_dynamic_weight",
    "detect_rule_conflicts",
    "append_history_entry",
    "HISTORY_MAX_ENTRIES",
    "CognitiveError",
    "CognitiveNodeNotFoundError",
    "DispositionProfileNotFoundError",
    "CognitiveRepository",
    "ConsolidationEngine",
    "Fragment",
    "CreateAction",
    "UpdateAction",
    "DeleteAction",
    "ConsolidationResult",
    "EntityResolver",
    "ResolutionContext",
    "ResolutionResult",
    "RRFFusionEngine",
    "RetrievalResult",
    "TemporalConstraint",
    "ForgettingEngine",
    "DreamCycle",
    "DreamCycleResult",
    "compute_memory_strength",
    "enforce_version_limit",
    "EntityPage",
    "TopicPage",
    "CompilationResult",
    "CompilationCache",
    "CompilationDebouncer",
    "CompilationScheduler",
    "compile_entity_page",
    "compile_topic_page",
    "check_compilation_consistency",
]
