# Agent Memory 验证案例集

> OntologyEngine Agent 记忆系统的端到端验证案例集。
> 所有案例通过标准 CLIRunner 接口调用，不破坏封装。

## 目录结构

```
agent_memory/
  _lib/                        ← 共享基础设施（CLIRunner, EvalReport）
  01_ingestion_pipeline/       ← 记忆摄取管线
  02_contradiction_belief/     ← 矛盾检测与信念修订
  03_consolidation_compilation/← 巩固与编译
  04_locomo_eval/              ← LOCOMO 综合评估（含 E2E + CLI 模拟）
  05_lifecycle_governance/     ← 生命周期与治理（含 Gap 验证）
  06_full_agent_eval/          ← 全量 Agent 评估（含真实 LLM）
  07_modeling_objects/         ← 建模对象与权限治理
  08_qul_lifecycle/            ← QUL 约束驱动与生命周期集成
  09_sota_optimization_eval/   ← SOTA 优化评估
  10_contradiction_fix_eval/   ← 矛盾修复评估
  11_acpt_retrieval/           ← ACPT 检索验证
  12_acpt_management/          ← ACPT 管理验证
  13_acpt_e2e/                 ← ACPT 端到端验证
  14_locomo_benchmark/         ← LOCOMO-10 真实数据集：OE vs Mem0 公平对比
  _deprecated/                 ← 废弃案例归档
```

## 案例说明

### 01 — 记忆摄取管线

**验证点**: V-AM-1, V-API-1, V-AM-7, V-LC-1, V-AM-6, V-AM-8, V-HIE-3

| 轨迹 | 说明 |
|------|------|
| T1 | 基础 remember→recall 双存储验证 |
| T2 | DeduplicationGate 高相似度去重 |
| T3 | Entity Resolution L1 精确匹配 |
| T4 | Entity Resolution L2 trigram 模糊匹配 |
| T5 | model_domain 自动推断 |
| T6 | observation cognitive_layer 动态分类 |
| T7 | source_trust_tier 传播 |
| T8 | 多源摄取与类型特有属性 |

```bash
python -m examples.agent_memory.01_ingestion_pipeline.run_eval
```

### 02 — 矛盾检测与信念修订

**验证点**: V-REF-7, V-REF-1, V-LC-7, V-LC-8, V-REF-3

| 轨迹 | 说明 |
|------|------|
| T1 | 规则矛盾检测（否定模式） |
| T2 | LLM 语义矛盾检测 |
| T3 | 信念取代（supersede） |
| T4 | 更正传播（沿认知边 BFS） |
| T5 | Approve/reject 工作流 |
| T6 | Reflect 强制检索序列 |
| T7 | 幻觉防护（evidence_ids） |

```bash
python -m examples.agent_memory.02_contradiction_belief.run_eval
```

### 03 — 巩固与编译

**验证点**: V-CON-1, V-CON-2, V-CON-10, V-LC-10, V-AM-2

| 轨迹 | 说明 |
|------|------|
| T1 | Fragment→observation 巩固 |
| T2 | Observation→entity 升级 |
| T3 | 巩固证据追踪 |
| T4 | LLM 驱动巩固 |
| T5 | EntityPage 编译 |
| T6 | TopicPage 编译 |
| T7 | 巩固推理轨迹 |
| T8 | Stats 验证 |

```bash
python -m examples.agent_memory.03_consolidation_compilation.run_eval
```

### 04 — LOCOMO 综合评估

**验证点**: 跨维度交叉验证（单跳/多跳/时序/矛盾/巩固/遗忘/DreamCycle/更正传播）

包含三个子模式：
- `run_eval.py` — LOCOMO 综合评估（10 轨迹）
- `run_eval_e2e.py` — E2E API 验证（6 轨迹）
- `run_eval_cli_sim.py` — CLI Agent 模拟（6 轨迹）

```bash
python -m examples.agent_memory.04_locomo_eval.run_eval
python -m examples.agent_memory.04_locomo_eval.run_eval_e2e
python -m examples.agent_memory.04_locomo_eval.run_eval_cli_sim
```

### 05 — 生命周期与治理

**验证点**: XV-1, V-AM-2, V-LC-9, V-LC-1, V-AM-8, V-LC-8, V-MOD-3, V-MOD-6

包含两个子模式：
- `run_eval.py` — 生命周期 + MCP 接口（8 轨迹）
- `run_eval_gap.py` — Gap 19-25 验证（8 轨迹）

```bash
python -m examples.agent_memory.05_lifecycle_governance.run_eval
python -m examples.agent_memory.05_lifecycle_governance.run_eval_gap
```

### 06 — 全量 Agent 评估

**验证点**: V-MOD-1/2/3/8, V-LC-10, V-MOD-11

