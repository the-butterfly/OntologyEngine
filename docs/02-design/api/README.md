# API Design

> **status**: draft
> **phase**: phase1
> **source_of_truth**: `docs/01-overview/04-modules.md`, `docs/02-design/services/README.md`, `docs-baseline/05-schema-v2/09-canonical-schema-spec.md`
> **last_verified**: 2026-04-19
> **[待核对代码]**

---

## Overview

This document defines the REST API interface for OntologyEngine, providing a clean route design aligned with the five-layer architecture. The API layer (L4) exposes services to external clients while maintaining strict boundaries with lower layers.

**Design Principles**:
- RESTful resource-based routing
- Service layer directly mapped to resources (SchemaService, EntityService, QueryService, etc.)
- Schema v2 terminology for all request/response fields
- No storage engine specifics leaked to API consumers

---

## Base URL

```
/v1
```

---

## Route Groups

| Prefix | Description | Service |
|--------|-------------|---------|
| `/v1/spaces` | Semantic Spaces lifecycle and management | SchemaService, EntityService |
| `/v1/views` | Consumption views and analysis execution | AnalysisService, VisualizationService |
| `/v1/actions` | Business action definitions and execution | RuleService, AnalysisService |
| `/v1/query` | Knowledge retrieval (Layer-R/S dual channel) | QueryService |
| `/v1/ontology` | Global ontology schema operations | SchemaService |

---

## 1. /v1/spaces - Semantic Spaces

Semantic Spaces are containers for organizing fact objects (entities/relations) with their associated schemas across L1-L4 layers.

### 1.1 Space CRUD

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/spaces` | List all semantic spaces |
| `POST` | `/v1/spaces` | Create a new semantic space |
| `GET` | `/v1/spaces/{space_id}` | Get space details |
| `PUT` | `/v1/spaces/{space_id}` | Update space metadata |
| `DELETE` | `/v1/spaces/{space_id}` | Delete a space (soft delete) |

**Path Parameters**:
- `space_id` (string): Unique space identifier

**Example - Create Space Request**:
```json
{
  "name": "company_analysis",
  "type": "management",
  "description": "Company entity analysis space",
  "fact_objects": {
    "entities": [],
    "relations": []
  },
  "categorizations": {
    "dimensions": []
  },
  "analytical_elements": {
    "metrics": []
  },
  "business_logic": {
    "rule_definitions": [],
    "rule_logics": []
  }
}
```

### 1.2 Space Lifecycle

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/spaces/{space_id}/activate` | Activate a draft space |
| `POST` | `/v1/spaces/{space_id}/deactivate` | Deactivate an active space |
| `POST` | `/v1/spaces/{space_id}/archive` | Archive a space |

**Lifecycle States**: `DRAFT` -> `ACTIVE` -> `ARCHIVED`

### 1.3 Schema Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/spaces/{space_id}/schema` | Get complete schema (L1-L4) |
| `PUT` | `/v1/spaces/{space_id}/schema` | Update complete schema |
| `GET` | `/v1/spaces/{space_id}/schema/L1/fact-objects` | Get L1 fact objects |
| `PUT` | `/v1/spaces/{space_id}/schema/L1/fact-objects` | Update L1 fact objects |
| `GET` | `/v1/spaces/{space_id}/schema/L2/categorizations` | Get L2 categorizations |
| `PUT` | `/v1/spaces/{space_id}/schema/L2/categorizations` | Update L2 categorizations |
| `GET` | `/v1/spaces/{space_id}/schema/L3/analytical-elements` | Get L3 analytical elements |
| `PUT` | `/v1/spaces/{space_id}/schema/L3/analytical-elements` | Update L3 analytical elements |
| `GET` | `/v1/spaces/{space_id}/schema/L4/rules` | Get L4 business logic rules |
| `PUT` | `/v1/spaces/{space_id}/schema/L4/rules` | Update L4 business logic rules |

### 1.4 Instance Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/spaces/{space_id}/instances/entities` | List entities in space |
| `POST` | `/v1/spaces/{space_id}/instances/entities` | Create entity instance |
| `GET` | `/v1/spaces/{space_id}/instances/entities/{entity_id}` | Get entity details |
| `PUT` | `/v1/spaces/{space_id}/instances/entities/{entity_id}` | Update entity |
| `DELETE` | `/v1/spaces/{space_id}/instances/entities/{entity_id}` | Delete entity |
| `GET` | `/v1/spaces/{space_id}/instances/relations` | List relations in space |
| `POST` | `/v1/spaces/{space_id}/instances/relations` | Create relation instance |
| `GET` | `/v1/spaces/{space_id}/instances/relations/{relation_id}` | Get relation details |
| `DELETE` | `/v1/spaces/{space_id}/instances/relations/{relation_id}` | Delete relation |

