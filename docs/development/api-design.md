# API 设计: OntologyEngine MVP

> **⚠️ 注意**: 本文档为 MVP 阶段的开发者实现指南。API 设计规格请参考：
> - [02-design/02-api-design.md](../02-design/02-api-design.md)
> - Agent 接口：[07-agent-interface.md](../07-agent-interface.md)

## 背景

MVP 实现以配置为核心，通过 YAML 配置文件定义 schema、instances 和 rules。OntologyEngine 本身是工具链，不包含内置配置。

## 核心接口

### OntologyEngine - 主入口

```python
class OntologyEngine:
    """主引擎类"""

    @classmethod
    def from_config(cls, schema_path: str) -> "OntologyEngine":
        """从 schema.yaml 创建引擎实例"""
        pass

    async def load_instances(self, instances_path: str) -> None:
        """加载实例数据"""
        pass

    async def analyze(
        self,
        entity_id: str,
        dimension: str
    ) -> AnalysisResult:
        """执行维度分析"""
        pass

    async def query(
        self,
        concept: str,
        filters: dict | None = None
    ) -> list[Entity]:
        """查询实体"""
        pass
```

### SchemaLoader - Schema 加载

```python
class SchemaLoader:
    """KGML Schema 加载器"""

    def load(self, path: str) -> KGMLSchema:
        """从 YAML 文件加载 KGML Schema"""
        pass

    def validate(self, schema: KGMLSchema) -> ValidationResult:
        """验证 Schema 合法性"""
        pass
```

### KGMLSchema - Schema 数据模型

```python
@dataclass
class KGMLSchema:
    """KGML Schema 完整模型"""
    metadata: SchemaMetadata
    types: list[TypeDefinition]
    enums: list[EnumDefinition]
    concepts: list[ConceptDefinition]
    metrics: list[MetricDefinition]
    rules: RulesDefinition
    data_sources: list[DataSourceDefinition]
    vector_config: VectorConfig
    llm_config: LLMConfig

@dataclass
class ConceptDefinition:
    """概念定义"""
    name: str
    description: str
    category: str  # "entity" | "relation"
    attributes: list[AttributeDefinition]
    relations: list[RelationDefinition]

    # 注意: dimension_attributes 已移除
    # 派生属性在 metrics/rules 中定义，按需计算

@dataclass
class AttributeDefinition:
    """属性定义"""
    name: str
    type: str
    required: bool = False
    unique: bool = False
    description: str = ""
    validation: dict | None = None
```

### InstanceLoader - 实例加载

```python
class InstanceLoader:
    """实例数据加载器"""

    def load(self, path: str) -> list[EntityInstance]:
        """从 YAML 文件加载实例"""
        pass

    async def save(self, path: str, entities: list[EntityInstance]) -> None:
        """保存实例到文件"""
        pass

@dataclass
class EntityInstance:
    """实体实例"""
    concept: str
    data: dict
```

### RuleEngine - 规则引擎

```python
class RuleEngine:
    """规则引擎 - 加载并执行 YAML 规则"""

    def load_rules(self, rules: RulesDefinition) -> None:
        """加载规则定义"""
        pass

    async def execute_rule(
        self,
        rule_id: str,
        context: ExecutionContext
    ) -> RuleResult:
        """执行单条规则"""
        pass

    async def execute_dimension(
        self,
        dimension: str,
        entity: EntityInstance,
        context: ExecutionContext
    ) -> list[RuleResult]:
        """执行维度下所有规则"""
        pass

    async def analyze(
        self,
        entity_id: str,
        dimension: str
    ) -> AnalysisResult:
        """完整维度分析"""
        pass
```

### ExpressionEvaluator - 表达式求值器

```python
class ExpressionEvaluator:
    """简单表达式求值器"""

    def evaluate(
        self,
        expression: str,
        context: dict
    ) -> Any:
        """求值表达式

        支持:
        - 比较: ==, !=, >, <, >=, <=
        - 逻辑: and, or, not
        - 字段访问: supplier.status, invoice.amount.value
        - 函数: today(), days_between(), sum(), avg()

        不支持 (Future):
        - Graph queries (Cypher)
        - 复杂嵌套表达式
        - DAG 依赖解析
        """
        pass
```

### Storage - 存储层 (DuckDB)

