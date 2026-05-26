# 深度对比分析：OntologyEngine × LLM Wiki × GBrain × Obsidian-Wiki

> **日期**: 2026-05-15 | **类型**: 深度调研对比 | **范围**: 知识工程范式对比 + 治理重构

---

## 一、知识工程范式全景对比

### 1.1 核心哲学对比

| 维度 | LLM Wiki (Karpathy) | GBrain (Garry Tan) | Obsidian-Wiki | **OntologyEngine** |
|------|--------------------|--------------------|---------------|-------------------|
| **核心理念** | "编译一次，持续更新" | Thin Harness, Fat Skills | Agent 无关 + Skill 驱动 | **Schema 编译 + 双引擎检索 + 四建模对象** |
| **知识形态** | 纯 Markdown 文件集合 | Markdown + SQLite 向量索引 | Markdown + Obsidian WikiLink | **CognitiveNode 统一 + Layer-R/S 双存储 + 类型化边** |
| **检索范式** | index.md + grep | 混合搜索 (Chunk→Page→分层) | index.md + wikilink 遍历 | **TEMPR 四路 + RRF 融合 + Bundle Search** |
| **规模上限** | ~100 来源/数百页面 | ~240 页富文本 (Benchmark) | 中小规模 | **设计为大规模，但当前实现~70%** |
| **可编程性** | 无 (纯思想文章) | Python + CLI | Markdown Skills | **Python engine + API + Schema DSL** |
| **持久化** | Git + Markdown | Markdown + SQLite + ChromaDB | Markdown + Obsidian | **KuzuDB(图) + ChromaDB(向量) + SQLite(元数据)** |
| **适用场景** | 个人知识管理 | 个人/小团队 PKM | 个人 PKM (Agent 驱动) | **企业级 Schema 驱动知识治理** |

### 1.2 三层架构对比

| 层级 | LLM Wiki | GBrain | Obsidian-Wiki | **OntologyEngine** |
|------|----------|--------|---------------|-------------------|
| **Layer 1: 原始资料** | Raw Sources (只读) | 文件系统输入 | 来源目录 + Delta 追踪 | **Ingestion Pipeline (AST + LLM + SHA256 三通道)** |
| **Layer 2: 知识本体** | Wiki 页面 (Markdown) | Markdown + 实体页面 | Wiki 页面 + wikilink | **CognitiveNode + EntityInstance + EdgeInstance (多态)** |
| **Layer 3: Schema/索引** | Schema 元指令文件 | links 表 + 图谱 + 向量索引 | .manifest.json + Skill 文件 | **Schema v2 (L1-L4 + Instance层 + 互索引边) + BASE_TYPE_WEIGHTS** |

### 1.3 GBrain "Thin Harness, Fat Skills" vs OE "Schema 驱动"

GBrain 的核心哲学 "Thin Harness, Fat Skills" 强调：
- Harness 尽量薄，只做路由和编排
- 所有知识/逻辑通过 Skill (Markdown) 表达
- 把"做什么"留给 LLM (潜在空间)，把"如何做"留给代码 (确定性)

**OE 对比**：
- OE 的 Schema 驱动设计本质上也是一种"Fat Knowledge"模式 — Schema 不仅定义数据结构，还嵌入提取规则、检索权重、互索引逻辑
- OE 的引擎层 (ConsolidationEngine / ReflectAgent / DeduplicationGate) 对应 GBrain 的确定性代码层
- OE 的 **四建模对象** (User/Task/World/Self Model) × **四认知层** 正交分类，比 GBrain 的实体-关系图更结构化

**差距**：
- OE 缺少 GBrain 的"潜在空间 vs 确定性"的显式划分哲学
- OE 的 DispositionProfile 七维权重体系比 GBrain 更精细，但缺乏类似 GBrain graph-query 的可遍历性 CLI

### 1.4 混合检索架构对比

| 特性 | GBrain | OE 当前设计 | OE 实现状态 |
|------|--------|------------|-----------|
| **向量粗筛** | ChromaDB 混合搜索 (BM25 + 向量) | ChromaDB 7 集合设计 ✅ 文档 | 代码实现中 |
| **整页加载** | get_page() 获取全量 Markdown | CognitiveNode 完整数据模型 ✅ 设计 | 存储层待实现 |
| **分层呈现** | 编译真相 > 时间线证据 | TEMPR 四路 + RRF 融合 ✅ 文档 | ~70% 完成 |
| **图谱加权** | back-link boost (+31.4pp) | Bundle Search Phase 2 投影 ✅ 设计 | 待实现 |
| **Chunk 策略** | ~2KB 语义块 | 未定义 chunk 粒度 | ⚠️ **缺失** |
| **Layered Feeding** | 优先最新综合摘要 | Layer-R/S 双路再融合 | ⚠️ 缺乏显式分层策略 |

