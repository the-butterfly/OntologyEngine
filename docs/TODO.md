# TODO - 基于评审意见

> **Last Updated**: 2026-04-08
> **状态**: P0/P1 已完成，P2 待处理

## 🔴 High Priority (Must Fix Before MVP) — ✅ 已完成

### ✅ TODO-001: DuckDB + NetworkX 存储策略
- **Decision**: DuckDB + NetworkX(按需)
- **Location**: [02-design/03-storage-design.md](./02-design/03-storage-design.md)
- **Completed**: 2026-04-08

### ✅ TODO-002: 实现真实规则引擎
- **Decision**: KGML YAML + DAG 执行模型
- **Location**: [02-design/04-rule-engine-design.md](./02-design/04-rule-engine-design.md)
- **Completed**: 2026-04-08

### ✅ TODO-003: 算子注册系统
- **Decision**: OperatorRegistry + 9 种算子
- **Location**: [05-schema-v2/04-business-logic.md](./05-schema-v2/04-business-logic.md)
- **Completed**: 2026-04-08

## 🟡 Medium Priority (Before Phase 2) — 🔄 部分完成

### 🔄 TODO-004: Faiss 维度处理
- **Task**:
  1. Store dimension in vector metadata ✅ 已写入存储设计
  2. Validate dimension consistency on insert
  3. Document index rebuild process
- **Status**: 部分完成
- **Location**: [02-design/03-storage-design.md](./02-design/03-storage-design.md)

### 🔄 TODO-005: LLM 推理边界定义
- **Task**:
  1. LLM_INFERENCE 算子已设计 ✅
  2. Prompt templates 待定义
  3. Cost control 待实现
- **Status**: 设计完成，实现待 Phase 2
- **Location**: [05-schema-v2/04-business-logic.md](./05-schema-v2/04-business-logic.md)

### ⏳ TODO-006: 并发写入模型
- **Task**:
  1. Single-writer requirement
  2. Transaction boundaries
  3. Locking strategy
- **Status**: Open
- **Location**: 待补充

### ✅ TODO-007: dimension_attributes 冲突解决
- **Decision**: L2 categorization 独立层 + L4 applies_to 声明
- **Location**: [05-schema-v2/02-categorization.md](./05-schema-v2/02-categorization.md)
- **Completed**: 2026-04-08

## 🟢 Lower Priority (Nice to Have)

### ⏳ TODO-008: 文档一致性检查更新
- **Task**: 验证文档与代码一致性
- **Status**: Open

### ⏳ TODO-009: AGENTS.md 约束验证
- **Task**: 更新路径引用为现有模块
- **Status**: Open

## 📋 完成清单

| TODO | Priority | Status |
|------|----------|--------|
| TODO-001 Storage | 🔴 | ✅ Done |
| TODO-002 RuleEngine | 🔴 | ✅ Done |
| TODO-003 Operators | 🔴 | ✅ Done |
| TODO-004 Faiss | 🟡 | 🔄 Partial |
| TODO-005 LLM | 🟡 | 🔄 Partial |
| TODO-006 Concurrent | 🟡 | ⏳ Open |
| TODO-007 dimension | 🟡 | ✅ Done |
| TODO-008 consistency | 🟢 | ⏳ Open |
| TODO-009 AGENTS | 🟢 | ⏳ Open |
