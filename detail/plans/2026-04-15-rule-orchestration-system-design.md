# 规则逻辑编排系统设计计划

> **状态**: DRAFT  
> **日期**: 2026-04-15  
> **阶段**: Phase 2 核心特性  
> **负责人**: 待定  
> **关联文档**: `docs/06-module-detailed-design/06-rule-engine.md`, `docs/05-schema-v2/09-canonical-schema-spec.md`

---

## 一、背景与目标

### 1.1 现状与痛点

当前规则引擎已实现 DAG 执行模型和基础算子体系（Binning / Scorecard / DecisionTable / LLMJudge），但存在以下问题：

| 问题 | 表现 | 影响 |
|------|------|------|
| 规则只能写 YAML，无可视化入口 | 业务人员无法参与规则创建 | 规则管理门槛高 |
| 规则实例与规则框架混合 | 修改一个规则需要理解整个 YAML 结构 | 维护困难 |
| 要素间计算关系不透明 | 不知道一个指标依赖哪些输入 | 调试困难 |
| 规则执行无法单独模拟 | 要调试一条规则需要运行全量推理 | 验证低效 |
| DAG 仅在执行时构建，无可视化 | 无法预先检查规则依赖问题 | 潜在循环依赖 |

### 1.2 目标

**面向用户场景**：业务分析师/规则工程师能够通过画布**可视化创建、编辑、验证**业务规则，并快速理解要素间的计算依赖关系，从原子数据到最终决策结果的完整 DAG 一目了然。

**核心交付**：

1. **规则编排画布** — 拖拽式规则组和规则实例创建
2. **要素计算图** — 业务要素（指标）间的完整 DAG 可视化
3. **规则四元素标准化** — 作用对象 / 适用场景 / 输入输出要素 / 分析逻辑统一表达
4. **单规则模拟执行** — 输入测试数据，即时查看规则结果
5. **全量 DAG 组装** — 从原子指标到最终决策结果的完整计算图

---

## 二、核心概念重定义

### 2.1 规则四元素模型

每一条具体规则必须包含以下四个要素：

```
┌─────────────────────────────────────────────────────┐
│                    规则四元素                         │
│                                                     │
│  ① 作用对象 (Target)                                 │
│     └─ 规则作用于哪种实体类型（Supplier/Invoice/...） │
│                                                     │
│  ② 适用场景 (Applicability)                          │
│     └─ 何时触发该规则（维度/分类/前置条件）            │
│                                                     │
│  ③ 输入输出要素 (I/O Elements)                       │
│     └─ 需要哪些指标作为输入，产出哪些指标              │
│                                                     │
│  ④ 分析逻辑 (Logic Expression)                      │
│     └─ 具体的计算/判断逻辑（算子 + 表达式）            │
└─────────────────────────────────────────────────────┘
```

### 2.2 规则体系两级分层

```
规则组 (RuleGroup / rule_definition)
  ├─ 定义规则的框架结构（四元素的 ① ② ③）
  ├─ 声明适用对象、适用场景、I/O 要素约束
  └─ 包含一组有序的规则实例

    规则实例 (RuleInstance / rule_logic.step)
      ├─ 具体的逻辑表达式（四元素的 ④）
      ├─ 一个 when → then/else 结构
      └─ 使用算子执行计算
```

### 2.3 算子分类（五大类型）

| 算子类型 | 代码名 | 场景 | 特点 |
|---------|--------|------|------|
| 分箱 | `BINNING` | 连续值离散化（年龄段/信用分段） | 区间定义 + 标签映射 |
| 评分卡 | `SCORECARD` | 多变量积分式评估 | baseline + 变量得分表 |
| 加权计算 | `WEIGHTED_SUM` | 复合指标聚合 | 权重配置 + 归一化 |
| 决策树 | `DECISION_TABLE` | 多条件矩阵决策 | 条件组合 → 结果映射 |
| LLM定性分析 | `LLM_JUDGE` | 非结构化/主观评估 | Prompt模板 + 置信度 |

> 除上述五类外，还保留：`SWITCH`（分支选择）/ `COMPUTE`（公式计算）/ `GRAPH`（图遍历）/ `SET_FLAG`（标志设置）/ `TRIGGER_ALERT`（预警触发）

---

## 三、用户流程设计

### 3.1 规则创建主流程

```
[用户入口] 规则管理 → 规则编排画布
        │
        ├─ Step 1: 选择/创建规则组
        │    └─ 配置框架：作用对象 + 适用场景 + I/O要素声明
        │
        ├─ Step 2: 在规则组内添加规则实例
        │    ├─ 设置 when 条件（表达式编辑器）
        │    ├─ 配置 then 动作（选择算子 + 参数）
        │    └─ 可选 else 分支
        │
        ├─ Step 3: 查看要素关系（计算图）
        │    └─ 自动推导输入→输出的 DAG 路径
        │
        ├─ Step 4: 单规则模拟验证
        │    └─ 输入测试数据 → 执行 → 查看结果
        │
        └─ Step 5: 保存为 YAML 配置
             └─ 生成符合 Schema v2 canonical spec 的 YAML
```

