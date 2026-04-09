# 工程评审讨论记录

**Date**: 2026-04-08 22:34  
**Context**: 对 docs/ 全部文档进行软件工程管理视角的系统性分析与辩论

## 分析范围

阅读了 30+ 个文档，覆盖：
- `01-overview/`（愿景/动机/目标/模块）
- `02-design/`（Schema/API/存储/规则引擎）
- `03-rfc/`（RFC-001~003）
- `05-schema-v2/`（四层分离设计）
- `architecture/decisions/`（ADR-001~006）
- 根目录散落文件

## 核心争议点与结论

### 1. 图查询 Cypher API — 不可行
**问题**：`POST /v1/query/graph` 接受 Cypher，但底层是 DuckDB（SQL）  
**结论**：MVP 阶段改用 filter-based 查询，Cypher 接口推迟到 Neo4j 集成后

### 2. L4 formula 多行语法 — 待定
**问题**：v2 的 formula 包含 `if/elif/变量赋值`，simpleeval 不支持多行  
**结论**：需要明确限制 formula 为单行表达式，或引入受限的多行脚本语言（如 RestrictedPython）

### 3. 三个互相矛盾的 Roadmap — 高风险
**问题**：`roadmap.md`（旧）引用 Neo4j Phase 1；`03-goals.md`（新）用 DuckDB；`ADR-004` 修正时间线  
**结论**：以 `03-goals.md` 为唯一权威，删除旧 `roadmap.md`

### 4. Services 层职责 — 文档缺失
**问题**：api→services→engine 调用链，services 层无设计文档  
**结论**：Phase 1 前需要补充 services 设计文档，明确是 Application Service 还是含业务逻辑

### 5. 跨引擎协调 — 设计缺失
**问题**：L4 RuleEngine 需要 L3 MetricEngine 的计算结果作为输入，编排机制未说明  
**结论**：需要一个 ExecutionOrchestrator 或明确由 RuleEngine 内部调用 MetricEngine

## 文档评分汇总

| 维度 | 分 | 关键问题 |
|------|---|---------|
| 愿景清晰度 | 7/10 | AI Native 路径模糊，L3"决策层"概念偏误 |
| 动机合理性 | 8/10 | 竞品遗漏 GraphRAG/LangGraph |
| 目标可达性 | 6/10 | 三版 roadmap 矛盾，P1 时间线乐观 |
| 模块设计 | 7/10 | services 层缺失，跨引擎协调未说 |
| API 设计 | 6/10 | Cypher 不可行，缺批量接口 |
| Schema 设计 | 7.5/10 | v2 四层抽象有价值，formula 语言未定 |
| 文档目录 | 5/10 | 双轨并存，未清场 |

## 亮点

1. **Schema v2 四层分离**（事实/归类/分析/业务逻辑）—— 正确的领域建模抽象
2. **ADR-004 三层复用策略**（直接复用/包装扩展/自研核心）—— 工程务实
3. **分层架构约束 + 可执行检查命令** —— AGENTS.md 执行性强
4. **动机文档的竞品盲区分析** —— 逻辑清晰

## 行动项优先级

**P0（必须，Phase 1 启动前）**
- [ ] 图查询 API 降级为 filter-based
- [ ] 明确 formula 语言规范

**P1（Phase 1 期间）**
- [ ] 清场旧文档，`development/` 合并入 `02-design/`
- [ ] 删除旧 `roadmap.md`
- [ ] 补充 services 层设计文档
- [ ] 补充跨引擎协调机制说明（ExecutionOrchestrator）

**P2（可推迟）**
- [ ] 竞品分析补充（GraphRAG/LangGraph）
- [ ] 批量规则执行 API
- [ ] 图指标缓存失效策略细化
