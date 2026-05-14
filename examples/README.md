# Agent Memory Examples & Acceptance Tests

本目录包含 Agent Memory（知识库/记忆系统）的评估脚本和验收测试。
所有脚本通过 `_lib/cli_runner.py` 中的 `CLIRunner` 统一调用 `MemoryAPI`，
无需直接依赖内部模块。

---

## 目录结构

```
examples/agent_memory/
├── _lib/                              # 共享基础设施
│   ├── cli_runner.py                  # CLI模拟器，封装所有 MemoryAPI 操作
│   ├── acpt_test.py                   # 新一代验收测试框架（score-only）
│   └── __init__.py
├── 01_ingestion_pipeline/             # 旧: 摄入流水线验证（8 trajectories）
├── 02_contradiction_belief/           # 旧: 矛盾检测与信念状态（6 trajectories）
├── 03_consolidation_compilation/      # 旧: 整合与实体/话题编译
├── 04_locomo_eval/                    # 旧: LoCoMo风格综合评估（10 trajectories）
├── 05_lifecycle_governance/           # 旧: 生命周期与治理
├── 06_full_agent_eval/                # 旧: 全栈Agent评估
├── 07_modeling_objects/               # 旧: 认知对象建模
├── 08_qul_lifecycle/                  # 旧: QUL生命周期
├── 09_sota_optimization_eval/         # 旧: SOTA优化基线验证
├── 10_contradiction_fix_eval/         # 旧: 矛盾修复验证
├── 11_acpt_retrieval/                 # ★ 新: 检索效果验收测试（9 scenarios）
├── 12_acpt_management/                # ★ 新: 知识资产管理验收测试（8 scenarios）
└── TODO.md                            # 遗留问题与待办
```

---

## 评估框架：两代对比

### 旧框架 (01-10): `EvalReport` + `_ok()`

定义于 `_lib/cli_runner.py`，**二元 pass/fail + 数值 score**：

```python
from _lib.cli_runner import CLIRunner, EvalReport, _ok, create_runner

result = _ok("T1-xxx", passed=True, score=0.8, details="...", latency_ms=100.0)
report.add(result)
```

**已知问题**：
- ~60% 的测试检查"API 不崩"即为 pass，区分度低
- 8 条"永恒真"断言（如 "tags 是 list"、"node_id 非空"）永远通过
- `remember()` 的参数 `model_domain`、`source_trust_tier` 被**静默丢弃**（未传给 API）
- 无统一阈值标准

### 新框架 (11+): `AcptReport` + `r()` + Scoring Helpers

定义于 `_lib/acpt_test.py`，**仅连续 score [0.0, 1.0]，无 passed 字段**：

```python
from _lib.acpt_test import AcptReport, r, f1_score, rank_weighted_score, check_recall_chain_adjacency, score_behavior

result = r("A-01 Single-hop", score=0.75, details="prec=0.5 rec=1.0", latency_ms=100.0, sub_scores={"f1": 0.67})
report.add(result)
```

**核心改进**：
- **纯 score 评估**：每个场景产生 [0.0, 1.0] 连续分数，而非二元 pass/fail
- **F1 评分**：基于关键词在召回结果中的 precision/recall/F1
- **Rank-weighted 评分**：`Σ(1/rank_i)` 对相关结果排序质量评分（替代语义鸿沟的人工评估）
- **Chain adjacency**：验证 recall chain 中相邻节点的关联性（替代多跳推理的人工评估）
- **Weighted assertion bank**：加权断言组合，区分核心/辅助检查
- **统一阈值**：全局验收阈值 0.70
- **独立空间隔离**：每个 scenario 使用独立 space_id，互不干扰

---

## 新验收测试详情

### Category A: 检索效果 (`11_acpt_retrieval/`)