### 3.2 要素计算图查看流程

```
[用户入口] 指标管理 → 查看计算图 / 或 规则组详情 → 依赖图
        │
        ├─ 选择目标指标或规则
        │
        ├─ 系统自动展开：
        │    └─ 从原子指标 → 派生指标 → 复合指标 → 规则输入 → 规则输出 → 最终决策
        │
        └─ 交互：
             ├─ 点击节点查看定义详情
             ├─ 高亮依赖路径
             └─ 查看每个要素的值域约束
```

### 3.3 DAG 组装流程（全链路计算图）

```
[用户入口] Schema 视图 → 完整计算 DAG
        │
        ├─ 选择目标输出（如 credit_score, decision）
        │
        └─ 系统生成从原子指标到目标输出的完整 DAG
             ├─ L1 原子属性 → L3 atomic 指标
             ├─ L3 atomic → L3 derived 指标
             ├─ L3 derived → L3 composite 指标（含权重边）
             ├─ L3 指标 → L4 规则输入
             ├─ L4 规则执行 → L4 规则输出
             └─ L4 规则输出 → 最终决策
```

---

## 四、前端设计

### 4.1 页面结构

```
规则管理模块 (Route: /rules)
├── 规则组列表页       /rules
├── 规则组详情/编辑页  /rules/:id
│   ├── 基础信息面板（四元素 ①②③ 配置）
│   ├── 规则实例列表（有序，可拖拽排序）
│   └── 依赖图预览（该规则组的 I/O 要素图）
│
├── 规则实例编辑器     /rules/:id/steps/:stepId
│   ├── When 条件配置
│   ├── Then 动作配置（算子选择 + 参数表单）
│   ├── Else 分支配置
│   └── 模拟执行面板
│
要素/指标管理 (Route: /metrics)
├── 指标列表页         /metrics
├── 指标详情页         /metrics/:name
│   ├── 指标定义（类型/公式/依赖）
│   ├── 值域约束配置
│   └── 上下游依赖图（该指标在 DAG 中的位置）
│
全局计算图 (Route: /dag)
└── 完整 DAG 视图     /dag
    ├── 从目标结果反向展开
    ├── 节点类型分层显示
    └── 路径高亮 + 节点详情面板
```

### 4.2 规则编排画布核心组件

#### 4.2.1 规则组框架配置器 (RuleGroupEditor)

```
┌────────────────────────────────────────────────────────┐
│  规则组: credit_assessment_rule                        │
├────────────────────────────────────────────────────────┤
│  ① 作用对象                                             │
│     [ Supplier ▼ ]  [ Invoice ▼ ]  [ + 添加 ]         │
│                                                        │
│  ② 适用场景                                             │
│     维度: [ credit_assessment ▼ ]                      │
│     分类过滤: company_scale = [ LARGE, MEDIUM ▼ ]      │
│     前置条件: [ status == 'ACTIVE' _______________]    │
│                                                        │
│  ③ 输入要素                           输出要素          │
│     [🟢 credit_score      ] ↗         [📤 decision    ]│
│     [🟢 guarantee_depth   ]           [📤 credit_limit]│
│     [🟢 overdue_ratio     ]                            │
│     [ + 添加输入要素 ]                 [ + 添加输出要素]│
│                                                        │
│  优先级: [100] │ 状态: [ ✅ 启用 ▼ ]                    │
└────────────────────────────────────────────────────────┘
```

#### 4.2.2 规则实例编辑器 (RuleStepEditor)

```
┌────────────────────────────────────────────────────────┐
│  规则实例: R001 - 基本资质检查                           │
├──────────────────────────┬─────────────────────────────┤
│  WHEN 条件                │  THEN 动作                   │
│  ┌────────────────────┐  │  算子: [ SET_FLAG ▼ ]        │
│  │ 条件类型:           │  │                             │
│  │ ○ 单一表达式        │  │  flag: [eligible]           │
│  │ ● ALL OF (AND)     │  │  value: [true]              │
│  │ ○ ANY OF (OR)      │  │                             │
│  └────────────────────┘  │  输出: eligible = true      │
│                           │                             │
│  子条件:                   ├─────────────────────────────┤
│  ┌────────────────────┐  │  ELSE 动作（可选）            │
│  │status == 'ACTIVE'  │  │  算子: [ REJECT ▼ ]          │
│  ├────────────────────┤  │  reason: [不满足基本条件]    │
│  │registered_capital. │  │                             │
│  │value >= 1000000    │  │                             │
│  └────────────────────┘  │                             │
│  [+ 添加条件] [验证]       │                             │
└──────────────────────────┴─────────────────────────────┘
```

#### 4.2.3 算子参数配置器 (OperatorParamEditor)

**BINNING 算子**：

