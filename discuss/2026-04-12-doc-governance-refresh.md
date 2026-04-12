# 2026-04-12 文档治理刷新记录

## 背景

本轮整理的核心目标不是继续增加更多设计内容，而是先解决 `docs/` 的职责混叠、入口失真、状态分散、Schema grammar 漂移和文档重复维护问题。

## 本次决策

1. 将 `docs/README.md` 收敛为**单一入口**，只保留导航、分层说明和 SoT 索引
2. 新增 `docs/STATUS.md` 作为**唯一状态页**
3. 新增 `docs/ROADMAP.md` 作为**唯一路线图**
4. 将 `docs/TODO.md` 重构为**唯一 backlog**，只保留开放事项
5. 新增 `docs/04-migration-and-gap/README.md`，统一管理当前态 → 目标态 → 实施层的冲突与迁移说明
6. 为 `01-overview`、`02-design`、`05-schema-v2`、`06-module-detailed-design` 增加目录级 `README.md`
7. 新增 `docs/05-schema-v2/09-canonical-schema-spec.md` 作为 **Schema v2 根级 grammar 的单一事实源**
8. 在高风险旧文档中加入 **[关键设计点]** / **[待扩展]** / **[待核对代码]** 标记
9. 将文档治理约定同步进 `CLAUDE.md` 与 `AGENTS.md`

## 本次直接修改的关键文件

- `docs/README.md`
- `docs/STATUS.md`
- `docs/ROADMAP.md`
- `docs/TODO.md`
- `docs/04-migration-and-gap/README.md`
- `docs/01-overview/README.md`
- `docs/02-design/README.md`
- `docs/05-schema-v2/README.md`
- `docs/05-schema-v2/09-canonical-schema-spec.md`
- `docs/06-module-detailed-design/README.md`
- `docs/05-schema-v2/05-complete-example.md`
- `docs/06-module-detailed-design/07-expression-engine.md`
- `docs/06-module-detailed-design/10-api-layer.md`
- `docs/01-overview/05-concepts.md`
- `CLAUDE.md`
- `AGENTS.md`

## 后续建议

- 优先同步 `05-schema-v2/05-complete-example.md` 到 canonical grammar
- 补 current API / target API 的明确映射说明
- 继续核对 Formula / Expression / API 相关设计与当前代码的差异
