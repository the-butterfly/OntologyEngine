# Project Agent Guide

## 核心约束

| # | 约束 | 违反后果 | 检查方式 |
|---|------|----------|----------|
| 1 | **本地存储优先** | 禁止直接引入外部数据库 | `grep -r "from neo4j\|from redis\|import psycopg" ontology_engine/ --include="*.py" \| grep -v "adapters/"` |
| 2 | **API 边界封闭** | 禁止跨层直接调用 | `grep -r "sqlite3\|faiss\|redis" ontology_engine/{api,services,engine}/ --include="*.py"` |
| 3 | **测试先行** | 实现前必须有测试用例 | `ls tests/unit/$(dirname $file)/test_$(basename $file)` |
| 4 | **文档同步** | 代码变更必须同步文档 | PR / Session 检查 |
| 5 | **边界外扩需审批** | 新 API 需先写设计文档 | `docs/02-design/api/*.md` 或相关设计文档存在性检查 |
| 6 | **RFC 先行** | 关键增量的实施内容实现前必须先冻结 RFC | `docs/03-rfc/*.md` |

## 模块边界

```text
api/           → services/  (禁止直接调 storage/, engine/)
services/      → engine/    (禁止直接调 storage/)
engine/        → storage/base.py  (禁止直接调 local/, adapters/)
storage/local/ → 仅实现 base.py 接口 (禁止依赖上层)

# Phase 2 扩展
mcp/           → services/ + storage/  (MCP Server 调用现有 service 层)
```

## 开发流程

```text
任务分配
  ↓
边界检查 ──▶ 超出? ──是──▶ API / 架构设计 ──▶ 评审通过
  │              否
  ↓
测试用例编写 [详见 development/testing.md]
  ↓
代码实现
  ↓
UT / 设计一致性验收
  ↓
文档更新
  ↓
Session 关键决策记录到 discuss/
```

## 文档体系治理

### 文档三层结构

```
docs/                   ← 活跃文档（唯一事实源）
  ├── 01-overview/     ← 愿景、目标、术语、边界（source_of_truth）
  ├── 02-design/       ← 模块详细设计（draft/under-review）
  ├── 03-rfc/          ← RFC 提案
  ├── 04-adr/          ← 架构决策记录
  └── [STATUS|ROADMAP|TODO].md

docs-baseline/          ← 历史归档（仅供参考，不可作为设计依据）
  ├── 00-current-baseline/  ← 重写前实现基线
  ├── 02-design/            ← 废弃的设计文档（DuckDB/旧API）
  ├── 05-schema-v2/        ← Schema v2 目标架构（已迁移）
  └── 06-module-detailed-design/  ← 旧模块详细设计

docs-dev/              ← 开发过程文档
  ├── 03-rfc/          ← RFC 开发版本
  ├── 04-migration-and-gap/  ← 当前态→目标态映射
  ├── discuss/         ← Session 关键决策记录
  └── review-reports/  ← 审视报告
```

### 文档角色分层

| 层级 | 文件 / 目录 | 作用 |
|------|-------------|------|
| 入口层 | `docs/README.md` | 文档地图，只做导航和分层说明 |
| 状态层 | `docs/STATUS.md` | 文档状态、过期情况、热点风险的唯一状态页 |
| 路线层 | `docs/ROADMAP.md` | 阶段目标与收敛顺序 |
| Backlog 层 | `docs/TODO.md` | 只保留进行中 / 未完成事项 |
| 认知层 | `docs/01-overview/` | 愿景、目标、术语、边界（accepted 状态） |
| 设计层 | `docs/02-design/` | 各模块详细设计（source_of_truth） |
| Phase 2 层 | `docs/03-rfc/` | Phase 2 改进 RFC |
| 规范层 | `docs/development/` | 开发规范、测试、扩展指南 |

### 单一事实源（SoT）约定

| 主题 | 唯一入口 |
|------|----------|
| 文档有效性 / 是否过期 | `docs/STATUS.md` |
| 阶段路线与优先级 | `docs/ROADMAP.md` |
| 开放任务 / backlog | `docs/TODO.md` |
| 当前态 → 目标态的映射 | `docs-dev/04-migration-and-gap/README.md` |
| Schema v2 根级 grammar | `docs/02-design/schema/01-schema-spec.md` |
| Phase 2 路线与 RFC 状态 | `docs/03-rfc/RFC-010-phase2-roadmap.md` |