```
┌────────────────────────────────────────────┐
│  分箱算子 (BINNING) 配置                    │
├────────────────────────────────────────────┤
│  输入变量: [credit_score]                  │
│  输出变量: [credit_grade]                  │
│                                            │
│  分箱区间定义:                               │
│  ┌──────────┬──────────┬──────────────┐    │
│  │  下界     │  上界    │  标签        │    │
│  ├──────────┼──────────┼──────────────┤    │
│  │  90      │  +∞      │  AAA         │    │
│  │  85      │  90      │  AA          │    │
│  │  75      │  85      │  A           │    │
│  │  60      │  75      │  B           │    │
│  │  -∞      │  60      │  C           │    │
│  └──────────┴──────────┴──────────────┘    │
│  包含上界: [✅]  包含下界: [✅]              │
│  [ + 添加区间 ]                             │
└────────────────────────────────────────────┘
```

**SCORECARD 算子**：

```
┌────────────────────────────────────────────┐
│  评分卡算子 (SCORECARD) 配置               │
├────────────────────────────────────────────┤
│  基准分: [600]  输出变量: [final_score]    │
│  后处理公式: [baseline + total_points]     │
│                                            │
│  变量得分表:                                │
│  变量: [overdue_ratio]                     │
│  ┌──────────────────┬──────────────┐       │
│  │  条件            │  得分        │       │
│  ├──────────────────┼──────────────┤       │
│  │  < 5%            │  +50         │       │
│  │  5% - 15%        │  +20         │       │
│  │  >= 15%          │  -30         │       │
│  └──────────────────┴──────────────┘       │
│  [ + 添加变量 ]  [ + 添加得分条件 ]          │
└────────────────────────────────────────────┘
```

**WEIGHTED_SUM 算子**：

```
┌────────────────────────────────────────────┐
│  加权计算算子 (WEIGHTED_SUM) 配置           │
├────────────────────────────────────────────┤
│  输出变量: [credit_score]                  │
│  总分范围: [0] ~ [100]                     │
│                                            │
│  分量权重表:                                │
│  ┌──────────────────────┬──────┬────────┐  │
│  │  输入指标             │  权重│  权重% │  │
│  ├──────────────────────┼──────┼────────┤  │
│  │  business_stability  │ 0.30 │  30%   │  │
│  │  tax_compliance      │ 0.25 │  25%   │  │
│  │  network_centrality  │ 0.15 │  15%   │  │
│  │  reputation_score    │ 0.15 │  15%   │  │
│  │  guarantee_risk_adj  │ 0.15 │  15%   │  │
│  └──────────────────────┴──────┴────────┘  │
│  权重总和: 1.00 ✅                           │
│  [ + 添加分量 ]                             │
└────────────────────────────────────────────┘
```

**DECISION_TABLE 算子**：

```
┌──────────────────────────────────────────────────────────┐
│  决策表算子 (DECISION_TABLE) 配置                         │
├──────────────────────────────────────────────────────────┤
│  条件变量: [credit_grade] [overdue_ratio]                 │
│  输出变量: [decision]                                     │
│                                                          │
│  决策矩阵:                                                │
│  ┌─────────────┬─────────────────┬──────────────────────┐│
│  │ credit_grade│  overdue_ratio  │       decision       ││
│  ├─────────────┼─────────────────┼──────────────────────┤│
│  │  AAA / AA   │     < 15%       │       APPROVE        ││
│  │  AAA / AA   │     >= 15%      │  APPROVE_WITH_COND   ││
│  │  A / B      │     < 10%       │  APPROVE_WITH_COND   ││
│  │  A / B      │     >= 10%      │       REJECT         ││
│  │     C       │      ANY        │       REJECT         ││
│  └─────────────┴─────────────────┴──────────────────────┘│
│  [ + 添加条件列 ]  [ + 添加规则行 ]                         │
└──────────────────────────────────────────────────────────┘
```

**LLM_JUDGE 算子**：

```
┌────────────────────────────────────────────┐
│  LLM 定性分析算子 (LLM_JUDGE) 配置         │
├────────────────────────────────────────────┤
│  输出变量: [qualitative_risk]              │
│                                            │
│  Prompt 模板:                              │
│  ┌────────────────────────────────────┐   │
│  │请对以下供应商进行风险定性分析:      │   │
│  │公司名称: {{company_name}}          │   │
│  │负面新闻数: {{negative_news_count}} │   │
│  │行业: {{industry}}                  │   │
│  │                                    │   │
│  │请输出: HIGH/MEDIUM/LOW             │   │
│  └────────────────────────────────────┘   │
│                                            │
│  输入变量映射:                              │
│  [company_name → company.name]            │
│  [negative_news_count → L3.metric]        │
│                                            │
│  期望输出格式: [enum: HIGH,MEDIUM,LOW]     │
│  置信度阈值: [0.7]                         │
│  超时(ms): [5000]  降级值: [MEDIUM]        │
└────────────────────────────────────────────┘
```

### 4.3 要素计算图 (Element DAG View)

使用 AntV G6 渲染：

