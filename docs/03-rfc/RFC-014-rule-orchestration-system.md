# RFC-014: 规则逻辑编排系统

> **状态**: draft
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **创建日期**: 2026-04-15
> **作者**: the-butterfly
> **评审截止**: 待定
> **关联文档**: [RFC-011](./RFC-011-rule-executor-dag.md) · [RFC-012](./RFC-012-kuzu-storage.md)

---

## 摘要

本 RFC 定义 OntologyEngine 规则编排系统的完整设计方案，涵盖：规则四元素标准化模型、规则组/规则实例两级分层、5+5 算子体系、DAG 可视化、以及配套的 CRUD API 和 YAML 导入导出。

**核心目标**：让业务分析师/规则工程师能够通过画布可视化创建、编辑、验证业务规则，并快速理解要素间的计算依赖关系。

---

## 一、现状与痛点

### 1.1 当前问题

| 问题 | 表现 | 影响 |
|------|------|------|
| 规则只能写 YAML，无可视化入口 | 业务人员无法参与规则创建 | 规则管理门槛高 |
| 规则实例与规则框架混合 | 修改一个规则需要理解整个 YAML 结构 | 维护困难 |
| 要素间计算关系不透明 | 不知道一个指标依赖哪些输入 | 调试困难 |
| 规则执行无法单独模拟 | 要调试一条规则需要运行全量推理 | 验证低效 |
| DAG 仅在执行时构建，无可视化 | 无法预先检查规则依赖问题 | 潜在循环依赖 |

### 1.2 与 RFC-011 的关系

- **RFC-011**: 关注 RuleExecutor DAG 执行引擎（`depends_on` 拓扑排序）
- **本 RFC**: 关注规则编排 UI/存储/API 层（规则组 CRUD、算子配置、DAG 可视化）
- **两者互补**: RFC-011 定义执行模型，本 RFC 定义上层建筑

---

## 二、核心概念

### 2.1 规则四元素模型

每一条具体规则必须包含以下四个要素：

```
┌─────────────────────────────────────────────────────┐
│                    规则四元素                         │
│                                                     │
│  ① 作用对象 (Target)                                 │
│     └─ 规则作用于哪种实体类型（Supplier/Invoice/...） │
│                                                     │
│  ② 适用场景 (Applicability)                          │
│     └─ 何时触发该规则（维度/分类/前置条件）            │
│                                                     │
│  ③ 输入输出要素 (I/O Elements)                       │
│     └─ 需要哪些指标作为输入，产出哪些指标              │
│                                                     │
│  ④ 分析逻辑 (Logic Expression)                       │
│     └─ 具体的计算/判断逻辑（算子 + 表达式）            │
└─────────────────────────────────────────────────────┘
```

### 2.2 规则体系两级分层

```
规则组 (RuleGroup / rule_definition)
  ├─ 定义规则的框架结构（四元素的 ① ② ③）
  ├─ 声明适用对象、适用场景、I/O 要素约束
  └─ 包含一组有序的规则实例

    规则实例 (RuleInstance / rule_logic.step)
      ├─ 具体的逻辑表达式（四元素的 ④）
      ├─ 一个 when → then/else 结构
      └─ 使用算子执行计算
```

### 2.3 算子分类（五大类型 + 五类辅助）

| 算子类型 | 代码名 | 场景 | 特点 |
|---------|--------|------|------|
| 分箱 | `BINNING` | 连续值离散化（年龄段/信用分段） | 区间定义 + 标签映射 |
| 评分卡 | `SCORECARD` | 多变量积分式评估 | baseline + 变量得分表 |
| 加权计算 | `WEIGHTED_SUM` | 复合指标聚合 | 权重配置 + 归一化 |
| 决策树 | `DECISION_TABLE` | 多条件矩阵决策 | 条件组合 → 结果映射 |
| LLM定性分析 | `LLM_JUDGE` | 非结构化/主观评估 | Prompt模板 + 置信度 |

辅助算子：`SWITCH` / `COMPUTE` / `GRAPH` / `SET_FLAG` / `TRIGGER_ALERT`

