# 模块 01: Schema 加载与校验

> **位置**: `ontology_engine/core/schema/`
> **依赖**: Pydantic, PyYAML
> **被依赖**: InstanceLoader, MetricEngine, RuleEngine, CategorizationEngine

## 1. 职责

1. **解析 KGML YAML** → Pydantic 模型
2. **Schema 校验** — 结构合法性 + 语义一致性
3. **v1 / v2 兼容** — 统一内部模型，对外透明
4. **Schema 版本管理** — 快照存储与回滚

## 2. 数据模型

### 2.1 统一内部模型

无论 v1 还是 v2 格式的 Schema，解析后都映射到统一内部模型：

```python
# core/schema/models.py

class KGMLSchema(BaseModel):
    """统一 Schema 模型 — v1/v2 解析后的内部表示"""
    
    # --- 元信息 ---
    metadata: SchemaMetadata
    
    # --- L1: 事实对象 ---
    entities: list[EntityDefinition]       # v1: concepts[category=entity]
    relations: list[RelationDefinition]    # v1: concepts[category=relation]
    types: list[TypeDefinition]            # 自定义类型
    enums: list[EnumDefinition]            # 枚举类型
    
    # --- L2: 归类维度 ---
    categories: list[CategoryDimension]    # v2: categorization.dimensions
    
    # --- L3: 分析指标 ---
    metrics: list[MetricDefinition]        # v1: metrics / v2: analytical_elements.metrics
    
    # --- L4: 业务规则 ---
    rule_dimensions: list[RuleDimension]   # 维度定义
    rules: list[RuleDefinition]            # 规则定义
    
    # --- 辅助 ---
    data_sources: list[DataSourceMapping]  # 数据源映射 (Phase 2)
    vector_config: VectorConfig | None     # 向量配置
    llm_config: LLMConfig | None          # LLM 配置


class SchemaMetadata(BaseModel):
    id: str
    name: str
    version: str
    schema_version: str = "1.0"           # KGML 格式版本
    domain: str = ""
    language: list[str] = ["zh"]
    created_at: datetime | None = None
    modified_at: datetime | None = None


class EntityDefinition(BaseModel):
    """实体定义 (L1 事实对象)"""
    name: str
    description: str = ""
    category: str = "entity"               # entity | relation
    attributes: list[AttributeDefinition]
    relations: list[RelationRef] = []      # 出边关系引用
    vector_config: VectorFieldConfig | None = None


class AttributeDefinition(BaseModel):
    """属性定义"""
    name: str
    type: str                              # string, integer, float, Money, Percentage, ...
    required: bool = False
    unique: bool = False
    default: Any = None
    description: str = ""
    derived: bool = False                  # 是否为派生属性
    calculation: dict | None = None        # 派生属性的计算逻辑
    validation: dict | None = None         # 校验规则 (pattern, min, max, ...)
    enum_type: str | None = None           # 引用枚举类型名
    vector_config: VectorFieldConfig | None = None


class RelationDefinition(BaseModel):
    """关系定义"""
    name: str
    from_entity: str
    to_entity: str
    attributes: list[AttributeDefinition] = []
    cardinality: str = "0..*"
    inverse: str | None = None


class RelationRef(BaseModel):
    """实体中的关系引用"""
    name: str
    target: str
    cardinality: str = "0..*"
    inverse: str | None = None
    description: str = ""


class CategoryDimension(BaseModel):
    """L2 归类维度"""
    name: str
    type: str                              # hierarchical | derived | tags
    description: str = ""
    applicable_entities: list[str] = []
    values: list[str] | None = None        # hierarchical/tags 的可选值
    ruleset: str | None = None             # derived 类型的规则集名称


class MetricDefinition(BaseModel):
    """L3 分析指标"""
    name: str
    description: str = ""
    type: str = "float"                    # 返回类型
    scope: str = ""                        # 适用的实体类型
    metric_type: Literal["atomic", "derived", "composite", "graph"]
    
    # derived
    formula: str | None = None
    dependencies: list[str] = []
    risk_threshold: dict | None = None     # {warning: N, critical: N}
    
    # composite
    components: list[MetricComponent] | None = None
    output_range: tuple[float, float] | None = None
    
    # graph
    algorithm: str | None = None           # longest_path, page_rank, ...
    graph_query: str | None = None
    timeout: int = 30000
    
    # scope_dimensions
    scope_dimensions: list[str] = []       # 仅在特定维度下计算


class MetricComponent(BaseModel):
    """复合指标的组成"""
    metric: str
    weight: float = 1.0
    transform: str | None = None           # "value / 100", "min(value*100, 100)/100"


class RuleDimension(BaseModel):
    """规则维度定义"""
    name: str
    description: str = ""
    applicable_entities: list[str]
    triggers: list[dict] = []


class RuleDefinition(BaseModel):
    """L4 业务规则"""
    id: str
    name: str = ""
    description: str = ""
    type: str = "inference"                # constraint | inference | alert | decision
    priority: int = 0
    enabled: bool = True
    
    scope: dict = {}                       # {dimensions: [], entity_types: []}
    when: ConditionClause | None = None
    then: ActionClause | None = None
    else_: ActionClause | None = None      # Python 保留字用 else_
    
    # v2 扩展
    depends_on: list[str] = []             # 依赖的规则ID (显式DAG边)


class ConditionClause(BaseModel):
    """条件子句"""
    expression: str | None = None
    all_of: list[str] | None = None
    any_of: list[str] | None = None
    graph_query: str | None = None


class ActionClause(BaseModel):
    """动作子句"""
    action: str | None = None
    output: dict = {}
    computation: dict | None = None        # {formula: str, operator: str, ...}


class TypeDefinition(BaseModel):
    """自定义类型"""
    name: str
    description: str = ""
    base_type: str                         # string, integer, float, object
    properties: dict | None = None         # object 类型的属性
    min: float | None = None
    max: float | None = None
    enum: list[str] | None = None
    default: Any = None


class EnumDefinition(BaseModel):
    """枚举类型"""
    name: str
    description: str = ""
    values: list[EnumValue]


class EnumValue(BaseModel):
    id: str
    label: str = ""
    weight: float = 1.0
    severity_score: int = 1
    color: str | None = None
    description: str | None = None
```

