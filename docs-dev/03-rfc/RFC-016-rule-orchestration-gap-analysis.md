# RFC-016: 规则编排系统 Gap 分析与实施路线

> **状态**: updated
> **父 RFC**: RFC-014 · RFC-015
> **创建日期**: 2026-04-16
> **最后更新**: 2026-04-16
> **作者**: the-butterfly

---

## 摘要

本文档从用户旅程完整性视角，分析当前规则编排系统的关键实施缺口：

1. **双系统并存问题**：`/rules/logics`（旧系统）与 `/rules`（Phase 2 新系统）的定位重叠但数据模型不同
2. **画布编排缺口**：Phase 2-B 规划的拖拽可视化编排尚未实现
3. **桥接缺口**：旧规则声明（RuleDeclaration）无法关联到新规则组（RuleGroup）
4. **要素 DAG 深度联动**：当前 DAG 只读，缺少点击节点→编辑规则的双向联动
5. **YAML 格式不匹配**：Phase 2 `import_from_yaml` 的格式与 `RuleGroupDefinition` 模型不兼容，也与示例 `schema.yaml` 格式脱节

---

## 实施状态总览（2026-04-16）

| 任务 | 描述 | 状态 | 说明 |
|------|------|------|------|
| T1 | 统一入口导航 | ✅ **已完成** | 旧 `RuleLogicsPage`/`RuleDeclarationsPage` 已删除；`SpaceDetailPage` 导航统一为 `/rules?schemaId=X` |
| T2 | 画布拖拽编排（G6/X6） | 🔲 待实施 | `RuleChainDAG` 尚未支持节点拖拽排序 |
| T3 | DAG 双向联动（BFS 高亮） | 🔲 待实施 | `highlightNodeId` state 已预备，但高亮逻辑未完成 |
| T4 | 数据迁移准备（外键字段） | ✅ **已完成** | `rule_groups.source_declaration_id` VARCHAR 列已通过迁移脚本添加 |
| T5 | 旧系统废弃 | ✅ **已完成** | `RuleLogicsPage.tsx` / `RuleDeclarationsPage.tsx` 已删除；`App.tsx` 旧路由已清理 |
| T6 | Phase 2 YAML 格式适配 | 🔲 新发现 | `import_from_yaml` / `export_rule_group_to_yaml` 格式与 Phase 2 模型不兼容（见第三节 Gap 5） |

---

## 一、现状全景

### 1.1 当前存在的两套规则系统

| 维度 | 旧系统 (`/rules/logics`) | 新系统 Phase 2 (`/rules`) |
|------|--------------------------|--------------------------|
| **路由** | `/spaces/:spaceId/rules/logics` | `/rules`, `/rules/:groupId` |
| **数据模型** | `RuleDeclaration` + `RuleLogic` | `RuleGroup` + `RuleStep` |
| **四元素覆盖** | 部分（when/then_action，缺少 schema_id 隔离） | 完整（四元素 + schema_id 语义空间隔离） |
| **存储后端** | `rule_declarations` / `rule_logics` 表 | `rule_groups` / `rule_steps` DuckDB 表 |
| **编辑形态** | 表格 + Modal 表单（when/then/else） | 列表 + 算子专业化编辑器 + DAG 可视化 |
| **API 前缀** | `/v1/spaces/:id/rules/declarations` | `/v1/rule-groups` |
| **算子支持** | 6 种 action_type（approve/reject/compute/...） | 5+ 算子体系（BINNING/SCORECARD/WEIGHTED_SUM/...） |
| **DAG 可视化** | `rule_logic_view`（_definition → _logic 边，仅展示） | `element_dependency`（输入→步骤→输出完整链路） |
| **模拟执行** | 无 | `/rule-groups/:name/simulate` |

### 1.2 用户旅程的断点

```
用户进入语义空间
  ↓
左侧导航 → 规则管理（目前指向哪里？）
  ↓
[断点 A] 入口不明确：应该用旧系统还是新系统？
  ↓
即便进入新系统 /rules
  ↓
[断点 B] RuleGroupDetailPage 只有列表式编辑，缺少画布拖拽编排
  ↓
[断点 C] 旧规则声明（RuleDeclaration）无法迁移/关联到新 RuleGroup
```

---

## 二、关键 Gap 分析

### Gap 1: 入口与导航混淆

**问题**：`/rules` 和 `/spaces/:spaceId/rules/logics` 并存，用户不清楚何时用哪个。

