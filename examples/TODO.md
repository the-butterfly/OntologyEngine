# Examples - 遗留问题与待办

本文档记录 examples 评估体系中的已知问题、临时方案和待办事项。

---

## P0: 系统缺陷（影响评估准确性）

### 1. `CLIRunner.remember()` 参数静默丢弃

**状态**：已知，暂不修复  
**影响**：`model_domain`、`source_trust_tier` 参数传入 CLIRunner 后未传给 MemoryAPI  
**位置**：[cli_runner.py](agent_memory/_lib/cli_runner.py#L79-L95)  
**说明**：CLIRunner.remember() 方法签名接受 `model_domain`、`source_trust_tier` 参数，但调用 `self._api.remember()` 时未传递。MemoryAPI.remember() 的 `RememberRequest` 也缺少这些字段。  
**影响范围**：所有旧评估脚本中涉及 domain/trust 测试的场景  
**临时方案**：保持参数丢弃，不阻塞当前测试  
**修复方向**：需要在 MemoryAPI.remember() 的参数链（RememberRequest → _remember → ingestion）中逐层添加 domain/trust 传递

### 2. A-06 置信度过滤不生效

**状态**：部分修复，仍不生效  
**修复内容**：已在 `_recall()` 添加 min_confidence 过滤逻辑 (L654-655)，ingestion service 添加 confidence 参数透传  
**影响**：recall(min_confidence=0.5) 仍返回 confidence=0.3 的结果  
**位置**：[11_acpt_retrieval/run_eval.py](agent_memory/11_acpt_retrieval/run_eval.py#L269-L312)  
**分析**：过滤逻辑已实现但 RRF 融合层可能在 confidence 值上有覆盖；需排查 get_node 返回的 confidence 值  
**当前表现**：A-06 得分 0.50

### 3. A-07 证据链展开 ✅ 已修复 (2026-05-15)

**状态**：已修复  
**修复内容**：`_recall()` 添加三层证据 fallback：Router.expand_evidence → source_fragment_ids → edge 追溯  
**当前表现**：A-07 得分 1.00（has_evidence=True, evidence_depth=3）  
**位置**：[11_acpt_retrieval/run_eval.py](agent_memory/11_acpt_retrieval/run_eval.py#L315-L372)  
**说明**：evidence 展开逻辑可能未在 RRF 融合阶段正确注入，或 fragment 之间的 evidence 边未建立  
**当前表现**：A-07 得分 0.50（has_evidence=True, evidence_non_empty=False）

### 4. A-08 私有记忆隔离不生效

**状态**：部分修复，仍不生效  
**修复内容**：`_recall()` 添加 user_id visibility 过滤 (L663-675)，ingestion service 添加 visibility 参数透传  
**原因分析**：issue 可能出在 RRF 融合层未按 user_id 过滤，或在 `_recall` 的 else 分支中检索结果未包含 user_id/visibility 信息  
**当前表现**：A-08 得分 0.50（alice_leak=True）

### 5. B-06 `approve_memory` 与 ingestion pipeline 不兼容 ✅ 已修复 (2026-05-15)

**状态**：已修复  
**修复内容**：ingestion service `ingest()` 添加 `belief_status` 参数并透传到 `_make_fragment_node` 和 `_make_cognitive_node` 调用；`memory_api._remember()` 传递 `belief_status=req.belief_status`  
**当前表现**：02-T5 approve 通过，B-06 has_pending=True

---

## 2026-05-15 修复记录

### 已修复 P0 问题

| # | 问题 | 修复方案 | 验证 |
|---|------|----------|------|
| P0-1 | LLM Consolidation 序列化错误 | `_build_consolidation_adapter()` 桥接 Fragment→dict 序列化 | 03 consolidation LLM calls now succeed |
| P0-2 | DeduplicationGate 不生效 | content-hash fallback (SHA256) 在无 embedding 时使用 | 01-T2 dedup=True |
| P0-3 | MemoryAPI 缺少 list_my/record_commitment/compile | 新增 5 个方法到 MemoryAPI | 06 3/8→7/8, 07 3/8→7/8 |
| P0-4 | 证据链为空 | 三层 evidence 展开 fallback | A-07 0.50→1.00 |
| P0-5 | approve_memory 状态限制 | belief_status 透传 ingestion pipeline | 02-T5 通过 |

---

## P1: 评估框架改进

### 6. 旧评估脚本（01-10）需迁移到新框架

**状态**：待规划  
**影响**：旧脚本使用 `EvalReport` + `_ok()` 二元评估，约 60% 测试缺乏区分度  
**位置**：`01_ingestion_pipeline/` ~ `10_contradiction_fix_eval/`  
**迁移计划**：
- Phase 1（已完成）：新建 11_acpt_retrieval（替代旧 retrieval 测试）
- Phase 1（已完成）：新建 12_acpt_management（替代旧 management 测试）
- Phase 2：新建 13_acpt_contradiction（替代 02、10 矛盾测试）
- Phase 2：新建 14_acpt_lifecycle（替代 03、05、08 生命周期测试）
- Phase 3：新建 15_acpt_multiagent、16_acpt_robustness（替代 06、07、09）

### 7. 全局阈值应拆分为各场景独立阈值

**状态**：待执行  
**当前**：全局阈值 0.70  
**问题**：不同场景有不同难度和重要性，统一阈值过于粗放  
**建议**：
- 核心检索（A-01~A-04）：阈值 0.80
- 高级特性（A-05~A-09）：阈值 0.60
- 管理基础（B-01~B-05）：阈值 0.85
- 高级管理（B-06~B-08）：阈值 0.70

### 8. A-01 精度低需要关注

**状态**：持续监控  
**当前表现**：precision=0.25, recall=1.0, f1=0.40  
**说明**：系统找到了正确答案（recall 100%），但返回了 3 个无关结果。可能原因：
- RRF 融合权重配置需要调优
- BM25 召回过于宽泛
- 缺少有效的 post-recall relevance filtering

---

## P2: 技术债务

### 9. `CLIRunner.remember()` 参数签名与 MemoryAPI 不一致

**状态**：文档已记录  
**说明**：CLIRunner 为保持旧评估兼容，保留了一些 MemoryAPI 不支持的参数（scope、supersede_reason、model_domain 等），同时缺少 MemoryAPI 支持的参数（valid_from、valid_to、source_fragment_ids）

### 10. tests/unit 缺少工具函数测试

**状态**：待补充  
**需要测试的函数**：
- `f1_score()`, `rank_weighted_score()`, `check_recall_chain_adjacency()`, `score_behavior()` in `_lib/acpt_test.py`
- `CLIRunner.set_space()` 的边界行为

### 11. 旧脚本中的"永恒真"断言

**状态**：不紧急  
**说明**：约 8 条断言在所有场景下必然通过（如 `tags is list`、`node_id not None`），可作为 smoke test 但不应计入评估得分

---

## 待讨论

### 12. 矛盾检测的自动化可行性

A-10~A-15 矛盾检测场景中，语义矛盾（"技术栈是 Go" vs "技术栈是 Python"）可以通过规则+LLM 自动判定，但规则矛盾（约束冲突）需要更复杂的形式化验证。Phase 2 设计时需要确定哪些可自动化。

### 13. DreamCycle 评估指标

DreamCycle 的 5 个阶段（decay、reinforce、merge、prune、archive）属于后台维护流程，评估指标应为"系统健康度"而非"每次调用不报错"。Phase 2 需要设计合适的评估方法。

### 14. 性能基准测试

当前所有评估关注功能正确性，未包含性能/延迟测试。Phase 3 的 F-03 场景需要建立：
- remember() 单次延迟 < 200ms
- recall() 单次延迟 < 500ms
- consolidation 全量耗时 < 10s