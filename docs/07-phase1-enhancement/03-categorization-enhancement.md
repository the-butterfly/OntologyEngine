# 03: 分类 Category 完善设计

---
status: draft
phase: phase1
source_of_truth: true   # [单一事实源] 分类(Category) 声明/实例/关联的完整规范
last_verified: 2026-04-13
verified_against: docs-only
related_docs:
  - ../05-schema-v2/02-categorization.md
  - ../06-module-detailed-design/05-categorization-engine.md
  - ../05-schema-v2/01-fact-objects.md
  - ../05-schema-v2/04-business-logic.md
  - ../07-phase1-enhancement/02-operator-and-value-domain.md
related_adrs:
  - architecture/decisions/006-l2-reuse-l4-engine.md
  - architecture/decisions/007-l3-l4-computation-boundary.md
---

## 1. 现状分析

### 1.1 Schema v2 设计中的 L2 分类

当前 `docs/05-schema-v2/02-categorization.md` 定义了 L2 分类维度：

```yaml
categorization_declaration:
  id: string
  name: string
  type: hierarchical | flat | derived | tags
  dimensions:
    - name: string
      type: hierarchical | flat | derived | tags
      description: string
      values:
        - code/id: string
          name: string
          children: [...]    # hierarchical
```

### 1.2 代码中的 L2 模型

`ontology_engine/core/schema/models.py`:

```python
class CategorizationDimension(BaseModel):
    """L2 Categorization dimension."""
    id: str
    name: str | None = None
    description: str | None = None
    applicable_to: list[str] = Field(default_factory=list)
    triggers: list[dict] = Field(default_factory=list)
```

**核心 Gap**:
- 模型极度简化，`CategorizationDimension` **没有** `type`、`values`、`hierarchical` 等关键字段
- 分类值域只通过外部规则隐式定义，无**显式值域声明**
- 无**同义词 (synonyms)** 支持
- 无**多选 (multi_select)** 标识
- 无**对象类型 → 分类维度**的双向关联定义
- 无**分类维度 → 规则适用场景**的关联定义

### 1.3 用户新增需求对照

| 需求 | 当前状态 | 本文档目标 |
|------|----------|-----------|
| 分类值域完整声明 | ❌ 缺失 | ✅ 完整 value_domain |
| 同义词 | ❌ 缺失 | ✅ synonyms 字段 |
| 描述信息 | ⚠️ 有 description 但不完整 | ✅ 扩展为 rich description |
| 是否多选 | ❌ 缺失 | ✅ multi_select 字段 |
| 对象类型有所属分类的关系 | ⚠️ 仅 applicable_to 列表 | ✅ 双向关联模型 |
| 规则适用于指定分类场景 | ⚠️ 仅 scope.categories | ✅ explicit mapping |

## 2. 分类声明增强设计

### 2.1 完整的 CategorizationDimension 模型

