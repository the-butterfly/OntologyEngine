# Schema v2 设计概览

> **Status**: Design Phase
> **Target**: Post-MVP (Phase 1)

## v1 的问题

当前 Schema (v1) 的问题：

1. **概念混杂** —— `attributes` 既存事实又存分析结果
2. **规则与数据绑定** —— 规则写死 entity_type，复用性差
3. **维度理解混乱** —— `dimension_attributes` 被误解为存储字段
4. **缺乏分层** —— 事实、分类、要素、逻辑混在一起

## v2 核心思想

**四层分离**:

```
事实对象 (Factual Objects)
    │
    ▼
归类分析 (Categorization)
    │
    ▼
分析要素 (Analytical Elements)
    │
    ▼
业务逻辑 (Business Logic)
```

## 四层详解

### L1: 事实对象 (Factual)

**定义**: 客观存在、可观测、可验证的数据

**内容**:
- 实体类型定义 (公司、个人、发票)
- 关系类型定义 (担保、交易、归属)
- 原始属性 (注册资本、成立日期、金额)

**特点**:
- 与业务场景无关
- 可直接从数据源同步
- 结构稳定，变化少

### L2: 归类分析 (Categorization)

**定义**: 对事实对象的业务分类标签

**内容**:
- 行业分类 (国标行业、自定义行业)
- 企业规模 (大型、中型、小微)
- 风险等级 (高、中、低)
- 业务标签 (核心企业、白名单)

**特点**:
- 基于规则或模型自动打标
- 多维度可叠加
- 随业务定义变化

### L3: 分析要素 (Analytical Elements)

**定义**: 基于事实对象提炼的分析指标

**内容**:
- 基础指标 (营收、资产、负债)
- 派生指标 (资产负债率、流动比率)
- 评分指标 (信用分、稳定分)
- 图指标 (担保圈密度、中心性)

**特点**:
- 有明确的计算公式
- 可缓存，可增量更新
- 不同场景可复用

### L4: 业务逻辑 (Business Logic)

**定义**: 定义作用的分析事实对象、适用的业务分类、输入要素、输出要素

**内容**:
- 准入规则 (什么条件可通过)
- 评分规则 (如何计算综合分)
- 决策规则 (如何确定额度/利率)
- 预警规则 (何时触发警报)

**特点**:
- 高度场景化
- 需声明作用域 (哪些实体+哪些分类)
- 输入输出显式定义

## 对比

| 维度 | v1 | v2 |
|------|-----|-----|
| 结构 | 扁平 | 四层分层 |
| 复用 | 规则绑定 entity_type | 规则声明适用条件 |
| 清晰度 | attributes 混杂 | 事实与分析分离 |
| 灵活性 | 改规则需改 Schema | 规则独立演进 |

## 示例演进

### v1 写法
```yaml
concepts:
  - name: Supplier
    attributes:
      - name: registered_capital  # 事实
      - name: credit_score        # 分析结果 ❌ 混在一起

rules:
  - id: R001
    scope:
      entity_types: [Supplier]    # 硬编码绑定
```

### v2 写法
```yaml
# L1: 事实
fact_objects:
  - name: Company
    attributes:
      - name: registered_capital  # 纯事实

# L2: 归类
categories:
  - name: IndustryCategory
    values: [制造业, 批发零售, ...]

# L3: 要素
elements:
  - name: CapitalAdequacy
    formula: "registered_capital / industry_avg"

# L4: 逻辑
logic:
  - name: CreditAssessment
    applies_to:
      fact_objects: [Company]
      categories: {行业: 制造业}
    inputs: [CapitalAdequacy, ...]
    outputs: [credit_score, ...]
```
