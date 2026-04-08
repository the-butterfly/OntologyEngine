# Key Design Decisions - 2026-04-08

## Context
Session to clarify MVP implementation approach after critical review feedback.

---

## Decision 1: KGML as Schema Format

**Decision:** Use KGML v3 format as the canonical schema definition language.

**Rationale:**
- Already have a detailed `examples/supply_chain_finance/schema.yaml` using KGML
- KGML supports all needed concepts: metadata, types, enums, concepts, metrics, rules, data_sources, vector_config
- Separates schema definition from instance data

**File Organization:**
```
examples/supply_chain_finance/
├── schema.yaml          # Canonical schema definition (KGML format)
├── instances.yaml       # Instance data (entities, relations)
└── rules.yaml           # Optional: separate rules file (future)
```

**Action:**
- Keep `schema.yaml` in examples as canonical
- Create `instances.yaml` by extracting instance data from current `schema.yaml`
- Update docs to reflect this structure

---

## Decision 2: Dimension Attributes Are Computed, Not Stored

**Decision:** `dimension_attributes` are dimension-scoped derived properties, computed at query/execution time, NOT stored on the raw entity.

**Rationale:**
- A Supplier entity has the same core attributes regardless of dimension
- Different analysis dimensions (credit_assessment, transaction_monitoring) define different derived views
- These derived values are computed from base attributes + metrics when needed

**Schema Structure:**
```yaml
concepts:
  - name: "Supplier"
    attributes:
      - name: "supplier_id"      # Stored, global
      - name: "company_name"     # Stored, global
      - name: "registered_capital" # Stored, global

    # No dimension_attributes here - they are computed
    # derived_attributes defined at metric/dimension level
```

**Derived Properties Location:**
- Defined per dimension in `rules` or `metrics` section
- Computed when that dimension is activated
- Never stored as entity attributes

**Implication:**
- Remove `dimension_attributes` from concepts
- Add `derived_attributes` to metrics or keep in rules section
- Update schema.yaml to reflect this

---

## Decision 3: Real Rule Engine (No Hard-Coded Rules)

**Decision:** Implement a real rule engine that loads rules from YAML configuration. Start simple, extend later.

**MVP Rule Engine Scope:**
```
RuleEngine
├── load_rules(yaml_path)     # Load rules from YAML
├── validate_rules()          # Validate rule syntax
├── execute_rule(rule_id)      # Execute single rule
├── execute_dimension()        # Execute all rules for a dimension
└── get_results()             # Get execution results
```

**Rule Format (from KGML):**
```yaml
rules:
  ruleset:
    - id: "R001_basic_eligibility"
      type: "constraint"        # constraint | inference | alert | decision
      scope:
        dimensions: ["credit_assessment"]
        entity_types: ["Supplier"]
      when:
        expression: "status == 'ACTIVE'"   # Simple expression language
      then:
        action: "approve"
```

**Expression Language (MVP):**
- Simple comparisons: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Boolean logic: `and`, `or`, `not`
- Field access: `supplier.status`, `invoice.amount.value`
- Functions: `today()`, `days_between()`, `sum()`, `avg()`

**NOT in MVP:**
- Graph queries (Cypher)
- Complex DAG dependency resolution
- Nested expressions

**Extension Task (Future):**
- Full expression parser (AST-based)
- Graph-aware operators
- Rule dependency DAG with topological execution

---

## Decision 4: OntologyEngine Is a Toolchain, Not a Configured System

**Decision:** `ontology_engine` package is a toolchain for agents. It reads YAML configs and executes. It has NO built-in configuration files.

**Design Principle:**
```
ontology_engine/     # Toolchain - no config embedded
├── core/            # Core data models
├── storage/         # Storage abstractions
├── engine/          # Rule engine, query engine
├── services/        # Business logic services
└── api/             # API layer

examples/            # Example configurations (not part of package)
├── supply_chain_finance/
│   ├── schema.yaml       # Schema definition
│   ├── instances.yaml    # Instance data
│   └── rules.yaml        # Rule definitions (optional)
```

**Usage Pattern:**
```python
from ontology_engine import OntologyEngine

engine = OntologyEngine.from_config("path/to/schema.yaml")
result = engine.analyze(
    entity_id="SUP_2024_001",
    dimension="credit_assessment"
)
```

