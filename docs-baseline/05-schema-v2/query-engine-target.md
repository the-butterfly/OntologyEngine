# Query Engine（Phase 2 目标）

> **状态**: draft
> **Phase**: phase2
> **Last Verified**: 2026-04-14
> **verified_against**: 待与 Phase 2 实现核验

## 目标能力

### Vector Query（向量检索）
- Faiss 向量索引，支持 ANN 近似最近邻搜索
- sentence-transformers 嵌入模型
- 支持 entity / metric / rule 的向量表示

### Hybrid Query（混合检索）
- 固定权重融合：semantic × 0.6 + graph × 0.4（可配置）
- 融合策略可选：RRF、加权求和、交叉编码重排

### Graph Query DSL（图查询 DSL）
- 支持路径模式匹配：`Company -(guarantees)-> Company -(supplies)-> CoreEnterprise`
- 正则化关系序列表达

### kuzu 协同
- Phase 2 中 NetworkXGraphStore 升级为 kuzu 嵌入图数据库
- kuzu 负责：图遍历、路径查询、担保圈检测、循环检测、中心性计算
- DuckDB 继续负责：实体存储、指标计算、审计日志
- 两者通过统一 Repository 接口协同

## 性能目标

| 指标 | Phase 1 | Phase 2 |
|------|---------|---------|
| 节点规模 | 100K | 500K |
| 向量检索 P99 | - | < 1s |
| 图遍历 P99 | 2s | 1s |

## Phase 2 前置条件

- [ ] Faiss 集成完成
- [ ] kuzu 接入
- [ ] Repository 接口抽象完成
