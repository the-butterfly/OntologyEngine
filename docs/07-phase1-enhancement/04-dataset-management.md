# 04: 数据集 Dataset 管理模型设计

---
status: draft
phase: phase1
source_of_truth: true   # [单一事实源] Dataset 管理模型的唯一规范
last_verified: 2026-04-13
verified_against: docs-only
related_docs:
  - ../05-schema-v2/06-dataset-and-sync.md
  - ../05-schema-v2/01-fact-objects.md
  - ../06-module-detailed-design/02-instance-management.md
  - ../06-module-detailed-design/10-api-layer.md
related_adrs: []
---

## 1. 背景与动机

### 1.1 什么是 Dataset

**Dataset** 是 OntologyEngine 中**一组实体和关系的逻辑集合**，是管理构建层面的核心概念：

```
SemanticSpace (语义空间)
  ├── Schema (L1-L4 声明)
  ├── Dataset A (企业基础数据)
  │     ├── 50 个 Company 实例
  │     ├── 200 个 Transaction 关系
  │     └── 导入来源: ERP_API_2024
  ├── Dataset B (担保关系数据)
  │     ├── 50 个 Company 实例 (与 A 重叠)
  │     ├── 80 个 Guarantee 关系
  │     └── 导入来源: 征信系统
  └── Dataset C (供应商准入名单)
        ├── 30 个 Company 实例 (A 的子集)
        └── 导入来源: 人工维护
```

### 1.2 为什么需要 Dataset

当前系统的问题：

| 问题 | 影响 |
|------|------|
| 实体直接属于 SemanticSpace | 无法按数据来源分组管理 |
| 无数据集边界 | 查询时无法限定范围 |
| 无导入追踪 | 不知道实例来自哪里、何时导入 |
| 无差异化权限 | 无法对不同数据集设置不同访问级别 |
| 无数据集间关系 | 无法表达 "数据集 B 是 A 的补充" |

### 1.3 设计原则

1. **逻辑分组** —— Dataset 是实体的逻辑集合，不物理复制数据
2. **溯源追踪** —— 每个实体实例可标记其来源 Dataset
3. **增量更新** —— Dataset 支持增量导入，自动差异比对
4. **空间归属** —— Dataset 属于某个 SemanticSpace
5. **向后兼容** —— 不配置 Dataset 时行为与当前一致

## 2. Dataset 模型设计

### 2.1 声明: DatasetDefinition

```yaml
dataset:
  id: string                            # 全局唯一标识
  name: string                          # 显示名称
  description: string | null           # 描述

  # --- 空间归属 ---
  space_id: string                      # 所属 SemanticSpace ID

  # --- 数据范围 ---
  scope:
    object_types:                       # 包含的对象类型
      - string                          # 如 ["Company", "Borrower"]
    relation_types:                     # 包含的关系类型 (可选)
      - string | null
    filters:                            # 过滤条件 (可选)
      - field: string
        operator: string                # eq | neq | gt | lt | in | contains
        value: any

  # --- 导入配置 ---
  source:
    type: manual | file_import | api_sync | dataset_derived
    config:
      # type = file_import 时
      file_path: string | null
      file_format: "yaml" | "csv" | "json"
      encoding: "utf-8"

      # type = api_sync 时
      api_url: string | null
      sync_cron: string | null          # cron 表达式
      auth_config:                      # API 认证配置 (不存储明文)

      # type = dataset_derived 时 (从其他数据集派生)
      source_dataset_id: string | null
      derivation_rules:                  # 派生规则
        - type: "filter" | "transform" | "join"
          config: dict

  # --- 元数据 ---
  tags: list[string]                    # 标签
  version: integer                      # 数据集版本号
  created_at: string
  updated_at: string
  created_by: string
```

### 2.2 实例: DatasetInstance

```yaml
# Dataset 的实例状态 (运行时)
dataset_instance:
  dataset_id: string
  version: integer

  # --- 统计信息 ---
  stats:
    entity_count: integer                # 实体总数
    relation_count: integer              # 关系总数
    object_type_counts:                  # 按类型统计
      Company: 50
      Borrower: 30
    relation_type_counts:
      Guarantee: 80
      Transaction: 200

  # --- 导入状态 ---
  import_state:
    status: "pending" | "importing" | "completed" | "failed"
    started_at: string | null
    completed_at: string | null
    error_message: string | null
    records_processed: integer
    records_failed: integer

  # --- 关系映射 ---
  entity_dataset_map:                   # entity_id → dataset_id 映射
    - entity_id: string
      dataset_id: string
      imported_at: string
      source_line: integer | null       # 导入来源行号 (文件导入时)

  # --- 版本快照 ---
  snapshot_id: string | null            # 关联的版本快照 ID
```

