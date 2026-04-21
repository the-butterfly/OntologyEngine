# Case 3 用户旅程 — 亚太区总部税务架构优化

## 旅程概览

本案例通过7个步骤展示如何使用 What-If Simulation 功能对比三个税务架构方案。

**预计执行时间**: 15-20分钟
**所需工具**: MCP工具 或 CLI命令 或 API调用

---

## Step 1: 创建税务分析语义空间

### 操作

```bash
# CLI方式
ontology-cli space create --name tax_analysis_apac \
    --description "2026年亚太区总部税务架构分析"

# 或 MCP方式
mcp__ontology__create_space({
    "name": "tax_analysis_apac",
    "description": "2026年亚太区总部税务架构分析"
})
```

### 期望输出

```json
{
    "space_id": "space.tax_apac_2026",
    "name": "tax_analysis_apac",
    "status": "CREATED",
    "created_at": "2026-04-21T10:00:00Z"
}
```

### 验证点

- [ ] Space ID 格式正确: `space.tax_apac_2026`
- [ ] 状态为 CREATED

---

## Step 2: 加载转让定价Schema

### 操作

```bash
# CLI方式
ontology-cli schema load \
    --space space.tax_apac_2026 \
    --file schema.yaml

# 或 MCP方式
mcp__ontology__load_schema({
    "space_id": "space.tax_apac_2026",
    "schema_file": "schema.yaml"
})
```

### 期望输出

```json
{
    "schema_id": "schema.tax_apac.2026",
    "space_id": "space.tax_apac_2026",
    "fact_objects": [
        "Subsidiary", "IntercompanyTransaction", "TransferPricingRecord",
        "TaxTreaty", "TaxAuthority", "PermanentEstablishment"
    ],
    "metrics": 8,
    "rules": 12,
    "status": "LOADED"
}
```

### 验证点

- [ ] 6个实体类型已加载
- [ ] 8个指标已定义
- [ ] 12条规则已就绪

---

## Step 3: 导入子公司及交易数据

### 操作

```bash
# CLI方式
ontology-cli entities batch-import \
    --space space.tax_apac_2026 \
    --file instances.yaml

# 或 MCP方式
mcp__ontology__import_entities({
    "space_id": "space.tax_apac_2026",
    "instances_file": "instances.yaml"
})
```

### 期望输出

```json
{
    "space_id": "space.tax_apac_2026",
    "entities_imported": {
        "Subsidiary": 3,
        "IntercompanyTransaction": 8,
        "TransferPricingRecord": 15,
        "TaxTreaty": 3
    },
    "total_entities": 29,
    "relations_created": 42,
    "validation_passed": true
}
```

### 验证点

- [ ] 3个子公司实体已导入 (SUB_HK, SUB_SG, SUB_CN)
- [ ] 15条转让定价记录已录入
- [ ] 3个税收协定已关联

---

## Step 4: 定义三个What-If场景

### 操作

```bash
# CLI方式 - 定义场景A
ontology-cli simulation define-scenario \
    --space space.tax_apac_2026 \
    --scenario-id scenario_A \
    --scenario-name "香港总部模式" \
    --parameters @scenarios/scenario_a_params.yaml

# 重复定义场景B和场景C...

# 或 MCP方式
mcp__ontology__define_scenario({
    "space_id": "space.tax_apac_2026",
    "scenario_id": "scenario_A",
    "scenario_name": "香港总部模式",
    "parameters": {
        "hq_location": "香港",
        "ip_location": "香港",
        "operation_location": "中国",
        "royalty_rate": 0.05,
        "dividend_wht": 0.05,
        "qdmt": "香港"
    }
})
```

### 场景参数对照表

