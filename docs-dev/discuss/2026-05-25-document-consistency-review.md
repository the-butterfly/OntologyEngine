# 文档一致性审查报告

> **日期**: 2026-05-25
> **触发原因**: 面向 AGENT 知识库工具定位，对 docs 目录下内容进行逐一审查
> **审查范围**: docs/ 全量文档 + CLAUDE.md

---

## 一、P0 修复项（已实施）

### 1. TODO.md — 移除已标注 ✅ 的完成项

移除以下已完成但仍保留在 Now 列表中的条目：
- Agent Memory recall 通配符/空查询返回空（已修复）
- Agent Memory audit 字段扩展（已实现）
- Agent Memory 新增 heatmap/disposition/dashboard 等端点（已实现）

更新 QUL 约束类型扩展条目，将 `✅ temporal+user_preference+decision 已完成` 改为 `3/8 已完成` 的客观表述，降级为 P2。

更新日期至 2026-05-25。

### 2. CLAUDE.md — 修正 RFC 路径

实际 RFC 文件在 `docs-dev/03-rfc/`，而非 `docs/03-rfc/`。

修正位置：
- 核心约束 #6：`docs/03-rfc/*.md` → `docs-dev/03-rfc/*.md`
- 文档三层结构图：删除 `docs/` 下的 `03-rfc/` 子目录（已移至 docs-dev）
- 文档角色分层表：`docs/03-rfc/` → `docs-dev/03-rfc/`（Phase 2 改进 RFC 开发版本）
- SoT 约定表：`docs/03-rfc/RFC-010-phase2-roadmap.md` → `docs-dev/03-rfc/RFC-010-phase2-roadmap.md`
- 必备文档表：`docs-dev/03-rfc/ docs/03-rfc/` → `docs-dev/03-rfc/`

### 3. STATUS.md — 同步 TODO.md 变更与路径修正

- 更新日期至 2026-05-25
- 热点质量问题表：将 7 个"已完成"条目折叠（Agent Memory 编译层 BUG、QUL 架构缺失、Consolidation + Audit、recall 通配符 BUG、前端-后端 API 对齐、ActivityLog 系统、DispositionStore、Overrides 逻辑统一），合并保留 Agent 记忆系统总条目和 QUL 扩展条目
- `03-rfc/` 路径修正为 `docs-dev/03-rfc/`

### 4. api/README.md — 更新 Schema 归档链接

`source_of_truth` 中的 `docs-baseline/05-schema-v2/09-canonical-schema-spec.md`（已归档）改为 `docs/02-design/schema/01-schema-spec.md`（当前事实源）。

Reference Documents 表中同样修正。

### 5. 10-kb-process.md — 删除 §2.3 重复内容

§2.3 的 YAML 提取模板 + Schema 感知工作流程 + Schema 的意义段落完整重复了两遍（约 50 行），删除第二次重复。

---

## 二、P1 新增/修正项（已实施）

### 6. 新增 docs/02-design/README.md 目录索引页

`02-design/` 目录下含 10+ 个子目录，之前无入口索引页。新增 README.md 提供：
- 模块导航表（模块名、目录、状态、核心文档链接、说明）
- 模块依赖关系图
- 设计文档使用规则

### 7. STATUS.md 中 03-rfc 路径修正

目录级状态矩阵中 `03-rfc/` 指向 `docs-dev/03-rfc/`。

---

## 三、文档优化与补强（已实施）

### 8. 更新 last_verified 日期

批量更新 10 份 overview 文档的 `last_verified` 从 2026-04-xx 更新至 2026-05-25：
- 01-vision.md, 04-modules.md, 05-concepts.md, 06-tech-stack.md, 07-project-structure.md, 08-knowledge-retrieval.md
- 09-agent-memory.md, 10-kb-process.md, README.md, 03-goals.md

### 9. 修正 Bundle Search 重复描述

`08-knowledge-retrieval.md` 中的 Bundle Search 四阶段算法完整重复了 `06-tech-stack.md` 的内容。
修改：保留简短公式和核心思想，添加 `→ 详细算法见 06-tech-stack.md` 引用。

### 10. 新增 docs/02-design/ingestion/README.md

知识摄入统一文档，提供：
- 摄入全景架构图
- 5 阶段管线总览
- 来源类型矩阵（数据库/代码/文档/PDF/图片/网页/API）
- 子文档索引（IngestionService、Extraction Pipeline、非结构化来源）

### 11. 新增 docs/02-design/ingestion/unstructured-sources.md

非结构化来源处理流程文档，提供：
- 来源分类（PDF/图片/网页/泛文本）
- Stage -1 格式预处理（各类型专属管线）
- 分块策略扩展
- Schema-Aware 提取适配
- 存储策略与增量处理
- 与结构化来源的差异对比