```
节点类型与颜色规范:
  L1 属性 (attribute)     → 灰色矩形   #8C8C8C
  L3 atomic 指标          → 绿色圆角   #52C41A
  L3 derived 指标         → 橙色圆角   #FA8C16
  L3 composite 指标       → 紫色圆角   #722ED1
  L3 graph 指标           → 红色圆角   #F5222D
  L4 规则组 (frame)       → 蓝色六边形 #1677FF
  L4 规则实例 (step)      → 浅蓝菱形   #4096FF
  决策结果 (decision)     → 深绿六边形 #237804

边类型:
  数据依赖   → 实线灰色箭头
  加权聚合   → 带权重标签的实线橙色箭头
  覆盖关系   → 虚线橙色箭头（L4 override L3）
  规则流转   → 粗实线蓝色箭头
```

**DAG 展开示例（供应链金融授信）**：

```
[L1] registered_capital ─────┐
[L1] tax_score ──────────────┤
[L1] negative_news_count ────┤
                             ↓
[L1] invoice_data ──→ [atomic] total_invoice_90d
                  ──→ [atomic] overdue_invoice_amt
                  ──→ [atomic] invoice_count_90d
                             ↓
[atomic] total_invoice_90d ──┐
[atomic] overdue_invoice_amt ┤─→ [derived] overdue_ratio
                             ↓
[derived] overdue_ratio ──────→ [derived] business_stability
[derived] contract_util ──────→      ↓
[graph]   guarantee_depth ────→ [composite] credit_score
[graph]   page_rank ──────────→   (0.30+0.25+0.15+0.15+0.15)
[derived] reputation ─────────→      ↓
                                     ↓
                            [L4 RuleGroup: credit_assessment]
                             ├─[step R001] 资质检查  → eligible
                             ├─[step R002] SCORECARD  → credit_score_adj
                             ├─[step R003] 担保圈检查  → alert
                             ├─[step R004] BINNING    → credit_grade
                             ├─[step R005] WEIGHTED_SUM → credit_limit
                             └─[step R007] DECISION_TABLE → decision
                                     ↓
                          APPROVE / REJECT / APPROVE_WITH_CONDITIONS
```

---

## 五、后端 API 设计

### 5.1 规则组 CRUD

```
POST   /api/v1/rule-groups                    # 创建规则组
GET    /api/v1/rule-groups                    # 列表（含分页/过滤）
GET    /api/v1/rule-groups/{name}             # 获取规则组详情
PUT    /api/v1/rule-groups/{name}             # 更新规则组
DELETE /api/v1/rule-groups/{name}             # 删除规则组
GET    /api/v1/rule-groups/{name}/steps       # 获取规则实例列表
POST   /api/v1/rule-groups/{name}/steps       # 添加规则实例
PUT    /api/v1/rule-groups/{name}/steps/{id}  # 更新规则实例
DELETE /api/v1/rule-groups/{name}/steps/{id}  # 删除规则实例
POST   /api/v1/rule-groups/{name}/reorder     # 调整规则实例顺序
```

### 5.2 规则模拟执行

```
POST   /api/v1/rule-groups/{name}/simulate
```

Request Body:
```json
{
  "entity_data": {
    "status": "ACTIVE",
    "registered_capital": {"value": 5000000, "currency": "CNY"}
  },
  "pre_computed": {
    "credit_score": 87.5,
    "overdue_invoice_ratio": 0.03
  },
  "step_filter": ["R001", "R002"]
}
```

Response:
```json
{
  "steps": [
    {
      "step_id": "R001",
      "step_name": "基本资质检查",
      "condition_result": true,
      "condition_detail": {
        "type": "ALL_OF",
        "sub_conditions": [
          {"expr": "status == 'ACTIVE'", "result": true, "explain": "状态为激活"},
          {"expr": "registered_capital.value >= 1000000", "result": true, "explain": "注册资本500万 >= 100万"}
        ]
      },
      "action_taken": "SET_FLAG",
      "output": {"eligible": true},
      "duration_ms": 2
    }
  ],
  "final_output": {"eligible": true, "credit_score_adjusted": 92.0},
  "alerts": []
}
```

### 5.3 要素计算图

```
GET  /api/v1/metrics                          # 指标列表
GET  /api/v1/metrics/{name}                   # 指标详情
GET  /api/v1/metrics/{name}/dag               # 该指标的 DAG（上下游）
GET  /api/v1/dag/full                         # 完整 Schema DAG
     ?target=credit_score                     # 可选：聚焦目标节点
     ?depth=5                                 # 可选：展开深度
GET  /api/v1/dag/path                         # 从 source 到 target 的路径
     ?from=registered_capital&to=credit_score
```

### 5.4 YAML 生成

```
GET  /api/v1/rule-groups/{name}/export        # 导出为 YAML（Schema v2 canonical）
POST /api/v1/rule-groups/import               # 从 YAML 导入
POST /api/v1/rule-groups/validate-yaml        # 验证 YAML 合法性
```

### 5.5 算子查询

```
GET  /api/v1/operators                        # 算子列表（含参数 schema）
GET  /api/v1/operators/{name}/schema          # 算子参数 JSON Schema
POST /api/v1/operators/{name}/validate        # 验证算子参数
```

