# RFC-002: 存储策略

**Status**: ✅ Adopted
**Date**: 2026-04-08
**Author**: OntologyEngine Team

## 问题

MVP 需选择一种存储方案，满足：
1. 单机可运行，零外部依赖
2. 支持图查询 + 向量检索 + 分析查询
3. 百万级节点性能可接受

## 方案对比

| 维度 | SQLite | DuckDB | NetworkX(纯内存) |
|------|--------|--------|------------------|
| 依赖 | 0 | 0 | 0 |
| 图算法 | ❌ | ❌ | ✅ |
| 分析查询 | 弱 | 强 | 弱 |
| 持久化 | ✅ | ✅ | ❌ |
| 嵌入模式 | 单文件 | 单文件 | - |

## 决策

**DuckDB + NetworkX(按需)**

```
实体/关系 ──▶ DuckDB (持久化)
图算法   ──▶ NetworkX (内存，按需加载)
向量索引 ──▶ Faiss (本地文件)
```

## 技术细节

### DuckDB 表结构

```sql
-- 实体
CREATE TABLE entities (
    id VARCHAR PRIMARY KEY,
    concept_type VARCHAR,
    attributes JSON,
    created_at TIMESTAMP
);

-- 关系
CREATE TABLE edges (
    id VARCHAR PRIMARY KEY,
    from_id VARCHAR REFERENCES entities(id),
    to_id VARCHAR REFERENCES entities(id),
    relation_type VARCHAR,
    attributes JSON
);
```

### NetworkX 加载策略

```python
# 按需加载子图
def load_subgraph(center_id: str, depth: int = 2):
    # 从 DuckDB 查询节点和边
    # 构建 NetworkX DiGraph
    # 执行图算法
```

## 未来扩展

```yaml
# 配置切换
storage:
  type: neo4j  # local | neo4j
  neo4j:
    uri: bolt://localhost:7687
```