```yaml
# L2 分类维度完整声明
categorization_dimension:
  id: string                          # 全局唯一标识
  name: string                        # 显示名称
  description: string | null         # 描述

  # --- 维度类型 ---
  type: hierarchical | flat | derived | tags

  # --- 值域定义 [关键设计点] ---
  value_domain:
    # 值域定义复用 02-operator-and-value-domain.md 的值域类型
    type: discrete | enum | hierarchical | tags

    # type = discrete 时
    values:
      - id: string                    # 值 ID (如 "HIGH", "MEDIUM", "LOW")
        label: string                 # 显示名称 (如 "高风险")
        description: string | null    # 值描述
        synonyms: list[string]        # 同义词列表
        sort_order: integer           # 排序权重 (用于前后端展示排序)
        color: string | null          # 前端展示色 (Hex)
        metadata: dict                # 扩展元数据

    # type = hierarchical 时 (覆盖 values 结构)
    values:
      - id: string                    # 层级编码 (如 "C", "C31", "C311")
        label: string
        level: integer                # 层级深度 (1=门类, 2=大类, ...)
        description: string | null
        synonyms: list[string]
        parent_id: string | null      # 父级 ID (根节点为 null)
        children: [...]              # 子级列表 (嵌套)

    # type = tags 时
    values:
      - id: string
        label: string
        description: string | null
        synonyms: list[string]
        color: string | null
        metadata: dict

    # type = enum 时
    enum_ref: string                  # 引用 L1 enums 中的枚举名
    # 值从 enums 定义中自动获取

  # --- 多选支持 [关键设计点] ---
  multi_select: boolean               # 是否允许同时属于多个值 (默认 false)

  # --- 适用对象 [关键设计点] ---
  applicable_to:
    - object_type: string             # 适用的对象类型 (如 "Company", "Borrower")
      required: boolean               # 此分类对该类型是否必须 (默认 false)
      auto_categorize: boolean         # 是否自动归类 (默认 true)
      auto_dimension:                 # 自动归类时使用的属性映射
        source_attribute: string      # 从实体的哪个属性获取分类值
        mapping:                      # 属性值 → 分类值的映射 (可选)
          - from: string
            to: string

  # --- 分类规则 (仅 type=derived) ---
  ruleset:
    id: string
    name: string
    rules:
      - priority: integer
        condition:
          and: [...]                   # AND 条件列表
          or: [...]                    # OR 条件列表
        result: string | list         # 单一值或标签列表
        confidence: float             # 置信度 (0-1, 默认 1.0)

  # --- 规则关联映射 [关键设计点] ---
  rule_applicability:
    - dimension_value: string         # 当分类值为 X 时
      applicable_rule_groups:         # 适用的规则组
        - string
      excluded_rule_groups:           # 排除的规则组
        - string
      rule_overrides:                 # 规则覆盖
        - rule_id: string
          override_field: string
          override_value: any
```

### 2.2 示例：供应链金融分类维度

#### 行业分类 (hierarchical)

```yaml
categorizations:
  dimensions:
    - id: industry_category
      name: 行业分类
      description: "按国民经济行业分类标准 (GB/T 4754)"
      type: hierarchical
      multi_select: false
      applicable_to:
        - object_type: "Company"
          required: true
          auto_categorize: true
          auto_dimension:
            source_attribute: "industry_code"
      value_domain:
        type: hierarchical
        values:
          - id: "C"
            label: "制造业"
            level: 1
            description: "门类C: 制造业"
            synonyms: ["制造", "制造业企业"]
            children:
              - id: "C31"
                label: "黑色金属冶炼和压延加工业"
                level: 2
                description: "大类C31"
                parent_id: "C"
                synonyms: ["钢铁冶炼"]
              - id: "C34"
                label: "通用设备制造业"
                level: 2
                description: "大类C34"
                parent_id: "C"
                synonyms: ["机械制造", "装备制造"]

          - id: "F"
            label: "批发和零售业"
            level: 1
            description: "门类F: 批发和零售业"
            synonyms: ["批发零售", "贸易"]
            children:
              - id: "F51"
                label: "批发业"
                level: 2
                parent_id: "F"
                synonyms: ["经销"]
```

#### 企业规模 (derived + 多选)

