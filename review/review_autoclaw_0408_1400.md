现在我对整个代码库有了全面的了解。让我给你一份详细的代码审查报告。

---

# OntologyEngine 代码审查报告

## 📊 项目概览

| 维度 | 评估 |
|------|------|
| 项目定位 | 面向 AI Agent 的知识图谱分析工具链 |
| 当前阶段 | MVP 实现早期（TODO.md 显示多个高优先级任务仍 Open）|
| 代码规模 | ~1771 行 Python，schema.yaml 30KB |
| 文档体系 | 完善（12+ 架构/设计文档）|

---

## ✅ 做得好的地方

### 1. 文档体系优秀
- ADR（Architecture Decision Records）清晰记录了关键决策
- `critical-review-response.md` 诚实承认了设计批评
- `consistency-check.md` 验证了文档间一致性
- `docs/development/` 提供了详细的开发指南

### 2. 分层架构设计合理
```
api/ → services/ → engine/ → storage/
```
边界清晰，依赖单向流动，符合良好设计原则。

### 3. Schema 设计完整（YAML 层面）
- KGML v3.0 schema 支持 9 个顶层模块：types、enums、concepts、metrics、rules 等
- 规则支持 `allOf`/`anyOf` 条件组合
- 支持优先级、维度作用域、派生计算

### 4. Pydantic 模型定义规范
- 使用 Pydantic v2（现代版本）
- 有 `SchemaValidationError`、`StorageError` 等自定义异常
- 有 `from __future__ import annotations` 保持兼容性

### 5. DuckDB 选型合理（针对分析场景）
- DuckDB 比 SQLite 更适合 OLAP 场景
- 向量存储配置已预留（`vector_config`）
- DuckDB 的列式存储对 JSON 友好

### 6. 表达式求值器（`evaluator.py`）有基本防护
- 使用正则而非直接 `eval()`
- 处理了 `None` 值比较
- 有布尔 literals 处理

### 7. 错误处理意识
- 有自定义异常类
- 验证失败有警告机制
- 实体查找返回 `None` 而非抛异常

### 8. 代码可读性
- 分行清晰
- 文档字符串完整
- 类型注解覆盖较好

---

## 🔴 严重问题

### 问题 1：DuckDB 是同步库，但被包在 async def 里

**位置**: `ontology_engine/storage/duckdb/store.py`

```python
class DuckDBStorage(StorageBackend):
    async def save_entity(self, entity: EntityInstance) -> str:
        if self._conn is None:
            raise StorageError("...")
        import json
        self._conn.execute(...)  # ← DuckDB.execute() 是同步阻塞的！
```

DuckDB 的 Python 绑定是**同步的**。把它包在 `async def` 里不会让它变成异步——它会**阻塞整个事件循环**。

**影响**: 在 FastAPI 中使用会严重拖累并发性能。

**建议**:
1. 使用 `asyncio.to_thread()` 包装同步调用
2. 或使用 `duckdb-ai` 等异步封装
3. 或切换到 `aiosqlite` + SQLite

---

### 问题 2：代码实现与文档严重不一致

| 文档说的 | 代码做的 |
|----------|----------|
| `tech-stack.md`: SQLite + NetworkX | 实际: DuckDB |
| `architecture.md`: SQLiteGraphStore | 实际: DuckDBStorage |
| `project-structure.md`: `local/sqlite_graph.py` | 实际: `storage/duckdb/store.py` |
| `project-structure.md`: `storage/local/` | 实际: `storage/duckdb/` |

`pyproject.toml`:
```toml
dependencies = [
    "pyyaml>=6.0",
    "duckdb>=0.9.0",  # ← DuckDB
    "pydantic>=2.0",
]
```

**没有任何地方提到 DuckDB！**

---

### 问题 3：表达式求值器有安全漏洞

**位置**: `ontology_engine/engine/rule/evaluator.py`

```python
def _resolve_fields(self, expr: str, context: dict[str, Any]) -> str:
    # ...
    RESERVED = frozenset([...])
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]*)*)\b'
    
    def replace_field(match):
        field_path = match.group(1)
        # ...
        value = self._get_nested(context, field_path)
        # ...
        return str(value)  # ← 直接拼接到表达式字符串中！
```

虽然有 RESERVED 列表，但 `replace_field` 返回的是**拼接后的完整表达式字符串**，然后进入 `_eval_comparison`。如果 context 中有一个 key 叫 `__import__` 或 `os`，可能会被利用。

**更安全的做法**: 使用 AST 白名单沙箱，完全不依赖字符串求值。

---

### 问题 4：没有真正的 API 层

```python
# ontology_engine/api/__init__.py
"""API layer."""  # ← 空的！

# ontology_engine/services/__init__.py
# 完全空
```

`OntologyEngine.__init__.py` 里的 `analyze()` 方法需要**手动调用**：
```python
result = await engine.analyze(entity_id="SUP_001", dimension="credit_assessment")
```

没有任何 HTTP 端点。

---

### 问题 5：`DuckDBStorage` 没有连接池

DuckDB 默认是单线程的。`__init__` 里：
```python
self._conn = None  # 只有一个连接
```

没有连接池，没有 WAL 模式配置（ADR-001 提到但没实现）。

---

### 问题 6：`RuleExecutor` 是半硬编码的

