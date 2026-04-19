# 文档与架构收敛路线图

> **作用**: `docs/` 下唯一阶段路线图
> **最后更新**: 2026-04-19
> **使用规则**: 本页只记录阶段目标与收敛顺序，不记录细碎执行项；开放任务请看 [`TODO.md`](./TODO.md)

## 当前判断

文档体系重构和详细设计审视已全部完成。8 个模块的设计文档已从 overview 出发逐一审视重写，参考了 KAG/m_flow/Cognee/MemPalace 四个优秀开源项目。跨模块一致性验证发现 5 个严重问题待修复。

## 阶段路线

| 阶段 | 目标 | 主要输出 | 状态 |
|------|------|----------|------|
| Phase 0 | docs 目录重构 | 三层目录结构（docs/docs-baseline/docs-dev） | ✅ 完成 |
| Phase 1 | Schema 设计审视 | L1-L4 + Instance 层 + 互索引边 + 时序字段 grammar（6 份文档） | ✅ 完成 |
| Phase 2 | 存储 + 规则引擎 + Formula 审视 | KuzuDB/ChromaDB/SQLite schema + DAG 执行 + L0/L1 执行（13 份文档） | ✅ 完成 |
| Phase 3 | 查询引擎 + 提取管线审视 | Layer-R/S 检索 + Bundle Search + 三通道提取（12 份文档） | ✅ 完成 |
| Phase 4 | 服务层 + API 审视 | IngestionService 双通道 + 新路由结构（13 份文档） | ✅ 完成 |
| Phase 5 | 跨模块一致性验证 | grammar↔存储↔查询↔API 四层对齐检查 | ✅ 完成（发现 5 个严重问题） |
| Phase 6 | 一致性问题修复 | 修复跨模块一致性报告中的严重问题 | 待启动 |
| Phase 7 | 代码实现 | 按设计文档实现代码 | 待启动 |

## 审视成果统计

| 模块 | 文档数 | 审视报告 | 关键偏差 |
|------|--------|----------|----------|
| Schema | 6 | schema-review.md | 新增 Instance 层/互索引边/时序建模 grammar |
| Storage | 6 | storage-review.md | DuckDB→KuzuDB+ChromaDB+SQLite 三引擎迁移 |
| Rule Engine | 4 | rule-engine-review.md | priority→DAG 执行，规则模型一体→声明/实例分离 |
| Query Engine | 7 | query-engine-review.md | 占位符→完整 Layer-R/S 双路检索 |
| Extraction Pipeline | 5 | extraction-pipeline-review.md | 新增三通道提取管线 |
| Services | 6 | services-review.md | 22 项严重偏差，需双通道/三层检索/反馈闭环 |
| API | 7 | api-review.md | 14 路由文件→7 路由文件，130+端点→60 端点 |
| Formula | 3 | formula-review.md | 函数库实现率 19%，L0/L1 执行模型未实现 |

## 跨模块一致性问题

5 个严重问题（详见 `docs-dev/review-reports/consistency-report.md`）：

1. **S-1**: TRACE_TO 源端类型不一致（Grammar: ExecutionStepSnapshot vs KuzuDB: EntityNode）
2. **S-2**: DEFINED_IN 不支持 MetricDeclaration 源端（KuzuDB 无 MetricDeclarationNode）
3. **S-3**: API 使用旧术语 concept_type，Schema v2 使用 _fact_object
4. **S-4**: API 查询路由缺少时序查询参数（as_of、include_history）
5. **S-5**: KuzuDB 未定义 7 种时序边表

## 退出标准

当以下条件满足时，文档体系可视为完成本轮审视：

1. ✅ 所有 02-design/ 子目录状态从 `under-review` 变为 `draft`
2. ✅ 每个设计文档都有明确的"目的"和"要解决的问题"
3. ✅ 每个设计决策都有与 overview 的对齐说明
4. ⚠️ Schema grammar ↔ 存储层 schema ↔ 查询接口 ↔ API 路由四层对齐（5 个严重问题待修复）
5. ⚠️ 所有文档术语与 01-overview/05-concepts.md 一致（API 层仍有旧术语）
6. ✅ docs/ 目录下无归档文档残留