**影响**：
- 维护两套规则数据造成冗余
- 业务分析师不知道哪个是"正确"入口
- 未来迁移路线不清晰

**决策**：✅ **选项 A：废弃旧系统**（用户确认 D1）

**实施结果**（✅ 已完成 T1 + T5）：
- `RuleLogicsPage.tsx` / `RuleDeclarationsPage.tsx` 已从 `ontology-engine-ui/src/pages/spaces/` 删除
- `App.tsx` 旧路由已清理（`RuleDeclarationsPage`/`RuleLogicsPage` import 已移除）
- `SpaceDetailPage` 导航统一为单一条目 `rules → /rules?schemaId=X`
- 旧 `rule_declarations` / `rule_logics` 表仍存在于 DuckDB（待后续迁移脚本清理）

---

### Gap 2: 画布可视化编排（Phase 2-B 待办）

**现状**：RFC-014 Phase 2-B 路线图明确包含"规则画布可视化（拖拽编排）"，但尚未实现。

**已实现部分**（Phase 2-A）：
- `RuleChainDAG` 组件：`element_dependency` 维度的只读 DAG 展示
- 节点位置静态计算（`x: 100/300/500`, `y: 80 * idx`）
- 点击节点可跳转编辑（`handleDAGNodeClick` → `setInitialEditStep`）
- `RuleStepList` 列表层级拖拽排序（`@dnd-kit`）✅

**缺失部分**：
- 画布层级节点拖拽排序（应同步更新 `step_order` 并调用 `POST /rule-groups/:name/steps/reorder`）
- 新节点创建（从左侧算子面板拖入画布）
- 连线编辑（INPUT → STEP → OUTPUT 的边连接方式）
- 画布缩放/平移

**实施关键细节**：
- `@dnd-kit` 已引入项目（RuleStepList 中有使用），但 DAG 画布区域未使用
- **决策**：✅ **G6/X6**（用户确认 D2）
  - G6 (`@antv/g6`) 4.x 支持拖拽节点、边编辑、画布缩放/平移
  - X6（@antv/x6）是 G6 的 React 封装，更适合 React 项目
  - 扩展 `RuleChainDAG` 为可编辑模式，无需引入新库
- DAG 节点拖拽后需要：
  1. 更新本地位置 state
  2. 调用 `POST /rule-groups/{name}/steps/reorder` 持久化 `step_order`
  3. 乐观更新 UI

---

### Gap 3: 旧规则声明到新规则组的桥接

**现状**：`RuleLogicsPage` 创建的 `RuleLogic` 存储在 `rule_logics` 表，`RuleGroup` 存储在 `rule_groups` 表，两者无关联字段。

**桥接方案**：

| 方案 | 说明 | 复杂度 |
|------|------|--------|
| 软链接 | `RuleGroup.name` 或 `RuleGroup.description` 包含旧 `RuleDeclaration` ID | 低 |
| 外键引用 | `rule_groups.source_declaration_id` 指向 `rule_declarations.id` | 中 |
| 数据迁移 | 将 `rule_logics` 数据迁移到 `rule_steps`，废弃旧表 | 高（一次性） |

**决策**：✅ **外键引用**（用户确认 D3）

**实施结果**（✅ 已完成 T4）：
- `rule_groups` 表已增加 `source_declaration_id` VARCHAR 列（可空）
- 迁移脚本：`ontology_engine/migrations/add_source_declaration_id.py`
- 迁移完成后删除旧 `rule_declarations`/`rule_logics` 表（待后续数据迁移阶段执行）

---

### Gap 4: DAG 双向联动深度不足

**现状**：
- `RuleChainDAG` 展示只读 DAG
- `handleDAGNodeClick` 可以跳转到编辑 Modal
- `RuleGroupDetailPage` 已预备 `highlightNodeId` state 和 `onReorder` 回调，但高亮逻辑未完成

**缺失部分**：
- BFS 上游（绿色）/ 下游（橙色）路径高亮未实现
- 从选中节点反向遍历 `edges` 推导上游路径（前端实时计算，无需 API）
- 影响分析：遍历从该节点出发的所有 OUTPUT 边，展示下游影响
- DAG 右侧"路径详情面板"（显示从选中节点到根节点的完整路径）

**实施关键细节**：
- **决策**：✅ **前端推导**（用户确认 D5）
  - 路径高亮基于前端已加载数据（`dagData.nodes`/`dagData.edges`）实时计算
  - BFS/DFS 从选中节点反向遍历 `edges` 推导上游路径
  - 影响分析：遍历从该节点出发的所有 OUTPUT 边，展示下游影响
