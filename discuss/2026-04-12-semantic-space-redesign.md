# 2026-04-12 语义空间架构重构设计会话记录

**会话时间**: 2026-04-12
**参与**: 设计评审
**分支**: dev

---

## 1. 背景

本次会话源于对当前代码仓的深度分析（详见分析报告），发现以下关键问题：

1. **执行引擎是 mock**：Phase 2 的 semantic_spaces 执行端点使用 mock 实现，无法真正验证规则逻辑
2. **Schema v2 设计文档与实现不一致**：L3_elements vs L3_analytical_elements 命名不匹配
3. **管理面/消费面未分离**：API 和前端都混在一起
4. **规则声明/实例未分离**：设计文档提到但实现未跟上

## 2. 核心设计决策

### 2.1 语义空间架构

**决策**：引入语义空间 (Semantic Space) 作为顶层容器

| 空间类型 | 说明 |
|----------|------|
| **管理空间 (Management Space)** | 权威数据源，完整控制，可编辑，可同步外部数据 |
| **消费视图 (Consumption View)** | 只读，授权获得，可聚合多个管理空间 |

**关系**：
- 一个管理空间可以授权部分内容给多个消费视图
- 一个消费视图可以聚合多个管理空间的授权
- 默认创建管理空间时同步生成同名消费视图

### 2.2 路由分离

**决策**：管理面和消费面 API 完全分离

| 模块 | 前缀 | 说明 |
|------|------|------|
| 管理面 API | `/v1/management/{spaceId}/` | Space/Schema/Instances/Datasets/... |
| 消费面 API | `/v1/consumption/{viewId}/` | Visualize/Execute/Simulate |

**前端路由**：
```
/management/{spaceId}/
/consumption/{viewId}/
```

### 2.3 声明与实例分离

**决策**：L1-L4 各层都区分声明和实例

| 层 | 声明 | 实例 |
|---|---|---|
| L1 | 事实对象定义 | 实体实例 |
| L2 | 分类方案定义 | 分类标签 |
| L3 | 指标定义 | 指标值 |
| L4 | 规则声明 | 规则逻辑 |

**核心原则**：
- 声明 = 定义（类型、约束、范畴）
- 实例 = 具体数据/配置

### 2.4 规则声明 vs 规则实例

**决策**：一个规则声明可关联多个规则实例

**规则声明 (Rule Definition)**：
```yaml
id: R001
name: 信用检查
target_objects: [Supplier]
input_elements: [credit_score, overdue_ratio]
output_elements: [eligible, risk_level]
priority: 100
```

**规则实例 (Rule Logic)**：
```yaml
id: R001_logic_manufacturing
definition_id: R001
applicable_conditions:
  - classification: industry
    value: 制造业
when: "credit_score >= 60"
then_action:
  action_type: set_flag
  output: { eligible: true }
```

### 2.5 分层版本管理

**决策**：各层独立版本管理，Schema 层完整快照，实例层增量 diff

| 层 | 存储策略 |
|---|----------|
| L1-L4 声明 | 完整快照 |
| L4 rule_logics | 增量 diff |
| Instances | 增量 diff (上限 10W) |

### 2.6 数据集与同步

**决策**：
- Dataset = 外部数据源的逻辑抽象
- 支持全量同步和增量同步
- 增量支持：时间戳字段 / 业务条件

---

## 3. 术语对照

| 英文 | 中文 | 说明 |
|------|------|------|
| Semantic Space | 语义空间 | 顶层容器 |
| Management Space | 管理空间 | 权威数据源 |
| Consumption View | 消费视图 | 授权数据视图 |
| Authorization | 授权 | 管理→消费的映射配置 |
| Declaration | 声明 | 各层的定义 |
| Instance | 实例 | 具体数据和配置 |
| Layer | 层 | L1/L2/L3/L4 |
| Sync | 同步 | 从 Dataset 更新实例 |
| Dataset | 数据集 | 外部数据源抽象 |
| Field Mapping | 字段映射 | Dataset → Entity 的字段对应 |

---

## 4. 新增/更新文档清单

| 文档 | 状态 | 说明 |
|------|------|------|
| `docs/05-schema-v2/00-overview.md` | ✅ 更新 | 整合语义空间概念 |
| `docs/05-schema-v2/00b-semantic-space-architecture.md` | 🆕 新增 | 语义空间架构详细说明 |
| `docs/05-schema-v2/01-fact-objects.md` | ✅ 更新 | 声明/实例分离 |
| `docs/05-schema-v2/02-categorization.md` | ✅ 更新 | 声明/实例分离 |
| `docs/05-schema-v2/03-analytical-elements.md` | ✅ 更新 | 声明/实例分离 |
| `docs/05-schema-v2/04-business-logic.md` | ✅ 更新 | 声明/实例分离 |
| `docs/05-schema-v2/06-dataset-and-sync.md` | 🆕 新增 | 数据集与同步设计 |
| `docs/05-schema-v2/07-rule-declaration-and-instance.md` | 🆕 新增 | 规则声明/实例详细说明 |
| `docs/05-schema-v2/08-version-management.md` | 🆕 新增 | 分层版本管理设计 |
| `docs/09-frontend-architecture.md` | ✅ 更新 | 新路由结构 |
| `docs/10-api-architecture.md` | 🆕 新增 | API 架构设计 |

---

## 5. 待解决问题

### 5.1 Phase 2 执行引擎

**问题**：当前 semantic_spaces.py 的 execute_analyze 和 execute_simulate 使用 mock 实现

**影响**：
- What-if 模拟不生效
- 规则执行无法真正验证

**建议**：Phase 3 优先实现真实表达式引擎集成

### 5.2 前端消费页面

**问题**：Phase 2 新增的 consumption/ 页面没有真正实现 G6 可视化

**影响**：
- 页面是半成品

**建议**：Phase 3 完成 G6 渲染实现

### 5.3 API 实现

**问题**：新的 API 设计需要完整实现

**影响**：
- 当前 semantic_spaces.py 需要重构
- 需要拆分 management 和 consumption 路由

**建议**：按阶段实现

---

## 6. 后续工作

### Phase 2.5 (短期)
1. 实现真实表达式引擎集成到 semantic_spaces
2. 完成前端 consumption 页面 G6 可视化
3. 重构 semantic_spaces.py 路由

### Phase 3 (中期)
1. 完整实现 management/consumption 路由拆分
2. 实现 Dataset 同步功能
3. 实现分层版本管理

### Phase 4 (长期)
1. 消费视图授权机制
2. Neo4j 存储适配器
3. 企业级特性 (RBAC, 审计)

---

*记录结束*
