# ADR-009: 记忆强度 recency 衰减算法从指数衰减切换为线性衰减

| 字段 | 值 |
|------|-----|
| 状态 | accepted |
| 日期 | 2026-05-11 |
| 决策者 | Agent Memory 模块维护 |
| 关联 | `ontology_engine/engine/cognitive/memory_api.py` `_compute_strength` |

## 背景

`_compute_strength` 中 recency 分量的计算方式发生了变更。旧版使用 `lifecycle.compute_memory_strength` 中的指数衰减公式 `math.exp(-0.1 * days_since_access)`，新版改为线性衰减公式 `max(0.0, 1.0 - (age_hours / (30 * 24)))`。

## 决策

采用线性衰减替代指数衰减，30 天窗口线性归零。

## 理由

1. **可解释性**: 线性衰减的行为更直观——"30 天内线性衰退至零"，便于用户和开发者理解
2. **计算简单**: 无需导入 `math` 模块，减少依赖
3. **长期记忆区分度**: 指数衰减在 30 天后仍有 ~5% 残留值（`e^(-3) ≈ 0.05`），导致长期未访问记忆的 recency 分量几乎无区分度；线性衰减在 30 天后直接归零，区分更明确
4. **与 rank_score 简化一致**: `rank_score` 计算也同步简化为 `score * type_weight * (0.7 + 0.3 * tp)`，硬编码权重替代了动态 `compute_temporal_weight`

## 影响

- 30 天后 recency 分量从 ~5% 降为 0%，长期记忆的 strength 值会略低
- `rank_score` 中时间权重从动态 `tw` 改为固定 0.3，丧失了通过 `DispositionProfile.recency_bias` 调节的能力
- 此变更为临时简化，QUL 重新集成后应恢复可配置的 recency_bias

## 后续

- QUL 重新集成时，考虑恢复 `recency_bias` 配置能力
- 30 天窗口是否合适需通过实际数据验证
