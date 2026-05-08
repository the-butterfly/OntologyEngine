# RFC-021: QueryUnderstandingLayer 完整实现

> **状态**: draft
> **创建日期**: 2026-05-07
> **作者**: agent-memory-session
> **评审截止**: 待定
> **关联设计**: [query-understanding-layer.md](../../docs/02-design/agent-memory/query-understanding-layer.md)
> **验收基准**: examples/agent_memory/ 08_qul

## 摘要

实现完整的 QueryUnderstandingLayer (QUL)，包括 8 种约束类型提取、规则层/LLM 层双层提取、约束→检索策略映射、约束驱动重排序。将散落在 rrf_fusion.py 中的约束提取逻辑整合为统一入口。

## 背景与动机

### 当前问题

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| G18 | QUL 完全缺失 | HIGH | recall 无法根据任务约束调整检索策略 |
| — | 约束提取逻辑散落在 rrf_fusion.py | MED | 维护困难，无法统一扩展 |
| — | 缺少 5 种约束类型 | HIGH | task_history/environmental/self_reference/entity_targets/confidence_demand 未实现 |
| — | 约束→策略映射缺失 | HIGH | 提取的约束无法影响检索行为 |
| — | 约束驱动重排序缺失 | HIGH | QUL 对检索结果无实际影响 |

### 验收组影响

- 08_qul: T1 score=0.25（只检测 1/4 约束），T2-T3 约束驱动重排序未实现

### 设计规范要求

QUL 设计文档定义的核心架构:

```
query → QUL.extract_constraints(query, context) → constraints
      → CONSTRAINT_TO_RETRIEVAL_STRATEGY[constraint.type] → strategy
      → recall with strategy → results
      → apply_constraint_boost(results, constraints) → reranked_results
```

8 种约束类型:

| 约束类型 | 提取方式 | 影响的检索策略 |
|---------|---------|---------------|
| user_preference | 规则层: 关键词匹配 | boost model_domain=user |
| task_history | 规则层: 任务状态关键词 | boost model_domain=task |
| temporal_scope | 规则层: 时间模式匹配 | temporal 权重提升 |
| decision_type | 规则层: 决策关键词 | boost model_domain=task + risk_tolerance |
| environmental | 规则层: 环境约束关键词 | boost model_domain=world |
| self_reference | 规则层: 自我引用关键词 | boost model_domain=self |
| entity_targets | 规则层+LLM: 实体名识别 | boost 指定 entity |
| confidence_demand | 规则层: 精确度关键词 | 提升证据要求阈值 |

## 设计方案

### D1: QUL 统一入口

```python
# ontology_engine/engine/cognitive/query_understanding_layer.py

class QueryUnderstandingLayer:
    def __init__(self, repository: CognitiveRepository):
        self._repo = repository
        self._rule_extractors: list[RuleExtractor] = [
            TemporalConstraintExtractor(),
            UserPreferenceExtractor(),
            TaskHistoryExtractor(),
            DecisionTypeExtractor(),
            EnvironmentalExtractor(),
            SelfReferenceExtractor(),
            EntityTargetExtractor(),
            ConfidenceDemandExtractor(),
        ]

    async def extract_constraints(
        self, query: str, context: RecallContext | None = None
    ) -> list[QueryConstraint]:
        constraints: list[QueryConstraint] = []
        # Phase 1: 规则层 (<10ms)
        for extractor in self._rule_extractors:
            result = extractor.extract(query, context)
            constraints.extend(result)
        # Phase 2: LLM 层 (可选, <565ms)
        if self._llm_available and len(constraints) < 2:
            llm_constraints = await self._extract_with_llm(query, context)
            constraints.extend(llm_constraints)
        return constraints

    def map_to_retrieval_strategy(
        self, constraints: list[QueryConstraint]
    ) -> RetrievalStrategyAdjustment:
        adjustment = RetrievalStrategyAdjustment()
        for c in constraints:
            strategy = CONSTRAINT_TO_RETRIEVAL_STRATEGY.get(c.constraint_type)
            if strategy:
                adjustment.apply(strategy, c)
        return adjustment

    def apply_constraint_boost(
        self, results: list[dict], constraints: list[QueryConstraint]
    ) -> list[dict]:
        for r in results:
            boost = 1.0
            for c in constraints:
                strategy = CONSTRAINT_TO_RETRIEVAL_STRATEGY.get(c.constraint_type)
                if strategy and strategy.matches(r):
                    boost *= strategy.boost_factor
            r["constraint_boost"] = boost
            r["rank_score"] = r.get("rank_score", 0) * boost
        return sorted(results, key=lambda x: x["rank_score"], reverse=True)
```

### D2: 约束提取器

