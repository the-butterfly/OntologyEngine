# 语义空间架构

> **Status**: v1.0
> **Date**: 2026-04-12

## 1. 概念定义

### 1.1 什么是语义空间 (Semantic Space)

语义空间是 OntologyEngine 的顶层容器单位。它包含：

1. **完整的企业知识资产**：L1-L4 声明 + 实例数据
2. **版本历史**：每层的变更记录
3. **授权配置**：向消费视图共享的内容
4. **同步配置**：与外部数据集的映射关系

```
语义空间 (Semantic Space)
├── 声明层 (Declarations)
│   ├── L1: 事实对象定义
│   ├── L2: 分类定义
│   ├── L3: 分析要素定义
│   └── L4: 规则声明
├── 实例层 (Instances)
│   ├── 实体实例 (Entity Instances)
│   ├── 分类标签 (Category Tags)
│   ├── 指标值 (Metric Values)
│   └── 规则逻辑实例 (Rule Logic Instances)
├── 版本历史 (Version History)
├── 数据集映射 (Dataset Mappings)
└── 授权配置 (Authorizations)
```

### 1.2 两类语义空间

| 类型 | 用途 | 特点 |
|------|------|------|
| **管理空间 (Management Space)** | 权威数据源 | 完整控制，可编辑，可同步外部数据 |
| **消费视图 (Consumption View)** | 数据消费方 | 只读，授权获得，可聚合多个管理空间 |

**关系图**：
```
┌─────────────────────────────────────────────────────────────┐
│                    OntologyEngine                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────┐          ┌─────────────────┐         │
│   │  管理空间 A      │          │  管理空间 B      │         │
│   │  (Management)   │          │  (Management)   │         │
│   │                 │          │                 │         │
│   │  L1-L4 Decl     │          │  L1-L4 Decl     │         │
│   │  Instances      │          │  Instances      │         │
│   │  Datasets       │          │  Datasets       │         │
│   └────────┬────────┘          └────────┬────────┘         │
│            │                            │                  │
│            │     Authorization         │                  │
│            ▼                            ▼                  │
│   ┌─────────────────────────────────────────┐             │
│   │           消费视图 (Consumption View)     │             │
│   │                                          │             │
│   │  view_001 = {                            │             │
│   │    from A: L1(Supplier), L3, L4          │             │
│   │    from B: L1(Customer), L2, L3         │             │
│   │  }                                       │             │
│   └─────────────────────────────────────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 空间状态机

```
                    ┌──────────────────┐
                    │      DRAFT       │  ← 初始状态，可编辑
                    └────────┬─────────┘
                             │ activate()
                             ▼
                    ┌──────────────────┐
         ┌─────────│     ACTIVE       │  ← 生效状态，可执行/消费
         │         └────────┬─────────┘
         │                  │
         │         publish()│
         │                  ▼
         │         ┌──────────────────┐
         │         │   PUBLISHED      │  ← 版本快照（不可修改）
         │         └──────────────────┘
         │                  │
         │ rollback() │   activate()
         │                  │
    archive()         ◄─────┘
         │
         ▼
┌──────────────────┐
│    ARCHIVED      │  ← 归档状态，保留历史
└──────────────────┘
```

### 状态说明

| 状态 | 含义 | 可编辑 | 可执行 | 可消费 |
|------|------|--------|--------|--------|
| `DRAFT` | 编辑中 | ✅ | ❌ | ❌ |
| `ACTIVE` | 生效中 | ⚠️ (需解锁) | ✅ | ✅ |
| `PUBLISHED` | 已发布快照 | ❌ | ❌ | ✅ (读快照) |
| `ARCHIVED` | 已归档 | ❌ | ❌ | ❌ |

---

## 3. 授权模型

### 3.1 授权粒度

授权可以在多个维度进行：

| 维度 | 选项 | 说明 |
|------|------|------|
| **层** | L1 / L2 / L3 / L4 | 可选择部分层授权 |
| **声明类型** | fact_objects, categorizations, analytical_elements, business_logic | 更细粒度 |
| **实例范围** | 全部 / 筛选条件 | Entity 可按条件过滤 |

### 3.2 授权配置示例

```yaml
# 管理空间 A 的授权配置
authorizations:
  - id: auth_001
    target_view: "view_001"
    enabled: true
    granted:
      layers:
        - L1_fact_objects
        - L3_analytical_elements
        - L4_business_logic
      scope:
        L1_fact_objects:
          - types: [Supplier, CoreEnterprise]  # 只授权这两类
        L3_analytical_elements:
          - all: true  # 全部指标
    created_at: "2026-04-12T00:00:00Z"
    created_by: "admin"
```

### 3.3 消费视图的聚合

消费视图可以聚合多个管理空间的授权：

```yaml
# 消费视图定义
consumption_view:
  id: "view_001"
  name: "供应链金融总览"
  source_authorizations:
    - space_id: "space_A"      # 管理空间 A
      auth_id: "auth_001"
    - space_id: "space_B"      # 管理空间 B
      auth_id: "auth_002"
  merged_layers:
    L1_fact_objects:
      # 自动合并来自 A 和 B 的 Fact Object 定义
    L4_business_logic:
      # 自动合并规则声明，合并时处理冲突
