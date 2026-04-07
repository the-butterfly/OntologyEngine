# TODO - Based on Critical Review (2026-04-07)

## 🔴 High Priority (Must Fix Before MVP)

### TODO-001: Clarify SQLite + NetworkX Architecture
- **Issue:** SQLite + NetworkX dual storage causes consistency problems
- **Task:** Decide on ONE graph storage strategy:
  - Option A: SQLite only (accept limitations)
  - Option B: DuckDB + NetworkX with proper persistence
  - Option C: SQLite as metadata, NetworkX as sole graph (no SQLite graph ops)
- **Owner:** TBD
- **Status:** Open

### TODO-002: Implement Real Rule Engine (Not Hard-coded)
- **Issue:** mvp_demo.py RuleEngine is if/else, not declarative
- **Task:**
  1. Define YAML/JSON rule format
  2. Implement RuleLoader
  3. Implement DAG-based rule executor
- **Owner:** TBD
- **Status:** Open
- **Blocked By:** TODO-003

### TODO-003: Add Operator Registration System
- **Issue:** operator.md describes correct design but code doesn't implement it
- **Task:** Implement `engine/rules/operators/base.py` OperatorRegistry
- **Owner:** TBD
- **Status:** Open

## 🟡 Medium Priority (Before Phase 2)

### TODO-004: Faiss Dimension Handling
- **Issue:** Hard-coded 1536 dimension, no migration strategy
- **Task:**
  1. Store dimension in vector metadata
  2. Validate dimension consistency on insert
  3. Document index rebuild process
- **Owner:** TBD
- **Status:** Open

### TODO-005: Define LLM Inference Boundary
- **Issue:** LLM/符号推理协同 undefined
- **Task:** Before Phase 4, define:
  1. When to use LLM vs symbolic reasoning
  2. Prompt templates for each use case
  3. Cost control (caching, rate limiting)
- **Owner:** TBD
- **Status:** Open

### TODO-006: Document Concurrent Write Model
- **Issue:** SQLite WAL mode but no multi-writer strategy
- **Task:** Define:
  1. Single-writer requirement (at app level)
  2. Transaction boundaries
  3. Optimistic/pessimistic locking if needed
- **Owner:** TBD
- **Status:** Open

### TODO-007: Resolve dimension_attributes Conflict
- **Issue:** Schema dimension_attributes vs Concept attributes conceptual conflict
- **Task:** Decide:
  1. Attributes are global OR dimension-scoped (not both)
  2. Update schema.yaml examples accordingly
  3. Update concepts.md
- **Owner:** TBD
- **Status:** Open

## 🟢 Lower Priority (Nice to Have)

### TODO-008: Update consistency-check.md
- **Issue:** Current check only verifies doc-doc consistency, not doc-code
- **Task:** Add section verifying:
  1. Each documented module has corresponding code
  2. Interfaces match implementation
- **Owner:** TBD
- **Status:** Open

### TODO-009: AGENTS.md Constraint Validation
- **Issue:** AGENTS.md references non-existent directories
- **Task:** Update constraint checks to:
  1. Reference existing paths only
  2. Add check: `ls ontology_engine/*/` for existing modules
- **Owner:** TBD
- **Status:** Open

---

## Progress Tracking

| TODO | Priority | Status | Owner | Completed |
|------|----------|--------|-------|-----------|
| TODO-001 | 🔴 | Open | - | - |
| TODO-002 | 🔴 | Open | - | - |
| TODO-003 | 🔴 | Open | - | - |
| TODO-004 | 🟡 | Open | - | - |
| TODO-005 | 🟡 | Open | - | - |
| TODO-006 | 🟡 | Open | - | - |
| TODO-007 | 🟡 | Open | - | - |
| TODO-008 | 🟢 | Open | - | - |
| TODO-009 | 🟢 | Open | - | - |
