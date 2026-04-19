# Schema 设计审视报告

> **审视日期**: 2026-04-19
> **审视范围**: docs/02-design/schema/ 全部文档
> **审视流程**: Overview 对齐 → Baseline 审视 → 参考项目对齐 → 偏差标注 → 重写

## 审视结论

Schema 设计审视已完成，产出了 6 份设计文档，覆盖 L1-L4 声明层、Instance 层、互索引边、时序建模、参考项目对齐分析。

## Overview 对齐结果

| Overview 概念 | Schema 文档对齐状态 | 备注 |
|---------------|---------------------|------|
| L1 Fact Objects | ✅ 完全对齐 | EntityDeclaration + RelationDeclaration |
| L2 Categorizations | ✅ 完全对齐 | DimensionDeclaration (hierarchical/derived/tag_based) |
| L3 Analytical Elements | ✅ 完全对齐 | MetricDeclaration (atomic/derived/graph/composite/variable) |
| L4 Business Logic | ✅ 完全对齐 | RuleDefinitionDeclaration + RuleLogicDeclaration |
| Layer-R KnowledgeFragment | ✅ 完全对齐 | Instance 层 KnowledgeFragment |
| Layer-S EntityInstance/EdgeInstance | ✅ 完全对齐 | Instance 层 EntityInstance/EdgeInstance |
| 互索引边 (4 种) | ✅ 完全对齐 | mutual-index-edges.md |
| 时序建模 | ✅ 完全对齐 | temporal-modeling.md |
| 语义空间隔离 | ✅ 完全对齐 | L1-L4-declarations.md semantic_space |
| 矛盾检测 | ⚠️ 部分对齐 | Instance 层 confidence 字段支持，详细设计在服务层 |
| 反馈闭环 | ⚠️ 部分对齐 | Instance 层 feedback_weight 字段支持，详细设计在服务层 |

## Baseline 审视结果

| Baseline 文档 | 提取内容 | 偏差处理 |
|---------------|----------|----------|
| 09-canonical-schema-spec.md | L1-L4 完整 grammar | 以冻结 grammar 为准，增强 identity_fields/temporal/logical_type 等字段 |
| 01-fact-objects.md | L1 设计决策 | 保留所有决策，增强参考项目洞察 |
| 02-categorization.md | L2 设计决策 | 保留三种维度类型，增强 applicable_to |
| 03-analytical-elements.md | L3 设计决策 | 保留五种指标类型，增强 source_* 溯源 |
| 04-business-logic.md | L4 设计决策 | 保留声明/实例分离，增强 applicability 六维度 |
| 01-schema-spec.md (v1 MVP) | 旧术语映射 | 标注 deprecated，提供 v1→v2 迁移映射表 |

## 参考项目对齐结果

| 项目 | 借鉴模式 | 融合位置 |
|------|----------|----------|
| KAG | IND# 逻辑推导前缀 | L1 RelationDeclaration.logical_type |
| KAG | 属性/关系二分法 | L1 EntityDeclaration.attributes + RelationDeclaration |
| m_flow | edge_text 语义文本 | Instance 层 EdgeInstance.edge_text |
| m_flow | index_fields 元数据 | L1 AttributeDef.index_fields |
| m_flow | canonical_name 实体归一 | 时序建模 same_entity_as |
| Cognee | identity_fields + UUID5 | Instance 层 EntityInstance.id |
| Cognee | source_* 五维溯源 | Instance 层 source_pipeline/content_hash |
| Cognee | feedback_weight | Instance 层 EntityInstance.feedback_weight |
| MemPalace | valid_from/valid_to 时态窗口 | 时序建模 |
| MemPalace | invalidate 软删除 | 时序建模 valid_to 设置 |

## 偏差矩阵

| 维度 | Overview 定义 | Baseline 实现 | 选择方向 | 原因 |
|------|---------------|---------------|----------|------|
| Instance 层 | 05-concepts.md 定义了 5 种实例 | 09-canonical-spec 无 Instance grammar | 新增 Instance 层 | 实例数据需要明确的 grammar |
| 互索引边 | 05-concepts.md 定义了 4 种边 | 09-canonical-spec 无互索引边 | 新增互索引边 grammar | Layer-R/S 桥接是核心架构 |
| 时序建模 | 05-concepts.md 定义了时序字段 | 09-canonical-spec 无 temporal 声明 | 新增 temporal + identity_fields | 金融场景必须支持时序 |
| 溯源链 | 05-concepts.md 定义了来源追踪 | 09-canonical-spec 无 source_* 字段 | 新增 source_pipeline/content_hash | 参考 Cognee 最佳实践 |
| 反馈权重 | 05-concepts.md 定义了 feedback_weight | 09-canonical-spec 无此字段 | 新增 feedback_weight | 支持反馈闭环 |
| 边语义 | 05-concepts.md 定义了 edge_text | 09-canonical-spec 无 edge_text | 新增 EdgeInstance.edge_text | 参考 m_flow 最佳实践 |

## 产出文件清单

| 文件 | 状态 | 核心内容 |
|------|------|----------|
| docs/02-design/schema/README.md | draft | Schema 设计总览 |
| docs/02-design/schema/L1-L4-declarations.md | draft | L1-L4 声明层 grammar |
| docs/02-design/schema/instance-layer.md | draft | Instance 层 grammar |
| docs/02-design/schema/mutual-index-edges.md | draft | 互索引边 grammar |
| docs/02-design/schema/temporal-modeling.md | draft | 时序建模 grammar |
| docs/02-design/schema/reference-alignment.md | draft | 参考项目对齐分析 |
