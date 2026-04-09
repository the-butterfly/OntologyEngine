# L2: 归类分析 (Categorization)

> 对事实对象的业务分类标签

## 核心概念

```yaml
categorization:
  dimensions:        # 分类维度
  rules:             # 打标规则
```

## 分类维度

### 行业分类

```yaml
categorization:
  dimensions:
    - name: industry_category
      description: "国标行业分类"
      type: hierarchical          # 层级分类
      levels:
        - name: section           # 门类
          code_length: 1
        - name: division          # 大类
          code_length: 2
        - name: group             # 中类
          code_length: 3
        - name: class             # 小类
          code_length: 4
      values:
        - code: "C"
          name: "制造业"
          children:
            - code: "31"
              name: "黑色金属冶炼和压延加工业"
              children:
                - code: "311"
                  name: "炼铁"

    - name: custom_industry
      description: "业务自定义行业"
      type: flat                  # 平级分类
      values:
        - id: CORE_MANUFACTURING
          name: "核心制造企业"
        - id: LOGISTICS
          name: "物流配套企业"
```

### 企业规模

```yaml
    - name: company_scale
      description: "企业规模"
      type: derived               # 派生分类，由规则计算
      ruleset: determine_scale    # 引用打标规则
      values:
        - id: LARGE
          name: "大型企业"
        - id: MEDIUM
          name: "中型企业"
        - id: SMALL
          name: "小型企业"
        - id: MICRO
          name: "微型企业"
```

### 风险等级

```yaml
    - name: risk_level
      description: "风险等级"
      type: derived
      ruleset: assess_risk_level
      values:
        - id: HIGH
          name: "高风险"
          color: "#FF4D4F"
        - id: MEDIUM
          name: "中风险"
          color: "#FAAD14"
        - id: LOW
          name: "低风险"
          color: "#52C41A"
```

## 打标规则

```yaml
categorization_rules:
  - name: determine_scale
    description: "根据营收和员工数判定规模"
    target_dimension: company_scale

    rules:
      - priority: 100
        condition:
          and:
            - fact: "annual_revenue.value"
              op: gte
              value: 400000000  # 4亿
            - fact: "employee_count"
              op: gte
              value: 1000
        result: LARGE

      - priority: 90
        condition:
          and:
            - fact: "annual_revenue.value"
              op: gte
              value: 20000000   # 2000万
            - fact: "employee_count"
              op: gte
              value: 300
        result: MEDIUM

      - priority: 80
        condition:
          and:
            - fact: "annual_revenue.value"
              op: gte
              value: 3000000    # 300万
            - fact: "employee_count"
              op: gte
              value: 20
        result: SMALL

      - priority: 0              # 默认规则
        condition: {}
        result: MICRO
```

## 标签系统

```yaml
    - name: business_tags
      description: "业务标签"
      type: tags                  # 多标签
      values:
        - id: CORE_ENTERPRISE
          name: "核心企业"
        - id: WHITELIST
          name: "白名单"
        - id: KEY_SUPPLIER
          name: "重点供应商"
        - id: NEW_CUSTOMER
          name: "新客户"
```

标签打标规则：

```yaml
categorization_rules:
  - name: tag_core_enterprise
    description: "标记核心企业"
    target_dimension: business_tags
    operation: add_tag           # add_tag / remove_tag

    rules:
      - condition:
          or:
            - fact: "annual_revenue.value"
              op: gte
              value: 10000000000  # 10亿
            - fact: "is_listed"
              op: eq
              value: true
        result: CORE_ENTERPRISE
```

## 使用场景

### 场景 1: 行业准入

```yaml
logic:
  - name: IndustryAccess
    applies_to:
      categories:
        industry_category: ["C", "F"]  # 制造业、批发零售
```

### 场景 2: 规模差异化政策

```yaml
logic:
  - name: CreditLimitByScale
    applies_to:
      categories:
        company_scale: [LARGE, MEDIUM]
    config:
      LARGE:
        max_limit: 100000000
      MEDIUM:
        max_limit: 50000000
```

## 与 v1 的区别

| v1 | v2 |
|-----|-----|
| 无明确分类层 | 独立的 categorization 层 |
| 分类逻辑散落在 rules | 分类规则集中管理 |
| 无法多维度叠加 | 支持多维度分类共存 |

## 运行时行为

**L2 复用 L4 规则引擎（决策 #6）**：CategorizationEngine 将 L2 规则编译为 L4 格式后，调用 RuleExecutor 统一执行。

```python
class CategorizationEngine:
    """L2 归类引擎 - 复用 L4 规则引擎"""
    
    def __init__(self, rule_executor: RuleExecutor):
        self.rule_executor = rule_executor
    
    def categorize(self, entity: Entity) -> CategoryTags:
        """为实体打标"""
        tags = CategoryTags()

        for dimension in self.dimensions:
            if dimension.type == "hierarchical":
                value = self.match_hierarchical(entity, dimension)
            elif dimension.type == "derived":
                # 将 L2 规则编译为 L4 格式，复用 RuleExecutor
                rules = self._compile_to_l4_rules(
                    dimension.ruleset, dimension.name
                )
                result = self.rule_executor.execute(
                    entity_id=entity.id,
                    dimension=dimension.name,
                    rules=rules
                )
                value = result.computed.get(dimension.name)
            elif dimension.type == "tags":
                value = self.apply_tag_rules(entity, dimension)

            tags.set(dimension.name, value)

        return tags
    
    def _compile_to_l4_rules(
        self, ruleset: CategorizationRuleset, dimension_name: str
    ) -> list[Rule]:
        """将 L2 categorization_rules 编译为 L4 Rule 格式
        
        L2: condition → result (简单映射)
        L4: id + when + then (DAG 节点)
        
        编译规则：
        - L2 condition.and[] → L4 when.expression (AND 连接)
        - L2 result → L4 then.set_flag(dimension_name, result)
        - L2 priority → L4 priority
        """
        rules = []
        for i, cat_rule in enumerate(ruleset.rules):
            rule = Rule(
                id=f"L2_{dimension_name}_{i}",
                when=Condition(expression=self._build_expression(cat_rule.condition)),
                then=Action(
                    type="set_flag",
                    flag=dimension_name,
                    value=cat_rule.result
                ),
                priority=cat_rule.priority
            )
            rules.append(rule)
        return rules
    
    def _build_expression(self, condition: dict) -> str:
        """将 L2 条件结构编译为表达式字符串"""
        if not condition:
            return "True"  # 默认规则
        
        parts = []
        for cond in condition.get("and", []):
            op_map = {"gte": ">=", "lte": "<=", "eq": "==", "gt": ">", "lt": "<"}
            op = op_map.get(cond["op"], cond["op"])
            parts.append(f"{cond['fact']} {op} {cond['value']}")
        return " AND ".join(parts)
```
