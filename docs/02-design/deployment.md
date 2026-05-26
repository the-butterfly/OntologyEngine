# 部署指南

> **status**: draft | **phase**: phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-05-25 | **[待核对代码]**

---

## 目的

定义 OntologyEngine 的本地部署流程，包括环境准备、配置、启动和验证。

---

## 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| Python | 3.11+ | 3.12+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 2 GB（不含数据） | SSD 推荐 |
| 操作系统 | macOS / Linux / WSL2 | macOS / Linux |

### 依赖

| 依赖 | 用途 | 版本约束 |
|------|------|---------|
| Kuzu | 图数据库（Layer-S 存储） | 本地嵌入式，无需独立部署 |
| ChromaDB | 向量索引（Layer-R 存储） | 本地持久化，无需独立部署 |
| SQLite | 元数据/缓存/队列 | Python 内置，无额外依赖 |

> **本地优先原则**: OntologyEngine 设计为单机可运行，零外部依赖。所有存储引擎均为嵌入式。

---

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件

复制示例配置文件并编辑：

```bash
cp config.yaml.example config.yaml
```

关键配置项：

```yaml
# config.yaml
storage:
  mode: local                    # local | cloud | hybrid
  graph_backend: kuzu            # 本地图数据库
  vector_backend: chroma         # chroma | faiss
  cache_backend: diskcache       # diskcache | redis

data_dir: ./data                 # 数据目录（自动创建）
log_level: info                  # debug | info | warning | error

# Phase 2: LLM 配置（可选）
llm:
  provider: openai               # openai | anthropic | local
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}     # 从环境变量读取
```

### 3. 启动 API Server

```bash
uvicorn ontology_engine.api:app --host 0.0.0.0 --port 8000 --reload
```

验证：

```bash
curl http://localhost:8000/docs  # Swagger UI
curl http://localhost:8000/health  # 健康检查
```

### 4. 启动 MCP Server（Agent 接入）

```bash
python -m ontology_engine.mcp.server
```

或作为 Claude Desktop / Cursor / Windsurf 的 MCP 工具：

```json
// .mcp.json
{
  "mcpServers": {
    "ontology-engine": {
      "command": "python",
      "args": ["-m", "ontology_engine.mcp.server"]
    }
  }
}
```

---

## 数据目录结构

```
data/
├── kuzu/              # KuzuDB 图数据（自动创建）
├── chroma/            # ChromaDB 向量索引（自动创建）
├── sqlite.db          # SQLite 元数据 + 缓存 + 队列
├── uploads/           # 上传的原始文件
└── cache/             # 提取缓存（SHA256）
```

---

## 生产环境部署（Phase 2）

### 云存储模式

```yaml
storage:
  mode: cloud
  graph_backend: neo4j
  vector_backend: pgvector
  cache_backend: redis

neo4j:
  uri: bolt://neo4j-host:7687
  username: neo4j
  password: ${NEO4J_PASSWORD}

postgres:
  dsn: postgresql://user:pass@pg-host:5432/ontology
  pgvector_dsn: postgresql://user:pass@pg-host:5432/ontology_vectors
```

### Docker 部署（规划中）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ontology_engine/ ./ontology_engine/
COPY config.yaml .
EXPOSE 8000
CMD ["uvicorn", "ontology_engine.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 故障恢复

| 场景 | 恢复方式 |
|------|---------|
| 进程重启 | KuzuDB/ChromaDB/SQLite 均为持久化存储，自动恢复 |
| 向量索引不同步 | 读取 SQLite WAL → 同步 pending 记录到 ChromaDB |
| 缓存失效 | SHA256 缓存失效后自动重新提取，无数据丢失 |
| 队列中断 | SQLite 持久化队列保证断电恢复 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 存储架构 | [`docs/02-design/storage/`](../02-design/storage/) |
| MCP Server 实现 | `ontology_engine/mcp/server.py` |
| 配置文件示例 | `config.yaml.example` |
