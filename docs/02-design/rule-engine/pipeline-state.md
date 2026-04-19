# 管道状态持久化

> **status**: draft | **phase**: rewrite | **source_of_truth**: 本文档（管道状态模型） | **last_verified**: 2026-04-19

---

## 目的

定义规则引擎执行过程的持久化模型，支持断点续跑、审计追踪和执行历史回溯，对齐 Cognee PipelineRun 状态管理模式。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **执行结果仅内存** | `AnalysisResult` 和 `RuleResult` 仅在内存中，进程崩溃即丢失 | `PipelineRun` + `ExecutionStepSnapshot` 持久化到 SQLite |
| 2 | **无断点续跑** | 执行中断后必须从头开始 | 记录每个步骤的完成状态，中断后从最后完成步骤继续 |
| 3 | **无审计追踪** | 无法追溯"谁在什么时候执行了什么规则，产出什么结果" | `PipelineRun` 记录完整执行上下文和溯源信息 |
| 4 | **无执行历史** | 无法对比同一规则在不同时间的执行结果差异 | `PipelineRun` 版本链 + `supersedes` 关系 |

---

## PipelineRun 模型

### 对齐 Cognee PipelineRun

| Cognee 字段 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| `id` (UUID) | `id` (UUID) | 管道运行唯一标识 |
| `pipeline_name` | `rule_logic_name` | 关联的规则逻辑名称 |
| `pipeline_id` | `rule_definition_name` | 关联的规则定义名称 |
| `dataset_id` | `entity_id` | 执行目标实体 |
| `status` (Enum) | `status` (Enum) | 运行状态 |
| `created_at` | `created_at` | 创建时间 |
| `run_info` (JSON) | `run_config` (JSON) | 运行配置 |

### 模型定义

```yaml
PipelineRun:
  id: UUID
  rule_logic_name: string
  rule_definition_name: string
  entity_id: string
  dimension: string

  status: enum
  created_at: datetime
  started_at: datetime | None
  completed_at: datetime | None

  run_config: JSON
  error_message: string | None

  source_pipeline: string
  source_user: string | None
  source_content_hash: string | None

  supersedes: UUID | None
```

### 状态枚举

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `PENDING` | 等待执行 | PipelineRun 创建时 |
| `RUNNING` | 执行中 | DAGExecutor 开始执行时 |
| `COMPLETED` | 执行完成 | 所有步骤成功完成 |
| `FAILED` | 执行失败 | 任一步骤失败且 ErrorStrategy 为 STOP/ABORT |
| `PARTIALLY_COMPLETED` | 部分完成 | 部分步骤失败但 ErrorStrategy 为 CONTINUE |

### 状态机

```
PENDING ──▶ RUNNING ──▶ COMPLETED
  │             │
  │             ├────────▶ FAILED
  │             │
  │             └────────▶ PARTIALLY_COMPLETED
  │
  └──▶ FAILED (前置条件检查失败)
```

状态转换规则：

| 当前状态 | 目标状态 | 触发条件 |
|---------|---------|---------|
| `PENDING` | `RUNNING` | `DAGExecutor.execute()` 开始 |
| `RUNNING` | `COMPLETED` | 所有层执行成功 |
| `RUNNING` | `FAILED` | 层执行失败 + `STOP_LAYER` / `ABORT_ALL` |
| `RUNNING` | `PARTIALLY_COMPLETED` | 部分步骤失败 + `CONTINUE` |
| `PENDING` | `FAILED` | 前置条件检查失败 |

---

## ExecutionStepSnapshot 模型

### 目的

记录每个步骤的执行状态和产出，支持断点续跑和审计追踪。

### 模型定义

```yaml
ExecutionStepSnapshot:
  id: UUID
  pipeline_run_id: UUID
  step_id: string
  step_name: string

  status: enum
  started_at: datetime | None
  completed_at: datetime | None

  condition_met: boolean | None
  action_type: string | None
  operator_name: string | None

  input_snapshot: JSON
  output_snapshot: JSON

  error_message: string | None
  skip_reason: string | None

  dag_layer: integer
  depends_on: list[string]

  trace_to: list[string] | None
```

### 步骤状态枚举

| 状态 | 含义 |
|------|------|
| `PENDING` | 等待执行 |
| `RUNNING` | 执行中 |
| `COMPLETED` | 执行成功 |
| `SKIPPED` | 条件不满足，跳过 |
| `FAILED` | 执行失败 |
| `ROLLED_BACK` | 因同层其他步骤失败而回滚 |

