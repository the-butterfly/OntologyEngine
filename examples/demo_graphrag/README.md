# GraphRAG Demo — 图+向量混合检索演示

基于 OntologyEngine × rag-skill 知识库的 **GraphRAG（Graph + Vector Hybrid Retrieval）** 快速演示项目。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (frontend.html)                 │
│          D3.js 知识图谱可视化 + 搜索交互界面                    │
└──────────────┬──────────────────────────────┬──────────────┘
               │ GET /api/graph              │ POST /api/query
               │ GET /api/domains            │ POST /api/search
               ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Backend (backend.py / FastAPI)                │
│                                                             │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│    │ Vector   │  │ Graph    │  │ Path    │  │ LLM     │  │
│    │ Search   │  │ Expansion│  │ BFS     │  │ Answer  │  │
│    │ (cosine) │  │ (co-occur)│  │ (entity)│  │Synth    │  │
│    └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────────┘  │
│         └──────────────┼─────────────┘                      │
│                        ▼                                    │
│                ⚖️ RRF Fusion                                 │
│           (Reciprocal Rank Fusion)                          │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                Data Layer (kb_data.json / .emb.json)         │
│                                                             │
│   1638 nodes · 8746 edges · 1487 chunks · 125 entities      │
│   4 domains: AI Knowledge · Financial Report Data           │
│              Safety Knowledge · E-commerce Data             │
└─────────────────────────────────────────────────────────────┘
```

## 混合检索策略

### 三通道并行检索

| 通道 | 方法 | 含义 |
|------|------|------|
| **V** (Vector) | 余弦相似度 top-K | 用户 query → embedding → 与所有 chunk 向量比较 → 返回语义最相似的 chunks |
| **G** (Graph) | 实体共现扩散 | 从 Vector 命中的 chunks 提取实体 → 沿 `mentioned_in` 边找到这些实体也出现的其他 chunks |
| **P** (Path) | 实体链 2-hop BFS | 从 query 中提取实体 → 沿 `entity→chunk→entity→chunk` 做两跳遍历 |

### RRF (Reciprocal Rank Fusion) 融合

```
score(c) = Σ 1/(k + rank_i(c)),  k=60
```

RRF 将三个通道的排序结果归一化融合。如果一个 chunk 被多个通道同时命中，它的总分显著高于单通道结果 → 多源交叉验证 → 高置信度。

## 图结构 (6 层关系)

当前知识图谱包含 **6 种边类型**，构建完整的实体关系网络：

```
domain ──belongs_to── document ──contains── chunk ──mentioned_in── entity
  │                                                                   │
  │  entity_belongs_to (直接连接实体→域)                               │
  └────────────────────────────────────────────────────────────────────┘
                                                                        │
entity ──related_to── entity (基于同 chunk 共现的语义关联)              │
                                                                        │
chunk ──references── chunk (通过共享实体的跨文档引用)                   │
                                                                        │
document ──related_to── document (共享实体类型产生的文档相似度)          │
```

### 边类型分布

| 边类型 | 数量 | 含义 |
|--------|------|------|
| `contains` | 1,487 | chunk 属于 document |
| `mentioned_in` | 1,788 | entity 在 chunk 中出现 |
| `references` | 4,745 | chunk 间共享实体的引用 |
| `related_to` | 579 | entity↔entity 共现关联 |
| `entity_belongs_to` | 125 | entity 直接连到 domain |
| `belongs_to` | 22 | document 属于 domain |

## 快速开始

### 1. 环境依赖

```bash
pip install fastapi uvicorn pydantic requests
pip install pymupdf openpyxl  # 可选，用于 PDF/XLSX 加载
```

后端服务：
- **Embedding API**：LMStudio 或其他 OpenAI 兼容接口（默认 `http://127.0.0.1:7852`）
- **LLM API**：OpenAI 兼容接口（默认 `http://localhost:9528`）

### 2. 加载知识库

```bash
cd /Volumes/Extension/Projects/CodeDev/OntologyEngine
python examples/demo_graphrag/loader.py
```

