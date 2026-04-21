# Case 1 用户旅程 — 供应链金融合规检查

## 旅程概览

本案例通过6个步骤展示如何使用 Rule Hot-Update 功能在48小时内完成央行23号文合规改造。

**预计执行时间**: 10-15分钟
**所需工具**: MCP工具 或 CLI命令 或 API调用

---

## Step 1: 加载扩展Schema

### 操作

```bash
# CLI方式
ontology-cli schema load \
    --space space.supply_chain_finance \
    --file schema.yaml

# 或 MCP方式
mcp__ontology__load_schema({
    "space_id": "space.supply_chain_finance",
    "schema_file": "schema.yaml"
})
```

### 期望输出

```json
{
    "schema_id": "schema.circ23.2026",
    "space_id": "space.supply_chain_finance",
    "fact_objects": [
        "Supplier", "CoreEnterprise", "Invoice",
        "Contract", "GuaranteeRelation",
        "ComplianceRecord"
    ],
    "metrics": 12,
    "rules": 8,
    "new_rules_added": 4,
    "status": "LOADED"
}
```

---

## Step 2: 导入供应商数据

### 操作

```bash
ontology-cli entities batch-import \
    --space space.supply_chain_finance \
    --file instances.yaml
```

### 期望输出

```json
{
    "space_id": "space.supply_chain_finance",
    "entities_imported": {
        "Supplier": 5,
        "CoreEnterprise": 3,
        "Invoice": 23,
        "Contract": 10,
        "GuaranteeRelation": 4
    },
    "total_entities": 45,
    "relations_created": 67,
    "validation_passed": true
}
```

---

## Step 3: 热点更新合规规则（核心演示）

### 操作

```bash
# CLI方式 - 规则热更新
ontology-cli rules hot-update \
    --space space.supply_chain_finance \
    --file rules/RD_circular23_compliance.yaml

# 或 MCP方式
mcp__ontology__load_rules({
    "space_id": "space.supply_chain_finance",
    "rules_file": "rules/RD_circular23_compliance.yaml"
})
```

### 期望输出

```json
{
    "rules_loaded": [
        {"rule_id": "RD_C23_001", "name": "核心企业白名单检查", "status": "ACTIVE"},
        {"rule_id": "RD_C23_002", "name": "发票真实性核验", "status": "ACTIVE"},
        {"rule_id": "RD_C23_003", "name": "担保金额上限检查", "status": "ACTIVE"},
        {"rule_id": "RD_C23_004", "name": "风险集中度检查", "status": "ACTIVE"},
        {"rule_id": "RD_C23_005", "name": "综合合规评估", "status": "ACTIVE"}
    ],
    "activation_time_ms": 847,
    "effective_immediately": true,
    "regulatory_reference": "银发〔2025〕77号"
}
```

### 验证点

- [ ] 规则在 < 1秒 内激活
- [ ] 无需重启服务
- [ ] 立即生效

---

## Step 4: 执行合规分析

### 操作

```bash
ontology-cli analyze \
    --space space.supply_chain_finance \
    --entity-type Supplier \
    --category compliance_assessment \
    --dimension circular23_compliance
```

### 期望输出

```json
{
    "analysis_id": "analysis_20260421_001",
    "space_id": "space.supply_chain_finance",
    "entities_analyzed": 5,
    "results": [
        {
            "entity_id": "SUP_C1",
            "company_name": "深圳恒通科技有限公司",
            "compliance_status": "PASSED",
            "rules_checked": ["RD_C23_001", "RD_C23_002", "RD_C23_003", "RD_C23_004", "RD_C23_005"],
            "score": 95
        },
        {
            "entity_id": "SUP_C2",
            "company_name": "上海贸易有限公司",
            "compliance_status": "FAILED",
            "rules_checked": ["RD_C23_001", "RD_C23_002", "RD_C23_003", "RD_C23_004", "RD_C23_005"],
            "failed_rules": ["RD_C23_001"],
            "failure_reasons": ["核心企业'XX集团'不在白名单内"],
            "score": 45
        },
        {
            "entity_id": "SUP_C3",
            "company_name": "广州制造有限公司",
            "compliance_status": "FAILED",
            "failed_rules": ["RD_C23_002"],
            "failure_reasons": ["发票真实性核验通过率60%，低于95%阈值"],
            "score": 50
        },
        {
            "entity_id": "SUP_C4",
            "company_name": "北京担保有限公司",
            "compliance_status": "FAILED",
            "failed_rules": ["RD_C23_003"],
            "failure_reasons": ["担保金额1,500万超过注册资本10%上限"],
            "score": 40
        },
        {
            "entity_id": "SUP_C5",
            "company_name": "成都供应链有限公司",
            "compliance_status": "FAILED",
            "failed_rules": ["RD_C23_004"],
            "failure_reasons": ["风险集中度65%超过50%阈值"],
            "score": 35
        }
    ],
    "summary": {
        "total": 5,
        "passed": 1,
        "failed": 4,
        "pass_rate": "20%"
    }
}
```

