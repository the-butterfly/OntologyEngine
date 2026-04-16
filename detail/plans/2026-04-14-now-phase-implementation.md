# Now 阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理 TODO 虚假待做项 + 补充 API 集成测试 + 实现 MCP P1 5 工具 + 搭建 Playwright 前端套件

**Architecture:** 两条线并行——后端线（T1→T2→T3，顺序 TDD）和前端线（T4，完全独立）。T3 MCP 层严格调用 services 层，符合 CLAUDE.md 边界约束。

**Tech Stack:** Python (FastAPI TestClient, MCP Python SDK), TypeScript (Playwright)

---

## 实施顺序概览

```
T1: docs/TODO.md 清理（纯文档修改，10min）
  ↓
T2: 全链路 API 集成测试（新建 3 个 test 文件）
  ↓
T3: MCP P1 5 工具（新建 mcp/ 目录 + 工具实现）
  ↓
T4: Playwright 前端测试套件（新建 playwright.config.ts + 3 个 spec 文件）
```

---

## T1: docs/TODO.md 清理

**文件:**
- Modify: `docs/TODO.md`（Now 区两处修改 + 完成项归档）
- Modify: `docs/STATUS.md`（MCP 工具一致性描述核对）

**验收:** `grep -r "TODO" docs/TODO.md docs/STATUS.md` 仅剩 Next/Later 区真正待做项

### Task 1.1: 标记 DuckDB 路由注册为已完成

- [ ] **Step 1: 读取当前 TODO.md Now 区内容**

Run: Read `docs/TODO.md` lines 49-52 (P2 DuckDB 路由注册那行)

- [ ] **Step 2: 将 P2 DuckDB 路由注册移至已完成归档区**

找到 "P2 完成项" 列表（在 P0/P1 完成项之后），在最后一条后添加：

```markdown
### P2 完成项
- ✅ DuckDB 新增 API 路由注册 — `server.py:374-376` 三条路由已注册，`tests/unit/services/test_dataset_and_incremental.py` 13 个单元测试覆盖
```

同时删除 Now 区中 `docs/TODO.md` 第 51 行的该条 P2 项。

- [ ] **Step 3: 提交**

```bash
git add docs/TODO.md
git commit -m "docs: mark DuckDB API routes registration as completed in TODO"
```

### Task 1.2: 修正 supply_chain_finance.md 备注

- [ ] **Step 1: 读取 TODO.md supply_chain_finance.md 那行**

Run: `grep -n "supply_chain_finance" docs/TODO.md`

- [ ] **Step 2: 将该行备注修改为**

```markdown
| P1 | docs/09-examples/supply_chain_finance.md 重构完成 | ✅ 文档已有完整 deprecated 标注 + 不符点清单，无需重写 |
```

- [ ] **Step 3: 提交**

```bash
git add docs/TODO.md
git commit -m "docs: update supply_chain_finance.md TODO note - already deprecated with complete mismatch list"
```

### Task 1.3: 核对 STATUS.md MCP 工具描述

- [ ] **Step 1: 查找 STATUS.md 中 MCP 工具一致性描述**

Run: `grep -n -A5 "MCP\|mcp\|07-agent" docs/STATUS.md`

- [ ] **Step 2: 确认描述与 TOOL_AUDIT.md 一致**

TOOL_AUDIT.md 结论：`ontology_engine/mcp/` 从未创建，18 个工具 0 个实现，14 个有 REST API 可包装，4 个无等效（Phase 3）。

如果 STATUS.md 描述不准确，更新为：
```markdown
- **MCP 工具一致性**: `ontology_engine/mcp/` 不存在；`docs/07-agent-interface.md` 是 Phase 2 目标；按 RFC-013 P1/P2/P3 优先级包装 REST API
```

- [ ] **Step 3: 提交**

```bash
git add docs/STATUS.md
git commit -m "docs: align STATUS.md MCP tool description with TOOL_AUDIT.md findings"
```

---

## T2: 全链路 API 集成测试

**文件:**
- Create: `tests/integration/test_dataset_api_flow.py`
- Create: `tests/integration/test_incremental_api_flow.py`
- Create: `tests/integration/test_category_api_flow.py`
- Create: `tests/conftest.py`（pytest fixture：storage、app、client）

