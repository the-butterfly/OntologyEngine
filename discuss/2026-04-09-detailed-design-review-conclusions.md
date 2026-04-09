# 详细设计对齐讨论记录

> 日期: 2026-04-09
> 议题: 结合 Agent 检视意见，分析详细设计文档是否满足

## 评审交叉验证结果

| # | 评审问题 | 状态 | 对应文档 |
|---|---------|------|---------|
| 1 | Schema v1 vs v2 割裂 | ✅ 已解决 | 01-schema-loading.md: V1CompatMapper |
| 2 | DAG 执行模型缺失 | ✅ 已解决 | 06-rule-engine.md: RuleDAG + depends_on |
| 3 | 表达式引擎安全 | ✅ 已解决 | 07-expression-engine.md: L0+L1 两级 |
| 4 | 存储层表不全 | ✅ 已解决 | 03-storage-layer.md: 7 张表 |
| 5 | MetricEngine 缺失 | ✅ 已解决 | 04-metric-engine.md |
| 6 | Services 层空缺 | ✅ 已解决 | 09-services-layer.md |
| 7 | 图遍历 DSL 未实现 | ✅ 已解决 | 08-query-engine.md |
| 8 | CategorizationEngine | ✅ 已解决 | 05-categorization-engine.md |
| 9 | 跨引擎协调 | ✅ 已解决 | 09-services-layer.md: 直接调用 |
| 10 | 移除 Cypher API | ✅ 已解决 | 08-query-engine.md |
| 11 | 目录结构清理 | ✅ 已解决 | 已提交 |

## 争议处理

### 争议 1: L3/L4 公式归属

**评审立场**: L3 = 定义"WHAT"，不应含 formula；formula 应在 L4 action 中重复定义。

**最终决策**: 保留当前设计（L3 默认 + L4 可覆盖）

**理由**: L3 的 `formula` 是**客观计算定义**（如比率计算方式），L4 action 的 `computation.formula` 是**业务决策逻辑**（如授信乘数）。两者不是重复定义，而是**默认 + 可覆盖**机制，避免同一指标在不同规则组中出现不一致。

**文档更新**: 04-metric-engine.md 头部添加澄清说明。

### 争议 2: 图查询 SLA 定义位置

**最终决策**: 补充到 00-overview.md 的性能目标章节。

**内容**: 5 类查询的 P99 目标（点查<50ms / 邻居<100ms / 路径<200ms / 图指标<1s / 混合<500ms）。

**文档更新**: 00-overview.md 补充"图查询 SLA（Phase 1）"表格。

### 争议 3: edges vs relations 表名

**评审发现**: 实际代码用 `relations`，设计文档用 `edges`。

**最终决策**: 统一改为 `relations`（改设计文档）

**文档更新**:

- `03-storage-layer.md`: 表名 + 索引名改为 `relations`
- `02-design/03-storage-design.md`: 同步更新
- `02-design/02-api-design.md`: API 端点 `/v1/edges` → `/v1/relations`
- `10-api-layer.md`: 路由前缀 + 文件名 + 函数名
- `02-instance-management.md`: SQLite 示例代码 + 注释 + 变量名
- `00-overview.md`: 架构图表名

**一致性**: 存储层 → API 层 → 文档层全部统一为 `relations`。

## 结论

详细设计文档经过评审交叉验证后：
- 11 个已解决项全部对应到具体文档位置
- 3 个争议项均已讨论决策并落实文档更新

详细设计满足 Phase 1 实现需求，可作为代码实现的依据。