---

## Step 5: 查询决策溯源

### 操作

```bash
ontology-cli query trace \
    --space space.supply_chain_finance \
    --entity-id SUP_C4 \
    --include-evidence true
```

### 期望输出

```json
{
    "entity_id": "SUP_C4",
    "company_name": "北京担保有限公司",
    "trace_id": "trace_20260421_001",
    "decision": {
        "outcome": "FAILED",
        "reason": "担保金额超过上限"
    },
    "rule_execution_path": [
        {
            "rule_id": "RD_C23_003",
            "rule_name": "担保金额上限检查",
            "step_id": "step_1",
            "status": "FAILED",
            "input": {
                "guarantee_amount": 15000000,
                "registered_capital": 100000000,
                "ratio": 0.15
            },
            "condition": "guarantee_amount <= registered_capital * 0.1",
            "condition_result": "false",
            "output": {
                "passed": false,
                "message": "担保金额1,500万超过注册资本1亿的10%上限(1,000万)"
            },
            "evidence_chain": [
                {
                    "evidence_type": "guarantee_relation",
                    "source": "GuaranteeRelation:GR_001",
                    "field": "guarantee_amount",
                    "value": 15000000,
                    "confidence": 1.0
                },
                {
                    "evidence_type": "fact_object",
                    "source": "Supplier:SUP_C4",
                    "field": "registered_capital",
                    "value": 100000000,
                    "confidence": 1.0
                }
            ]
        }
    ],
    "mutual_index_links": [
        {
            "from": "EntityInstance:SUP_C4",
            "to": "KnowledgeFragment:frag_guarantee_contract_2026",
            "relation": "extracted_from",
            "confidence": 1.0
        },
        {
            "from": "ExecutionStepSnapshot:RD_C23_003_step_1",
            "to": "KnowledgeFragment:frag_circular23_article_15",
            "relation": "trace_to",
            "confidence": 1.0
        }
    ],
    "regulatory_reference": "银发〔2025〕77号 第十五条"
}
```

---

## Step 6: 生成合规审计报告

### 操作

```bash
ontology-cli report generate \
    --space space.supply_chain_finance \
    --analysis-id analysis_20260421_001 \
    --type compliance_audit \
    --period Q1-2026 \
    --format pdf
```

### 期望输出

```json
{
    "report_id": "report_c23_2026Q1",
    "report_type": "compliance_audit",
    "period": "Q1-2026",
    "format": "pdf",
    "sections": [
        "executive_summary",
        "regulation_overview",
        "entities_analyzed",
        "compliance_results",
        "failed_entities_detail",
        "evidence_chains",
        "recommendations",
        "appendix"
    ],
    "generated_at": "2026-04-21T14:30:00Z",
    "retention_years": 7
}
```

---

## API端点速查

| 操作 | API端点 | CLI命令 | MCP工具 |
|------|---------|---------|---------|
| 加载Schema | `POST /v1/schema/load` | `ontology-cli schema load` | `mcp__ontology__load_schema` |
| 导入实体 | `POST /v1/entities/batch` | `ontology-cli entities batch-import` | `mcp__ontology__import_entities` |
| 热更新规则 | `POST /v1/rules/import` | `ontology-cli rules hot-update` | `mcp__ontology__load_rules` |
| 执行分析 | `POST /v1/analysis/execute` | `ontology-cli analyze` | `mcp__ontology__analyze` |
| 查询溯源 | `GET /v1/query/trace/{id}` | `ontology-cli query trace` | `mcp__ontology__query_trace` |
| 生成报告 | `POST /v1/reports/generate` | `ontology-cli report generate` | `mcp__ontology__generate_report` |

---

## 快速执行脚本

```bash
#!/bin/bash
# case1_regulatory_compliance/quick_run.sh

# Step 1: 加载扩展Schema
ontology-cli schema load \
    --space space.supply_chain_finance \
    --file schema.yaml

# Step 2: 导入供应商数据
ontology-cli entities batch-import \
    --space space.supply_chain_finance \
    --file instances.yaml

# Step 3: 热点更新合规规则
ontology-cli rules hot-update \
    --space space.supply_chain_finance \
    --file rules/RD_circular23_compliance.yaml

# Step 4: 执行合规分析
ontology-cli analyze \
    --space space.supply_chain_finance \
    --entity-type Supplier \
    --category compliance_assessment

# Step 5: 查询溯源(示例: SUP_C4)
ontology-cli query trace \
    --space space.supply_chain_finance \
    --entity-id SUP_C4 \
    --include-evidence true

# Step 6: 生成审计报告
ontology-cli report generate \
    --space space.supply_chain_finance \
    --analysis-id analysis_latest \
    --type compliance_audit \
    --period Q1-2026
```

---

## 遗留问题

1. **Bundle Search未实现**: 多维度证据筛选暂用规则替代
2. **LLM Judge Stub**: 合理论证暂用规则引擎
3. **MCP工具列表**: 需验证实际MCP工具名称