每个 RuleExtractor 实现:

```python
class RuleExtractor(Protocol):
    def extract(self, query: str, context: RecallContext | None) -> list[QueryConstraint]: ...
```

已有实现迁移:
- `extract_temporal_constraint` → `TemporalConstraintExtractor`
- `extract_user_preference_constraint` → `UserPreferenceExtractor`
- `extract_decision_constraint` → `DecisionTypeExtractor`

新增实现:
- `TaskHistoryExtractor`: 匹配 "之前/上次/历史/曾经/否决过/拒绝过" 等关键词
- `EnvironmentalExtractor`: 匹配 "限制/约束/环境/平台/系统要求/兼容" 等关键词
- `SelfReferenceExtractor`: 匹配 "我/我们/我的工具/我的经验" 等关键词
- `EntityTargetExtractor`: 匹配引号内实体名或已知 entity_name
- `ConfidenceDemandExtractor`: 匹配 "精确/准确/确定/确认/可靠/权威" 等关键词

### D3: 约束→策略映射

```python
CONSTRAINT_TO_RETRIEVAL_STRATEGY = {
    "user_preference": StrategyAdjustment(
        boost_model_domain="user", boost_factor=1.5,
        boost_memory_types=["opinion", "mental_model"],
    ),
    "task_history": StrategyAdjustment(
        boost_model_domain="task", boost_factor=1.3,
        boost_memory_types=["commitment", "task_state", "episode"],
    ),
    "temporal_scope": StrategyAdjustment(
        boost_weights={"temporal": 0.6},
        temporal_window_days=30,
    ),
    "decision_type": StrategyAdjustment(
        boost_model_domain="task", boost_factor=1.4,
        boost_memory_types=["rule", "constraint"],
        require_evidence=True,
    ),
    "environmental": StrategyAdjustment(
        boost_model_domain="world", boost_factor=1.3,
        boost_memory_types=["constraint", "rule"],
    ),
    "self_reference": StrategyAdjustment(
        boost_model_domain="self", boost_factor=1.2,
        boost_memory_types=["self_experience", "procedure"],
    ),
    "entity_targets": StrategyAdjustment(
        boost_entity_names=[],  # 动态填充
        boost_factor=2.0,
    ),
    "confidence_demand": StrategyAdjustment(
        min_proof_count=2,
        min_belief_status="accepted",
        boost_factor=1.0,  # 不 boost，但过滤低证据结果
    ),
}
```

### D4: recall 集成

```python
# memory_api.py _recall() 中:
async def _recall(self, req: RecallRequest) -> dict:
    # 1. QUL 约束提取
    qul = QueryUnderstandingLayer(self._repo)
    constraints = await qul.extract_constraints(req.query, context)
    strategy = qul.map_to_retrieval_strategy(constraints)

    # 2. 检索 (strategy 影响权重和过滤)
    results = await self._query_router.route(
        query=req.query, space_id=req.space_id,
        strategy_adjustment=strategy, ...
    )

    # 3. 约束驱动重排序
    results = qul.apply_constraint_boost(results, constraints)

    # 4. 后续处理 (disposition, token budget, etc.)
    ...
```

## 验收标准

### 08_qul 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T1-EXT | 8 种约束类型提取 | 至少提取 6/8 种约束类型 |
| T1-CN | 中文约束提取 | "上周否决过微服务方案" 提取 task_history + entity_targets |
| T2-EXT | 约束→策略映射验证 | user_preference 约束使 model_domain=user 的结果排名提升 |
| T2-BOOST | 重排序效果验证 | 有约束时 vs 无约束时，相关结果排名差异 >= 2 位 |
| T3-EXT | 自动上下文加载 | recall 时自动加载活跃任务 + 用户偏好 + 待履行承诺 |
| T9-NEW | 规则层延迟验证 | 规则层提取耗时 < 10ms |
| T10-NEW | LLM 层降级验证 | LLM 不可用时，规则层仍可提取 >= 3 种约束 |

## 实施计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| Phase 1 | QUL 类框架 + RuleExtractor 协议 | 无 |
| Phase 2 | 迁移已有 3 种提取器 + 新增 5 种提取器 | Phase 1 |
| Phase 3 | 约束→策略映射 + apply_constraint_boost | Phase 2 |
| Phase 4 | recall 集成 + 自动上下文加载 | Phase 3 |
| Phase 5 | LLM 层提取 (可选) | Phase 4 |

## 风险

1. 规则层提取的精确度有限，可能需要多轮迭代优化关键词表
2. LLM 层提取增加延迟（200-500ms），需设超时和降级
3. 约束驱动重排序可能与 DispositionProfile 权重冲突，需定义优先级