```yaml
    - id: company_scale
      name: 企业规模
      description: "按国家统计局标准划分的大中小微企业"
      type: derived
      multi_select: false
      applicable_to:
        - object_type: "Company"
          required: true
          auto_categorize: true
      ruleset:
        id: determine_scale_rules
        name: 企业规模判定规则
        rules:
          - priority: 100
            condition:
              and:
                - fact: "annual_revenue"
                  op: gte
                  value: 400000000
                - fact: "employee_count"
                  op: gte
                  value: 1000
            result: "LARGE"
          - priority: 90
            condition:
              and:
                - fact: "annual_revenue"
                  op: gte
                  value: 20000000
                - fact: "employee_count"
                  op: gte
                  value: 300
            result: "MEDIUM"
          - priority: 80
            condition:
              and:
                - fact: "annual_revenue"
                  op: gte
                  value: 3000000
                - fact: "employee_count"
                  op: gte
                  value: 20
            result: "SMALL"
          - priority: 0
            condition: {}
            result: "MICRO"
      value_domain:
        type: discrete
        values:
          - id: "LARGE"
            label: "大型企业"
            description: "年营收≥4亿且从业人数≥1000人"
            synonyms: ["大企业", "大型"]
            sort_order: 1
            color: "#1890FF"
          - id: "MEDIUM"
            label: "中型企业"
            description: "年营收≥2000万且从业人数≥300人"
            synonyms: ["中企业", "中型"]
            sort_order: 2
            color: "#52C41A"
          - id: "SMALL"
            label: "小型企业"
            description: "年营收≥300万且从业人数≥20人"
            synonyms: ["小企业", "小型"]
            sort_order: 3
            color: "#FAAD14"
          - id: "MICRO"
            label: "微型企业"
            description: "不满足小型企业标准"
            synonyms: ["微企业", "微型"]
            sort_order: 4
            color: "#FF7A45"
```

#### 业务标签 (tags + 多选)

```yaml
    - id: business_tags
      name: 业务标签
      description: "人工或规则标注的业务属性标签"
      type: tags
      multi_select: true                    # 关键: 允许多标签
      applicable_to:
        - object_type: "Company"
          required: false
          auto_categorize: false            # 标签通常手动打标
        - object_type: "Borrower"
          required: false
          auto_categorize: false
      value_domain:
        type: tags
        values:
          - id: "CORE_ENTERPRISE"
            label: "核心企业"
            description: "供应链核心企业，信用等级高"
            synonyms: ["核心", "核心企业客户", "链主"]
            color: "#1890FF"
            metadata:
              priority_weight: 0.8
          - id: "WHITELIST"
            label: "白名单"
            description: "经审核纳入白名单，享受优惠条件"
            synonyms: ["白名单客户", "VIP"]
            color: "#52C41A"
          - id: "KEY_SUPPLIER"
            label: "重点供应商"
            description: "年度采购量Top 20%"
            synonyms: ["重点", "重点供应商客户"]
            color: "#722ED1"
          - id: "RISK_WATCH"
            label: "风险关注"
            description: "近期出现风险信号，需持续跟踪"
            synonyms: ["风险关注客户", "观察名单"]
            color: "#FF4D4F"
          - id: "NEW_CUSTOMER"
            label: "新客户"
            description: "首次合作不满6个月"
            synonyms: ["新", "新客户"]
            color: "#13C2C2"
```

#### 风险等级 + 规则关联映射

