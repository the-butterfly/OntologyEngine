# P0-P2 审查改进计划实施记录

> **date**: 2026-05-17
> **source**: docs/plans/2026-05-16-post-p2-review-improvement.md
> **status**: completed

## 概要

两轮代码审查共 31 项问题（7 P0 + 12 P1 + 12 P2），按 6 个 Sprint 全部实施完成。

## 关键决策

### Sprint 1: 安全 + 数据完整性

| 决策 | 理由 |
|------|------|
| `rule_eval.py` 保留内部 `eval()` 但先做 AST 验证 | 完全自写求值器复杂度高且易出错；AST 白名单验证已足够防止代码注入 |
| `rule_eval.py` 新增 `ast.Tuple/List/Set` 支持 | `BR_R002` 规则使用 `source in ('征信报告', '法院判决')` 语法，原实现不支持容器节点 |
| `BR_R007` 的 `conflicting_domains` 变量不在白名单中 | 标记为已知问题，需后续决定是否加入白名单或修改规则 |
| FTS5 BM25 归一化公式从 `(s-min)/range` 改为 `(max-s)/range` | SQLite FTS5 bm25() 返回负值，更负=更相关。原公式给最相关分配 0.0，与直觉相反 |

### Sprint 2: 架构合规

| 决策 | 理由 |
|------|------|
| `LegacyStorageAdapter` 包装旧接口而非直接迁移 | 最小侵入性，现有 `CognitiveStorageBackend` 实现无需修改 |
| `StorageInterface` 新增 7 个方法（带默认 `raise NotImplementedError`） | 不破坏现有子类，同时让 Repository 能统一调用 |
| `transition_belief` 重构为 `get_node + 修改 + save_node` | 避免新增方法，用已有接口组合实现 |
| SQLite `threading.Lock` + `asyncio.to_thread()` 闭包模式 | 锁获取和 DB 操作必须在同一线程，否则死锁 |
| 测试迁移到 `pytest-asyncio` | Python 3.10+ 弃用 `asyncio.get_event_loop()` |

### Sprint 3: 上帝对象拆分

| 决策 | 理由 |
|------|------|
| MemoryAPI 使用门面模式（facade） | MCP 工具和外部调用者无需修改，公共 API 完全不变 |
| RecallService (333行) 和 ReflectOrchestrator (331行) 略超 300 行目标 | recall/reflect 逻辑本身复杂度高，进一步拆分引入不必要间接层 |
| `KuzuGraphStore` 添加适配方法 | Repository 调用的方法名与 KuzuGraphStore 实际方法名不匹配，添加委托方法解决 |
| ConsumptionService (720行) 仍超 300 行目标 | 拆分了 3 个子服务但原服务仍保留查询/编排方法，需后续进一步瘦身 |
| deprecated 路由添加 RFC 8594 Sunset header | 设置日落日期 2026-06-30，不立即删除路由 |

### Sprint 4: DI + 前端统一

| 决策 | 理由 |
|------|------|
| simulation.py 辅助函数保留直接调用 | 3 处 `get_space_service()` 在非路由处理器的辅助函数中，不适合 Depends 注入 |
| `spaceStore.simulationResult` 使用 `ExecutionResult` 而非 `SimulationResult` | `spaceApi.executeSimulate()` 实际返回 `ExecutionResult`，用 `SimulationResult` 是类型谎言 |
| 前端 `tsc --noEmit` 仍有 ~35 个预存错误 | 本次改动未引入新错误，预存错误需后续专项修复 |

### Sprint 5: 质量提升

| 决策 | 理由 |
|------|------|
| `VALID_MEMORY_TYPES` 新增 `"relation"` 和 `"metrics"` | 这两个类型在 `infer_memory_type()` 等函数中已被使用，是合法 memory type |
| `_rrf_fuse` 和 `as_of` 传递已在先前提交中修复 | 无需额外修改 |
| ChromaDB `_CHROMADB_MISSING_FIELDS` 显式记录 25 个无法存入的字段 | 透明化数据丢失范围，便于后续审计 |
| `CognitiveStorage.get_node()` 添加 SQLite 回退补充 | ChromaDB 节点不完整时，尝试从 SQLite 获取完整数据 |

### Sprint 6: 评估体系

| 决策 | 理由 |
|------|------|
| `search_cognitive()` 双路径（有 storage 委托 RRF，无 storage 回退子串匹配） | 向后兼容，现有调用方无需修改 |
| 14 个 eval 文件从 `EvalReport` 迁移到 `AcptReport` | 统一评估框架，消除双轨制 |
| P99 修复使用 `math.ceil` 而非 `int` 截断 | `int()` 等同 floor，会低估百分位索引 |

## 验收汇总

| Sprint | 测试数 | 核心验收 |
|--------|--------|----------|
| S1 | 108 passed | eval() 安全封装, batch_save ID 映射, FTS5 排序, delete_memory |
| S2 | 510 passed | 0 个 type:ignore[union-attr], 0 个跨层导入, threading.Lock, 0 个 get_event_loop |
| S3 | 1200 passed | MemoryAPI 323行, 子服务 < 333行, deprecated 路由有 Sunset header |
| S4 | 1203 passed | DI 全部 Depends(), FeedbackService 注册, MemoryService close 修复 |
| S5 | 1269 passed | _normalize_element_type 1处定义, to_space_layers_dict 78行, 中文推断, ChromaDB 字段扩展 |
| S6 | 1279 passed | search_cognitive RRF 融合, AcptReport 统一, P99 修复, 验证脚本增强 |

## 未完成项 / 后续工作

1. **ConsumptionService 仍 720 行** — 需进一步将查询方法下沉到子服务
2. **management.py 1220 行 / semantic_spaces.py 1359 行** — deprecated 路由文件，计划 2026-06-30 后删除
3. **BR_R007 `conflicting_domains` 变量** — 不在 `ALLOWED_VARIABLES` 白名单中，需决定处理方式
4. **前端 tsc ~35 个预存错误** — 需专项修复
5. **ChromaDB 25 个字段仍无法存入** — 需评估是否需要扩展存储策略
