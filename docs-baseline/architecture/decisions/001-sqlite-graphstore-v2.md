# ADR-001: SQLiteGraphStore 并发与一致性改进

**状态**: Accepted
**日期**: 2026-04-07
**来源**: critical-review-response.md 问题1

---

## 背景问题

SQLiteGraphStore 存在以下并发缺陷：

| 缺陷 | 影响 | 根源 |
|------|------|------|
| 单一连接 | FastAPI async 冲突 | 未使用连接池 |
| 未启用WAL | 读写冲突 | SQLite默认DELETE模式 |
| 内存-磁盘状态分裂 | 数据不一致 | NetworkX与SQLite无同步机制 |

---

## 决策

### 1. 连接池实现

使用 `aiosqlite` 实现异步连接池，支持多并发连接：

```python
class ConnectionPool:
    def __init__(self, config: SQLiteGraphConfig):
        self.config = config
        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        self._max_size = config.pool_size
        self._initialized = False
        self._lock = asyncio.Lock()
```

### 2. WAL 模式启用

配置 SQLite 使用 WAL (Write-Ahead Logging) 模式替代默认的 DELETE 模式：

```python
# 启用WAL模式
await conn.execute(f"PRAGMA journal_mode = WAL")
await conn.execute(f"PRAGMA synchronous = NORMAL")
```

### 3. NetworkX 与 SQLite 状态同步

通过 SyncManager 保证内存图与磁盘状态一致性：

- 写操作：先写SQLite，成功后更新NetworkX
- 读操作：优先读NetworkX缓存，未命中查SQLite并回填
- 崩溃恢复：启动时从SQLite重建NetworkX

---

## 配置选项

```python
@dataclass
class SQLiteGraphConfig:
    db_path: str = "data/graph.db"
    wal_mode: bool = True
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    pool_size: int = 5
    checkpoint_interval: int = 1000
    cache_size: int = 10000
    consistency_level: ConsistencyLevel = ConsistencyLevel.SESSION
```

---

## 一致性保证

```
写入流程：
┌──────────┐    ┌──────────┐    ┌──────────┐
│  业务代码  │───▶│ SQLite   │───▶│ NetworkX │
└──────────┘    │ (WAL模式) │    │ (内存缓存) │
                └──────────┘    └──────────┘
                    │ commit       │ 回填
                    ▼              ▼
                磁盘持久化      查询加速

读取流程：
┌──────────┐    ┌──────────┐    ┌──────────┐
│  业务代码  │───▶│ NetworkX │───▶│ SQLite   │
└──────────┘    │ (优先)   │    │ (未命中)  │
                └──────────┘    └──────────┘
```

---

## 相关文档

- 问题2: FaissVectorStore 持久化 ([002-faiss-vectorstore-persistence.md](./002-faiss-vectorstore-persistence.md))
