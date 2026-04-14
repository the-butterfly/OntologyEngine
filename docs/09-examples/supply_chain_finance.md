# 供应链金融端到端用户案例

> **场景**: 供应商"北京智造科技"申请融资授信
>
> **验证目标**: OntologyEngine 管理面 → Schema → 数据集 → 规则执行 → 可视化 → Agent 调用

## 前置条件

- OntologyEngine 服务已启动 (`uvicorn ontology_engine.api.server:app`)
- 示例数据已加载 (`examples/supply_chain_finance/schema.yaml` + `instances.yaml`)
- 实体 COMP001 (北京智造科技有限公司) 已存在于系统中

---

## Step 1: 创建管理空间

**MCP 工具**: `oe_create_space`
**HTTP 方法**: `POST /v1/management/spaces`

### 请求

```json
{
  "name": "供应链金融v2",
  "description": "供应链金融风控模型管理空间",
  "domain": "supply_chain_finance",
  "space_type": "management"
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "space_id": "space_scf_v2",
    "name": "供应链金融v2",
    "domain": "supply_chain_finance",
    "space_type": "management",
    "status": "DRAFT",
    "view_id": "view_scf_v2",
    "created_at": "2026-04-13T10:00:00Z"
  }
}
```

### 验证点

- [ ] `space_id` 非空且唯一
- [ ] `view_id` 自动生成，与 `space_id` 关联
- [ ] `status` 为 DRAFT 或 ACTIVE

---

## Step 2: Schema 上传与加载

**MCP 工具**: `oe_load_schema`
**HTTP 方法**: `PUT /v1/management/{spaceId}/schema`

### 请求

```json
{
  "schema_version": "2.0",
  "semantic_space": {
    "id": "kg://scf/v2.0",
    "name": "供应链金融风控模型 v2",
    "type": "management",
    "status": "ACTIVE"
  },
  "fact_objects": {
    "entities": [
      {
        "name": "Company",
        "description": "企业",
        "attributes": [
          {"name": "uscc", "type": "string", "required": true, "unique": true},
          {"name": "name", "type": "string", "required": true},
          {"name": "registered_capital", "type": "Money"},
          {"name": "status", "type": "enum", "enum_type": "CompanyStatus"}
        ]
      }
    ],
    "relations": [
      {
        "name": "Guarantee",
        "from": "Company",
        "to": "Company",
        "attributes": [
          {"name": "amount", "type": "Money", "required": true},
          {"name": "type", "type": "enum", "enum_type": "GuaranteeType"}
        ]
      }
    ]
  },
  "categorizations": {
    "dimensions": [
      {"name": "industry", "type": "hierarchical", "values": [{"code": "C", "name": "制造业"}]},
      {"name": "company_scale", "type": "derived", "rule_logic": "determine_scale"},
      {"name": "risk_level", "type": "derived", "rule_logic": "assess_risk"}
    ]
  },
  "analytical_elements": {
    "metrics": [
      {"name": "credit_score", "type": "composite", "description": "综合信用评分"},
      {"name": "guarantee_exposure", "type": "graph", "description": "担保敞口", "dependencies": ["Guarantee"]}
    ]
  },
  "business_logic": {
    "rule_definitions": [
      {
        "name": "global_eligibility_check",
        "description": "全局准入检查",
        "applies_to": {"fact_objects": [], "categories": {}},
        "preconditions": [
          {"expression": "status == 'ACTIVE'", "fail": {"reject": true, "reason": "企业状态非正常"}}
        ],
        "outputs": [{"name": "base_eligible", "type": "boolean"}]
      },
      {
        "name": "credit_assessment",
        "description": "融资授信评估",
        "applies_to": {"fact_objects": ["Company"], "categories": {"industry": ["C", "F"]}},
        "inputs": [{"metric": "credit_score"}, {"metric": "guarantee_exposure"}],
        "outputs": [
          {"name": "eligible", "type": "boolean"},
          {"name": "credit_limit", "type": "Money"},
          {"name": "interest_rate", "type": "decimal"}
        ]
      }
    ],
    "rule_logics": [
      {
        "name": "credit_assessment_logic",
        "description": "供应链金融授信评估完整流程",
        "steps": [
          {"id": "R001", "name": "信用分准入", "priority": 100, "condition": {"and": [{"expression": "credit_score >= 60"}, {"expression": "guarantee_exposure < registered_capital.value * 2"}]}, "action": {"type": "set_flag", "flag": "eligible", "value": true}},
          {"id": "R004", "name": "授信额度计算", "priority": 80, "depends_on": ["R001"], "condition": "eligible == true", "action": {"type": "compute", "output": "credit_limit", "operator": "SWITCH", "input": "risk_bucket", "branches": [{"condition": "LOW_RISK", "formula": "min(registered_capital * 0.6, 15000000)"}], "default": "min(registered_capital * 0.2, 5000000)"}},
          {"id": "R005", "name": "差异化利率定价", "priority": 70, "depends_on": ["R004"], "action": {"type": "compute", "output": "interest_rate", "operator": "SCORECARD", "baseline": 0.045}}
        ]
      }
    ]
  }
}
```

