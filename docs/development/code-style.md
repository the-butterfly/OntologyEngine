# 代码规范

## 强制规则

### 类型注解

```python
# ❌ 禁止
async def query(q, params=None): ...

# ✅ 正确
async def query(
    q: str,
    params: dict[str, Any] | None = None
) -> QueryResult: ...
```

### 错误处理

```python
# 异常层级
class OntologyError(Exception): pass
class StorageError(OntologyError): pass
class GraphError(StorageError): pass

# 使用
async def create(self, node: Node) -> NodeId:
    try:
        cursor.execute("INSERT ...", (node.id,))
    except sqlite3.IntegrityError as e:
        raise DuplicateError(f"Node {node.id} exists") from e
```

### 文档字符串

```python
async def method(
    self,
    param: str
) -> Result:
    """一句话描述
    
    详细说明 (如需要)
    
    Args:
        param: 参数说明
    
    Returns:
        返回值说明
    
    Raises:
        SomeError: 异常说明
    
    Examples:
        >>> await obj.method("value")
        Result(data=...)
    """
```

## 文件头

```python
"""模块名称 - 一句话描述"""

from __future__ import annotations

__all__ = ["PublicClass"]
```

## 工具命令

```bash
# 类型检查
mypy ontology_engine/ --strict

# 代码风格
ruff check ontology_engine/
black --check ontology_engine/

# 格式化
black ontology_engine/
ruff check --fix ontology_engine/
```
