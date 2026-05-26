# 矛盾仲裁引擎

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-05-15

---

## 目的

当 Consolidation 或 Ingestion 检测到知识矛盾时，仲裁引擎负责裁决哪条知识保留、如何标记冲突。

## 设计原则

1. **Annotate 优先于判决**：对于无法明确裁决的矛盾（如"分析师 A 看好 / 分析师 B 看跌"），保留双方并标记 `belief_status=contradicting`
2. **证据权重自动裁决**：通过 proof_count、confidence、source_trust_tier 综合评分决定保留哪方
3. **矛盾链可追溯**：所有裁决通过 CONTRADICTS 边记录在 KuzuDB 中

## 仲裁流程

```
矛盾检测触发
    ↓
证据收集：proof_count × confidence × source_trust_tier
    ↓
┌─ 一方证据显著占优 (>2x) → SUPERSEDES (旧→新取代)
├─ 双方证据接近 (<2x)     → CONTRADICTS + belief_status=contradicting
└─ 双方均可成立           → 共存标注 (belief_status=annotated)
```

## 关键决策

| # | 决策 | 理由 |
|---|------|------|
| D-ARB-1 | 默认共存标注，显式裁决需满足阈值 | 避免过早丢弃有价值信息 |
| D-ARB-2 | 证据权重 = proof_count × confidence × source_trust_tier_multiplier | 三重维度综合评估 |

> 详细设计参考 `docs/01-overview/10-kb-process.md` §矛盾检测 和 `docs/02-design/agent-memory/memory-lifecycle.md` §矛盾生命周期。