包含两个子模式：
- `run_eval.py` — 全量 Agent 记忆评估（8 轨迹）
- `run_eval_llm.py` — 真实 LLM 评估（8 轨迹，需配置 LLM API Key）

```bash
python -m examples.agent_memory.06_full_agent_eval.run_eval
ONTOLOGY_LLM_API_KEY=xxx python -m examples.agent_memory.06_full_agent_eval.run_eval_llm
```

### 07 — 建模对象与权限治理

**验证点**: V-MOD-1/2/3/6/8/11, V-HIE-9

| 轨迹 | 说明 |
|------|------|
| T1 | User Model 创建与更新 |
| T2 | Task Model（commitment 生命周期） |
| T3 | World Model（constraint 治理） |
| T4 | Self Model（工具可靠性追踪） |
| T5 | list-my-memories |
| T6 | 按 model_domain 的权限治理 |
| T7 | 跨模型引用 |
| T8 | Commitment 截止日期追踪 |

```bash
python -m examples.agent_memory.07_modeling_objects.run_eval
```

### 08 — QUL 约束驱动与生命周期集成

**验证点**: V-QUL-1/3/4/5, V-LC-3/4/5/6/9, XV-1, XV-2

| 轨迹 | 说明 |
|------|------|
| T1 | QUL 约束提取 |
| T2 | 约束驱动重排序 |
| T3 | 自动上下文加载 |
| T4 | 全生命周期闭环 |
| T5 | DreamCycle 5 阶段 |
| T6 | Ebbinghaus 价值感知衰减 |
| T7 | 策略性遗忘 |
| T8 | 端到端交叉验证 |

```bash
python -m examples.agent_memory.08_qul_lifecycle.run_eval
```

### 14 — LOCOMO-10 真实数据集基准对比

**验证点**: 在真实 LOCOMO-10 长对话数据集上，使用统一 LLM（sensenova/sensenova-6.7-flash-lite）对 OE 与 Mem0 进行公平对比。

| 维度 | 说明 |
|------|------|
| 数据集 | LOCOMO-10（Snap Research, ACL 2024） |
| LLM | sensenova/sensenova-6.7-flash-lite（answerer + judge） |
| Cutoffs | top-10 / top-20 / top-50 / top-200 |
| 指标 | 按 short-term / medium-term / long-term / cross-dialogue 分类的 accuracy |

```bash
# OE backend
python -m examples.agent_memory.14_locomo_benchmark.run_eval \
    --backend oe --project-name oe_sensenova \
    --answerer-model sensenova/sensenova-6.7-flash-lite \
    --judge-model sensenova/sensenova-6.7-flash-lite \
    --llm-base-url http://localhost:9528/v1

# Mem0 backend（需先启动 mem0oss）
python -m examples.agent_memory.14_locomo_benchmark.run_eval \
    --backend mem0 --project-name mem0_sensenova \
    --answerer-model sensenova/sensenova-6.7-flash-lite \
    --judge-model sensenova/sensenova-6.7-flash-lite \
    --llm-base-url http://localhost:9528/v1

# 生成对比报告
python -m examples.agent_memory.14_locomo_benchmark.run_eval \
    --compare \
    --oe-results results/locomo_oe/predicted_oe_sensenova/results.json \
    --mem0-results results/locomo_mem0/predicted_mem0_sensenova/results.json
```

## 设计文档索引

| 主题 | 文档 |
|------|------|
| 记忆层次 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 生命周期 | `docs/02-design/agent-memory/memory-lifecycle.md` |
| 认知操作 API | `docs/02-design/agent-memory/memory-api.md` |
| 巩固引擎 | `docs/02-design/agent-memory/consolidation-engine.md` |
| Reflect Agent | `docs/02-design/agent-memory/reflect-agent.md` |
| 建模对象 | `docs/02-design/agent-memory/modeling-objects.md` |
| QUL | `docs/02-design/agent-memory/query-understanding-layer.md` |

## 原案例编号映射

| 原编号 | 新位置 |
|--------|--------|
| case5_memory_ingestion_pipeline | 01_ingestion_pipeline |
| case6_contradiction_belief_revision | 02_contradiction_belief |
| case7_consolidation_compilation | 03_consolidation_compilation |
| case8_locomo_memory_eval | 04_locomo_eval (主) |
| case9_e2e_memory_via_api | 04_locomo_eval (run_eval_e2e.py) |
| case10_cli_agent_simulation | 04_locomo_eval (run_eval_cli_sim.py) |
| case11_lifecycle_mcp_eval | 05_lifecycle_governance (主) |
| case12_gap19_25_eval | 05_lifecycle_governance (run_eval_gap.py) |
| case13_full_agent_memory_eval | 06_full_agent_eval (主) |
| case14_real_llm_eval | 06_full_agent_eval (run_eval_llm.py) |
| case15_modeling_objects_governance | 07_modeling_objects |
| case16_qul_lifecycle_integration | 08_qul_lifecycle |
