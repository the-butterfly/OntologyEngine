# 模块 02: 实例加载与实体管理

> **位置**: `ontology_engine/core/instances/`, `ontology_engine/storage/`, `ontology_engine/services/`
> **依赖**: SchemaLoader, DuckDBStorage
> **被依赖**: MetricEngine, RuleEngine, CategorizationEngine, EntityService

## 1. 职责

1. **实例 YAML 加载** → Entity[] + Relation[]
2. **属性校验** — 基于 Schema 定义校验实例数据
3. **实体 CRUD** — 创建/读取/更新/删除
4. **批量导入** — 事务性批量操作
5. **关系管理** — 创建/查询邻居/图遍历

## 2. 数据模型

### 2.1 实体与关系

```python
# core/instances/models.py

class Entity(BaseModel):
    """实体实例"""
    id: str                                # 实体唯一 ID
    concept_type: str                      # 对应 EntityDefinition.name
    attributes: dict[str, Any]             # 属性值 {name: value}
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 运行时字段 (不持久化)
    _category_tags: dict[str, str] = {}    # L2 归类标签
    _computed_metrics: dict[str, Any] = {} # L3 计算指标
    _rule_outputs: dict[str, Any] = {}     # L4 规则输出
    
    class Config:
        arbitrary_types_allowed = True


class Relation(BaseModel):
    """关系实例 (边)"""
    id: str                                # 关系唯一 ID
    relation_type: str                     # 对应 RelationDefinition.name
    from_id: str                           # 起始实体 ID
    to_id: str                             # 目标实体 ID
    attributes: dict[str, Any] = {}        # 关系属性
    created_at: datetime = Field(default_factory=datetime.now)


class InstanceData(BaseModel):
    """instances.yaml 的完整结构"""
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
```

### 2.2 实体查询

```python
# storage/models.py

class EntityFilter(BaseModel):
    """实体过滤条件"""
    concept_type: str | None = None
    attributes: dict[str, FilterCondition] = {}
    
class FilterCondition(BaseModel):
    """单字段过滤"""
    eq: Any | None = None
    neq: Any | None = None
    gt: float | None = None
    gte: float | None = None
    lt: float | None = None
    lte: float | None = None
    in_: list[Any] | None = None           # Python in 是保留字
    contains: str | None = None

class PaginatedResult(BaseModel):
    """分页结果"""
    items: list[Entity]
    total: int
    offset: int
    limit: int
```

## 3. InstanceLoader 实现

```python
# core/instances/loader.py

class InstanceLoader:
    """实例数据加载器"""
    
    def __init__(self, schema: KGMLSchema):
        self.schema = schema
        self._entity_defs = {e.name: e for e in schema.entities}
        self._relation_defs = {r.name: r for r in schema.relations}
    
    def load(self, path: str | Path) -> tuple[list[Entity], list[Relation]]:
        """加载实例 YAML 文件
        
        Returns:
            (entities, relations) 元组
        """
        raw = self._read_yaml(path)
        data = InstanceData(**raw)
        
        entities = []
        for item in data.entities:
            entity = self._parse_entity(item)
            entities.append(entity)
        
        relations = []
        for item in data.relations:
            relation = self._parse_relation(item)
            relations.append(relation)
        
        return entities, relations
    
    def _parse_entity(self, raw: dict) -> Entity:
        """解析单个实体"""
        concept_type = raw.get("concept") or raw.get("_concept", "")
        
        # 提取实体 ID
        entity_id = self._extract_entity_id(concept_type, raw)
        
        # 提取属性 (排除元数据字段)
        meta_keys = {"concept", "_concept", "active_dimensions", "_id"}
        attributes = {k: v for k, v in raw.items() if k not in meta_keys}
        
        # 校验属性
        self._validate_attributes(concept_type, attributes)
        
        return Entity(
            id=entity_id,
            concept_type=concept_type,
            attributes=attributes
        )
    
    def _extract_entity_id(self, concept_type: str, raw: dict) -> str:
        """从实例数据中提取实体唯一标识
        
        按照命名约定: {concept_type_lower}_{id_field}
        Supplier → supplier_id
        Invoice → invoice_no
        """
        entity_def = self._entity_defs.get(concept_type)
        if entity_def:
            for attr in entity_def.attributes:
                if attr.unique and attr.required:
                    if attr.name in raw:
                        return str(raw[attr.name])
        
        # 回退: 查找常见的 ID 字段
        for key in ["id", "supplier_id", "enterprise_id", "invoice_no", "contract_no"]:
            if key in raw:
                return str(raw[key])
        
        raise InstanceLoadError(
            f"无法确定实体ID: concept={concept_type}, keys={list(raw.keys())}"
        )
    
    def _validate_attributes(self, concept_type: str, attributes: dict):
        """基于 Schema 校验属性"""
        entity_def = self._entity_defs.get(concept_type)
        if not entity_def:
            return  # 未定义的概念跳过校验
        
        attr_defs = {a.name: a for a in entity_def.attributes}
        
        # 检查必需属性
        for attr_def in entity_def.attributes:
            if attr_def.required and attr_def.name not in attributes:
                # 派生属性不需要提供
                if not attr_def.derived:
                    raise InstanceLoadError(
                        f"实体 {concept_type} 缺少必需属性: {attr_def.name}"
                    )
        
        # 检查类型兼容性 (宽松模式 — 只检查明显错误)
        for name, value in attributes.items():
            attr_def = attr_defs.get(name)
            if attr_def and attr_def.enum_type:
                # 枚举值检查
                enum_def = next(
                    (e for e in self.schema.enums if e.name == attr_def.enum_type),
                    None
                )
                if enum_def:
                    valid_values = {v.id for v in enum_def.values}
                    if value not in valid_values:
                        raise InstanceLoadError(
                            f"属性 {name} 的值 '{value}' 不在枚举 {attr_def.enum_type} 中"
                        )
    
    def _parse_relation(self, raw: dict) -> Relation:
        """解析关系"""
        relation_type = raw.get("type", raw.get("relation_type", ""))
        from_id = str(raw.get("from", raw.get("from_id", "")))
        to_id = str(raw.get("to", raw.get("to_id", "")))
        
        meta_keys = {"type", "relation_type", "from", "from_id", "to", "to_id"}
        attributes = {k: v for k, v in raw.items() if k not in meta_keys}
        
        # 生成关系 ID
        relation_id = f"{relation_type}:{from_id}->{to_id}"
        
        return Relation(
            id=relation_id,
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            attributes=attributes
        )


class InstanceLoadError(Exception):
    """实例加载错误"""
    pass
```

