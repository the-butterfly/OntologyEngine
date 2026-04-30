# 多文档设计审查典型问题经验

> **日期**: 2026-04-30
> **场景**: 对 OntologyEngine 知识库/记忆库设计文档（overview + 02-design + docs-ui）进行系统性审查，涉及10+文档、120+硬编码值、7个设计文档重写

---

## 1. 同一概念多套术语

**现象**：不同层文档对同一概念使用不同术语，读者无法确认是否指同一事物。

**样例**：
- overview层用 `MemoryUnit`，design层用 `CognitiveNode`
- overview层用 `MAPPED_TO` 边，design层已消除此边
- overview层用 Formation/Evolution/Retrieval，design层用 Build/Govern/Consume

**对策**：概念层文档在术语首次出现时标注 design 层对应术语，如 `MemoryUnit（设计层称 CognitiveNode）`。概念演进后，旧术语保留但加 `[已演进]` 标注。

---

## 2. 同一阈值多处重复且不一致

**现象**：同一数值在多个文档中重复定义，且值不同。

**样例**：
- `abstraction_preference` 触发阈值：memory-hierarchy 写 `>0.7`，10-kb-process 写 `>0.8`
- `strength` 遗忘阈值 (0.3/0.2/0.1/0.01) 在3个文档重复
- 自动晋升条件：ingestion-service 写 `confidence>0.9 + proof≥3`，temporal-modeling 只写 `confidence>0.9`

**对策**：建立参数注册表（单一事实源），其他文档引用而非重复。引用格式：`见 memory-lifecycle §5 遗忘阈值`。

---

## 3. 新旧设计同文档并存导致自相矛盾

**现象**：文档迭代时，旧设计未删除，新设计追加在后面，同一文档内逻辑矛盾。

**样例**：
- ingestion-service.md 早期写"矛盾→阻止写入"，后期追加"矛盾→分流不阻塞"，两段同时存在
- 09-agent-memory.md 架构图展示5个操作，正文主张3个操作

**对策**：每次设计变更必须全文搜索旧描述并替换，不留"历史层叠"。可用 git blame 追踪变更，但文档正文只保留当前设计。

---

## 4. 参数声明"不影响"但实际影响

**现象**：设计文档声明某参数不影响某环节，但深入分析后发现确实影响。

**样例**：
- `empathy` 声明"不影响检索，只影响交互风格"→实际影响回答生成策略（模糊查询推断、降级时替代结果）
- `risk_tolerance` 声明"不影响检索"→实际影响 min_confidence 阈值（低→0.8，高→0.3）

**对策**：对每个参数做"影响链分析"——从参数值出发，追踪到所有受影响的环节，用表格列出。不要凭直觉声明"不影响"。

---

## 5. API端点跨文档不一致

**现象**：API设计文档和UI文档使用不同的路径模式、参数命名风格、HTTP方法。

**样例**：
- memory-api.md: `/v1/spaces/{space_id}/memory/*` (snake_case, POST recall)
- docs-ui: `/v1/management/{spaceId}/knowledge/*` (camelCase, GET recall)

**对策**：在 `docs/02-design/api/` 下定义统一URL规范，所有文档引用此规范。路径参数风格、资源命名、HTTP方法选择必须在规范中明确。

---

## 6. 两套状态机关系未定义

**现象**：不同文档定义了不同粒度的状态机，但两者之间的映射关系未说明。

**样例**：
- 10-kb-process.md: 五阶段状态机 (INGESTED/EXTRACTED/ALIGNED/ACTIVE/SUPERSEDED)
- design层: belief_status (accepted/pending_review/rejected/superseded)
- 两者都有 SUPERSEDED 状态，但 ACTIVE ≠ accepted 的关系未说明

**对策**：显式定义两套状态机的映射表。标注每套状态机的适用范围（如"五阶段用于Fragment提取流程，belief_status用于CognitiveNode治理流程"）。

---

## 7. 权重体系分散无注册表

**现象**：类型权重、RRF权重、边权重、alignment权重分散在不同文档，缺乏统一视图。

**样例**：
- BASE_TYPE_WEIGHTS 在 memory-hierarchy.md
- RRF权重在 query-routing.md
- alignment_score 权重在 10-kb-process.md
- 遗忘公式权重在 memory-lifecycle.md

**对策**：建立参数注册表文档，按功能域（retrieval/lifecycle/governance/cost）分组，每个参数标注单一事实源、可配置性、作用域。

---

## 8. DDL默认值与YAML模型重复

**现象**：CognitiveNode的默认值在YAML模型和DDL中各写一遍，存在漂移风险。

**样例**：
- memory-hierarchy.md YAML: `confidence: float = 1.0`
- kuzudb-schema.md DDL: `confidence DOUBLE DEFAULT 1.0`

**对策**：DDL是存储层单一事实源，YAML模型引用DDL而非重复定义。格式：`confidence: float  # DEFAULT 1.0, 见 kuzudb-schema.md`。

---

## 9. 场景强制覆盖值缺乏推导

**现象**：场景覆盖值（如审计场景 evidence_demand=1.0）直接硬编码，未说明为什么是这个值。

**样例**：
- 审计场景: `evidence_demand=1.0, skepticism=0.9, thoroughness=0.8`
- 快速回答: `abstraction_preference=0.8, thoroughness=0.3`

**对策**：每个场景覆盖值附一行注释说明取值依据。如 `evidence_demand=1.0  # 审计必须全层检索，不允许任何证据遗漏`。

---

## 10. 概念层与设计层的演进不同步

**现象**：design层文档重写后，overview层文档未同步更新，导致新读者从overview入门时获得过时信息。

**样例**：
- 09-agent-memory.md 仍描述 MAPPED_TO 边和 MemoryUnit，design层已改为 CognitiveNode
- 09-agent-memory.md 架构图仍展示5操作，design层已确定为3操作

**对策**：每次design层重大变更后，在overview层文档头部增加演进说明区块：
```
> **[设计演进]** 本文档描述的 MemoryUnit/MAPPED_TO 已演进为 CognitiveNode 统一模型。
> 详见 memory-hierarchy.md。
```