### 对齐 Cognee TaskRun

| Cognee TaskRun 字段 | OntologyEngine 对应 | 说明 |
|---------------------|-------------------|------|
| `task_id` | `step_id` | 步骤标识 |
| `status` | `status` | 执行状态 |
| `input_data` | `input_snapshot` | 输入快照 |
| `output_data` | `output_snapshot` | 输出快照 |
| `error` | `error_message` | 错误信息 |

---

## PipelineStateManager

### 职责

管理 PipelineRun 和 ExecutionStepSnapshot 的生命周期，提供断点续跑和审计查询接口。

### 接口

```python
class PipelineStateManager:
    def __init__(self, storage: Storage):
        self.storage = storage

    async def create_run(
        self,
        rule_logic_name: str,
        rule_definition_name: str,
        entity_id: str,
        dimension: str,
        run_config: dict,
    ) -> PipelineRun:
        ...

    async def start_run(self, run_id: UUID) -> None:
        ...

    async def complete_run(self, run_id: UUID) -> None:
        ...

    async def fail_run(self, run_id: UUID, error: str) -> None:
        ...

    async def partial_complete_run(self, run_id: UUID) -> None:
        ...

    async def create_step_snapshot(
        self,
        run_id: UUID,
        step: Step,
        dag_layer: int,
    ) -> ExecutionStepSnapshot:
        ...

    async def start_step(self, snapshot_id: UUID, input_snapshot: dict) -> None:
        ...

    async def complete_step(
        self,
        snapshot_id: UUID,
        output_snapshot: dict,
        condition_met: bool,
        action_type: str,
        operator_name: str | None,
    ) -> None:
        ...

    async def fail_step(self, snapshot_id: UUID, error: str) -> None:
        ...

    async def skip_step(self, snapshot_id: UUID, reason: str) -> None:
        ...

    async def rollback_step(self, snapshot_id: UUID) -> None:
        ...

    async def get_run(self, run_id: UUID) -> PipelineRun | None:
        ...

    async def get_latest_run(
        self,
        rule_logic_name: str,
        entity_id: str,
    ) -> PipelineRun | None:
        ...

    async def get_step_snapshots(self, run_id: UUID) -> list[ExecutionStepSnapshot]:
        ...

    async def get_completed_step_ids(self, run_id: UUID) -> list[str]:
        ...
```

---

## 断点续跑

### 恢复流程

```
DAGExecutor.execute() 调用
  ↓
检查是否有未完成的 PipelineRun:
  ├─ 无 → 创建新 PipelineRun → 从头执行
  └─ 有 (status=FAILED 或 RUNNING)
      ↓
      查询已完成的 step_ids
      ↓
      从 ExecutionDAG 中移除已完成步骤
      ↓
      重新计算剩余步骤的拓扑分层
      ↓
      从断点继续执行
```

### 恢复条件

| 条件 | 说明 |
|------|------|
| 同一 `rule_logic_name` + `entity_id` | 必须匹配 |
| 上次运行状态为 `FAILED` 或 `PARTIALLY_COMPLETED` | `COMPLETED` 不需要续跑 |
| 已完成步骤的 `output_snapshot` 完整 | 缺失输出的步骤需要重算 |
| DAG 结构未变更 | `rule_logic` 版本与上次一致 |

### 版本不一致处理

```
检查 rule_logic 的 source_content_hash
  ↓
与上次 PipelineRun 的 run_config.hash 对比
  ├─ 一致 → 可以续跑
  └─ 不一致 → 创建新 PipelineRun，从头执行
      ↓
      旧 PipelineRun 标记为 superseded
```

---

## 审计追踪

### 审计查询接口

```python
class AuditQuery:
    async def get_execution_history(
        self,
        entity_id: str,
        rule_logic_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[PipelineRun]:
        ...

    async def get_step_trace(
        self,
        run_id: UUID,
        step_id: str,
    ) -> StepTrace:
        ...

    async def get_decision_explanation(
        self,
        entity_id: str,
        dimension: str,
    ) -> DecisionExplanation:
        ...
```

### StepTrace 模型

```yaml
StepTrace:
  step_id: string
  step_name: string
  action_type: string
  operator_name: string | None

  condition_expression: string | None
  condition_result: boolean | None

  input_values: dict
  output_values: dict

  started_at: datetime
  completed_at: datetime
  duration_ms: integer

  trace_to_fragments: list[FragmentRef]
```

### DecisionExplanation 模型