```

---

## 4. 路由结构

### 4.1 API 路由

```
/v1/management/
├── /spaces                              # Space CRUD
│   ├── POST /                          # 创建管理空间
│   ├── GET /                           # 列表
│   └── /{spaceId}                      # 单个空间操作
│
├── /{spaceId}/
│   ├── /schema/                        # L1-L4 声明管理
│   │   ├── /L1/fact-objects            # 事实对象
│   │   ├── /L2/categorizations         # 分类定义
│   │   ├── /L3/analytical-elements     # 分析要素
│   │   └── /L4/rules/                  # 规则声明
│   │       ├── /definitions            # 规则声明 CRUD
│   │       └── /logics                 # 规则实例 CRUD
│   │
│   ├── /instances/                     # 实例管理
│   │   ├── /entities                   # 实体实例
│   │   ├── /category-tags              # 分类标签
│   │   └── /metrics                    # 指标值
│   │
│   ├── /datasets/                      # 数据集管理
│   │   ├── /{datasetId}/mappings       # 映射规则
│   │   └── /{datasetId}/sync          # 同步配置
│   │
│   ├── /versions/                      # 版本管理
│   │   ├── /{layer}/history           # 指定层版本历史
│   │   └── /{layer}/{version}/rollback
│   │
│   ├── /authorizations/               # 授权管理
│   │   ├── POST /                     # 创建授权
│   │   ├── GET /                      # 列表
│   │   └── /{authId}                 # 单个操作
│   │
│   └── /sync/                         # 同步执行
│       ├── POST /trigger              # 触发同步
│       └── GET /history              # 同步历史

/v1/consumption/
├── /spaces                            # 消费视图 CRUD
│   ├── POST /                         # 创建消费视图
│   ├── GET /                          # 列表
│   └── /{viewId}                      # 单个视图
│
└── /{viewId}/
    ├── /visualize/                    # Schema 可视化
    ├── /execute/                      # 规则执行
    │   ├── /analyze                   # 执行分析
    │   └── /simulate                  # What-if 模拟
    └── /entities/                     # 实例查询（只读）
```

### 4.2 页面路由 (Frontend)

```
/management/
├── /                                   # Space 列表
├── /{spaceId}/
│   ├── /overview                      # 空间概览
│   ├── /schema                        # Schema 编辑器
│   │   ├── /L1                        # 事实对象
│   │   ├── /L2                        # 分类定义
│   │   ├── /L3                        # 分析要素
│   │   └── /L4                        # 规则
│   │       ├── /definitions           # 声明管理
│   │       └── /logics                # 实例管理
│   ├── /entities                      # 实体管理
│   ├── /datasets                      # 数据集配置
│   ├── /versions                      # 版本历史
│   ├── /authorizations                # 授权配置
│   └── /sync                          # 同步管理

/consumption/
├── /                                   # 视图列表
└── /{viewId}/
    ├── /overview                      # 视图概览
    ├── /visualize                     # Schema 可视化
    ├── /execute                       # 规则执行
    └── /simulate                      # What-if 模拟
```

---

## 5. 数据边界

### 5.1 管理空间数据边界

- 拥有完整的 L1-L4 声明
- 拥有全部实例数据
- 可配置 Dataset 同步
- 可创建/管理授权

### 5.2 消费视图数据边界

- 只读访问授权数据
- 可执行已授权的规则
- 可进行 What-if 模拟
- **不拥有** 原始实例数据（只持有引用或缓存）

---

## 6. 与 Schema v2 的关系

语义空间是 Schema v2 的**顶层容器**。

```
语义空间 (Semantic Space)
│
├── Schema v2 结构
│   ├── L1_fact_objects (声明)
│   ├── L2_categorizations (声明)
│   ├── L3_analytical_elements (声明)
│   └── L4_business_logic (声明)
│       ├── rule_definitions (声明)
│       └── rule_logics (实例)
│
└── 实例数据 (Instances)
    ├── entities (实体实例)
    ├── category_tags (分类标签)
    └── metric_values (指标值)
```

**核心原则**：
- 一个管理空间对应一个完整的 Schema v2
- Schema v2 的内容在空间内自洽
- 消费视图可以跨空间聚合

---

## 7. 术语对照

| 英文 | 中文 | 说明 |
|------|------|------|
| Semantic Space | 语义空间 | 顶层容器 |
| Management Space | 管理空间 | 权威数据源 |
| Consumption View | 消费视图 | 授权数据视图 |
| Authorization | 授权 | 管理→消费的映射配置 |
| Declaration | 声明 | L1-L4 的定义 |
| Instance | 实例 | 具体数据和配置 |
| Layer | 层 | L1/L2/L3/L4 |
| Sync | 同步 | 从 Dataset 更新实例 |

---

*文档结束*
