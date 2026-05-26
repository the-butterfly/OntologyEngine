# Frontend Refactor RFC-001

## 概述

基于代码Review发现的问题，制定前端重构计划，重点解决硬编码标签和大文件问题。

## 问题清单

### P0 - 立即修复

- [x] **P0-1**: 删除 `labelMappings.ts` 中的硬编码业务标签，改为使用 backend 返回的 `label` 字段 ✅
- [x] **P0-2**: 修改 `SchemaGraph.tsx` 优先使用 `node.data.label` 而非 `METRIC_LABELS[node.id]` ✅
- [x] **P0-3**: 修改 `NodeDetailPanel.tsx` 优先使用 backend label ✅
- [x] **P0-4**: 修改 `MetricScorecard.tsx` 优先使用 backend label ✅
- [x] **P0-5**: 修改 `StepDetailPanel.tsx` 优先使用 backend label ✅

### P1 - 大文件拆分

- [x] **P1-1**: 拆分 `RuleExecutionPage.tsx` (814行) - 提取 render 函数为独立组件 ✅
- [x] **P1-2**: 拆分 `SchemaDeclarationPage.tsx` (724行) - 按 L1/L2/L3/L4 拆分为 tab 组件 ✅
- [x] **P1-3**: 拆分 `SchemaGraph.tsx` (660行) - 提取配置、工具函数、组件 ✅
- [x] **P1-4**: 拆分 `RulesEmbedPage.tsx` (719行) - 提取规则列表、编辑器 ✅
- [x] **P1-5**: 拆分 `RuleGroupDetailEmbedPage.tsx` (640行) - 拆分为详情面板、逻辑列表 ✅

### P2 - 代码质量改进

- [x] **P2-1**: 统一 `RULE_TYPE_COLORS` 到 `colorSchemes.ts` ✅ (已存在于colorSchemes)
- [x] **P2-2**: 清理 `simulation_tree_builder.py` 中未使用的 `Literal` import ✅
- [x] **P2-3**: 删除或 i18n 化 `labelMappings.ts` 中的硬编码中文 ✅ (已由P0处理)

### P3 - 类型增强

- [x] **P3-1**: 为 `spaceApi.ts` 添加完整的 TypeScript 类型定义 ✅
- [x] **P3-2**: 替换 `RuleExecutionPage.tsx` 中的 `any` 类型 ✅

---

## 修改记录

| 日期 | 任务 | 状态 | 验证方式 |
|------|------|------|----------|
| 2026-04-28 | P0-1 to P0-5 | ✅ Done | Schema可视化页面标签显示正确 |
| 2026-04-28 | P1-1 | ✅ Done | 规则执行页面功能正常 |
| 2026-04-28 | P1-2 | ✅ Done | Schema声明页各Tab正常切换 |
| 2026-04-28 | P1-3 | ✅ Done | 图可视化正常渲染 |
| 2026-04-28 | P1-4, P1-5 | ✅ Done | 规则嵌入页面正常 |
| 2026-04-28 | P2-1 to P2-3 | ✅ Done | 编译通过 |
| 2026-04-28 | P3-1 | ✅ Done | TypeScript类型完善 |
| 2026-04-28 | P3-2 | ✅ Done | TypeScript any类型替换 |

---

## 验证链接

### Schema可视化页面
- URL: `http://localhost:3000/spaces/space_2f568ad3/visualize`
- 验证: 检查指标和概念节点是否显示正确的 backend label

### 规则执行页面
- URL: `http://localhost:3000/spaces/space_2f568ad3/execute`
- 验证: 执行分析后检查结果中的指标名称是否正确显示

### Schema声明页面
- URL: `http://localhost:3000/spaces/space_2f568ad3/schema`
- 验证: L1/L2/L3/L4 各 Tab 数据正常显示