---

## 三、数据模型

### 3.1 Python 模型定义

```python
# ontology_engine/engine/rule/models.py 扩展

@dataclass
class RuleGroupDefinition:
    """规则组（框架）- 对应四元素的 ① ② ③

    Attributes:
        id: UUID primary key, used by frontend and as URL parameter
        name: Business identifier, unique within a semantic space (schema_id)
        schema_id: Semantic space identifier - enforces name uniqueness isolation
    """
    id: str = ""          # UUID primary key for frontend/URL use
    name: str = ""        # Business name, unique within (name, schema_id)
    description: str = ""
    type: Literal["constraint", "inference", "alert", "decision"] = "decision"
    priority: int = 100
    applies_to: AppliesToConfig = field(default_factory=AppliesToConfig)
    preconditions: list[Precondition] = field(default_factory=list)
    inputs: list[IOElement] = field(default_factory=list)
    outputs: list[IOElement] = field(default_factory=list)
    enabled: bool = True
    schema_id: str = ""   # Semantic space ID (required for isolation)
    created_at: str = ""
    updated_at: str = ""

@dataclass
class RuleStep:
    """规则实例（具体逻辑）- 对应四元素的 ④"""
    id: str
    name: str
    rule_group: str                       # 所属规则组 name (not UUID)
    order: int                            # 执行顺序（支持拖拽调整）
    when: ConditionClause
    then: ActionClause
    else_: ActionClause | None = None
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)

@dataclass
class ActionClause:
    """动作子句：算子配置"""
    operator: str                         # 算子名称
    params: dict                          # 算子参数（JSON Schema 约束）
    output_mapping: dict[str, str] = field(default_factory=dict)

@dataclass
class ConditionClause:
    """条件子句：支持单一/AND/OR"""
    type: Literal["expression", "all_of", "any_of"]
    expression: str | None = None
    sub_conditions: list[str] = field(default_factory=list)

@dataclass
class OperatorSchema:
    """算子注册信息"""
    name: str
    display_name: str
    description: str
    category: Literal["binning", "scorecard", "weighted_sum", "decision_table",
                       "llm_judge", "flag", "alert", "compute", "switch", "graph"]
    param_schema: dict
    input_types: list[str]
    output_types: list[str]
```

### 3.2 DuckDB 存储表

```sql
-- 规则组表（框架层）
-- id: UUID primary key for frontend/URL use
-- name: Business identifier, unique within a semantic space (schema_id)
-- schema_id: Semantic space identifier for name isolation
-- Unique constraint is on (name, schema_id) for semantic space isolation
CREATE TABLE rule_groups (
    id          VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    description TEXT,
    type        VARCHAR NOT NULL,
    priority    INTEGER DEFAULT 100,
    applies_to  JSON,
    preconditions JSON,
    inputs      JSON,
    outputs     JSON,
    enabled     BOOLEAN DEFAULT TRUE,
    schema_id   VARCHAR NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, schema_id)
);

-- 规则实例表（逻辑层）
-- References rule_groups via rule_group name (not UUID)
CREATE TABLE rule_steps (
    id           VARCHAR NOT NULL,
    rule_group   VARCHAR NOT NULL REFERENCES rule_groups(name),
    step_order   INTEGER NOT NULL,
    name         VARCHAR,
    when_clause  JSON,
    then_clause  JSON,
    else_clause  JSON,
    enabled      BOOLEAN DEFAULT TRUE,
    description  TEXT,
    tags         JSON,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_group, id)
);

-- 指标扩展表（补充值域/阈值/颜色）
CREATE TABLE metric_extensions (
    metric_name  VARCHAR PRIMARY KEY,
    value_domain JSON,
    thresholds   JSON,
    color        VARCHAR,
    unit         VARCHAR,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 算子注册表
CREATE TABLE operator_registry (
    name         VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    description  TEXT,
    category     VARCHAR,
    param_schema JSON,
    input_types  JSON,
    output_types JSON,
    enabled      BOOLEAN DEFAULT TRUE
);
```

---

## 四、API 设计

### 4.1 规则组 CRUD