### 验证 Schema

**HTTP 方法**: `GET /v1/management/{spaceId}/schema`

### 响应

```json
{
  "success": true,
  "data": {
    "schema_version": "2.0",
    "semantic_space": {"id": "kg://scf/v2.0"},
    "fact_objects": {
      "entities": [{"name": "Company"}],
      "relations": [{"name": "Guarantee"}]
    },
    "categorizations": {
      "dimensions": [
        {"name": "industry"},
        {"name": "company_scale"},
        {"name": "risk_level"}
      ]
    },
    "analytical_elements": {
      "metrics": [
        {"name": "credit_score"},
        {"name": "guarantee_exposure"}
      ]
    },
    "business_logic": {
      "rule_definitions": [
        {"name": "global_eligibility_check"},
        {"name": "credit_assessment"}
      ],
      "rule_logics": [
        {"name": "credit_assessment_logic", "steps_count": 3}
      ]
    }
  }
}
```

### 验证点

- [ ] Schema 版本为 2.0
- [ ] L1 事实对象包含 Company 和 Guarantee
- [ ] L2 分类维度包含 3 个维度
- [ ] L4 业务逻辑包含 2 个规则定义

---

## Step 3: 数据集注册与同步

**MCP 工具**: `oe_register_dataset`
**HTTP 方法**: `POST /v1/management/{spaceId}/datasets`

### 3.1 注册数据集

```json
{
  "name": "北京智造科技企业数据",
  "description": "供应商 COMP001 的企业注册与财务数据",
  "source_type": "file",
  "source_config": {
    "format": "yaml",
    "path": "examples/supply_chain_finance/instances.yaml"
  },
  "target_concept": "Company"
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "dataset_id": "ds_comp001",
    "name": "北京智造科技企业数据",
    "status": "CREATED",
    "created_at": "2026-04-13T10:05:00Z"
  }
}
```

### 3.2 配置字段映射

**HTTP 方法**: `POST /v1/management/{spaceId}/datasets/{datasetId}/mappings`

```json
{
  "field_mappings": [
    {"source": "entities[0].attributes.uscc", "target": "Company.uscc"},
    {"source": "entities[0].attributes.name", "target": "Company.name"},
    {"source": "entities[0].attributes.registered_capital", "target": "Company.registered_capital"},
    {"source": "entities[0].attributes.status", "target": "Company.status"},
    {"source": "entities[0].attributes.annual_revenue", "target": "Company.annual_revenue"},
    {"source": "entities[0].attributes.total_assets", "target": "Company.total_assets"},
    {"source": "entities[0].attributes.total_liabilities", "target": "Company.total_liabilities"}
  ],
  "relation_mappings": [
    {"source": "relations[0]", "target": "Guarantee", "from": "COMP001", "to": "COMP002"}
  ]
}
```

### 3.3 触发同步

**MCP 工具**: `oe_trigger_sync`
**HTTP 方法**: `POST /v1/management/{spaceId}/datasets/{datasetId}/sync`

```json
{
  "mode": "full",
  "dry_run": false
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "sync_id": "sync_20260413_001",
    "status": "COMPLETED",
    "entities_loaded": 1,
    "relations_loaded": 1,
    "started_at": "2026-04-13T10:05:30Z",
    "completed_at": "2026-04-13T10:05:32Z",
    "duration_ms": 234
  }
}
```

