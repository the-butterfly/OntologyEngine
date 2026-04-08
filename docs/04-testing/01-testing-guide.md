# 测试规范

## Subagent 指令模板

### 1. 生成测试用例

```
为 {module_path} 编写单元测试。

输入:
- 源码路径: {file_path}
- 输出路径: tests/unit/{relative_path}/test_{name}.py

要求:
1. 使用 pytest-asyncio
2. 每个测试独立，使用 tmp_path
3. 命名: test_{method}__{scenario}
4. 覆盖: 正常/异常/边界
5. 目标覆盖率: >= 80%

禁止:
- 不要修改源码
- 不要跳过复杂测试，用 xfail 标记
```

### 2. 业务用例分析

```
分析 {feature} 的业务场景。

输出检查清单:
| 场景 | 输入 | 期望输出 | 优先级 |
|------|------|----------|--------|
| {描述} | {数据} | {结果} | P0/P1/P2 |

必含场景:
- 正常流程 (happy path)
- 空值/None 输入
- 极限值 (MAX_INT, 超长字符串等)
- 并发冲突 (如适用)
```

### 3. UT 验收

```
执行测试并报告结果。

命令: pytest {test_path} -v --tb=short --cov={module} --cov-report=term-missing

输出格式:
- 通过数 / 失败数
- 覆盖率百分比
- 失败原因分析
- 修复建议 (如有)

成功标准: 100% 通过 + >= 80% 覆盖
```

---

## 分层测试

```
┌─────────────────────────────────────────┐
│  E2E 测试 (tests/e2e/)                  │
│   完整流程: 加载 -> 入库 -> 执行 -> 验证  │
├─────────────────────────────────────────┤
│  集成测试 (tests/integration/)          │
│   模块交互: storage + engine            │
├─────────────────────────────────────────┤
│  单元测试 (tests/unit/)                 │
│   单一模块: parser / executor / store   │
└─────────────────────────────────────────┘
```

## 单元测试规范

### 命名

```
tests/unit/
├── core/
│   └── schema/
│       └── test_loader.py        # 测试 SchemaLoader
├── engine/
│   └── rules/
│       └── test_executor.py      # 测试 RuleExecutor
└── storage/
    └── test_duckdb_store.py      # 测试 DuckDBStorage
```

### 模板

```python
import pytest
from ontology_engine.core.schema import SchemaLoader


class TestSchemaLoader:
    """SchemaLoader 单元测试"""

    def test_load_valid_schema(self):
        """应正确加载有效 Schema"""
        loader = SchemaLoader()
        schema = loader.load("tests/fixtures/valid_schema.yaml")

        assert schema.metadata.id == "kg://test/v1"
        assert len(schema.concepts) > 0

    def test_load_invalid_schema_raises(self):
        """无效 Schema 应抛出 ValidationError"""
        loader = SchemaLoader()

        with pytest.raises(ValidationError):
            loader.load("tests/fixtures/invalid_schema.yaml")

    def test_concept_name_unique(self):
        """概念名必须唯一"""
        # Arrange
        raw = {
            "concepts": [
                {"name": "A", "category": "entity"},
                {"name": "A", "category": "entity"},  # 重复
            ]
        }

        # Act / Assert
        with pytest.raises(ValueError, match="duplicate"):
            SchemaLoader().parse(raw)
```

## 集成测试

```python
class TestStorageEngineIntegration:
    """Storage + Engine 集成测试"""

    def test_rule_execution_persists_result(self):
        """规则执行结果应持久化"""
        # Arrange
        store = DuckDBStorage(":memory:")
        engine = RuleEngine(store)

        # Act
        store.add_entity(Entity(...))
        result = engine.execute("E001", "credit_assessment")

        # Assert
        persisted = store.get_computed_metrics("E001")
        assert persisted["credit_score"] == result.score
```

## E2E 测试

```python
def test_supply_chain_finance_workflow():
    """供应链金融完整流程"""
    # Arrange
    client = TestClient(app)

    # 1. 加载 Schema
    client.post("/v1/schema/load", json={
        "schema_path": "examples/supply_chain_finance/schema.yaml"
    })

    # 2. 创建实体
    client.post("/v1/entities", json={
        "concept_type": "Supplier",
        "entity_id": "S001",
        "attributes": {...}
    })

    # 3. 执行规则
    response = client.post("/v1/rules/execute", json={
        "entity_id": "S001",
        "dimension": "credit_assessment"
    })

    # Assert
    assert response.status_code == 200
    assert response.json()["data"]["results"]["R001"]["eligible"] is True
```

## 测试数据

```
tests/fixtures/
├── schema/
│   ├── valid_schema.yaml
│   └── invalid_schema.yaml
├── entities/
│   └── suppliers.json
└── rules/
    └── simple_rules.yaml
```

## 质量门禁

```bash
# 提交前必跑
mypy ontology_engine/ --strict
ruff check ontology_engine/
pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing
```

| 指标 | 阈值 |
|------|------|
| 单测覆盖率 | ≥ 80% |
| 类型检查 | 0 errors |
| Lint | 0 warnings |

## 模块覆盖率要求

| 模块类型 | 行覆盖 | 分支覆盖 |
|----------|--------|----------|
| core/ | ≥ 90% | ≥ 80% |
| storage/ | ≥ 85% | ≥ 75% |
| engine/ | ≥ 85% | ≥ 75% |
| services/ | ≥ 80% | ≥ 70% |
| api/ | ≥ 75% | ≥ 60% |

## 测试模板

```python
import pytest
from pathlib import Path


class Test{ClassName}:
    """{ClassName} 单元测试"""

    @pytest.fixture
    async def {fixture_name}(self, tmp_path: Path):
        """测试夹具"""
        db_path = tmp_path / "test.db"
        instance = {Class}(db_path)
        await instance.init()
        yield instance
        await instance.close()

    async def test_{method}__success(self, {fixture_name}):
        """正常场景"""
        pass

    async def test_{method}__invalid_input(self, {fixture_name}):
        """无效输入"""
        with pytest.raises({Exception}):
            pass

    async def test_{method}__empty_data(self, {fixture_name}):
        """空数据"""
        pass
```