> **注意**:
> - 主资源路由使用 `{id}` (UUID)，嵌套路由保留 `{name}` (业务标识)
> - 所有操作都需要 `schema_id` 参数用于语义空间隔离
> - `schema_id` 在创建时为必填，查询/更新/删除时用于区分同名规则组

```
POST   /api/v1/rule-groups                     # 创建规则组 (body: {name, schema_id, ...})
GET    /api/v1/rule-groups?schema_id=xxx      # 列表（按语义空间过滤）
GET    /api/v1/rule-groups/{id}?schema_id=xxx # 获取规则组详情 (by UUID, schema_id for name lookup)
PUT    /api/v1/rule-groups/{id}?schema_id=xxx # 更新规则组 (by UUID, schema_id for name lookup)
DELETE /api/v1/rule-groups/{id}?schema_id=xxx # 删除规则组 (by UUID, schema_id for name lookup)
GET    /api/v1/rule-groups/{name}/steps?schema_id=xxx      # 获取规则实例列表 (by name)
POST   /api/v1/rule-groups/{name}/steps?schema_id=xxx      # 添加规则实例 (by name)
PUT    /api/v1/rule-groups/{name}/steps/{step_id}?schema_id=xxx  # 更新规则实例
DELETE /api/v1/rule-groups/{name}/steps/{step_id}?schema_id=xxx  # 删除规则实例
POST   /api/v1/rule-groups/{name}/reorder?schema_id=xxx    # 调整规则实例顺序 (by name)
```

### 4.2 规则模拟执行

```
POST   /api/v1/rule-groups/{name}/simulate
```

Request Body:
```json
{
  "entity_data": {
    "status": "ACTIVE",
    "registered_capital": {"value": 5000000, "currency": "CNY"}
  },
  "pre_computed": {
    "credit_score": 87.5,
    "overdue_invoice_ratio": 0.03
  },
  "step_filter": ["R001", "R002"]
}
```

Response:
```json
{
  "steps": [
    {
      "step_id": "R001",
      "step_name": "基本资质检查",
      "condition_result": true,
      "condition_detail": {
        "type": "ALL_OF",
        "sub_conditions": [
          {"expr": "status == 'ACTIVE'", "result": true, "explain": "状态为激活"},
          {"expr": "registered_capital.value >= 1000000", "result": true, "explain": "注册资本500万 >= 100万"}
        ]
      },
      "action_taken": "SET_FLAG",
      "output": {"eligible": true},
      "duration_ms": 2
    }
  ],
  "final_output": {"eligible": true, "credit_score_adjusted": 92.0},
  "alerts": []
}
```

### 4.3 要素计算图

```
GET  /api/v1/metrics                          # 指标列表
GET  /api/v1/metrics/{name}                   # 指标详情
GET  /api/v1/metrics/{name}/dag               # 该指标的 DAG（上下游）
GET  /api/v1/dag/full                          # 完整 Schema DAG
     ?target=credit_score                     # 可选：聚焦目标节点
     ?depth=5                                 # 可选：展开深度
GET  /api/v1/dag/path                          # 从 source 到 target 的路径
     ?from=registered_capital&to=credit_score
```

### 4.4 YAML 导入导出

```
GET  /api/v1/rule-groups/{name}/export?schema_id=xxx  # 导出为 YAML（Schema v2 canonical）
POST /api/v1/rule-groups/import               # 从 YAML 导入 (body: {yaml_content, schema_id})
POST /api/v1/rule-groups/validate-yaml        # 验证 YAML 合法性
```

### 4.5 算子查询

```
GET  /api/v1/operators                        # 算子列表（含参数 schema）
GET  /api/v1/operators/{name}/schema          # 算子参数 JSON Schema
POST /api/v1/operators/{name}/validate        # 验证算子参数
```

---

## 五、模块拆解

### 5.1 后端模块调整（增量变更）

