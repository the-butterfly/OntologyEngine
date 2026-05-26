# ADR-010: RFC 衍生的关键架构决策汇总

| 字段 | 值 |
|------|-----|
| 状态 | accepted |
| 日期 | 2026-05-15 |
| 决策者 | 文档治理审查 |
| 关联 | RFC-010 ~ RFC-019, ADR-008 |

---

## 背景

`docs-dev/03-rfc/` 中包含 20 个 RFC，记录了从 Phase 2 改进路线到 Agent 记忆系统的完整设计历程。本 ADR 从中提取对未来架构有持续约束力的关键决策，作为 ADR-008 (Phase 1-4 审查决策) 的补充。

---

## D10-1: 规则执行模型从 priority 排序升级为 DAG 拓扑执行

**来源**: RFC-010 (Phase 2 路线图), RFC-011 (DAG 引擎)

**决策**:
1. 规则执行模型从 `sorted(rules, key=lambda r: -r.priority)` 升级为 DAGBuilder 拓扑排序
2. `RuleStep` 增加 `depends_on` 字段支持显式依赖声明，格式为 step_id 列表
3. DAG 执行采用同层 `asyncio.gather` 并行，不跨层并行
4. 向后兼容：现有 `when/then_action/else_action` 格式作为 DAG 单节点特殊情况继续有效

**理由**:
- 跨规则依赖场景（Rule B 需要 Rule A 输出）无法用 priority 表达
- 多步 DAG 场景（A→B→C）需要拓扑顺序执行
- 向后兼容确保现有规则无需重写

**影响**:
- `RuleStep.depends_on` 字段成为规则模型的必选语义
- 规则执行引擎新增 DAGBuilder/DAGExecutor 两层
- 执行状态持久化从仅内存 AnalysisResult 升级为 PipelineRun + ExecutionStepSnapshot

---

## D10-2: 存储层三引擎拆分 (KuzuDB + ChromaDB + SQLite)

**来源**: RFC-012 (kuzu 图存储升级), RFC-010

**决策**:
1. 图存储从 NetworkX 内存 + DuckDB 升级为 **KuzuDB** 持久化，支持 100K 节点 + 200K 边
2. 向量检索从 LocalVectorStore 内存实现升级为 **ChromaDB** 持久化
3. 事务元数据独立到 **SQLite WAL** 数据库，与主存储分离
4. 实施采用双写协调 (DualWriteCoordinator) 策略：DuckDB 与 KuzuDB 并行写入，逐步迁移

**理由**:
- NetworkX 无法持久化，100K 节点时内存和性能均不可接受
- LocalVectorStore 重启后向量索引丢失
- 元数据与图数据分离，各引擎独立扩展

**影响**:
- 存储接口从单一 StorageBackend 拆分为 GraphStore + VectorStore + MetaStore
- 新代码应通过新三接口访问，旧 DuckDB 路径保留兼容
- Edge 分区写入策略 (UNWIND+MERGE) 解决 KuzuDB write-write conflict

---

## D10-3: MCP 工具三层依赖注入架构

**来源**: RFC-013 (MCP 工具实现)

**决策**:
1. MCP 工具必须通过 service 层调用，禁止直接依赖 storage / engine / core / api
2. 依赖注入通过 `ontology_engine/mcp/__init__.py` 的 `init_mcp_dependencies()` 实现
3. MCP 工具命名约定：`oe_{verb}_{noun}` (如 `oe_create_space`)
4. 每个工具 description 至少 3 句：用途 + 前置条件 + 返回值概述

**理由**:
- 防止 MCP 层跳过 service 层直接操作存储，破坏模块边界
- 中心化依赖注入便于测试和替换实现

**影响**:
- MCP 工具开发必须遵循 `MCP tools → services → engine/storage` 调用链
- 新增 MCP 工具必须注册依赖到 `init_mcp_dependencies()`

---

## D10-4: 规则模型双分离 + Step.action 结构化

**来源**: RFC-018 (规则模型双分离), RFC-019 (Step.action 结构化), ADR-008 D8/D12

**决策**:
1. 规则模型拆分为 RuleDefinitionDeclaration (规则定义) + RuleLogicDeclaration (规则逻辑)，与 L4 grammar 对齐
2. Step.action 从 `str + dict` 扁平表示升级为结构化 ActionClause 模型 + ActionType 枚举
3. 一个规则定义可关联多个规则逻辑，提升跨场景复用性

**理由**:
- 消除三套并行规则模型 (Schema/Service/Engine 层各一套) 的术语混乱
- 结构化 ActionType 让执行引擎可针对不同动作类型优化处理

**影响**:
- 规则创建流程变为：先创建 RuleDefinitionDeclaration，再关联 RuleLogicDeclaration
- ActionClause + ActionType 枚举成为规则步骤的标准模型
- 旧 YAML 格式 (`when/then/else_`) 需升级为 `steps[]` + `depends_on` 格式

---

## D10-5: 规则编排四元素模型

**来源**: RFC-014 (规则逻辑编排系统), RFC-015 (前端), RFC-016 (Gap 分析), RFC-017 (YAML 格式)

**决策**:
1. 每条具体规则包含四个要素：输入 (inputs) + 条件 (condition) + 计算/动作 (action) + 输出 (outputs)
2. RuleGroup + RuleInstance 两级分层管理
3. 5+5 算子体系：5 个基本算子 (SET_FLAG/COMPUTE/REJECT/EMIT_ALERT/ASSIGN_CATEGORY) + 5 个高级算子 (SWITCH/SCORECARD/DECISION_TABLE/WEIGHTED_SUM/GRAPH)
4. YAML 导入/导出格式与 RuleGroupDefinition + RuleStep 模型对齐

**理由**:
- 四元素模型让规则可视化编排成为可能
- 两级分层解决规则框架与规则实例混合维护的痛点

**影响**:
- 旧规则声明 (RuleDeclaration) 需桥接到新规则组 (RuleGroup)
- YAML 导入导出格式从扁平 `rule_definitions[] + rule_logics[]` 升级为结构化 `rule_group + rule_steps`
- DAG 可视化默认只读，拖拽编辑为 Phase 2-B 规划

---

## 影响范围

| 决策 | 影响模块 | 影响层级 |
|------|----------|----------|
| D10-1: DAG 执行 | engine/rule/ | Engine |
| D10-2: 三引擎存储 | storage/, engine/ | Storage + Engine |
| D10-3: MCP 注入 | mcp/ | MCP |
| D10-4: 规则双分离 | core/schema/, services/ | Core + Service |
| D10-5: 四元素模型 | services/, frontend/ | Service + Frontend |

## 关联 RFC

| RFC | 决策 | ADR 覆盖 |
|-----|------|----------|
| RFC-010 | Phase 2 路线总纲 | D10-1, D10-2 |
| RFC-011 | DAG 引擎 | D10-1 |
| RFC-012 | Kuzu 存储 | D10-2 |
| RFC-013 | MCP 工具 | D10-3 |
| RFC-014 | 规则编排系统 | D10-5 |
| RFC-015 | 规则编排前端 | D10-5 |
| RFC-016 | Gap 分析 | D10-5 (桥接策略) |
| RFC-017 | YAML 格式 | D10-5 |
| RFC-018 | 规则双分离 | D10-4 |
| RFC-019 | Step.action 结构化 | D10-4 |