---

## 六、YAML 配置规范（Schema v2 扩展）

### 6.1 规则四元素在 YAML 中的对应关系

```yaml
# L4: business_logic.rule_definitions
rule_definitions:
  - name: credit_assessment_rule              # 规则组名称
    description: "供应商信用评估规则组"
    type: decision
    priority: 100

    # ① 作用对象
    applies_to:
      fact_objects: [Supplier]
      categories:
        company_scale: [LARGE, MEDIUM]        # 仅适用于大中型企业

    # ② 适用场景（前置条件）
    preconditions:
      - expression: "status == 'ACTIVE'"
        fail:
          reject: true
          reason: "企业状态非激活"

    # ③ 输入输出要素
    inputs:
      - metric: credit_score
      - metric: guarantee_chain_depth
      - metric: overdue_invoice_ratio
      - attribute: registered_capital
    outputs:
      - name: decision
        type: string
      - name: credit_limit
        type: Money
      - name: interest_rate
        type: decimal

# ④ 分析逻辑在 rule_logics 中定义
rule_logics:
  - name: credit_assessment_logic
    rule_definition: credit_assessment_rule
    steps:

      - id: R001
        name: "基本资质检查"
        when:
          all_of:
            - "status == 'ACTIVE'"
            - "registered_capital.value >= 1000000"
        then:
          operator: SET_FLAG
          params:
            flag: eligible
            value: true
        else:
          operator: REJECT
          params:
            reason: "不满足基本资质要求"

      - id: R002
        name: "信用评分调整（评分卡）"
        when:
          expression: "eligible == true"
        then:
          operator: SCORECARD
          params:
            output: credit_score_adjusted
            baseline: 600
            variables:
              - name: overdue_invoice_ratio
                points:
                  "< 0.05":   50
                  "0.05-0.15": 20
                  ">= 0.15": -30
              - name: negative_news_count
                points:
                  "0":    30
                  "1-3":  10
                  "> 3": -50

      - id: R003
        name: "担保圈风险检查"
        when:
          any_of:
            - "has_guarantee_circle == true"
            - "guarantee_chain_depth >= 3"
        then:
          operator: TRIGGER_ALERT
          params:
            alert_level: HIGH
            alert_type: GUARANTEE_RISK
            message: "存在担保圈或担保链过深风险"

      - id: R004
        name: "信用等级分箱"
        when:
          expression: "credit_score_adjusted IS NOT NULL"
        then:
          operator: BINNING
          params:
            input: credit_score_adjusted
            output: credit_grade
            inclusive_max: true
            bins:
              - range: [90, null]
                label: AAA
              - range: [85, 90]
                label: AA
              - range: [75, 85]
                label: A
              - range: [60, 75]
                label: B
              - range: [null, 60]
                label: C

      - id: R005
        name: "信用额度计算（加权）"
        when:
          expression: "eligible == true"
        then:
          operator: WEIGHTED_SUM
          params:
            output: credit_limit
            weights:
              - input: registered_capital_value
                weight: 0.5
              - input: total_contract_amount_value
                weight: 0.3
              - input: total_invoice_amount_90d_value
                weight: 0.2
            grade_multipliers:
              AAA: 1.8
              AA:  1.5
              A:   1.2
              B:   0.8
              C:   0.3
            grade_input: credit_grade

      - id: R007
        name: "最终授信决策"
        when:
          expression: "true"
        then:
          operator: DECISION_TABLE
          params:
            conditions:
              - variable: credit_grade
              - variable: overdue_invoice_ratio
                format: percentage
            output: decision
            matrix:
              - when: {credit_grade: [AAA, AA], overdue_invoice_ratio: "< 0.15"}
                result: APPROVE
              - when: {credit_grade: [AAA, AA], overdue_invoice_ratio: ">= 0.15"}
                result: APPROVE_WITH_CONDITIONS
              - when: {credit_grade: [A, B], overdue_invoice_ratio: "< 0.10"}
                result: APPROVE_WITH_CONDITIONS
              - when: {credit_grade: [A, B], overdue_invoice_ratio: ">= 0.10"}
                result: REJECT
              - default: REJECT
```

---

## 七、数据模型设计

### 7.1 后端数据模型扩展

