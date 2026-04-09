# 设计讨论：评审意见 + Agent 接口需求

**Date**: 2026-04-09
**来源**: review/ + 用户新需求

---

## 一、评审报告关键问题 (P0)

### 问题 1: L3/L4 边界模糊

**评审意见**: L3 指标的计算公式应该在哪里？

**当前设计**:
```yaml
# L3: 仅声明指标存在
metrics:
  - name: asset_liability_ratio
    type: derived
    dependencies: [total_assets, total_liabilities]
    # ❓ formula 在哪里？

# L4: 规则中定义
rules:
  - action:
      type: compute
      output: asset_liability_ratio
      formula: "total_liabilities / total_assets"
```

**评审建议**: L3 包含 `default_formula`，L4 可覆盖

**我的分析**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| A: L3 无 formula | L4 完全控制，灵活 | 同一指标可能重复定义 |
| B: L3 有 default_formula | L3 自包含，减少重复 | 覆盖场景复杂 |
| C: L3 + L4 分离定义 | 指标定义与业务计算分离 | 增加概念复杂度 |

**决策点**: 选择哪个方案？

---

### 问题 2: Formula 多行支持

**评审意见**: 单行限制与 simpleeval 矛盾，复杂逻辑被迫用算子

**我的分析**:

| 阶段 | 方案 | 工具 | 复杂度 |
|------|------|------|--------|
| MVP | 单行表达式 | simpleeval | ⭐ |
| Phase 1 | 多行安全脚本 | asteval (AST白名单) | ⭐⭐ |
| Phase 2 | 自定义 DSL | Lark + 安全执行器 | ⭐⭐⭐ |

**评审建议**: Phase 1 改用 asteval

**决策点**: MVP 阶段是否直接用 asteval？

---

## 二、Agent 接口设计 (新需求)

### 2.1 接口形态

**需求**: 给 Agent 提供知识资产构建接口

**选项**:

| 接口 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **CLI** | 简单，脚本友好 | 无状态，复杂场景受限 | 快速原型 |
| **MCP** | Claude 原生支持，工具调用 | 协议限制，灵活性低 | Claude Agent 集成 |
| **REST API** | 通用，灵活性高 | 无原生 Agent 支持 | 通用平台 |
| **混合** | 最佳灵活性 | 实现复杂度高 | 完整产品 |

**我的倾向**: **MCP + CLI 混合
- MCP: Claude Agent 调用（Schema 加载、实体操作、规则执行）
- CLI: 本地开发、批量操作、脚本化

---

### 2.2 Agent 知识检索服务

**需求 a: Query 匹配 (向量 + 图语义)**

```yaml
# Schema 语义匹配
POST /agent/query/pattern-match

{
  "query": "查找提供芯片的供应商",
  "match_mode": "hybrid",    # semantic | graph | hybrid
  "top_k": 10,
  "filters": {
    "concept_type": "Supplier",
    "status": "ACTIVE"
  },
  "semantic_weight": 0.6,    # 向量权重
  "graph_weight": 0.4        # 图语义权重
}
```

**match_mode 选项**:
- `semantic`: 纯向量相似度
- `graph`: 图模式匹配（Schema 关系）
- `hybrid`: 加权融合
- `path`: 路径查询（起点 → 关系 → 终点）

**决策点**: hybrid 模式下的权重分配策略？

---

**需求 b: 实例 → 规则追溯**

```yaml
# 从对象实例追溯应用规则
POST /agent/query/rule-trace

{
  "entity_id": "COMP001",
  "trace_mode": "full",      # categorization | rule | dependency | full
  "include_intermediate": true
}
```

**trace_mode 说明**:

| 模式 | 返回 |
|------|------|
| `categorization` | 实例 → 分类标签 (L2) |
| `rule` | 实例 → 适用规则组 (L4) |
| `dependency` | 规则 → 依赖的计算树 |
| `full` | 完整链路：实例 → 分类 → 规则 → 依赖 → 原子指标 |