- 无需额外 API 调用，响应更快

### Gap 5: Phase 2 YAML 格式与模型不兼容（新发现）

**问题**：`RuleService.import_from_yaml()` 和 `export_rule_group_to_yaml()` 使用的格式与 `RuleGroupDefinition` + `RuleStep` 模型不匹配，也与示例 `schema.yaml` 格式完全脱节。

**详细分析**：

| 格式 | 结构 | 来源 |
|------|------|------|
| 当前导入/导出 | 顶级 `rule_definitions[]` + `rule_logics[]`（扁平） | `rule_service.py:386-415` |
| Phase 2 模型 | `RuleGroupDefinition`（四元素①②③）+ `RuleStep`（四元素④） | `engine/rule/models.py` |
| 旧 L4 示例 | `semantic_space.business_logic.rule_definitions[]` + `rule_logics[]`（嵌套） | `examples/supply_chain_finance/schema.yaml` |

**字段对照**：

| 旧 L4 (`schema.yaml`) | Phase 2 (`RuleGroupDefinition`) | 当前导入格式 |
|---|---|---|
| `id: RD001` | `name` | `name` |
| `rule_type: constraint` | `type: constraint` | `type` |
| `applies_to: [Supplier]` | `applies_to.fact_objects: []` | `applies_to: {}` |
| `applicable_categorizations` | `applies_to.categories: {}` | ❌ 缺失 |
| `action_type: set_flag` | `operator: SET_FLAG` | ❌ 字段不同 |
| `output: {is_eligible: true}` | `params: {}` + `output_mapping: {}` | ❌ 结构不同 |
| `when.expression` | `when.type` + `when.expression` | ✅ 已支持 |
| `allOf/anyOf` | `type: all_of/any_of` + `sub_conditions[]` | ⚠️ 值格式变化 |

**关联影响范围**：
- `ontology_engine/services/rule_service.py` — `import_from_yaml()` / `export_rule_group_to_yaml()` 核心逻辑
- `ontology_engine/api/routes/rules.py` — import/export API 端点（接口不变）
- 前端 UI 和 API 调用层**无需修改**

**解决方案**（详见 RFC-017）：
- 重新设计 Phase 2 YAML 格式（`rule_group` + `rule_steps`）
- `import_from_yaml` 支持 Phase 2 格式（优先）和旧 L4 格式（兼容）
- `export_rule_group_to_yaml` 输出 Phase 2 格式（与导入对称）

---

## 三、实施路线

```
当前（Phase 2 完成度约 85%）
  ✅ T1: 统一入口导航          — 已完成
  ✅ T4: 数据迁移准备（外键字段）— 已完成
  ✅ T5: 旧系统废弃            — 已完成
  🔲 T2: 完善画布编排（Phase 2-B）— G6/X6 节点拖拽排序
  🔲 T3: 双向联动增强（BFS 高亮）— 上游/下游路径高亮
  🔲 T6: Phase 2 YAML 格式适配  — 见 RFC-017
```

**说明**：Gap 1（入口导航）和 Gap 3（外键桥接）已通过 T1+T4+T5 解决。剩余 Gap 2（G6 画布）、Gap 4（DAG 联动）、Gap 5（YAML 格式）构成 Phase 2-B/C 的核心工作。

---

## 四、关键决策点（已确认）

| # | 决策 | 选项 | 已选 |
|---|------|------|------|
| D1 | 旧 `/rules/logics` 的最终处理策略？ | A: 废弃  B: 保留为只读兼容视图  C: 无限期双轨 | ✅ A |
| D2 | 画布编排技术选型？ | A: G6 可编辑  B: React Flow  C: 自研 Canvas | ✅ A (G6/X6) |
| D3 | 旧系统到新系统的桥接方式？ | A: 软链接  B: 外键字段  C: 不建立引用 | ✅ B (外键字段) |
| D4 | Phase 2-B 画布编排是否独立里程碑？ | A: 独立  B: 与 T3 合并 | ✅ B (合并) |
| D5 | DAG 路径高亮的计算位置？ | A: 后端 API  B: 前端推导 | ✅ B (前端推导) |

---

## 五、已验证可用的 API（实施依据）

### Phase 2 规则组 API（`/v1/rule-groups`）