```python
# ontology_engine/engine/rule/models.py 扩展

@dataclass
class RuleGroupDefinition:
    """规则组（框架）- 对应四元素的 ① ② ③"""
    name: str
    description: str
    type: Literal["constraint", "inference", "alert", "decision"]
    priority: int = 100
    applies_to: AppliesToConfig = field(default_factory=AppliesToConfig)
    preconditions: list[Precondition] = field(default_factory=list)
    inputs: list[IOElement] = field(default_factory=list)
    outputs: list[IOElement] = field(default_factory=list)
    enabled: bool = True
    schema_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

@dataclass
class RuleStep:
    """规则实例（具体逻辑）- 对应四元素的 ④"""
    id: str
    name: str
    rule_group: str                       # 所属规则组
    order: int                            # 执行顺序（支持拖拽调整）
    when: ConditionClause
    then: ActionClause
    else_: ActionClause | None = None
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)

@dataclass
class ActionClause:
    """动作子句：算子配置"""
    operator: str                         # 算子名称
    params: dict                          # 算子参数（JSON Schema 约束）
    output_mapping: dict[str, str] = field(default_factory=dict)  # 输出变量别名

@dataclass
class ConditionClause:
    """条件子句：支持单一/AND/OR"""
    type: Literal["expression", "all_of", "any_of"]
    expression: str | None = None         # type=expression 时使用
    sub_conditions: list[str] = field(default_factory=list)  # type=all_of/any_of

@dataclass
class OperatorSchema:
    """算子注册信息"""
    name: str
    display_name: str
    description: str
    category: Literal["binning", "scorecard", "weighted_sum", "decision_table",
                       "llm_judge", "flag", "alert", "compute", "switch", "graph"]
    param_schema: dict                    # JSON Schema 约束算子参数
    input_types: list[str]               # 支持的输入类型
    output_types: list[str]              # 产出的输出类型
```

### 7.2 DuckDB 存储新增表

```sql
-- 规则组表（框架层）
CREATE TABLE rule_groups (
    name        VARCHAR PRIMARY KEY,
    description TEXT,
    type        VARCHAR NOT NULL,
    priority    INTEGER DEFAULT 100,
    applies_to  JSON,
    preconditions JSON,
    inputs      JSON,
    outputs     JSON,
    enabled     BOOLEAN DEFAULT TRUE,
    schema_id   VARCHAR,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 规则实例表（逻辑层）
CREATE TABLE rule_steps (
    id           VARCHAR NOT NULL,
    rule_group   VARCHAR NOT NULL REFERENCES rule_groups(name),
    step_order   INTEGER NOT NULL,
    name         VARCHAR,
    when_clause  JSON,
    then_clause  JSON,
    else_clause  JSON,
    enabled      BOOLEAN DEFAULT TRUE,
    description  TEXT,
    tags         JSON,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_group, id)
);

-- 指标扩展表（补充值域/阈值/颜色）
CREATE TABLE metric_extensions (
    metric_name  VARCHAR PRIMARY KEY,
    value_domain JSON,
    thresholds   JSON,
    color        VARCHAR,
    unit         VARCHAR,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 算子注册表
CREATE TABLE operator_registry (
    name         VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    description  TEXT,
    category     VARCHAR,
    param_schema JSON,
    input_types  JSON,
    output_types JSON,
    enabled      BOOLEAN DEFAULT TRUE
);
```

---

## 八、模块拆解

### 8.1 后端模块调整（增量变更）

```
ontology_engine/
├── engine/
│   ├── rule/
│   │   ├── engine.py             # 现有 RuleEngine（DAG 模块升级）
│   │   ├── executor.py           # 现有 RuleExecutor
│   │   ├── dag.py                # ✨ 新增: RuleDAG 构建 + to_graph_data()
│   │   ├── models.py             # 扩展: RuleGroupDefinition + RuleStep
│   │   ├── evaluator.py          # 现有条件评估
│   │   └── operators/
│   │       ├── binning.py        # 升级: 支持 UI 友好格式
│   │       ├── scorecard.py      # 升级: 得分表 UI 友好格式
│   │       ├── weighted_sum.py   # ✨ 新增: WEIGHTED_SUM 算子
│   │       ├── decision_table.py # 升级: 矩阵配置 UI 友好格式
│   │       ├── llm_judge.py      # 升级: Prompt 模板 + 降级策略
│   │       └── registry.py       # ✨ 新增: 算子注册中心 + JSON Schema
│   │
│   └── metric/
│       ├── engine.py             # 现有 MetricEngine
│       └── dag.py                # 扩展: to_graph_data() 输出可视化 JSON
│
├── services/
│   ├── rule_service.py           # ✨ 新增: 规则组/实例 CRUD + YAML 导出
│   ├── dag_service.py            # ✨ 新增: 全量 DAG 构建 + 路径查询
│   └── simulation_service.py    # 升级: 支持单步/局部 DAG + 条件拆解详情
│
├── api/routes/
│   ├── rules.py                  # ✨ 新增: 规则 CRUD + 模拟 + YAML
│   ├── metrics.py                # ✨ 新增: 指标 CRUD + DAG 子图
│   ├── dag.py                    # ✨ 新增: 全局 DAG + 路径查询
│   └── operators.py              # ✨ 新增: 算子列表 + 参数 Schema
│
└── storage/duckdb/
    └── store.py                  # 扩展: rule_groups / rule_steps / metric_extensions
```

### 8.2 前端模块拆解