**Future Todo:**
- Management API/tools to build schema.yaml, instances.yaml, rules.yaml
- CLI commands for CRUD operations on configurations
- UI for configuration management

---

## Decision 5: DuckDB for Storage Layer

**Decision:** Use DuckDB as the primary local storage, NOT SQLite.

**Rationale (from review feedback):**
- SQLite + NetworkX dual storage causes consistency issues
- DuckDB handles complex data types better
- Good performance for analytical queries
- Supports persistent storage with Parquet/CSV backing

**MVP Storage Stack:**
```
DuckDB                     # Primary OLAP storage
├── entities table         # All entity data
├── relations table        # All relations
├── metrics table          # Computed metrics
└── vector storage?        # Future: integrate Faiss

In-Memory Graph (NetworkX) # For graph algorithms
├── For guarantee_circle detection
├── For path queries
└── Sync from DuckDB on load
```

**Why Not SQLite:**
- SQLite WAL mode but no true concurrent writer model
- NetworkX + SQLite = dual storage problems
- DuckDB is better for analytical workloads

**Why DuckDB Now:**
- Single storage for entities + analytics
- Can load from Parquet/CSV (future)
- Good Python integration
- No dual storage issues

---

## Implementation Priority (MVP)

### Phase 1: Core Infrastructure
1. Create `ontology_engine/` package structure
2. Implement `config.py` for YAML loading
3. Create KGML schema parser (load schema.yaml)
4. Implement DuckDB storage layer (entities, relations)

### Phase 2: Rule Engine
1. Create rule YAML loader
2. Implement simple expression evaluator
3. Implement RuleEngine class
4. Execute rules from schema.yaml

### Phase 3: Integration
1. Refactor mvp_demo.py to use ontology_engine
2. Load instances from instances.yaml
3. Execute dimension analysis using rules
4. Return results

### Phase 4 (Future): Extensions
1. Add graph algorithms (NetworkX for guarantee circle)
2. Add vector storage (Faiss)
3. Add management tools

---

## Files to Create/Modify

### New Files
```
ontology_engine/
├── __init__.py
├── __main__.py
├── config.py
├── core/
│   ├── __init__.py
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── models.py         # KGML data models
│   │   ├── loader.py         # YAML schema loader
│   │   └── validator.py      # Schema validator
│   ├── types/
│   │   ├── __init__.py
│   │   └── primitives.py
│   └── instances/
│       ├── __init__.py
│       ├── loader.py
│       └── models.py
├── storage/
│   ├── __init__.py
│   ├── base.py               # Storage interfaces
│   └── duckdb/
│       ├── __init__.py
│       └── store.py          # DuckDB implementation
├── engine/
│   ├── __init__.py
│   ├── rule/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── loader.py
│   │   ├── evaluator.py      # Simple expression evaluator
│   │   └── executor.py
│   └── query/
│       └── __init__.py
└── api/
    └── __init__.py

examples/supply_chain_finance/
├── schema.yaml               # Keep as-is
├── instances.yaml           # Extract from schema.yaml
└── rules.yaml               # Extract from schema.yaml (optional)

docs/
└── development/
    └── api-design.md         # Update with new decisions
```

### Files to Update
- `docs/development/api-design.md` - Add KGML schema format, rule engine API
- `docs/concepts.md` - Clarify dimension_attributes are computed
- `examples/supply_chain_finance/schema.yaml` - Remove dimension_attributes from concepts
- `examples/supply_chain_finance/instances.yaml` - Extract instance data
- `docs/PROJECT_PHASE.md` - Update to reflect decisions

---

## Questions Resolved

| # | Question | Decision |
|---|----------|----------|
| 1 | KGML vs Pydantic | KGML as canonical, Pydantic for code models |
| 2 | dimension_attributes | Computed at query time, not stored |
| 3 | Rule format | Real rule engine, YAML-based, simple expression language |
| 4 | Config location | Examples folder, ontology_engine is toolchain only |
| 5 | Storage | DuckDB + optional NetworkX for graph algorithms |

---

## Next Steps

1. Update `docs/development/api-design.md` with new API designs
2. Extract `instances.yaml` from current `schema.yaml`
3. Remove `dimension_attributes` from `schema.yaml` concepts
4. Create `ontology_engine/` package structure
5. Implement KGML schema loader
6. Implement DuckDB storage layer
7. Implement rule engine
8. Refactor mvp_demo.py
