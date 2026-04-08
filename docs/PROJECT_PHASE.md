# Project Phase Clarification

> **Last Updated:** 2026-04-08

## Current Phase: MVP Implementation

This project is in **implementation phase**, not design phase. The key design decisions have been made and documented in `discuss/2026-04-08-key-design-decisions.md`.

## Key Decisions

| # | Decision | Impact |
|---|----------|--------|
| 1 | KGML as Schema Format | Schema in YAML, separate from instances |
| 2 | Dimension Attributes Are Computed | No stored dimension_attributes, computed at query time |
| 3 | Real Rule Engine | Load rules from YAML, no hard-coded Python rules |
| 4 | OntologyEngine Is Toolchain | Package has no embedded config, reads YAML files |
| 5 | DuckDB for Storage | Not SQLite - better for analytical workloads |

## What Exists

| Component | Status | Location |
|-----------|--------|----------|
| Example Schema | ✅ | `examples/supply_chain_finance/schema.yaml` |
| Example Instances | 🔄 | `examples/supply_chain_finance/instances.yaml` (to be extracted) |
| KGML Docs | ✅ | `docs/` |

## What Doesn't Exist Yet (To Be Implemented)

| Component | Status | Notes |
|-----------|--------|-------|
| ontology_engine package | ❌ | Package structure to be created |
| KGML Schema Loader | ❌ | Parse schema.yaml |
| DuckDB Storage | ❌ | Storage implementation |
| Rule Engine | ❌ | Load and execute YAML rules |
| Instance Loader | ❌ | Load instances.yaml |
| MVP Demo Integration | ❌ | Refactor to use ontology_engine |

## Architecture

```
ontology_engine/     # Toolchain - no config embedded
├── core/schema/     # KGML models and loader
├── storage/         # DuckDB storage layer
├── engine/rule/     # Rule engine
└── engine/query/    # Query engine

examples/           # Example configurations
└── supply_chain_finance/
    ├── schema.yaml      # Schema definition (KGML)
    └── instances.yaml  # Instance data
```

## Principles

1. **KGML is canonical** - Schema defined in YAML, not Python code
2. **Instances separate from Schema** - `instances.yaml` distinct from `schema.yaml`
3. **Rules are declarative** - Rules in YAML, loaded by engine, no hard-coded logic
4. **Computed on demand** - dimension-specific derived attributes calculated at query time, not stored
5. **DuckDB for storage** - Analytical queries, not transactional SQLite

## Design Decisions

See `discuss/2026-04-08-key-design-decisions.md` for full details.

## References

- [Key Design Decisions](../../discuss/2026-04-08-key-design-decisions.md)
- [API Design](../development/api-design.md)
- [AGENTS.md](../../AGENTS.md)
