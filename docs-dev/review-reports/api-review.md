# API 设计评审报告

> **评审日期**: 2026-04-19
> **评审范围**: OntologyEngine API 全量路由
> **评审方法**: Overview 对齐 → Baseline 审查 → 参考项目对齐 → 偏差标记 → 重写
> **评审人**: the-butterfly

---

## 1. 评审概述

### 1.1 评审目标

对 OntologyEngine 当前 API 进行全面评审，识别路由重复、概念混淆、命名不一致、HTTP 方法滥用等问题，并输出新 API 设计文档。

### 1.2 评审范围

| 维度 | 覆盖范围 |
|------|---------|
| 路由文件 | 15 个路由文件（schema.py, entities.py, relations.py, analysis.py, ingestion.py, datasets.py, visualization.py, categories.py, incremental.py, management.py, consumption.py, rules.py, query.py, semantic_spaces.py, __init__.py） |
| 端点总数 | 约 130+ 个 |
| 服务层 | SchemaService, EntityService, AnalysisService, QueryService, IngestionService, VisualizationService, DatasetService, IncrementalUpdateService, RuleService, DAGService, SimulationService |
| 前端影响 | spaceApi.ts (25+ 处), visualization.ts, entities.ts, ruleGroups.ts |

---

## 2. Baseline 审查

### 2.1 路由重复问题（严重程度：高）

| # | 问题 | 路由 A | 路由 B | 影响 |
|---|------|--------|--------|------|
| R1 | Space 管理重复 | `/v1/management/spaces` (management.py) | `/v1/spaces` (semantic_spaces.py) | 两套 CRUD 并存，数据可能不一致 |
| R2 | 规则定义重复 | `/v1/rule-groups` (rules.py) | `/{space_id}/schema/L4/rules/definitions` (management.py) | 两套规则模型并存 |
| R3 | 规则逻辑重复 | `/v1/rule-groups/{name}/steps` (rules.py) | `/{space_id}/schema/L4/rules/logics` (management.py) | RuleStep vs RuleLogic 概念混淆 |
| R4 | 执行端点重复 | `/v1/rules/execute` (rules.py) | `/v1/consumption/views/{id}/execute/analyze` (consumption.py) | 三处执行入口 |
| R5 | 依赖图重复 | `/{space_id}/schema/L4/rules/dependency-graph` | `/v1/consumption/views/{id}/rules/dependency-graph` | 管理面 vs 消费面语义不同但路径相似 |
| R6 | 可视化重复 | `/v1/visualize/*` (visualization.py) | `/v1/consumption/views/{id}/visualize/*` (consumption.py) | 6 个端点功能重复 |

**结论：** 6 处高严重度路由重复，必须合并。

### 2.2 概念混淆问题（严重程度：高）

| # | 问题 | 表现 | 影响 |
|---|------|------|------|
| C1 | Schema vs schema | `/v1/schema`（全局 KGMLSchema）与 `/{space_id}/schema`（Space 内 L1-L4） | 开发者和前端混淆 |
| C2 | RuleGroup vs RuleDefinition | Phase 2 RuleGroup = L4 RuleDefinition，但代码中并存 | 两套模型映射不清 |
| C3 | RuleStep vs RuleLogic | Phase 2 RuleStep = L4 RuleLogic，但代码中并存 | 步骤与逻辑概念混用 |
| C4 | Space vs Management | `/v1/management/spaces` vs `/v1/spaces` | 前缀无语义价值 |

**结论：** 4 处概念混淆，需要术语统一和路径重命名。

### 2.3 命名不一致问题（严重程度：中）

| # | 问题 | 表现 | 建议 |
|---|------|------|------|
| N1 | 路径参数混用 | `/rule-groups/{id}` vs `/rule-groups/{name}/steps` | 统一使用 `{id}` |
| N2 | 复数/单数混乱 | `/rules` vs `/rule-groups/{name}` | 集合用复数，单个资源用 `{id}` |
| N3 | 嵌套路径缺少资源名 | `/{space_id}/instances/entities` | `/spaces/{space_id}/instances/entities` |
| N4 | Query 参数滥用 | `schema_id: str = Query(...)` 多个端点 | 统一使用 path 参数 |
| N5 | 前缀不一致 | `/v1/management` vs `/v1/consumption` | 统一 `/v1` 下的资源分组 |