**核心差距**: GBrain 在240页Benchmark上 P@5=49.1% (无图谱仅17.7%)。OE 需要建立自己的 recall Benchmark 来验证 TEMPR + RRF 的有效性。

---

## 二、D-7~D-10 存储架构决策验证

### 2.1 四联决策概览

| 决策 | 内容 | 状态 | 文档对齐度 | 代码对齐度 |
|------|------|------|-----------|-----------|
| **D-7** | CognitiveNode 覆盖全部存储层 | ✅ 已决策 | ⚠️ memory-hierarchy.md §3.3 仍有 ALIGNED_WITH | ❌ kuzudb-schema.md 仍有 EntityNode 表 |
| **D-8** | ChromaDB 主存储 + KuzuDB 轻量索引 | ✅ 已决策 | ⚠️ chromadb-collections.md 仍用 7 集合非单一 | ⚠️ 代码使用 ChromaDB 但架构未对齐 |
| **D-9** | 保留双引擎但重新划分职责 | ✅ 已决策 | ⚠️ storage/README.md 写入流程仍用 EntityNode | ❌ kuzu_store.py 有 CognitiveNode 但旧 Entity 未移除 |
| **D-10** | EntityNode 直接废弃，不设过渡期 | ✅ 已决策 | ❌ 3 处仍有 ALIGNED_WITH 引用 | ❌ 代码中 EntityNode 概念未清理 |

### 2.2 不一致文件清单 (需清理)

| 文件 | 违反决策 | 需修改内容 | 优先级 |
|------|---------|-----------|--------|
| `docs/02-design/storage/kuzudb-schema.md` §迁移策略 | D-10 | 删除 Phase 1→Phase 2 过渡方案，删除 EntityNode 表 | **P0** |
| `docs/02-design/storage/kuzudb-schema.md` §ALIGNED_WITH 边 | D-10 | 删除 ALIGNED_WITH 边表定义 | **P0** |
| `docs/02-design/storage/README.md` §写入流程 | D-9/D-10 | 写入流程 EntityNode 改为 CognitiveNode | **P1** |
| `docs/02-design/agent-memory/memory-hierarchy.md` §3.3 | D-10 | 删除 Phase 1 过渡方案 (第 380-396 行) | **P0** |
| `docs/02-design/agent-memory/memory-hierarchy.md` §7.2 | D-10 | 删除 ALIGNED_WITH 边 (第 669 行) | **P1** |
| `docs/02-design/storage/chromadb-collections.md` §集合总览 | D-8 | 增加 cognitive_node 统一集合设计 | **P1** |

### 2.3 代码文件清理清单

| 文件 | 当前状态 | 需修改 |
|------|---------|--------|
| `ontology_engine/engine/cognitive/models.py` | 有 CognitiveNode 模型 | 确认无 EntityNode 残留 |
| `ontology_engine/storage/graph/kuzu_store.py` | 有 CognitiveNode 写入 | 确认旧 EntityNode 路径已移除 |
| `ontology_engine/engine/cognitive/rrf_types.py` | BASE_TYPE_WEIGHTS 有 12 种 | 需精简为 10 种 (移 commitment/constraint/self_experience/task_state，改为 sub_type) |
| `ontology_engine/engine/cognitive/memory_api.py` | 引用 BASE_TYPE_WEIGHTS | 对齐 10 种 |

---

## 三、P0 问题更新与已解决标记

### 3.1 已解决 (由 D-7~D-10 闭合)

| 原编号 | 原问题 | 解决决策 | 状态 |
|--------|-------|---------|------|
| P0-5 | storage/ 写入流程使用 EntityNode | D-9/D-10 ChromaDB 主存储 + KuzuDB 轻量索引 | ✅ 已解决 |
| P0-6 | memory-hierarchy.md §3.3 ALIGNED_WITH 过渡方案 | D-10 直接废弃，不设过渡期 | ✅ 已解决 |
| §3.1 深层矛盾 | CognitiveNode 逻辑 vs 物理统一不明确 | D-8 ChromaDB 主存储 + KuzuDB 轻量图索引 | ✅ 已解决 |
| S-2 | DEFINED_IN 不支持 MetricDeclaration | 随 D-8/D-9 重写 kuzudb-schema | ✅ 已解决 |

