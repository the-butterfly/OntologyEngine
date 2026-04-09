# OntologyEngine 设计文档

> **项目阶段**: MVP (Demo 已跑通) → Phase 1 准备
> **文档版本**: 2026-04-09
> **最后整理**: 架构评审决策落地（12项关键设计点）

## 文档导航

### 01 - 概要设计

| 文档 | 内容 |
|------|------|
| [01-vision.md](./01-overview/01-vision.md) | 项目愿景：面向 AI Agent 的结构化知识推理引擎 |
| [02-motivation.md](./01-overview/02-motivation.md) | 动机：为什么需要 OntologyEngine |
| [03-goals.md](./01-overview/03-goals.md) | 阶段目标与验收标准 |
| [04-modules.md](./01-overview/04-modules.md) | 模块架构与边界约束 |
| [05-concepts.md](./01-overview/05-concepts.md) | 核心概念 (Concept/Relation/Rule/Metric) |
| [06-tech-stack.md](./01-overview/06-tech-stack.md) | 技术选型与核心依赖 |
| [07-project-structure.md](./01-overview/07-project-structure.md) | 代码组织与模块边界 |

### 02 - 详细设计

| 文档 | 内容 |
|------|------|
| [01-schema-spec.md](./02-design/01-schema-spec.md) | KGML Schema v1 规范 |
| [02-api-design.md](./02-design/02-api-design.md) | REST API 设计 |
| [03-storage-design.md](./02-design/03-storage-design.md) | DuckDB + Faiss 存储设计 |
| [04-rule-engine-design.md](./02-design/04-rule-engine-design.md) | 规则引擎 DAG 执行模型 |
| [05-services-design.md](./02-design/05-services-design.md) | Services 层 (用例编排/事务/协调) |
| [06-formula-spec.md](./02-design/06-formula-spec.md) | Formula 表达式规范 (语法/函数/安全) |

### 07 - Agent 接口

| 文档 | 内容 |
|------|------|
| [07-agent-interface.md](./07-agent-interface.md) | MCP/CLI 接口 + 云端/本地混合部署 |
| [08-knowledge-retrieval.md](./08-knowledge-retrieval.md) | 知识检索服务 (Query/Trace/Execute) |

### 03 - RFC 过程文档

| 文档 | 状态 |
|------|------|
| [RFC-001-knowledge-graph-markup-language.md](./03-rfc/RFC-001-knowledge-graph-markup-language.md) | ✅ Adopted |
| [RFC-002-storage-strategy.md](./03-rfc/RFC-002-storage-strategy.md) | ✅ Adopted |
| [RFC-003-rule-execution-model.md](./03-rfc/RFC-003-rule-execution-model.md) | ✅ Adopted |

### 04 - 测试与修复

| 文档 | 内容 |
|------|------|
| [01-testing-guide.md](./04-testing/01-testing-guide.md) | 测试规范、Subagent 模板、覆盖率要求 |

### 05 - Schema v2 (Next Phase)

> 下一步核心设计：四层分离架构

| 文档 | 内容 |
|------|------|
| [00-overview.md](./05-schema-v2/00-overview.md) | v2 设计概览与动机 |
| [01-fact-objects.md](./05-schema-v2/01-fact-objects.md) | L1: 事实对象定义 |
| [02-categorization.md](./05-schema-v2/02-categorization.md) | L2: 归类分析 |
| [03-analytical-elements.md](./05-schema-v2/03-analytical-elements.md) | L3: 分析要素 |
| [04-business-logic.md](./05-schema-v2/04-business-logic.md) | L4: 业务逻辑 (算子体系) |
| [05-complete-example.md](./05-schema-v2/05-complete-example.md) | 完整示例 |

### 06 - 开发指南

