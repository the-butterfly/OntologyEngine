# RFC-016: 规则编排系统 Gap 分析与实施路线

> **状态**: draft
> **父 RFC**: RFC-014 · RFC-015
> **创建日期**: 2026-04-16
> **作者**: the-butterfly

---

## 摘要

本文档从用户旅程完整性视角，分析当前规则编排系统的关键实施缺口：

1. **双系统并存问题**：`/rules/logics`（旧系统）与 `/rules`（Phase 2 新系统）的定位重叠但数据模型不同
2. **画布编排缺口**：Phase 2-B 规划的拖拽可视化编排尚未实现
3. **桥接缺口**：旧规则声明（RuleDeclaration）无法关联到新规则组（RuleGroup）
4. **要素 DAG 深度联动**：当前 DAG 只读，缺少点击节点→编辑规则的双向联动

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

**决策点**：
- 选项 A：逐步废弃旧系统，所有流量引导到 `/rules`（Phase 2 新系统）
- 选项 B：双轨并存，通过桥接层让旧规则声明引用新规则组
- 选项 C：统一入口层，URL 只是视图不同，共用同一数据模型

**建议**：采用选项 B/C 的混合——统一数据模型到 Phase 2，保留 `/rules/logics` 作为"兼容视图"，Phase 2 完成后废弃旧系统。

---

### Gap 2: 画布可视化编排（Phase 2-B 待办）

**现状**：RFC-014 Phase 2-B 路线图明确包含"规则画布可视化（拖拽编排）"，但尚未实现。

**已实现部分**（Phase 2-A）：
- `RuleChainDAG` 组件：`element_dependency` 维度的只读 DAG 展示
- 节点位置静态计算（`x: 100/300/500`, `y: 80 * idx`）
- 点击节点可跳转编辑（`handleDAGNodeClick` → `setInitialEditStep`）

**缺失部分**：
- 节点拖拽排序（应同步更新 `step_order` 并调用 `POST /rule-groups/:name/steps/reorder`）
- 新节点创建（从左侧算子面板拖入画布）
- 连线编辑（INPUT → STEP → OUTPUT 的边连接方式）
- 画布缩放/平移

**实施关键细节**：
- `@dnd-kit` 已引入项目（RuleStepList 中有使用），但 DAG 区域未使用
- G6 (`@antv/g6`) 已用于 `RuleChainDAG`，画布编排可考虑：
  - 选项 A：扩展 G6 使其可编辑（G6 4.x 支持拖拽节点）
  - 选项 B：引入 React Flow 等专门的可编辑画布库
- DAG 节点拖拽后需要：
  1. 更新本地位置 state
  2. 调用 `POST /rule-groups/:name/steps/reorder` 持久化 `step_order`
  3. 乐观更新 UI

---

### Gap 3: 旧规则声明到新规则组的桥接

**现状**：`RuleLogicsPage` 创建的 `RuleLogic` 存储在 `rule_logics` 表，`RuleGroup` 存储在 `rule_groups` 表，两者无关联字段。

**桥接方案**（若采用双轨并存）：

| 方案 | 说明 | 复杂度 |
|------|------|--------|
| 软链接 | `RuleGroup.name` 或 `RuleGroup.description` 包含旧 `RuleDeclaration` ID | 低 |
| 外键引用 | `rule_groups.source_declaration_id` 指向 `rule_declarations.id` | 中 |
| 数据迁移 | 将 `rule_logics` 数据迁移到 `rule_steps`，废弃旧表 | 高（一次性） |

**建议**：Phase 2 完成后执行一次性数据迁移，将 `rule_logics` → `rule_steps`，`rule_declarations` → 相关信息存入 `RuleGroup.description` 或 `applies_to`。

---

### Gap 4: DAG 双向联动深度不足

**现状**：
- `RuleChainDAG` 展示只读 DAG
- `handleDAGNodeClick` 可以跳转到编辑 Modal，但：
  - 没有反馈当前节点在 DAG 中的上下游关系
  - 没有高亮路径（从 INPUT 到该节点的路径）
  - 没有展示如果删除该节点会影响哪些 OUTPUT

