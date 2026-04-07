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