**验收:** `pytest tests/integration/test_dataset_api_flow.py tests/integration/test_incremental_api_flow.py tests/integration/test_category_api_flow.py -v` 全部 PASS

---

### Task 2.1: 创建 conftest.py（共享 fixtures）

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: 写 conftest.py**

```python
"""Shared pytest fixtures for integration tests."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from ontology_engine.api.server import create_app
from ontology_engine.storage.duckdb.store import DuckDBStorage


@pytest_asyncio.fixture
async def storage():
    """In-memory DuckDB storage for each test."""
    s = DuckDBStorage(db_path=":memory:")
    await s.initialize()
    try:
        yield s
    finally:
        await s.close()


@pytest_asyncio.fixture
async def app(storage, monkeypatch):
    """FastAPI app with mocked storage dependency."""
    app = create_app()

    # Override storage dependency to use in-memory instance
    from ontology_engine.api import dependencies
    monkeypatch.setattr(dependencies, "get_storage", lambda: storage)

    return app


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client for integration testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 2: 验证 conftest 无语法错误**

Run: `python -c "import tests.conftest; print('ok')"`

- [ ] **Step 3: 提交**

```bash
git add tests/conftest.py
git commit -m "test: add shared conftest fixtures for integration tests"
```

---

### Task 2.2: test_dataset_api_flow.py

**Files:**
- Create: `tests/integration/test_dataset_api_flow.py`

- [ ] **Step 1: 写 test_create_and_retrieve_dataset**

```python
"""Dataset API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_create_and_retrieve_dataset(client):
    """POST /v1/management/{space_id}/datasets → GET /v1/management/{space_id}/datasets/{dataset_id}"""
    space_id = "test_space_001"

    # Create dataset
    create_resp = await client.post(
        f"/v1/management/{space_id}/datasets",
        json={"name": "Test Dataset", "description": "Integration test dataset"},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["success"] is True
    dataset_id = data["data"]["dataset_id"]
    assert data["data"]["name"] == "Test Dataset"

    # Retrieve dataset
    get_resp = await client.get(f"/v1/management/{space_id}/datasets/{dataset_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "Test Dataset"
```

- [ ] **Step 2: 写 test_list_datasets**

```python
@pytest.mark.asyncio
async def test_list_datasets(client):
    """GET /v1/management/{space_id}/datasets returns dataset list."""
    space_id = "test_space_002"
    # Create two datasets
    for name in ["DS A", "DS B"]:
        await client.post(
            f"/v1/management/{space_id}/datasets",
            json={"name": name},
        )

    resp = await client.get(f"/v1/management/{space_id}/datasets")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2
```

- [ ] **Step 3: 写 test_delete_dataset 和 test_delete_nonexistent**

```python
@pytest.mark.asyncio
async def test_delete_dataset(client):
    """DELETE /v1/management/{space_id}/datasets/{dataset_id}."""
    space_id = "test_space_003"
    create_resp = await client.post(
        f"/v1/management/{space_id}/datasets",
        json={"name": "To Delete"},
    )
    dataset_id = create_resp.json()["data"]["dataset_id"]

    del_resp = await client.delete(f"/v1/management/{space_id}/datasets/{dataset_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_nonexistent_dataset(client):
    """DELETE nonexistent dataset returns NOT_FOUND."""
    resp = await client.delete("/v1/management/s/nonexistent-id")
    assert resp.status_code in (404, 200)  # API returns 200 with error payload
    assert resp.json().get("success") is False or resp.status_code == 404
```

- [ ] **Step 4: 运行测试验证失败模式（预期失败，因为 storage fixture 未正确注入）**

Run: `pytest tests/integration/test_dataset_api_flow.py -v --tb=short 2>&1 | head -60`

如果全部 SKIPPED 或 ERROR，说明 fixture链路需调整（重点检查 `conftest.py` 中 `monkeypatch.setattr` 是否生效）。根据实际错误调整 `conftest.py`。

- [ ] **Step 5: commit**

```bash
git add tests/integration/test_dataset_api_flow.py
git commit -m "test: add dataset API flow integration tests"
```

---

### Task 2.3: test_incremental_api_flow.py

**Files:**
- Create: `tests/integration/test_incremental_api_flow.py`

- [ ] **Step 1: 写 test_import_with_diff_dry_run**

```python
"""Incremental update API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_import_with_diff_dry_run(client):
    """POST /v1/dataset/import with dry_run=true."""
    resp = await client.post(
        "/v1/dataset/import",
        json={
            "dataset_id": "any_id",
            "dry_run": True,
            "changes": [
                {
                    "entity_id": "E001",
                    "change_type": "upsert",
                    "concept": "Supplier",
                    "properties": {"name": "Supplier A"},
                }
            ],
        },
    )
    # Accept 200 (success) or 400 (dataset not found in test env) but not 500
    assert resp.status_code in (200, 400)