### 2.2 v1 → v2 兼容映射

```python
# core/schema/v1_compat.py

class V1CompatMapper:
    """将 v1 格式 Schema 映射为统一内部模型"""
    
    def map_v1_to_unified(raw: dict) -> KGMLSchema:
        """
        v1 → 统一模型映射规则:
        
        concepts[category=entity]  → entities
        concepts[category=relation] → relations
        metrics                    → metrics (metric_type 保留)
        rules.rule_dimensions      → rule_dimensions
        rules.ruleset              → rules
        enums                      → enums
        types                      → types
        
        v1 独有字段处理:
        - dimension_attributes → 拆解为 L3 指标的 scope_dimensions
        - data_source → 保留但 Phase 2 实现
        - vector_config → 保留
        - llm_config → 保留
        """
        ...
```

## 3. SchemaLoader 实现

```python
# core/schema/loader.py

class SchemaLoader:
    """Schema 加载器 — 支持 v1 和 v2 格式"""
    
    def load(self, path: str | Path) -> KGMLSchema:
        """加载 Schema 文件
        
        自动检测版本:
        - 有 fact_objects 字段 → v2
        - 有 concepts 字段 → v1
        """
        raw = self._read_yaml(path)
        version = self._detect_version(raw)
        
        if version == "2.0":
            return self._parse_v2(raw)
        else:
            return V1CompatMapper.map_v1_to_unified(raw)
    
    def _detect_version(self, raw: dict) -> str:
        """检测 Schema 版本"""
        if "fact_objects" in raw:
            return "2.0"
        if "concepts" in raw:
            return "1.0"
        raise SchemaError("无法识别的 Schema 格式")
    
    def _parse_v2(self, raw: dict) -> KGMLSchema:
        """解析 v2 四层分离格式"""
        # L1
        entities = self._parse_entities(raw.get("fact_objects", {}))
        relations = self._parse_relations(raw.get("fact_objects", {}))
        
        # L2
        categories = self._parse_categories(raw.get("categorization", {}))
        
        # L3
        metrics = self._parse_metrics(raw.get("analytical_elements", {}))
        
        # L4
        rule_dims, rules = self._parse_business_logic(raw.get("business_logic", {}))
        
        return KGMLSchema(
            metadata=self._parse_metadata(raw.get("metadata", {})),
            entities=entities,
            relations=relations,
            categories=categories,
            metrics=metrics,
            rule_dimensions=rule_dims,
            rules=rules,
            types=self._parse_types(raw.get("types", [])),
            enums=self._parse_enums(raw.get("enums", [])),
        )
    
    def validate(self, schema: KGMLSchema) -> list[ValidationIssue]:
        """Schema 校验"""
        issues = []
        
        # 1. 结构校验
        issues.extend(self._validate_structure(schema))
        
        # 2. 引用完整性
        issues.extend(self._validate_references(schema))
        
        # 3. 依赖无环
        issues.extend(self._validate_dag(schema))
        
        # 4. 类型兼容性
        issues.extend(self._validate_types(schema))
        
        return issues
    
    def _validate_references(self, schema: KGMLSchema) -> list[ValidationIssue]:
        """引用完整性校验"""
        issues = []
        entity_names = {e.name for e in schema.entities}
        metric_names = {m.name for m in schema.metrics}
        
        # 关系引用的实体必须存在
        for rel in schema.relations:
            if rel.from_entity not in entity_names:
                issues.append(ValidationIssue(
                    level="error",
                    message=f"关系 {rel.name} 引用了不存在的实体 {rel.from_entity}"
                ))
            if rel.to_entity not in entity_names:
                issues.append(ValidationIssue(
                    level="error",
                    message=f"关系 {rel.name} 引用了不存在的实体 {rel.to_entity}"
                ))
        
        # 指标依赖必须存在
        for metric in schema.metrics:
            for dep in metric.dependencies:
                if dep not in metric_names and dep not in entity_names:
                    issues.append(ValidationIssue(
                        level="warning",
                        message=f"指标 {metric.name} 依赖了未定义的 {dep}"
                    ))
        
        return issues
    
    def _validate_dag(self, schema: KGMLSchema) -> list[ValidationIssue]:
        """依赖 DAG 无环校验"""
        # 构建指标依赖图
        G = nx.DiGraph()
        for m in schema.metrics:
            G.add_node(m.name)
            for dep in m.dependencies:
                G.add_edge(dep, m.name)
        
        if not nx.is_directed_acyclic_graph(G):
            cycles = list(nx.simple_cycles(G))
            return [ValidationIssue(
                level="error",
                message=f"指标依赖存在循环: {cycles}"
            )]
        return []


@dataclass
class ValidationIssue:
    level: str     # error | warning | info
    message: str
    location: str = ""


class SchemaError(Exception):
    """Schema 加载/校验错误"""
    pass
```

