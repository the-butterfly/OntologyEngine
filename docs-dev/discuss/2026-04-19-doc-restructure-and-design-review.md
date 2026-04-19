# 文档体系重构与详细设计审视 — 关键决策记录

> **日期**: 2026-04-19
> **参与者**: 用户 + Agent

## 决策 1: 文档三层分离

**选择**: docs/（活跃设计）+ docs-baseline/（归档参考）+ docs-dev/（开发过程）

**备选**: 保留原有 docs/ 多版本并存

**理由**: 项目处于重写阶段，多版本并存导致开发混乱。三层分离确保活跃文档干净，归档文档可追溯。

## 决策 2: Schema v2 为唯一 grammar 准则

**选择**: 以 01-overview + 09-canonical-schema-spec.md 为准，废弃 MVP Schema

**备选**: 双轨并存（v1 + v2）

**理由**: 双轨并存导致术语混乱（Concept vs FactObject, Metric vs AnalyticalElement），开发无法确定以哪个为准。

## 决策 3: 存储架构迁移到 KuzuDB+ChromaDB+SQLite

**选择**: 三引擎各司其职（图存储+向量存储+元数据存储）

**备选**: 继续使用 DuckDB 单一存储

**理由**: DuckDB 是 OLAP 引擎，不适合高频写入和图遍历。KuzuDB 提供原生 Cypher 查询，ChromaDB 提供向量检索+元数据过滤，SQLite 提供事务性元数据管理。参考 Cognee/m_flow/MemPalace 均采用多引擎方案。

## 决策 4: API 路由以新设计为准

**选择**: /v1/spaces + /v1/views + /v1/actions + /v1/query + /v1/ontology

**备选**: 保留旧路由 /v1/management + /v1/consumption

**理由**: 旧路由无语义（management 是什么？），新路由以 Space 为一等资源，语义清晰。端点从 130+ 精简到 60，重复端点从 20+ 降到 0。

## 决策 5: Instance 层 grammar 新增

**选择**: 新增 EntityInstance/EdgeInstance/CategoryTag/MetricValue/KnowledgeFragment 五种实例数据结构

**备选**: 不定义 Instance 层，实例隐式创建

**理由**: 参考 Cognee DataPoint 和 m_flow MemoryNode，实例层需要明确的 grammar 才能保证数据一致性和可验证性。

## 决策 6: 互索引边作为一等公民

**选择**: 四种互索引边（EXTRACTED_FROM/SUPPORTED_BY/DEFINED_IN/TRACE_TO）携带 source_file/offset/confidence/edge_text

**备选**: 仅存储实体-碎片关联，不携带语义

**理由**: 互索引边是 Layer-R/Layer-S 桥接的核心，edge_text 向量化后参与 Bundle Search 评分。参考 m_flow 的 includes_chunk/supported_by/derived_procedure 边模式。

## 决策 7: 时序建模作为 Instance 层一等特性

**选择**: EntityDeclaration 级 temporal 声明 + EntityInstance valid_from/valid_to + 时序边

**备选**: 不支持时序，所有实体视为当前快照

**理由**: 金融场景（注册资本、营收数据、担保敞口）必须支持时序。参考 MemPalace 的 valid_from/valid_to 时态窗口。

## 决策 8: RuleEngine 从 priority 升级为 DAG

**选择**: DAGBuilder + 拓扑排序 + 并行执行 + snapshot/restore 回滚

**备选**: 继续使用 priority 排序

**理由**: priority 排序无法表达步骤间显式依赖，无法并行执行无依赖规则。参考 KAG STRUCTURE 块 + Cognee Pipeline Task 三层结构。

## 决策 9: ExpressionEngine L0/L1 两级执行

**选择**: SimpleEvalExecutor(L0) + ASTSandboxExecutor(L1)，自动选择

**备选**: 继续使用 simpleeval + asteval 无条件 fallback

**理由**: asteval 无 AST 白名单校验、无循环/超时限制，存在安全风险。L0/L1 分离确保简单表达式快速执行，复杂表达式安全执行。

## 决策 10: 参考项目对齐策略

**选择**: 每个模块设计必须参考至少一个参考项目的对应模块

**备选**: 不参考外部项目，纯自研

**理由**: KAG/m_flow/Cognee/MemPalace 都是成熟的知识图谱项目，其设计模式经过验证。借鉴而非照搬，确保 OE 设计站在巨人肩膀上。
