# 存储设计评审报告

> **status**: draft | **phase**: rewrite | **last_verified**: 2026-04-19

---

## 目的

记录 OntologyEngine 存储层设计评审的完整过程和结论，包括偏差矩阵、参考项目对齐结果和产出文件清单。

## 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 存储设计缺乏系统性评审 | 建立偏差矩阵，逐维度对比基线与目标 |
| 2 | 参考项目的设计点未显式追踪 | 建立对齐矩阵，逐项目逐维度标注 |
| 3 | 评审产出缺乏统一记录 | 本报告作为评审唯一产出入口 |

---

## 评审流程

```
Overview 对齐 → 基线审查 → 参考项目对齐 → 偏差标记 → 重写
     ✅              ✅            ✅             ✅          ✅
```

---

## 偏差矩阵

### 架构级偏差

| # | 维度 | 基线（DuckDB） | 目标（KuzuDB+ChromaDB+SQLite） | 偏差级别 | 偏差原因 |
|---|------|---------------|-------------------------------|---------|---------|
| 1 | 存储引擎 | DuckDB 单一引擎 | KuzuDB + ChromaDB + SQLite 三引擎 | **重大** | DuckDB 不支持 Cypher、向量持久化、WAL 并发 |
| 2 | 接口设计 | StorageBackend 单一接口 | GraphStore + VectorStore + MetaStore 三接口 | **重大** | 职责分离，各接口独立演化 |
| 3 | 目录结构 | storage/duckdb/ 单目录 | storage/graph/ + storage/vector/ + storage/meta/ | **重大** | 模块边界重构 |
| 4 | 配置模型 | 无统一配置 | StorageConfig (pydantic-settings) | **中等** | 支持环境变量和多后端切换 |
| 5 | 工厂模式 | 无 | create_graph_store / create_vector_store / create_meta_store | **中等** | 依赖倒置，上层不依赖具体实现 |

### 数据模型偏差

| # | 维度 | 基线 | 目标 | 偏差级别 | 对齐规范 |
|---|------|------|------|---------|---------|
| 6 | 实体模型 | entities 表（id, type, name, properties） | EntityNode（id, _fact_object, name, attributes, valid_from/valid_to, domain_id, confidence, source_pipeline, source_content_hash, feedback_weight） | **重大** | Schema v2 EntityInstance |
| 7 | 关系模型 | relations 表（id, source_id, target_id, relation_type, properties） | RELATES_TO（id, from_id, to_id, relation_name, attributes, edge_text, weight, valid_from/valid_to, confidence, source_pipeline, source_content_hash） | **重大** | Schema v2 EdgeInstance |
| 8 | 向量存储 | LocalVectorStore 内存 | ChromaDB 7 集合持久化 | **重大** | ChromaDB 集合设计 |
| 9 | 元数据 | 无独立存储 | SQLite 7 表 | **重大** | SQLite 表设计 |
| 10 | 互索引边 | 无 | EXTRACTED_FROM / SUPPORTED_BY / DEFINED_IN / TRACE_TO | **重大** | Schema v2 互索引边 |
| 11 | 分类标注 | 无 | CategoryTagNode + CATEGORIZED_AS 边 | **新增** | Schema v2 CategoryTag |
| 12 | 指标值 | 无 | MetricValueNode + HAS_METRIC 边 | **新增** | Schema v2 MetricValue |
| 13 | 规则定义 | 无 | RuleDefinitionNode + DEFINED_IN 边 | **新增** | Schema v2 RuleDefinition |
| 14 | 知识碎片 | 无 | KnowledgeFragmentNode + 互索引边 | **新增** | Schema v2 KnowledgeFragment |

### 操作级偏差

