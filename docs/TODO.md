# 实施 Backlog

> **作用**: `docs/` 下唯一开放事项列表
> **最后更新**: 2026-04-29
> **说明**: 本文件只保留进行中 / 未完成事项；文档状态看 [`STATUS.md`](./STATUS.md)，阶段路线看 [`ROADMAP.md`](./ROADMAP.md)

## Now

| 优先级 | 事项                                    | 关联文档                                            | 备注                                                |
| --- | ------------------------------------- | ----------------------------------------------- | ------------------------------------------------- |
| P0  | 修复跨模块一致性严重问题 S-1\~S-5                 | `docs-dev/review-reports/consistency-report.md` | TRACE\_TO 源端类型、DEFINED\_IN 源端、API 旧术语、时序查询参数、时序边表 |
| P0  | 规则模型双分离实施                              | `docs-dev/03-rfc/RFC-018-rule-model-dual-separation.md` | RFC-018 draft，待评审后实施 |
| P0  | Step.action 结构化实施                         | `docs-dev/03-rfc/RFC-019-step-action-structization.md` | RFC-019 draft，待 P0-3 完成后实施 |
| P1  | 按 Schema v2 设计实现代码                    | `02-design/schema/`                             | Instance 层 + 互索引边 + 时序建模                          |
| P1  | 按 Storage 设计实现 KuzuDB+ChromaDB+SQLite | `02-design/storage/`                            | 三引擎迁移                                             |
| P1  | 按 Rule Engine 设计实现 DAG 执行             | `02-design/rule-engine/`                        | DAGBuilder + 并行执行 + 回滚                            |
| P1  | 按 Query Engine 设计实现 Layer-R/S 检索      | `02-design/query-engine/`                       | Bundle Search + RRF 融合                            |
| P1  | 按 Extraction Pipeline 设计实现三通道提取       | `02-design/extraction-pipeline/`                | AST + LLM + SHA256 缓存                             |

## Next

| 优先级 | 事项                                      | 关联文档                                                 | 备注              |
| --- | --------------------------------------- | ---------------------------------------------------- | --------------- |
| P2  | 按 Services 设计实现双通道 IngestionService     | `02-design/services/`                                | 快速通道+慢速通道       |
| P2  | 按 API 设计重构路由                            | `02-design/api/`                                     | 新路由结构+301 兼容层   |
| P2  | 按 Formula 设计实现 L0/L1 执行模型               | `02-design/formula/`                                 | 函数库补全（当前 19%）   |
| P2  | LLMJudgeOperator.\_call\_llm() 接入实际 LLM | `ontology_engine/engine/rule/operators/llm_judge.py` | 当前为 placeholder |

## 使用规则

1. 完成项从本文件移除，不在此保留历史完成记录
2. 本文件不再维护端点数、服务数、模块数等容易漂移的数据
3. 若事项属于"判断文档是否过期"，请更新 [`STATUS.md`](./STATUS.md)
4. 若事项属于"阶段目标变化"，请更新 [`ROADMAP.md`](./ROADMAP.md)
5. 若事项属于"当前态与目标态不一致"，先记录到 `docs-dev/04-migration-and-gap/`