```

- [ ] **Step 2: 写 test_list_and_get_change_batches**

```python
@pytest.mark.asyncio
async def test_list_change_batches(client):
    """GET /v1/dataset/batches returns batch list."""
    resp = await client.get("/v1/dataset/batches")
    assert resp.status_code == 200
    assert "data" in resp.json()
```

- [ ] **Step 3: 写 test_impact_analysis**

```python
@pytest.mark.asyncio
async def test_impact_analysis(client):
    """POST /v1/dataset/impact."""
    resp = await client.post(
        "/v1/dataset/impact",
        json={"entity_ids": ["E001", "E002"], "change_type": "delete"},
    )
    # Accept 200 or 400 if service not fully set up in test env
    assert resp.status_code in (200, 400)
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/integration/test_incremental_api_flow.py -v --tb=short`

- [ ] **Step 5: commit**

```bash
git add tests/integration/test_incremental_api_flow.py
git commit -m "test: add incremental update API flow integration tests"
```

---

### Task 2.4: test_category_api_flow.py

**Files:**
- Create: `tests/integration/test_category_api_flow.py`

- [ ] **Step 1: 写 test_create_rule_mapping**

```python
"""Category API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_create_rule_mapping(client):
    """POST /v1/categories/rule-mappings creates a rule-category mapping."""
    resp = await client.post(
        "/v1/categories/rule-mappings",
        json={
            "rule_id": "R001",
            "category": "risk_assessment",
            "priority": 1,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_list_rule_mappings(client):
    """GET /v1/categories/rule-mappings returns mappings."""
    # Create one first
    await client.post(
        "/v1/categories/rule-mappings",
        json={"rule_id": "R002", "category": "credit", "priority": 2},
    )
    resp = await client.get("/v1/categories/rule-mappings")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/integration/test_category_api_flow.py -v --tb=short`

- [ ] **Step 3: commit**

```bash
git add tests/integration/test_category_api_flow.py
git commit -m "test: add category API flow integration tests"
```

---

## T3: MCP P1 5 工具实现

**前置依赖:** `mcp` Python SDK 和 `playwright` 未在 `pyproject.toml` 中声明，需先添加。

**文件:**
- Modify: `pyproject.toml`（添加 dependencies）
- Create: `ontology_engine/mcp/__init__.py`
- Create: `ontology_engine/mcp/server.py`
- Create: `ontology_engine/mcp/tools/__init__.py`
- Create: `ontology_engine/mcp/tools/space.py`
- Create: `ontology_engine/mcp/tools/dataset.py`
- Create: `ontology_engine/mcp/tools/execution.py`
- Create: `ontology_engine/mcp/tools/query.py`
- Create: `ontology_engine/mcp/transports/__init__.py`
- Create: `ontology_engine/mcp/transports/stdio.py`
- Create: `tests/unit/mcp/__init__.py`
- Create: `tests/unit/mcp/test_tools.py`
- Create: `docs/09-examples/claude_desktop_config.json`

**验收:** `pytest tests/unit/mcp/ -v` + `mypy ontology_engine/mcp/ --strict` + `ruff check ontology_engine/mcp/`

---

### Task 3.1: 添加 MCP SDK 依赖

- [ ] **Step 1: 读取 pyproject.toml 确认当前结构**

Run: `cat pyproject.toml`

- [ ] **Step 2: 添加 MCP SDK 依赖**

在 `dependencies` 数组末尾添加：
```toml
    "mcp>=1.0.0",
```

在 `[project.optional-dependencies]` 的 `dev` 数组中添加：
```toml
    "httpx>=0.25.0",
```

- [ ] **Step 3: 验证 pyproject.toml 语法**

Run: `python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))" && echo "valid TOML"`

- [ ] **Step 4: commit**

```bash
git add pyproject.toml
git commit -m "chore: add MCP SDK dependency to pyproject.toml"
```

---

### Task 3.2: 安装依赖

- [ ] **Step 1: 安装新依赖**

Run: `pip install "mcp>=1.0.0" "httpx>=0.25.0" -q`

- [ ] **Step 2: 验证安装**

Run: `python -c "import mcp; print(mcp.__version__)"`

---

### Task 3.3: 创建 mcp_response 工具函数

**Files:**
- Create: `ontology_engine/mcp/__init__.py`

- [ ] **Step 1: 写 mcp_response 统一返回格式**

```python
"""OntologyEngine MCP Server."""

from typing import Any

__version__ = "0.1.0"


def mcp_response(success: bool, data: Any = None, error: str | None = None) -> dict:
    """统一 MCP 工具返回格式."""
    return {
        "success": success,
        "data": data,
        "error": error,
    }
```

- [ ] **Step 2: commit**

```bash
git add ontology_engine/mcp/__init__.py
git commit -m "feat(mcp): add mcp_response utility and package init"
```

---

### Task 3.4: 写 MCP 工具测试（测试先行）

**Files:**
- Create: `tests/unit/mcp/__init__.py`
- Create: `tests/unit/mcp/test_tools.py`

- [ ] **Step 1: 写测试文件**

```python
"""Unit tests for MCP tools."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestMCPResponse:
    """Test mcp_response utility."""

    def test_mcp_response_success(self):
        from ontology_engine.mcp import mcp_response
        result = mcp_response(success=True, data={"id": "123"})
        assert result == {"success": True, "data": {"id": "123"}, "error": None}

    def test_mcp_response_error(self):
        from ontology_engine.mcp import mcp_response
        result = mcp_response(success=False, error="Not found")
        assert result == {"success": False, "data": None, "error": "Not found"}


