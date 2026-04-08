# OntologyEngine MVP - Key Design Decisions

> **Date**: 2026-04-07
> **Context**: Implementing MVP for OntologyEngine with KGML schema and DuckDB storage

## Architecture Decisions

### 1. KGML as Schema Format
- **Decision**: Use KGML (YAML-based) for schema definition, separate from instances
- **Schema file**: `schema.yaml` - defines concepts, relations, metrics, rules
- **Instances file**: `instances.yaml` - entity data
- **Why**: YAML is human-readable, supports complex nested structures, separates schema from data

### 2. DuckDB for Storage
- **Decision**: DuckDB (in-memory or file) for entity and relation storage
- **Why**: OLAP-focused, fast analytical queries, embedded (no external server), Python-native

### 3. Toolchain Architecture
- **Decision**: OntologyEngine is a toolchain library, no embedded config
- **Why**: Users configure via schema YAML, instances YAML, and code

### 4. Real Rule Engine
- **Decision**: Declarative rules with expression evaluation, not hard-coded Python
- **Rule structure**: `when` (condition), `then` (action), `else` (alternative action)
- **Expression evaluator**: Handles comparisons, boolean logic, field resolution, functions like `today()`, `days_between()`

### 5. Metric Computation
- **Decision**: Metrics are defined in schema but NOT automatically computed
- **Current approach**: Pre-compute key metrics in `_compute_entity_metrics()` before rule evaluation
- **Why**: MVP scope - full metric computation engine is future work

### 6. Dimension Attributes
- **Decision**: dimension_attributes are computed at query time, not stored
- **Why**: Derived values, don't need persistence

## Implementation Details

### Rule Execution Order
- Rules are sorted by **descending priority** (higher priority number = runs first)
- Priority 100 runs before priority 50
- This allows high-priority gating rules (like basic eligibility) to run first

### Expression Evaluator Features
- **Field resolution**: Handles nested fields like `registered_capital.value`
- **Boolean literals**: `true`/`false` strings map to Python booleans
- **Reserved words**: `true`, `false`, `and`, `or`, `not`, `in`, `is`, `none`, `null` are skipped
- **Functions**: `today()`, `days_between(date1, date2)`

### Metric Pre-computation
For Supplier entities, the following are computed before rule evaluation:
- `total_invoice_amount_90d` - sum of invoice amounts within 90 days
- `overdue_invoice_amount` - sum of overdue invoice amounts
- `overdue_invoice_ratio` - percentage
- `guarantee_chain_depth` - traverses guarantee relationships to detect cycles
- `has_guarantee_circle` - True if cycle detected (depth >= 3)

### Instance Data Linking
- Instance loader extracts relations from entity fields: `has_invoice`, `supplies_to`, `guaranteed_by`
- Related entities must be explicitly linked in instance data (no reverse relation inference)

## Schema Structure (KGML)

```yaml
metadata:        # Schema identification
types:          # Custom types (Money, Percentage, etc.)
enums:          # Enumerations
concepts:       # Entity/relation definitions
metrics:        # Metric definitions (not auto-computed)
rules:          # Rule definitions with when/then/else
data_sources:   # Data source mappings (for future)
vector_config:  # Semantic search config
llm_config:     # LLM integration config
```

## Open Issues / Future Work

1. **Metric Computation Engine**: Full implementation to compute metrics from entity data
2. **Graph Queries**: `guarantee_chain_depth` uses simple traversal, not graph algorithms
3. **Multi-dimension Analysis**: Run multiple dimensions in single analysis
4. **Type System**: Pydantic models need better type annotations for mypy
5. **Testing**: No unit tests yet
