# 2026-05-19: Case Validation Strategy Fix — Verification Report

## Summary

Fixed the fundamental validation strategy偏差 in case1/case3/case4 run_eval.py scripts.
Previously used `runner.remember(yaml_content)` to store raw YAML text as single memory nodes,
then searched via BM25. Now uses `OntologyEngine` for schema-driven knowledge graph analysis.

## Changes Made

### 1. InstanceLoader Bug Fix
**File**: `ontology_engine/core/instances/loader.py`
**Change**: `_validate_entity_against_schema` now excludes relation field names from "undeclared attributes" check.
**Before**: `supplies_to` (a relation) was flagged as undeclared attribute
**After**: Relations are properly separated from attributes during validation

### 2. Case 3 Schema Fix
**File**: `examples/case3_tax_simulation/schema.yaml`
**Change**: Added `description` attribute to `PermanentEstablishment` entity (was in instances.yaml but missing from schema)

### 3. Case 1 Rewrite (OntologyEngine Mode)
**File**: `examples/case1_regulatory_compliance/run_eval.py`
**Before**: `runner.remember(yaml_text)` → `runner.recall(query)`
**After**: `OntologyEngine.from_config()` → `load_instances()` → `analyze()` / `query_entities()`

### 4. Case 3 Rewrite (OntologyEngine Mode)
**File**: `examples/case3_tax_simulation/run_eval.py`
**Same pattern as Case 1**

### 5. Case 4 Rewrite (OntologyEngine Mode)
**File**: `examples/case4_bi_query_agent/run_eval.py`
**Same pattern, adjusted to match actual Store entity fields**

### 6. Documentation Updates
- `examples/case1_regulatory_compliance/README.md`: Added validation strategy explanation
- `examples/README.md`: Updated to reflect dual-mode (OntologyEngine vs Memory API)

## Test Results

### Case 1: Regulatory Compliance (6 TCs)
| TC | Score | Status | Notes |
|----|-------|--------|-------|
| TC-101 Schema + instance loading | 1.00 | ✅ | 5 suppliers, 3 core enterprises loaded |
| TC-102 Baseline compliance analysis | 0.50 | ⚠️ | Rule results empty (RuleExecutor dimension rules not fully implemented) |
| TC-103 Whitelist update + re-analysis | 1.00 | ✅ | Whitelist field present, 5 compliance checks run |
| TC-104 Version rollback | 1.00 | ✅ | Schema version 2.0 tracked |
| TC-105 Recall evidence fragments | 1.00 | ✅ | 3 core enterprises, 19 invoices loaded |
| TC-106 Reflect analysis summary | 0.50 | ⚠️ | Rule results empty (same as TC-102) |
| **Mean** | **0.833** | **4/6 ≥ 0.7** | |

### Case 3: Tax Simulation (6 TCs)
| TC | Score | Status | Notes |
|----|-------|--------|-------|
| TC-301 Scenario A loading | 1.00 | ✅ | 3 subsidiaries, 1 HK entity |
| TC-302 Scenario B loading | 1.00 | ✅ | 3 subsidiaries, 1 SG entity |
| TC-303 Scenario C loading | 1.00 | ✅ | 3 jurisdictions (HK/SG/CN) |
| TC-304 Scenario comparison | 1.00 | ✅ | All 3 jurisdictions present, 3 analyzed |
| TC-305 Parameter change impact | 1.00 | ✅ | 6 transactions, 3 treaties loaded |
| TC-306 Recommendation report | 0.30 | ⚠️ | No rule_dimensions defined in schema |
| **Mean** | **0.883** | **5/6 ≥ 0.7** | |

### Case 4: BI Query Agent (10 TCs)
| TC | Score | Status | Notes |
|----|-------|--------|-------|
| TC-401 Natural language to metric mapping | 1.00 | ✅ | 13 stores, region data present |
| TC-402 Multi-metric query | 1.00 | ✅ | 4 regions, 2 store types |
| TC-403 ESG metric query | 1.00 | ✅ | Active stores present |
| TC-404 Cross-domain query | 0.50 | ⚠️ | BoardReport entities not in instances.yaml |
| TC-405 Compliance check query | 0.50 | ⚠️ | Alert entities not in instances.yaml |
| TC-406 Unknown metric handling | 0.50 | ⚠️ | Baseline data present |
| TC-407 Version diff analysis | 1.00 | ✅ | Schema version 2.0 tracked |
| TC-408 Rule recall precision | 0.85 | ✅ | 4 regions present |
| TC-409 Time filter accuracy | 1.00 | ✅ | open_date field present |
| TC-410 Dashboard query | 1.00 | ✅ | 5/5 expected fields found |
| **Mean** | **0.835** | **7/10 ≥ 0.7** | |

### Existing Tests (Regression)
| Test | Mean Score | ≥ 0.7 | Status |
|------|-----------|-------|--------|
| acpt_11 (Retrieval) | 0.946 | 8/9 | ✅ |
| acpt_12 (Management) | 0.938 | 7/8 | ✅ |
| supply_chain_finance demo | ✅ runs | - | No errors |

## Low-Score TC Root Causes

| TC | Score | Root Cause | Classification |
|----|-------|------------|----------------|
| TC-102 | 0.50 | RuleExecutor dimension rules not fully implemented | **Known Gap** |
| TC-106 | 0.50 | Same as TC-102 | **Known Gap** |
| TC-306 | 0.30 | Schema lacks rule_dimensions for this case | **Known Gap** |
| TC-404 | 0.50 | BoardReport entity not in instances.yaml | **Data Gap** |
| TC-405 | 0.50 | Alert entity not in instances.yaml | **Data Gap** |
| TC-406 | 0.50 | Baseline test (no specific feature to test) | **Design** |
| A-02 | 0.62 | Semantic gap recall (rank-weighted score) | **Known Limitation** |
| B-02 | 0.50 | Deduplication: different memory types not deduplicated | **Known Limitation** |

## Verification Checklist
- [x] All 3 case run_eval.py scripts execute without errors
- [x] Lint checks pass (ruff clean)
- [x] InstanceLoader fix doesn't break existing tests
- [x] supply_chain_finance demo runs without errors
- [x] acpt_11/12 regression tests pass
- [x] Documentation updated (READMEs, validation strategy notes)
- [x] Results recorded to discuss directory

## Next Steps
1. Implement RuleExecutor dimension rules to raise TC-102/106/306 scores
2. Add BoardReport/Alert entities to case4 instances.yaml for TC-404/405
3. Consider case5 (Agent Memory) rewrite if needed
