# ADR-012: 规则编排系统剩余架构决策

| 字段 | 值 |
|------|-----|
| 状态 | accepted |
| 日期 | 2026-05-15 |
| 决策者 | 文档治理审查 |
| 关联 | RFC-014 ~ RFC-017, ADR-010 D10-5 |

---

## 背景

ADR-010 D10-5 已记录规则四元素模型和 5+5 算子体系的关键决策。本 ADR 补充记录规则编排系统的其他架构级决策，包括双系统合并、语义空间隔离、YAML 格式升级。

---

## D12-1: 规则系统统一命名空间

**来源**: RFC-014 (§1.2), RFC-016 (§T1 统一入口导航)

**决策**:
1. `/rules/logics`（旧系统）与 `/rules`（Phase 2 新系统）合并为统一 `/rules` 命名空间
2. 旧 `RuleLogicsPage`/`RuleDeclarationsPage` 前端路由已删除
3. `SpaceDetailPage` 导航统一为 `/rules?schemaId=X`
4. 旧规则声明通过 `rule_groups.source_declaration_id` 外键桥接，不做数据迁移

**理由**:
- 双系统并行造成用户困惑（"该用哪个规则入口？"）
- 统一命名空间减少维护负担
- 桥接策略避免破坏性迁移

**影响**:
- 新代码应只通过 `/rules` 命名空间访问规则
- 旧 `RuleDeclaration` 声明文件不做迁移，通过桥接字段查询关联
- 前端所有规则入口合并

---

## D12-2: 语义空间隔离原则

**来源**: RFC-015 (§摘要), RFC-014 (§4.0 语义空间隔离)

**决策**:
1. 所有规则编排 API 调用必须携带 `schema_id` 参数
2. 前端所有自定义 Hooks 默认接收 `schemaId`，从 URL 参数或 Zustand store 获取
3. API 客户端在请求头或查询参数中传递 `schema_id`
4. 规则组、规则步骤按 `schema_id` 隔离，不同语义空间互不可见

**理由**:
- 多语义空间（多知识域）场景下，规则是空间内的资源，不是全局资源
- 为未来多租户和空间级 RBAC 奠定基础

**影响**:
- 前端所有 `useRuleGroups()` / `useRuleSteps()` 等 hooks 必须传 `schemaId`
- Zustand store 中的 `currentSchemaId` 是全局状态，不可省略
- YAML 导入/导出也需携带 `schema_id` 上下文

---

## D12-3: YAML 格式从扁平升级为结构化

**来源**: RFC-017 (§摘要)

**决策**:
1. YAML 导入/导出格式从扁平的 `rule_definitions[] + rule_logics[]` 升级为结构化的 `rule_group + rule_steps`
2. 新格式与 `RuleGroupDefinition` 数据模型完全对齐
3. 旧格式导入按需通过兼容层处理
4. `when/then_action/else_action` 格式升级为 `steps[] + depends_on` 格式

**理由**:
- 扁平格式无法表达规则组结构（RuleGroup → RuleStep 层级）
- 结构化格式与四元素模型一一对应，降低解析复杂度
- 为 DAG 可视化提供直接的 JSON/YAML → 画布映射

**影响**:
- `RuleService.import_from_yaml()` 和 `export_rule_group_to_yaml()` 需重新实现
- 旧 schema.yaml 示例文件需逐步升级
- Phase 2-B 画布拖拽依赖新格式的表达力

---

## D12-4: 前端状态管理架构

**来源**: RFC-015 (§一)

**决策**:
1. 前端规则编排采用 **Zustand** 作为全局状态管理（非 Redux）
2. 数据获取通过自定义 **React Query Hooks**（非 useEffect 手写 fetch）
3. TypeScript 类型定义集中管理在 `src/types/rule.ts`
4. API 客户端通过 `src/api/ruleGroups.ts` 统一封装
5. DAG 可视化采用 **ReactFlow + dagre**（仅在 Phase 2-B 实现可编辑模式）

**理由**:
- 与项目中现有前端架构一致（非引入新框架）
- React Query 处理缓存失效和乐观更新
- G6→ReactFlow+dagre 切换已在前序实现中验证

**影响**:
- 新增规则功能遵循同一模式：类型 → API → Hooks → Store → 组件
- DAG 可编辑模式保留为 Phase 2-B 规划

---

## 影响范围

| 决策 | 影响模块 | 影响层级 |
|------|----------|----------|
| D12-1: 统一命名空间 | services/rules, frontend/ | Service + Frontend |
| D12-2: 语义空间隔离 | api/, frontend/ | API + Frontend |
| D12-3: YAML 格式化 | services/rules, frontend/ | Service + Frontend |
| D12-4: 前端架构 | frontend/ | Frontend |

## 关联 ADR

| ADR | 关系 |
|-----|------|
| ADR-010 D10-5 | 互补：D10-5 定义四元素模型，本 ADR D12-1~D12-4 定义周边架构决策 |
| ADR-008 | 补充：Phase 1-4 审查中的规则相关决策 |
