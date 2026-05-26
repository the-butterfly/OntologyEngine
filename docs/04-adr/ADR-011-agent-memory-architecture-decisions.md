# ADR-011: Agent 记忆系统关键架构决策

| 字段 | 值 |
|------|-----|
| 状态 | accepted |
| 日期 | 2026-05-15 |
| 决策者 | Agent 记忆模块设计评审 |
| 关联 | RFC-020 ~ RFC-025, ADR-009, `docs/02-design/agent-memory/` |

---

## 背景

Agent 记忆系统 (RFC-020~025) 是 Phase 2 增量中最重大的架构新增。本 ADR 从 6 个 RFC 及后续实施审查中提取对未来有持续约束力的关键决策。

---

## D11-1: 双层存储 + memory_type 标签 (非四层物理架构)

**来源**: RFC-020~025 设计基础, `02-design/agent-memory/README.md` D-AM-1

**决策**:
1. Agent 记忆采用双层存储：Layer-R (KnowledgeFragment, 原始碎片) + Layer-S (MemoryUnit, 类型化记忆单元)
2. 记忆类型通过 `memory_type` 标签区分 (fragment/observation/entity/mental_model/episode/procedure 等)，而非物理分层
3. 共享字段统一建表，类型特有字段存为 JSON attributes

**理由**:
- Observation/Mental Model 的差异是语义和生命周期差异，不是存储范式差异
- Hindsight 用一张表 + fact_type 证明了统一存储可行
- JSON attributes 避免多表冗余，灵活扩展

**影响**:
- 新增 CognitiveNode / MemoryUnit 模型，与现有 EntityNode 共存
- memory_type 枚举后续扩展需经过评审
- 类型特有字段的 JSON schema 需维护文档

---

## D11-2: 三大认知操作 (remember / recall / reflect) 而非五个

**来源**: `02-design/agent-memory/README.md` D-AM-5, RFC-020

**决策**:
1. 认知操作缩减为 3 个：remember (写入) / recall (检索) / reflect (反思)
2. consolidate (巩固) 和 forget (遗忘) 作为 reflect 内部机制，不暴露为独立 API
3. 对应 MCP 工具：`oe_remember` / `oe_recall` / `oe_reflect`

**理由**:
- Agent 交互接口应简化，减少认知负担
- consolidat/forget 是系统内部维护行为，不应由 Agent 直接触发
- 参考 MemOS + Hindsight 设计

**影响**:
- API 设计按 3 操作组织，consolidation/forgetting 为内部引擎
- Reflect Agent 内部包含强制检索序列 + 矛盾检测

---

## D11-3: 巩固 = memory_type 类型升级 (非跨层复制)

**来源**: `02-design/agent-memory/README.md` D-AM-2

**决策**:
1. 巩固操作是 memory_type 在类型体系中的升级：fragment → observation → entity → mental_model
2. 巩固在同一存储层内完成，无需跨层数据复制
3. 巩固通过 Create/Update/Delete 三动作模型实现

**理由**:
- 避免数据冗余：升级而非复制
- 生命周期可追溯：保留升级路径

**影响**:
- ConsolidationEngine 需维护类型升级映射表
- 每个类型升级需明确触发条件

---

## D11-4: 遗忘采用价值感知 Ebbinghaus 衰减 (非统一衰减)

**来源**: `02-design/agent-memory/README.md` D-AM-3, ADR-009

**决策**:
1. 遗忘衰减采用线性衰减 (30 天窗口归零)，替代指数衰减
2. 高价值记忆 (高 strength) 衰减更慢
3. recency 分量从指数 `math.exp(-0.1 * days_since_access)` 改为线性 `max(0.0, 1.0 - (age_hours / (30 * 24)))`

**理由**:
- 线性衰减更可解释
- 指数衰减在 30 天后仍有 ~5% 残留，长期未访问记忆的 recency 无区分度
- 此变更为临时简化，QUL 重新集成后应恢复可配置的 recency_bias