### 3.2 新增 P0 项

| # | 问题 | 文件 | 说明 | 优先级 |
|---|------|------|------|--------|
| **P0-7** | kuzudb-schema.md 仍含 EntityNode 表和 ALIGNED_WITH 过渡方案 | `storage/kuzudb-schema.md` | D-10 决策后未同步更新，新读者会被 Phase 1 方案误导 | **P0** |
| **P0-8** | memory-hierarchy.md BASE_TYPE_WEIGHTS 含 4 种已降级类型 (共12 非 10) | `memory-hierarchy.md` §4.2 | 旧 12 类型影响检索权重计算，与 D-1 精简方案矛盾 | **P0** |
| P0-9 | chromadb-collections.md 7 集合与 D-8 单 cognitive_node 集合矛盾 | `storage/chromadb-collections.md` | 需增加 cognitive_node 统一集合方案说明 | P0 (设计) |

### 3.3 剩余 P0 列表

| # | 问题 | 状态 | 工作量 |
|---|------|------|--------|
| P0-1 | 10-kb-process.md §2.3 内容重复 | ⏳ 待修复 | 低 (删段落) |
| P0-2 | 交叉引用断裂 — lencx 批判文件缺失 | ⏳ 待修复 | 低 (创建占位) |
| P0-3 | STATUS.md agent-memory 状态不准确 | ⏳ 待修复 | 低 (改标记) |
| P0-4 | agent-memory 文档自身状态 vs STATUS.md 不一致 | ⏳ 待修复 | 中 (同步多处) |
| P0-5 (old) | 三套层体系对照表融入正式文档 | ✅ 设计已闭合 | 零设计量 |
| P0-6 (old) | vision.md 超范围内容迁移 | ⏳ 待修复 | 中 (移~350行) |
| **P0-7** | kuzudb-schema.md EntityNode 表未清理 (D-10) | ❌ 未开始 | 中 (删表+过渡方案) |
| **P0-8** | BASE_TYPE_WEIGHTS 12 种旧类型 (D-1 未对齐) | ❌ 未开始 | 低 (删4个键) |

---

## 四、OS 能力边界与 LLM Wiki 对标

### 4.1 OE vs LLM Wiki 三操作对比

| 操作 | LLM Wiki | OE 等价设计 | OE 实现度 |
|------|----------|------------|---------|
| **Ingest (摄入)** | LLM 读源→讨论→写 summary→更新 index→更新关联页 10-15 个 | Ingestion Pipeline (AST+LLM+SHA256) + ConsolidationEngine | ~70% (QUL 后置处理等缺失) |
| **Query (查询)** | 读 index→定位页面→综合答案→可归档为新页面 | TEMPR 四路 + Layer-R/S + RRF 融合 | ~65% (分层喂养未实现) |
| **Lint (维护)** | 矛盾检测/过时清理/孤儿页面/交叉引用补全 | ReflectAgent + ContradictionDetection + ForgettingEngine | ~40% (核心引擎设计完整但实现滞后) |

### 4.2 OE 独有优势 (LLM Wiki/GBrain 不具备)

| 优势 | 说明 | 对标状态 |
|------|------|---------|
| **Schema 驱动的知识编译** | Schema v2 不仅是数据结构，更是提取模板、检索骨架、推理导航 | LLM Wiki/GBrain 无等价物 |
| **双引擎存储范式分离** | Layer-R (向量优先) + Layer-S (图优先) 职责分离 | 业界均用单引擎 |
| **四建模对象正交分类** | User/Task/World/Self × 四认知层 | Obsidian-Wiki 仅有实体-概念分类 |
| **类型化边体系 (互索引四边)** | extracted_from/supported_by/defined_in/trace_to + 6 种认知边 | GBrain 有 links 表但关系类型更少 |
| **治理优先理念** | 双轨治理、权限、策略性遗忘、矛盾检测前移 | 业界治理成熟度偏低 |

### 4.3 OE 与文章核心论点的映射

文章核心论点："Skillify — 渐进式披露的知识形态"