| 参数 | 场景A (香港) | 场景B (新加坡) | 场景C (混合) |
|------|-------------|---------------|-------------|
| 总部所在地 | 香港 | 新加坡 | 香港+新加坡 |
| IP授权地 | 香港 | 新加坡 | 香港 |
| 运营地 | 中国 | 中国/新加坡 | 新加坡 |
| 特许权费率 | 5% | 7% | 5% |
| 股息预提税 | 5% | 5% | 5%+5% |
| QDMTT | 香港 2025 | 新加坡 2025 | 两地 |

### 期望输出

```json
{
    "space_id": "space.tax_apac_2026",
    "scenarios_defined": [
        {"scenario_id": "scenario_A", "name": "香港总部模式", "status": "CONFIGURED"},
        {"scenario_id": "scenario_B", "name": "新加坡总部模式", "status": "CONFIGURED"},
        {"scenario_id": "scenario_C", "name": "混合架构模式", "status": "CONFIGURED"}
    ],
    "total_scenarios": 3,
    "validation_passed": true
}
```

---

## Step 5: 执行干运行模拟

### 操作

```bash
# CLI方式
ontology-cli simulation run \
    --space space.tax_apac_2026 \
    --mode dry_run \
    --scenarios scenario_A,scenario_B,scenario_C

# 或 MCP方式
mcp__ontology__run_simulation({
    "space_id": "space.tax_apac_2026",
    "mode": "dry_run",
    "scenarios": ["scenario_A", "scenario_B", "scenario_C"],
    "persist_results": false
})
```

### 期望输出

```json
{
    "simulation_id": "sim_20260421_001",
    "space_id": "space.tax_apac_2026",
    "mode": "dry_run",
    "execution_mode": "in_memory_only",
    "results": [
        {
            "scenario_id": "scenario_A",
            "scenario_name": "香港总部模式",
            "effective_tax_rate": 0.132,
            "annual_tax_cost_cny": 45000000,
            "beps_risk_level": "LOW",
            "pillar2_exposure": false,
            "execution_time_ms": 234
        },
        {
            "scenario_id": "scenario_B",
            "scenario_name": "新加坡总部模式",
            "effective_tax_rate": 0.141,
            "annual_tax_cost_cny": 52000000,
            "beps_risk_level": "LOW",
            "pillar2_exposure": false,
            "execution_time_ms": 198
        },
        {
            "scenario_id": "scenario_C",
            "scenario_name": "混合架构模式",
            "effective_tax_rate": 0.128,
            "annual_tax_cost_cny": 48000000,
            "beps_risk_level": "MEDIUM",
            "pillar2_exposure": true,
            "execution_time_ms": 312
        }
    ],
    "total_execution_time_ms": 744,
    "persistence": false
}
```

### 验证点

- [ ] 所有场景均完成干运行
- [ ] 无数据持久化 (persistence: false)
- [ ] 各场景ETR计算完成
- [ ] BEPS风险等级已评估

---

## Step 6: 对比分析结果

### 操作

```bash
# CLI方式
ontology-cli simulation compare \
    --space space.tax_apac_2026 \
    --simulation-id sim_20260421_001 \
    --output-format table

# 或 MCP方式
mcp__ontology__compare_scenarios({
    "space_id": "space.tax_apac_2026",
    "simulation_id": "sim_20260421_001",
    "metrics": ["effective_tax_rate", "annual_tax_cost", "beps_risk_level", "pillar2_exposure"]
})
```

### 期望输出

```json
{
    "simulation_id": "sim_20260421_001",
    "comparison_matrix": {
        "headers": ["指标", "场景A (香港)", "场景B (新加坡)", "场景C (混合)", "最优"],
        "rows": [
            ["有效税率 (ETR)", "13.2%", "14.1%", "12.8%", "场景C"],
            ["年税务成本 (CNY)", "4,500万", "5,200万", "4,800万", "场景A"],
            ["BEPS风险等级", "低", "低", "中", "A/B"],
            ["支柱二补税", "无", "无", "潜在", "A/B"],
            ["合规复杂度", "低", "中", "高", "场景A"],
            ["综合得分", "82", "78", "75", "场景A"]
        ]
    },
    "recommendation": {
        "preferred_scenario": "scenario_A",
        "reason": "税务效率与合规风险最佳平衡",
        "caveats": [
            "场景C ETR最低但BEPS风险较高",
            "建议进一步评估支柱二长期影响"
        ]
    }
}
```