**影响**:
- `_compute_strength` 使用线性衰减
- `rank_score` 时间权重从动态改为固定 0.3 (丧失 recency_bias 调节能力)
- 需通过实际数据验证 30 天窗口是否合适

---

## D11-5: 四建模对象 × 四认知层正交分类

**来源**: 设计讨论, lencx 批判框架

**决策**:
1. memory_type 解决"是什么"的类型问题，model_domain 解决"属于谁"的归属问题
2. 四建模对象：User Model / Task Model / World Model / Self Model
3. 两者构成正交分类体系

**理由**:
- lencx 批判框架指出原设计缺少模型归属维度
- 正交分类让检索可同时按类型和归属过滤

**影响**:
- CognitiveNode 增加 `model_domain` 字段
- 检索 API 增加 model_domain 过滤参数
- Self Model / Task Model 详细设计待补充 (TODO.md P2)

---

## D11-6: QUL (Query Understanding Layer) 作为检索策略中枢

**来源**: RFC-021, `02-design/agent-memory/query-understanding-layer.md`

**决策**:
1. QUL 负责任务约束提取 → 驱动检索策略 (而非 LLM 直接分类)
2. QUL 支持 8 种约束类型：temporal / entity_type / user_preference / task_status / numeric / negation / scope / decision
3. QUL 按约束类型逐步解析，非一次性 LLM 调用

**理由**:
- 本地优先原则：避免每次查询调用 LLM
- 特征匹配 O(1) 优于 LLM O(tokens)
- 多约束可组合

**影响**:
- QUL 是 Agent 记忆检索的必由之路
- 8 种约束类型的实现优先级：temporal/user_preference/decision 已完成，其余待实施
- QUL 重新集成时需恢复 recency_bias 配置能力

---

## D11-7: 治理优先于容量 — 权限治理 + 来源可信层级 + 策略性遗忘

**来源**: lencx 批判框架, 设计审视

**决策**:
1. 记忆治理是 Agent 记忆系统的核心挑战，优先级高于存储容量
2. 引入来源可信层级：用户声明 > 行为推断 > 环境观测 > Agent 生成
3. 策略性遗忘由否定信号驱动 (superseded/rejected 触发加速遗忘)
4. DeduplicationGate + ArbitrationEngine + PermissionService 作为治理层组件

**理由**:
- 无治理的记忆系统 = 不可信的记忆系统
- Agent 生成知识的可信度天然低于用户声明
- 否定信号是遗忘的最强驱动力

**影响**:
- 所有记忆操作需经过 DeduplicationGate 去重 + 矛盾检测
- 来源可信层级影响检索排序权重
- 策略性遗忘实现优先级高于容量驱动遗忘

---

## 影响范围

| 决策 | 影响模块 | 影响层级 |
|------|----------|----------|
| D11-1: 双层 + memory_type | `engine/cognitive/`, `storage/` | Engine + Storage |
| D11-2: 3 认知操作 | `api/`, `mcp/`, `services/` | API + MCP + Service |
| D11-3: 巩固=类型升级 | `engine/cognitive/consolidation.py` | Engine |
| D11-4: 线性衰减 | `engine/cognitive/memory_api.py` | Engine |
| D11-5: 正交分类 | `core/schema/cognitive.py` | Core |
| D11-6: QUL 中枢 | `engine/cognitive/qul/` | Engine |
| D11-7: 治理优先 | `engine/cognitive/dedup.py`, `engine/cognitive/arbitration.py` | Engine |

## 关联 RFC

| RFC | 主题 | ADR 覆盖 |
|-----|------|----------|
| RFC-020 | 记忆生成路径优化 | D11-1, D11-2, D11-3 |
| RFC-021 | Query Understanding Layer | D11-6 |
| RFC-022 | LLM Reflection + 策略性遗忘 | D11-4, D11-7 |
| RFC-023 | 检索路径优化 | D11-1, D11-5 |
| RFC-024 | CognitiveNode 模型修复 | D11-1 |
| RFC-025 | 旅程优化 | D11-2, D11-7 |