## 4. DuckDBStorage 实体管理

```python
# storage/duckdb/store.py (增强版)

class DuckDBStorage:
    """DuckDB 主存储"""
    
    async def initialize(self) -> None:
        """初始化数据库表"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id VARCHAR PRIMARY KEY,
                concept_type VARCHAR NOT NULL,
                attributes JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id VARCHAR PRIMARY KEY,
                from_id VARCHAR NOT NULL,
                to_id VARCHAR NOT NULL,
                relation_type VARCHAR NOT NULL,
                attributes JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS computed_metrics (
                entity_id VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                metric_value JSON,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity_id, metric_name)
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS category_tags (
                entity_id VARCHAR NOT NULL,
                dimension VARCHAR NOT NULL,
                value VARCHAR NOT NULL,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity_id, dimension)
            )
        """)
        # 索引
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(concept_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(relation_type)")
    
    # --- Entity CRUD ---
    
    async def save_entity(self, entity: Entity) -> str:
        """保存实体 (INSERT OR REPLACE)"""
        self._conn.execute("""
            INSERT OR REPLACE INTO entities (id, concept_type, attributes, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, [entity.id, entity.concept_type, json.dumps(entity.attributes)])
        return entity.id
    
    async def get_entity(self, concept_type: str, entity_id: str) -> Entity | None:
        """获取实体"""
        result = self._conn.execute("""
            SELECT id, concept_type, attributes, created_at, updated_at
            FROM entities WHERE id = ? AND concept_type = ?
        """, [entity_id, concept_type]).fetchone()
        
        if not result:
            return None
        
        return Entity(
            id=result[0],
            concept_type=result[1],
            attributes=json.loads(result[2])
        )
    
    async def query_entities(
        self,
        concept_type: str | None = None,
        filters: EntityFilter | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> PaginatedResult:
        """条件查询实体
        
        利用 DuckDB 的 JSON 路径查询:
        WHERE attributes->>'$.status' = 'ACTIVE'
        """
        conditions = []
        params = []
        
        if concept_type:
            conditions.append("concept_type = ?")
            params.append(concept_type)
        
        if filters and filters.attributes:
            for field, cond in filters.attributes.items():
                if cond.eq is not None:
                    conditions.append(f"attributes->>'$.{field}' = ?")
                    params.append(str(cond.eq))
                elif cond.gte is not None:
                    conditions.append(f"CAST(attributes->>'$.{field}' AS DOUBLE) >= ?")
                    params.append(cond.gte)
                # ... 其他操作符
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 计数
        count = self._conn.execute(
            f"SELECT COUNT(*) FROM entities WHERE {where_clause}", params
        ).fetchone()[0]
        
        # 查询
        rows = self._conn.execute(
            f"SELECT id, concept_type, attributes FROM entities WHERE {where_clause} LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        
        entities = [
            Entity(id=r[0], concept_type=r[1], attributes=json.loads(r[2]))
            for r in rows
        ]
        
        return PaginatedResult(items=entities, total=count, offset=offset, limit=limit)
    
    async def delete_entity(self, entity_id: str) -> bool:
        """删除实体及其关联边"""
        self._conn.execute("DELETE FROM edges WHERE from_id = ? OR to_id = ?", [entity_id, entity_id])
        self._conn.execute("DELETE FROM computed_metrics WHERE entity_id = ?", [entity_id])
        self._conn.execute("DELETE FROM category_tags WHERE entity_id = ?", [entity_id])
        result = self._conn.execute("DELETE FROM entities WHERE id = ?", [entity_id])
        return result.fetchone() is not None
    
    # --- Edge CRUD ---
    
    async def save_relation(self, relation: Relation) -> str:
        """保存关系"""
        self._conn.execute("""
            INSERT OR REPLACE INTO edges (id, from_id, to_id, relation_type, attributes)
            VALUES (?, ?, ?, ?, ?)
        """, [relation.id, relation.from_id, relation.to_id,
              relation.relation_type, json.dumps(relation.attributes)])
        return relation.id
    
    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        direction: str = "both",
        limit: int = 100
    ) -> list[tuple[Entity, Relation]]:
        """获取邻居实体和关系
        
        Args:
            direction: "outgoing" | "incoming" | "both"
        """
        conditions = []
        params = []
        
        if direction in ("outgoing", "both"):
            conditions.append("from_id = ?")
            params.append(entity_id)
        if direction in ("incoming", "both"):
            conditions.append("to_id = ?")
            params.append(entity_id)
        
        where_dir = " OR ".join(conditions)
        
        if relation_type:
            where_dir += " AND relation_type = ?"
            params.append(relation_type)
        
        edges = self._conn.execute(
            f"SELECT id, from_id, to_id, relation_type, attributes FROM edges WHERE {where_dir} LIMIT ?",
            params + [limit]
        ).fetchall()
        
        results = []
        for edge_row in edges:
            rel = Relation(
                id=edge_row[0], from_id=edge_row[1], to_id=edge_row[2],
                relation_type=edge_row[3], attributes=json.loads(edge_row[4])
            )
            # 获取对端实体
            neighbor_id = edge_row[2] if edge_row[1] == entity_id else edge_row[1]
            neighbor = await self.get_entity_by_id(neighbor_id)
            if neighbor:
                results.append((neighbor, rel))
        
        return results
    
    # --- Metrics 持久化 ---
    
    async def save_metric(self, entity_id: str, name: str, value: Any) -> None:
        """保存计算指标"""
        self._conn.execute("""
            INSERT OR REPLACE INTO computed_metrics (entity_id, metric_name, metric_value, computed_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, [entity_id, name, json.dumps(value)])
    
    async def get_metric(self, entity_id: str, name: str) -> Any | None:
        """获取已计算的指标"""
        result = self._conn.execute(
            "SELECT metric_value FROM computed_metrics WHERE entity_id = ? AND metric_name = ?",
            [entity_id, name]
        ).fetchone()
        return json.loads(result[0]) if result else None
    
    # --- Category Tags 持久化 ---
    
    async def save_category_tag(self, entity_id: str, dimension: str, value: str) -> None:
        """保存归类标签"""
        self._conn.execute("""
            INSERT OR REPLACE INTO category_tags (entity_id, dimension, value, computed_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, [entity_id, dimension, value])
    
    async def get_category_tags(self, entity_id: str) -> dict[str, str]:
        """获取实体所有归类标签"""
        rows = self._conn.execute(
            "SELECT dimension, value FROM category_tags WHERE entity_id = ?",
            [entity_id]
        ).fetchall()
        return {r[0]: r[1] for r in rows}
```