| API | 用途 |
|-----|------|
| `POST /rule-groups` | 创建规则组 |
| `GET /rule-groups?schema_id=X` | 列表 |
| `GET /rule-groups/{id}` | 详情 |
| `PUT /rule-groups/{id}` | 更新 |
| `DELETE /rule-groups/{id}` | 删除 |
| `POST /rule-groups/{name}/steps` | 创建步骤 |
| `GET /rule-groups/{name}/steps` | 步骤列表 |
| `PUT /rule-groups/{name}/steps/{step_id}` | 更新步骤 |
| `DELETE /rule-groups/{name}/steps/{step_id}` | 删除步骤 |
| `POST /rule-groups/{name}/steps/reorder` | 重新排序（**已修复路径**） |
| `POST /rule-groups/{name}/simulate` | 模拟执行 |
| `GET /rule-groups/{name}/export` | 导出 YAML |
| `POST /rule-groups/import` | 导入 YAML |

### DAG API

| API | 用途 |
|-----|------|
| `GET /dag/full?target=X&depth=N` | 全量 DAG |
| `GET /dag/path?from=X&to=Y` | 路径查询 |

---

## 六、相关文件索引

### 前端（Phase 2 已实现）

| 文件 | 作用 | 状态 |
|------|------|------|
| `ontology-engine-ui/src/pages/rules/RuleGroupListPage.tsx` | 规则组列表 + 导入/导出 | ✅ |
| `ontology-engine-ui/src/pages/rules/RuleGroupDetailPage.tsx` | 三栏详情页（含 DAG） | ✅ |
| `ontology-engine-ui/src/pages/rules/RuleGroupCreatePage.tsx` | 创建页 | ✅ |
| `ontology-engine-ui/src/pages/rules/RuleStepEditPage.tsx` | 步骤编辑页（深链接） | ✅ |
| `ontology-engine-ui/src/components/rule/RuleStepList.tsx` | 步骤列表 + 拖拽排序 | ✅ |
| `ontology-engine-ui/src/components/rule/RuleChainDAG.tsx` | DAG 可视化（只读） | ✅ |
| `ontology-engine-ui/src/components/rule/ActionEditor.tsx` | 5 算子参数编辑器 | ✅ |
| `ontology-engine-ui/src/api/ruleGroups.ts` | API 客户端 | ✅ |
| `ontology-engine-ui/src/hooks/useRuleGroups.ts` | 数据获取 Hook | ✅ |
| `ontology-engine-ui/src/stores/ruleStore.ts` | Zustand 状态 | ✅ |
| `ontology-engine-ui/src/pages/spaces/SpaceDetailPage.tsx` | 统一规则管理导航入口 | ✅ |

### 后端

| 文件 | 作用 | 状态 |
|------|------|------|
| `ontology_engine/api/routes/rules.py` | 规则 API 路由 | ✅ |
| `ontology_engine/services/rule_service.py` | 规则服务层（含 YAML 导入/导出） | ✅ 但格式待升级 |
| `ontology_engine/engine/rule/models.py` | 规则数据模型 | ✅ |
| `ontology_engine/storage/duckdb/store.py` | DuckDB 存储（含 upsert 修复） | ✅ |
| `ontology_engine/engine/rule/operators/` | 算子注册中心 | ✅ |
| `ontology_engine/migrations/add_source_declaration_id.py` | 外键字段迁移脚本 | ✅ |

### 旧系统（已废弃）

| 文件 | 状态 |
|------|------|
| `ontology-engine-ui/src/pages/spaces/RuleLogicsPage.tsx` | ✅ 已删除（T5） |
| `ontology-engine-ui/src/pages/spaces/RuleDeclarationsPage.tsx` | ✅ 已删除（T5） |

### 新增设计文档

| 文件 | 内容 |
|------|------|
| `docs/03-rfc/RFC-017-rule-orchestration-yaml-format.md` | Phase 2 YAML 格式设计（rule_group + rule_steps） |

---

## 七、附录：用户旅程图（Phase 2 目标态）

```
[语义空间]
     │
     ▼
[规则组列表 /rules]
     │
     ├──[创建规则组]──→ 四元素配置（作用对象/适用场景/I/O要素）
     │                      │
     │                      ▼
     │              [规则实例列表] ←── DAG 可视化
     │                      │
     │            ┌─────────┼─────────┐
     │            ▼         ▼         ▼
     │       [添加规则] [拖拽排序] [模拟执行]
     │            │
     │            ▼
     │    [算子选择]──→ [专业化参数编辑器]
     │                      │
     │                      ▼
     │              [保存]──→ [DAG 更新]
     │
     └──[导出 YAML]──→ [合规性验证]──→ [下载]
```
