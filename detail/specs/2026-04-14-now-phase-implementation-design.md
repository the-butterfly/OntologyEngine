# Now 阶段实施计划设计

> **状态**: approved
> **创建日期**: 2026-04-14
> **来源**: docs/TODO.md + docs/03-rfc/RFC-010 + 用户确认

## 背景

本次 session 目标：清理 TODO 中与实际代码不符的状态，补充缺失的验收测试，实现 MCP P1 工具，建立前端 Playwright 套件。

## 范围

### 本次包含

| 任务 | 类型 | 备注 |
|------|------|------|
| T1: docs/TODO.md 清理 | 文档 | 移除已完成的虚假待做项 |
| T2: 全链路 API 集成测试 | 测试 | dataset / incremental / category |
| T3: MCP P1 5 工具实现 | 实现 | 测试先行，mcp/ 目录新建 |
| T4: Playwright 前端测试套件 | 测试 | 全新建，webServer 配置 |

### 本次不包含

- RuleExecutor DAG (RFC-011) / kuzu (RFC-012)
- LLMJudgeOperator LLM 接入
- MCP P2/P3 工具
- category 路由全量 CRUD（当前仅部分实现，T2 集成测试验证覆盖范围）

## T1: docs/TODO.md 清理

### 行动

1. `docs/TODO.md` Now 区：将 **"DuckDB 新增 API 路由注册"** 从 P2 移至已完成归档
   - 理由：`server.py:374-376` 三条路由已注册并完整实现，`tests/unit/services/test_dataset_and_incremental.py` 13 个单元测试覆盖

2. `docs/TODO.md` Now 区：更新 **"docs/09-examples/supply_chain_finance.md 重构"** 备注
   - 当前状态：文档顶部已有完整 `[已过期入口]` 标注 + 不符点清单，无需重写
   - 备注改为：`✅ 已标注 deprecated，文档本身已完整，无需重写`

3. `docs/STATUS.md`：确认 "MCP 工具一致性" 热点质量项描述与 TOOL_AUDIT.md 一致

### 验收

- `docs/TODO.md` 无虚假待做项（每项在代码中均有未完成证据）
- `grep -r "TODO" docs/TODO.md docs/STATUS.md` 仅剩 Next/Later 真正待做项

---

## T2: 全链路 API 集成测试

### 策略

使用 FastAPI `AsyncClient`（TestClient 模式），对齐 `tests/integration/test_credit_assessment_flow.py` 风格：
- 每个测试类使用独立 DuckDB `:memory:` 实例（`storage fixture`）
- 不依赖外部服务，`pytest tests/integration/ -v` 独立运行

### 新增文件

**`tests/integration/test_dataset_api_flow.py`**
```python
async def test_create_and_retrieve_dataset()      # POST /v1/management/{space_id}/datasets → GET
async def test_add_entities_to_dataset()         # POST .../datasets/{dataset_id}/entities
async def test_dataset_snapshot()                # POST .../datasets/{dataset_id}/snapshot
async def test_delete_dataset()                  # DELETE .../datasets/{dataset_id}
async def test_list_datasets()                   # GET /v1/management/{space_id}/datasets
```

**`tests/integration/test_incremental_api_flow.py`**
```python
async def test_import_with_diff_dry_run()        # POST /v1/dataset/import (dry_run=true)
async def test_import_persist_and_rollback()     # POST ... + rollback_actions
async def test_impact_analysis()               # POST /v1/dataset/impact
async def test_list_and_get_change_batches()    # GET /v1/dataset/batches
```

**`tests/integration/test_category_api_flow.py`**
```python
async def test_create_and_list_categories()     # POST /v1/categories + GET /v1/categories
async def test_create_rule_mapping()             # POST /v1/categories/rule-mappings
```

### 验收

- `pytest tests/integration/test_dataset_api_flow.py tests/integration/test_incremental_api_flow.py tests/integration/test_category_api_flow.py -v` 全部 PASS
- `pytest tests/integration/ -v --cov=ontology_engine --cov-report=term-missing` 覆盖率有提升
- 每条 API 路径覆盖：Happy path + 错误 path（如删除不存在 dataset）

---

## T3: MCP P1 5 工具实现

### 约束（来自 CLAUDE.md）

