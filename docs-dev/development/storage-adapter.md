# 存储适配器开发指南

## 添加本地存储

```python
# storage/local/{name}_{type}.py

from storage.base import {Type}Store


class {Name}{Type}Store({Type}Store):
    """{description}"""
    
    def __init__(self, path: str):
        self.path = path
        self._init_db()
    
    async def create_{entity}(self, {entity}: {Entity}) -> {Id}:
        """创建"""
        pass
    
    async def get_{entity}(self, {id}: str) -> {Entity} | None:
        """读取"""
        pass
    
    async def update_{entity}(self, {id}: str, data: dict) -> bool:
        """更新"""
        pass
    
    async def delete_{entity}(self, {id}: str) -> bool:
        """删除"""
        pass
```

## 添加外部适配器 (预留)

```python
# storage/adapters/{name}_{type}.py

from storage.base import {Type}Store


class {Name}{Type}Store({Type}Store):
    """{Name} 适配器 (预留)"""
    
    def __init__(self, ...):
        raise NotImplementedError(
            "{Name} 适配器需安装 {driver}: pip install {package}"
        )
```

## 注册到工厂

```python
# storage/__init__.py

def create_{type}_store(config: Config) -> {Type}Store:
    if config.store_type == "local":
        return Local{Type}Store(config.path)
    elif config.store_type == "{name}":
        return {Name}{Type}Store(...)  # 新适配器
    else:
        raise ValueError(f"Unknown store type: {config.store_type}")
```

## 检查清单

- [ ] 实现所有抽象方法
- [ ] 添加异常转换层
- [ ] 资源清理 (close/cleanup)
- [ ] 线程/协程安全
- [ ] 单元测试通过