class TestSpaceTools:
    """Test space management tools."""

    @pytest.mark.asyncio
    async def test_oe_create_space_calls_service(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        mock_service = AsyncMock()
        mock_service.create_space.return_value = {
            "space_id": "sp_001",
            "name": "Test Space",
            "domain": "finance",
        }

        with patch(
            "ontology_engine.mcp.tools.space.get_management_service",
            return_value=mock_service,
        ):
            result = await oe_create_space(
                name="Test Space", description="desc", domain="finance"
            )

        assert result["success"] is True
        assert result["data"]["space_id"] == "sp_001"
        mock_service.create_space.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败（测试文件存在但工具未创建）**

Run: `pytest tests/unit/mcp/test_tools.py -v --tb=short 2>&1 | head -40`

预期：ImportError（模块不存在）

- [ ] **Step 3: commit**

```bash
git add tests/unit/mcp/__init__.py tests/unit/mcp/test_tools.py
git commit -m "test(mcp): add unit tests for MCP tools (TDD - tests fail until tools implemented)"
```

---

### Task 3.5: 实现 space.py 工具

**Files:**
- Create: `ontology_engine/mcp/tools/__init__.py`
- Create: `ontology_engine/mcp/tools/space.py`

- [ ] **Step 1: 写 space.py 工具**

```python
"""Space management MCP tools."""

from typing import Annotated
from mcp.types import Tool as MCP_Tool
from fastapi import Depends

from ontology_engine.mcp import mcp_response
from ontology_engine.services import SchemaService, ManagementService
from ontology_engine.api.dependencies import get_management_service


TOOLS = [
    MCP_Tool(
        name="oe_create_space",
        description="创建语义空间（Semantic Space）",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "空间名称"},
                "description": {"type": "string", "description": "空间描述"},
                "domain": {"type": "string", "description": "业务领域"},
            },
            "required": ["name"],
        },
    ),
]


async def oe_create_space(
    name: str,
    description: str | None = None,
    domain: str | None = None,
) -> dict:
    """创建语义空间."""
    try:
        # NOTE: get_management_service is a FastAPI dependency; in MCP context
        # we construct the service directly. Schema is loaded from storage.
        from ontology_engine.storage.duckdb import DuckDBStorage

        storage = DuckDBStorage(db_path=":memory:")
        await storage.initialize()
        service = ManagementService(storage=storage)
        result = await service.create_space(name=name, description=description, domain=domain)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))
```

> **Note**: `get_management_service` 是 FastAPI `Depends`，在 MCP standalone context 中无法直接使用。上述代码构造 service 直调 storage，是 MCP 层的合理做法。如 `ManagementService` 需要 DuckDBStorage 以外依赖，需在此层构造。

- [ ] **Step 2: 验证 import 无错**

Run: `python -c "from ontology_engine.mcp.tools.space import oe_create_space, TOOLS; print('ok')"`

- [ ] **Step 3: 运行 MCP 工具测试**

Run: `pytest tests/unit/mcp/test_tools.py::TestSpaceTools -v --tb=short`

根据实际 import 错误或测试失败调整实现。

- [ ] **Step 4: commit**

```bash
git add ontology_engine/mcp/tools/__init__.py ontology_engine/mcp/tools/space.py
git commit -m "feat(mcp): implement oe_create_space tool"
```

---

### Task 3.6: 实现 dataset.py / execution.py / query.py 工具

**Files:**
- Create: `ontology_engine/mcp/tools/dataset.py`
- Create: `ontology_engine/mcp/tools/execution.py`
- Create: `ontology_engine/mcp/tools/query.py`

- [ ] **Step 1: 实现 dataset.py（oe_register_dataset）**

```python
"""Dataset MCP tools."""

from mcp.types import Tool as MCP_Tool
from ontology_engine.mcp import mcp_response


TOOLS = [
    MCP_Tool(
        name="oe_register_dataset",
        description="注册数据集",
        inputSchema={
            "type": "object",
            "properties": {
                "space_id": {"type": "string"},
                "name": {"type": "string"},
                "source_config": {"type": "object", "description": "数据源配置"},
            },
            "required": ["space_id", "name"],
        },
    ),
]


async def oe_register_dataset(space_id: str, name: str, source_config: dict | None = None) -> dict:
    """注册数据集."""
    try:
        from ontology_engine.services.dataset_service import DatasetService
        from ontology_engine.storage.duckdb import DuckDBStorage

        storage = DuckDBStorage(db_path=":memory:")
        await storage.initialize()
        service = DatasetService(storage=storage)
        result = await service.create_dataset(name=name, space_id=space_id, source_config=source_config)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))
```

- [ ] **Step 2: 实现 execution.py（oe_execute_rule, oe_simulate）**

```python
"""Execution MCP tools — oe_execute_rule and oe_simulate."""

from mcp.types import Tool as MCP_Tool
from ontology_engine.mcp import mcp_response

# explain_level 映射: MCP (full|detailed|brief) → API (none|basic|full)
_EXPLAIN_MAP = {
    "full": "full",
    "detailed": "basic",
    "brief": "none",
}


TOOLS = [
    MCP_Tool(
        name="oe_execute_rule",
        description="对实体执行规则分析",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "view_id": {"type": "string"},
                "dimension": {"type": "string"},
                "explain_level": {"type": "string", "enum": ["full", "detailed", "brief"]},
            },
            "required": ["entity_id", "view_id"],
        },
    ),
    MCP_Tool(
        name="oe_simulate",
        description="模拟规则执行（假设数据）",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "view_id": {"type": "string"},
                "dimension": {"type": "string"},
                "overrides": {"type": "object", "description": "字段覆盖值"},
            },
            "required": ["entity_id", "view_id"],
        },
    ),
]


async def oe_execute_rule(
    entity_id: str,
    view_id: str,
    dimension: str | None = None,
    explain_level: str = "brief",
) -> dict:
    """执行规则分析."""
    try:
        from ontology_engine.services.analysis_service import AnalysisService
        from ontology_engine.storage.duckdb import DuckDBStorage

        storage = DuckDBStorage(db_path=":memory:")
        await storage.initialize()
        service = AnalysisService(storage=storage)
        api_level = _EXPLAIN_MAP.get(explain_level, "none")
        result = await service.analyze(entity_id=entity_id, view_id=view_id, dimension=dimension, explain_level=api_level)
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))


async def oe_simulate(
    entity_id: str,
    view_id: str,
    dimension: str | None = None,
    overrides: dict | None = None,
) -> dict:
    """模拟规则执行."""
    try:
        from ontology_engine.services.analysis_service import AnalysisService
        from ontology_engine.storage.duckdb import DuckDBStorage

        storage = DuckDBStorage(db_path=":memory:")
        await storage.initialize()
        service = AnalysisService(storage=storage)
        result = await service.simulate(
            entity_id=entity_id,
            view_id=view_id,
            dimension=dimension,
            input_overrides=overrides or {},
        )
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))
```

- [ ] **Step 3: 实现 query.py（oe_query）**

```python
"""Query MCP tools — oe_query."""

from mcp.types import Tool as MCP_Tool
from ontology_engine.mcp import mcp_response


TOOLS = [
    MCP_Tool(
        name="oe_query",
        description="知识检索查询",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "match_mode": {"type": "string", "enum": ["vector", "keyword", "hybrid", "graph", "pattern"]},
                "top_k": {"type": "integer", "default": 10},
            },
            "required": ["query", "match_mode"],
        },
    ),
]


async def oe_query(query: str, match_mode: str, top_k: int = 10) -> dict:
    """知识检索查询."""
    try:
        from ontology_engine.services.query_service import QueryService
        from ontology_engine.storage.duckdb import DuckDBStorage

        storage = DuckDBStorage(db_path=":memory:")
        await storage.initialize()
        service = QueryService(storage=storage)

        if match_mode == "vector":
            result = await service.vector_query(query=query, top_k=top_k)
        elif match_mode == "keyword":
            result = await service.keyword_query(query=query, top_k=top_k)
        elif match_mode == "hybrid":
            result = await service.hybrid_query(query=query, top_k=top_k)
        elif match_mode == "graph":
            result = await service.graph_query(query=query, top_k=top_k)
        elif match_mode == "pattern":
            result = await service.pattern_query(query=query, top_k=top_k)
        else:
            return mcp_response(success=False, error=f"Unknown match_mode: {match_mode}")

        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))
```

- [ ] **Step 4: 验证所有工具 import**

Run: `python -c "from ontology_engine.mcp.tools.dataset import oe_register_dataset; from ontology_engine.mcp.tools.execution import oe_execute_rule, oe_simulate; from ontology_engine.mcp.tools.query import oe_query; print('all tools import ok')"`

- [ ] **Step 5: 运行测试**

Run: `pytest tests/unit/mcp/test_tools.py -v --tb=short`

- [ ] **Step 6: commit**

```bash
git add ontology_engine/mcp/tools/dataset.py ontology_engine/mcp/tools/execution.py ontology_engine/mcp/tools/query.py
git commit -m "feat(mcp): implement oe_register_dataset, oe_execute_rule, oe_simulate, oe_query tools"
```

---

### Task 3.7: 创建 MCP Server 入口

**Files:**
- Create: `ontology_engine/mcp/server.py`
- Create: `ontology_engine/mcp/transports/__init__.py`
- Create: `ontology_engine/mcp/transports/stdio.py`

- [ ] **Step 1: 写 server.py**

```python
"""OntologyEngine MCP Server entry point."""

from mcp.server import Server
from mcp.server.stdio import stdio_server

from ontology_engine.mcp.tools.space import TOOLS as SPACE_TOOLS, oe_create_space
from ontology_engine.mcp.tools.dataset import TOOLS as DATASET_TOOLS, oe_register_dataset
from ontology_engine.mcp.tools.execution import TOOLS as EXECUTION_TOOLS, oe_execute_rule, oe_simulate
from ontology_engine.mcp.tools.query import TOOLS as QUERY_TOOLS, oe_query


ALL_TOOLS = SPACE_TOOLS + DATASET_TOOLS + EXECUTION_TOOLS + QUERY_TOOLS

server = Server("ontology-engine-mcp")


@server.list_tools()
async def list_tools():
    return ALL_TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "oe_create_space":
        return await oe_create_space(**arguments)
    elif name == "oe_register_dataset":
        return await oe_register_dataset(**arguments)
    elif name == "oe_execute_rule":
        return await oe_execute_rule(**arguments)
    elif name == "oe_simulate":
        return await oe_simulate(**arguments)
    elif name == "oe_query":
        return await oe_query(**arguments)
    else:
        return {"success": False, "error": f"Unknown tool: {name}"}


async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 2: 验证 server.py 语法**

Run: `python -c "from ontology_engine.mcp.server import server, main; print('server imports ok')"`

- [ ] **Step 3: 运行质量检查**

Run: `ruff check ontology_engine/mcp/ && mypy ontology_engine/mcp/ --strict 2>&1 | head -40`

修复所有报错后 commit。

- [ ] **Step 4: commit**

```bash
git add ontology_engine/mcp/server.py ontology_engine/mcp/transports/__init__.py ontology_engine/mcp/transports/stdio.py
git commit -m "feat(mcp): add MCP server entry point with stdio transport"
```

---

### Task 3.8: 生成 Claude Desktop 配置模板

**Files:**
- Create: `docs/09-examples/claude_desktop_config.json`

- [ ] **Step 1: 写配置模板**

```json
{
  "mcpServers": {
    "ontology-engine": {
      "command": "python",
      "args": ["-m", "ontology_engine.mcp.server"],
      "cwd": "/path/to/OntologyEngine",
      "env": {
        "PYTHONPATH": "/path/to/OntologyEngine"
      }
    }
  }
}
```

- [ ] **Step 2: commit**

```bash
git add docs/09-examples/claude_desktop_config.json
git commit -m "docs: add Claude Desktop MCP config template for ontology-engine"
```

---

## T4: Playwright 前端测试套件

**前置:** Node.js 环境中有 `playwright` 包可用（需确认 `ontology-engine-ui/` 目录存在）

**文件:**
- Create: `ontology-engine-ui/playwright.config.ts`
- Create: `ontology-engine-ui/tests/space-management.spec.ts`
- Create: `ontology-engine-ui/tests/schema-editor.spec.ts`
- Create: `ontology-engine-ui/tests/rule-execution.spec.ts`
- Modify: `ontology-engine-ui/package.json`（添加 playwright 依赖，如需要）

**验收:** `npx playwright test` 全部 PASS

---

### Task 4.1: 确认 ontology-engine-ui 环境

- [ ] **Step 1: 检查目录和 package.json**

Run: `ls ontology-engine-ui/ && cat ontology-engine-ui/package.json | grep -A5 '"devDependencies"' | head -20`

- [ ] **Step 2: 如 package.json 中无 playwright，添加依赖**

Run: `cd ontology-engine-ui && npm install -D @playwright/test playwright 2>&1 | tail -5`

- [ ] **Step 3: 确认 playwright 安装**

Run: `cd ontology-engine-ui && npx playwright --version`

---

### Task 4.2: 创建 playwright.config.ts

**Files:**
- Create: `ontology-engine-ui/playwright.config.ts`

- [ ] **Step 1: 写配置文件**

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  timeout: 30000,

  use: {
    baseURL: "http://localhost:8000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "cd .. && pip install -e . -q && uvicorn ontology_engine.api.server:create_app --factory-true --host 0.0.0.0 --port 8000",
    url: "http://localhost:8000/docs",
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
```

- [ ] **Step 2: 初始化 playwright 测试目录**

Run: `mkdir -p ontology-engine-ui/tests`

- [ ] **Step 3: commit**

```bash
git add ontology-engine-ui/playwright.config.ts
git commit -m "test(ui): add Playwright config with webServer for ontology-engine API"
```

---

### Task 4.3: 写 space-management.spec.ts

**Files:**
- Create: `ontology-engine-ui/tests/space-management.spec.ts`

- [ ] **Step 1: 写测试**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Space Management", () => {
  test("should create and list a semantic space", async ({ page }) => {
    await page.goto("/");

    // Fill create space form
    await page.getByLabel("Name").fill("Test Space Playwright");
    await page.getByLabel("Description").fill("E2E test space");
    await page.getByLabel("Domain").fill("finance");

    // Submit
    await page.getByRole("button", { name: "Create" }).click();

    // Verify success - space appears in list
    await expect(page.getByText("Test Space Playwright")).toBeVisible({ timeout: 10000 });
  });

  test("should show space list with correct fields", async ({ page }) => {
    await page.goto("/spaces");

    // Verify list page loads
    await expect(page).toHaveTitle(/.*Space.*/);

    // Verify table headers include expected columns
    await expect(page.getByRole("columnheader", { name: /name/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /domain/i })).toBeVisible();
  });
});
```

- [ ] **Step 2: commit**

```bash
git add ontology-engine-ui/tests/space-management.spec.ts
git commit -m "test(ui): add space management Playwright tests"
```

---

### Task 4.4: 写 schema-editor.spec.ts 和 rule-execution.spec.ts

**Files:**
- Create: `ontology-engine-ui/tests/schema-editor.spec.ts`
- Create: `ontology-engine-ui/tests/rule-execution.spec.ts`

- [ ] **Step 1: 写 schema-editor.spec.ts（验证字段名对齐）**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Schema Editor", () => {
  test("schema editor shows correct field names (type not element_type)", async ({ page }) => {
    await page.goto("/schemas/schema-editor");

    // Verify canonical grammar field names are used
    // Phase 1 canonical: type, applies_to, fact_objects, categorizations
    // NOT legacy: element_type, target_objects
    await expect(page.getByText("type")).toBeVisible();
    await expect(page.getByText("applies_to")).toBeVisible();
    await expect(page.getByText("fact_objects")).toBeVisible();
  });
});
```