```
ontology_engine/
├── engine/
│   ├── rule/
│   │   ├── engine.py             # 现有 RuleEngine（DAG 模块升级）
│   │   ├── executor.py           # 现有 RuleExecutor
│   │   ├── dag.py                # ✨ 新增: RuleDAG 构建 + to_graph_data()
│   │   ├── models.py             # 扩展: RuleGroupDefinition + RuleStep
│   │   ├── evaluator.py          # 现有条件评估
│   │   └── operators/
│   │       ├── binning.py        # 升级: 支持 UI 友好格式
│   │       ├── scorecard.py      # 升级: 得分表 UI 友好格式
│   │       ├── weighted_sum.py   # ✨ 新增: WEIGHTED_SUM 算子
│   │       ├── decision_table.py # 升级: 矩阵配置 UI 友好格式
│   │       ├── llm_judge.py      # 升级: Prompt 模板 + 降级策略
│   │       └── registry.py       # ✨ 新增: 算子注册中心 + JSON Schema
│   │
│   └── metric/
│       ├── engine.py             # 现有 MetricEngine
│       └── dag.py                # 扩展: to_graph_data() 输出可视化 JSON
│
├── services/
│   ├── rule_service.py           # ✨ 新增: 规则组/实例 CRUD + YAML 导出
│   ├── dag_service.py            # ✨ 新增: 全量 DAG 构建 + 路径查询
│   └── simulation_service.py     # 升级: 支持单步/局部 DAG + 条件拆解详情
│
├── api/routes/
│   ├── rules.py                  # ✨ 新增: 规则 CRUD + 模拟 + YAML
│   ├── metrics.py                # ✨ 新增: 指标 CRUD + DAG 子图
│   ├── dag.py                    # ✨ 新增: 全局 DAG + 路径查询
│   └── operators.py              # ✨ 新增: 算子列表 + 参数 Schema
│
└── storage/duckdb/
    └── store.py                  # 扩展: rule_groups / rule_steps / metric_extensions
```

### 5.2 前端模块拆解

```
ontology-engine-ui/src/
├── pages/
│   ├── rules/
│   │   ├── RuleGroupListPage.tsx        # 规则组列表
│   │   ├── RuleGroupDetailPage.tsx      # 规则组详情
│   │   ├── RuleGroupEditorPage.tsx      # 规则组框架编辑
│   │   └── RuleStepEditorPage.tsx       # 规则实例编辑
│   │
│   ├── metrics/
│   │   ├── MetricListPage.tsx           # 指标列表
│   │   ├── MetricDetailPage.tsx          # 指标详情
│   │   └── MetricEditorPage.tsx          # 指标编辑
│   │
│   └── dag/
│       └── FullDAGPage.tsx              # 全局计算 DAG
│
├── components/
│   ├── rule-editor/
│   │   ├── RuleGroupForm.tsx            # 四元素框架表单
│   │   ├── AppliesToSelector.tsx        # 作用对象选择器
│   │   ├── ApplicabilityConfig.tsx      # 适用场景配置
│   │   ├── IOElementsEditor.tsx         # I/O 要素编辑器
│   │   ├── RuleStepList.tsx            # 规则实例列表
│   │   ├── ConditionEditor.tsx         # 条件编辑器
│   │   ├── ActionEditor.tsx             # 动作编辑器
│   │   └── SimulationPanel.tsx         # 模拟执行面板
│   │
│   ├── operator-params/
│   │   ├── DynamicParamForm.tsx         # 通用参数表单
│   │   ├── BinningParamEditor.tsx      # 分箱编辑器
│   │   ├── ScorecardParamEditor.tsx    # 评分卡编辑器
│   │   ├── WeightedSumParamEditor.tsx  # 加权编辑器
│   │   ├── DecisionTableEditor.tsx     # 决策表编辑器
│   │   └── LLMJudgeParamEditor.tsx     # LLM 分析编辑器
│   │
│   └── dag-view/
│       ├── ElementDAGGraph.tsx          # 要素 DAG
│       ├── RuleFlowGraph.tsx            # 规则流转图
│       ├── DAGNodeDetail.tsx            # 节点详情
│       └── DAGToolbar.tsx               # DAG 工具栏
│
├── hooks/
│   ├── useRuleGroups.ts
│   ├── useRuleSteps.ts
│   ├── useOperators.ts
│   ├── useMetrics.ts
│   ├── useDAG.ts
│   └── useSimulation.ts
│
└── stores/
    ├── ruleStore.ts
    └── dagStore.ts
```

