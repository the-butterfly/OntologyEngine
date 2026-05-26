# 04 — LOCOMO 综合评估（功能验证）

> **注意**：本目录下的案例使用**人造数据**（TechNova、CloudGroup、王芳等）进行功能通路验证，并非真实的 LOCOMO-10 基准数据集。
>
> 若需要在真实 LOCOMO-10 数据集上与 Mem0 进行公平对比，请使用 `14_locomo_benchmark`。

## 案例说明

本案例通过 10 个轨迹（T1-T10）验证 OE 记忆系统的核心功能通路：

| 轨迹 | 验证点 |
|------|--------|
| T1 | 单跳召回（direct fact retrieval） |
| T2 | 多跳推理（cross-entity inference） |
| T3 | 时序推理（time-aware queries） |
| T4 | 矛盾检测（rule + semantic） |
| T5 | 巩固与类型升级 |
| T6 | 取代与信念修订 |
| T7 | 遗忘与保护 |
| T8 | 更正传播 |
| T9 | DreamCycle 维护 |
| T10 | 全生命周期交叉验证 |

## 运行方式

```bash
python -m examples.agent_memory.04_locomo_eval.run_eval
python -m examples.agent_memory.04_locomo_eval.run_eval_e2e
python -m examples.agent_memory.04_locomo_eval.run_eval_cli_sim
```

## 已知限制

根据 `ANALYSIS.md`（2026-05-06）的分析，本案例在**检索质量**方面存在以下已知问题：

- **向量检索降级为 BM25**：中文子串匹配几乎无效，导致 recall 精确度低
- **analytical 查询返回空列表**：`rrf_fusion.py` 对分析型查询直接短路
- **Layer-S 仅查询 entity 类型**：observation / mental_model 未被检索
- **时序推理失效**：无法正确找到最新的策略版本

这些问题在 `14_locomo_benchmark` 的真实数据集评估中会暴露得更明显，因此建议将 `14_locomo_benchmark` 作为量化迭代的主要依据。

## 相关案例

- `14_locomo_benchmark/` — 真实 LOCOMO-10 数据集，OE vs Mem0 公平对比