## 4. Schema 版本管理

```python
# core/schema/version_manager.py

class SchemaVersionManager:
    """Schema 版本管理 (决策 #8: 全量快照策略)"""
    
    def __init__(self, storage: DuckDBStorage):
        self.storage = storage
    
    def commit(
        self,
        schema: KGMLSchema,
        description: str,
        actor: str = "system"
    ) -> SchemaVersion:
        """提交新版本"""
        version_num = self._next_version()
        snapshot = SchemaVersion(
            id=f"sv_{version_num}",
            version=version_num,
            schema_snapshot=schema.model_dump_json(),
            change_description=description,
            created_by=actor,
            created_at=datetime.now()
        )
        self.storage.save_schema_version(snapshot)
        return snapshot
    
    def rollback(self, target_version: int) -> KGMLSchema:
        """回滚到指定版本"""
        snapshot = self.storage.get_schema_version(target_version)
        return KGMLSchema.model_validate_json(snapshot.schema_snapshot)
    
    def diff(self, v1: int, v2: int) -> SchemaDiff:
        """比较两个版本差异"""
        s1 = self._load_version(v1)
        s2 = self._load_version(v2)
        return SchemaDiffComputer.compute(s1, s2)
    
    def impact_analysis(self, target_version: int) -> ImpactReport:
        """影响分析"""
        current = self._load_current()
        target = self._load_version(target_version)
        diff = SchemaDiffComputer.compute(target, current)
        return ImpactReport(
            added_entities=diff.added_entities,
            removed_entities=diff.removed_entities,
            changed_rules=diff.changed_rules,
            affected_metrics=diff.changed_metrics,
            risk_level=self._assess_risk(diff)
        )
```

