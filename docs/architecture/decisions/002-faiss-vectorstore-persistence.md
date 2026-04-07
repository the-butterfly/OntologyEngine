# ADR-002: FaissVectorStore 持久化与线程安全

**状态**: Accepted
**日期**: 2026-04-07
**来源**: critical-review-response.md 问题2

---

## 背景问题

FaissVectorStore 存在以下问题：

| 缺陷 | 影响 | 根源 |
|------|------|------|
| 多并发写无锁 | 索引损坏 | Faiss非线程安全 |
| 手动persist() | 崩溃丢数据 | 非自动持久化 |
| 无WAL机制 | 写入不可恢复 | 直接修改主索引 |

---

## 决策

### 1. 读写锁分离

使用 asyncio 信号量实现读写锁分离：

```python
class ThreadSafeFaissIndex:
    def __init__(self, config: FaissVectorConfig):
        self._read_lock = asyncio.Semaphore(config.max_concurrent_reads)
        self._write_lock = asyncio.Lock()
```

- 读操作：多读锁（允许多并发）
- 写操作：独占写锁

### 2. WAL (Write-Ahead Log) 实现

在向量数据写入主索引前，先记录到 WAL：

```python
class VectorWriteAheadLog:
    """
    格式：
    [操作类型:1byte][向量ID长度:4bytes][向量ID:nbytes][向量数据:dimension*4bytes]

    操作类型：
    0x01 = ADD
    0x02 = DELETE
    0x03 = UPDATE
    """
```

### 3. 自动持久化

后台任务定期自动持久化到磁盘：

```python
async def auto_persist_task(self):
    """后台自动持久化任务"""
    while True:
        await asyncio.sleep(self.config.auto_persist_interval)
        await self.persist()
```

---

## 配置选项

```python
@dataclass
class FaissVectorConfig:
    index_path: str = "data/vectors"
    dimension: int = 1536
    index_type: str = "IndexFlatIP"
    nlist: int = 100
    write_lock_timeout: float = 10.0
    max_concurrent_reads: int = 10
    wal_enabled: bool = True
    wal_flush_interval: int = 100
    auto_persist: bool = True
    auto_persist_interval: int = 300
    backup_count: int = 3
```

---

## 写入流程

```
业务代码 → WAL追加 → 索引更新 → 自动持久化(后台) → 清空WAL(成功时)
```

---

## 相关文档

- ADR-001: SQLiteGraphStore 并发改进 ([001-sqlite-graphstore-v2.md](./001-sqlite-graphstore-v2.md))