| 文档 | 用途 |
|------|------|
| [storage-adapter.md](./development/storage-adapter.md) | 添加新存储适配器指南 |
| [operator.md](./development/operator.md) | 添加规则算子指南 |
| [code-style.md](./development/code-style.md) | 代码规范 (类型注解/错误处理) |
| [communication.md](./development/communication.md) | 沟通风格与反馈模板 |
| [api-design.md](./development/api-design.md) | Python API 类设计 (vs REST API) |
| [schema-spec.md](./development/schema-spec.md) | Pydantic 模型定义 (vs YAML 规范) |
| [testing.md](./development/testing.md) | ➡️ 重定向到 [04-testing/](./04-testing/01-testing-guide.md) |

---

## 快速参考

### Schema v2 架构 (四层分离)

```
L1 事实对象 ──────────────────────────▶ 定义实体/关系/属性
    │                                      (客观数据)
    ▼
L2 归类分析 ──────────────────────────▶ 行业/规模/风险标签
    │                                      (分类维度，复用 L4 引擎)
    ▼
L3 分析要素 ──────────────────────────▶ 指标定义 + overridable 标记
    │                                      (WHAT: 计算什么)
    │                          直接调用 ──▶│
    ▼                                      │
L4 业务逻辑 ──────────────────────────▶ Formula/算子/规则
                                           (HOW: 如何计算)
                                           两级执行: L0 simpleeval + L1 AST 沙箱
                                           SWITCH/BINNING/SCORECARD
                                           GRAPH/MODEL_INFERENCE/LLM
```

### 当前架构 (MVP)

```
API (FastAPI)
    ↓
Services (用例编排/事务管理)
    ↓
Engine (Query/Rule/Metric/Vector)
    ↓
Storage (DuckDB + Faiss + NetworkX)
    ↓
Core (SchemaLoader/OperatorRegistry/ExpressionEngine)
```

### 关键约束

1. 本地存储优先 —— 零外部依赖
2. API 边界封闭 —— 禁止跨层调用
3. Schema 即配置 —— 业务逻辑 YAML 定义
4. 测试先行 —— 覆盖率 ≥ 80%

### Schema v1 vs v2

| 维度 | v1 | v2 |
|------|-----|-----|
| 结构 | 扁平 | 四层分离 |
| 复用 | 规则绑定 entity_type | 声明式 applies_to + GLOBAL |
| 清晰度 | attributes 混杂 | 事实/分类/指标/逻辑分离 |
| formula 位置 | 分散在各层 | 统一在 L4 |
| 公式表达 | 多行文本 | 两级执行：L0 simpleeval + L1 AST 沙箱 |
| 复杂规则 | if/else | SWITCH/BINNING/SCORECARD/GRAPH/MODEL/LLM |
| 跨引擎协调 | 未定义 | L3→L4 直接调用 |
| 规则作用域 | 硬编码 | 声明式 applies_to (含 GLOBAL) |
| 覆盖控制 | 无 | L3 overridable 标记 |
| 图查询 | Cypher 空壳 | 简化版图遍历 DSL（1-2跳） |
| 反馈闭环 | 无 | 自动影响分析 + 人工确认 |
| 部署模式 | 仅本地 | 本地+平台双模式 |

### 质量门禁

```bash
mypy ontology_engine/ --strict
ruff check ontology_engine/
pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing
```

---

## 归档文档

- [archive/](./archive/) - 已废弃/历史文档

---

## 待办

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P0 | 评审意见修复 | ✅ 完成 |
| P0 | 架构评审 12 项决策落地 | ✅ 完成 (2026-04-09) |
| P1 | Services 层设计 | ✅ 完成 |
| P1 | Formula 两级执行模型 | ✅ 完成 (决策 #10) |
| P1 | 文档目录重组 + 清理 | ✅ 完成 |
| P1 | 图遍历 DSL 替代 Cypher | ✅ 完成 (决策 #9) |
| P2 | 自适应权重检索 | ⏳ Phase 2 |
| P2 | LLM 推理边界细化 | ⏳ 待处理 |
| P2 | 并发写入模型 | ⏳ 待处理 |

详细清单见 [TODO.md](./TODO.md)