## 5. 与供应链金融场景的对接

```python
# 使用示例
loader = SchemaLoader()
schema = loader.load("examples/supply_chain_finance/schema.yaml")

# 自动识别为 v1 格式，映射为统一模型
# schema.entities = [Supplier, CoreEnterprise, Invoice, Contract, LogisticsRecord, GuaranteeRelation]
# schema.metrics = [total_invoice_amount_90d, overdue_invoice_ratio, credit_score, ...]
# schema.rules = [R001_basic_eligibility, R002_credit_score_calculation, ...]
# schema.rule_dimensions = [credit_assessment, transaction_monitoring, risk_early_warning]

# 校验
issues = loader.validate(schema)
for issue in issues:
    if issue.level == "error":
        raise SchemaError(issue.message)
```

## 6. 文件结构

```
ontology_engine/core/schema/
├── __init__.py              # 导出 KGMLSchema, SchemaLoader
├── models.py                # 统一内部模型 (上面定义)
├── loader.py                # SchemaLoader + V1/V2 解析
├── v1_compat.py             # v1 → 统一模型映射
├── validator.py             # 校验逻辑
├── version_manager.py       # 版本管理
└── diff.py                  # Schema 差异计算
```

## 7. 代码映射

| 设计组件 | 实际代码路径 | 实现状态 |
|---------|-------------|---------|
| KGMLSchema 模型 | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| SchemaMetadata | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| ConceptDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| AttributeDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| RelationDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| TypeDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| EnumDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| MetricDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| RuleDefinition | `ontology_engine/core/schema/models.py` | ✅ 已实现 |
| SchemaLoader | `ontology_engine/core/schema/loader.py` | ✅ 已实现 |
| Schema 验证 | `ontology_engine/core/schema/loader.py` | ⚠️ 部分实现 (基础验证已实现) |
| V1/V2 版本检测 | `ontology_engine/core/schema/loader.py` | ⚠️ 部分实现 (当前仅支持v1格式) |
| v1_compat 映射 | `ontology_engine/core/schema/v1_compat.py` | ⏭️ 待实现 |
| 版本管理器 | `ontology_engine/core/schema/version_manager.py` | ⏭️ 待实现 |
| 差异计算 | `ontology_engine/core/schema/diff.py` | ⏭️ 待实现 |

## 8. 测试要点

- [ ] Schema 解析测试 - YAML 文件正确解析为 Pydantic 模型
- [ ] 元数据解析测试 - metadata 字段完整提取
- [ ] Concepts 解析测试 - 实体和关系概念正确解析
- [ ] Attributes 解析测试 - 属性定义（类型、必填、默认值等）
- [ ] Relations 解析测试 - 关系引用和目标实体
- [ ] Types 解析测试 - 自定义类型定义解析
- [ ] Enums 解析测试 - 枚举值和权重解析
- [ ] Metrics 解析测试 - 指标定义和依赖关系
- [ ] Rules 解析测试 - 规则维度、条件和动作解析
- [ ] 重复概念名称验证测试
- [ ] 重复枚举名称验证测试
- [ ] 关系引用有效性验证测试 - 引用的概念必须存在
- [ ] 属性类型有效性验证测试 - 类型必须已定义或为内置类型
- [ ] 空 Schema 文件错误处理测试
- [ ] 缺失 Schema 文件错误处理测试
