# 算子开发指南

## 添加算子

```python
# engine/rules/operators/{category}_ops.py

from engine.rules.operators.base import BaseOperator


class {Name}Operator(BaseOperator):
    """{description}"""
    
    name = "{UPPER_NAME}"        # 唯一标识
    category = "{category}"       # math/logic/comparison/graph/external
    
    async def execute(
        self,
        params: dict[str, Any],
        context: Context
    ) -> Any:
        """执行逻辑
        
        Args:
            params: 参数映射
            context: 执行上下文
        
        Returns:
            计算结果
        
        Raises:
            OperatorError: 参数无效
            ExecutionError: 执行失败
        """
        # 1. 参数提取
        value = params["value"]
        
        # 2. 校验
        if not isinstance(value, (int, float)):
            raise OperatorError(f"Expected number, got {type(value)}")
        
        # 3. 计算
        result = value * 2
        
        # 4. 返回
        return result
```

## 参数规范

| 字段 | 说明 |
|------|------|
| `params` | 用户传入的参数，已解析变量引用 |
| `context` | 执行上下文，包含已计算结果 |
| 返回值 | 必须是可 JSON 序列化的类型 |

## 注册

```python
# engine/rules/operators/__init__.py

from .math_ops import {Name}Operator

__all__ = [
    ...,  # 现有算子
    "{Name}Operator",
]
```

## 测试要求

```python
# tests/unit/engine/rules/operators/test_{category}_ops.py

class Test{Name}Operator:
    async def test_execute__success(self):
        op = {Name}Operator()
        result = await op.execute({"value": 5}, Context())
        assert result == 10
    
    async def test_execute__invalid_type(self):
        op = {Name}Operator()
        with pytest.raises(OperatorError):
            await op.execute({"value": "not a number"}, Context())
```