```yaml
    - id: risk_level
      name: 风险等级
      description: "综合风险等级判定结果"
      type: derived
      multi_select: false
      applicable_to:
        - object_type: "Company"
          required: true
          auto_categorize: true
      ruleset:
        id: assess_risk_rules
        name: 风险等级评估规则
        rules:
          - priority: 100
            condition:
              and:
                - fact: "credit_score"
                  op: lt
                  value: 40
                - fact: "has_critical_alert"
                  op: eq
                  value: true
            result: "CRITICAL"
          - priority: 90
            condition:
              and:
                - fact: "credit_score"
                  op: lt
                  value: 60
            result: "HIGH"
          - priority: 80
            condition:
              and:
                - fact: "credit_score"
                  op: gte
                  value: 60
                - fact: "credit_score"
                  op: lt
                  value: 80
            result: "MEDIUM"
          - priority: 0
            condition: {}
            result: "LOW"
      value_domain:
        type: discrete
        values:
          - id: "LOW"
            label: "低风险"
            description: "信用评分≥80, 无重大预警"
            synonyms: ["低风险客户"]
            sort_order: 1
            color: "#52C41A"
          - id: "MEDIUM"
            label: "中风险"
            description: "信用评分60-80"
            synonyms: ["中风险客户"]
            sort_order: 2
            color: "#FAAD14"
          - id: "HIGH"
            label: "高风险"
            description: "信用评分<60"
            synonyms: ["高风险客户"]
            sort_order: 3
            color: "#FF4D4F"
          - id: "CRITICAL"
            label: "极高风险"
            description: "信用评分<40且有严重预警"
            synonyms: ["极高风险客户", "黑名单"]
            sort_order: 4
            color: "#F5222D"

      # [关键设计点] 分类值 → 规则适用映射
      rule_applicability:
        - dimension_value: "LOW"
          applicable_rule_groups:
            - "standard_credit_assessment"
            - "fast_track_approval"
          excluded_rule_groups:
            - "enhanced_review"
        - dimension_value: "MEDIUM"
          applicable_rule_groups:
            - "standard_credit_assessment"
        - dimension_value: "HIGH"
          applicable_rule_groups:
            - "enhanced_review"
            - "risk_mitigation_check"
          excluded_rule_groups:
            - "fast_track_approval"
        - dimension_value: "CRITICAL"
          applicable_rule_groups:
            - "enhanced_review"
            - "escalation_protocol"
          excluded_rule_groups:
            - "fast_track_approval"
            - "standard_credit_assessment"
          rule_overrides:
            - rule_id: "R001_credit_check"
              override_field: "priority"
              override_value: 200          # 提升优先级
            - rule_id: "R007_final_decision"
              override_field: "default_decision"
              override_value: "REJECT"    # 直接拒绝
```

## 3. 对象类型 ↔ 分类关联模型

### 3.1 双向关联

```
L1 FactObject ←→ L2 Categorization ←→ L4 BusinessLogic

Company
  ├── [has_dimension] industry_category    (required: true)
  ├── [has_dimension] company_scale        (required: true)
  ├── [has_dimension] risk_level           (required: true)
  └── [has_dimension] business_tags        (required: false, multi_select)

risk_level = "HIGH"
  ├── [applicable_rules] enhanced_review
  ├── [excluded_rules] fast_track_approval
  └── [overrides] R001 → priority=200
```

### 3.2 关系存储

```sql
-- 存储分类维度与对象类型的关联
CREATE TABLE IF NOT EXISTS dimension_applicability (
    dimension_id VARCHAR NOT NULL,
    object_type VARCHAR NOT NULL,
    required BOOLEAN DEFAULT FALSE,
    auto_categorize BOOLEAN DEFAULT TRUE,
    source_attribute VARCHAR,
    PRIMARY KEY (dimension_id, object_type)
);

-- 存储分类值与规则组的映射
CREATE TABLE IF NOT EXISTS category_rule_mapping (
    dimension_id VARCHAR NOT NULL,
    dimension_value VARCHAR NOT NULL,
    rule_group_id VARCHAR NOT NULL,
    mapping_type VARCHAR NOT NULL DEFAULT 'applicable',  -- applicable | excluded
    override_rule_id VARCHAR,
    override_field VARCHAR,
    override_value JSON,
    PRIMARY KEY (dimension_id, dimension_value, rule_group_id)
);
```

### 3.3 API 设计

#### 分类维度 CRUD

```
GET    /v1/management/{spaceId}/schema/L2/categorizations
POST   /v1/management/{spaceId}/schema/L2/categorizations
GET    /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}
PUT    /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}
DELETE /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}
```

#### 对象类型 ↔ 分类关联

```
GET    /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}/applicable-types
POST   /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}/applicable-types
DELETE /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}/applicable-types/{objectType}
```

#### 分类标签实例管理

```
GET    /v1/management/{spaceId}/instances/category-tags
POST   /v1/management/{spaceId}/instances/category-tags
PUT    /v1/management/{spaceId}/instances/category-tags/{entityId}/{dimension}
DELETE /v1/management/{spaceId}/instances/category-tags/{entityId}/{dimension}

# 批量归类 (按对象类型)
POST   /v1/management/{spaceId}/instances/category-tags/batch-categorize
# Body: { "object_type": "Company", "dimension_ids": ["industry_category", "risk_level"] }

# 同义词查询
GET    /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}/lookup
# ?query=大企业 → 匹配 synonyms 返回 LARGE
```

