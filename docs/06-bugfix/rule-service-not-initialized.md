# BugFix: Rule Service Not Initialized

## Issue Summary

| Item | Description |
|------|-------------|
| **Bug ID** | BUG-001 |
| **Severity** | P1 (Blocking) |
| **Date** | 2026-04-16 |
| **Status** | Fixed |

## Symptoms

1. Frontend API call to `/v1/rule-groups` returns HTTP 500
2. Error message: `{"detail":"Rule service not initialized"}`
3. Rule orchestration UI cannot load rule groups

## Root Cause Analysis

### Phase 1: Root Cause Investigation

**Evidence:**
- Backend log: `GET /v1/rule-groups?schema_id=space_7482a398 HTTP/1.1" 500 Internal Server Error`
- Error: `Rule service not initialized`

**Data Flow Trace:**
1. Frontend calls `/v1/rule-groups`
2. `ontology_engine/api/routes/rules.py` → `list_rules()` endpoint
3. Endpoint depends on `get_rule_service()` from `dependencies.py`
4. `get_rule_service()` checks if `"rule"` key exists in `_services` dict
5. `_services["rule"]` was never initialized → raises HTTPException 500

**Location of Failure:**
- `ontology_engine/api/server.py` lines 288-314 - Service initialization block
- `ontology_engine/api/dependencies.py` lines 97-101 - Service getter

### Phase 2: Pattern Analysis

**What was working:**
- Other services (`schema`, `entity`, `analysis`, `query`, `ingestion`, `visualization`, `dataset`, `incremental`) were properly initialized
- Their getter functions in `dependencies.py` worked correctly

**What was missing:**
- `services["rule"]` → `RuleService`
- `services["dag"]` → `DAGService`
- `services["simulation"]` → `SimulationService`

These three services had getter functions defined but were never added to the `services` dict during startup.

## Fix Applied

### File: `ontology_engine/api/server.py`

Added missing service initializations after line 311:

```python
services["rule"] = RuleService(storage=storage)
services["dag"] = DAGService(storage=storage, schema=schema)
services["simulation"] = SimulationService()
```

### File: `ontology_engine/services/__init__.py`

Added exports:
```python
from ontology_engine.services.rule_service import RuleService
from ontology_engine.services.dag_service import DAGService
from ontology_engine.services.simulation_service import SimulationService
```

### File: `tests/unit/api/test_services_initialization.py` (NEW)

Created test file to verify all services can be instantiated.

## Verification

```bash
# Before fix:
$ curl http://localhost:8000/v1/rule-groups?schema_id=test
{"detail":"Rule service not initialized"}

# After fix:
$ curl http://localhost:8000/v1/rule-groups?schema_id=test
{"success":true,"data":{"rule_groups":[]},"error":null,...}
```

## Related Bug: API Response Path Incorrect

### Issue
Frontend API clients were accessing `response.data.X` instead of `response.data.data.X`.

### Root Cause
Backend wraps all responses in envelope:
```json
{
  "success": true,
  "data": { "rule_groups": [] },
  "error": null,
  "meta": {...}
}
```

With axios, `response.data` is the envelope, not the inner data.

### Files Fixed
- `ontology-engine-ui/src/api/ruleGroups.ts` - 8 endpoints
- `ontology-engine-ui/src/api/ruleSteps.ts` - 4 endpoints
- `ontology-engine-ui/src/api/operators.ts` - 2 endpoints

### Pattern
```javascript
// Before (broken):
return response.data.rule_groups;

// After (fixed):
return response.data.data.rule_groups;
```

## Impact

- Rule Group List page now loads correctly
- Rule Group Create page works
- Rule Group Detail page works
- Rule Step editing works

## Test Results

```
Backend: 220 tests passed (18 pre-existing kuzu failures unrelated)
Frontend: Page loads, displays "规则", no JS errors
API: Returns 200 OK with proper JSON envelope
```