| # | 维度 | 基线 | 目标 | 偏差级别 |
|---|------|------|------|---------|
| 15 | 写入模式 | INSERT OR REPLACE | MERGE（幂等） | **中等** |
| 16 | 批量写入 | 逐条写入 | UNWIND+MERGE + 端点分区 | **重大** |
| 17 | 异步 | 同步阻塞 | async/await + ThreadPoolExecutor | **中等** |
| 18 | 时序查询 | 无 | valid_from/valid_to 时间切片 | **新增** |
| 19 | 溯源查询 | 无 | source_pipeline + source_content_hash | **新增** |
| 20 | 反馈闭环 | 无 | feedback_weight 更新 + 检索评分 | **新增** |
| 21 | Schema 版本 | 无 | SchemaVersionManager | **新增** |
| 22 | 审计日志 | 无 | audit_log | **新增** |

---

## 参考项目对齐结果

### Cognee KuzuAdapter 对齐

| # | 设计点 | Cognee 实现 | OntologyEngine 采用 | 对齐程度 |
|---|--------|-----------|-------------------|---------|
| 1 | 节点表设计 | 1 表（DataPoint） | 5 节点表 | 部分对齐（多表扩展） |
| 2 | 边表设计 | 1 表（Edge） | RELATES_TO + 6 边表 | 部分对齐（多表扩展） |
| 3 | UUID5 确定性 ID | DataPoint UUID5 | EntityInstance UUID5 | 完全对齐 |
| 4 | UNWIND+MERGE 批量写入 | add_nodes / add_edges | batch_create_nodes / batch_create_edges | 完全对齐 |
| 5 | ThreadPoolExecutor 异步 | execute_query | query_cypher | 完全对齐 |
| 6 | source_pipeline 溯源 | DataPoint.source_pipeline | EntityInstance.source_pipeline | 完全对齐 |
| 7 | source_content_hash | DataPoint.source_content_hash | EntityInstance.source_content_hash | 完全对齐 |
| 8 | feedback_weight | apply_feedback_weights | update_feedback_weight | 完全对齐 |
| 9 | MAP 动态属性 | properties MAP | attributes MAP(STRING, STRING) | 完全对齐 |

### m_flow GraphProvider 对齐

| # | 设计点 | m_flow 实现 | OntologyEngine 采用 | 对齐程度 |
|---|--------|-----------|-------------------|---------|
| 1 | 多节点表 | Entity / Concept / ContentFragment | 5 节点表 | 完全对齐 |
| 2 | 边分区写入 | _partition_edges_by_endpoints | 端点分区批处理 | 完全对齐 |
| 3 | edge_text 边语义 | 每条边携带自然语言描述 | EdgeInstance.edge_text | 完全对齐 |
| 4 | weight 边权重 | Bundle Search 代价传播 | EdgeInstance.weight | 完全对齐 |
| 5 | attributes 边属性 | FacetPoint 属性字典 | EdgeInstance.attributes | 完全对齐 |
| 6 | checkpoint 机制 | GraphProvider.checkpoint | 迁移脚本进度记录 | 部分对齐 |
| 7 | 多集合向量 | VectorProvider 多集合 | ChromaDB 7 集合 | 完全对齐 |
| 8 | Bundle Search | 四阶段算法 | 集成互索引边的五阶段 | 扩展对齐 |

### MemPalace 对齐

| # | 设计点 | MemPalace 实现 | OntologyEngine 采用 | 对齐程度 |
|---|--------|--------------|-------------------|---------|
| 1 | ChromaDB 向量存储 | Drawer 集合 | 7 集合 | 扩展对齐 |
| 2 | metadata 过滤 | Wing/Room | domain_id + confidence + edge_type | 扩展对齐 |
| 3 | SQLite WAL | 时序三元组 | 7 表 + WAL | 扩展对齐 |
| 4 | Validity Window | invalidate() 设置 valid_to | valid_from/valid_to 字段 | 完全对齐 |
| 5 | verbatim 存储 | 原文块存储 | KnowledgeFragment.text | 完全对齐 |
| 6 | 置信度评分 | triple 级置信度 | EntityInstance.confidence | 扩展对齐（实例级） |