```yaml
DecisionExplanation:
  entity_id: string
  dimension: string
  decision: string
  reasoning: string

  rule_chain: list[StepTrace]
  evidence_chain: list[FragmentRef]

  pipeline_run_id: UUID
  computed_at: datetime
```

### 与互索引协同

```
ExecutionStepSnapshot.trace_to
  ↓
KnowledgeFragment (Layer-R)
  ↓
提供决策的证据链:
  "授信额度 500 万"
    ← 步骤: calc_credit_limit
    ← 规则: credit_limit_override
    ← 证据: 企业财报 (fragment_003) + 评分卡文档 (fragment_007)
```

---

## 存储设计

### SQLite 表结构

```sql
CREATE TABLE pipeline_runs (
    id TEXT PRIMARY KEY,
    rule_logic_name TEXT NOT NULL,
    rule_definition_name TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    run_config TEXT NOT NULL,
    error_message TEXT,
    source_pipeline TEXT NOT NULL DEFAULT 'rule_engine',
    source_user TEXT,
    source_content_hash TEXT,
    supersedes TEXT,
    FOREIGN KEY (supersedes) REFERENCES pipeline_runs(id)
);

CREATE INDEX idx_pipeline_runs_logic_entity
    ON pipeline_runs(rule_logic_name, entity_id);

CREATE INDEX idx_pipeline_runs_status
    ON pipeline_runs(status);

CREATE TABLE execution_step_snapshots (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    condition_met INTEGER,
    action_type TEXT,
    operator_name TEXT,
    input_snapshot TEXT NOT NULL,
    output_snapshot TEXT,
    error_message TEXT,
    skip_reason TEXT,
    dag_layer INTEGER NOT NULL,
    depends_on TEXT NOT NULL,
    trace_to TEXT,
    FOREIGN KEY (pipeline_run_id) REFERENCES pipeline_runs(id)
);

CREATE INDEX idx_step_snapshots_run
    ON execution_step_snapshots(pipeline_run_id);

CREATE INDEX idx_step_snapshots_run_status
    ON execution_step_snapshots(pipeline_run_id, status);
```

---

## 与 DAGExecutor 集成

### 执行流程集成

```
DAGExecutor.execute()
  ↓
PipelineStateManager.create_run()
  ↓
PipelineStateManager.start_run()
  ↓
for layer in dag.layers:
  ↓
  for node in layer.nodes:
    PipelineStateManager.create_step_snapshot()
    PipelineStateManager.start_step(input_snapshot=context.snapshot())
    ↓
    执行步骤
    ↓
    成功: PipelineStateManager.complete_step(output_snapshot=result)
    失败: PipelineStateManager.fail_step(error=message)
    跳过: PipelineStateManager.skip_step(reason=reason)
    回滚: PipelineStateManager.rollback_step()
  ↓
  层执行结果汇总
  ↓
全部完成: PipelineStateManager.complete_run()
部分失败: PipelineStateManager.partial_complete_run()
层失败: PipelineStateManager.fail_run(error=message)
```

### 与 PipelineRunInfo 对齐

Cognee 的 `PipelineRunInfo` 使用事件模式通知管道状态变更。OntologyEngine 采用类似模式：

| Cognee 事件 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| `PipelineRunStarted` | `PipelineRun.status = RUNNING` | 管道开始 |
| `PipelineRunYield` | `ExecutionStepSnapshot.status = COMPLETED` | 步骤产出 |
| `PipelineRunCompleted` | `PipelineRun.status = COMPLETED` | 管道完成 |
| `PipelineRunAlreadyCompleted` | 查询到已有 COMPLETED 运行 | 跳过重复执行 |
| `PipelineRunErrored` | `PipelineRun.status = FAILED` | 管道失败 |

---

## 参考文档

| 主题 | 文档 |
|------|------|
| 规则引擎设计概览 | [README.md](./README.md) |
| DAG 执行设计 | [dag-execution.md](./dag-execution.md) |
| 逻辑边按需计算 | [logical-edges.md](./logical-edges.md) |
| Cognee PipelineRun | [PipelineRun.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/cognee/cognee/modules/pipelines/models/PipelineRun.py) |
| Cognee PipelineRunInfo | [PipelineRunInfo.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/cognee/cognee/modules/pipelines/models/PipelineRunInfo.py) |
| m_flow Procedure 版本管理 | [Procedure.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/m_flow/m_flow/core/domain/models/Procedure.py) |
| 互索引概念 | [05-concepts.md](../../01-overview/05-concepts.md) |