- MCP 层只调用 **services 层**，不直接调用 storage/engine
- **测试先行**：`tests/unit/mcp/test_*.py` 先写，再实现代码
- 完成后通过 `mypy --strict` + `ruff check`

### 目录结构

```
ontology_engine/mcp/
├── __init__.py
├── server.py              # MCP Server 入口（使用 @mcp.tool() 装饰器）
├── tools/
│   ├── __init__.py
│   ├── space.py           # oe_create_space, oe_load_schema
│   ├── dataset.py         # oe_register_dataset, oe_trigger_sync
│   ├── execution.py       # oe_execute_rule, oe_trace_rule
│   └── query.py           # oe_query, oe_simulate
└── transports/
    ├── __init__.py
    └── stdio.py           # Claude Desktop stdio 传输
```

### 参数修正（来自 TOOL_AUDIT.md 3.2 节）

| 工具 | MCP 参数 | API 参数 | 对齐方式 |
|------|---------|---------|---------|
| `oe_execute_rule` | `explain_level: full\|detailed\|brief` | `ExplainLevel: none\|basic\|full` | MCP 层做枚举映射 |
| `oe_query` | `match_mode: hybrid\|vector\|graph` | `MatchMode: vector\|keyword\|hybrid\|graph\|pattern` | MCP 层支持所有 API 模式 |
| `oe_simulate` | `dimension`, `overrides` | `categorization`, `input_overrides` | MCP 层字段名对齐 |

### 工具签名

```python
@mcp.tool()
async def oe_create_space(name: str, description: str | None, domain: str | None) -> dict:
    """创建语义空间"""
    # 调用 management service.create_space()

@mcp.tool()
async def oe_query(query: str, match_mode: str, top_k: int = 10) -> dict:
    """知识检索"""
    # 调用 query service.hybrid_query() / vector_query() / graph_query()

@mcp.tool()
async def oe_execute_rule(entity_id: str, view_id: str, dimension: str | None, explain_level: str) -> dict:
    """执行规则分析"""
    # 调用 consumption service.analyze()

@mcp.tool()
async def oe_simulate(entity_id: str, view_id: str, dimension: str | None, overrides: dict) -> dict:
    """模拟执行"""
    # 调用 consumption service.simulate()

@mcp.tool()
async def oe_register_dataset(space_id: str, name: str, source_config: dict) -> dict:
    """注册数据集"""
    # 调用 dataset service.create_dataset()
```

### 统一返回格式

```python
def mcp_response(success: bool, data: Any = None, error: str | None = None) -> dict:
    return {"success": success, "data": data, "error": error}
```

### 验收

1. `pytest tests/unit/mcp/ -v` 全部 PASS
2. `mypy ontology_engine/mcp/ --strict` 无错
3. `ruff check ontology_engine/mcp/` 无警告
4. `claude_desktop_config.json` 模板生成（放在 `docs/09-examples/`），包含 5 个工具定义

---

## T4: Playwright 前端测试套件

### 策略

- 前端测试验证 **Phase 1 新功能在 UI 中的展示**（字段名对齐：element_type→type 等）
- 不 mock API，使用 `playwright.config.ts` 的 `webServer` 启动真实后端
- 截图存 `tests/screenshots/`

### 新增文件

```
ontology-engine-ui/
├── playwright.config.ts
├── tests/
│   ├── screens/
│   ├── space-management.spec.ts    # Space 创建列表
│   ├── schema-editor.spec.ts       # Schema 编辑器字段名
│   └── rule-execution.spec.ts      # 规则执行结果展示
```

### 验收

- `npx playwright test` 全部 PASS
- `npx playwright show-report` 截图覆盖三个核心界面

---

## 错误处理约定

| 层级 | 策略 |
|------|------|
| MCP 工具 | 捕获所有异常 → `mcp_response(success=False, error=str(e))` |
| API 集成测试 | 覆盖 HTTP 400/404/500 错误路径 |
| Playwright | 失败时截图 + 控制台日志 |

---

## 开放问题（已对齐）

| 问题 | 决策 |
|------|------|
| supply_chain_finance.md 是否重写？ | **不重写**，deprecated 标注已完整 |
| DuckDB 路由是否已实现？ | **已实现**，可标记完成 |
| Playwright 是否从零搭建？ | **是**，全新建完整套件 |
| 全链路 API 验收方式？ | **TestClient 集成测试** |
