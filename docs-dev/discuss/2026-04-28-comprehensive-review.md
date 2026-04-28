# 2026-04-28 全面代码审查 GAP 分析决策记录

## 审查范围

6 个 subagent 并行分析：Schema、Storage、Engine、API/Services、Overview 文档一致性、设计文档内部一致性。

## 总体统计

| 维度 | GAP 总数 | Critical | High | Medium | Low |
|------|---------|----------|------|--------|-----|
| Schema 设计 vs 代码 | 58 | 4 | 21 | 25 | 8 |
| 存储层设计 vs 代码 | 45 | 0 | 14 | 20 | 11 |
| 引擎层设计 vs 代码 | 25 | 0 | 6 | 11 | 8 |
| API/服务层设计 vs 代码 | 53 | 0 | 7 | ~30 | ~16 |
| Overview 文档一致性 | 30 | 0 | 6 | 15 | 9 |
| 设计文档内部一致性 | 34 | 0 | 7 | 14 | 13 |
| **合计** | **~245** | **4** | **61** | **~115** | **~65** |

## 用户决策

| 议题 | 决策 | 说明 |
|------|------|------|
| 规则模型架构 | 完全重构为双模型 | RuleDefinitionDeclaration + RuleLogicDeclaration 替代一体模型 |
| Instance 验证规则 | 仅实现关键规则 | 引用完整性、类型约束等关键规则，其余 Phase 2 |
| AST 提取器 | 混合策略 | Python/JS 用 tree-sitter，其余语言正则回退 |
| 术语统一 | 统一为 Schema L4 术语 | rule_definitions + rule_logics 为标准 |

## 已执行的文档更新

### Overview 层
- README.md: 5→8 核心问题统一
- 01-vision.md: status proposed→accepted, last_verified 更新
- 03-goals.md: status proposed→accepted, Agent 会话记忆→Phase 2 规划
- 05-concepts.md: SoT 引用路径修正 (docs/05-schema-v2→docs/02-design/schema)
- 04-modules.md: NetworkXGraph 废弃→回退保留
- 06-tech-stack.md: status proposed→accepted
- 07-project-structure.md: status proposed→accepted, storage 子目录名修正

### 设计文档层
- 04-rule-engine-design.md: 引用路径修正 + 算子体系废弃警告
- 05-services-design.md: 引用路径修正 + VectorEngine 过时警告
- reference-alignment.md / temporal-modeling.md: Schema v2 引用路径修正
- 06-formula-spec.md: expression-engine 引用路径修正
- RFC-011: status draft→partial-implemented
- RFC-014: 引用路径修正

## 待执行项

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P0 | 规则模型双分离重构 | RuleDefinitionDeclaration + RuleLogicDeclaration |
| P0 | CategoryTag 数据类实现 | 设计文档定义完整，代码完全缺失 |
| P0 | Step.action 结构化 | 设计定义丰富 action 类型，代码仅用 str+dict |
| P1 | Instance 验证规则关键项 | 引用完整性、类型约束 |
| P1 | 统一 QueryEngine 编排器 | 各查询组件独立存在，无统一入口 |
| P1 | KnowledgeFragment 创建 | 提取管线不产出碎片实例 |
| P2 | AST 提取器 tree-sitter | 混合策略：Python/JS 用 tree-sitter |
| P2 | 术语映射表创建 | Schema L4 ↔ RFC-014 ↔ API 三套术语映射 |
| P2 | 设计文档补充 | 分类引擎、校验引擎独立设计文档 |