### 文档写作硬规则

1. **同一主题只能有一个主规范**；其他文档必须链接引用，不得重复维护完整定义
2. **当前态 / 目标态 / 实施态必须分开写**，禁止混在同一段叙事里
3. `README.md` 不再维护任务明细、端点数量、服务数量等易漂移内容
4. `TODO.md` 只保留未完成事项；完成项移出，不保留在 backlog 中
5. 若内容尚未与代码逐项核验，必须显式标注 **[待核对代码]**
6. 若内容已确定方向但尚未冻结细节，必须显式标注 **[待扩展]**
7. 若某文档是当前主题唯一规范，必须显式标注 **[单一事实源]**
8. 示例代码、伪代码、接口草图若非当前实现，不得写成“已实现”口吻
9. 设计文档新增或重写时，优先补充以下元数据：`status`、`phase`、`source_of_truth`、`last_verified`、`verified_against`
10. 固定数字（端点数、服务数、模块数）若无法稳定维护，应改成链接到规范，不要作为长期真相写死

### 标注约定

- **[单一事实源]**: 当前主题唯一规范入口
- **[关键设计点]**: 已收敛、实现或评审时必须优先关注的内容
- **[待扩展]**: 已确认方向但仍待补细节
- **[待核对代码]**: 尚未与当前代码逐段核验，不能直接当实现真相
- **[已过期入口]**: 历史入口或旧叙述，仅保留兼容阅读

### 文档更新触发器

出现以下情况时，必须同步更新文档：

- **代码结构变更**: 更新对应设计文档（docs/02-design/），并检查 `STATUS.md`
- **目标设计变更**: 更新设计文档，并检查 `ROADMAP.md` 与迁移层文档
- **冲突被发现**: 先更新 `docs-dev/04-migration-and-gap/README.md`，再决定是否重写专题文档
- **开放任务变化**: 更新 `docs/TODO.md`
- **文档入口变化**: 更新 `docs/README.md`
- **关键结论形成**: 记录到 `docs-dev/discuss/*.md`

### 文档迁移规则

1. **废弃文档归档**: 当设计文档被重写或废弃时，将其移动到 `docs-baseline/` 对应目录
2. **目标态迁移**: `docs/05-schema-v2/` → `docs-baseline/05-schema-v2/`，Schema v2 规范已归档
3. **旧模块设计迁移**: `docs/06-module-detailed-design/` → `docs-baseline/06-module-detailed-design/`
4. **迁移层分离**: `docs/04-migration-and-gap/` → `docs-dev/04-migration-and-gap/`
5. **归档文档标注**: 移动到 docs-baseline 的文档，在文件头添加 `[已过期入口]` 标注

## 必备文档

| 场景 | 查阅文档 |
|------|----------|
| 文档状态判断 | `docs/STATUS.md` |
| 架构阶段路线 | `docs/ROADMAP.md` |
| 编写测试用例 | `docs-dev/development/testing.md` |
| 设计新 API | `docs/02-design/api/README.md` |
| 代码规范 | `docs-dev/development/code-style.md` |
| 沟通风格 | `docs-dev/development/communication.md` |
| 当前态 / 目标态映射 | `docs-dev/04-migration-and-gap/README.md` |
| 过程中的关键RFC文档(已实施&目标) | `docs-dev/03-rfc/` `docs/03-rfc/`|
| Session 退出后记录关键沟通内容 | `docs-dev/discuss/*.md` |

## 质量门禁

```bash
# 提交前必跑
mypy ontology_engine/ --strict
ruff check ontology_engine/
pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing
```

## 快速检查

| 检查项 | 命令 |
|--------|------|
| 是否跨层调用 | `grep -r "from.*storage.*import\|from.*engine.*import" ontology_engine/api/ --include="*.py"` |
| 是否直接依赖外部存储 | `grep -r "neo4j\|redis\|psycopg" ontology_engine/ --include="*.py" \| grep -v "adapters/"` |
| 测试是否存在 | `find tests/unit -name "test_*.py" \| wc -l` |
| 文档入口是否同步 | `ls docs/{README.md,STATUS.md,ROADMAP.md,TODO.md}` |

## HOOK

- DO THINK DEEPLY.
- BACKUP ALL KEY DECISIONS IN SESSION TO `discuss/`.
- WHEN DOC GOVERNANCE CHANGES, SYNC `CLAUDE.md` AND `AGENTS.md` TOGETHER.