```
ontology-engine-ui/src/
├── pages/
│   ├── rules/
│   │   ├── RuleGroupListPage.tsx        # 规则组列表（卡片/表格切换）
│   │   ├── RuleGroupDetailPage.tsx      # 规则组详情（框架 + 实例列表 + 依赖图）
│   │   ├── RuleGroupEditorPage.tsx      # 规则组框架编辑（四元素表单）
│   │   └── RuleStepEditorPage.tsx       # 规则实例编辑（条件+算子+模拟面板）
│   │
│   ├── metrics/
│   │   ├── MetricListPage.tsx           # 指标列表（类型分组）
│   │   ├── MetricDetailPage.tsx         # 指标详情（含 DAG 子图）
│   │   └── MetricEditorPage.tsx         # 指标编辑（类型/公式/值域/阈值）
│   │
│   └── dag/
│       └── FullDAGPage.tsx              # 全局计算 DAG（G6 大图）
│
├── components/
│   ├── rule-editor/
│   │   ├── RuleGroupForm.tsx            # 四元素框架表单
│   │   ├── AppliesToSelector.tsx        # 作用对象选择器
│   │   ├── ApplicabilityConfig.tsx      # 适用场景配置（维度+分类+前置条件）
│   │   ├── IOElementsEditor.tsx         # 输入输出要素编辑器
│   │   ├── RuleStepList.tsx             # 规则实例列表（DnD 排序）
│   │   ├── ConditionEditor.tsx          # 条件编辑器（单一/ALL_OF/ANY_OF）
│   │   ├── ActionEditor.tsx             # 动作编辑器（算子选择 + 参数动态渲染）
│   │   └── SimulationPanel.tsx          # 单规则模拟执行面板
│   │
│   ├── operator-params/
│   │   ├── DynamicParamForm.tsx         # 基于 JSON Schema 的通用参数表单
│   │   ├── BinningParamEditor.tsx       # 分箱：区间可视化编辑
│   │   ├── ScorecardParamEditor.tsx     # 评分卡：得分表格编辑
│   │   ├── WeightedSumParamEditor.tsx   # 加权计算：权重滑块+总和校验
│   │   ├── DecisionTableEditor.tsx      # 决策表：矩阵可视化编辑
│   │   └── LLMJudgeParamEditor.tsx      # LLM分析：Prompt模板编辑器
│   │
│   └── dag-view/
│       ├── ElementDAGGraph.tsx          # 要素 DAG（G6，节点分层着色）
│       ├── RuleFlowGraph.tsx            # 规则流转图（X6，步骤节点）
│       ├── DAGNodeDetail.tsx            # 节点详情浮窗
│       └── DAGToolbar.tsx               # DAG 工具栏（过滤/定位/导出）
│
├── hooks/
│   ├── useRuleGroups.ts                 # 规则组数据（CRUD + YAML）
│   ├── useRuleSteps.ts                  # 规则实例数据（CRUD + 排序）
│   ├── useOperators.ts                  # 算子列表 + 参数 Schema
│   ├── useMetrics.ts                    # 指标数据（CRUD + DAG）
│   ├── useDAG.ts                        # DAG 数据（全量 + 路径）
│   └── useSimulation.ts                 # 模拟执行（单步/全量）
│
└── stores/
    ├── ruleStore.ts                     # 规则编排全局状态（Zustand）
    └── dagStore.ts                      # DAG 视图状态（布局/过滤/高亮）
```

---

## 九、实施路线

### Phase 2-A：规则编排核心（第 1-4 周）

| 周次 | 后端任务 | 前端任务 |
|------|---------|---------|
| W1 | `rule_groups`/`rule_steps` 数据模型 + DuckDB 表 + 基础 CRUD API | 规则组列表页 + 框架编辑器（四元素表单） |
| W2 | 算子注册中心 + JSON Schema + WEIGHTED_SUM 算子新增 + 现有算子升级 | 规则实例编辑器（条件编辑器 + 动作编辑器） |
| W3 | 单规则模拟 API（支持条件拆解详情） | 5 种算子参数配置器 + 模拟执行面板 |
| W4 | YAML 导入/导出 + Schema v2 合规验证 | 规则组详情页（实例列表 + YAML 预览）|

### Phase 2-B：要素 DAG 可视化（第 5-7 周）

| 周次 | 后端任务 | 前端任务 |
|------|---------|---------|
| W5 | `dag_service.py`：要素 DAG 构建 + `to_graph_data()` + 指标 DAG API | `ElementDAGGraph` 组件（G6 节点着色 + 层级布局） |
| W6 | 全局 DAG API + 路径查询 API | `FullDAGPage`（全量计算图 + 路径高亮 + 过滤）|
| W7 | 规则 DAG：`RuleDAG.to_graph_data()` + 规则流转图 API | `RuleFlowGraph` 组件（X6 步骤节点 + 条件/动作卡）|

### Phase 2-C：集成与深化（第 8-9 周）

| 周次 | 任务 |
|------|------|
| W8 | DAG 与规则编辑联动（点击节点→规则编辑页） + 影响分析集成（修改规则→自动提示影响范围） |
| W9 | LLM_JUDGE 完整实现（Prompt 模板 + 降级策略） + 端到端测试覆盖 + 文档更新 |

---

## 十、关键设计决策