#### 分类 → 规则关联

```
GET    /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}/rule-mappings
PUT    /v1/management/{spaceId}/schema/L2/categorizations/{dimensionId}/rule-mappings
```

## 4. Pydantic 模型

```python
# core/schema/models.py (扩展)

class CategoryValueDefinition(BaseModel):
    """分类值定义。"""
    id: str
    label: str
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    sort_order: int = 0
    color: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # hierarchical 扩展
    level: int | None = None
    parent_id: str | None = None
    children: list["CategoryValueDefinition"] = Field(default_factory=list)


class CategoryValueDomain(BaseModel):
    """分类值域定义。"""
    type: Literal["discrete", "enum", "hierarchical", "tags"]
    values: list[CategoryValueDefinition] = Field(default_factory=list)
    enum_ref: str | None = None  # type=enum 时引用 L1 enums


class DimensionApplicability(BaseModel):
    """分类维度对对象类型的适用性声明。"""
    object_type: str
    required: bool = False
    auto_categorize: bool = True
    auto_dimension: AutoCategorizeMapping | None = None


class AutoCategorizeMapping(BaseModel):
    """自动归类映射配置。"""
    source_attribute: str
    mapping: list[AutoMappingEntry] = Field(default_factory=list)

class AutoMappingEntry(BaseModel):
    from_value: str
    to_value: str


class RuleApplicabilityMapping(BaseModel):
    """分类值 → 规则适用映射。"""
    dimension_value: str
    applicable_rule_groups: list[str] = Field(default_factory=list)
    excluded_rule_groups: list[str] = Field(default_factory=list)
    rule_overrides: list[RuleOverride] = Field(default_factory=list)

class RuleOverride(BaseModel):
    rule_id: str
    override_field: str
    override_value: Any


class CategorizationDimension(BaseModel):
    """L2 分类维度完整定义 [增强版]。"""
    id: str
    name: str
    description: str | None = None
    type: Literal["hierarchical", "flat", "derived", "tags"]

    # 值域
    value_domain: CategoryValueDomain | None = None

    # 多选
    multi_select: bool = False

    # 适用对象
    applicable_to: list[DimensionApplicability] = Field(default_factory=list)

    # 规则 (derived 类型)
    ruleset: CategorizationRuleset | None = None

    # 规则关联映射
    rule_applicability: list[RuleApplicabilityMapping] = Field(default_factory=list)

    # 触发条件 (保留原设计)
    triggers: list[dict] = Field(default_factory=list)
```

## 5. 前端展示设计

### 5.1 Schema 声明页 (L2 编辑器)

```
┌─────────────────────────────────────────────────────────┐
│ 分类维度: 风险等级                          [编辑] [删除]  │
├─────────────────────────────────────────────────────────┤
│ 类型: 派生 (derived)    多选: ❌    必须: Company        │
│                                                          │
│ ┌─ 值域 ────────────────────────────────────────────┐   │
│ │ ID       │ 标签      │ 同义词        │ 排序 │ 色块 │   │
│ │ LOW      │ 低风险    │ 低风险客户     │ 1    │ 🟢  │   │
│ │ MEDIUM   │ 中风险    │ 中风险客户     │ 2    │ 🟡  │   │
│ │ HIGH     │ 高风险    │ 高风险客户     │ 3    │ 🔴  │   │
│ │ CRITICAL │ 极高风险  │ 极高风险客户   │ 4    │ 🔴  │   │
│ └────────────────────────────────────────────────────┘   │
│                                                          │
│ ┌─ 规则关联映射 ────────────────────────────────────┐   │
│ │ 分类值    │ 适用规则组          │ 排除规则组        │   │
│ │ LOW      │ standard, fast      │ enhanced          │   │
│ │ HIGH     │ enhanced, risk      │ fast              │   │
│ └────────────────────────────────────────────────────┘   │
│                                                          │
│ 适用对象类型: Company (必须✓) │ Borrower (可选)           │
└─────────────────────────────────────────────────────────┘
```