**返回示例** (full 模式):
```json
{
  "entity_id": "COMP001",
  "trace": {
    "categorization": {
      "industry": "制造业",
      "company_scale": "MEDIUM",
      "risk_level": "LOW"
    },
    "rule_groups": ["credit_assessment", "collateral_assessment"],
    "computation_tree": {
      "credit_assessment": {
        "R001_eligibility": {
          "inputs": ["credit_score >= 60", "guarantee_exposure < ...*2"],
          "output": "eligible"
        },
        "R002_credit_limit": {
          "inputs": {
            "credit_score": {"source": "L3_metric", "metric_id": "..."},
            "registered_capital": {"source": "L1_fact", "attribute": "..."}
          },
          "formula": "min(registered_capital * 0.5, ...) * factor",
          "output": "credit_limit"
        }
      }
    },
    "atomic_metrics": [
      {"id": "credit_score", "value": 78},
      {"id": "registered_capital", "value": 5000000}
    ]
  }
}
```

---

**需求 c: 规则执行 + 可解释性**

```yaml
# 执行规则并返回可解释结果
POST /agent/execute/with-explain

{
  "entity_id": "COMP001",
  "rule_group": "credit_assessment",
  "explain_level": "full",    # minimal | intermediate | full
  "include_trace": true
}
```

**explain_level**:

| 级别 | 返回 |
|------|------|
| `minimal` | 最终输出 |
| `intermediate` | 最终输出 + 中间规则结果 |
| `full` | 最终输出 + 中间结果 + 计算树 + 数据来源 |

**返回示例** (full):
```json
{
  "entity_id": "COMP001",
  "rule_group": "credit_assessment",
  "final_output": {
    "eligible": true,
    "credit_limit": {"value": 7500000, "currency": "CNY"},
    "interest_rate": 0.072
  },
  "explain": {
    "R001": {
      "name": "基础准入",
      "condition": "credit_score >= 60 AND guarantee_exposure < registered_capital * 2",
      "evaluated": "78 >= 60 AND 3000000 < 10000000 = TRUE",
      "result": {"eligible": true}
    },
    "R002": {
      "name": "额度计算",
      "formula": "min(registered_capital * 0.5, 10000000) * credit_score / 100",
      "inputs": {
        "registered_capital": 5000000,
        "credit_score": 78
      },
      "calculation": "min(2500000, 10000000) * 0.78 = 1950000",
      "result": {"credit_limit": 1950000}
    }
  },
  "data_sources": {
    "credit_score": {"layer": "L3", "computed": true, "timestamp": "..."},
    "registered_capital": {"layer": "L1", "instance": "COMP001"}
  }
}
```

---

### 2.3 反馈闭环

**需求 d: 操作反馈 + 历史管理**

```yaml
# Agent 反馈接口
POST /agent/feedback

{
  "operation_id": "op_20260409_001",
  "feedback_type": "correction",    # correction | rejection | suggestion
  "target": {
    "type": "rule_result",
    "entity_id": "COMP001",
    "rule_id": "R002",
    "field": "credit_limit",
    "actual_value": 7500000,
    "expected_value": 8000000
  },
  "reason": "忽略了担保物的价值",
  "suggested_change": {
    "type": "override",
    "rule_id": "R002",
    "input_adjustments": {
      "credit_score": 82  # 建议调整输入指标
    }
  }
}
```

**反馈类型**:

| 类型 | 说明 | 后续动作 |
|------|------|----------|
| `correction` | 修正结果 | 记录，触发 review |
| `rejection` | 拒绝结果 | 记录，标记为问题 |
| `suggestion` | 改进建议 | 记录，供人工 review |

**操作历史记录**:

```yaml
# 历史查询
GET /agent/history/operations

{
  "filters": {
    "entity_id": "COMP001",
    "time_range": {"start": "2026-04-01", "end": "2026-04-09"},
    "feedback_type": "correction"
  },
  "limit": 50
}
```

**回退机制**:

```yaml
# 回退到历史状态
POST /agent/rollback

{
  "target": {
    "type": "rule_result",
    "entity_id": "COMP001",
    "rule_group": "credit_assessment"
  },
  "rollback_to": {
    "type": "operation_id",
    "operation_id": "op_20260408_015"  # 回退到此操作之前
  },
  "reason": "规则逻辑错误，需重新评估"
}
```

**回退影响分析**:

```json
{
  "rollback_id": "rb_001",
  "will_affect": {
    "dependent_rules": ["R003", "R004"],
    "derived_metrics": ["final_credit_limit"],
    "dependent_entities": ["COMP002", "COMP003"]  # COMP001 为担保方
  },
  "requires_confirmation": true
}
```

---

## 三、平台化扩展 (新需求)

### 3.1 中间件集成

**需求**: 支持外部数据库作为扩展，进行 Schema 历史审计

```yaml
# 配置扩展
config:
  extensions:
    audit:
      enabled: true
      backend: postgresql    # local | postgresql | mysql
      dsn: "postgresql://user:pass@host:5432/ontology_audit"
      tables:
        schema_history: "schema_versions"
        operation_log: "operations"
        audit_log: "audit_events"

    cache:
      backend: redis
      dsn: "redis://host:6379/0"
      ttl:
        metric: 3600
        rule_result: 86400
```

**Schema 版本审计**:

```sql
-- schema_history 表
CREATE TABLE schema_versions (
    id SERIAL PRIMARY KEY,
    schema_id VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    changes JSONB NOT NULL,
    diff_from_previous JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR,  -- 操作者 (Agent/User)
    reason TEXT
);

-- operation_log 表
CREATE TABLE operations (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR UNIQUE NOT NULL,
    operation_type VARCHAR NOT NULL,  -- create_entity, execute_rule, etc.
    entity_id VARCHAR,
    rule_id VARCHAR,
    inputs JSONB,
    outputs JSONB,
    status VARCHAR,  -- success, failed, rolled_back
    error_message TEXT,
    executed_by VARCHAR,
    executed_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Schema 热更新与回滚

```yaml
# Schema 版本管理
POST /v1/schema/version

{
  "action": "update",
  "target_version": "v2.1.0",
  "changes": {
    "added_metrics": ["new_metric"],
    "modified_rules": ["R003"],
    "deleted": []
  },
  "rollback_version": "v2.0.0",
  "reason": "优化额度计算逻辑",
  "dry_run": true  # 先预览
}
```

**热更新流程**:

```
Schema v2.0.0 ──▶ Diff 分析 ──▶ 兼容性检查 ──▶ 增量更新
                     │                │
                     ▼                ▼
              影响范围分析        失败回滚

Schema v2.1.0 ──▶ 规则重执行 ──▶ 结果更新
                     │
                     ▼
              影响分析 ──▶ Agent 通知
```

---

## 四、已确认设计决策

| # | 决策点 | 确认方案 |
|---|--------|----------|
| 1 | L3/L4 边界 | **L3 包含 optional `default_formula`**，相当于直接生成通用规则 |
| 2 | Formula 执行器 | **asteval + 预制表达式/函数** |
| 3 | Agent 接口形态 | **MCP + CLI + 云端/本地混合部署** |

### 云端/本地混合架构

```
云端 (Organization)
├── 共享 Schema 库
├── 权威规则库
├── 模型仓库
└── 知识图谱

本地 (Local Instance)
├── Schema 实例化
├── 实体数据
├── 本地缓存
└── 个人配置

同步机制:
├── pull: 云端 → 本地
├── push: 本地 → 云端 (需权限)
└── merge: 智能合并 (冲突提示)
```

---

## 五、设计文档更新

| 文档 | 状态 |
|------|------|
| `docs/07-agent-interface.md` | ✅ 已创建 |
| `docs/08-knowledge-retrieval.md` | ✅ 已创建 |
| `docs/09-feedback-loop.md` | ✅ 已合并到 08 |
| `docs/10-platform-extensions.md` | ✅ 已合并到 07 |

---

请确认以上设计是否符合预期方向。
