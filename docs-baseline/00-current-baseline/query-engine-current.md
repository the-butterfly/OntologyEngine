# Query Engine（当前实现）

> **模块**: ontology_engine/services/query_service.py
> **状态**: accepted
> **Phase**: phase1
> **Last Verified**: 2026-04-14
> **verified_against**: ontology_engine/services/query_service.py

## 概述

QueryService 是 Phase 1 的查询能力实现，基于 DuckDB 提供结构化查询和受限图遍历。

## 方法签名

### pattern_match

```python
async def pattern_match(
    self,
    filters: dict,
    limit: int = 100
) -> list[Entity]
```
- **能力**: DuckDB SQL WHERE 条件过滤
- **限制**: 仅支持精确匹配和简单比较运算符

### graph_traverse

```python
async def graph_traverse(
    self,
    entity_id: str,
    relation_types: list[str] | None,
    depth: int,
    direction: str = "outgoing"
) -> list[Entity]
```
- **能力**: DuckDB BFS 图遍历
- **限制**: `depth > 2` 时抛 `DepthLimitExceeded` 异常
- **方向**: outgoing / incoming / undirected

### find_path

```python
async def find_path(
    self,
    source_id: str,
    target_id: str,
    max_depth: int = 3,
    relation_types: list[str] | None = None
) -> list[list[str]]
```
- **能力**: DuckDB DFS 路径查询
- **限制**: `max_depth > 3` 抛异常；硬编码 `has_invoice` 关系过滤
- **返回**: 路径列表，每条路径为实体 ID 序列

### trace_rule

```python
async def trace_rule(
    self,
    entity_id: str,
    rule_id: str | None = None,
    limit: int = 100
) -> list[ExecutionRecord]
```
- **能力**: 直接 SQL 查询 `rule_execution_log` 表
- **参数**: rule_id 为空时返回该实体的所有执行记录

## 向量搜索

**当前未实现**。Faiss 未集成，不支持语义相似度检索。

## 与 Phase 2 目标的差距

见 [`docs/05-schema-v2/query-engine-target.md`](../05-schema-v2/query-engine-target.md)