---

## 六、关键设计决策

### D1：规则组与规则实例存储分离

**决策**: `rule_groups` 存框架（四元素 ①②③），`rule_steps` 存实例（④），通过 `rule_group` 字段关联。

**理由**: 框架变更不频繁（作用对象/适用场景/IO 声明稳定），实例变更频繁（逻辑表达式随业务调整）。分离存储支持独立 diff 和版本管理，也与 Schema v2 `rule_definitions` + `rule_logics` 的双层结构对齐。

### D2：算子参数统一用 JSON Schema 描述

**决策**: 每个算子注册时提供 `param_schema`（JSON Schema），前端动态渲染基础参数表单，复杂算子可提供专用编辑器覆盖基础渲染。

**理由**: 算子可扩展，前端不应与算子强耦合。新增算子只需后端注册，前端自动适配，专用编辑器按需补充。

### D3：DAG 可视化与执行 DAG 共用数据结构

**决策**: `MetricDAG.to_graph_data()` 和 `RuleDAG.to_graph_data()` 均输出 `{nodes: [...], edges: [...]}` 格式（兼容 G6 5.x / X6 2.x），前端无需了解后端 NetworkX 内部结构。

**理由**: 与现有 `visualization/builders.py` 设计保持一致，复用前端图渲染基础设施。

### D4：规则实例模拟不写存储

**决策**: 模拟执行（`/simulate`）使用 `dry_run=True`，仅内存执行，不写入持久化存储，不触发预警推送。

**理由**: 与可视化模块 `RuleChainSimulator.dry_run` 决策一致，保证模拟的无副作用性。

### D5：LLM_JUDGE 三级降级策略

**决策**: ① LLM 超时/报错 → 使用配置的 `fallback_value`；② 置信度低于阈值 → 返回值+置信度标记（不阻断）；③ 完全不可用 → 跳过该步骤，打 `SKIPPED` 标记。降级值必须由规则设计者显式配置。

**理由**: LLM 调用不稳定，不能因 LLM 失败中断整个规则链。降级策略透明可配置，可审计。

### D6：WEIGHTED_SUM 为新算子，与 composite 指标的关系

**决策**: L3 `composite` 指标的权重聚合（`components`）在 MetricEngine 内计算；L4 规则中的 `WEIGHTED_SUM` 算子用于**基于规则动态调整权重**的场景（如根据企业等级使用不同权重乘数）。两者不互相替代。

**理由**: L3 composite 是静态权重配置（Schema 定义），L4 WEIGHTED_SUM 是动态规则逻辑，语义不同。

---

## 七、实施路线

### Phase 2-A：规则编排核心（第 1-4 周）

| 周次 | 后端任务 | 前端任务 |
|------|---------|---------|
| W1 | `rule_groups`/`rule_steps` 数据模型 + DuckDB 表 + 基础 CRUD API | 规则组列表页 + 框架编辑器（四元素表单） |
| W2 | 算子注册中心 + JSON Schema + WEIGHTED_SUM 算子新增 + 现有算子升级 | 规则实例编辑器（条件编辑器 + 动作编辑器） |
| W3 | 单规则模拟 API（支持条件拆解详情） | 5 种算子参数配置器 + 模拟执行面板 |
| W4 | YAML 导入/导出 + Schema v2 合规验证 | 规则组详情页（实例列表 + YAML 预览）|

### Phase 2-B：要素 DAG 可视化（第 5-7 周）

| 周次 | 后端任务 | 前端任务 |
|------|---------|---------|
| W5 | `dag_service.py`：要素 DAG 构建 + `to_graph_data()` + 指标 DAG API | `ElementDAGGraph` 组件（G6 节点着色 + 层级布局） |
| W6 | 全局 DAG API + 路径查询 API | `FullDAGPage`（全量计算图 + 路径高亮 + 过滤）|
| W7 | 规则 DAG：`RuleDAG.to_graph_data()` + 规则流转图 API | `RuleFlowGraph` 组件（X6 步骤节点 + 条件/动作卡）|