---

## 对齐度总结

| 参考项目 | 完全对齐 | 部分对齐 | 扩展对齐 | 未对齐 |
|---------|---------|---------|---------|--------|
| Cognee KuzuAdapter | 6 | 2 | 0 | 1（2 表极简） |
| m_flow GraphProvider | 6 | 1 | 1 | 0 |
| MemPalace | 2 | 0 | 4 | 0 |

**未对齐项说明**：

| # | 未对齐项 | 原因 |
|---|---------|------|
| 1 | Cognee 2 表极简设计 | OntologyEngine 有 5 种节点类型（EntityInstance、RuleDefinition、KnowledgeFragment、CategoryTag、MetricValue），2 表无法满足类型约束需求 |

---

## 产出文件清单

| # | 文件路径 | 内容 | 状态 |
|---|---------|------|------|
| 1 | `docs/02-design/storage/README.md` | 存储设计总览，架构、偏差、数据流、配置 | draft |
| 2 | `docs/02-design/storage/kuzudb-schema.md` | KuzuDB 节点/边表 Schema，对齐 Instance 层 | draft |
| 3 | `docs/02-design/storage/chromadb-collections.md` | ChromaDB 7 集合设计、嵌入策略、CRUD | draft |
| 4 | `docs/02-design/storage/sqlite-tables.md` | SQLite 7 表、WAL 模式、SchemaVersionManager | draft |
| 5 | `docs/02-design/storage/interfaces.md` | GraphStore/VectorStore/MetaStore 接口、工厂模式 | draft |
| 6 | `docs/02-design/storage/migration.md` | DuckDB→KuzuDB 迁移路径、数据映射、回滚 | draft |
| 7 | `docs-dev/review-reports/storage-review.md` | 本评审报告 | draft |

---

## 评审结论

### 通过项

| # | 评审项 | 结论 |
|---|--------|------|
| 1 | 架构方向 | DuckDB → KuzuDB+ChromaDB+SQLite 三引擎拆分方向正确 |
| 2 | Schema v2 对齐 | KuzuDB 节点/边表严格对齐 Instance 层 5 种数据结构 |
| 3 | 互索引边 | 4 种互索引边完整实现，对齐 mutual-index-edges.md |
| 4 | 参考项目对齐 | Cognee/m_flow/MemPalace 核心设计点均已对齐 |
| 5 | 接口设计 | 三接口职责分离，异步优先，工厂模式 |
| 6 | 迁移策略 | 并行运行→验证→切换，回滚计划完整 |

### 待扩展项

| # | 待扩展项 | 说明 | 优先级 |
|---|---------|------|--------|
| 1 | ExecutionStepSnapshotNode | TRACE_TO 的源端应为 ExecutionStepSnapshot，当前暂用 EntityNode | Phase 2 |
| 2 | Neo4j 后端 | GraphStore 的 Neo4j 实现 | Phase 2 |
| 3 | FAISS 后端 | VectorStore 的 FAISS 实现（>100K 规模） | Phase 2 |
| 4 | PostgreSQL 后端 | MetaStore 的 PostgreSQL 实现 | Phase 2 |
| 5 | 关系表拆分 | RELATES_TO 按高频关系拆分为独立表 | Phase 2 |
| 6 | 补偿事务 | 跨引擎事务的补偿机制实现 | Phase 1 |

### 风险项

| # | 风险 | 缓解措施 |
|---|------|---------|
| 1 | KuzuDB UNWIND+MERGE write-write conflict | 端点分区批处理（已对齐 m_flow） |
| 2 | ChromaDB 集合数量多（7 个），初始化和同步成本 | 懒初始化 + 异步双写 |
| 3 | knowledge_fragments 双写（KuzuDB + SQLite） | 异步同步 + 定期校验 |
