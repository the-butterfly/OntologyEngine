# OntologyEngine 设计文档

> Python 版下一代知识库系统

## 项目定位

面向 AI Agent 的下一代知识库，提供：
- 分层事实描述（Schema → Entity → Instance）
- 规则管理与执行引擎
- Agent Memory 服务
- 用户反馈实时回流

## 核心架构

```
┌─────────────────────────────────────────────────────────┐
│ 应用层: Agent / 风控系统 / 智能问答                      │
├─────────────────────────────────────────────────────────┤
│ API 层: FastAPI / GraphQL / gRPC                        │
├─────────────────────────────────────────────────────────┤
│ 引擎层: 查询 / 规则 / 推理 / 向量检索                     │
├─────────────────────────────────────────────────────────┤
│ 存储层: SQLite + Faiss (本地) / Neo4j + pgvector (预留) │
├─────────────────────────────────────────────────────────┤
│ 数据层: KGML 导入 / ETL / 反馈回流                      │
└─────────────────────────────────────────────────────────┘
```

## 文档导航

### 核心设计

| 文档 | 内容 |
|------|------|
| [PROJECT_PHASE.md](./PROJECT_PHASE.md) | 项目阶段澄清 (重要！) |
| [TODO.md](./TODO.md) | 待办任务清单 |
| [架构概览](./architecture.md) | 系统分层、组件职责、数据流转 |
| [核心概念](./concepts.md) | Concept/Relation/Attribute/Rule/Metric 定义 |
| [技术选型](./tech-stack.md) | Python 技术栈、本地存储优先策略 |
| [项目结构](./project-structure.md) | 代码组织、模块边界、API 分层 |
| [开发路线](./roadmap.md) | 里程碑、Phase 规划 |

### Architecture Decisions

| 文档 | 内容 |
|------|------|
| [decisions/README.md](./architecture/decisions/README.md) | 决策索引 |
| [001-sqlite-graphstore-v2.md](./architecture/decisions/001-sqlite-graphstore-v2.md) | SQLite v2 |

### Archived Designs

| 文档 | 状态 |
|------|------|
| [design-proposals/](../archive/design-proposals/) | 已归档设计提案 |

### 开发指南 (`docs/development/`)

| 文档 | 场景 |
|------|------|
| [testing.md](./development/testing.md) | 编写测试用例、Subagent 指令模板 |
| [api-design.md](./development/api-design.md) | 设计新 API、接口评审 |
| [storage-adapter.md](./development/storage-adapter.md) | 添加存储适配器 |
| [operator.md](./development/operator.md) | 添加规则算子 |
| [code-style.md](./development/code-style.md) | 类型注解、错误处理、文档规范 |
| [communication.md](./development/communication.md) | 沟通风格、反馈模板 |

### 参考

| 文档 | 内容 |
|------|------|
| [一致性检查](./consistency-check.md) | 文档间约束一致性分析 |
| `raw/` | 原始详细设计文档 (KGML v3、金融场景等) |

## 快速开始

```bash
# 安装依赖 (仅本地存储)
pip install -e ".[dev]"

# 启动服务
python -m ontology_engine.server
```

## Agent 开发约束

详见 [AGENTS.md](../AGENTS.md) (项目根目录)

**核心约束**:
1. 本地存储优先 (SQLite/Faiss)
2. API 边界封闭
3. 测试先行
4. 文档同步
5. 边界外扩需审批
