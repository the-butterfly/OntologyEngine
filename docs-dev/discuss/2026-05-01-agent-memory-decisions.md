# Agent Memory 设计决策记录

> **date**: 2026-05-01 | **session**: Agent Memory 补充设计文档深度分析 + Phase 1-2 实施

---

## 已决议事项

### D-01: BASE_TYPE_WEIGHTS 统一

| 项目 | 内容 |
|------|------|
| **问题** | `memory-hierarchy.md` (3.0/2.5/2.0) 与 `rrf-fusion.md`/`09-agent-memory.md` (2.0/1.3/1.5) 存在两套权重值 |
| **决议** | 统一到 `memory-hierarchy.md` 的权重体系，通过 DispositionProfile 动态调整 |
| **理由** | 权重本身是基准值，实际使用时由 DispositionProfile 的7维度动态调整，基准值应取较大值以保留调整空间 |
| **代码体现** | `compute_dynamic_weights()` 使用统一基准值 3.0/2.5/2.0/2.0/1.5/1.8/1.2/1.0 |

### D-02: RRF 四路与分层漏斗的关系

| 项目 | 内容 |
|------|------|
| **问题** | `query-routing.md` 的分层漏斗与 `rrf-fusion.md` 的四路融合是串行还是并行关系 |
| **决议** | 理解 B：RRF 并行检索 + 漏斗排序 |
| **理由** | 漏斗仅决定结果展示顺序和截断，不决定检索路径。全量检索后按认知层排序更灵活 |
| **代码体现** | 待 T5/T6 实现时嵌套 |

### D-03: opinion 类型定位

| 项目 | 内容 |
|------|------|
| **问题** | opinion 主观判断置信度低，是否应放入检索漏斗顶层 |
| **决议** | 保留在 cognitive_layer=opinion 中，与 Hindsight 策略一致 |
| **理由** | Hindsight 无独立 opinion 类型（只有 world/experience fact），OE 的 opinion 作为扩展保留 |
| **代码体现** | `VALID_COGNITIVE_LAYERS` 包含 "opinion" |

### D-04: KuzuDB 索引创建限制

| 项目 | 内容 |
|------|------|
| **问题** | KuzuDB v0.x 不支持 `CREATE INDEX` 语法 |
| **决议** | 注释掉索引创建代码，待 KuzuDB 支持后启用 |
| **理由** | KuzuDB 当前版本不支持 CREATE INDEX，尝试创建会报 Parser exception |
| **代码体现** | `_ensure_schema()` 中索引创建代码已注释，`kuzudb-schema.md` 添加 P-KZ-7 原则 |

### D-05: KuzuDB numpy.int64 兼容性

| 项目 | 内容 |
|------|------|
| **问题** | KuzuDB 返回 INT64 字段为 numpy.int64，传入参数时不被 KuzuDB 识别 |
| **决议** | 在 `upsert_cognitive_node()` 中强制转换参数类型 |
| **理由** | KuzuDB Python binding 不接受 numpy 类型，需转为 Python 原生类型 |
| **代码体现** | `str()` / `int()` 包装所有参数 |

### D-06: 乐观并发控制策略

| 项目 | 内容 |
|------|------|
| **问题** | `CognitiveRepository.update_node()` 需要并发保护 |
| **决议** | 使用 history 数组长度作为版本号，支持 `expected_version` 参数 |
| **理由** | CognitiveNode 已有 history 字段，无需额外 version 字段；history 长度天然递增 |
| **代码体现** | `update_node(expected_version=...)` 参数 + `CognitiveNodeConflictError` |

---

## 待决议事项

### A-01: CO_OCCURS_WITH 调用方缺失

| 项目 | 内容 |
|------|------|
| **问题** | `entity-resolver.md` 定义了共现边创建，但未明确谁负责调用 `update_cooccurrences()` |
| **候选方案** | (A) IngestionService (B) ExtractionPipeline (C) EntityResolver 自身 |
| **建议** | 方案 C：EntityResolver 在 resolve() 完成后自动更新共现边 |

### A-02: KnowledgeFragmentNode 缺少 consolidated_at

| 项目 | 内容 |
|------|------|
| **问题** | 碎片被巩固后如何标记？依赖 CONSOLIDATED_INTO 边存在性？ |
| **候选方案** | (A) 在碎片节点添加 consolidated_at 字段 (B) 通过 CONSOLIDATED_INTO 边判断 |
| **建议** | 方案 B：通过边判断，避免碎片节点字段膨胀 |

### A-03: rule 放在 cognitive_layer=semantic 是否合理

| 项目 | 内容 |
|------|------|
| **问题** | 规则是业务逻辑定义，不是语义知识 |
| **候选方案** | (A) 保留在 semantic (B) 移到 procedure 层 |
| **建议** | 方案 A：保留在 semantic，rule 与 entity 同属"结构化知识" |

---

## 实施进度

| Phase | 任务 | 状态 | 测试 |
|-------|------|------|------|
| Phase 1 | T1: Schema DDL + T10: DispositionProfile | ✅ 完成 | 15/15 |
| Phase 2 | T2: CognitiveNode CRUD Repository | ✅ 完成 | 24/24 |
| Phase 3 | T3: ConsolidationEngine | ✅ 完成 | 18 |
| Phase 3 | T4: EntityResolver | ✅ 完成 | 19 |
| Phase 3 | T5: RRF 四路融合 | ✅ 完成 | 19 |
| Phase 4 | T6: QueryRouter | ⏳ 依赖 T5 | — |
| Phase 5 | T7: ReflectAgent | ⏳ 依赖 T2,T5 | — |
| Phase 5 | T9: Memory Lifecycle | ⏳ 依赖 T2,T3 | — |
| Phase 6 | T8: Memory API | ⏳ 依赖 T3,T6,T7 | — |

**总测试数**: 109/109 passed (截至 Phase 3 完成)

---

## Phase 3 实施决策

### D-07: KuzuDB 不支持 TYPE() 函数

| 项目 | 内容 |
|------|------|
| **问题** | Cypher `RETURN type(r)` 在 KuzuDB 中报错 "function TYPE does not exist" |
| **决议** | 使用硬编码的 edge_type 字符串替代 `type(r)` 返回值 |
| **代码体现** | `create_cognitive_edge()` 返回 `edge_type` 参数而非 `type(r)` |

### D-08: 认知边属性过滤

| 项目 | 内容 |
|------|------|
| **问题** | 不同认知边有不同的属性定义，传入不存在的属性会报 Binder exception |
| **决议** | 在 `create_cognitive_edge()` 中按 edge_type 过滤属性，只设置边表定义的属性 |
| **代码体现** | `edge_schemas` 字典定义每种边允许的属性集合 |

### D-09: EntityResolver 精确匹配评分

| 项目 | 内容 |
|------|------|
| **问题** | 三维度评分 name_sim × 0.5 最高只有 0.5，精确匹配也无法超过 0.6 重用阈值 |
| **决议** | 精确名称匹配 (name_sim == 1.0) 直接返回 1.0 分 |
| **理由** | 精确匹配不应被共现/时序维度拖低，这是 D-ER-5 "Schema identity 优先" 的自然延伸 |