### 验证点

- [ ] 数据集状态为 CREATED
- [ ] 字段映射配置成功
- [ ] 同步任务状态为 COMPLETED
- [ ] 实体数量和关系数量正确

---

## Step 4: 规则执行与结果验证

**MCP 工具**: `oe_execute_rule`
**HTTP 方法**: `POST /v1/consumption/views/{viewId}/execute/analyze`

### 4.1 执行信用评估规则

```json
{
  "entity_id": "COMP001",
  "dimension": "credit_assessment",
  "explain_level": "full"
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "entity_id": "COMP001",
    "fact_object": "Company",
    "execution": {
      "timestamp": "2026-04-13T10:10:00Z",
      "rule_definitions": {
        "global_eligibility_check": {
          "matched": true,
          "results": {"base_eligible": true}
        },
        "credit_assessment": {
          "matched": true,
          "applies_to": {"industry": "C", "risk_level": "LOW"},
          "results": {
            "R001": {"eligible": true},
            "R004": {"credit_limit": 7500000},
            "R005": {"interest_rate": 0.072}
          }
        }
      },
      "final_output": {
        "eligible": true,
        "credit_limit": {"value": 7500000, "currency": "CNY"},
        "interest_rate": 0.072
      }
    }
  }
}
```

### 4.2 获取 Schema 图数据

**HTTP 方法**: `GET /v1/visualize/schema/graph`
查询参数: `graph_type=entity_relation`, `space_id=space_scf_v2`

### 响应

```json
{
  "success": true,
  "data": {
    "schema_id": "kg://scf/v2.0",
    "graph_type": "entity_relation",
    "nodes": [
      {"id": "Company", "type": "entity", "data": {"label": "企业", "layer": "L1"}},
      {"id": "Invoice", "type": "entity", "data": {"label": "发票", "layer": "L1"}}
    ],
    "edges": [
      {"id": "e1", "source": "Company", "target": "Invoice", "type": "relation", "data": {"label": "has_invoice"}}
    ],
    "metadata": {"entity_count": 5, "relation_count": 4, "metric_count": 10, "rule_count": 7}
  }
}
```

### 4.3 获取规则链 DAG

**HTTP 方法**: `GET /v1/visualize/rule-chain/credit_assessment`

### 响应

```json
{
  "success": true,
  "data": {
    "dimension": "credit_assessment",
    "nodes": [
      {"id": "R001", "data": {"ruleName": "信用分准入", "priority": 100, "ruleType": "constraint"}},
      {"id": "R004", "data": {"ruleName": "授信额度计算", "priority": 80, "ruleType": "decision"}},
      {"id": "R005", "data": {"ruleName": "差异化利率定价", "priority": 70, "ruleType": "decision"}}
    ],
    "edges": [
      {"id": "R001-R004", "source": "R001", "target": "R004", "data": {"dependency_type": "data_flow"}},
      {"id": "R004-R005", "source": "R004", "target": "R005", "data": {"dependency_type": "data_flow"}}
    ],
    "dimension_info": {"name": "credit_assessment", "rule_count": 7}
  }
}
```

### 验证点

- [ ] `eligible == true`
- [ ] `credit_limit.value == 7500000`
- [ ] `credit_limit.currency == CNY`
- [ ] `interest_rate == 0.072`
- [ ] Schema 图节点数 >= 5
- [ ] 规则链 DAG 包含 R001, R004, R005

---

## Step 5: What-if 模拟

**HTTP 方法**: `POST /v1/visualize/simulate`

### 5.1 模拟场景：降低信用分 + 担保链加深

