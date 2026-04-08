# 项目结构

```
ontology_engine/                 # 主包
├── __init__.py
├── __main__.py                  # python -m ontology_engine
├── config.py                    # 配置管理
│
├── core/                        # 核心模块
│   ├── __init__.py
│   ├── schema/                  # Schema 管理
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic 模型
│   │   ├── loader.py           # Schema 加载
│   │   └── validator.py        # Schema 校验
│   ├── models/                  # 数据模型
│   │   ├── __init__.py
│   │   ├── concept.py
│   │   ├── entity.py
│   │   ├── relation.py
│   │   └── metric.py
│   └── types/                   # 类型定义
│       ├── __init__.py
│       └── primitives.py
│
├── storage/                     # 存储层 (本地优先)
│   ├── __init__.py
│   ├── base.py                 # 存储抽象接口
│   │
│   ├── duckdb/                 # DuckDB 实现 (默认)
│   │   ├── __init__.py
│   │   └── store.py            # DuckDB 主存储
│   │
│   └── adapters/               # 预留外部存储接口
│       ├── __init__.py
│       ├── neo4j_store.py      # Neo4j 适配器 (预留)
│       ├── pgvector_store.py   # pgvector 适配器 (预留)
│       └── redis_cache.py      # Redis 适配器 (预留)
│
├── engine/                      # 引擎层
│   ├── __init__.py
│   │
│   ├── query/                  # 查询引擎
│   │   ├── __init__.py
│   │   ├── parser.py
│   │   ├── local_executor.py   # 本地查询执行
│   │   └── optimizer.py
│   │
│   ├── rules/                  # 规则引擎
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── resolver.py         # DAG 依赖解析
│   │   ├── executor.py
│   │   └── operators/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── math_ops.py
│   │       ├── logic_ops.py
│   │       └── graph_ops.py    # NetworkX 图算子
│   │
│   ├── inference/              # 推理引擎
│   │   ├── __init__.py
│   │   ├── symbolic.py
│   │   └── llm.py
│   │
│   └── vector/                 # 向量引擎
│       ├── __init__.py
│       ├── embedder.py         # Embedding 生成
│       └── indexer.py          # 向量索引管理
│
├── services/                    # 服务层
│   ├── __init__.py
│   ├── schema_service.py
│   ├── query_service.py
│   ├── rule_service.py
│   └── memory_service.py
│
├── api/                         # API 层
│   ├── __init__.py
│   ├── server.py               # FastAPI 应用
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── schema.py
│   │   ├── query.py
│   │   ├── rules.py
│   │   └── memory.py
│   └── dependencies.py
│
└── ingestion/                   # 数据接入
    ├── __init__.py
    ├── loaders/
    │   ├── __init__.py
    │   ├── kgml_loader.py
    │   └── csv_loader.py
    └── transformers.py

data/                            # 本地数据目录 (gitignore)
├── .gitkeep
├── ontology.db                  # DuckDB 主数据库
├── vectors/                     # Faiss 索引
└── cache/                       # diskcache

docs/                            # 文档
├── README.md
├── architecture.md
├── concepts.md
├── tech-stack.md
├── project-structure.md
└── roadmap.md

tests/                           # 测试
├── __init__.py
├── unit/
├── integration/
└── conftest.py

pyproject.toml                   # 项目配置
├── [project]                   # 基础依赖 (本地存储)
├── [project.optional-dependencies]
│   ├── ai                      # openai, sentence-transformers
│   ├── prod                    # neo4j, asyncpg, redis
│   └── dev                     # pytest, black, ruff
│
docker-compose.yml               # 可选：生产环境服务
Dockerfile
Makefile
scripts/                         # 工具脚本
├── init_db.py                  # 初始化本地数据库
├── migrate.py                  # 数据迁移工具
└── backup.py                   # 数据备份
```

## 存储层设计

### 接口抽象

```python
# storage/base.py
from abc import ABC, abstractmethod

class StorageBackend(ABC):
    """主存储抽象接口 (DuckDB 实现)"""

    @abstractmethod
    async def save_entity(self, entity: EntityInstance) -> str: ...

    @abstractmethod
    async def get_entity(self, concept: str, entity_id: str) -> EntityInstance | None: ...

    @abstractmethod
    async def query_entities(self, concept: str, filters: dict | None) -> list[EntityInstance]: ...

    @abstractmethod
    async def save_relation(self, relation: RelationInstance) -> None: ...

    @abstractmethod
    async def get_relations(self, from_entity_id: str, relation_type: str | None) -> list[RelationInstance]: ...

class VectorStore(ABC):
    """向量存储抽象接口"""

    @abstractmethod
    async def insert(self, id: str, vector: list[float], metadata: dict): ...

    @abstractmethod
    async def search(self, query: list[float], top_k: int) -> list[SearchResult]: ...

class MetaStore(ABC):
    """元数据存储抽象接口"""

    @abstractmethod
    async def save_schema(self, schema: Schema): ...

    @abstractmethod
    async def load_schema(self, schema_id: str) -> Schema: ...
```

### 工厂模式

```python
# storage/__init__.py
from .duckdb.store import DuckDBStorage
from .adapters.faiss_vector import FaissVectorStore  # 预留向量适配器
from .adapters.neo4j_store import Neo4jGraphStore  # 预留

def create_storage(config: StorageConfig) -> StorageBackend:
    if config.storage_type == "duckdb":
        return DuckDBStorage(config.data_dir / "ontology.db")
    elif config.storage_type == "neo4j":
        return Neo4jGraphStore(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    else:
        raise ValueError(f"Unknown storage type: {config.storage_type}")
```

## 模块依赖

```
api/
  └── services/
        └── engine/
              ├── storage/     ← 通过接口注入
              │     ├── duckdb/     (默认)
              │     └── adapters/   (预留)
              └── core/
```

**原则**:
- 上层依赖下层接口，不关心具体实现
- 默认使用本地 DuckDB 存储
- 通过配置切换外部存储，无需改代码
- 图算法 (NetworkX) 按需加载，不作为主存储
