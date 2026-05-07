# Session 记录：Agent 记忆外部批判框架集成

> **Session 日期**: 2026-04-28
> **触发原因**: 阅读 lencx WeChat 文章《记忆不是蒸馏》，发现 OntologyEngine Agent 记忆设计的系统性缺口
> **处理模式**: 只读分析 + 文档更新（不执行代码变更）
> **输出**: 1 份审视报告 + 6 份设计文档更新 + 3 份元文档更新

---

## 1. 外部输入摘要

**来源**: lencx 微信公众号文章（2026），《记忆不是蒸馏》

**核心批判框架**:
1. 记忆 ≠ 蒸馏——蒸馏只是管理环节的一个操作，不是记忆本身
2. 四建模对象：User Model / Task Model / World Model / Self Model
3. 六记忆维度：content / type / confidence / source / scope / time-decay
4. 三条闭环链路：写入（边际价值判断）/ 管理（冲突+衰减+来源+权限）/ 读取（任务约束驱动）
5. 核心挑战：治理（governance）优先于容量

---

## 2. 关键发现与决策

### 决策 S-1：确认 OntologyEngine 存在"记忆=蒸馏"认知偏差

**发现**: Consolidation 引擎被过度定位为记忆的"终极目标"，将碎片归纳为 observation/entity 视为"好的记忆"。但 lencx 指出蒸馏只是归档，记忆必须保留形成结论的轨迹。

**决策**:
- 在 `09-agent-memory.md` 中新增"记忆≠蒸馏"章节，明确 Consolidation 是管理环节而非终极目标
- 在 `memory-hierarchy.md` 中新增 `consolidation_reasoning` 字段，记录 LLM 归纳时的推理摘要
- 在 `10-kb-process.md` 中将此列为根因 #5

### 决策 S-2：四建模对象必须在设计中显式表达

**发现**: OntologyEngine 当前只有 World Model（Schema L1-L4）和部分 User Model（DispositionProfile），Task Model 和 Self Model 完全缺失。

**决策**:
- 新增 `model_domain` 字段（user/task/world/self），与 `cognitive_layer` 正交
- 新增 4 种 memory_type：
  - `commitment`：Agent 对用户的承诺
  - `constraint`：不可违反的环境边界
  - `self_experience`：Agent 工具调用经验
  - `task_state`：任务快照/方案历史/artifact 版本
- 在 `09-agent-memory.md` 中新增"四建模对象×四认知层正交矩阵"章节

### 决策 S-3：六记忆维度补齐 scope 和 source_trust_tier

**发现**: content/confidence 已覆盖，type/source/time-decay 部分覆盖，scope 完全缺失。

**决策**:
- 新增 `source_trust_tier` 字段：user_declared > behavior_inferred > environment_observed > agent_generated
- 新增 `scope` 字段：JSON 格式 `{type, ref_id, window}`
- 新增 `last_confirmed_at` 字段：被后续证据确认的时间，用于替代/补充 Ebbinghaus 衰减
- 在 `kuzudb-schema.md` 中更新 DDL 和索引

### 决策 S-4：三条闭环链路需补全写入控制和读取驱动

**发现**: 写入是"来了就存"，读取是"RAG 式语义召回"，都缺少 lencx 强调的"边际价值判断"和"任务约束驱动"。

**决策**:
- 新增 `DeduplicationGate` 引擎：写入前去重 + 边际价值判断 + 矛盾前置检测
- 新增 `QueryUnderstandingLayer`：任务约束提取 → 驱动检索策略
- 新增 `ArbitrationEngine`：证据权重自动裁决矛盾
- 在 `10-kb-process.md` 演进路径中新增 Phase 2e（治理层完善）

### 决策 S-5：治理成熟度不足是当前最大风险

**发现**: 权限治理几乎空白，自动裁决缺失，策略性遗忘未实现。

