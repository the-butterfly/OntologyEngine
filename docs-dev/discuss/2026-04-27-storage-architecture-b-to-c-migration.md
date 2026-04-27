# 架构决策：存储层方案 B→C 渐进迁移

**日期**: 2026-04-27
**状态**: accepted
**决策者**: 项目 Owner

## 决策

采用**方案 B→C 渐进迁移**策略：

| 引擎 | 职责 | 当前状态 | 目标状态 |
|------|------|---------|---------|
| SQLite/PostgreSQL | 全量数据存储（实体、关系、指标、分类、规则、元数据） | ✅ 已实现 | 保留为主存储，可分库隔离 |
| KuzuDB/Neo4j | 关系存储（互索引边、逻辑边、图遍历加速） | ⚠️ 辅助查询 | 强化关系存储，与 SQLite 双写 |
| LanceDB | 向量存储（嵌入向量、语义检索） | ❌ 未实现 | 替代 ChromaDB，支持 >100K 规模 |

## 核心原则

1. **SQLite 为数据真相源**：所有实体/关系/指标/分类的完整数据集保存在 SQLite 中
2. **KuzuDB 为关系加速层**：存储互索引边、逻辑边，提供图遍历和路径查询加速
3. **LanceDB 为向量检索层**：替代 ChromaDB，支持大规模向量检索
4. **分库隔离**：SQLite 可按语义空间/Schema/Instances 分库，实现物理隔离
5. **双写协调**：SQLite ↔ KuzuDB 关系数据双写，通过 DualWriteCoordinator 保证最终一致性

## 迁移路径

### Phase 1（当前）：SQLite 主存储 + KuzuDB 辅助 + ChromaDB 向量
- 保持现有 SQLiteStorage 为主存储
- KuzuGraphStore 提供图遍历加速
- ChromaVectorStore 提供向量检索

### Phase 2：SQLite 分库 + KuzuDB 关系强化 + LanceDB 引入
- SQLite 按语义空间分库
- KuzuDB 写入互索引边和逻辑边
- LanceDB 替代 ChromaDB

### Phase 3：PostgreSQL 可选 + Neo4j 可选 + LanceDB 规模化
- PostgreSQL 替代 SQLite（可选，企业级场景）
- Neo4j 替代 KuzuDB（可选，大规模图场景）
- LanceDB 支持百万级向量

## 与原设计文档的偏差

| 设计文档定义 | 本决策 | 偏差原因 |
|-------------|--------|---------|
| KuzuDB 为实体主存储 | SQLite 为实体主存储 | SQLite 事务支持更好、实现更完整、迁移成本低 |
| ChromaDB 向量存储 | LanceDB 向量存储 | LanceDB 支持 >100K 规模、与 SQLite 同为本地文件 |
| GraphStore+VectorStore+MetaStore 三接口 | StorageBackend+扩展 四接口 | 保留现有实现，渐进扩展 |

## 需同步更新的文档

- [ ] docs/02-design/storage/README.md — 存储架构描述
- [ ] docs/02-design/storage/interfaces.md — 接口定义
- [ ] docs/02-design/storage/kuzudb-schema.md — KuzuDB 职责调整
- [ ] docs/02-design/storage/sqlite-tables.md — SQLite 分库策略
- [ ] docs/02-design/storage/chromadb-collections.md → lancedb-collections.md
- [ ] docs/01-overview/06-tech-stack.md — 技术选型
- [ ] docs/01-overview/04-modules.md — 存储职责矩阵
