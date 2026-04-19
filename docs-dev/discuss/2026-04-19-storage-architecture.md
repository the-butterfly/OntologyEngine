# 存储架构决策讨论

> 日期：2026-04-19
> 作者：the-butterfly
> 状态：待确认

## 背景

基于对 m_flow、MemPalace、KAG、MAMGA 等外部系统的深度调研，结合用户业务场景分析，对 OntologyEngine 存储架构进行了重大更新。

## 已确认决策

### 1. 废弃 DuckDB 主存储

**废弃方案**：
- ~~DuckDB 作为 Entity/Edge 主存储~~
- ~~DuckDB 作为分析主引擎~~

**原因**：
- DuckDB 是分析引擎（OLAP），MVCC 写入代价高，不适合频繁更新的场景
- 高频更新 EntityInstance 字段（如 risk_level）导致版本膨胀
- 参考：m_flow 使用 Kuzu 做图存储，MemPalace 使用 SQLite 做时序

**新方案**：
- SQLite：事务 + 元数据
- KuzuDB：实体关系主存储
- ChromaDB/FAISS：向量检索
- SQLite + diskcache：指标缓存

### 2. Concepts 对齐方案

**采用方案 A1**：
- 废弃独立 Concept 层
- L2 `tag_based` + L3 `indicator` 承担标签功能
- 与 LLM-Wiki concepts/ 等效

**原因**：
- 本地知识库场景够用
- 未来需要跨域泛化时，做多 Space 知识融合即可

### 3. 存储职责分配

| 数据类型 | 存储引擎 |
|---------|---------|
| 事务 + 元数据 | SQLite |
| 实体关系 | KuzuDB |
| 向量检索 | ChromaDB（<100K）/ FAISS（>100K）|
| 指标缓存 | SQLite + diskcache |
| 图版本 | SQLite + Kuzu checkpoint |

## 待确认问题

### Q1：边向量存储位置

**问题**：Kuzu 和 Faiss 独立引擎，无法跨引擎 ACID 事务。边向量存在哪里？

**选项**：
- A) Kuzu 主存 + Faiss 索引双写（WAL 保证一致）
- B) 仅 Faiss（Kuzu 不存边向量属性）

**影响**：
- A) 边向量双重备份，一致性需 WAL 维护
- B) 简化架构，但边遍历时无法直接获取边向量

**推荐**：A（Kuzu 主存 + Faiss 索引双写）

---

### Q2：向量规模阈值

**问题**：ChromaDB 和 FAISS 的分界线是多少？

**选项**：
- A) 100K 向量
- B) 其他（请说明）

**参考**：
- MemPalace 使用 ChromaDB
- m_flow 统一使用 ChromaDB 接口
- FAISS 对 >100K 向量有 IVF+PQ 压缩优势

**推荐**：A（100K）

---

### Q3：本地与云端同步策略

**问题**：本地与云端数据同步方式？

**选项**：
- A) 手动触发 + 用户确认
- B) 自动 + 人工确认（矛盾时）

**推荐**：A（手动触发）

---

## 参考来源

- m_flow 适配器架构（FSCacheAdapter、GraphProvider、Kuzu adapter）
- MemPalace ChromaDB 实现
- KAG 存储分层设计
- MAMGA NetworkX 图接口
- DuckDB VSS 实验特性分析

## 相关文档

- `docs/01-overview/06-tech-stack.md` — 技术选型（已更新）
- `docs/01-overview/08-knowledge-retrieval.md` — 知识检索机制
