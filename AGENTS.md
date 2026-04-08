# AGENTS.md

## 核心约束

| # | 约束 | 违反后果 | 检查方式 |
|---|------|----------|----------|
| 1 | **本地存储优先** | 禁止直接引入外部数据库 | `grep -r "from neo4j\|from redis\|import psycopg" ontology_engine/ --include="*.py" \| grep -v "adapters/"` |
| 2 | **API 边界封闭** | 禁止跨层直接调用 | `grep -r "sqlite3\|faiss\|redis" ontology_engine/{api,services,engine}/ --include="*.py"` |
| 3 | **测试先行** | 实现前必须有测试用例 | `ls tests/unit/$(dirname $file)/test_$(basename $file)` |
| 4 | **文档同步** | 代码变更必须同步文档 | PR 描述检查 |
| 5 | **边界外扩需审批** | 新 API 需先写设计文档 | `docs/api/*.md` 存在性检查 |

## 模块边界

```
api/           → services/  (禁止直接调 storage/, engine/)
services/      → engine/    (禁止直接调 storage/)
engine/        → storage/base.py  (禁止直接调 local/, adapters/)
storage/local/ → 仅实现 base.py 接口 (禁止依赖上层)
```

## 开发流程

```
任务分配
  ↓
边界检查 ──▶ 超出? ──是──▶ API 设计 ──▶ 评审通过
  │              否
  ↓
测试用例编写 [subagent: 详见 development/testing.md]
  ↓
代码实现
  ↓
UT 验收 [subagent: 详见 development/testing.md]
  ↓
文档更新
```

## 必备文档

| 场景 | 查阅文档 |
|------|----------|
| 编写测试用例 | `docs/development/testing.md` |
| 设计新 API | `docs/development/api-design.md` |
| 添加存储适配器 | `docs/development/storage-adapter.md` |
| 添加算子 | `docs/development/operator.md` |
| 代码规范 | `docs/development/code-style.md` |
| 沟通风格 | `docs/development/communication.md` |
| Session退出后记录关键沟通内容 | `discuss/*.md` |


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


## HOOK
AT LAST: DO THINK DEEPLY. 
AND BACKUP ALL KEY DESICIONS in session TO `discuss` foler.