### 2.3 数据集间关系

```yaml
# Dataset 之间可以有关系
dataset_relation:
  source_dataset_id: string
  target_dataset_id: string
  relation_type: "supplement" | "subset" | "derived_from" | "replaces"
  description: string | null
```

| 关系类型 | 含义 | 示例 |
|----------|------|------|
| `supplement` | 补充关系 | 担保数据集补充企业基础数据 |
| `subset` | 子集 | 准入名单是基础数据的子集 |
| `derived_from` | 派生自 | 风险评分数据集从基础数据派生 |
| `replaces` | 替代 | 新版本数据集替代旧版本 |

## 3. Pydantic 模型

```python
# core/dataset/models.py

class DatasetScope(BaseModel):
    """数据集范围定义。"""
    object_types: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    filters: list[DatasetFilter] = Field(default_factory=list)

class DatasetFilter(BaseModel):
    """数据集过滤条件。"""
    field: str
    operator: Literal["eq", "neq", "gt", "lt", "gte", "lte", "in", "contains"]
    value: Any

class DatasetSource(BaseModel):
    """数据集来源配置。"""
    type: Literal["manual", "file_import", "api_sync", "dataset_derived"]
    config: dict[str, Any] = Field(default_factory=dict)

class DatasetDefinition(BaseModel):
    """数据集声明。"""
    id: str
    name: str
    description: str | None = None
    space_id: str

    scope: DatasetScope = Field(default_factory=DatasetScope)
    source: DatasetSource = Field(default_factory=DatasetSource)

    tags: list[str] = Field(default_factory=list)
    version: int = 1
    created_at: str | None = None
    updated_at: str | None = None
    created_by: str | None = None

class DatasetImportState(BaseModel):
    """数据集导入状态。"""
    status: Literal["pending", "importing", "completed", "failed"] = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    records_processed: int = 0
    records_failed: int = 0

class DatasetStats(BaseModel):
    """数据集统计信息。"""
    entity_count: int = 0
    relation_count: int = 0
    object_type_counts: dict[str, int] = Field(default_factory=dict)
    relation_type_counts: dict[str, int] = Field(default_factory=dict)

class DatasetInstance(BaseModel):
    """数据集运行时实例。"""
    dataset_id: str
    version: int = 1
    stats: DatasetStats = Field(default_factory=DatasetStats)
    import_state: DatasetImportState = Field(default_factory=DatasetImportState)
    snapshot_id: str | None = None
```

## 4. 存储层

### 4.1 DuckDB 表设计

```sql
-- 数据集声明
CREATE TABLE IF NOT EXISTS datasets (
    id VARCHAR PRIMARY KEY,
    space_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    scope_json JSON NOT NULL,           -- DatasetScope 序列化
    source_json JSON NOT NULL,          -- DatasetSource 序列化
    tags JSON DEFAULT '[]',
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR
);

CREATE INDEX idx_datasets_space ON datasets(space_id);

-- 实体-数据集关联 (多对多: 一个实体可属于多个数据集)
CREATE TABLE IF NOT EXISTS entity_dataset_membership (
    entity_id VARCHAR NOT NULL,
    dataset_id VARCHAR NOT NULL,
    concept VARCHAR NOT NULL,            -- 实体类型
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_line INTEGER,                -- 导入行号
    is_primary BOOLEAN DEFAULT FALSE,    -- 是否为主数据集
    PRIMARY KEY (entity_id, dataset_id)
);

CREATE INDEX idx_membership_dataset ON entity_dataset_membership(dataset_id);
CREATE INDEX idx_membership_entity ON entity_dataset_membership(entity_id);

-- 数据集版本快照
CREATE TABLE IF NOT EXISTS dataset_snapshots (
    id VARCHAR PRIMARY KEY,
    dataset_id VARCHAR NOT NULL,
    version INTEGER NOT NULL,
    snapshot_json JSON NOT NULL,        -- 完整快照 (entity_ids + relations)
    entity_count INTEGER,
    relation_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR
);
```