**实施关键细节**：
- 后端 `/dag/path?from=X&to=Y` API 已存在，可用于高亮路径
- 可在 DAG 右侧增加"路径详情面板"，显示从选中节点到根节点的完整路径
- 影响分析：后端 DAG 构建时可以计算出"删除此节点影响哪些 OUTPUT"，可复用到前端

---

## 三、实施路线

### 路线 A：渐进式桥接（推荐）

```
当前（Phase 2 完成度 80%）
  ↓
[T1] 统一入口导航：规则管理菜单只保留一个入口
  ↓
[T2] 完善 Phase 2 画布编排（Phase 2-B）
  - 节点拖拽排序
  - 算子面板拖入创建
  - 连线编辑
  ↓
[T3] 双向联动增强
  - 路径高亮
  - 影响分析面板
  ↓
[T4] 数据迁移准备
  - 建立 rule_groups.source_declaration_id 外键
  - 迁移脚本编写
  ↓
[T5] 旧系统废弃（可选）
```

### 路线 B：一次性重建

```
[T1] 设计新统一数据模型（融合两套）
[T2] 一次性迁移所有 rule_logics → rule_steps
[T3] 实现完整 Phase 2（包括画布编排）
[T4] 废弃旧表和 API
```

---

## 四、关键决策点（需确认）

| # | 决策 | 选项 |
|---|------|------|
| D1 | 旧 `/rules/logics` 的最终处理策略？ | A: 废弃  B: 保留为只读兼容视图  C: 无限期双轨 |
| D2 | 画布编排技术选型？ | A: G6 可编辑模式  B: React Flow  C: 自研 Canvas |
| D3 | `RuleGroup.name` 是否允许与旧 `RuleDeclaration.id` 建立引用？ | A: 允许软链接  B: 新增 source_id 字段  C: 不建立引用 |
| D4 | Phase 2-B 画布编排是否作为独立里程碑？ | A: 独立完成  B: 与 T3 双向联动合并 |
| D5 | DAG 路径高亮是在后端计算还是前端计算？ | A: 后端 `/dag/path` API  B: 前端基于现有数据推导 |

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

| 文件 | 作用 |
|------|------|
| `ontology-engine-ui/src/pages/rules/RuleGroupListPage.tsx` | 规则组列表 |
| `ontology-engine-ui/src/pages/rules/RuleGroupDetailPage.tsx` | 三栏详情页（含 DAG） |
| `ontology-engine-ui/src/pages/rules/RuleGroupCreatePage.tsx` | 创建页 |
| `ontology-engine-ui/src/pages/rules/RuleStepEditPage.tsx` | 步骤编辑页（深链接） |
| `ontology-engine-ui/src/components/rule/RuleStepList.tsx` | 步骤列表 + 拖拽排序 |
| `ontology-engine-ui/src/components/rule/RuleChainDAG.tsx` | DAG 可视化 |
| `ontology-engine-ui/src/components/rule/ActionEditor.tsx` | 5 算子参数编辑器 |
| `ontology-engine-ui/src/api/ruleGroups.ts` | API 客户端 |
| `ontology-engine-ui/src/hooks/useRuleGroups.ts` | 数据获取 Hook |
| `ontology-engine-ui/src/stores/ruleStore.ts` | Zustand 状态 |

### 后端

| 文件 | 作用 |
|------|------|
| `ontology_engine/api/routes/rules.py` | 规则 API 路由 |
| `ontology_engine/services/rule_service.py` | 规则服务层 |
| `ontology_engine/engine/rule/models.py` | 规则数据模型 |
| `ontology_engine/storage/duckdb/store.py` | DuckDB 存储（含 upsert 修复） |
| `ontology_engine/engine/rule/operators/` | 算子注册中心 |

### 旧系统（待桥接或废弃）

| 文件 | 作用 |
|------|------|
| `ontology-engine-ui/src/pages/spaces/RuleLogicsPage.tsx` | 旧规则逻辑页 |
| `ontology-engine-ui/src/pages/spaces/RuleDeclarationsPage.tsx` | 旧规则声明页 |
| `ontology_engine/services/rule_service.py` (legacy) | 旧规则服务 |

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