这会读取 rag-skill 知识库的全部 4 个域：
- 解析 14 个 PDF（AI Knowledge）→ 853 chunks
- 解析 3 个 .txt 财报（Financial Report Data）→ 602 chunks
- 解析 3 个 .md/.txt 安全文档（Safety Knowledge）→ 28 chunks
- 解析 4 个 .xlsx 电商数据（E-commerce Data）→ 4 chunks

**总计**：1,487 chunks, 125 entities, 8,746 edges。

### 3. 启动后端

```bash
python examples/demo_graphrag/backend.py
```

启动在 `http://localhost:8765`

### 4. 打开前端

```bash
open examples/demo_graphrag/frontend.html
```

### 5. 查询示例

| 查询 | 预期效果 |
|------|----------|
| "XSS攻击有哪些类型" | Vector 匹配语义 + Path 精确匹配实体 "XSS" |
| "三一重工营收是多少" | Vector 找到财报 chunks + Graph 扩散到相关财务指标 |
| "AI Agent 发展趋势" | Vector 从 AI Knowledge PDF 中找到相关内容 |
| "库存不足的商品" | Graph 扩散到 E-commerce Data 的 inventory 数据 |
| "什么是 CSRF" | Path 精确匹配 "CSRF" 实体，Vector 补充语义相关 |

## API 文档

### `GET /api/health`

服务状态。

```json
{"status":"ok","chunks":1487,"nodes":1638,"embeddings":1487}
```

### `GET /api/graph`

返回完整知识图谱（nodes + edges）。

### `GET /api/domains`

返回分域统计。

### `POST /api/search`

**请求**：
```json
{"query": "XSS攻击有哪些类型"}
```

**响应**：
```json
{
  "results": [{"chunk_id":"...","score":0.0328,"sources":["path","vector"],"domain":"Safety Knowledge",...}],
  "meta": {"vector_results":10,"graph_results":8,"path_results":5}
}
```

### `POST /api/query`

**请求**：
```json
{"query": "三一重工2025年营收是多少", "use_llm": true}
```

**响应**：
```json
{
  "answer": "根据财报数据，三一重工2025年Q3营业收入为... [来源: 1(V+P), 3(V)]",
  "evidence": [{"chunk_id":"...","domain":"Financial Report Data","sources":["vector","path"],...}],
  "meta": {"vector_results":10,"graph_results":8,"path_results":5}
}
```

## 数据文件

| 文件 | 大小 | 内容 |
|------|------|------|
| `kb_data.json` | ~4.8 MB | 全量结构化数据（nodes + edges + chunks 全文） |
| `kb_data.emb.json` | ~33 MB | 预计算向量（1487 chunks × 2560 dim） |
| `loader.py` | 源码 | 知识库加载、分块、实体抽取、建图、向量化 |
| `backend.py` | 源码 | FastAPI 后端服务 |
| `frontend.html` | 源码 | 前端可视化界面 |
| `report.html` | 源码 | 离线分析报告 |

## 技术细节

### 实体抽取

基于正则模式的域特定实体抽取。每域独立配置 pattern 列表：

- **AI Knowledge**: 大模型、LLM、RAG、Agent、Transformer、多模态、AIGC 等
- **Financial Report Data**: 营收、利润、每股收益、资产负债率、上市公司名称等
- **Safety Knowledge**: XSS、CSRF、CORS、CSP、同源策略、OWASP 等
- **E-commerce Data**: 库存、SKU、复购、区域、部门等

### 知识图谱构建阶段

```
Phase 1: Domain 节点             → 4 个顶级域
Phase 2: 文件遍历→分块→实体提取   → document/chunk/entity 节点 + belongs_to/contains/mentioned_in 边
Phase 3: 实体-实体共现边          → related_to（同 chunk 内实体对）
Phase 4: 实体-域直接边            → entity_belongs_to（跨层级连接）
Phase 5: 跨文档引用边              → references（共享实体的 chunk 间引用）
Phase 6: 文档相似度边              → related_to（文档间共享实体）
```

### 性能指标

| 指标 | 数值 |
|------|------|
| 知识库文件数 | 27（含 PDF/XLSX/TXT/MD） |
| 总文本量 | ~474K chars |
| 总节点数 | 1,638 |
| 总边数 | 8,746 |
| 实体数 | 125 |
| 向量维度 | 2,560 |
| 混合检索延迟 | ~15-30s（含 query embedding） |