```json
{
  "entity_id": "COMP001",
  "dimension": "credit_assessment",
  "overrides": {"credit_score": 50, "guarantee_chain_depth": 5},
  "dry_run": true
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "entity_id": "COMP001",
    "simulation_type": "what_if",
    "steps": [
      {"step": 1, "rule_id": "R001", "rule_name": "信用分准入", "condition_result": false, "explanation": "信用分 50 < 60，未达到准入阈值"}
    ],
    "final_outputs": {"eligible": false, "rejection_reason": "基础准入未通过"},
    "comparison": {
      "baseline": {"eligible": true, "credit_limit": {"value": 7500000, "currency": "CNY"}, "interest_rate": 0.072},
      "simulated": {"eligible": false, "credit_limit": null, "interest_rate": null},
      "diffs": [
        {"field": "eligible", "baseline_value": true, "simulated_value": false, "impact": "资格降级"},
        {"field": "credit_limit", "baseline_value": 7500000, "simulated_value": null, "impact": "额度归零"}
      ]
    }
  }
}
```

### 验证点

- [ ] 模拟后 `eligible == false`
- [ ] 触发条件失败：`credit_score = 50 < 60`
- [ ] `credit_limit` 从 7500000 降至 null
- [ ] 对比结果展示变更影响路径

---

## Step 6: Agent 调用

### 6.1 知识检索

**MCP 工具**: `oe_query`

```json
{
  "query": "资本充足的大型制造业供应商",
  "match_mode": "hybrid",
  "top_k": 5,
  "filters": {"concept_types": ["Company"], "attributes": {"industry": "C"}}
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "entity_id": "COMP001",
        "concept_type": "Company",
        "relevance_score": 0.92,
        "match_details": {"semantic_score": 0.85, "graph_score": 0.99, "matched_path": ["Company → (industry=C)"]},
        "attributes": {"name": "北京智造科技有限公司", "registered_capital": {"value": 5000000, "currency": "CNY"}, "status": "ACTIVE"}
      }
    ]
  }
}
```

### 6.2 执行规则并解释

**MCP 工具**: `oe_execute_rule`

```json
{
  "entity_id": "COMP001",
  "rule_group": "credit_assessment",
  "explain_level": "full"
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "execution": {
      "entity_id": "COMP001",
      "rule_group": "credit_assessment",
      "executed_at": "2026-04-13T10:15:00Z",
      "duration_ms": 45
    },
    "final_output": {
      "eligible": true,
      "credit_limit": {"value": 7500000, "currency": "CNY"},
      "interest_rate": 0.072
    },
    "explain": {
      "rules_executed": [
        {
          "rule_id": "R001", "name": "信用分准入",
          "condition_evaluated": "credit_score >= 60 AND guarantee_exposure < registered_capital.value * 2",
          "condition_result": true,
          "computation_detail": {"formula": "credit_score >= 60", "inputs": {"credit_score": 78}, "calculation": "78 >= 60 = true", "result": true}
        },
        {
          "rule_id": "R004", "name": "授信额度计算",
          "condition_evaluated": "eligible == true",
          "condition_result": true,
          "computation_detail": {"formula": "min(registered_capital * 0.6, 15000000)", "inputs": {"registered_capital": 5000000}, "calculation": "min(5000000 * 0.6, 15000000) = 3000000", "result": 3000000}
        },
        {
          "rule_id": "R005", "name": "差异化利率定价",
          "computation_detail": {"formula": "baseline + total_points", "inputs": {"credit_score": 78, "baseline": 0.045}, "calculation": "0.045 + 0.010 + 0.005 = 0.072", "result": 0.072}
        }
      ],
      "data_sources": [
        {"field": "credit_score", "layer": "L3_metric", "value": 78},
        {"field": "guarantee_exposure", "layer": "L3_graph_metric", "value": 3000000},
        {"field": "registered_capital", "layer": "L1_fact", "value": 5000000}
      ]
    }
  }
}
```

### 6.3 规则追溯

**MCP 工具**: `oe_trace_rule`

```json
{
  "entity_id": "COMP001",
  "trace_mode": "full"
}
```

### 响应

