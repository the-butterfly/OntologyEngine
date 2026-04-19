# 模块 05: 归类引擎 (CategorizationEngine)

> **位置**: `ontology_engine/engine/categorization/`
> **依赖**: SchemaLoader, DuckDBStorage, RuleExecutor, ExpressionEngine
> **被依赖**: AnalysisService

## 1. 职责

1. **L2 归类计算** — 将实体自动归类到业务维度
2. **复用规则引擎** — derived 类型归类编译为 L4 规则格式 (决策 #6)
3. **标签管理** — 归类结果持久化、查询、更新
4. **规则匹配** — 规则引擎执行归类的入口

## 2. 归类维度类型

| 类型 | 说明 | 示例 | 实现方式 |
|------|------|------|----------|
| `hierarchical` | 层级分类 | 行业分类 (国标) | 直接属性映射 |
| `derived` | 规则推导 | 企业规模、风险等级 | 编译为 L4 规则，复用 RuleExecutor |
| `tags` | 标签集合 | 核心企业、白名单 | 条件匹配 |

## 3. 核心接口

```python
# engine/categorization/engine.py

class CategorizationEngine:
    """L2 归类引擎
    
    设计决策 #6: L2 归类引擎复用 L4 规则引擎。
    CategorizationEngine 将 L2 规则编译为 L4 格式后调用 RuleExecutor。
    """
    
    def __init__(
        self,
        schema: KGMLSchema,
        storage: DuckDBStorage,
        rule_executor: RuleExecutor,
        expr_engine: ExpressionEngine
    ):
        self.schema = schema
        self.storage = storage
        self.rule_executor = rule_executor
        self.expr_engine = expr_engine
        
        # 预编译归类规则
        self._category_defs = {c.name: c for c in schema.categories}
        self._compiled_rules: dict[str, list[RuleDefinition]] = {}
        self._compile_all_rules()
    
    async def categorize(
        self,
        entity: Entity,
        dimensions: list[str] | None = None
    ) -> CategoryTags:
        """对实体执行归类
        
        Args:
            entity: 待归类实体
            dimensions: 指定维度，为空则全部
        
        Returns:
            CategoryTags: {dimension_name: category_value}
        """
        tags = CategoryTags(entity_id=entity.id)
        
        target_dims = dimensions or list(self._category_defs.keys())
        
        for dim_name in target_dims:
            dim_def = self._category_defs.get(dim_name)
            if not dim_def:
                continue
            
            # 检查实体是否适用
            if dim_def.applicable_entities and entity.concept_type not in dim_def.applicable_entities:
                continue
            
            # 按类型执行归类
            if dim_def.type == "hierarchical":
                value = self._categorize_hierarchical(entity, dim_def)
            elif dim_def.type == "derived":
                value = await self._categorize_derived(entity, dim_def)
            elif dim_def.type == "tags":
                value = self._categorize_tags(entity, dim_def)
            else:
                continue
            
            if value is not None:
                tags.set(dim_name, value)
                # 持久化
                await self.storage.save_category_tag(
                    entity.id, dim_name, str(value)
                )
        
        return tags
    
    async def get_tags(self, entity_id: str) -> CategoryTags:
        """获取实体已有归类标签 (从缓存/存储)"""
        stored = await self.storage.get_category_tags(entity_id)
        return CategoryTags(entity_id=entity_id, tags=stored)


class CategoryTags(BaseModel):
    """归类标签集"""
    entity_id: str
    tags: dict[str, str] = {}
    
    def set(self, dimension: str, value: str):
        self.tags[dimension] = value
    
    def get(self, dimension: str) -> str | None:
        return self.tags.get(dimension)
    
    def matches(self, required: dict[str, str | list[str]]) -> bool:
        """检查是否满足所需归类条件
        
        用于 L4 规则的 applies_to 匹配
        """
        for dim, required_value in required.items():
            actual = self.tags.get(dim)
            if actual is None:
                return False
            if isinstance(required_value, list):
                if actual not in required_value:
                    return False
            elif actual != required_value:
                return False
        return True
```

## 4. 归类实现

### 4.1 层级分类 (Hierarchical)

```python
def _categorize_hierarchical(
    self,
    entity: Entity,
    dim_def: CategoryDimension
) -> str | None:
    """层级分类: 直接从实体属性映射
    
    示例: industry → 从 entity.industry_type 属性获取
    """
    # 从实体属性中查找匹配的值
    # 假设维度名与属性名对应
    attr_name = dim_def.name
    if attr_name in entity.attributes:
        value = entity.attributes[attr_name]
        # 验证值在合法范围内
        if dim_def.values:
            valid = set()
            for v in dim_def.values:
                if isinstance(v, str):
                    valid.add(v)
                elif isinstance(v, dict):
                    valid.add(v.get("code", v.get("id", "")))
            if str(value) in valid:
                return str(value)
        return str(value)
    
    # 尝试常见属性名映射
    name_map = {
        "industry": ["industry_type", "industry_category", "industry_code"],
        "company_scale": ["company_size", "scale"],
        "risk_level": ["risk_grade", "risk_rating"],
    }
    
    for alt_name in name_map.get(attr_name, []):
        if alt_name in entity.attributes:
            return str(entity.attributes[alt_name])
    
    return None
```

### 4.2 规则推导 (Derived) — 核心设计

```python
async def _categorize_derived(
    self,
    entity: Entity,
    dim_def: CategoryDimension
) -> str | None:
    """规则推导归类: 复用 L4 规则引擎 (决策 #6)
    
    流程:
    1. 查找维度对应的 ruleset
    2. 获取预编译的 L4 规则
    3. 调用 RuleExecutor.execute_dimension()
    4. 从结果中提取归类值
    """
    ruleset_name = dim_def.ruleset
    if not ruleset_name:
        return None
    
    compiled_rules = self._compiled_rules.get(ruleset_name, [])
    if not compiled_rules:
        return None
    
    # 构建执行上下文
    entity_data = dict(entity.attributes)
    entity_data["_concept"] = entity.concept_type
    
    # 调用规则引擎
    # 使用 L2_ 前缀的维度名，避免与 L4 规则冲突
    l2_dimension = f"L2_{dim_def.name}"
    
    result = await self.rule_executor.execute_dimension(
        dimension=l2_dimension,
        entity_id=entity.id,
        entity_data=entity_data
    )
    
    # 从结果中提取分类值
    for rule_result in result.rule_results:
        if rule_result.output and "category_value" in rule_result.output:
            return rule_result.output["category_value"]
    
    # 回退: 从 computed_metrics 中查找
    if dim_def.name in result.computed_metrics:
        return str(result.computed_metrics[dim_def.name])
    
    return None


def _compile_all_rules(self):
    """预编译所有 L2 derived 规则为 L4 格式"""
    # 从 schema 的 categorization.rules 中提取
    category_rules = self._extract_category_rules()
    
    for ruleset_name, rules in category_rules.items():
        compiled = []
        for i, rule in enumerate(rules):
            compiled_rule = self._compile_to_l4_rule(rule, ruleset_name, i)
            compiled.append(compiled_rule)
        self._compiled_rules[ruleset_name] = compiled


def _compile_to_l4_rule(
    self,
    cat_rule: dict,
    ruleset_name: str,
    index: int
) -> RuleDefinition:
    """将 L2 分类规则编译为 L4 RuleDefinition
    
    L2 格式:
      condition: "annual_revenue >= 400000000 AND employee_count >= 1000"
      result: LARGE
    
    L4 格式:
      id: L2_company_scale_0
      when: {expression: "annual_revenue >= 400000000 AND employee_count >= 1000"}
      then: {action: "set_category", output: {category_value: "LARGE"}}
    """
    condition = cat_rule.get("condition", "")
    result_value = cat_rule.get("result", cat_rule.get("default"))
    is_default = "default" in cat_rule
    
    if is_default:
        expression = "true"
    elif isinstance(condition, str):
        expression = condition
    elif isinstance(condition, dict):
        # 结构化条件 → 表达式
        parts = []
        for and_cond in condition.get("and", []):
            parts.append(and_cond)
        expression = " AND ".join(parts) if parts else "true"
    else:
        expression = "true"
    
    return RuleDefinition(
        id=f"L2_{ruleset_name}_{index}",
        name=f"L2归类: {ruleset_name}[{index}]",
        type="inference",
        priority=100 - index,  # 先定义的优先级高
        enabled=True,
        scope={"dimensions": [f"L2_{ruleset_name}"]},
        when=ConditionClause(expression=expression),
        then=ActionClause(
            action="set_category",
            output={"category_value": str(result_value)}
        )
    )


def _extract_category_rules(self) -> dict[str, list[dict]]:
    """从 Schema 提取归类规则"""
    rules = {}
    
    # v2 格式: categorization.rules
    for cat in self.schema.categories:
        if cat.type == "derived" and cat.ruleset:
            # 从 schema 的额外数据中查找规则定义
            # (需要 SchemaLoader 将 rules 也加载进来)
            pass
    
    # v1 兼容: 从 rules 中查找 L2 归类规则
    for rule in self.schema.rules:
        scope = rule.scope or {}
        dims = scope.get("dimensions", [])
        for dim in dims:
            if dim.startswith("L2_"):
                ruleset_name = dim[3:]
                if ruleset_name not in rules:
                    rules[ruleset_name] = []
                rules[ruleset_name].append(rule)
    
    return rules
```

### 4.3 标签匹配 (Tags)

```python
def _categorize_tags(
    self,
    entity: Entity,
    dim_def: CategoryDimension
) -> str | None:
    """标签匹配: 条件检查
    
    简单条件匹配，不依赖规则引擎
    """
    # Phase 1: 简化实现，从属性直接映射
    if dim_def.name in entity.attributes:
        return str(entity.attributes[dim_def.name])
    return None
```

## 5. 供应链金融场景归类流

```
Supplier (SUP_2024_001)
    │
    ├─ [hierarchical] industry → "MANUFACTURING" (从 industry_type 属性)
    │
    ├─ [derived] company_scale → 执行规则:
    │   L2_company_scale_0: annual_revenue >= 400000000 AND ... → LARGE
    │   L2_company_scale_1: annual_revenue >= 20000000 AND ... → MEDIUM
    │   L2_company_scale_2: annual_revenue >= 3000000 AND ... → SMALL
    │   L2_company_scale_3: default → MICRO
    │   → 结果: "LARGE"
    │
    └─ [derived] risk_level → 执行规则:
        L2_risk_level_0: credit_score >= 80 AND guarantee_chain_depth < 2 → LOW
        L2_risk_level_1: credit_score >= 50 → MEDIUM
        L2_risk_level_2: default → HIGH
        → 结果: "LOW"

CategoryTags: {industry: "MANUFACTURING", company_scale: "LARGE", risk_level: "LOW"}
```

## 6. 与 L4 规则引擎的对接

归类结果用于 L4 规则的 `applies_to` 匹配：

```python
# 在 RuleExecutor 中检查 applies_to
async def _matches_applies_to(
    self,
    rule_group: RuleDefinition,
    entity: Entity,
    category_tags: CategoryTags
) -> bool:
    """检查规则组是否适用于该实体
    
    L4 规则的 applies_to 包含:
    - fact_objects: [Company]  → 匹配 entity.concept_type
    - categories: {industry: ["C", "F"], risk_level: [LOW, MEDIUM]}  → 匹配 category_tags
    """
    scope = rule_group.scope or {}
    
    # 检查 fact_objects (v2) 或 entity_types (v1)
    fact_objects = scope.get("fact_objects", scope.get("entity_types", []))
    if fact_objects and entity.concept_type not in fact_objects:
        return False
    
    # 检查 categories
    categories = scope.get("categories", {})
    if categories and not category_tags.matches(categories):
        return False
    
    return True
```

## 7. 文件结构

```
ontology_engine/engine/categorization/
├── __init__.py           # 导出 CategorizationEngine, CategoryTags
├── engine.py             # CategorizationEngine 主类
├── compiler.py           # L2 → L4 规则编译器
└── models.py             # CategoryTags
```