**结论：** 5 处命名不一致，需要统一规范。

### 2.4 HTTP 方法滥用问题（严重程度：中）

| # | 路由 | 问题 | 建议 |
|---|------|------|------|
| H1 | `/query/pattern-match/{concept}` GET+POST | 重复端点 | 仅保留 POST |
| H2 | `/query/traverse/{entity_id}` GET+POST | 重复端点 | 仅保留 POST |
| H3 | `/query/path` GET+POST | 重复端点 | 仅保留 POST |
| H4 | `/rule-groups/{name}/steps/reorder` POST | 应该是 PUT | 改为 PUT |

**结论：** 4 处 HTTP 方法滥用，需要修正。

### 2.5 路由结构问题（严重程度：高）

| # | 问题 | 当前 | 建议 |
|---|------|------|------|
| S1 | 缺少 `/spaces` 顶级路径 | `/v1/management/spaces` | `/v1/spaces` |
| S2 | L4 嵌套过深 | `/{space_id}/schema/L4/rules/definitions` | `/spaces/{space_id}/schema/L4/rules` |
| S3 | consumption 前缀冗余 | `/v1/consumption/views` | `/v1/views` |
| S4 | 实体查询路径不一致 | 三种模式并存 | `/spaces/{space_id}/instances/entities` |
| S5 | 执行入口分散 | 三处执行端点 | `/v1/actions` 统一 |

**结论：** 5 处结构问题，需要重构路由体系。

---

## 3. 参考项目对齐

### 3.1 Palantir Foundry 对齐

| OntologyEngine 概念 | Palantir 类比 | 当前对齐状态 | 偏差 |
|---------------------|--------------|-------------|------|
| Semantic Space | Ontology | 部分对齐 | Palantir Ontology 是全局的，我们的 Space 是实例化的 |
| L1 Fact Objects | Object Types | 对齐 | 无 |
| L2 Categorizations | Link Types | 部分对齐 | Palantir Link Types 更偏关系，我们更偏分类 |
| L3 Analytical Elements | Actions | 部分对齐 | Palantir Actions 包含执行，我们分离到 Actions API |
| L4 Rule Definitions | Functions (Declarations) | 对齐 | 无 |
| L4 Rule Logics | Functions (Implementations) | 对齐 | 无 |
| Views | Object Sets | 对齐 | 无 |

### 3.2 服务层对齐审查

| API 路由 | 对齐服务 | 对齐状态 | 偏差说明 |
|---------|---------|---------|---------|
| `/v1/ontology` | SchemaService | 需新增 | 当前 SchemaService 方法需扩展版本管理 |
| `/v1/spaces` | SemanticSpaceStorage | 部分对齐 | SemanticSpaceStorage 是内存存储，非 Service 层 |
| `/v1/spaces/{id}/schema/L4/rules` | RuleService | 需适配 | RuleService 当前基于 DuckDB，需适配 Space 模型 |
| `/v1/spaces/{id}/instances/entities` | EntityService | 部分对齐 | EntityService 当前无 space_id 参数 |
| `/v1/views` | SemanticSpaceStorage | 需新增 | View 管理当前在 consumption.py 内联实现 |
| `/v1/views/{id}/schema-graph` | VisualizationService | 对齐 | 无 |
| `/v1/views/{id}/execute/analyze` | AnalysisService | 对齐 | 无 |
| `/v1/actions` | AnalysisService + SimulationService | 需新增 | Actions API 为新端点 |
| `/v1/query/search` | QueryService.semantic_search | 需适配 | 当前为 `/query/vector` |
| `/v1/query/graph` | QueryService.graph_traverse | 需扩展 | 需合并 pattern/traverse/path 三种模式 |
| `/v1/query/hybrid` | QueryService.hybrid_search | 对齐 | 无 |
| `/v1/query/explain` | QueryService | 需新增 | 查询解释为新端点 |