| 场景 | 评估方式 | 说明 |
|------|---------|------|
| A-01 单跳精确匹配 | F1 (precision/recall/f1) | 查询"TechNova总部在哪"是否返回含"深圳"的结果 |
| A-02 语义鸿沟 | Rank-weighted `Σ(1/rank_i)` | 查询"云平台技术栈"的 CloudGroup/K8s 排名 |
| A-03 多跳推理链 | Chain adjacency | 验证"王芳→CloudGroup→Kubernetes"推理链节点相邻性 |
| A-04 时序排序 | Rank position check | 最新策略(10000/分钟)排最前，最旧排最后 |
| A-05 跨类型召回 | Type diversity | "架构"查询返回 entity/observation/rule 多种类型 |
| A-06 置信度过滤 | Filter verification | min_confidence=0.5 应排除低置信(0.3)记忆 |
| A-07 证据链展开 | Evidence depth | include_evidence=True 应返回非空证据 |
| A-08 私有隔离 | Cross-user visibility | alice 不应能召回 bob 的 private 记忆 |
| A-09 Token 预算截断 | Token budget | token_budget=400 应限制返回结果数 |

当前结果：**Mean Score: 0.767 | Min Score: 0.400 | >= 0.7: 5/9**

### Category B: 知识资产管理 (`12_acpt_management/`)

| 场景 | 评估方式 | 说明 |
|------|---------|------|
| B-01 基础摄入 | Weighted assertions | 创建 entity 类型记忆，验证 node_id 和 stats |
| B-02 去重 | Weighted assertions | 相同内容两次 remember 返回相同 node_id |
| B-03 实体解析 | Weighted assertions | entity 类型创建后可被 recall |
| B-04 可见性推断 | Weighted assertions | PII 内容自动推断 visibility 并限制访问 |
| B-05 认知层推断 | Weighted assertions | observation/entity/rule/mental_model 四种类型均可创建 |
| B-06 信念状态 | Weighted assertions | pending_review 状态可通过 stats 追踪 |
| B-07 版本历史 | Weighted assertions | correct → SUPERSEDES 边 + audit trail |
| B-08 结构提取 | Weighted assertions | 结构化内容摄入和召回 |

当前结果：**Mean Score: 0.963 | Min Score: 0.700 | >= 0.7: 8/8**

---

## 运行方式

```bash
# 新验收测试（推荐）
python examples/agent_memory/11_acpt_retrieval/run_eval.py
python examples/agent_memory/12_acpt_management/run_eval.py

# 旧评估脚本（兼容保留）
python examples/agent_memory/01_ingestion_pipeline/run_eval.py
python examples/agent_memory/04_locomo_eval/run_eval.py
# ... etc
```

所有脚本均使用临时数据库（`tempfile.mkdtemp`），运行结束后自动清理，不影响生产数据。

---

## 设计原则

1. **独立空间隔离**：每个测试场景使用 `runner.set_space(f"{SPACE}_{scenario_name}")`，避免数据交叉干扰
2. **自动化优先**：核心基础内容全自动化；仅保留极少数需要人工判断的语义评估（如 A-07 证据链质量）
3. **评分有区分度**：每个场景产生 0.0-1.0 分数，避免"API不崩=pass"的低区分度陷阱
4. **已知缺陷透明**：参数丢弃、置信过滤不生效等已知问题在 `TODO.md` 中记录
5. **阈值按场景重评估**：当前全局阈值 0.70 为初始值，后续应按各场景独立校准

---

## 后续规划（Phase 2-3）

| Phase | 类别 | 场景数 | 目标 |
|-------|------|--------|------|
| 2 | C: 矛盾检测 (Contradiction) | 6 | 语义矛盾、规则矛盾、反馈保护 |
| 2 | D: 生命周期 (Lifecycle) | 5 | 遗忘、整合、DreamCycle、治理 |
| 3 | E: 多Agent (Multi-Agent) | 4 | 跨空间隔离、协作、冲突解决 |
| 3 | F: 鲁棒性 (Robustness) | 3 | 边界条件、错误恢复、性能基准 |

总计 35 个验收场景，覆盖 Agent Memory 全功能矩阵。