# API 重新设计提案 v2.0

> **日期**: 2026-04-17
> **状态**: 整合 Phase 2 Rule Groups 与 L4 Schema 语义
> **版本**: v2.0
> **维护人**: the-butterfly

---

## 目录

1. [现有语义模型分析](#一现有语义模型分析)
2. [问题全量分析](#二问题全量分析)
3. [整合后的 API 设计](#三整合后的-api-设计)
4. [前端关联影响分析](#四前端关联影响分析)
5. [全量迁移清单](#五全量迁移清单)
6. [实施风险评估](#六实施风险评估)

---

## 一、现有语义模型分析

### 1.1 OntologyEngine 核心概念

```
Semantic Space (语义空间)
├── L1: Fact Objects (要素/实体定义)
│   └── concept_type: Supplier, Product, Contract...
│   └── properties, relations
│
├── L2: Categorizations (分类体系)
│   └── 行业分类, 风险等级, 企业规模...
│   └── dimensions, values
│
├── L3: Analytical Elements (分析要素)
│   └── metrics, indicators, scores
│   └── formula, dependencies, overridable
│
└── L4: Business Logic (业务逻辑)
    ├── Rule Definitions (规则定义) ← 声明式
    │   └── applies_to, inputs, outputs, preconditions
    │
    └── Rule Logics (规则实例) ← 执行逻辑
        └── when, then_action, else_action, applicable_conditions

Instances (实例数据)
├── Entities (实体实例)
├── Relations (关系实例)
├── Category Tags (分类标签)
└── Metric Values (指标值)

Views (消费视图)
└── Space 的只读投影，供前端/Agent 消费
```

### 1.2 Phase 2 Rule Groups (新模型)

```
Rule Group (规则组)
├── id, name, description, type, priority
├── applies_to: { fact_objects, categories }
├── inputs: [{ name, type, metric, attribute }]
├── outputs: [{ name, type }]
├── preconditions: [{ expression, fail }]
└── enabled

Rule Steps (规则步骤) ← 与 L4 Rule Logics 对应
├── id, name, order
├── when: { type, expression, sub_conditions }
├── then: { operator, params, output_mapping }
└── else: { operator, params, output_mapping }
```

### 1.3 语义模型映射 (OntologyEngine ↔ Palantir)

| OntologyEngine 语义 | Palantir 类比 | 当前 API 路径 |
|---------------------|---------------|---------------|
| Semantic Space | Ontology | `/v1/management/spaces` |
| L1 Fact Objects | Object Types | `/v1/management/{id}/schema/L1/fact-objects` |
| L2 Categorizations | Link Types | `/v1/management/{id}/schema/L2/categorizations` |
| L3 Analytical Elements | Actions | `/v1/management/{id}/schema/L3/analytical-elements` |
| L4 Rule Definitions | Functions (Declarations) | `/v1/management/{id}/schema/L4/rules/definitions` |
| L4 Rule Logics | Functions (Implementations) | `/v1/management/{id}/schema/L4/rules/logics` |
| Phase 2 Rule Groups | - | `/v1/rule-groups` |
| Phase 2 Rule Steps | - | `/v1/rule-groups/{name}/steps` |
| Views | Object Sets | `/v1/consumption/views` |
| Actions (执行) | - | `/v1/rules/execute`, `/v1/consumption/views/{id}/execute` |

---

## 二、问题全量分析

### 2.0 关键概念澄清

#### 2.0.1 Schema vs Semantic Space 的关系

```
当前问题: 两套 Schema 概念并存，容易混淆

┌─────────────────────────────────────────────────────────────────┐
│  旧架构: Schema (全局单例)                                        │
│  ├── /v1/schema                    ← KGMLSchema (内存中的)       │
│  ├── /v1/schema/load              ← 加载 YAML                   │
│  ├── /v1/schema/rollback/{v}      ← Schema 版本回退              │
│  └── 问题: 不关联 Space，是全局状态                               │
├─────────────────────────────────────────────────────────────────┤
│  新架构: Semantic Space (Space 包含完整 Schema)                  │
│  ├── /v1/spaces/{id}/schema       ← Space 内的 Schema L1-L4     │
│  ├── /v1/spaces/{id}/activate     ← 激活时同步到消费视图          │
│  └── 问题: 与旧 Schema 并存                                      │
└─────────────────────────────────────────────────────────────────┘

澄清:
- Schema (大写 S) = KGMLSchema = 旧架构全局 Schema
- schema (小写 s) = Space 内的 L1-L4 层 = 新架构
- 关系: Space.schema 包含完整的 L1-L4 定义
```

#### 2.0.2 当前所有路由前缀清单

| 前缀 | 文件 | 端点数量 | 说明 |
|------|------|---------|------|
| `/v1/schema` | schema.py | 5 | 旧全局 Schema 管理 |
| `/v1/entities` | entities.py | 5 | 实体 CRUD |
| `/v1/relations` | relations.py | 1 | 关系创建 |
| `/v1/analysis` | analysis.py | 2 | 分析执行 (与 consumption 重复) |
| `/v1/ingestion` | ingestion.py | 3 | 批量数据导入 |
| `/v1/datasets` | datasets.py | 9 | 数据集管理 |
| `/v1/visualize` | visualization.py | 6 | 可视化 (与 consumption 重复) |
| `/v1/management` | management.py | 35+ | Space 管理 (prefix 过长) |
| `/v1/categories` | categories.py | 7 | 分类管理 |
| `/v1/incremental` | incremental.py | 5 | 增量更新 |
| `/v1/query` | query.py | 10 | 知识检索 |
| `/v1/consumption` | consumption.py | 9 | 消费视图 |
| `/v1/spaces` | semantic_spaces.py | 15+ | **与 management 重复!** |
| `/v1` (无) | rules.py | 17 | 规则组 + 算子 |
| `/v1/rule-groups` | rules.py | - | 实际是 rules.py 的一部分 |

**总计: 15 个路由文件，约 130+ 端点**

#### 2.0.3 版本回退端点位置

```
Schema 版本回退 (旧架构):
└── POST /v1/schema/rollback/{target_version}     ← schema.py:97

Space 版本回退 (新架构):
├── GET /v1/management/{space_id}/versions         ← management.py:1043
├── POST /v1/management/{space_id}/versions        ← management.py:1067
└── POST /v1/management/{space_id}/versions/{version}/rollback  ← management.py:1091
```

### 2.1 完整 API 端点清单 (按文件分组)

#### schema.py (当前 prefix: `/v1/schema`) ← 旧架构

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/load` | 14 | 加载 Schema |
| GET | `/` | 41 | 获取当前 Schema |
| POST | `/reload` | 59 | 热重载 Schema |
| GET | `/versions` | 84 | Schema 版本历史 |
| POST | `/rollback/{target_version}` | 97 | **Schema 版本回退** |

#### entities.py (当前 prefix: `/v1/entities`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/` | 35 | 创建实体 |
| POST | `/batch` | 61 | 批量创建 |
| GET | `/{entity_id}` | 86 | 获取实体 |
| POST | `/query` | 116 | 查询实体 |
| GET | `/{entity_id}/neighbors` | 136 | 邻居查询 |

#### relations.py (当前 prefix: `/v1/relations`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/` | 24 | 创建关系 |

#### analysis.py (当前 prefix: `/v1/analysis`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/execute` | 27 | 执行分析 |
| POST | `/dry-run` | 58 | 干运行预览 |

#### ingestion.py (当前 prefix: `/v1/ingestion`) ← **提案遗漏**

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/import` | 39 | 批量导入实体/关系 |
| POST | `/import/dict` | 74 | 从字典导入 |
| POST | `/validate` | 104 | 验证导入数据 |

#### datasets.py (当前 prefix: `/v1/datasets`) ← **提案遗漏**

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/` | 17 | 创建数据集 |
| GET | `/` | 39 | 列出数据集 |
| GET | `/{dataset_id}` | 51 | 获取数据集 |
| PUT | `/{dataset_id}` | 69 | 更新数据集 |
| DELETE | `/{dataset_id}` | 94 | 删除数据集 |
| POST | `/{dataset_id}/entities` | 107 | 添加实体到数据集 |
| GET | `/{dataset_id}/entities` | 126 | 获取数据集实体 |
| POST | `/{dataset_id}/snapshots` | 140 | 创建数据集快照 |
| GET | `/{dataset_id}/snapshots` | 159 | 获取数据集快照列表 |
| POST | `/compare` | 172 | 比较两个数据集 |

#### visualization.py (当前 prefix: `/v1/visualize`) ← **提案遗漏**

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| GET | `/schema/graph` | 23 | Schema 图数据 |
| GET | `/entities` | 46 | 可视化实体列表 |
| GET | `/metrics/{entity_id}` | 62 | 指标快照 |
| GET | `/rule-chain/{dimension}` | 80 | 规则链 DAG |
| POST | `/simulate` | 107 | 模拟执行 |
| GET | `/execution/{entity_id}/{dimension}` | 132 | 执行追溯 |

#### categories.py (当前 prefix: `/v1/categories`) ← **提案遗漏**

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/dimensions/applicability` | 18 | 保存维度适用性 |
| GET | `/dimensions/{dimension_id}/applicability` | 45 | 获取维度适用性 |
| DELETE | `/dimensions/{dimension_id}/applicability/{object_type}` | 59 | 删除维度适用性 |
| POST | `/rule-mappings` | 74 | 保存分类-规则映射 |
| GET | `/rule-mappings` | 102 | 获取分类-规则映射 |
| DELETE | `/rule-mappings/{dimension_id}/{dimension_value}/{rule_group_id}` | 116 | 删除映射 |
| GET | `/entities/{entity_id}/versions` | 137 | 实体版本列表 |
| GET | `/entities/{entity_id}/versions/{version}` | 148 | 实体版本详情 |

#### incremental.py (当前 prefix: `/v1/incremental`) ← **提案遗漏**

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/import` | 21 | 增量导入 |
| GET | `/batches` | 54 | 变更批次列表 |
| GET | `/batches/{batch_id}` | 67 | 获取变更批次 |
| GET | `/batches/{batch_id}/rollback-actions` | 85 | 回滚操作 |
| POST | `/impact` | 101 | 计算变更影响 |

#### management.py (当前 prefix: `/v1/management`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/spaces` | 184 | 创建 Space |
| GET | `/spaces` | 264 | 列出 Spaces |
| GET | `/spaces/{space_id}` | 307 | 获取 Space |
| PUT | `/spaces/{space_id}` | 349 | 更新 Space |
| DELETE | `/spaces/{space_id}` | 465 | 删除 Space |
| POST | `/spaces/{space_id}/activate` | 376 | 激活 Space |
| POST | `/spaces/{space_id}/deactivate` | 442 | 停用 Space |
| POST | `/spaces/{space_id}/archive` | 485 | 归档 Space |
| GET | `/{space_id}/schema/L1/fact-objects` | 599 | L1 要素列表 |
| POST | `/{space_id}/schema/L1/fact-objects` | 611 | 添加 L1 要素 |
| GET | `/{space_id}/schema/L2/categorizations` | 643 | L2 分类列表 |
| POST | `/{space_id}/schema/L2/categorizations` | 655 | 添加 L2 分类 |
| GET | `/{space_id}/schema/L3/analytical-elements` | 687 | L3 要素列表 |
| POST | `/{space_id}/schema/L3/analytical-elements` | 699 | 添加 L3 要素 |
| GET | `/{space_id}/schema/L4/rules/definitions` | 732 | L4 规则定义列表 |
| POST | `/{space_id}/schema/L4/rules/definitions` | 744 | 添加规则定义 |
| GET | `/{space_id}/schema/L4/rules/definitions/{rule_id}` | 777 | 获取规则定义 |
| PUT | `/{space_id}/schema/L4/rules/definitions/{rule_id}` | 797 | 更新规则定义 |
| DELETE | `/{space_id}/schema/L4/rules/definitions/{rule_id}` | 834 | 删除规则定义 |
| GET | `/{space_id}/schema/L4/rules/logics` | 860 | L4 规则逻辑列表 |
| POST | `/{space_id}/schema/L4/rules/logics` | 872 | 添加规则逻辑 |
| GET | `/{space_id}/schema/L4/rules/logics/{logic_id}` | 910 | 获取规则逻辑 |
| PUT | `/{space_id}/schema/L4/rules/logics/{logic_id}` | 930 | 更新规则逻辑 |
| DELETE | `/{space_id}/schema/L4/rules/logics/{logic_id}` | 967 | 删除规则逻辑 |
| GET | `/{space_id}/schema/L4/rules/dependency-graph` | 1384 | 规则依赖图 |
| GET | `/{space_id}/instances/entities` | 993 | 实体实例列表 |
| POST | `/{space_id}/instances/entities` | 1012 | 添加实体实例 |
| GET | `/{space_id}/instances/relations` | 1282 | 关系实例列表 |
| POST | `/{space_id}/instances/relations` | 1294 | 添加关系实例 |
| GET | `/{space_id}/versions` | 1043 | 版本列表 |
| POST | `/{space_id}/versions` | 1067 | 创建快照 |
| POST | `/{space_id}/versions/{version}/rollback` | 1091 | **Space 版本回滚** |
| POST | `/{space_id}/schema/load-from-yaml` | 1111 | 从 YAML 加载 Schema |
| POST | `/{space_id}/instances/load-from-yaml` | 1216 | 从 YAML 加载实例 |
| GET | `/{space_id}/schema/overview` | 1313 | Schema 总览 |

#### rules.py (当前 prefix: `/v1`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| GET | `/rules` | 43 | 列出规则 |
| POST | `/rules/execute` | 80 | 执行规则 |
| POST | `/rule-groups` | 136 | 创建规则组 |
| GET | `/rule-groups` | 153 | 列出规则组 |
| GET | `/rule-groups/{id}` | 169 | 获取规则组 |
| PUT | `/rule-groups/{id}` | 188 | 更新规则组 |
| DELETE | `/rule-groups/{id}` | 206 | 删除规则组 |
| POST | `/rule-groups/{name}/steps` | 252 | 添加步骤 |
| GET | `/rule-groups/{name}/steps` | 270 | 列出步骤 |
| PUT | `/rule-groups/{name}/steps/{step_id}` | 286 | 更新步骤 |
| DELETE | `/rule-groups/{name}/steps/{step_id}` | 305 | 删除步骤 |
| POST | `/rule-groups/{name}/steps/reorder` | 322 | 重排步骤 |
| POST | `/rule-groups/{name}/simulate` | 351 | 模拟执行 |
| POST | `/rule-groups/import` | 418 | 导入 YAML |
| POST | `/rule-groups/validate-yaml` | 436 | 验证 YAML |
| GET | `/rule-groups/{name}/export` | 452 | 导出 YAML |
| GET | `/operators` | 476 | 列出算子 |
| GET | `/operators/{name}/schema` | 488 | 算子 Schema |
| GET | `/dag/full` | 503 | 完整 DAG |
| GET | `/dag/path` | 521 | DAG 路径 |
| GET | `/metrics/{name}/dag` | 537 | 指标 DAG |

#### consumption.py (当前 prefix: `/v1/consumption`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| GET | `/views` | 75 | 列出视图 |
| GET | `/views/{view_id}` | 102 | 获取视图 |
| GET | `/views/{view_id}/entities` | 133 | 视图实体列表 |
| GET | `/views/{view_id}/visualize/schema-graph` | 156 | Schema 图 |
| GET | `/views/{view_id}/rules/dependency-graph` | 323 | 规则依赖图 |
| GET | `/views/{view_id}/rules/for-entity/{entity_id}` | 469 | 实体适用规则 |
| POST | `/views/{view_id}/execute/analyze` | 583 | 执行分析 |
| POST | `/views/{view_id}/execute/simulate` | 604 | What-if 模拟 |

#### query.py (当前 prefix: `/v1/query`)

| 方法 | 路径 | 行号 | 说明 |
|------|------|------|------|
| POST | `/vector` | 37 | 向量搜索 |
| POST | `/hybrid` | 56 | 混合搜索 |
| POST | `/graph` | 84 | 图遍历 |
| GET | `/pattern-match/{concept}` | 128 | 模式匹配 (GET) |
| POST | `/pattern-match/{concept}` | 150 | 模式匹配 (POST) ← 重复 |
| GET | `/traverse/{entity_id}` | 172 | 图遍历 (GET) |
| POST | `/traverse/{entity_id}` | 205 | 图遍历 (POST) ← 重复 |
| GET | `/path/{from_entity_id}/{to_entity_id}` | 256 | 路径查询 |
| POST | `/path` | 286 | 路径查询 ← 重复 |
| GET | `/trace/{entity_id}` | 234 | 追溯 |

---

### 2.2 问题汇总

#### 2.2.1 路由重复问题

| # | 问题类型 | 路由 A | 路由 B | 严重程度 | 文件位置 |
|---|---------|--------|--------|---------|---------|
| 1 | Space 管理重复 | `/v1/management/spaces` | `/v1/spaces` (semantic_spaces.py) | **高** | management.py:184, semantic_spaces.py |
| 2 | 规则定义重复 | `/v1/rule-groups` | `/{space_id}/schema/L4/rules/definitions` | **高** | rules.py:136, management.py:744 |
| 3 | 规则逻辑重复 | `/v1/rule-groups/{name}/steps` | `/{space_id}/schema/L4/rules/logics` | **高** | rules.py:252, management.py:872 |
| 4 | 执行端点重复 | `/v1/rules/execute` | `/v1/consumption/views/{id}/execute/analyze` | **高** | rules.py:80, consumption.py:583 |
| 5 | 依赖图重复 | `/{space_id}/schema/L4/rules/dependency-graph` | `/views/{id}/rules/dependency-graph` | **中** | management.py:1384, consumption.py:323 |
| 6 | 视图管理重复 | `/v1/consumption/views` | management.py 内的 view 创建 | **中** | consumption.py:75, management.py:184 |
| 7 | 可视化重复 | `/v1/visualize/...` | `/v1/consumption/views/{id}/visualize/...` | **中** | visualization.py, consumption.py:156 |
| 8 | 分析执行重复 | `/v1/analysis/execute` | `/v1/consumption/views/{id}/execute/analyze` | **中** | analysis.py:27, consumption.py:583 |

#### 2.2.2 概念混淆问题

| # | 问题 | 当前表现 | 建议 |
|---|------|---------|------|
| 1 | Schema vs schema | `/v1/schema` (旧 KGMLSchema) vs `/v1/spaces/{id}/schema` (L1-L4) | 明确区分：Ontology vs Space Schema |
| 2 | 无全局 Schema | `/v1/schema` 不关联 Space | 是否保留旧架构？ |
| 3 | Space 包含 Schema | Space 是 L1-L4 的容器 | 关系明确 |
| 4 | View 是 Space 的投影 | View 自动创建并同步 | 关系明确 |

#### 2.2.3 命名不一致问题

| # | 问题类型 | 当前表现 | 建议 | 文件位置 |
|---|---------|---------|------|---------|
| 1 | 路径参数混用 | `/rule-groups/{id}` 和 `/rule-groups/{name}/steps` 混用 id/name | 统一用 `id` (UUID) | rules.py:169,252 |
| 2 | 复数/单数混乱 | `/rules` (复数集合) vs `/rule-groups/{name}` (单数路径) | 集合用复数，单个资源用 `{id}` | rules.py:43,169 |
| 3 | 嵌套路径缺少资源名 | `/{space_id}/instances/entities` (缺少 spaces) | `/spaces/{space_id}/instances/entities` | management.py:993 |
| 4 | Query 参数滥用 | `schema_id: str = Query(...)` 多个端点 | 统一使用 path 参数 | rules.py:155,172,256 |
| 5 | 前缀不一致 | `/v1/management` vs `/v1/consumption` | 统一 `/v1` 前缀下的资源分组 | management.py:35, consumption.py:24 |

#### 2.2.4 HTTP 方法滥用

| # | 路由 | 当前方法 | 问题 | 建议 | 文件位置 |
|---|------|---------|------|------|---------|
| 1 | `/query/pattern-match/{concept}` | GET + POST | 重复端点 | 仅保留 POST | query.py:128,150 |
| 2 | `/query/traverse/{entity_id}` | GET + POST | 重复端点 | 仅保留 POST | query.py:172,205 |
| 3 | `/query/path` | GET + POST | 重复端点 | 仅保留 POST | query.py:256,286 |
| 4 | `/rule-groups/{name}/steps/reorder` | POST | 应该是 PUT | 改为 PUT | rules.py:322 |
| 5 | `/rule-groups/{name}/simulate` | POST | 模拟应该用 POST (OK) | 保持 | rules.py:351 |

#### 2.2.5 路由结构问题

| # | 问题 | 当前结构 | 建议结构 |
|---|------|---------|---------|
| 1 | 缺少 `/spaces` 顶级路径 | `/v1/management/spaces` | `/v1/spaces` |
| 2 | L4 嵌套过深 | `/{space_id}/schema/L4/rules/definitions` | `/spaces/{space_id}/schema/L4/rules` |
| 3 | consumption 前缀冗余 | `/v1/consumption/views` | `/v1/views` |
| 4 | 实体查询路径不一致 | 三种模式并存 | `/spaces/{space_id}/instances/entities` |

#### 2.2.6 提案遗漏的端点

| # | 类别 | 文件 | 端点数量 | 状态 |
|---|------|------|---------|------|
| 1 | 数据导入 | ingestion.py | 3 | 提案未提及 |
| 2 | 数据集管理 | datasets.py | 9 | 提案未提及 |
| 3 | 可视化 | visualization.py | 6 | 提案未提及 |
| 4 | 分类管理 | categories.py | 7 | 提案未提及 |
| 5 | 增量更新 | incremental.py | 5 | 提案未提及 |
| 6 | 旧 Schema | schema.py | 5 | 需决定保留/废弃 |

---

### 2.3 问题文件位置索引

#### 高严重程度问题

| 问题 | 文件:行号 | 描述 |
|------|----------|------|
| semantic_spaces.py 重复 | `routes/semantic_spaces.py` 全文件 | 与 management.py 功能重复 |
| 规则执行入口分散 | `rules.py:80`, `consumption.py:583` | 两处执行规则 |
| L4 与 Phase 2 模型并存 | `management.py:732-854`, `rules.py:136-335` | 两套规则系统 |

#### 中等严重程度问题

| 问题 | 文件:行号 | 描述 |
|------|----------|------|
| GET+POST 重复 | `query.py:128-286` | 6 个重复端点 |
| 路径参数不一致 | `rules.py:169,252` | id vs name |
| 嵌套路径缺少资源名 | `management.py:599-1313` | 15+ 端点缺少 spaces |

---

## 三、整合后的 API 设计

### 3.1 核心概念关系图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Ontology Engine 架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Ontology (本体论)                                                   │   │
│  │  - 全局 Schema 定义 (L1-L4)                                         │   │
│  │  - 由 Semantic Space 实例化                                          │   │
│  │  - 路径: /v1/ontology                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ 实例化                                  │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Semantic Space (语义空间)                                          │   │
│  │  ├── metadata: id, name, status, domain                           │   │
│  │  ├── L1: fact_objects (实体定义)                                   │   │
│  │  ├── L2: categorizations (分类)                                   │   │
│  │  ├── L3: analytical_elements (分析要素)                            │   │
│  │  ├── L4: rule_definitions + rule_logics (业务逻辑)                 │   │
│  │  ├── instances: entities, relations, category_tags, metric_values │   │
│  │  ├── versions: 版本快照                                             │   │
│  │  └── views: 消费视图 (自动创建)                                     │   │
│  │                                                                      │   │
│  │  路径: /v1/spaces/{space_id}                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    │ 同步                                    │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  View (消费视图)                                                     │   │
│  │  - Space 的只读投影                                                 │   │
│  │  - 用于前端/Agent 消费                                              │   │
│  │  - 路径: /v1/views/{view_id}                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

数据流:
1. 创建 Space → 定义 L1-L4 Schema → 填充 Instances
2. 激活 Space → 自动创建 View → 同步到消费面
3. 执行分析 → 从 View 读取数据 → 返回结果
```

### 3.2 版本回退端点设计

```
Schema 版本回退 (Ontology 级别):
├── POST /v1/ontology/rollback/{version}    ← 回退到指定版本
└── GET /v1/ontology/versions              ← 获取版本历史

Space 版本回退 (Space 级别):
├── GET /v1/spaces/{space_id}/versions              ← 版本列表
├── POST /v1/spaces/{space_id}/versions             ← 创建快照
└── POST /v1/spaces/{space_id}/versions/{v}/rollback  ← 回退
```

### 3.3 数据集成端点设计

```
数据导入:
├── POST /v1/ingestion/import    ← 批量导入 (保持)
├── POST /v1/ingestion/validate  ← 验证 (保持)
└── POST /v1/spaces/{space_id}/instances/import  ← 导入到指定 Space

数据集:
├── POST /v1/datasets           ← 创建数据集
├── GET /v1/datasets           ← 列出数据集
├── GET /v1/datasets/{id}     ← 获取数据集
└── POST /v1/datasets/compare ← 比较数据集

增量更新:
├── POST /v1/incremental/import   ← 增量导入
├── GET /v1/incremental/batches  ← 变更批次
└── POST /v1/incremental/impact  ← 影响分析
```

### 3.4 可视化端点设计

```
可视化 (整合到 Views):
├── GET /v1/views/{view_id}/schema-graph    ← Schema 图 (来自 visualization.py)
├── GET /v1/views/{view_id}/entities        ← 可视化实体
├── GET /v1/views/{view_id}/metrics/{entity_id}  ← 指标快照
├── GET /v1/views/{view_id}/rule-chain/{dimension}  ← 规则链
├── POST /v1/views/{view_id}/simulate      ← 模拟执行
└── GET /v1/views/{view_id}/execution/{entity_id}/{dimension}  ← 执行追溯
```

### 3.5 完整路由结构总览

```
/v1
│
├── /ontology                      # Ontology Schema 管理 (整合旧 schema.py)
│   ├── GET /ontology             # 获取 Ontology
│   ├── POST /ontology/load      # 加载 Ontology YAML
│   ├── GET /ontology/versions    # 版本历史
│   └── POST /ontology/rollback/{version}  # 版本回退
│
├── /spaces                        # Semantic Spaces (管理面)
│   ├── GET /spaces
│   ├── POST /spaces
│   ├── GET /spaces/{space_id}
│   ├── PUT /spaces/{space_id}
│   ├── DELETE /spaces/{space_id}
│   │
│   ├── POST /spaces/{space_id}/activate
│   ├── POST /spaces/{space_id}/deactivate
│   ├── POST /spaces/{space_id}/archive
│   │
│   ├── GET /spaces/{space_id}/schema
│   ├── POST /spaces/{space_id}/schema/load-yaml
│   │
│   ├── GET /spaces/{space_id}/schema/L1/fact-objects
│   ├── POST /spaces/{space_id}/schema/L1/fact-objects
│   │
│   ├── GET /spaces/{space_id}/schema/L2/categorizations
│   ├── POST /spaces/{space_id}/schema/L2/categorizations
│   │
│   ├── GET /spaces/{space_id}/schema/L3/analytical-elements
│   ├── POST /spaces/{space_id}/schema/L3/analytical-elements
│   │
│   ├── GET /spaces/{space_id}/schema/L4/rules
│   ├── POST /spaces/{space_id}/schema/L4/rules
│   ├── GET /spaces/{space_id}/schema/L4/rules/{rule_id}
│   ├── PUT /spaces/{space_id}/schema/L4/rules/{rule_id}
│   ├── DELETE /spaces/{space_id}/schema/L4/rules/{rule_id}
│   │
│   ├── GET /spaces/{space_id}/schema/L4/rules/{rule_id}/logics
│   ├── POST /spaces/{space_id}/schema/L4/rules/{rule_id}/logics
│   ├── PUT /spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}
│   ├── DELETE /spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}
│   │
│   ├── GET /spaces/{space_id}/schema/rules/dependency-graph
│   │
│   ├── GET /spaces/{space_id}/instances/entities
│   ├── POST /spaces/{space_id}/instances/entities
│   ├── POST /spaces/{space_id}/instances/entities/batch
│   ├── POST /spaces/{space_id}/instances/entities/import
│   │
│   ├── GET /spaces/{space_id}/instances/relations
│   ├── POST /spaces/{space_id}/instances/relations
│   │
│   ├── GET /spaces/{space_id}/versions
│   ├── POST /spaces/{space_id}/versions
│   ├── POST /spaces/{space_id}/versions/{version}/rollback
│   │
│   └── POST /spaces/{space_id}/load-from-json
│
├── /views                         # 消费视图
│   ├── GET /views
│   ├── GET /views/{view_id}
│   ├── GET /views/{view_id}/entities
│   ├── GET /views/{view_id}/schema-graph        ← 整合 visualization.py
│   ├── GET /views/{view_id}/rule-chain/{dimension}
│   ├── GET /views/{view_id}/rules/dependency-graph
│   ├── GET /views/{view_id}/rules/for-entity/{entity_id}
│   │
│   ├── POST /views/{view_id}/execute/analyze
│   ├── POST /views/{view_id}/execute/simulate
│   ├── POST /views/{view_id}/simulate           ← 整合 visualization.py
│   ├── GET /views/{view_id}/metrics/{entity_id}
│   └── GET /views/{view_id}/execution/{entity_id}/{dimension}
│
├── /actions                       # 业务动作 (统一规则执行)
│   ├── GET /actions              # 列出所有可用动作
│   ├── GET /actions/{action_name}
│   ├── POST /actions/{action_name}/execute
│   ├── GET /actions/{action_name}/explain/{entity_id}
│
├── /query                         # 知识检索
│   ├── POST /query/search         # 向量搜索
│   ├── POST /query/graph          # 图遍历
│   ├── POST /query/paths          # 路径查询 (合并 GET+POST)
│   ├── GET /query/trace/{entity_id}
│
├── /ingestion                     # 数据导入
│   ├── POST /ingestion/import     # 批量导入
│   ├── POST /ingestion/validate   # 验证
│   └── POST /ingestion/import/dict
│
├── /datasets                      # 数据集管理
│   ├── GET /datasets
│   ├── POST /datasets
│   ├── GET /datasets/{id}
│   ├── PUT /datasets/{id}
│   ├── DELETE /datasets/{id}
│   ├── POST /datasets/{id}/entities
│   ├── GET /datasets/{id}/entities
│   ├── POST /datasets/{id}/snapshots
│   ├── GET /datasets/{id}/snapshots
│   └── POST /datasets/compare
│
├── /incremental                   # 增量更新
│   ├── POST /incremental/import
│   ├── GET /incremental/batches
│   ├── GET /incremental/batches/{id}
│   ├── GET /incremental/batches/{id}/rollback-actions
│   └── POST /incremental/impact
│
├── /categories                    # 分类管理
│   ├── POST /categories/dimensions/applicability
│   ├── GET /categories/dimensions/{id}/applicability
│   ├── DELETE /categories/dimensions/{id}/applicability/{object_type}
│   ├── POST /categories/rule-mappings
│   ├── GET /categories/rule-mappings
│   ├── DELETE /categories/rule-mappings/{dim}/{val}/{rule_id}
│   ├── GET /categories/entities/{entity_id}/versions
│   └── GET /categories/entities/{entity_id}/versions/{version}
│
├── /entities                      # 实体管理 (全局, 跨 Space)
│   ├── POST /entities
│   ├── POST /entities/batch
│   ├── GET /entities/{entity_id}
│   ├── POST /entities/query
│   └── GET /entities/{entity_id}/neighbors
│
├── /relations                     # 关系管理 (全局)
│   └── POST /relations
│
├── /analysis                      # 分析执行 (保留, 或合并到 actions)
│   ├── POST /analysis/execute
│   └── POST /analysis/dry-run
│
└── /operators                     # 算子
    ├── GET /operators
    └── GET /operators/{name}/schema

```
/v1
│
├── /ontology                      # Ontology Schema 管理
│   ├── GET /ontology             # 获取完整 Ontology
│   ├── POST /ontology/load       # 加载 Schema
│   └── GET /ontology/versions    # 版本历史
│
├── /spaces                        # Semantic Spaces (管理面)
│   ├── GET /spaces               # 列出所有 Space
│   ├── POST /spaces              # 创建 Space
│   ├── GET /spaces/{space_id}    # 获取 Space
│   ├── PUT /spaces/{space_id}    # 更新 Space
│   ├── DELETE /spaces/{space_id} # 删除 Space
│   │
│   ├── POST /spaces/{space_id}/activate
│   ├── POST /spaces/{space_id}/deactivate
│   ├── POST /spaces/{space_id}/archive
│   │
│   ├── GET /spaces/{space_id}/schema
│   ├── POST /spaces/{space_id}/schema/load-yaml
│   │
│   ├── GET /spaces/{space_id}/schema/L1/fact-objects
│   ├── POST /spaces/{space_id}/schema/L1/fact-objects
│   │
│   ├── GET /spaces/{space_id}/schema/L2/categorizations
│   ├── POST /spaces/{space_id}/schema/L2/categorizations
│   │
│   ├── GET /spaces/{space_id}/schema/L3/analytical-elements
│   ├── POST /spaces/{space_id}/schema/L3/analytical-elements
│   │
│   ├── GET /spaces/{space_id}/schema/L4/rules
│   ├── POST /spaces/{space_id}/schema/L4/rules
│   ├── GET /spaces/{space_id}/schema/L4/rules/{rule_id}
│   ├── PUT /spaces/{space_id}/schema/L4/rules/{rule_id}
│   ├── DELETE /spaces/{space_id}/schema/L4/rules/{rule_id}
│   │
│   ├── GET /spaces/{space_id}/schema/L4/rules/{rule_id}/logics
│   ├── POST /spaces/{space_id}/schema/L4/rules/{rule_id}/logics
│   ├── PUT /spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}
│   ├── DELETE /spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}
│   │
│   ├── GET /spaces/{space_id}/schema/rules/dependency-graph
│   │
│   ├── GET /spaces/{space_id}/instances/entities
│   ├── POST /spaces/{space_id}/instances/entities
│   ├── POST /spaces/{space_id}/instances/entities/batch
│   ├── POST /spaces/{space_id}/instances/entities/load-yaml
│   │
│   ├── GET /spaces/{space_id}/instances/relations
│   ├── POST /spaces/{space_id}/instances/relations
│   │
│   ├── GET /spaces/{space_id}/versions
│   ├── POST /spaces/{space_id}/versions
│   ├── POST /spaces/{space_id}/versions/{version}/rollback
│   │
│   └── POST /spaces/{space_id}/load-from-json
│
├── /views                         # 消费视图
│   ├── GET /views
│   ├── GET /views/{view_id}
│   ├── GET /views/{view_id}/entities
│   ├── GET /views/{view_id}/schema-graph
│   ├── GET /views/{view_id}/rules/dependency-graph
│   ├── GET /views/{view_id}/rules/for-entity/{entity_id}
│   │
│   ├── POST /views/{view_id}/execute/analyze
│   ├── POST /views/{view_id}/execute/simulate
│
├── /actions                       # 业务动作 (统一规则执行)
│   ├── GET /actions              # 列出所有可用动作
│   ├── GET /actions/{action_name}
│   ├── POST /actions/{action_name}/execute
│   ├── GET /actions/{action_name}/explain/{entity_id}
│
├── /query                         # 知识检索
│   ├── POST /query/search         # 向量搜索
│   ├── POST /query/graph          # 图遍历
│   ├── POST /query/paths          # 路径查询
│   ├── GET /query/trace/{entity_id}
│
└── /operators                     # 算子
    ├── GET /operators
    └── GET /operators/{name}/schema
```

### 3.2 关键设计决策 (v2.0 确认)

#### 决策 1: `/v1/schema` 标记为弃用，历史版本和回退整合到 Space

**问题**: 旧 Schema (KGMLSchema) 与 Space 内的 schema 概念混淆

**方案**:
```
旧架构 (保留但标记为弃用):
└── /v1/schema/*     ← 弃用 (deprecated)

新架构 (主路径):
├── /v1/spaces/{space_id}/schema           ← Schema 总览
├── /v1/spaces/{space_id}/schema/versions   ← 版本历史
├── /v1/spaces/{space_id}/schema/rollback/{version}  ← 版本回退
└── /v1/spaces/{space_id}/schema/load-yaml   ← 加载 YAML
```

#### 决策 2: 所有资产管理必须关联 Space

**问题**: 部分端点 (`/v1/entities`, `/v1/relations`) 是全局的，与 Space 无关

**方案**:
```
资产管理 (统一关联 Space):
├── /v1/spaces/{space_id}/schema/L1/fact-objects      ← L1 要素
├── /v1/spaces/{space_id}/schema/L2/categorizations    ← L2 分类
├── /v1/spaces/{space_id}/schema/L3/analytical-elements ← L3 要素
├── /v1/spaces/{space_id}/schema/L4/rules              ← L4 规则
├── /v1/spaces/{space_id}/instances/entities          ← 实体实例
├── /v1/spaces/{space_id}/instances/relations        ← 关系实例
├── /v1/spaces/{space_id}/versions                    ← 版本快照
└── /v1/spaces/{space_id}/...                        ← 其他资产

废弃全局资产管理:
├── /v1/entities/*    → 移除，全局无 Space 关联
├── /v1/relations/*   → 移除
└── /v1/analysis/*   → 合并到 actions 或 views
```

#### 决策 3: Ingestion 增加 `?space=xxx_id` 查询参数

**问题**: 数据导入需要指定目标 Space

**方案**:
```
数据导入 (必须指定 Space):
├── POST /v1/ingestion/import?space={space_id}
├── POST /v1/ingestion/validate?space={space_id}
└── POST /v1/ingestion/import/dict?space={space_id}

等价于:
└── POST /v1/spaces/{space_id}/instances/import
```

#### 决策 4: Visualization 合并到 Views 下

**问题**: visualization.py 与 consumption.py 功能重复

**方案**:
```
Visualization 端点迁移到 Views:
├── GET /v1/visualize/schema/graph    →  GET /v1/views/{id}/schema-graph
├── GET /v1/visualize/entities       →  GET /v1/views/{id}/entities
├── GET /v1/visualize/metrics/{eid}  →  GET /v1/views/{id}/metrics/{eid}
├── GET /v1/visualize/rule-chain/{d} →  GET /v1/views/{id}/rule-chain/{d}
├── POST /v1/visualize/simulate       →  POST /v1/views/{id}/simulate
└── GET /v1/visualize/execution/... →  GET /v1/views/{id}/execution/...

废弃 visualization.py，统一使用 views 前缀
```

#### 决策 5: 统一 Space 路由前缀

**方案**: `/v1/management/spaces` → `/v1/spaces`

#### 决策 6: Actions API (规则执行抽象)

**方案**: 统一到 `/v1/actions/{dimension}/execute`

#### 决策 7: 移除重复的 GET/POST

**方案**: 复杂查询仅保留 POST，简单查询用 GET

### 3.3 完整路由映射表 (向后兼容)

| 旧路由 | 新路由 | HTTP | 兼容策略 | 说明 |
|--------|--------|------|---------|------|
| `/v1/management/spaces` | `/v1/spaces` | GET/POST | 301 重定向 | Space 管理 |
| `/v1/management/{space_id}` | `/v1/spaces/{space_id}` | GET/PUT/DELETE | 301 重定向 | 单个 Space |
| `/v1/management/{space_id}/activate` | `/v1/spaces/{space_id}/activate` | POST | 301 重定向 | 激活 |
| `/v1/management/{space_id}/deactivate` | `/v1/spaces/{space_id}/deactivate` | POST | 301 重定向 | 停用 |
| `/v1/management/{space_id}/archive` | `/v1/spaces/{space_id}/archive` | POST | 301 重定向 | 归档 |
| `/{space_id}/schema/L1/fact-objects` | `/spaces/{space_id}/schema/L1/fact-objects` | GET/POST | 301 重定向 | L1 |
| `/{space_id}/schema/L2/categorizations` | `/spaces/{space_id}/schema/L2/categorizations` | GET/POST | 301 重定向 | L2 |
| `/{space_id}/schema/L3/analytical-elements` | `/spaces/{space_id}/schema/L3/analytical-elements` | GET/POST | 301 重定向 | L3 |
| `/{space_id}/schema/L4/rules/definitions` | `/spaces/{space_id}/schema/L4/rules` | GET/POST | 301 重定向 | L4 规则 |
| `/{space_id}/schema/L4/rules/logics` | `/spaces/{space_id}/schema/L4/rules/{rule_id}/logics` | GET/POST | 301 重定向 | L4 逻辑 |
| `/{space_id}/schema/L4/rules/dependency-graph` | `/spaces/{space_id}/schema/rules/dependency-graph` | GET | 301 重定向 | 依赖图 |
| `/{space_id}/instances/entities` | `/spaces/{space_id}/instances/entities` | GET/POST | 301 重定向 | 实体 |
| `/{space_id}/instances/relations` | `/spaces/{space_id}/instances/relations` | GET/POST | 301 重定向 | 关系 |
| `/{space_id}/versions` | `/spaces/{space_id}/versions` | GET/POST | 301 重定向 | 版本 |
| `/v1/rule-groups` | `/v1/spaces/{space_id}/schema/L4/rules` | GET/POST | 兼容层 | Phase 2 规则组 |
| `/v1/rule-groups/{name}` | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}` | GET/PUT/DELETE | 兼容层 | 规则组 CRUD |
| `/v1/rule-groups/{name}/steps` | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics` | GET/POST | 兼容层 | 规则步骤 |
| `/v1/rule-groups/{name}/simulate` | `/v1/actions/{action_name}/simulate` | POST | 301 重定向 | 模拟执行 |
| `/v1/rules/execute` | `/v1/actions/{dimension}/execute` | POST | 301 重定向 | 规则执行 |
| `/v1/consumption/views` | `/v1/views` | GET | 301 重定向 | 视图列表 |
| `/v1/consumption/views/{id}` | `/v1/views/{id}` | GET | 301 重定向 | 单个视图 |
| `/v1/consumption/views/{id}/execute/analyze` | `/v1/views/{id}/execute/analyze` | POST | 301 重定向 | 执行分析 |
| `/v1/consumption/views/{id}/execute/simulate` | `/v1/views/{id}/execute/simulate` | POST | 301 重定向 | What-if |
| `/v1/query/pattern-match/{concept}` (GET) | `/v1/query/pattern-match/{concept}` (POST) | - | 移除 GET | 保留 POST |
| `/v1/query/traverse/{entity_id}` (GET) | `/v1/query/traverse/{entity_id}` (POST) | - | 移除 GET | 保留 POST |
| `/v1/query/path` (GET) | `/v1/query/paths` (POST) | - | 合并为 POST | 统一为 paths |

---

## 四、前端关联影响分析

### 4.1 受影响的 Frontend 文件清单

| # | 文件路径 | 当前 API | 影响程度 | 变更类型 |
|---|---------|---------|---------|---------|
| 1 | `src/api/client.ts` | `/v1` | 低 | 仅 BASE_URL 配置 |
| 2 | `src/api/spaceApi.ts` | `/v1/management` | **高** | 需全局替换 (25+ 处) |
| 3 | `src/api/ruleGroups.ts` | `/v1/rule-groups` | **中** | 兼容层可保持 |
| 4 | `src/api/ruleSteps.ts` | `/v1/rule-groups/{name}/steps` | **中** | 兼容层可保持 |
| 5 | `src/api/operators.ts` | `/v1/operators` | 低 | 路径不变 |
| 6 | `src/api/visualization.ts` | `/v1/visualize` | **高** | 合并到 views，文件删除 |
| 7 | `src/pages/rules/RuleGroupListPage.tsx` | `spaceApi.listSpaces()` | **中** | API 调用更新 |
| 8 | `src/pages/rules/RuleGroupCreatePage.tsx` | `spaceApi.createSpace()` | **中** | API 调用更新 |
| 9 | `src/pages/rules/RuleGroupLayout.tsx` | `spaceApi.getSpace()` | **中** | API 调用更新 |
| 10 | `src/components/rule/RuleEditorModal.tsx` | `ruleGroupsApi` | **中** | 兼容层可保持 |
| 11 | `src/components/rule/RuleGroupForm.tsx` | `ruleGroupsApi.simulate()` | **中** | 兼容层可保持 |
| **12** | `src/api/entities.ts` | `/v1/entities` | **高** | **废弃，删除或标记弃用** |
| **13** | `src/api/datasets.ts` | `/v1/datasets` | **中** | 保持独立 |
| **14** | `src/api/ingestion.ts` | `/v1/ingestion` | **中** | 增加 `?space=` 参数 |

### 4.2 前端变更详解

#### 4.2.1 visualization.ts → 删除，合并到 views

```typescript
// 删除 src/api/visualization.ts
// 功能迁移到 spaceApi.ts 或新建 viewsApi.ts

// 原 visualization API:
GET /v1/visualize/schema/graph  →  GET /v1/views/{id}/schema-graph
GET /v1/visualize/entities       →  GET /v1/views/{id}/entities
GET /v1/visualize/metrics/{eid}  →  GET /v1/views/{id}/metrics/{eid}
POST /v1/visualize/simulate       →  POST /v1/views/{id}/simulate
```

#### 4.2.2 entities.ts → 废弃

```typescript
// 标记为废弃，所有实体操作通过 spaceApi.ts

// 原 /v1/entities/* 端点:
POST /v1/entities/         →  废弃
GET /v1/entities/{id}       →  废弃
POST /v1/entities/batch    →  废弃
POST /v1/entities/query     →  废弃
GET /v1/entities/{id}/neighbors →  废弃

// 改用 spaceApi.ts:
POST /v1/spaces/{space_id}/instances/entities
GET /v1/spaces/{space_id}/instances/entities/{entity_id}
```

#### 4.2.3 ingestion.ts → 增加 space 参数

```typescript
// 增加 ?space=xxx_id 参数

// 原:
POST /v1/ingestion/import { entities, relations }

// 改为:
POST /v1/ingestion/import?space={space_id} { entities, relations }

// spaceApi.ts 中的方法:
async importInstances(spaceId: string, data: IngestionData) {
  const response = await axios.post(`/v1/ingestion/import?space=${spaceId}`, data);
}
```

#### 4.2.4 datasets.ts → 保持独立

```typescript
// datasets API 保持不变，但建议增加 space 关联

// 建议字段:
interface Dataset {
  id: string;
  name: string;
  space_id?: string;  // 可选关联
}
```

### 4.2 spaceApi.ts 详细变更

#### 当前实现
```typescript
// ontology-engine-ui/src/api/spaceApi.ts
const BASE_URL = '/v1/management';  // 第 6 行

// 方法调用示例:
async listSpaces(): Promise<SpaceResponse[]> {
  const response = await axios.get(`${BASE_URL}/spaces`);  // → /v1/management/spaces
}

async listFactObjects(spaceId: string): Promise<any[]> {
  const response = await axios.get(`${BASE_URL}/${spaceId}/schema/L1/fact-objects`);
  // → /v1/management/{spaceId}/schema/L1/fact-objects
}
```

#### 需变更的方法列表 (共 25+ 处)

| # | 方法名 | 当前路径 | 新路径 | 行号 |
|---|-------|---------|--------|------|
| 1 | `listSpaces()` | `/v1/management/spaces` | `/v1/spaces` | 142 |
| 2 | `createSpace()` | `/v1/management/spaces` | `/v1/spaces` | 147 |
| 3 | `getSpace()` | `/v1/management/spaces/${spaceId}` | `/v1/spaces/${spaceId}` | 152 |
| 4 | `updateSpace()` | `/v1/management/spaces/${spaceId}` | `/v1/spaces/${spaceId}` | 157 |
| 5 | `deleteSpace()` | `/v1/management/spaces/${spaceId}` | `/v1/spaces/${spaceId}` | 162 |
| 6 | `activateSpace()` | `/v1/management/spaces/${spaceId}/activate` | `/v1/spaces/${spaceId}/activate` | 166 |
| 7 | `deactivateSpace()` | `/v1/management/spaces/${spaceId}/deactivate` | `/v1/spaces/${spaceId}/deactivate` | 171 |
| 8 | `listFactObjects()` | `/v1/management/${spaceId}/schema/L1/fact-objects` | `/v1/spaces/${spaceId}/schema/L1/fact-objects` | 177 |
| 9 | `createFactObject()` | 同上 | 同上 | 182 |
| 10 | `listCategorizations()` | `/v1/management/${spaceId}/schema/L2/...` | `/v1/spaces/${spaceId}/schema/L2/...` | 188 |
| 11 | `createCategorization()` | 同上 | 同上 | 193 |
| 12 | `deleteCategorization()` | 同上 | 同上 | 198 |
| 13 | `listAnalyticalElements()` | `/v1/management/${spaceId}/schema/L3/...` | `/v1/spaces/${spaceId}/schema/L3/...` | 203 |
| 14 | `createAnalyticalElement()` | 同上 | 同上 | 208 |
| 15 | `deleteAnalyticalElement()` | 同上 | 同上 | 213 |
| 16 | `listRuleDefinitions()` | `/v1/management/${spaceId}/schema/L4/rules/definitions` | `/v1/spaces/${spaceId}/schema/L4/rules` | 218 |
| 17 | `createRuleDefinition()` | 同上 | 同上 | 223 |
| 18 | `getRuleDefinition()` | 同上 | `/v1/spaces/${spaceId}/schema/L4/rules/${ruleId}` | 228 |
| 19 | `updateRuleDefinition()` | 同上 | 同上 | 233 |
| 20 | `deleteRuleDefinition()` | 同上 | 同上 | 238 |
| 21 | `listRuleLogics()` | `/v1/management/${spaceId}/schema/L4/rules/logics` | `/v1/spaces/${spaceId}/schema/L4/rules/${ruleId}/logics` | 243 |
| 22 | `createRuleLogic()` | 同上 | 同上 | 248 |
| 23 | `getRuleLogic()` | 同上 | `/v1/spaces/${spaceId}/schema/L4/rules/${ruleId}/logics/${logicId}` | 253 |
| 24 | `updateRuleLogic()` | 同上 | 同上 | 258 |
| 25 | `deleteRuleLogic()` | 同上 | 同上 | 263 |
| 26 | `listVersions()` | `/v1/management/${spaceId}/versions` | `/v1/spaces/${spaceId}/versions` | 268 |
| 27 | `createVersion()` | 同上 | 同上 | 273 |
| 28 | `rollbackToVersion()` | 同上 | 同上 | 278 |
| 29 | `listEntities()` | `/v1/management/${spaceId}/instances/entities` | `/v1/spaces/${spaceId}/instances/entities` | 284 |
| 30 | `createEntity()` | 同上 | 同上 | 290 |
| 31 | `listRelations()` | `/v1/management/${spaceId}/instances/relations` | `/v1/spaces/${spaceId}/instances/relations` | 295 |
| 32 | `createRelation()` | 同上 | 同上 | 300 |
| 33 | `loadSchemaFromYaml()` | `/v1/management/${spaceId}/schema/load-from-yaml` | `/v1/spaces/${spaceId}/schema/load-yaml` | 366 |
| 34 | `loadInstancesFromYaml()` | `/v1/management/${spaceId}/instances/load-from-yaml` | `/v1/spaces/${spaceId}/instances/load-yaml` | 375 |
| 35 | `getSchemaOverview()` | `/v1/management/${spaceId}/schema/overview` | `/v1/spaces/${spaceId}/schema` | 384 |

### 4.3 visualization.ts 详细变更

```typescript
// 当前: /v1/consumption/views
// 新: /v1/views

// 受影响方法:
async getSchemaGraph(viewId, graphType, layerFilter) {
  const response = await axios.get(`/v1/consumption/views/${viewId}/visualize/schema-graph`, ...);
  // 改为: /v1/views/${viewId}/schema-graph
}
```

### 4.4 前端路由变更影响页面

| 页面 | 使用的 API | 变更影响 |
|------|----------|---------|
| `RuleGroupListPage.tsx` | `spaceApi.listSpaces()`, `spaceApi.getSpace()` | 路由路径变化 |
| `RuleGroupCreatePage.tsx` | `spaceApi.createSpace()`, `spaceApi.activateSpace()` | 路由路径变化 |
| `RuleGroupLayout.tsx` | `spaceApi.getSpace()`, `spaceApi.listRuleDefinitions()` | 路由路径变化 |
| 规则编辑器组件 | `ruleGroupsApi.*` | 兼容层可保持 |

---

## 五、全量迁移清单

### 5.1 Phase 1: 路由整合 (向后兼容)

#### Backend 变更 (共 8 项)

| # | 文件 | 变更类型 | 具体变更 | 风险评估 |
|---|------|---------|---------|---------|
| 1 | `api/routes/management.py` | 路由前缀修改 | `prefix="/v1/management"` → `prefix="/v1"` | **高** - 影响所有端点 |
| 2 | `api/routes/semantic_spaces.py` | 废弃/合并 | 合并到 management.py，设置重定向 | **高** - 删除文件 |
| 3 | `api/routes/consumption.py` | 路由前缀修改 | `prefix="/v1/consumption"` → `prefix="/v1"` | **中** - 需配合前端 |
| 4 | `api/routes/rules.py` | 清理 | 移除与 L4 重复的端点 | **中** - 需保持兼容 |
| 5 | `api/routes/query.py` | 清理 | 移除 GET 重复端点 (3个) | **低** - 简单删除 |
| 6 | `api/routes/schema.py` | 整合到 ontology | 重命名为 ontology.py 或合并到 spaces | **中** - 需决定保留/废弃 |
| 7 | `api/routes/visualization.py` | 整合到 views | `/v1/visualize` → `/v1/views/{id}` | **中** - 端点迁移 |
| 8 | `api/routes/entities.py` | 路径调整 | 可能需要关联 space_id | **中** - 需决定 |

#### Frontend 变更 (共 6 项)

| # | 文件 | 变更类型 | 具体变更 | 风险评估 |
|---|------|---------|---------|---------|
| 9 | `src/api/spaceApi.ts` | 路径前缀修改 | `BASE_URL = '/v1/management'` → `BASE_URL = '/v1'` | **高** - 25+ 处变更 |
| 10 | `src/api/visualization.ts` | 路径前缀修改 | `/v1/visualize` → `/v1/views/{id}` | **中** - 需重新组织 |
| 11 | `src/pages/rules/RuleGroupListPage.tsx` | API 调用更新 | 确保使用正确的 API 方法 | **低** - 应无变化 |
| 12 | `src/pages/rules/RuleGroupCreatePage.tsx` | API 调用更新 | 确保使用正确的 API 方法 | **低** - 应无变化 |
| 13 | `src/api/entities.ts` | 路径调整 | 可能需要关联 space_id | **中** - 需确认 |
| 14 | `src/api/datasets.ts` | 确认 | 检查数据集 API 是否正常 | **低** |

### 5.2 Phase 2: 语义统一

| # | 变更 | 具体内容 | 风险评估 |
|---|------|---------|---------|
| 15 | Actions API 实现 | 创建 `/v1/actions/{name}/execute` 统一入口 | **中** - 新增端点 |
| 16 | 兼容层实现 | `/rule-groups` → `/spaces/{id}/schema/L4/rules` 映射 | **中** - 需要适配器 |
| 17 | 消费视图路由 | `/v1/consumption/views` → `/v1/views` | **中** - 前端适配 |
| 18 | Ontology 整合 | `/v1/schema` → `/v1/ontology` | **中** - 决定是否保留 |

### 5.3 Phase 3: 清理

| # | 变更 | 具体内容 | 风险评估 |
|---|------|---------|---------|
| 19 | 删除 semantic_spaces.py | 移除废弃文件 | **低** - 已废弃 |
| 20 | 清理旧端点 | 移除 `/rules/execute` 等 | **低** - 已迁移 |
| 21 | 更新 OpenAPI 文档 | 同步 API 变更 | **低** - 文档更新 |
| 22 | 更新前端类型定义 | 确保与新 API 对齐 | **中** - 类型同步 |
| 23 | 删除 visualization.py | 整合到 consumption.py 后删除 | **低** |

### 5.4 迁移检查清单 (v2.0 确认版)

```
□ Backend 变更
  □ management.py prefix: /v1/management → /v1
  □ semantic_spaces.py: 合并到 management 或删除
  □ consumption.py prefix: /v1/consumption → /v1
  □ rules.py: 清理重复端点
  □ query.py: 移除 GET 重复 (pattern-match, traverse, path)
  □ visualization.py: 整合到 views 下，**删除原文件**
  □ schema.py: **标记为弃用**，增加 Deprecation 响应头
  □ entities.py: **标记为弃用**，所有操作迁移到 space 下
  □ relations.py: **标记为弃用**
  □ analysis.py: 合并到 actions 或 views

□ Frontend 变更
  □ spaceApi.ts BASE_URL: /v1/management → /v1
  □ spaceApi.ts 方法路径: 25+ 处更新
  □ visualization.ts: **删除**，功能迁移到 spaceApi 或 views
  □ entities.ts: **标记为弃用**
  □ ingestion.ts: 增加 ?space= 参数
  □ datasets.ts: 可选增加 space_id 关联
  □ ruleGroups.ts: 兼容层保持

□ 兼容性
  □ 301 重定向: /v1/management/* → /v1/*
  □ 301 重定向: /v1/consumption/* → /v1/*
  □ 301 重定向: /v1/visualize/* → /v1/views/{id}/*
  □ 200 + Deprecation Header: /v1/schema/* (标记弃用)
  □ 200 + Deprecation Header: /v1/entities/* (标记弃用)
  □ 301 重定向: /v1/relations/* → /v1/spaces/{id}/instances/relations

□ 关键问题决策 (已确认)
  ✅ /v1/schema: 标记弃用，历史版本和回退整合到 /spaces/{id}/schema
  ✅ Entities/Relations: 废弃全局端点，统一关联 Space
  ✅ Ingestion: 增加 ?space=xxx_id 查询参数
  ✅ Visualization: 合并到 views
```
  □ Visualization: 是否完全整合到 Views？

□ 测试
  □ Space CRUD 测试
  □ Rule CRUD 测试
  □ 执行/模拟测试
  □ 查询功能测试
  □ Ingestion 测试
  □ Datasets 测试
  □ Visualization 测试
  □ 版本回退测试 (schema + space)

□ 文档
  □ API 文档更新
  □ 前端引用更新
  □ 术语表更新 (Schema vs schema vs Ontology)
```

---

## 六、实施风险评估

### 6.1 风险矩阵

| 风险项 | 可能性 | 影响 | 风险等级 | 缓解措施 |
|--------|--------|------|---------|---------|
| 前端 spaceApi.ts 变更遗漏 | 高 | 高 | **严重** | 逐项核对方法，添加 TypeScript 类型检查 |
| 兼容层实现不完整 | 中 | 高 | **高** | 分阶段实施，每阶段完整测试 |
| 规则执行语义不一致 | 中 | 高 | **高** | 保持原有 consumption.py 执行逻辑 |
| 前端组件 API 调用遗漏 | 中 | 中 | **中** | 全面回归测试 |
| L4 与 Rule Groups 模型冲突 | 低 | 高 | **中** | 明确两套模型映射关系 |
| OpenAPI 文档不同步 | 低 | 低 | **低** | 自动生成或 CI 检查 |

### 6.2 建议实施顺序

```
Phase 1: 路由整合 (1-2 周)
├── Step 1.1: 修改 management.py prefix + 测试
├── Step 1.2: 修改 consumption.py prefix + 测试
├── Step 1.3: 更新 spaceApi.ts + 测试
├── Step 1.4: 更新 visualization.ts + 测试
└── Step 1.5: 清理 rules.py/query.py + 测试

Phase 2: 语义统一 (1 周)
├── Step 2.1: 实现 Actions API
├── Step 2.2: 实现兼容层
└── Step 2.3: 前端适配

Phase 3: 清理 (0.5 周)
├── Step 3.1: 删除 semantic_spaces.py
├── Step 3.2: 清理旧端点
└── Step 3.3: 更新文档
```

### 6.3 回滚计划

| 阶段 | 回滚方法 |
|------|---------|
| Phase 1 | 使用 git revert 恢复 management.py, consumption.py |
| Phase 2 | 禁用 Actions API，恢复旧端点 |
| Phase 3 | 从备份恢复 semantic_spaces.py |

---

## 附录 A: 当前 API 完整端点列表

### A.1 管理面端点

```
POST   /v1/management/spaces
GET    /v1/management/spaces
GET    /v1/management/spaces/{space_id}
PUT    /v1/management/spaces/{space_id}
DELETE /v1/management/spaces/{space_id}
POST   /v1/management/spaces/{space_id}/activate
POST   /v1/management/spaces/{space_id}/deactivate
POST   /v1/management/spaces/{space_id}/archive

GET    /v1/management/{space_id}/schema/L1/fact-objects
POST   /v1/management/{space_id}/schema/L1/fact-objects
GET    /v1/management/{space_id}/schema/L2/categorizations
POST   /v1/management/{space_id}/schema/L2/categorizations
GET    /v1/management/{space_id}/schema/L3/analytical-elements
POST   /v1/management/{space_id}/schema/L3/analytical-elements
GET    /v1/management/{space_id}/schema/L4/rules/definitions
POST   /v1/management/{space_id}/schema/L4/rules/definitions
GET    /v1/management/{space_id}/schema/L4/rules/definitions/{rule_id}
PUT    /v1/management/{space_id}/schema/L4/rules/definitions/{rule_id}
DELETE /v1/management/{space_id}/schema/L4/rules/definitions/{rule_id}
GET    /v1/management/{space_id}/schema/L4/rules/logics
POST   /v1/management/{space_id}/schema/L4/rules/logics
GET    /v1/management/{space_id}/schema/L4/rules/logics/{logic_id}
PUT    /v1/management/{space_id}/schema/L4/rules/logics/{logic_id}
DELETE /v1/management/{space_id}/schema/L4/rules/logics/{logic_id}
GET    /v1/management/{space_id}/schema/L4/rules/dependency-graph
GET    /v1/management/{space_id}/instances/entities
POST   /v1/management/{space_id}/instances/entities
GET    /v1/management/{space_id}/instances/relations
POST   /v1/management/{space_id}/instances/relations
GET    /v1/management/{space_id}/versions
POST   /v1/management/{space_id}/versions
POST   /v1/management/{space_id}/versions/{version}/rollback
POST   /v1/management/{space_id}/schema/load-from-yaml
POST   /v1/management/{space_id}/instances/load-from-yaml
GET    /v1/management/{space_id}/schema/overview
```

### A.2 规则组端点

```
GET    /v1/rules
POST   /v1/rules/execute
POST   /v1/rule-groups
GET    /v1/rule-groups
GET    /v1/rule-groups/{id}
PUT    /v1/rule-groups/{id}
DELETE /v1/rule-groups/{id}
POST   /v1/rule-groups/{name}/steps
GET    /v1/rule-groups/{name}/steps
PUT    /v1/rule-groups/{name}/steps/{step_id}
DELETE /v1/rule-groups/{name}/steps/{step_id}
POST   /v1/rule-groups/{name}/steps/reorder
POST   /v1/rule-groups/{name}/simulate
POST   /v1/rule-groups/import
POST   /v1/rule-groups/validate-yaml
GET    /v1/rule-groups/{name}/export
```

### A.3 消费面端点

```
GET    /v1/consumption/views
GET    /v1/consumption/views/{view_id}
GET    /v1/consumption/views/{view_id}/entities
GET    /v1/consumption/views/{view_id}/visualize/schema-graph
GET    /v1/consumption/views/{view_id}/rules/dependency-graph
GET    /v1/consumption/views/{view_id}/rules/for-entity/{entity_id}
POST   /v1/consumption/views/{view_id}/execute/analyze
POST   /v1/consumption/views/{view_id}/execute/simulate
```

### A.4 查询端点

```
POST   /v1/query/vector
POST   /v1/query/hybrid
POST   /v1/query/graph
GET    /v1/query/pattern-match/{concept}
POST   /v1/query/pattern-match/{concept}
GET    /v1/query/traverse/{entity_id}
POST   /v1/query/traverse/{entity_id}
GET    /v1/query/path/{from_entity_id}/{to_entity_id}
POST   /v1/query/path
GET    /v1/query/trace/{entity_id}
```

### A.5 其他端点

```
GET    /v1/operators
GET    /v1/operators/{name}/schema
GET    /v1/dag/full
GET    /v1/dag/path
GET    /v1/metrics/{name}/dag
```

---

## 附录 B: 新 API 完整端点列表

### B.1 目标架构端点

```
# Ontology
GET    /v1/ontology
POST   /v1/ontology/load
GET    /v1/ontology/versions

# Spaces
GET    /v1/spaces
POST   /v1/spaces
GET    /v1/spaces/{space_id}
PUT    /v1/spaces/{space_id}
DELETE /v1/spaces/{space_id}
POST   /v1/spaces/{space_id}/activate
POST   /v1/spaces/{space_id}/deactivate
POST   /v1/spaces/{space_id}/archive
GET    /v1/spaces/{space_id}/schema
POST   /v1/spaces/{space_id}/schema/load-yaml

# L1
GET    /v1/spaces/{space_id}/schema/L1/fact-objects
POST   /v1/spaces/{space_id}/schema/L1/fact-objects

# L2
GET    /v1/spaces/{space_id}/schema/L2/categorizations
POST   /v1/spaces/{space_id}/schema/L2/categorizations

# L3
GET    /v1/spaces/{space_id}/schema/L3/analytical-elements
POST   /v1/spaces/{space_id}/schema/L3/analytical-elements

# L4 Rules
GET    /v1/spaces/{space_id}/schema/L4/rules
POST   /v1/spaces/{space_id}/schema/L4/rules
GET    /v1/spaces/{space_id}/schema/L4/rules/{rule_id}
PUT    /v1/spaces/{space_id}/schema/L4/rules/{rule_id}
DELETE /v1/spaces/{space_id}/schema/L4/rules/{rule_id}

# L4 Rule Logics
GET    /v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics
POST   /v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics
PUT    /v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}
DELETE /v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}

# Dependency Graph
GET    /v1/spaces/{space_id}/schema/rules/dependency-graph

# Instances
GET    /v1/spaces/{space_id}/instances/entities
POST   /v1/spaces/{space_id}/instances/entities
POST   /v1/spaces/{space_id}/instances/entities/batch
POST   /v1/spaces/{space_id}/instances/entities/load-yaml
GET    /v1/spaces/{space_id}/instances/relations
POST   /v1/spaces/{space_id}/instances/relations

# Versions
GET    /v1/spaces/{space_id}/versions
POST   /v1/spaces/{space_id}/versions
POST   /v1/spaces/{space_id}/versions/{version}/rollback

# Views
GET    /v1/views
GET    /v1/views/{view_id}
GET    /v1/views/{view_id}/entities
GET    /v1/views/{view_id}/schema-graph
GET    /v1/views/{view_id}/rules/dependency-graph
GET    /v1/views/{view_id}/rules/for-entity/{entity_id}
POST   /v1/views/{view_id}/execute/analyze
POST   /v1/views/{view_id}/execute/simulate

# Actions
GET    /v1/actions
GET    /v1/actions/{action_name}
POST   /v1/actions/{action_name}/execute
GET    /v1/actions/{action_name}/explain/{entity_id}

# Query
POST   /v1/query/search
POST   /v1/query/graph
POST   /v1/query/paths
GET    /v1/query/trace/{entity_id}

# Operators
GET    /v1/operators
GET    /v1/operators/{name}/schema
```

---

## 附录 C: 问题-文件索引

### C.1 Backend 文件

| 文件路径 | 问题数量 | 主要问题 |
|---------|---------|---------|
| `api/routes/management.py` | 15+ | prefix 不一致，嵌套路径缺少资源名 |
| `api/routes/semantic_spaces.py` | 10+ | 与 management.py 重复 |
| `api/routes/rules.py` | 8+ | 与 L4 重复，HTTP 方法滥用 |
| `api/routes/consumption.py` | 5+ | prefix 冗余 (consumption) |
| `api/routes/query.py` | 6+ | GET+POST 重复端点 |

### C.2 Frontend 文件

| 文件路径 | 问题数量 | 主要问题 |
|---------|---------|---------|
| `src/api/spaceApi.ts` | 25+ | BASE_URL 和方法路径需要更新 |
| `src/api/visualization.ts` | 1 | 前缀需要从 consumption 改为 views |
| `src/pages/rules/*.tsx` | 3 | 间接影响，需验证 API 调用 |

---

## 附录 D: 术语表

| 术语 | 说明 |
|------|------|
| Semantic Space | 语义空间，OntologyEngine 的核心容器 |
| Fact Object (L1) | 实体定义，概念类型的结构定义 |
| Categorization (L2) | 分类体系，如行业、风险等级 |
| Analytical Element (L3) | 分析要素，如指标、评分 |
| Rule Definition (L4) | 规则定义，声明式规则元数据 |
| Rule Logic (L4) | 规则逻辑，规则的执行逻辑 |
| Rule Group | Phase 2 简化规则模型，对应 L4 Definition |
| Rule Step | Phase 2 规则步骤，对应 L4 Logic |
| View | 消费视图，Space 的只读投影 |
| Action | 动作，规则执行抽象 |
