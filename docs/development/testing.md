# 测试开发指南

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

## 覆盖率要求

| 模块类型 | 行覆盖 | 分支覆盖 |
|----------|--------|----------|
| core/ | >= 90% | >= 80% |
| storage/ | >= 85% | >= 75% |
| engine/ | >= 85% | >= 75% |
| services/ | >= 80% | >= 70% |
| api/ | >= 75% | >= 60% |
