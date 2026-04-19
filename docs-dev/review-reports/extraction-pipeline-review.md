# 提取管线设计审视报告

> **审视日期**: 2026-04-19
> **审视范围**: docs/02-design/extraction-pipeline/ 全部文档
> **审视流程**: Overview 对齐 → Baseline 审视 → 参考项目对齐 → 偏差标注 → 重写

## 审视结论

提取管线设计审视已完成，产出了 5 份设计文档，覆盖三通道提取架构、AST 确定性提取、LLM 语义提取、增量缓存、去重策略与互索引边创建。所有设计严格对齐 Schema v2 Instance 层和互索引边 Grammar。

## Overview 对齐结果

| Overview 概念 | 提取管线文档对齐状态 | 备注 |
|---------------|---------------------|------|
| ExtractionPipeline (L0 核心层) | ✅ 完全对齐 | 三通道提取管线架构 |
| Layer-R KnowledgeFragment | ✅ 完全对齐 | 文件分片产出 KnowledgeFragment |
| Layer-S EntityInstance / EdgeInstance | ✅ 完全对齐 | AST + LLM 提取产出 Instance 层数据结构 |
| 互索引边 EXTRACTED_FROM | ✅ 完全对齐 | Pass 1 + Pass 3 创建 |
| 互索引边 SUPPORTED_BY | ✅ 完全对齐 | Pass 2 LLM 提取时创建 |
| 置信度标签体系 | ✅ 完全对齐 | EXTRACTED / INFERRED / AMBIGUOUS 三级 |
| 增量缓存 | ✅ 完全对齐 | SHA256 + 语义缓存 + 推理检查点 |
| Cognee 对齐 | ✅ 完全对齐 | identity_fields + UUID5 + DataPoint 溯源 |
| Graphify 对齐 | ✅ 完全对齐 | AST 提取 + SHA256 缓存 + validate_extraction |
| MemPalace 对齐 | ✅ 完全对齐 | chunk_text 分片策略 |

## Baseline 审视结果

| Baseline 来源 | 提取内容 | 偏差处理 |
|---------------|----------|----------|
| 04-modules.md ExtractionPipeline 定义 | L0 核心层模块职责 | 扩展为三通道架构，增加 Pass 3 去重 |
| 05-concepts.md 置信度体系 | EXTRACTED/INFERRED/AMBIGUOUS 标签 | 细化数值范围和后续动作 |
| 05-concepts.md 互索引 | 四种互索引边 | 提取管线只创建 EXTRACTED_FROM 和 SUPPORTED_BY |
| instance-layer.md | EntityInstance / EdgeInstance / KnowledgeFragment | 所有提取产出严格对齐 |
| mutual-index-edges.md | EXTRACTED_FROM / SUPPORTED_BY 边字段 | 提取时同步创建，字段完全对齐 |

## 参考项目对齐结果

| 项目 | 借鉴模式 | 融合位置 |
|------|----------|----------|
| **Graphify** | LanguageConfig 驱动的 AST 提取 | ast-extraction.md: tree-sitter + LanguageConfig |
| **Graphify** | _make_id 稳定节点 ID | 改为 UUID5 基于 identity_fields |
| **Graphify** | SHA256 + relative_path 缓存键 | incremental-cache.md: 完全复用 |
| **Graphify** | _body_content Markdown body-only 哈希 | incremental-cache.md: 完全复用 |
| **Graphify** | check_semantic_cache / save_semantic_cache | incremental-cache.md: 扩展为三层缓存 |
| **Graphify** | validate_extraction 强制 schema 验证 | dedup-strategy.md: Pass 3 验证步骤 |
| **Graphify** | VALID_CONFIDENCES 三级标签 | llm-extraction.md: 复用并增加数值范围 |
| **Graphify** | build 合并多提取结果 | dedup-strategy.md: 改为显式合并策略 |
| **Graphify** | save_cached 原子写入 (tmp → rename) | incremental-cache.md: 完全复用 |
| **Cognee** | Cognify 6 步管线 | llm-extraction.md: 对齐 6 步流程 |
| **Cognee** | identity_fields + UUID5 确定性 ID | dedup-strategy.md: 实体去重核心机制 |
| **Cognee** | DataPoint.source_pipeline / source_content_hash | Instance 层溯源字段对齐 |
| **Cognee** | deduplicate_nodes_and_edges | dedup-strategy.md: 扩展为三层去重 |
| **Cognee** | Pipeline Task 链式执行 + Drop 信号 | README.md: 管线编排参考 |
| **Cognee** | feedback_weight 流式更新 | Instance 层 feedback_weight 对齐 |
| **MemPalace** | chunk_text 800 字符 + 100 overlap | ast-extraction.md: Markdown 分片策略 |
| **MemPalace** | detect_room 文件路由 | ast-extraction.md: domain_id 语义空间分配 |
| **MemPalace** | file_already_mined 增量检查 | incremental-cache.md: 增量判断参考 |