**Instance Schema (Entity)**:
```json
{
  "entity_type": "Company",
  "attributes": {
    "name": "Example Company",
    "registered_capital": {
      "value": 10000000,
      "currency": "CNY"
    },
    "status": "ACTIVE"
  }
}
```

### 1.5 Version Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/spaces/{space_id}/versions` | List version history |
| `GET` | `/v1/spaces/{space_id}/versions/{version}` | Get specific version |
| `POST` | `/v1/spaces/{space_id}/versions/{version}/rollback` | Rollback to version |
| `POST` | `/v1/spaces/{space_id}/versions/{version}/promote` | Promote version to production |

---

## 2. /v1/views - Consumption Views

Views are derived perspectives over Semantic Spaces, enabling analysis execution and result consumption.

### 2.1 View Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views` | List all views |
| `POST` | `/v1/views` | Create a view |
| `GET` | `/v1/views/{view_id}` | Get view definition |
| `PUT` | `/v1/views/{view_id}` | Update view definition |
| `DELETE` | `/v1/views/{view_id}` | Delete view |

**View Definition**:
```json
{
  "name": "company_risk_view",
  "space_id": "space.company_analysis",
  "dimensions": ["risk_level", "company_scale"],
  "metrics": ["credit_score", "guarantee_exposure"],
  "rules": ["risk_assessment_rule"]
}
```

### 2.2 View Entity Operations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views/{view_id}/entities` | Get entities in view scope |
| `GET` | `/v1/views/{view_id}/entities/{entity_id}` | Get entity in view context |

### 2.3 Schema Graph

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views/{view_id}/schema-graph` | Get schema dependency graph |

**Response**: Graph structure showing L1-L4 dependencies

### 2.4 Rule Dependency Graph

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views/{view_id}/rules/dependency-graph` | Get rule execution DAG |

### 2.5 Entity Rules

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views/{view_id}/rules/for-entity/{entity_id}` | Get applicable rules for entity |

### 2.6 Execution

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/views/{view_id}/execute/analyze` | Execute full analysis |
| `POST` | `/v1/views/{view_id}/execute/simulate` | Simulate execution (no persistence) |
| `POST` | `/v1/views/{view_id}/execute/entity/{entity_id}` | Execute for specific entity |

**Analyze Request**:
```json
{
  "entity_ids": ["ent_001", "ent_002"],
  "rules": ["risk_assessment"],
  "metrics": ["credit_score"],
  "include_trace": true
}
```

### 2.7 Metrics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views/{view_id}/metrics` | List computed metrics |
| `GET` | `/v1/views/{view_id}/metrics/{entity_id}` | Get metrics for entity |

### 2.8 Execution Trace

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/views/{view_id}/execution/{entity_id}` | Get execution trace for entity |
| `GET` | `/v1/views/{view_id}/execution/{entity_id}/{dimension}` | Get trace for specific dimension |

---

## 3. /v1/actions - Business Actions

Business actions are executable operations derived from L4 rule definitions, providing explainable execution.

### 3.1 Action Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/actions` | List all action definitions |
| `GET` | `/v1/actions/{action_name}` | Get action definition |

### 3.2 Execution

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/actions/{action_name}/execute` | Execute action |
| `POST` | `/v1/actions/{action_name}/execute/{entity_id}` | Execute action for entity |

**Execute Request**:
```json
{
  "entity_id": "ent_001",
  "inputs": {
    "override_metrics": {
      "credit_score": 750
    }
  },
  "dry_run": false
}
```

### 3.3 Explanation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/actions/{action_name}/explain/{entity_id}` | Get action execution explanation |

**Explain Response**:
```json
{
  "action_name": "approve_credit",
  "entity_id": "ent_001",
  "decision": "APPROVED",
  "rule_chain": ["eligibility_check", "credit_calculation", "final_approval"],
  "metric_values": {
    "credit_score": 750,
    "guarantee_exposure": 5000000
  },
  "applied_rules": [
    {
      "rule": "eligibility_check",
      "result": "PASSED",
      "reason": "Entity meets all preconditions"
    }
  ]
}
```