### 4.2 存储接口扩展

```python
# storage/base.py (扩展)

class StorageBackend(ABC):
    # ... 现有方法 ...

    # --- Dataset 管理 (新增) ---
    @abstractmethod
    async def save_dataset(self, dataset: DatasetDefinition) -> str:
        """保存数据集声明。"""

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> DatasetDefinition | None:
        """获取数据集声明。"""

    @abstractmethod
    async def list_datasets(
        self, space_id: str, filters: dict | None = None
    ) -> list[DatasetDefinition]:
        """列出空间下的数据集。"""

    @abstractmethod
    async def delete_dataset(self, dataset_id: str) -> bool:
        """删除数据集 (不删除实体, 只删除关联)。"""

    @abstractmethod
    async def add_entity_to_dataset(
        self, entity_id: str, dataset_id: str,
        concept: str, is_primary: bool = False,
        source_line: int | None = None,
    ) -> None:
        """将实体加入数据集。"""

    @abstractmethod
    async def remove_entity_from_dataset(
        self, entity_id: str, dataset_id: str
    ) -> None:
        """从数据集中移除实体 (不删除实体本身)。"""

    @abstractmethod
    async def get_dataset_entities(
        self, dataset_id: str, concept: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[EntityInstance]:
        """获取数据集中的实体列表。"""

    @abstractmethod
    async def get_entity_datasets(self, entity_id: str) -> list[str]:
        """获取实体所属的数据集 ID 列表。"""

    @abstractmethod
    async def create_dataset_snapshot(
        self, dataset_id: str, created_by: str = "system"
    ) -> str:
        """创建数据集快照, 返回快照 ID。"""
```

## 5. 服务层

```python
# services/dataset_service.py

class DatasetService:
    """数据集管理服务。"""

    def __init__(
        self,
        storage: StorageBackend,
        schema_loader: SchemaLoader,
        instance_loader: InstanceLoader,
    ):
        self.storage = storage
        self.schema_loader = schema_loader
        self.instance_loader = instance_loader

    async def create_dataset(
        self, space_id: str, definition: DatasetDefinition
    ) -> DatasetDefinition:
        """创建数据集。"""
        definition.space_id = space_id
        definition.version = 1
        definition.created_at = datetime.utcnow().isoformat()
        await self.storage.save_dataset(definition)
        return definition

    async def import_from_file(
        self, dataset_id: str, file_path: str,
        file_format: str = "yaml",
    ) -> DatasetImportResult:
        """从文件导入数据到数据集。

        支持格式: YAML (instances.yaml), CSV, JSON

        流程:
        1. 读取文件
        2. 解析为 EntityInstance 列表
        3. 校验实体是否符合空间 Schema
        4. 写入 DuckDB (实体 + 关联)
        5. 更新数据集统计
        """
        dataset = await self.storage.get_dataset(dataset_id)
        if not dataset:
            raise DatasetNotFoundError(dataset_id)

        # 1. 读取文件
        if file_format == "yaml":
            entities, relations = self.instance_loader.load(file_path)
        elif file_format == "csv":
            entities, relations = self._parse_csv(file_path)
        else:
            raise ValueError(f"Unsupported format: {file_format}")

        # 2. 校验 + 3. 写入
        processed = 0
        failed = 0
        for i, entity in enumerate(entities):
            try:
                # 校验属性符合 Schema
                self._validate_entity(entity, dataset.space_id)
                # 写入 DuckDB
                await self.storage.save_entity(entity)
                # 加入数据集
                await self.storage.add_entity_to_dataset(
                    entity_id=entity.entity_id,
                    dataset_id=dataset_id,
                    concept=entity.concept,
                    is_primary=True,
                    source_line=i + 1,
                )
                processed += 1
            except Exception as e:
                failed += 1

        # 4. 更新统计
        stats = await self._compute_stats(dataset_id)
        # 5. 创建快照
        snapshot_id = await self.storage.create_dataset_snapshot(dataset_id)

        return DatasetImportResult(
            dataset_id=dataset_id,
            processed=processed,
            failed=failed,
            snapshot_id=snapshot_id,
            stats=stats,
        )

    async def query_dataset(
        self, dataset_id: str, concept: str | None = None,
        filters: dict | None = None,
    ) -> list[EntityInstance]:
        """在数据集范围内查询实体。"""
        return await self.storage.get_dataset_entities(
            dataset_id, concept=concept
        )

    async def get_intersection(
        self, dataset_a: str, dataset_b: str, concept: str | None = None,
    ) -> list[str]:
        """获取两个数据集的交集 (实体ID列表)。"""
        entities_a = await self.storage.get_dataset_entities(dataset_a, concept)
        ids_a = {e.entity_id for e in entities_a}
        entities_b = await self.storage.get_dataset_entities(dataset_b, concept)
        ids_b = {e.entity_id for e in entities_b}
        return list(ids_a & ids_b)

    async def get_diff(
        self, dataset_a: str, dataset_b: str, concept: str | None = None,
    ) -> DatasetDiff:
        """获取两个数据集的差异。"""
        entities_a = await self.storage.get_dataset_entities(dataset_a, concept)
        entities_b = await self.storage.get_dataset_entities(dataset_b, concept)
        ids_a = {e.entity_id for e in entities_a}
        ids_b = {e.entity_id for e in entities_b}
        return DatasetDiff(
            only_in_a=list(ids_a - ids_b),
            only_in_b=list(ids_b - ids_a),
            common=list(ids_a & ids_b),
        )
```