### 验证点

- [ ] 对比矩阵格式正确
- [ ] 各指标可对比
- [ ] 有推荐结论

---

## Step 7: 生成决策报告

### 操作

```bash
# CLI方式
ontology-cli report generate \
    --space space.tax_apac_2026 \
    --simulation-id sim_20260421_001 \
    --type tax_decision \
    --format pdf \
    --output report_tax_decision_2026Q2.pdf

# 或 MCP方式
mcp__ontology__generate_report({
    "space_id": "space.tax_apac_2026",
    "simulation_id": "sim_20260421_001",
    "report_type": "tax_decision",
    "format": "pdf",
    "include_sections": ["executive_summary", "scenario_comparison", "risk_analysis", "recommendations"]
})
```

### 期望输出

```json
{
    "report_id": "report_20260421_001",
    "report_type": "tax_decision",
    "format": "pdf",
    "file_path": "expected_outputs/tax_decision_report.pdf",
    "sections": [
        "executive_summary",
        "scenario_comparison_matrix",
        "effective_tax_rate_analysis",
        "beps_risk_assessment",
        "pillar2_impact_analysis",
        "recommendations",
        "appendix_transfer_pricing"
    ],
    "pages": 12,
    "generated_at": "2026-04-21T10:15:00Z"
}
```

### 验证点

- [ ] 报告生成成功
- [ ] 包含所有必要章节
- [ ] CFO级别人物可直接使用

---

## 可视化输出

### 场景对比图

```
effective_tax_rate (%)
├── scenario_A: ████████████ 13.2%
├── scenario_B: █████████████ 14.1%
└── scenario_C: ██████████ 12.8%

annual_tax_cost (M CNY)
├── scenario_A: ████████████████ 45M ★ LOWEST
├── scenario_B: ████████████████████ 52M
└── scenario_C: ██████████████████ 48M

beps_risk_level
├── scenario_A: ● LOW
├── scenario_B: ● LOW
└── scenario_C: ●● MEDIUM
```

### 风险雷达图

```
           LOW
            ↑
            │
   LOW     │     LOW
  ←─────────┼─────────→
            │
            │
         MEDIUM↓
```

---

## 快速执行脚本

```bash
#!/bin/bash
# case3_tax_simulation/quick_run.sh

# Step 1: Create space
ontology-cli space create --name tax_analysis_apac

# Step 2: Load schema
ontology-cli schema load --space space.tax_apac_2026 --file schema.yaml

# Step 3: Import data
ontology-cli entities batch-import --space space.tax_apac_2026 --file instances.yaml

# Step 4: Define scenarios
for scenario in A B C; do
    ontology-cli simulation define-scenario \
        --space space.tax_apac_2026 \
        --scenario-id scenario_$scenario \
        --parameters scenarios/scenario_${scenario}_params.yaml
done

# Step 5: Run simulation
ontology-cli simulation run \
    --space space.tax_apac_2026 \
    --mode dry_run \
    --scenarios scenario_A,scenario_B,scenario_C

# Step 6: Compare results
ontology-cli simulation compare \
    --space space.tax_apac_2026 \
    --simulation-id sim_latest \
    --output-format table

# Step 7: Generate report
ontology-cli report generate \
    --space space.tax_apac_2026 \
    --simulation-id sim_latest \
    --type tax_decision \
    --format pdf
```

---

## 遗留问题

1. **LLM Judge Stub**: 转让定价合理性判断暂用规则替代
2. **Bundle Search未实现**: 多维度场景筛选暂用规则引擎
3. **MCP工具列表待确认**: 需验证实际MCP工具名称