**决策**:
- 新增 `PermissionService`：用户查看/编辑/删除记忆权限
- 策略性遗忘：superseded/rejected 触发加速遗忘
- 在 `ROADMAP.md` 中新增 Phase 6b（Agent 记忆外部批判修复）

---

## 3. 文档变更清单

| 文档 | 变更类型 | 关键变更 |
|------|---------|---------|
| `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` | 新增 | 完整外部批判框架审视报告（~20KB） |
| `docs/01-overview/10-kb-process.md` | 更新 | 新增 8 个 GAP（GAP-11~GAP-18）、四建模对象矩阵、DeduplicationGate、QueryUnderstandingLayer、Phase 2e |
| `docs/01-overview/09-agent-memory.md` | 更新 | 新增记忆≠蒸馏章节、4 种 memory_type、三条闭环链路、四建模对象矩阵、六维度覆盖检查 |
| `docs/02-design/agent-memory/README.md` | 更新 | 新增 D-AM-8~D-AM-10 决策、3 种新边、3 个新引擎、PermissionService、Phase 2e |
| `docs/02-design/agent-memory/memory-hierarchy.md` | 更新 | CognitiveNode 新增 5 字段、4 种新 memory_type、3 种新边类型、ChromaDB 元数据扩展 |
| `docs/02-design/storage/kuzudb-schema.md` | 更新 | CognitiveNode DDL 新增 5 字段、3 种新 REL TABLE、MERGE 语句更新、对齐总结扩展 |
| `docs/STATUS.md` | 更新 | 新增 discuss 报告引用、Agent 记忆热点更新、治理层设计待完善标记 |
| `docs/TODO.md` | 更新 | 新增 4 项 P1/P2 backlog（治理层设计、Schema 扩展、Self/Task Model、来源可信层级、策略性遗忘） |
| `docs/ROADMAP.md` | 更新 | 新增 Phase 6b、外部批判审视摘要、退出标准 #7 |

---

## 4. 新增 GAP 汇总

| GAP | 领域 | 严重程度 | 解决阶段 |
|-----|------|---------|---------|
| GAP-11 | 四建模对象缺失（Task/Self） | 高 | Phase 2e |
| GAP-12 | 六记忆维度缺失（scope/source_trust_tier/last_confirmed_at） | 高 | Phase 1 |
| GAP-13 | 写入控制缺失（去重门/边际价值） | 中 | Phase 2e |
| GAP-14 | 读取驱动偏差（无任务约束驱动） | 高 | Phase 2e |
| GAP-15 | 矛盾裁决缺失（无自动裁决引擎） | 中 | Phase 3 |
| GAP-16 | 权限治理空白 | 高 | Phase 3 |
| GAP-17 | 轨迹保留缺失（无推理轨迹） | 中 | Phase 2 |
| GAP-18 | 记忆类型缺失（commitment/constraint/self_experience/task_state） | 中 | Phase 1 |

---

## 5. 待后续 Session 处理的事项

1. **memory-api.md 更新**: 新增 API（oe_list_my_memories, oe_correct_memory, oe_record_commitment, oe_recall_with_constraints）尚未写入正式 API 文档
2. **memory-lifecycle.md 更新**: DeduplicationGate、ArbitrationEngine、策略性遗忘的机制尚未写入生命周期文档
3. **Self Model 详细设计**: 当前仅在 09-agent-memory.md 中概念性提及，需独立设计文档
4. **Task Model 详细设计**: 同上
5. **QueryUnderstandingLayer 详细设计**: 当前仅在 10-kb-process.md 中概念性描述
6. **代码对齐**: 所有文档变更需在代码实现时逐项核验

---

## 6. 参考索引

- 外部批判框架完整分析: `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md`
- 五报告对照: `discuss/2026-04-28-five-reports-vs-source-docs-gap-analysis.md`
- SOTA 审视: `discuss/2026-04-27-agent-memory-design-analysis.md`