## 6. API 设计

```
# Dataset CRUD
POST   /v1/management/{spaceId}/datasets
GET    /v1/management/{spaceId}/datasets
GET    /v1/management/{spaceId}/datasets/{datasetId}
PUT    /v1/management/{spaceId}/datasets/{datasetId}
DELETE /v1/management/{spaceId}/datasets/{datasetId}

# Dataset 导入
POST   /v1/management/{spaceId}/datasets/{datasetId}/import
# Body: multipart/form-data (文件) 或 { "file_path": "...", "format": "yaml" }

# Dataset 实体查询
GET    /v1/management/{spaceId}/datasets/{datasetId}/entities
# ?concept=Company&limit=50&offset=0

# Dataset 统计
GET    /v1/management/{spaceId}/datasets/{datasetId}/stats

# Dataset 快照
POST   /v1/management/{spaceId}/datasets/{datasetId}/snapshots
GET    /v1/management/{spaceId}/datasets/{datasetId}/snapshots
GET    /v1/management/{spaceId}/datasets/{datasetId}/snapshots/{snapshotId}

# Dataset 对比
GET    /v1/management/{spaceId}/datasets/diff
# ?dataset_a=xxx&dataset_b=yyy

# 实体的数据集归属
GET    /v1/management/{spaceId}/entities/{entityId}/datasets
```

## 7. 文件结构

```
ontology_engine/
├── core/
│   ├── dataset/
│   │   ├── __init__.py
│   │   ├── models.py              # DatasetDefinition, DatasetStats, etc.
│   │   └── loader.py              # CSV/JSON/YAML 解析器
│   └── ...
├── services/
│   └── dataset_service.py          # DatasetService
└── api/routes/
    └── datasets.py                 # Dataset API 路由
```

## 8. 验收场景

### 场景 1: 创建数据集 + 文件导入

```
Given: 空间 supply_chain_finance, entities.yaml 含 8 个 Company
When: 创建数据集 "企业基础数据" 并导入 entities.yaml
Then:
  - Dataset 记录已创建, version=1
  - 8 个实体已写入 DuckDB
  - entity_dataset_membership 有 8 条记录
  - 统计: entity_count=8, Company=8
```

### 场景 2: 数据集范围查询

```
Given: 数据集 "企业基础数据" 含 8 个 Company
When: GET /datasets/{id}/entities?concept=Company
Then: 返回 8 个 Company 实体
```

### 场景 3: 数据集对比

```
Given: 数据集 A (50个Company), 数据集 B (30个Company, A的子集)
When: GET /datasets/diff?dataset_a=A&dataset_b=B
Then:
  - only_in_a: 20 个 entity_id
  - only_in_b: 0 个
  - common: 30 个
```

### 场景 4: 版本快照

```
Given: 数据集 version=1, 含 8 个实体
When: 更新数据集 (删除2个实体) + 创建快照
Then:
  - 新快照包含原始 8 个 entity_id
  - 当前数据集统计 entity_count=6
  - 可通过 snapshot_id 查看历史数据
```

---

*文档结束*