## 5. 供应链金融场景数据流

```
instances.yaml
    │
    ├─ entities:
    │   ├─ Supplier (SUP_2024_001)  → Entity(id="SUP_2024_001", concept_type="Supplier", attributes={...})
    │   ├─ Supplier (SUP_2024_002)  → Entity(id="SUP_2024_002", ...)
    │   ├─ Invoice (INV_001)        → Entity(id="INV_001", concept_type="Invoice", ...)
    │   └─ Contract (CTR_001)       → Entity(id="CTR_001", concept_type="Contract", ...)
    │
    └─ relations:
        ├─ {type: "has_invoice", from: "SUP_2024_001", to: "INV_001"}
        ├─ {type: "guarantees_for", from: "SUP_2024_001", to: "SUP_2024_002"}
        └─ ...
                │
                ▼
        DuckDBStorage.save_entity() × N
        DuckDBStorage.save_relation() × N
                │
                ▼
        entities 表: 5 rows
        edges 表: 8 rows
```

## 6. 文件结构

```
ontology_engine/
├── core/
│   └── instances/
│       ├── __init__.py
│       ├── models.py          # Entity, Relation, InstanceData
│       └── loader.py          # InstanceLoader + 属性校验
│
├── storage/
│   ├── base.py               # StorageBackend 接口
│   └── duckdb/
│       └── store.py           # DuckDBStorage (增强版)
│
└── services/
    └── entity_service.py      # EntityService (见 09-services-layer.md)
```