虽然规则从 YAML 加载，但**动作是硬编码的**：

```python
def _execute_action(self, action: str, ...):
    if action == "approve_eligibility":
        output["eligible"] = True
        context.computed_metrics["eligible"] = True
    elif action == "reject_eligibility":
        # ...
    elif action == "calculate_credit_score":
        # ...
```

**每加一个新 action就要改代码**。TODO-003 说要实现 Operator Registry，但还没做。

---

### 问题 7：DuckDB 作为主图存储不伦不类

DuckDB 擅长**分析查询**（列式存储、向量化执行），但这个项目把它当**图存储**用：

```python
# entities 表结构
CREATE TABLE entities (
    concept VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    data JSON NOT NULL,  # ← 整个实体存成一个 JSON
    PRIMARY KEY (concept, entity_id)
)
```

图查询（多跳遍历、路径搜索）用 JSON 存储效率极低。DuckDB 不是图数据库。

---

## 🟡 中等问题

### 问题 8：Schema 过于复杂

`schema.yaml` 有 **9 个顶层模块**：
```yaml
metadata, types, enums, concepts, metrics, rules, data_sources, vector_config, llm_config
```

一个 MVP 需要这么复杂的 schema 吗？`PROJECT_PHASE.md` 自己也承认"野心超出执行能力"。

---

### 问题 9：`InstanceLoader` 硬编码了关系类型

```python
id_fields = {
    "Supplier": "supplier_id",
    "CoreEnterprise": "enterprise_id",
    "Invoice": "invoice_no",
    "Contract": "contract_no",
    "GuaranteeRelation": "guarantor_id",
}

# 硬编码的关系
for rel_data in data.get("has_invoice", []):
    relations.append(RelationInstance(...))
for rel_data in data.get("supplies_to", []):
    # ...
```

每加一个新 Concept 或 Relation 要改代码。

---

### 问题 10：`_compute_entity_metrics` 方法过于复杂

`__init__.py` 里的这个方法有 **~120 行**，包含：
- 日期计算
- 发票遍历
- 合同遍历
- 担保链遍历
- 循环检测

应该拆成独立的 Metric 计算算子。

---

### 问题 11：DuckDB in-memory 默认不持久化

```python
storage = DuckDBStorage(":memory:")  # ← 数据不保存到磁盘！
```

如果不用 `DuckDBStorage("data/graph.db")`，数据重启后就丢了。

---

### 问题 12：`SchemaLoader.validate()` 只警告不报错

```python
def validate(self, schema: KGMLSchema) -> list[str]:
    issues = []
    # ...
    if issues:
        warnings.warn(f"Schema validation issues: {issues}")  # ← 只是警告
```

`from_config` 里也只是一条 warning，schema 有问题也继续运行。

---

### 问题 13：没有测试

```bash
$ find tests/ -name "test_*.py" 2>/dev/null
# 没有测试文件！
```

AGENTS.md 要求 80% 覆盖率，但完全没有测试。

---

### 问题 14：`project-structure.md` 描述的目录不存在

| 文档说 | 实际 |
|--------|------|
| `core/models/concept.py` | 不存在 |
| `core/models/entity.py` | 不存在 |
| `core/types/primitives.py` | 不存在 |
| `ingestion/` | 不存在 |
| `storage/local/` | 是 `storage/duckdb/` |

---

## 🟢 轻微问题

### 问题 15：datetime 在函数内导入

```python
async def _compute_entity_metrics(self, entity: dict) -> dict:
    from datetime import date, datetime, timedelta
```

应该在文件顶部导入。

### 问题 16：duckdb store 里重复 import json

```python
async def save_entity(self, ...):
    import json  # 每次调用都重新导入
```

应该在 `__init__` 或模块顶部导入一次。

### 问题 17：`RuleExecutor.execute_dimension` 里 `entity_type` 获取不可靠

```python
entity_type = entity_data.get("_concept", "")  # 依赖实体数据里有 _concept
```

如果加载时没设置 `data["_concept"] = concept`，这个就取不到。

---

## 📋 总结

| 类别 | 数量 |
|------|------|
| 🔴 严重问题 | 7 |
| 🟡 中等问题 | 7 |
| 🟢 轻微问题 | 3 |

### 核心矛盾

**文档说 SQLite + NetworkX，代码用 DuckDB** ——这是最大的不一致。

### 最需要修复的

1. **立即**: 修复 async/sync 混用问题（DuckDB 同步调用阻塞事件循环）
2. **立即**: 更新文档反映实际实现（DuckDB）
3. **高优**: 实现 Operator Registry 让规则动作可扩展
4. **高优**: 添加测试覆盖
5. **中优**: 拆分 `__init__.py` 里 120 行的 `_compute_entity_metrics`
6. **中优**: 完善 DuckDB 存储（连接池、WAL、持久化配置）

### 架构建议

如果坚持用 DuckDB：
- 考虑把 DuckDB 当**分析引擎**而不是图存储
- 图关系用 NetworkX 内存图 + DuckDB 做历史归档
- 或者直接换 aiosqlite + SQLite，后续切 Neo4j

目前的状态是：**文档和代码脱节，存储层选型存疑，核心引擎半成品**。建议先明确存储策略（DuckDB 还是 SQLite+NetworkX），再统一文档和实现。