```json
{
  "success": true,
  "data": {
    "trace": {
      "entity": {
        "id": "COMP001",
        "concept_type": "Company",
        "key_attributes": {"name": "北京智造科技有限公司", "uscc": "91110000123456789X", "status": "ACTIVE"}
      },
      "categorization": {"industry": "C", "company_scale": "MEDIUM", "risk_level": "LOW"},
      "rule_groups": [
        {"name": "global_eligibility_check", "matched": true, "reason": "企业状态正常，成立超过1年"},
        {"name": "credit_assessment", "matched": true, "reason": "制造业，中等规模，低风险"}
      ],
      "computation_tree": {
        "nodes": [
          {"rule_id": "R001", "name": "信用分准入", "type": "precondition", "inputs": [], "output": {"eligible": true}},
          {"rule_id": "R002", "name": "担保网络风险评估", "type": "compute", "inputs": [{"name": "guarantee_exposure", "source": "fact", "value": 3000000}], "output": {"network_risk_level": "LOW"}},
          {"rule_id": "R004", "name": "授信额度计算", "type": "decision", "inputs": [{"name": "registered_capital", "source": "fact", "value": 5000000}], "output": {"credit_limit": 7500000}},
          {"rule_id": "R005", "name": "差异化利率定价", "type": "decision", "inputs": [{"name": "credit_score", "source": "metric", "value": 78}], "output": {"interest_rate": 0.072}}
        ],
        "edges": [
          {"from": "R001", "to": "R002", "label": "depends_on"},
          {"from": "R002", "to": "R004", "label": "depends_on"},
          {"from": "R004", "to": "R005", "label": "depends_on"}
        ]
      },
      "atomic_metrics": [
        {"id": "credit_score", "name": "综合信用评分", "value": 78, "source": "L3_composite"},
        {"id": "guarantee_exposure", "name": "担保敞口", "value": 3000000, "source": "L3_graph"},
        {"id": "asset_liability_ratio", "name": "资产负债率", "value": 0.4, "source": "L3_derived"}
      ]
    }
  }
}
```

### 验证点

- [ ] `oe_query` 返回相关实体，相关度分数 > 0.8
- [ ] `oe_execute_rule` 返回完整执行解释
- [ ] `oe_trace_rule` 返回完整计算树
- [ ] 追溯结果与执行结果一致

---

## 端到端验证清单

| 验证项 | 预期结果 | 状态 |
|--------|----------|------|
| Space 创建成功 | `space_id` 非空 | [ ] |
| Schema 上传成功 | L1-L4 完整加载 | [ ] |
| 数据集注册成功 | `dataset_id` 非空 | [ ] |
| 数据同步成功 | 实体数 = 1, 关系数 = 1 | [ ] |
| 规则执行通过 | `eligible == true` | [ ] |
| 授信额度正确 | `credit_limit.value == 7500000` | [ ] |
| 利率正确 | `interest_rate == 0.072` | [ ] |
| Schema 图可获取 | nodes >= 5 | [ ] |
| 规则链 DAG 可获取 | 包含 R001, R004, R005 | [ ] |
| What-if 模拟生效 | eligible 降级至 false | [ ] |
| Agent 检索正常 | 返回 COMP001 | [ ] |
| Agent 追溯正常 | 完整计算树 | [ ] |

---

## 示例数据清单

| 数据项 | 文件位置 | 说明 |
|--------|----------|------|
| Schema | `examples/supply_chain_finance/schema.yaml` | 供应链金融完整 Schema v2 定义 |
| 实例数据 | `examples/supply_chain_finance/instances.yaml` | 实体 COMP001, COMP002 及 Guarantee 关系 |
| 测试用例 | `examples/supply_chain_finance/testcases.yaml` | 端到端验证测试用例 |
| 设计文档 | `examples/supply_chain_finance/SCHEMA_DESIGN.md` | Schema 设计背景与详细说明 |
| 入口文档 | `examples/supply_chain_finance/README.md` | 示例目录说明与快速开始 |
| 演示脚本 | `examples/supply_chain_finance/demo.py` | 基础演示脚本 |
| 空间验证 | `examples/supply_chain_finance/demo_verify_space.py` | 空间创建与验证脚本 |
| 空间快照 | `examples/supply_chain_finance/demo_space.json` | 空间数据快照 |

---

## 相关文档

- **MCP 工具定义**: [`07-agent-interface.md`](../07-agent-interface.md)
- **API 架构设计**: [`10-api-architecture.md`](../10-api-architecture.md)
- **可视化系统设计**: [`08-visualization-system.md`](../08-visualization-system.md)
- **Schema v2 完整示例**: [`05-schema-v2/05-complete-example.md`](../05-schema-v2/05-complete-example.md)