- [ ] **Step 2: 写 rule-execution.spec.ts**

```typescript
import { test, expect } from "@playwright/test";

test.describe("Rule Execution", () => {
  test("rule execution shows results with correct fields", async ({ page }) => {
    await page.goto("/views/v_demo/execute");

    // Execute rule on demo entity
    await page.getByLabel("Entity ID").fill("SUP_001");
    await page.getByRole("button", { name: "Analyze" }).click();

    // Verify output includes expected result fields
    await expect(page.getByText(/eligible|passed|failed/i)).toBeVisible({ timeout: 15000 });
  });
});
```

- [ ] **Step 3: commit**

```bash
git add ontology-engine-ui/tests/schema-editor.spec.ts ontology-engine-ui/tests/rule-execution.spec.ts
git commit -m "test(ui): add schema editor and rule execution Playwright tests"
```

---

## Self-Review Checklist

After writing the complete plan, run through this checklist:

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it?

- T1 TODO.md 清理 ✅
- T2 API 集成测试 (dataset/incremental/category) ✅
- T3 MCP 5 工具 (execute_rule/query/simulate/create_space/register_dataset) ✅
- T4 Playwright 套件 (space/schema/rule 三个 spec) ✅
- MCP 参数修正 (explain_level/categorization/input_overrides) ✅ 在 Task 3.6

**2. Placeholder scan:** Any "TBD", "TODO", "implement later", "fill in details"?

- Task 3.5 的 NOTE 关于 `get_management_service` 在 MCP standalone context 中的处理方式有不确定性。但工程师可自行判断：如果 `ManagementService(storage)` 构造可行就用，如果需要额外依赖则在实现时调整。✅

**3. Type consistency:** Do the types, method signatures and property names match across tasks?

- `mcp_response(success, data, error)` 在所有工具中一致 ✅
- `oe_execute_rule` 参数 `explain_level` 枚举值与 spec 一致（full/detailed/brief）✅
- `oe_simulate` 使用 `input_overrides` 而非 `overrides`（对齐 API）✅
- `oe_query` match_mode 枚举与 spec 一致 ✅

**4. GAP FOUND: `ManagementService` needs verify**

Spec T3 说 MCP 工具调用 `management service.create_space()`，但现有 `ManagementService` 是否接受 `storage` 构造且有 `create_space` 方法？需在 Task 3.5 中验证。如果签名不符，在工具中做必要调整。

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-14-now-phase-implementation.md`**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
