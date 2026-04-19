# 服务层设计评审报告

> **status**: draft | **phase**: rewrite | **last_verified**: 2026-04-19

---

## 评审范围

本次评审覆盖 OntologyEngine 服务层（L3）的全部服务，按照 Overview 对齐 → 基线审查 → 参考项目对齐 → 偏差标记 → 重写的流程执行。

### 评审文件

| 文件 | 说明 |
|------|------|
| `docs/01-overview/04-modules.md` | 模块架构定义（目标态） |
| `docs/01-overview/05-concepts.md` | 核心概念定义（术语规范） |
| `docs/02-design/services/05-services-design.md` | 旧服务层设计（基线） |
| `ontology_engine/services/` | 当前服务层代码（实现态） |

### 参考项目

| 项目 | 评审关注点 |
|------|-----------|
| m_flow | Episodic Memory 管道编排、双通道处理、Bundle Search |
| Cognee | ECL Pipeline、BaseRetriever 三步管道、apply_feedback_weights |

---

## 基线审查：当前实现 vs 目标设计

### IngestionService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| 双通道 | 同步顺序导入，无快速/慢速分离 | 快速通道同步写入 + 慢速通道后台推理 | **严重** |
| 矛盾检测 | 无 | Ingest 时 LLM 比对 + contradiction_report | **严重** |
| Dataset 注册 | 不处理 | Dataset 元数据声明 + linkage_targets | **严重** |
| Fragment 管理 | 不创建 KnowledgeFragment | 文档切分 + 向量索引 + extraction_status | **严重** |
| 术语 | concept_type | _fact_object（Schema v2） | **中等** |
| 事务边界 | 软失败模式（错误收集后继续） | batch_size 内原子提交 | **中等** |

### QueryService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| Layer-R 检索 | 无 | query_raw：ChromaDB 向量检索 | **严重** |
| Layer-S 图遍历 | graph_traverse 仅邻域查询 | query_structured：KuzuDB Cypher + 时序过滤 | **严重** |
| 双路协同 | 无 | query_hybrid：Layer-R → Layer-S → trace_to | **严重** |
| 查询路由 | 无 | QueryRouter 自动识别查询类型 | **严重** |
| 查询解释 | 无 | explain 接口返回查询计划 | **中等** |
| 硬编码关系 | find_path 默认 "has_invoice" | Schema 声明驱动 | **中等** |
| Phase 2 占位 | semantic_search / hybrid_search 抛 NotImplementedError | 完整实现 | **严重** |

### AnalysisService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| 执行快照 | 无 | ExecutionStepSnapshot 全链路追溯 | **严重** |
| L3 并行预计算 | compute_batch 顺序计算 | 按依赖分组并行计算 | **严重** |
| 指标缓存 | 无 | SQLite 缓存已计算指标 | **严重** |
| 外部注入 | 不支持 context.overrides | overrides 检查跳过计算 | **中等** |
| _find_entity | 硬编码 concept_types 列表 | KuzuDB 全局 ID 索引 | **中等** |
| applies_to 检查 | 不验证规则适用性 | fact_objects + categories 匹配 | **中等** |
| 术语 | concept_type | _fact_object（Schema v2） | **中等** |

### IncrementalUpdateService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| 自动更新 | 无 | 定时轮询 + SHA256 变更检测 | **严重** |
| SHA256 检测 | 全量内容比对 | O(1) 哈希比对 | **严重** |
| 影响分析 | compute_impact 仅列实体/规则 | affected_entities + contradictions + cascade_depth | **严重** |
| 矛盾扫描 | 无 | 变更传播时检测矛盾 | **严重** |
| 人工确认 | 无 | 矛盾/级联深度过大时触发确认 | **严重** |
| 术语 | concept | _fact_object（Schema v2） | **中等** |

### FeedbackService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| 服务存在性 | **不存在** | 完整 FeedbackService | **严重** |
| feedback_weight | 无 | 流式更新 + 参与检索评分 | **严重** |
| 反馈记录 | 无 | SQLite 持久化反馈记录 | **严重** |

### EntityService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| 术语 | concept_type | _fact_object（Schema v2） | **中等** |
| 事务边界 | 软失败模式 | batch_create 全成功或全失败 | **中等** |
| Schema 验证 | 验证 concept_type 在 schema.concepts 中 | 验证 _fact_object 在 EntityDeclaration 中 | **中等** |
| 时序支持 | 无 | valid_from/valid_to 时序查询 | **中等** |

### SchemaService / DatasetService

| 维度 | 当前实现 | 目标设计 | 偏差等级 |
|------|---------|---------|---------|
| SchemaService | 基本功能可用 | 需对齐 Schema v2 术语 | **低** |
| DatasetService | 基本功能可用 | 需增加 linkage_targets 管理 | **低** |

---

## 偏差汇总

### 按严重等级统计

| 严重等级 | 数量 | 说明 |
|----------|------|------|
| **严重** | 22 | 核心功能缺失，无法满足目标设计要求 |
| **中等** | 9 | 功能存在但实现方式偏离目标 |
| **低** | 2 | 小幅调整即可对齐 |

### 按服务统计

