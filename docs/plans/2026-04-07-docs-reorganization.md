# Docs Reorganization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize docs directory by archiving oversized raw designs, splitting large files, creating TODO清单, and addressing review feedback about doc-code misalignment.

**Architecture:**
- Archive `docs/raw/` to `docs/archive/design-proposals/` (not deleted, just moved)
- Split `critical-review-response.md` (1732 lines) into focused decision docs by topic
- Create `docs/TODO.md` with concrete tasks from review feedback
- Add `docs/PROJECT_PHASE.md` to clarify current project phase (design vs implementation)
- Consolidate overlapping content in development/ folder

**Tech Stack:** Markdown, file manipulation

---

## Task 1: Archive Raw Design Documents

**Files:**
- Move: `docs/raw/` → `docs/archive/design-proposals/`

**Step 1: Create archive directory**

```bash
mkdir -p docs/archive/design-proposals
```

**Step 2: Move raw files to archive**

```bash
mv docs/raw/kgml-v3-design.md docs/archive/design-proposals/
mv docs/raw/rule_management_detailed_design.md docs/archive/design-proposals/
mv docs/raw/rule_management_detailed_design_part2.md docs/archive/design-proposals/
mv docs/raw/financial_kg_optimized_design.md docs/archive/design-proposals/
```

**Step 3: Remove empty raw directory**

```bash
rmdir docs/raw
```

**Step 4: Create archive index**

Create `docs/archive/README.md`:
```markdown
# Archived Design Proposals

> These documents contain detailed design proposals that were used for discussion but are NOT yet implemented.

| Document | Status | Notes |
|----------|--------|-------|
| kgml-v3-design.md | Archived | KGML format design (superseded by current Schema design) |
| rule_management_detailed_design.md | Archived | Rule engine design (not implemented) |
| rule_management_detailed_design_part2.md | Archived | Rule engine detailed ops (not implemented) |
| financial_kg_optimized_design.md | Archived | Financial domain design (reference only) |
```

**Step 5: Commit**

```bash
git add -A && git commit -m "docs: archive raw design proposals"
```

---

## Task 2: Split critical-review-response.md by Topic

**Files:**
- Create: `docs/architecture/decisions/001-sqlite-graphstore-v2.md`
- Create: `docs/architecture/decisions/002-dimension-attributes-resolution.md`
- Create: `docs/architecture/decisions/003-rule-engine-declaration-format.md`
- Create: `docs/architecture/decisions/004-llm-inference-boundary.md`
- Create: `docs/architecture/decisions/005-concurrent-write-model.md`
- Modify: `docs/critical-review-response.md` (replace with index + summary)

**Step 1: Read critical-review-response.md to extract sections**

Extract these sections:
1. SQLiteGraphStore v2 design (around line 19-100)
2. dimension_attributes resolution (search for "dimension_attributes")
3. rule engine declaration format (search for "规则以数据格式声明")
4. LLM inference boundary (search for "LLM 推理")
5. concurrent write model (search for "并发写入")

**Step 2: Create decision docs**

Each decision doc follows format:
```markdown
# ADR-001: Title

**Status:** Proposed/Accepted/Rejected

**Context:** (the problem)

**Decision:** (the chosen approach)

**Consequences:** (positive and negative)
```

**Step 3: Replace critical-review-response.md with index**

Summary pointing to individual decision docs with brief summary of each.

**Step 4: Commit**

```bash
git add docs/architecture/decisions/ docs/critical-review-response.md && git commit -m "docs: split critical-review into architectural decisions"
```

---

## Task 3: Create PROJECT_PHASE.md

**Files:**
- Create: `docs/PROJECT_PHASE.md`

**Step 1: Write PROJECT_PHASE.md**

```markdown
# Project Phase Clarification

> **Last Updated:** 2026-04-07

## Current Phase: MVP Implementation

This project is in **implementation phase**, not design phase. The documentation describes the **target architecture**, not the current state.

### What Exists

| Component | Status | Location |
|-----------|--------|----------|
| Schema Models | ✅ Implemented | `ontology_engine/core/schema/` |
| MVP Demo | ✅ Implemented | `mvp_demo.py` (hard-coded logic, NOT engine) |
| Documentation | 🔄 In Progress | `docs/` |

### What Doesn't Exist Yet

| Component | Status | Notes |
|-----------|--------|-------|
| SQLiteGraphStore | ❌ Not Implemented | `storage/local/sqlite_graph.py` does not exist |
| FaissVectorStore | ❌ Not Implemented | `storage/local/faiss_vector.py` does not exist |
| RuleEngine | ❌ Not Implemented | mvp_demo.py has hard-coded if/else |
| QueryExecutor | ❌ Not Implemented | `engine/query/` directories don't exist |
| API Server | ❌ Not Implemented | `api/` routes not implemented |

### Principles

1. **Docs follow code, not code follows docs** - Document what exists, not what should exist
2. **MVP first** - Implement minimal working system before architectural generalization
3. **Incremental architecture** - Make it work, then make it right

### References

- [AGENTS.md](../../AGENTS.md) - Development constraints
- [roadmap.md](../roadmap.md) - Implementation milestones
```

**Step 2: Commit**

```bash
git add docs/PROJECT_PHASE.md && git commit -m "docs: add project phase clarification"
```

---

## Task 4: Create TODO.md from Review Feedback

**Files:**
- Create: `docs/TODO.md`

**Step 1: Write TODO.md with concrete tasks**

```markdown
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
```

**Step 2: Commit**

```bash
git add docs/TODO.md && git commit -m "docs: add TODO from critical review"
```

---

## Task 5: Update README.md Navigation

**Files:**
- Modify: `docs/README.md`

**Step 1: Update README.md**

Update the docs navigation to include new files:
- Add `PROJECT_PHASE.md` to core design section
- Add `TODO.md` prominently
- Add `archive/` section pointing to archived designs
- Add `architecture/decisions/` for split decisions

**Step 2: Commit**

```bash
git add docs/README.md && git commit -m "docs: update README navigation"
```

---

## Task 6: Create Architecture Decisions Index

**Files:**
- Create: `docs/architecture/decisions/README.md`

**Step 1: Write index**

```markdown
# Architecture Decisions

> Collected decisions from critical review and implementation learning.

## Decision Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | SQLite + NetworkX Storage Strategy | Pending | 2026-04-07 |
| ADR-002 | Rule Declaration Format | Pending | 2026-04-07 |
| ADR-003 | Dimension Attributes Resolution | Pending | 2026-04-07 |
| ADR-004 | LLM Inference Boundary | Pending | 2026-04-07 |
| ADR-005 | Concurrent Write Model | Pending | 2026-04-07 |

## Creating New Decisions

When a significant architectural decision is made:

1. Create `docs/architecture/decisions/XXX-title.md`
2. Follow ADR format (Status, Context, Decision, Consequences)
3. Update this index
4. Commit with `docs: add ADR-XXX`
```

**Step 2: Commit**

```bash
git add docs/architecture/decisions/README.md && git commit -m "docs: add architecture decisions index"
```

---

## Summary of Changes

| Action | Files |
|--------|-------|
| Archive raw designs | 4 files moved to `docs/archive/design-proposals/` |
| Split critical-review | 1 file → 5 decision docs + 1 index |
| Add PROJECT_PHASE | 1 new file |
| Add TODO | 1 new file with 9 tasks |
| Update README | 1 modified |
| Create decisions index | 1 new file |
| **Total** | ~7 new files, 1 modified, 4 moved |
