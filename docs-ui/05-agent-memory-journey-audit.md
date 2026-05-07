# Agent Memory 前端用户旅程审计

> **status**: accepted | **phase**: Phase1&2-completed | **source_of_truth**: 本文档 | **last_verified**: 2026-05-06

---

## 1. 审计结论

### 1.1 关键发现

| 维度 | 状态 | 说明 |
|------|------|------|
| 基础页面框架 | ✅ | 5 个页面已搭建，路由与导航完整 |
| 数据加载 | ✅ | 类型与后端已对齐，数据可正常显示 |
| 资产明细查看 | ✅ | `MemoryDetailDrawer` 组件已接入各页面 |
| 图谱视图 | ✅ | `MemoryGraphView` 已接入总览页 |
| 用户旅程连贯性 | ✅ | 页面间已添加关联跳转 |

### 1.2 已修复的断裂点

| # | 断裂点 | 修复方式 | 验证 |
|---|--------|---------|------|
| B1 | 无记忆节点详情查看 | 新增 `MemoryDetailDrawer`，接入总览/构建/消费页 | ✅ E2E |
| B2 | 无记忆关系图谱 | 新增 `MemoryGraphView` (G6)，接入总览页 | ✅ E2E |
| B3 | 待审区无审批操作 | 待审区添加确认/拒绝/更正按钮 | ✅ E2E |
| B4 | 消费结果无详情展开 | 结果列表添加查看详情按钮 + 分层折叠 | ✅ E2E |
| B5 | Disposition 滑块未生效 | 前端改为传 scene name（high_recency/high_relevance/high_confidence） | ✅ 直接实现 |
| B6 | 反思结果无展示 | 任务列表添加展开详情（洞察/矛盾/整合） | ✅ E2E |
| B7 | 页面间无关联跳转 | 管理页添加快捷导航，统计卡片可点击 | ✅ E2E |
| B8 | 无文档导入功能 | 未实现，标记为 Phase 3 | ⏳ |

---

## 2. 用户旅程

```
[用户进入空间] → [点击 Agent Memory 菜单]
    ↓
[记忆总览] ──→ 查看统计数据 (总记忆/Layer-R/Layer-S/待审)
    │         → 查看记忆类型分布、信念状态分布
    │         → 查看记忆节点图谱 (G6，按层级着色)
    │         → 查看记忆节点列表表格 → 点击"查看"打开详情 Drawer
    │         → 切换 Agent 活动 Tab → 查看活动统计 + 活动列表
    │         → 点击活动"查看"打开详情 Drawer
    │
    ├──→ [记忆构建] ──→ 填写表单创建记忆
    │              → 待审区列表：确认 / 更正 / 拒绝 / 查看
    │              → 更正：弹出表单提交 correctedText + reason
    │
    ├──→ [记忆管理] ──→ 查看统计 (总记忆数/待审核/类型数/层数)
    │              → 快捷导航：去构建 / 去检索 / 去反思
    │              → 点击"待审核"统计卡片跳转构建页
    │              → 运行整合 / 运行遗忘
    │              → 查看信念状态分布 / 记忆类型分布
    │              → 查看更正历史 (Timeline)
    │
    ├──→ [记忆消费] ──→ 输入查询内容
    │              → 调节 Disposition Profile (时效/相关/置信)
    │              → 查看分层检索结果 (按 opinion/semantic/procedure/perception 分组)
    │              → 展开层级面板 → 查看结果列表
    │              → 点击"查看详情"打开 Drawer
    │              → 对 pending_review 节点点击"批准"
    │
    └──→ [反思中心] ──→ 填写反思主题、迭代数、聚焦类型
                   → 启动反思任务
                   → 查看任务列表 → 点击"展开详情"
                   → 查看：摘要、洞察列表、矛盾列表、整合节点
```

---

## 3. 组件清单

| 组件 | 文件 | 用途 | 状态 |
|------|------|------|------|
| `MemoryDetailDrawer` | `src/components/memory/MemoryDetailDrawer.tsx` | 记忆节点详情抽屉（属性、时间、操作） | ✅ |
| `MemoryGraphView` | `src/components/memory/MemoryGraphView.tsx` | G6 力导向图谱（按层级着色） | ✅ |
| `MemoryOverviewPage` | `src/pages/spaces/memory/MemoryOverviewPage.tsx` | 总览：统计+图谱+列表+活动 | ✅ |
| `MemoryBuildPage` | `src/pages/spaces/memory/MemoryBuildPage.tsx` | 构建：表单+待审区（含审批） | ✅ |
| `MemoryManagePage` | `src/pages/spaces/memory/MemoryManagePage.tsx` | 管理：统计+导航+维护+更正历史 | ✅ |
| `MemoryConsumePage` | `src/pages/spaces/memory/MemoryConsumePage.tsx` | 消费：搜索+Disposition+分层结果 | ✅ |
| `ReflectCenterPage` | `src/pages/spaces/memory/ReflectCenterPage.tsx` | 反思：表单+任务列表+详情展开 | ✅ |