| 服务 | 严重 | 中等 | 低 |
|------|------|------|-----|
| IngestionService | 4 | 2 | 0 |
| QueryService | 5 | 2 | 0 |
| AnalysisService | 3 | 4 | 0 |
| IncrementalUpdateService | 5 | 1 | 0 |
| FeedbackService | 3 | 0 | 0 |
| EntityService | 0 | 4 | 0 |
| SchemaService | 0 | 0 | 1 |
| DatasetService | 0 | 0 | 1 |

---

## 参考项目对齐分析

### m_flow 对齐

| m_flow 模式 | OntologyEngine 应对齐 | 当前偏差 |
|-------------|---------------------|---------|
| Phase 0A 三路并行（实体提取 + Facet 生成 + 匹配器准备） | IngestionService 慢速通道 | 完全缺失 |
| Episode Router 跨批次增量更新 | IngestionService 快速通道路由 | 完全缺失 |
| Edge text 向量化参与检索 | QueryService Bundle Search | 完全缺失 |
| AdaptiveScoringContext 自适应评分 | QueryService 查询路由 | 完全缺失 |
| Procedure 执行快照 | AnalysisService ExecutionStepSnapshot | 完全缺失 |

### Cognee 对齐

| Cognee 模式 | OntologyEngine 应对齐 | 当前偏差 |
|-------------|---------------------|---------|
| Pipeline Task 链式执行 | AnalysisService 执行序列 | 顺序调用无管道化 |
| BaseRetriever 三步管道 | QueryService 检索流程 | 完全缺失 |
| register_retriever 策略模式 | QueryService RetrieverRegistry | 完全缺失 |
| apply_feedback_weights 流式更新 | FeedbackService | 完全缺失 |
| DataPoint.source_content_hash | IncrementalUpdateService SHA256 检测 | 完全缺失 |
| SyncOperation 同步操作 | IncrementalUpdateService 自动更新 | 完全缺失 |

---

## 重写优先级

### P0：核心功能缺失（必须立即重写）

| 优先级 | 服务 | 重写内容 | 依赖 |
|--------|------|---------|------|
| P0-1 | IngestionService | 双通道架构 + 矛盾检测 + Fragment 管理 | Instance 层、storage/base.py |
| P0-2 | QueryService | query_raw / query_structured / query_hybrid | QueryEngine、storage/base.py |
| P0-3 | FeedbackService | 全新创建 | Instance 层 feedback_weight |

### P1：功能增强（Phase 1 内完成）

| 优先级 | 服务 | 重写内容 | 依赖 |
|--------|------|---------|------|
| P1-1 | AnalysisService | ExecutionStepSnapshot + L3 并行预计算 + 缓存 | DAG 执行、MetricEngine |
| P1-2 | IncrementalUpdateService | 自动轮询 + SHA256 + 影响分析 + 人工确认 | IngestionService、AnalysisService |

### P2：术语和接口对齐（渐进式）

| 优先级 | 服务 | 重写内容 | 依赖 |
|--------|------|---------|------|
| P2-1 | EntityService | Schema v2 术语 + 时序支持 | Instance 层 |
| P2-2 | SchemaService | Schema v2 术语对齐 | Schema v2 规范 |
| P2-3 | DatasetService | linkage_targets 管理 | Schema v2 规范 |

---

## 重写产出

本次评审产出以下设计文档：

| 文档 | 说明 |
|------|------|
| [services/README.md](../02-design/services/README.md) | 服务层设计总览 |
| [services/ingestion-service.md](../02-design/services/ingestion-service.md) | IngestionService 双通道设计 |
| [services/query-service.md](../02-design/services/query-service.md) | QueryService 完整接口 |
| [services/analysis-service.md](../02-design/services/analysis-service.md) | AnalysisService 跨引擎协调 |
| [services/incremental-update-service.md](../02-design/services/incremental-update-service.md) | IncrementalUpdateService 增量更新 |
| [services/feedback-service.md](../02-design/services/feedback-service.md) | FeedbackService 反馈闭环 |

---

## 风险与建议

| # | 风险 | 建议 |
|---|------|------|
| 1 | IngestionService 双通道重写影响面大 | 先实现快速通道，慢速通道用 SQLite 队列解耦 |
| 2 | QueryService 依赖 QueryEngine 尚未实现 | 与 QueryEngine 重写并行推进，接口先行 |
| 3 | FeedbackService 是全新服务 | 优先实现 submit_feedback + 流式更新，检索评分集成后做 |
| 4 | 术语迁移（concept_type → _fact_object）影响全链路 | 统一在 DTO 层做映射，内部统一使用新术语 |
| 5 | 旧设计文档 05-services-design.md 与新设计冲突 | 标注旧文档为 [已过期入口]，新文档为 [单一事实源] |

---

## 评审结论

服务层当前实现与目标设计存在 **22 项严重偏差**，主要集中在：

1. **核心功能缺失**：双通道摄入、Layer-R/Layer-S 检索、反馈闭环、自动增量更新均未实现
2. **术语体系陈旧**：仍使用 MVP 阶段的 concept_type，未对齐 Schema v2 的 _fact_object
3. **参考项目对齐不足**：m_flow 的双通道处理和 Cognee 的 Pipeline 模式未在服务层体现

建议按 P0 → P1 → P2 优先级推进重写，P0 项在 Phase 1 内必须完成。