**关键偏差：**

1. **SemanticSpaceStorage 不是 Service 层**：当前 Space CRUD 直接操作 SemanticSpaceStorage（内存单例），绕过了 Service 层。新架构需要 SpaceService 封装。
2. **EntityService 缺少 space_id 参数**：当前 EntityService 基于全局 DuckDB，不关联 Space。新架构需要增加 space_id 上下文。
3. **RuleService 与 Space 模型不兼容**：当前 RuleService 基于 DuckDB 存储，与 SemanticSpaceStorage 是两套存储体系。

---

## 4. 偏差标记

### 4.1 架构级偏差

| # | 偏差 | 严重程度 | 说明 | 建议 |
|---|------|---------|------|------|
| A1 | 双存储体系并存 | 高 | DuckDBStorage（旧路由）+ SemanticSpaceStorage（新路由） | 统一到 SemanticSpaceStorage |
| A2 | Space CRUD 绕过 Service 层 | 高 | management.py 直接操作 SemanticSpaceStorage | 创建 SpaceService |
| A3 | EntityService 无 Space 上下文 | 中 | 全局实体操作 | 增加 space_id 参数 |
| A4 | RuleService 与 Space 模型不兼容 | 中 | 两套规则存储 | 统一到 Space 内 L4 |

### 4.2 设计级偏差

| # | 偏差 | 严重程度 | 说明 | 建议 |
|---|------|---------|------|------|
| D1 | `/v1/schema` 与 Space Schema 概念混淆 | 高 | 全局 vs Space 内 | 重命名为 `/v1/ontology` |
| D2 | `/v1/management` 前缀无语义价值 | 中 | 前缀冗余 | 精简为 `/v1/spaces` |
| D3 | `/v1/consumption` 前缀冗余 | 中 | 前缀冗余 | 精简为 `/v1/views` |
| D4 | 执行入口分散 | 高 | 三处执行端点 | 统一到 `/v1/actions` |
| D5 | 可视化端点重复 | 中 | visualization.py 与 consumption.py 重复 | 合并到 Views |

### 4.3 实现级偏差

| # | 偏差 | 严重程度 | 说明 | 建议 |
|---|------|---------|------|------|
| I1 | GET+POST 重复端点 | 中 | query.py 6 个重复 | 仅保留 POST |
| I2 | 路径参数混用 id/name | 低 | rules.py | 统一使用 id |
| I3 | semantic_spaces.py 与 management.py 重复 | 高 | 两套 Space CRUD | 合并 |
| I4 | 前端 spaceApi.ts 25+ 处需更新 | 高 | BASE_URL 变更 | 分阶段迁移 |

---

## 5. 重写方案

### 5.1 新路由体系

| 路由分组 | 端点数 | 对齐服务 | 替代旧路由 |
|---------|--------|---------|-----------|
| `/v1/ontology` | 4 | SchemaService | `/v1/schema/*` |
| `/v1/spaces` | 33 | SpaceService (新增) + EntityService | `/v1/management/*` + `/v1/entities/*` + `/v1/relations/*` + `/v1/rule-groups/*` |
| `/v1/views` | 11 | VisualizationService + AnalysisService | `/v1/consumption/*` + `/v1/visualize/*` |
| `/v1/actions` | 5 | AnalysisService + SimulationService | `/v1/rules/execute` + `/v1/analysis/*` |
| `/v1/query` | 5 | QueryService | `/v1/query/*` (精简) |
| `/v1/operators` | 2 | OperatorRegistry | 不变 |
| **总计** | **60** | | **从 130+ 精简到 60** |

### 5.2 端点精简率

| 维度 | 旧 | 新 | 精简率 |
|------|-----|-----|--------|
| 路由文件 | 14 | 7 | 50% |
| 端点总数 | 130+ | 60 | 54% |
| 重复端点 | 20+ | 0 | 100% |