```python
class StorageBackend(ABC):
    """存储后端抽象"""

    async def save_entity(self, entity: EntityInstance) -> str:
        """保存实体，返回ID"""
        pass

    async def get_entity(self, concept: str, entity_id: str) -> EntityInstance | None:
        """获取实体"""
        pass

    async def query_entities(
        self,
        concept: str,
        filters: dict | None = None
    ) -> list[EntityInstance]:
        """查询实体列表"""
        pass

    async def save_relation(self, relation: RelationInstance) -> None:
        """保存关系"""
        pass

    async def query_relations(
        self,
        source_id: str,
        relation_type: str | None = None
    ) -> list[RelationInstance]:
        """查询关系"""
        pass


class DuckDBStorage(StorageBackend):
    """DuckDB 存储实现"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn: duckdb.DuckDBPyConnection

    async def initialize(self) -> None:
        """初始化数据库表结构"""
        pass
```

---

## 输入

### Schema YAML 结构

```yaml
# examples/supply_chain_finance/schema.yaml

metadata:
  id: "kg://supply-chain/finance/credit-assessment/1.0"
  version: "1.0.0"

types:
  - name: "Money"
    base_type: "object"
    properties:
      value: { type: "decimal" }
      currency: { type: "string", default: "CNY" }

enums:
  - name: "SupplierStatus"
    values:
      - id: "ACTIVE"
      - id: "SUSPENDED"

concepts:
  - name: "Supplier"
    category: "entity"
    attributes:
      - name: "supplier_id"
        type: "string"
        required: true
        unique: true
      - name: "company_name"
        type: "string"
      - name: "status"
        type: "SupplierStatus"
    relations:
      - name: "has_invoice"
        target: "Invoice"
        cardinality: "0..*"

rules:
  rule_dimensions:
    - name: "credit_assessment"
      applicable_entities: ["Supplier"]
  ruleset:
    - id: "R001_basic_eligibility"
      type: "constraint"
      scope:
        dimensions: ["credit_assessment"]
        entity_types: ["Supplier"]
      when:
        expression: "status == 'ACTIVE'"
      then:
        action: "approve"
```

### Instances YAML 结构

```yaml
# examples/supply_chain_finance/instances.yaml

instances:
  - concept: "Supplier"
    data:
      supplier_id: "SUP_2024_001"
      company_name: "深圳智造科技有限公司"
      status: "ACTIVE"

  - concept: "Invoice"
    data:
      invoice_no: "INV2024001001"
      amount:
        value: 2800000
        currency: "CNY"
      issued_by:
        supplier_id: "SUP_2024_001"
```

---

## 输出

### AnalysisResult - 分析结果

```python
@dataclass
class AnalysisResult:
    """维度分析结果"""
    entity_id: str
    dimension: str

    # 规则执行结果
    rule_results: list[RuleResult]

    # 计算指标
    computed_metrics: dict[str, Any]

    # 预警信息
    alerts: list[Alert]

    # 最终决策
    decision: str
    decision_reasoning: str


@dataclass
class RuleResult:
    """规则执行结果"""
    rule_id: str
    rule_name: str
    passed: bool
    output: dict
```

---

## 异常

| 异常 | 场景 | 处理方式 |
|------|------|----------|
| SchemaNotFoundError | Schema 文件不存在 | 抛出异常 |
| SchemaValidationError | Schema 格式错误 | 详细错误信息 |
| InstanceNotFoundError | 实例不存在 | 返回 None |
| RuleEvaluationError | 规则执行失败 | 记录日志，跳过规则 |
| ExpressionSyntaxError | 表达式语法错误 | 详细错误位置 |

---

## 使用示例

```python
# 创建引擎
engine = OntologyEngine.from_config(
    "examples/supply_chain_finance/schema.yaml"
)

# 加载实例
await engine.load_instances(
    "examples/supply_chain_finance/instances.yaml"
)

# 执行分析
result = await engine.analyze(
    entity_id="SUP_2024_001",
    dimension="credit_assessment"
)

print(f"决策: {result.decision}")
print(f"信用评分: {result.computed_metrics.get('credit_score')}")
for alert in result.alerts:
    print(f"预警: {alert.level} - {alert.message}")
```

---

## 边界检查

- [x] 不破坏现有接口
- [x] 可被本地/远程实现
- [x] 测试可覆盖
- [x] Schema 与实例分离
- [x] 规则引擎可扩展
- [x] dimension_attributes 在消费时计算，非存储