---

## 4. /v1/query - Knowledge Retrieval

Query operations provide Layer-R (vector) and Layer-S (structured) dual-channel retrieval.

### 4.1 Vector Search (Layer-R)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/query/search` | Execute vector similarity search |

**Search Request**:
```json
{
  "query_text": "Find companies with high credit risk",
  "space_id": "space.company_analysis",
  "top_k": 10,
  "filters": {
    "status": "ACTIVE"
  },
  "include_vectors": false
}
```

### 4.2 Graph Traversal (Layer-S)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/query/graph` | Execute graph traversal query |

**Graph Request**:
```json
{
  "start_entity_id": "ent_001",
  "traversal": {
    "type": "neighbors",
    "relation": "has_subsidiary",
    "depth": 2,
    "direction": "outgoing"
  },
  "aggregations": [
    {
      "type": "count",
      "field": "name",
      "output": "subsidiary_count"
    }
  ]
}
```

### 4.3 Path Query

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/query/paths` | Find paths between entities |

**Paths Request**:
```json
{
  "from_entity_id": "ent_001",
  "to_entity_id": "ent_099",
  "max_hops": 3,
  "relation_types": ["has_subsidiary", "has_shareholder"]
}
```

### 4.4 Trace

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/query/trace/{entity_id}` | Get entity provenance trace |

### 4.5 Hybrid Query

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/query/hybrid` | Execute hybrid search (Layer-R + Layer-S) |

**Hybrid Request**:
```json
{
  "query_text": "High risk guarantee relationships",
  "space_id": "space.company_analysis",
  "filters": {
    "status": "ACTIVE"
  },
  "fusion": "rrf",
  "rrf_k": 60
}
```

---

## 5. /v1/ontology - Global Ontology

Global ontology operations for cross-space schema management.

### 5.1 Get Ontology

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/ontology` | Get global ontology schema |
| `GET` | `/v1/ontology/spaces/{space_id}` | Get ontology for specific space |

### 5.2 Load Schema

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/ontology/load` | Load schema from YAML/KGML |
| `POST` | `/v1/ontology/validate` | Validate schema syntax and semantics |

**Load Request**:
```json
{
  "schema_yaml": "...(KGML content)...",
  "space_id": "space.company_analysis",
  "validate_only": false
}
```

### 5.3 Version History

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/ontology/versions` | List global ontology versions |
| `GET` | `/v1/ontology/versions/{version_id}` | Get specific version |

### 5.4 Cross-Space Operations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/ontology/diff?from={v1}&to={v2}` | Diff between two versions |
| `POST` | `/v1/ontology/merge` | Merge multiple spaces into global |

---

## Common Request/Response Patterns

### Error Response

```json
{
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Entity ent_999 not found in space space.company_analysis",
    "details": {
      "entity_id": "ent_999",
      "space_id": "space.company_analysis"
    }
  }
}
```

### Pagination

List endpoints support pagination:
```
GET /v1/spaces?page=1&page_size=20
```

**Paginated Response**:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

## Service Layer Mapping

| Route Group | Primary Service | Supporting Services |
|-------------|-----------------|---------------------|
| `/v1/spaces` | SchemaService, EntityService | DatasetService |
| `/v1/views` | AnalysisService, VisualizationService | QueryService |
| `/v1/actions` | RuleService, AnalysisService | EntityService |
| `/v1/query` | QueryService | VisualizationService |
| `/v1/ontology` | SchemaService | DatasetService |

---

## Design Constraints

1. **No storage engine exposure**: API responses use Schema v2 terminology, never internal storage names (KuzuDB, ChromaDB, SQLite)
2. **Service boundary enforcement**: API layer calls only services, never engine or storage directly
3. **Versioning**: All routes under `/v1/` prefix for future compatibility
4. **Schema-driven**: Request/response structures align with KGML schema definitions

---

## Reference Documents

| Document | Role |
|----------|------|
| `docs/01-overview/04-modules.md` | Module architecture and layer definitions |
| `docs/02-design/services/README.md` | Service layer detailed design |
| `docs-baseline/05-schema-v2/09-canonical-schema-spec.md` | Schema v2 grammar (source of truth) |