## 偏差标注

| # | 偏差 | 说明 | 处理 |
|---|------|------|------|
| 1 | Graphify _make_id → UUID5 | Graphify 使用正则清洗生成 ID，OntologyEngine 改用 UUID5 | UUID5 支持跨管道幂等，更可靠 |
| 2 | Graphify build 幂等覆盖 → 显式合并 | Graphify NetworkX add_node 后者覆盖前者 | 改为显式合并策略，保留最高置信度 |
| 3 | Cognee 简单 ID 去重 → 三层去重 | Cognee deduplicate 只按 ID 去重 | 扩展为文件内 + 跨文件 + 边去重三层 |
| 4 | MemPalace 无 LLM 提取 → 增加 LLM 通道 | MemPalace 只做原文存储 | OntologyEngine 增加 Pass 2 LLM 语义提取 |
| 5 | Graphify 无互索引边 → EXTRACTED_FROM / SUPPORTED_BY | Graphify 只有 nodes + edges | 增加互索引边创建，对齐 Instance 层 |
| 6 | 04-modules.md 未提及 Pass 3 → 增加去重通道 | Overview 只描述提取，未提及去重 | 增加去重与互索引边创建作为独立通道 |

## 设计决策汇总

| # | 决策 | 理由 | 影响范围 |
|---|------|------|----------|
| D-EP-1 | 三通道分离 | AST 零成本先行，LLM 只做补充 | 管线架构 |
| D-EP-2 | SHA256 增量缓存 | 避免重复 LLM 调用 | 增量处理 |
| D-EP-3 | UUID5 确定性 ID | 跨管道幂等写入 | 实体去重 |
| D-EP-4 | EXTRACTED_FROM 边在提取时创建 | 溯源链完整性 | 互索引边 |
| D-EP-5 | 置信度标签体系 | 统一语义解读 | 质量管理 |
| D-EP-6 | Markdown body-only 哈希 | 避免元数据变更使缓存失效 | 增量缓存 |
| D-EP-7 | AST/语义缓存分离 | 生命周期不同 | 缓存架构 |
| D-EP-8 | 去重集中 Pass 3 | 避免分散逻辑 | 去重策略 |
| D-AST-1 | tree-sitter AST 提取 | 精确解析嵌套结构 | 代码提取 |
| D-AST-2 | LanguageConfig 驱动 | 新语言只需添加配置 | 可扩展性 |
| D-LLM-1 | LLM 只做 AST 做不到的 | 控制成本 | LLM 提取范围 |
| D-LLM-2 | 仅处理增量文件 | 降低 token 消耗 | 增量处理 |
| D-LLM-3 | assigned_by="llm" 区分规则归类 | 确定性 vs 推断性 | 分类标注 |
| D-LLM-4 | AMBIGUOUS 必须人工审查 | 防止污染知识图谱 | 质量管理 |
| D-CACHE-1 | SHA256 而非 MD5 | 碰撞概率更低 | 缓存键 |
| D-CACHE-5 | 原子写入 | 防止崩溃损坏 | 缓存写入 |
| D-DEDUP-1 | UUID5 去重 | 天然幂等 | 实体去重 |
| D-DEDUP-2 | AST 优先于 LLM | 确定性优先 | 合并策略 |
| D-DEDUP-3 | 双向边合并 | 减少冗余 | 边去重 |

## 产出文档清单

| 文档 | 状态 | 核心内容 |
|------|------|----------|
| [README.md](../../docs/02-design/extraction-pipeline/README.md) | draft | 三通道提取管线架构总览 |
| [ast-extraction.md](../../docs/02-design/extraction-pipeline/ast-extraction.md) | draft | Pass 1 AST 确定性提取 |
| [llm-extraction.md](../../docs/02-design/extraction-pipeline/llm-extraction.md) | draft | Pass 2 LLM 语义提取 |
| [incremental-cache.md](../../docs/02-design/extraction-pipeline/incremental-cache.md) | draft | SHA256 缓存与增量处理 |
| [dedup-strategy.md](../../docs/02-design/extraction-pipeline/dedup-strategy.md) | draft | 去重策略与互索引边创建 |

## 待后续设计覆盖的内容

| 主题 | 说明 | 建议位置 |
|------|------|----------|
| DEFINED_IN 边创建 | 规则/指标定义来源的互索引边 | 服务层设计（SchemaService / AnalysisService） |
| TRACE_TO 边创建 | 推理步骤到碎片的互索引边 | 引擎层设计（RuleEngine 执行快照） |
| LLM Provider 抽象 | 不同 LLM 提供商的适配 | 基础设施层设计 |
| 并行提取 | 多文件并行 AST/LLM 提取 | 管线编排优化 |
| 提取质量度量 | 提取准确率/召回率/矛盾率指标 | 可观测性设计 |
