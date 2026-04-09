# TODO - 基于评审意见

> **Last Updated**: 2026-04-09
> **状态**: 新增 Agent 接口设计任务

## 🔴 P0: 评审修复 (已完成)

| TODO | 状态 | 说明 |
|------|------|------|
| 移除 Cypher API | ✅ Done | 改为 filter-based |
| 删除 roadmap.md | ✅ Done | 以 goals.md 为准 |
| L3/L4 边界 | ✅ Done | L3 含 optional default_formula |
| Formula 执行器 | ✅ Done | asteval + 预制函数 |
| 删除 legacy docs | ✅ Done | 归档到 archive/ |

## 🟡 P1: Agent 接口设计 (已确认方向)

| TODO | 状态 | 说明 |
|------|------|------|
| MCP + CLI 接口 | ✅ 设计完成 | docs/07-agent-interface.md |
| 知识检索服务 | ✅ 设计完成 | docs/08-knowledge-retrieval.md |
| 云端/本地混合部署 | ✅ 设计完成 | 组织级资产共享 |
| 反馈闭环 | ✅ 合并到 08 | 操作历史 + 回退 |
| Schema 版本审计 | ✅ 合并到 07 | PostgreSQL 扩展 |

## 🟢 P2: 平台化扩展

| TODO | 状态 | 说明 |
|------|------|------|
| Faiss 维度处理 | 🔄 Partial | 需补充迁移策略 |
| LLM 推理边界 | 🔄 Partial | 需补充 Prompt 模板 |
| 并发写入模型 | ⏳ Open | 待设计 |
| 基准测试 | ⏳ Open | DuckDB 10M 性能验证 |

## 🔵 P3: Phase 1 模块实现 (基于 06-module-detailed-design)

> **基于**: docs/06-module-detailed-design/ (10个模块详细设计)
> **场景**: 供应链金融授信评估 (examples/supply_chain_finance)

### 模块实现优先级

| 优先级 | 模块 | 设计文档 | 关键任务 |
|--------|------|----------|----------|
| 🔴 P3.1 | Schema 加载 | 01-schema-loading.md | v1/v2 兼容、统一模型、校验增强 |
| 🔴 P3.1 | 实例管理 | 02-instance-management.md | 属性校验、DuckDB 增强 (metrics/tags 表) |
| 🔴 P3.1 | 存储层 | 03-storage-layer.md | computed_metrics/category_tags/rule_execution_log 表 |
| 🔴 P3.2 | 表达式引擎 | 07-expression-engine.md | 两级安全模型 (L0+L1) |
| 🔴 P3.2 | 指标引擎 | 04-metric-engine.md | 四类指标计算、DAG 依赖 |
| 🔴 P3.2 | 规则引擎 | 06-rule-engine.md | 通用算子体系、替代硬编码 action |
| 🟡 P3.3 | 归类引擎 | 05-categorization-engine.md | L2→L4 编译复用 |
| 🟡 P3.3 | 查询引擎 | 08-query-engine.md | 图遍历 DSL、向量检索 |
| 🟡 P3.4 | 服务层 | 09-services-layer.md | 5 个 Service 编排 |
| 🟡 P3.4 | API 层 | 10-api-layer.md | FastAPI 13 个端点 |

### 设计缺口已解决

| 缺口 | 解决方案 |
|------|----------|
| MetricEngine 缺失 | 04-metric-engine.md: 四类指标统一引擎 |
| CategorizationEngine 缺失 | 05-categorization-engine.md: 复用规则引擎 |
| QueryEngine 缺失 | 08-query-engine.md: 图遍历+向量+混合 |
| Services 层缺失 | 09-services-layer.md: 5 个 Service |
| API 层缺失 | 10-api-layer.md: 13 个端点 |
| 硬编码 action | 06-rule-engine.md: 8 个通用算子 |
| Schema v1/v2 割裂 | 01-schema-loading.md: 统一内部模型+兼容映射 |