OE 的对应设计：
- **Skill = CognitiveNode**：OE 的 CognitiveNode 统一了"知识碎片→实体→高层摘要"的整个知识形态谱系
- **渐进式披露 = TEMPR 分层路由**：QueryUnderstandingLayer 根据任务约束动态决定检索深度和广度
- **增量编译 = ConsolidationEngine**：fragment → observation → entity → mental_model 的渐进式升级路径
- **持久化记忆 = 双引擎存储**：ChromaDB 主存储 + KuzuDB 图索引

文章结论："混合架构是最佳实践"
- OE 的 TEMPR 四路 + Layer-R/S 双路 + RRF 融合正是在实践混合架构
- 但 OE 缺少对"什么时候用 RAG (向量) vs 什么时候用图遍历"的显式路由策略文档
- 建议在 query-understanding-layer.md 中补充路由决策树

---

## 五、具体重构计划

### 5.1 文档清理 (立即执行)

| # | 操作 | 文件 | 工作量 |
|---|------|------|--------|
| R-1 | 删除 memory-hierarchy.md §3.3 Phase 1 过渡方案 (L380-396) | `memory-hierarchy.md` | 5 min |
| R-2 | 删除 memory-hierarchy.md §7.2 ALIGNED_WITH 边 (L669) | `memory-hierarchy.md` | 1 min |
| R-3 | 精简 BASE_TYPE_WEIGHTS 为 10 种 (删 commitment/constraint/self_experience/task_state) | `memory-hierarchy.md` §4.2 | 5 min |
| R-4 | 更新 memory-hierarchy.md 升级路径 (增加 relation/metrics/rule) | `memory-hierarchy.md` §5.1 | 10 min |
| R-5 | 删除 kuzudb-schema.md EntityNode 过渡方案 + ALIGNED_WITH 边 | `storage/kuzudb-schema.md` | 15 min |
| R-6 | 更新 storage/README.md 写入流程 EntityNode→CognitiveNode | `storage/README.md` | 10 min |
| R-7 | ROADMAP.md Phase 5 状态改为 "⚠️ 发现问题待修复" | `ROADMAP.md` | 1 min |
| R-8 | 更新 STATUS.md docs-dev/discuss/ 计数 (当前 30 条，已到阈值) | `STATUS.md` | 2 min |
| R-9 | 同步 agent-memory/README.md 与 STATUS.md 状态 | `agent-memory/README.md` | 5 min |

### 5.2 代码清理 (短期执行)

| # | 操作 | 文件 | 风险 |
|---|------|------|------|
| R-10 | rrf_types.py BASE_TYPE_WEIGHTS 精简为 10 种 | `rrf_types.py` | 中 (影响权重计算) |
| R-11 | 检查 kuzu_store.py 中 EntityNode 引用 | `kuzu_store.py` | 中 |
| R-12 | 检查 models.py 中 EntityNode 模型残留 | `models.py` | 低 |
| R-13 | 删除 10-kb-process.md §2.3 重复段落 (L236-287) | `10-kb-process.md` | 低 |

### 5.3 需进一步设计的项

| # | 项 | 原因 | 截止 |
|---|-----|------|------|
| R-14 | chromadb-collections.md 增加 cognitive_node 统一集合设计 | D-8 决策要求 ChromaDB 作为主存储 | Phase 7 |
| R-15 | BASE_TYPE_WEIGHTS sub_type 继承权重决策 | D-1 将 4 种类型降级为 sub_type | Phase 2c |
| R-16 | OE recall Benchmark 建立 | GBrain 有 P@5/R@5 基准 | Phase 6d |

---

## 六、总结

**核心发现**：
1. OE 的设计思想与 LLM Wiki/GBrain 高度一致（编译型知识、渐进式披露、混合检索），但 OE 的 Schema 驱动和双引擎设计使其在结构化程度上远超前述方案
2. D-7~D-10 决策已收敛，但文档和代码有 6+ 处未同步更新（主要是 EntityNode 残留和过渡方案）
3. BASE_TYPE_WEIGHTS 不一致是文档-代码脱节的典型案例
4. GBrain 的 back-link boost 机制值得 OE 借鉴（当前 OE 缺少边权重对检索排名的显式贡献公式）

**立即行动**：
- 优先清理 P0 级文档不一致（R-1~R-7）
- 其次对齐 BASE_TYPE_WEIGHTS（R-3, R-10）
- 建立 OE recall Benchmark（R-16）以量化验证 TEMPR + RRF 的有效性

---

*本分析基于 OntologyEngine 项目文档体系 (2026-05-15) 与文章《深度解析LLM Wiki / Obsidian-Wiki / GBrain》(飞樰, 2026) 的对比研究*