### 12. 新增 docs/01-overview/11-agent-onboarding.md

Agent 引导文档（[单一事实源]），提供：
- MCP Server 连接方式
- 完整 MCP 工具清单（24+ 工具，按功能分组）
- 5 个典型使用场景（查询/记忆写入/反思/审批/规则执行）
- 调用约定（空间隔离、错误处理、置信度标签）

### 13. 新增 docs/02-design/deployment.md

部署指南文档，提供：
- 系统要求与依赖
- 快速启动流程（4 步）
- 数据目录结构
- 生产环境部署（云存储模式 + Docker）
- 故障恢复策略

### 14. 修正 CLAUDE.md tests/unit/ 引用

`tests/unit/` 目录不存在。修正：
- 约束 #3：添加备注"tests/ 目录规划中，当前以 examples/ 用例验证为主"
- 质量门禁：移除 pytest 命令，替换为 examples 验证命令

### 15. 更新 docs/README.md

- 更新日期至 2026-05-25
- 修正 `03-rfc/` 路径为 `docs-dev/03-rfc/`
- 新增 agent-memory、ingestion、deployment 导航条目

### 16. 更新 docs/STATUS.md

- 新增 3 份文档：agent-onboarding、ingestion、deployment

---

## 四、面向 AGENT 知识库工具的定位评估

### 已覆盖维度

| 维度 | 状态 | 文档入口 |
|------|------|---------|
| 结构化知识摄入 | ✅ Schema 驱动 + 三通道提取 | [06-tech-stack.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/01-overview/06-tech-stack.md), [ingestion/README.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/ingestion/README.md) |
| 非结构化摄入 | ✅ 知识摄入全链路文档 | [unstructured-sources.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/ingestion/unstructured-sources.md) |
| 知识管理循环 | ✅ Build → Govern → Consume 闭环 | [10-kb-process.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/01-overview/10-kb-process.md) |
| 消费检索 | ✅ Layer-R/S 双路 + RRF 融合 | [08-knowledge-retrieval.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/01-overview/08-knowledge-retrieval.md) |
| Agent 记忆 | ✅ remember/recall/reflect 三操作 | [09-agent-memory.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/01-overview/09-agent-memory.md) |
| Agent onboarding | ✅ MCP 工具清单 + 使用示例 | [11-agent-onboarding.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/01-overview/11-agent-onboarding.md) |
| 多域隔离 | ✅ 语义空间 + domain_id | [05-concepts.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/01-overview/05-concepts.md) |
| MCP 协议 | ✅ 工具暴露 | `ontology_engine/mcp/tools/` |
| 部署指南 | ✅ 本地部署 + 配置 + 启动 | [deployment.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/deployment.md) |

### 仍待补强维度

| 维度 | 建议 | 优先级 |
|------|------|--------|
| 前端架构设计 | `docs/02-design/frontend/` 仅有 TODO.md，需完整设计文档 | P2 |
| tests/ 目录 | CLAUDE.md 中提到的 pytest 质量门禁暂时以 examples/ 替代 | P2 |
| Docker Compose | 部署指南提到 Docker 部署"规划中"，需补充 docker-compose.yml | P2 |
| Agent onboarding 示例 | 增加更多 Agent 交互场景的完整调用示例 | P2 |

---

## 五、变更文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `docs/TODO.md` | 修改 | 移除完成项，更新日期 |
| `docs/STATUS.md` | 修改 | 折叠热点已完成项，新增 3 份文档 |
| `docs/ROADMAP.md` | 修改 | 更新日期 |
| `docs/README.md` | 修改 | 修正路径，新增导航 |
| `docs/02-design/api/README.md` | 修改 | 修正 Schema 链接 |
| `docs/01-overview/10-kb-process.md` | 修改 | 删除重复内容 |
| `docs/01-overview/08-knowledge-retrieval.md` | 修改 | Bundle Search 引用替代重复 |
| `docs/01-overview/` (10 份) | 修改 | 更新 last_verified |
| `CLAUDE.md` | 修改 | 修正 RFC/tests 路径 |
| `docs/02-design/README.md` | **新增** | 02-design 目录索引页 |
| `docs/02-design/ingestion/README.md` | **新增** | 知识摄入统一文档 |
| `docs/02-design/ingestion/unstructured-sources.md` | **新增** | 非结构化来源处理 |
| `docs/01-overview/11-agent-onboarding.md` | **新增** | Agent 引导文档 |
| `docs/02-design/deployment.md` | **新增** | 部署指南 |