---

## 4. 验收标准

### 4.1 功能验收

| # | 验收项 | 验证方式 |
|---|--------|---------|
| A1 | 记忆总览页加载时显示统计数据和分布标签 | Playwright: `memory-overview-phase2.png` |
| A2 | 记忆节点表格展示所有节点，点击"查看"打开详情 Drawer | Playwright: 点击表格行按钮，验证 Drawer 标题 |
| A3 | G6 图谱渲染节点，点击节点打开详情 Drawer | Playwright: 验证图谱容器存在 |
| A4 | Agent 活动 Tab 显示统计卡片和活动列表 | Playwright: `memory-activities-phase2.png` |
| A5 | 待审区列表显示确认/更正/拒绝/查看按钮 | Playwright: `memory-build-phase2.png` |
| A6 | 消费页搜索结果按认知层级分组折叠展示 | Playwright: `memory-consume-phase2.png` |
| A7 | 反思任务可展开查看洞察/矛盾/整合节点 | Playwright: `memory-reflect-phase2.png` |
| A8 | 管理页显示快捷导航和更正历史 | Playwright: `memory-manage-phase2.png` |
| A9 | 页面间可通过导航按钮跳转 | Playwright: 验证 URL 变化 |

### 4.2 质量门禁

```bash
cd ontology-engine-ui
npm run type-check    # 通过（memory 相关无错误）
npx playwright test tests/memory-journey-e2e.spec.ts --project=chromium  # 7/7 通过
```

---

## 5. 外部依赖

| # | API | 状态 | 影响 |
|---|-----|------|------|
| D1 | `GET /spaces/{id}/memory/{node_id}` | ✅ 已补充 | DetailDrawer 当前通过 recall 兼容，可直接替换 |
| D2 | `GET /spaces/{id}/memory/graph` 返回边数据 | ✅ 已补充 | recall 接口 `include_evidence=True` 时返回 `edges` 字段，前端 MemoryGraphView 已接入 |
| D3 | recall 支持 `disposition_override` | ✅ 已补充 | 前端改为传 scene name（high_recency/high_relevance/high_confidence），后端已支持 |
| D4 | `GET /spaces/{id}/memory/contradictions` | ✅ 已补充 | 矛盾查询端点，返回 CONTRADICTS 边列表 |
| D5 | `GET /spaces/{id}/memory/{node_id}/evidence` | ✅ 已补充 | 证据链端点，返回 source_fragments + supporting_nodes + consolidated_into |
| D6 | `GET /spaces/{id}/memory/corrections` | ✅ 已补充 | 更正历史端点，返回 SUPERSEDES 边列表 |
| D7 | `GET /spaces/{id}/memory/stats` 增强 | ✅ 已补充 | 新增 pending_review/superseded/expired/open_contradictions/total_corrections 字段 |

---

## 6. Phase 3 待办（未实现）

| # | 任务 | 优先级 | 依赖 | 状态 |
|---|------|--------|------|------|
| T3.1 | 文档上传与提取进度 | P2 | 后端需新增 ingestion API | ⏳ |
| T3.2 | 矛盾看板 | P2 | ~~后端需新增 contradictions 查询接口~~ | ✅ 后端已补充 |
| T3.3 | 证据链展开 | P2 | ~~后端需新增 evidence API~~ | ✅ 后端已补充 |
| T3.4 | 治理仪表盘增强 | P2 | ~~后端需补充编译成本、过期数等指标~~ | ✅ 后端 stats 已增强 |

---

## 7. 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-06 | v1.0 | 初始审计，识别 8 个断裂点 |
| 2026-05-06 | v2.0 | Phase 1&2 完成：修复 B1-B7，更新用户旅程、验收标准、组件清单 |
| 2026-05-06 | v3.0 | Phase 3 后端 API 补充：D2-D7 全部实现，B5 从间接改为直接实现，T3.2-T3.4 后端依赖已解除 |