### D1：规则组与规则实例存储分离

**决策**: `rule_groups` 存框架（四元素 ①②③），`rule_steps` 存实例（④），通过 `rule_group` 字段关联。

**理由**: 框架变更不频繁（作用对象/适用场景/IO 声明稳定），实例变更频繁（逻辑表达式随业务调整）。分离存储支持独立 diff 和版本管理，也与 Schema v2 `rule_definitions` + `rule_logics` 的双层结构对齐。

### D2：算子参数统一用 JSON Schema 描述

**决策**: 每个算子注册时提供 `param_schema`（JSON Schema），前端动态渲染基础参数表单，复杂算子可提供专用编辑器覆盖基础渲染。

**理由**: 算子可扩展，前端不应与算子强耦合。新增算子只需后端注册，前端自动适配，专用编辑器按需补充（如 DECISION_TABLE 需要矩阵编辑器）。

### D3：DAG 可视化与执行 DAG 共用数据结构

**决策**: `MetricDAG.to_graph_data()` 和 `RuleDAG.to_graph_data()` 均输出 `{nodes: [...], edges: [...]}` 格式（兼容 G6 5.x / X6 2.x），前端无需了解后端 NetworkX 内部结构。

**理由**: 与现有 `visualization/builders.py` 设计保持一致，复用前端图渲染基础设施。

### D4：规则实例模拟不写存储

**决策**: 模拟执行（`/simulate`）使用 `dry_run=True`，仅内存执行，不写入持久化存储，不触发预警推送。

**理由**: 与可视化模块 `RuleChainSimulator.dry_run` 决策一致，保证模拟的无副作用性。

### D5：LLM_JUDGE 三级降级策略

**决策**: ① LLM 超时/报错 → 使用配置的 `fallback_value`；② 置信度低于阈值 → 返回值+置信度标记（不阻断）；③ 完全不可用 → 跳过该步骤，打 `SKIPPED` 标记。降级值必须由规则设计者显式配置。

**理由**: LLM 调用不稳定，不能因 LLM 失败中断整个规则链。降级策略透明可配置，可审计。

### D6：WEIGHTED_SUM 为新算子，与 composite 指标的关系

**决策**: L3 `composite` 指标的权重聚合（`components`）在 MetricEngine 内计算；L4 规则中的 `WEIGHTED_SUM` 算子用于**基于规则动态调整权重**的场景（如根据企业等级使用不同权重乘数）。两者不互相替代。

**理由**: L3 composite 是静态权重配置（Schema 定义），L4 WEIGHTED_SUM 是动态规则逻辑，语义不同。

---

## 十一、验收标准

### Phase 2-A MVP 验收

- [ ] 用户可通过页面完整创建一个规则组（含四元素：作用对象 + 适用场景 + I/O要素 + 至少1条规则实例）
- [ ] 5 种算子（BINNING/SCORECARD/WEIGHTED_SUM/DECISION_TABLE/LLM_JUDGE）均可通过 UI 配置参数
- [ ] 用户可通过模拟面板输入测试数据，查看单条规则实例的执行结果（含条件拆解详情）
- [ ] 可将规则组导出为符合 Schema v2 canonical spec 的 YAML 文件
- [ ] 可从 YAML 文件导入规则组（合规验证通过后写入存储）

### Phase 2-B DAG 验收

- [ ] 全量 DAG 视图展示从 L1 原子属性 → L3 指标 → L4 规则 → 最终决策的完整链路
- [ ] 节点按类型分层着色（L1/atomic/derived/composite/graph/rule_group/rule_step/decision）
- [ ] 点击任意节点可查看该节点的详情（指标定义/规则四元素/算子参数）
- [ ] 支持按目标结果反向过滤：选定 `credit_score`，只展示其上游 DAG

### Phase 2-C 完整验收

- [ ] 规则编辑后，影响链分析自动提示受影响的下游规则和指标（BFS 影响路径）
- [ ] LLM_JUDGE 降级策略完整：超时降级 / 低置信度标记 / 完全不可用跳过，均可配置
- [ ] 所有规则管理 API 端点有完整测试覆盖（单元测试覆盖率 ≥ 80%）
- [ ] 端到端场景：供应链金融授信完整规则链可在 UI 上创建、模拟、导出 YAML

---

## 十二、文档关联

| 文档 | 关系 |
|------|------|
| `docs/06-module-detailed-design/06-rule-engine.md` | 现有规则引擎设计（本计划扩展基础） |
| `docs/06-module-detailed-design/04-metric-engine.md` | 指标引擎（DAG 模块扩展依据） |
| `docs/05-schema-v2/09-canonical-schema-spec.md` | YAML 规范（导入/导出合规基准，单一事实源） |
| `docs/08-visualization-system.md` | 可视化系统（DAG 渲染基础设施复用） |
| `detail/plans/2026-04-15-phase2-unified-retrieval-design.md` | Phase 2 整体检索设计（并行推进） |
| `discuss/` | 本计划形成的关键决策（D1-D6）应在 session 后记录 |