### 5.3 新增文档

| 文档 | 路径 | 状态 |
|------|------|------|
| API 设计总览 | `docs/02-design/api/README.md` | 已完成 |
| Spaces 路由设计 | `docs/02-design/api/spaces-routes.md` | 已完成 |
| Views 路由设计 | `docs/02-design/api/views-routes.md` | 已完成 |
| Actions 路由设计 | `docs/02-design/api/actions-routes.md` | 已完成 |
| Query 路由设计 | `docs/02-design/api/query-routes.md` | 已完成 |
| Ontology 路由设计 | `docs/02-design/api/ontology-routes.md` | 已完成 |
| 兼容层设计 | `docs/02-design/api/compatibility-layer.md` | 已完成 |

---

## 6. 风险评估

| 风险项 | 可能性 | 影响 | 风险等级 | 缓解措施 |
|--------|--------|------|---------|---------|
| 前端 spaceApi.ts 变更遗漏 | 高 | 高 | 严重 | 逐项核对方法，TypeScript 类型检查 |
| 兼容层实现不完整 | 中 | 高 | 高 | 分阶段实施，每阶段完整测试 |
| 双存储体系迁移 | 中 | 高 | 高 | 统一存储后再迁移路由 |
| RuleService 与 Space 模型冲突 | 中 | 中 | 中 | 明确两套模型映射关系 |
| L4 与 Rule Groups 语义不一致 | 低 | 高 | 中 | 在兼容层做参数转换 |
| 前端组件 API 调用遗漏 | 中 | 中 | 中 | 全面回归测试 |

---

## 7. 实施建议

### 7.1 前置条件

1. **创建 SpaceService**：封装 SemanticSpaceStorage，提供 Service 层接口
2. **EntityService 增加 space_id**：所有实体操作关联 Space
3. **统一存储体系**：DuckDBStorage → SemanticSpaceStorage 迁移

### 7.2 实施顺序

```
Phase 0: 前置准备 (1 周)
├── 创建 SpaceService
├── EntityService 增加 space_id 参数
└── RuleService 适配 Space 模型

Phase 1: 路由整合 (2 周)
├── 创建新路由文件 (spaces.py, views.py, actions.py, ontology.py)
├── 旧路由添加 301 重定向
├── 旧路由添加 Deprecation Header
└── 前端 spaceApi.ts 更新

Phase 2: 语义统一 (1 周)
├── 实现 Actions API
├── 实现兼容层映射
├── Query 路由精简
└── 前端适配

Phase 3: 清理 (1 周)
├── 删除 semantic_spaces.py, visualization.py, analysis.py
├── schema.py → ontology.py
├── entities.py / relations.py 标记弃用
└── 更新 OpenAPI 文档
```

### 7.3 验收标准

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | 无路由重复 | `grep -r "相同路径" ontology_engine/api/routes/` |
| 2 | 无 GET+POST 重复 | 检查 query.py |
| 3 | 所有资产关联 Space | `grep -r "space_id" ontology_engine/api/routes/` |
| 4 | 旧路由返回 301 | curl 测试 |
| 5 | 旧路由返回 Deprecation Header | curl -I 测试 |
| 6 | 前端功能正常 | E2E 测试 |
| 7 | mypy + ruff 通过 | CI 检查 |
| 8 | 单元测试通过 | pytest |

---

## 8. 结论

当前 API 存在 **6 处高严重度路由重复**、**4 处概念混淆**、**5 处命名不一致** 和 **4 处 HTTP 方法滥用**。通过本次重写，端点数从 130+ 精简到 60，路由文件从 14 个精简到 7 个，重复端点清零。

关键架构决策：
1. **Ontology vs Space Schema 分离**：消除 Schema/schema 概念混淆
2. **Space-first 路由体系**：所有资产关联 Space
3. **Actions 统一执行入口**：消除三处执行端点分散
4. **Views 整合可视化**：消除 visualization.py 重复
5. **兼容层渐进迁移**：301 重定向 + Deprecation Header + 3 阶段时间线
