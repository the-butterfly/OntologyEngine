# RFC-024: CognitiveNode 模型补齐 + 运行时 Bug 修复

> **状态**: draft
> **创建日期**: 2026-05-07
> **作者**: agent-memory-session
> **评审截止**: 待定
> **关联设计**: [memory-hierarchy.md](../../docs/02-design/agent-memory/memory-hierarchy.md) · [models.py](../../ontology_engine/engine/cognitive/models.py)
> **验收基准**: examples/agent_memory/ 全部 8 组

## 摘要

补齐 CognitiveNode 设计规范要求但实现缺失的 12 个字段；修复代码审查发现的运行时 Bug（correct_memory space_id 未定义、update_node 遗漏 confirmation_count、query_cognitive_nodes SELECT 缺列、entity_resolver._store 属性错误）；修复模块边界违规和静默吞异常问题。

## 背景与动机

### 运行时 Bug（P0 必须立即修复）

| # | Bug | 位置 | 影响 |
|---|-----|------|------|
| B1 | `correct_memory` 中 `space_id` 未定义变量 | memory_api.py L1281 | 调用 correct_memory 必抛 NameError |
| B2 | `update_node()` 遗漏 `confirmation_count` 参数 | repository.py L178-207 | 每次更新将 confirmation_count 重置为 0 |
| B3 | `query_cognitive_nodes()` SELECT 缺 `confirmation_count` 和 `attributes` 列 | kuzu_store.py L2051-2072 | 查询结果两字段始终返回默认值 |
| B4 | `entity_resolver._store` 应为 `_repo` | entity_resolver.py L374 | 必抛 AttributeError |

### CognitiveNode 缺失字段（P2 模型补齐）

| 字段 | 设计规范 | 当前状态 | 影响 |
|------|---------|---------|------|
| `strength` | DOUBLE DEFAULT 1.0 | 缺失（运行时计算） | 无法持久化强度，遗忘策略依赖运行时 |
| `entity_name` | STRING | 缺失 | 实体消歧 L1 无法精确匹配 |
| `entity_type` | STRING | 缺失 | Schema 对齐评分缺少维度 |
| `version` | INT64 DEFAULT 1 | 缺失 | OCC 并发控制无法实现 |
| `last_confirmed_at` | STRING | 缺失 | confirmation 因子无法正确计算 |
| `consolidation_reasoning` | STRING | 缺失 | 巩固过程不可解释 |
| `compiled_at` | STRING | 缺失 | 编译 staleness 无法判断 |
| `model_domain` | STRING | 缺失 | 建模对象权限治理无依据 |
| `source_trust_tier` | STRING | 缺失 | 来源可信度无法追踪 |
| `scope` | STRING | 缺失 | 作用域隔离无法实现 |
| `source_pipeline` | STRING | 缺失 | 来源管道无法追踪 |
| `source_content_hash` | STRING | 缺失 | 内容去重缺少快速路径 |

### 模块边界违规

| # | 违规 | 位置 | 修复 |
|---|------|------|------|
| V1 | API 层直接访问 `api._repo` | memory.py L335-578 | MemoryAPI 新增公共方法 |
| V2 | engine 层直接 `import sqlite3` | activity_log.py L14 | 迁移到 storage 层 |
| V3 | API 层直接导入 engine 内部模块 | memory.py L396-421 | MemoryAPI 新增 update_disposition |

## 设计方案

### D1: 运行时 Bug 修复

**B1**: `memory_api.py L1281`: `space_id=space_id` → `space_id=old_node.space_id`

**B2**: `repository.py L178-207`: 在 `upsert_cognitive_node` 调用中添加 `confirmation_count=node.confirmation_count`

**B3**: `kuzu_store.py L2051-2072`: SELECT 中添加 `n.confirmation_count AS confirmation_count, n.attributes AS attributes`

**B4**: `entity_resolver.py L374`: `self._store` → `self._repo`

### D2: CognitiveNode 字段补齐