### 5.2 分类标签实例查看

```
实体: 深圳智造科技有限公司 (SUP_2024_001)
┌──────────────────────────────────────────────┐
│ 分类维度        │ 值           │ 来源    │ 置信度 │
│ 行业分类        │ C 制造业      │ 自动    │ 1.0   │
│ 企业规模        │ LARGE         │ 规则    │ 1.0   │
│ 风险等级        │ LOW           │ 规则    │ 0.95  │
│ 业务标签        │ 核心企业, 白名单│ 手动    │ 1.0   │
└──────────────────────────────────────────────┘
```

## 6. 同义词查询

### 6.1 用途

- API 搜索时支持模糊匹配
- 前端输入时自动补全
- 实例导入时自动映射 (如 "大企业" → LARGE)

### 6.2 实现

```python
class SynonymLookup:
    """同义词查询服务。"""

    def __init__(self, schema: KGMLSchema):
        self.schema = schema
        self._index: dict[str, list[tuple[str, str]]] = {}  # normalized → [(dim_id, value_id)]
        self._build_index()

    def _build_index(self):
        """构建同义词倒排索引。"""
        for dim in self.schema.categorizations.dimensions:
            if dim.value_domain and dim.value_domain.values:
                for val in dim.value_domain.values:
                    # 索引 ID
                    self._index[val.id.lower()].append((dim.id, val.id))
                    # 索引 label
                    self._index[val.label.lower()].append((dim.id, val.id))
                    # 索引 synonyms
                    for syn in val.synonyms:
                        self._index[syn.lower()].append((dim.id, val.id))

    def lookup(
        self,
        query: str,
        dimension_id: str | None = None,
    ) -> list[SynonymMatch]:
        """查询同义词匹配。

        Args:
            query: 查询字符串
            dimension_id: 限定在某个维度内查询

        Returns:
            匹配结果列表，按匹配精度排序
        """
        query_lower = query.lower().strip()
        results = []

        for key, matches in self._index.items():
            if query_lower in key or key in query_lower:
                for dim_id, val_id in matches:
                    if dimension_id and dim_id != dimension_id:
                        continue
                    results.append(SynonymMatch(
                        dimension_id=dim_id,
                        value_id=val_id,
                        matched_term=key,
                    ))

        return results
```

## 7. 验收场景

### 场景 1: 行业分类层级结构

```
Given: 行业分类维度 (hierarchical), 含 C→C31→C311 层级
When: 公司实例 industry_code = "C311"
Then: 归类结果为 ["C", "C31", "C311"] (全层级)
      查询 "钢铁冶炼" 通过 synonyms 匹配到 C31
```

### 场景 2: 多选标签

```
Given: business_tags 维度 (multi_select: true)
When: 手动打标 ["CORE_ENTERPRISE", "WHITELIST"]
Then: 两个标签同时存储
      查询 entity 的 tags 时返回列表
```

### 场景 3: 分类 → 规则关联

```
Given: risk_level 维度, 含 rule_applicability 映射
When: 实体 risk_level = "HIGH"
Then: 规则引擎自动获取:
      - applicable_rule_groups = ["enhanced_review", "risk_mitigation_check"]
      - excluded_rule_groups = ["fast_track_approval"]
      不执行 fast_track_approval 组内的规则
```

### 场景 4: 规则覆盖

```
Given: risk_level = "CRITICAL", 含 rule_overrides
When: 执行规则 R001_credit_check
Then: R001 的 priority 被覆盖为 200 (而非默认值)
      执行日志记录 "priority overridden by category risk_level=CRITICAL"
```

---

*文档结束*