### Phase 2-C：集成与深化（第 8-9 周）

| 周次 | 任务 |
|------|------|
| W8 | DAG 与规则编辑联动（点击节点→规则编辑页） + 影响分析集成 |
| W9 | LLM_JUDGE 完整实现 + 端到端测试覆盖 + 文档更新 |

---

## 八、验收标准

### Phase 2-A MVP 验收

- [ ] 用户可通过页面完整创建一个规则组（含四元素：作用对象 + 适用场景 + I/O要素 + 至少1条规则实例）
- [ ] 5 种算子（BINNING/SCORECARD/WEIGHTED_SUM/DECISION_TABLE/LLM_JUDGE）均可通过 UI 配置参数
- [ ] 用户可通过模拟面板输入测试数据，查看单条规则实例的执行结果（含条件拆解详情）
- [ ] 可将规则组导出为符合 Schema v2 canonical spec 的 YAML 文件
- [ ] 可从 YAML 文件导入规则组（合规验证通过后写入存储）

### Phase 2-B DAG 验收

- [ ] 全量 DAG 视图展示从 L1 原子属性 → L3 指标 → L4 规则 → 最终决策的完整链路
- [ ] 节点按类型分层着色（L1/atomic/derived/composite/graph/rule_group/rule_step/decision）
- [ ] 点击任意节点可查看该节点的详情
- [ ] 支持按目标结果反向过滤：选定 `credit_score`，只展示其上游 DAG

### Phase 2-C 完整验收

- [ ] 规则编辑后，影响链分析自动提示受影响的下游规则和指标
- [ ] LLM_JUDGE 降级策略完整：超时降级 / 低置信度标记 / 完全不可用跳过
- [ ] 所有规则管理 API 端点有完整测试覆盖（单元测试覆盖率 ≥ 80%）
- [ ] 端到端场景：供应链金融授信完整规则链可在 UI 上创建、模拟、导出 YAML

---

## 九、文档关联

| 文档 | 关系 |
|------|------|
| [RFC-010](./RFC-010-phase2-roadmap.md) | Phase 2 整体路线 |
| [RFC-011](./RFC-011-rule-executor-dag.md) | RuleExecutor DAG 执行引擎 |
| [RFC-012](./RFC-012-kuzu-storage.md) | kuzu 图存储升级 |
| `docs/06-module-detailed-design/06-rule-engine.md` | 现有规则引擎设计（本计划扩展基础） |
| `docs/06-module-detailed-design/04-metric-engine.md` | 指标引擎（DAG 模块扩展依据） |
| `docs/05-schema-v2/09-canonical-schema-spec.md` | YAML 规范（导入/导出合规基准） |

---

## 十、任务清单

| 任务 | 模块 | 状态 | 完成日期 |
|------|------|------|----------|
| T1: 数据模型扩展 (models.py) | engine/rule | ✅ done | 2026-04-15 |
| T2: DuckDB 表创建 | storage/duckdb | ✅ done | 2026-04-15 |
| T3: 算子注册中心 (registry.py) | engine/rule/operators | ✅ done | 2026-04-15 |
| T4: WEIGHTED_SUM 算子 | engine/rule/operators | ✅ done | 2026-04-15 |
| T5: 规则 Service | services | ✅ done | 2026-04-15 |
| T6: DAG Service | services | ✅ done | 2026-04-15 |
| T7: Simulation Service | services | ✅ done | 2026-04-15 |
| T8: API 端点 | api/routes | ✅ done | 2026-04-15 |
| T9: DAG Builder 扩展 | visualization | ✅ done | 2026-04-15 |
| T10: 前端组件 | ontology-engine-ui | pending | - |

> **W1-W2 完成内容**: 数据模型 + DuckDB 存储层 + 算子注册中心 + WEIGHTED_SUM 算子 + Rule/DAG/Simulation Service + API 端点 + DAG Builder 扩展