```python
@dataclass
class CognitiveNode:
    # ... 现有字段 ...

    # 新增字段
    strength: float = 1.0
    entity_name: str = ""
    entity_type: str = ""
    version: int = 1
    last_confirmed_at: str = ""
    consolidation_reasoning: str = ""
    compiled_at: str = ""
    model_domain: str = ""
    source_trust_tier: str = ""
    scope: str = ""
    source_pipeline: str = ""
    source_content_hash: str = ""
```

**KuzuDB Schema 迁移**:

```sql
ALTER TABLE CognitiveNode ADD COLUMN strength DOUBLE DEFAULT 1.0;
ALTER TABLE CognitiveNode ADD COLUMN entity_name STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN entity_type STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN version INT64 DEFAULT 1;
ALTER TABLE CognitiveNode ADD COLUMN last_confirmed_at STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN consolidation_reasoning STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN compiled_at STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN model_domain STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN source_trust_tier STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN scope STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN source_pipeline STRING DEFAULT '';
ALTER TABLE CognitiveNode ADD COLUMN source_content_hash STRING DEFAULT '';
```

**字段使用场景**:

| 字段 | 写入时机 | 读取/使用 |
|------|---------|----------|
| strength | ForgettingEngine.apply_forgetting() | 遗忘策略判定 |
| entity_name | EntityResolver.resolve() | L1 精确匹配 |
| entity_type | ConsolidationEngine | Schema 对齐评分 |
| version | update_node() | OCC 并发控制 |
| last_confirmed_at | approve 操作 | confirmation 因子计算 |
| consolidation_reasoning | ConsolidationEngine | 审计追踪 |
| compiled_at | Compilation | staleness 判定 |
| model_domain | remember() | 建模对象权限 |
| source_trust_tier | remember() | 信任层级传播 |
| scope | remember() | 作用域隔离 |
| source_pipeline | remember() | 来源追踪 |
| source_content_hash | DeduplicationGate | 快速去重 |

### D3: 模块边界修复

**V1**: MemoryAPI 新增公共方法:
- `get_contradictions(space_id, severity=None, limit=50)`
- `get_corrections(space_id, node_id=None, limit=50)`
- `get_evidence(node_id)`
- `get_node_by_id(node_id)`

**V2**: ActivityLog SQLite 操作迁移到 `storage/local/activity_log_store.py`:
- `ActivityLogStore` 类实现 `storage/base.py` 接口
- `ActivityLogWriter` 通过接口访问

**V3**: MemoryAPI 新增 `update_disposition(space_id, profile_data)` 方法

### D4: 静默吞异常修复

| 文件 | 修复 |
|------|------|
| disposition_store.py `_load/_dump` | 添加 `logger.error` + 考虑抛出异常 |
| activity_log.py `_flush_batch` | 添加重试机制 + 错误计数器 |
| lifecycle.py `_enhance_self_links` | 添加 `logger.debug` |

## 验收标准

### 全组通用补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| BUG-1 | correct_memory 不抛 NameError | correct_memory 正常执行 |
| BUG-2 | update_node 保留 confirmation_count | 更新前后 confirmation_count 不变 |
| BUG-3 | query_cognitive_nodes 返回 confirmation_count | 查询结果 confirmation_count > 0 |
| BUG-4 | entity_resolver 不抛 AttributeError | L1/L2 策略切换正常 |
| MODEL-1 | CognitiveNode 12 个新字段可读写 | remember 后新字段正确持久化 |
| MODEL-2 | model_domain 权限治理 | 不同 domain 的记忆按权限隔离 |
| BOUNDARY-1 | API 层不直接访问 _repo | grep 无 `api._repo` 匹配 |

## 实施计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| Phase 1 | 运行时 Bug 修复 (D1) | 无 |
| Phase 2 | 静默吞异常修复 (D4) | Phase 1 |
| Phase 3 | 模块边界修复 (D3) | Phase 1 |
| Phase 4 | CognitiveNode 字段补齐 (D2) | Phase 1 |

## 风险

1. KuzuDB ALTER TABLE 可能需要重建索引
2. CognitiveNode 字段增加影响所有序列化/反序列化路径
3. 模块边界修复涉及 API 路由层重构，可能影响前端调用
