# 知识摄入设计索引

> **status**: draft | **phase**: phase1+phase2 | **source_of_truth**: 本目录 | **last_verified**: 2026-05-25

本目录统一描述 OntologyEngine 的知识摄入（Ingestion）全链路设计，覆盖结构化与非结构化来源。

---

## 摄入全景

```
结构化来源                    非结构化来源
   │                              │
   │  (数据库表/CSV/API/代码)      │  (PDF/Markdown/网页/图片)
   ▼                              ▼
┌──────────────────────────────────────────┐
│         IngestionService                  │
│                                          │
│  ┌────────────┐    ┌──────────────────┐  │
│  │ 快速通道    │    │ 慢速通道          │  │
│  │ 同步写入    │───▶│ LLM 推理         │  │
│  │ 无 LLM     │    │ 后台处理         │  │
│  └─────┬──────┘    └────────┬─────────┘  │
│        │                    │             │
│        ▼                    ▼             │
│  ┌──────────────────────────────────┐    │
│  │ 矛盾检测 + 双轨治理               │    │
│  │ 企业治理(轨道A) / Agent自治(轨道B)│    │
│  └──────────────────────────────────┘    │
└──────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   Layer-S (KuzuDB)    Layer-R (ChromaDB)
   EntityInstance      KnowledgeFragment
   EdgeInstance        向量索引
```

---

## 子文档索引

| 文档 | 内容 | 阶段 |
|------|------|------|
| [IngestionService 双通道设计](../services/ingestion-service.md) | 快速/慢速通道、矛盾检测、Dataset 注册、Fragment 管理、双轨治理 | Phase 1 |
| [提取管线设计](../extraction-pipeline/README.md) | 三通道提取（AST + LLM + 去重）、增量缓存 | Phase 1 |
| [非结构化来源处理](unstructured-sources.md) | PDF/图片/网页/API 响应的摄入流程 | Phase 2 |

---

## 摄入管线总览（5 阶段）

详见 [`10-kb-process.md`](../../01-overview/10-kb-process.md) §2.1：

| 阶段 | 名称 | 关键操作 |
|------|------|---------|
| Stage 0 | 哈希校验 | SHA256 比对，仅处理变化文件 |
| Stage 1 | 智能分块 | QMD 算法，目标 900 tokens，AST 感知 |
| Stage 2 | 两通道提取 | Pass 1 AST 确定性提取 → Pass 2 LLM 语义提取 |
| Stage 3 | 消歧与对齐 | identity_fields + trigram + LLM 辅助 |
| Stage 4 | Schema 绑定 | schema_alignment_score 计算与分级 |
| Stage 5 | 写入与索引 | Layer-R ChromaDB + Layer-S KuzuDB + 互索引边 |

---

## 来源类型矩阵

| 来源类型 | 处理通道 | 分块策略 | 提取方式 | 存储目标 |
|---------|---------|---------|---------|---------|
| 数据库表/CSV | 快速通道 | 每行一个 Fragment | AST/结构化解析 | Layer-S EntityInstance |
| 代码文件 | 快速通道 → 慢速通道 | AST 感知分块 | tree-sitter + LLM | Layer-S + Layer-R |
| Markdown 文档 | 快速通道 → 慢速通道 | QMD 智能分块 | LLM 语义提取 | Layer-R Fragment + Layer-S Entity |
| PDF | 慢速通道 | 页/段落分块 | OCR + LLM | Layer-R Fragment |
| 图片 | 慢速通道 | 单图一个 Fragment | VLM 描述提取 | Layer-R Fragment |
| 网页 | 慢速通道 | 标题/段落分块 | DOM 解析 + LLM | Layer-R Fragment |
| API 响应 | 快速通道 | 每字段一个 Fragment | 结构化解析 | Layer-S EntityInstance |

---

## 与其他模块的关系

| 模块 | 关系 |
|------|------|
| [Schema](../schema/) | 提供 EntityDeclaration 作为提取模板 |
| [Storage](../storage/) | 摄入产物的持久化目标 |
| [Extraction Pipeline](../extraction-pipeline/) | 提取管线的具体实现 |
| [Query Engine](../query-engine/) | 摄入完成后支持检索消费 |
