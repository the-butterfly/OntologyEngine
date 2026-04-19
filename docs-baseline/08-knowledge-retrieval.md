# 知识检索服务设计

> **服务类型**: Agent 知识检索与规则追溯
> **核心能力**: 向量语义匹配 + 图 Schema 匹配 + 规则链路追溯

## 一、服务概览

### 1.1 三大检索模式

```
Knowledge Retrieval Service
    │
    ├── Pattern Matching (Query 匹配)
    │   ├── Semantic Search (向量)
    │   ├── Graph Schema Match (图关系)
    │   └── Hybrid Fusion (混合)
    │
    ├── Rule Trace (规则追溯)
    │   ├── Instance → Categorization
    │   ├── Instance → Rule Group
    │   ├── Rule → Computation Tree
    │   └── Full Dependency Chain
    │
    └── Rule Execution (规则执行)
        ├── Input Resolution
        ├── Formula Evaluation
        └── Explainable Output
```

### 1.2 API 端点

```yaml
/agent/query/pattern-match    # 知识检索
/agent/query/rule-trace       # 规则追溯
/agent/execute/with-explain   # 执行并解释
/agent/history/operations      # 操作历史
/agent/feedback               # 反馈提交
/agent/rollback               # 回退操作
```

---

## 二、Pattern Matching (Query 匹配)

### 2.1 匹配模式

```yaml
match_mode:
  semantic:     # 向量语义匹配
    - 使用 Embedding 模型
    - 计算余弦相似度
    - 适合：自然语言描述

  graph:       # 图 Schema 关系匹配
    - 匹配实体类型
    - 匹配关系路径
    - 适合：结构化查询

  hybrid:      # 加权混合 (默认)
    - semantic_weight + graph_weight = 1.0
    - 分数融合

  path:        # 路径模式
    - 指定起点/终点/关系类型
    - 匹配符合模式的路径
```

### 2.2 请求/响应

#### 请求

```yaml
POST /agent/query/pattern-match

{
  "query": "查找提供芯片的供应商",
  "match_mode": "hybrid",

  "top_k": 10,

  # 过滤条件
  "filters": {
    "concept_types": ["Supplier"],      # 实体类型
    "attributes": {                     # 属性过滤
      "status": {"eq": "ACTIVE"},
      "industry.category": {"in": ["C", "F"]}
    },
    "relation_filters": [
      {
        "type": "supplies",            # 关系类型
        "target_type": "Product",
        "target_attributes": {
          "category": "芯片"
        }
      }
    ]
  },

  # hybrid 权重
  "weights": {
    "semantic": 0.6,
    "graph": 0.4
  },

  # 返回内容控制
  "return": {
    "attributes": ["name", "status", "credit_score"],  # 返回的字段
    "include_neighbors": true,      # 返回邻居节点
    "neighbor_depth": 1,          # 邻居深度
    "include_paths": true          # 返回匹配路径
  }
}
```

#### 响应

```yaml
{
  "success": true,
  "data": {
    "query": "查找提供芯片的供应商",
    "match_mode": "hybrid",
    "total_candidates": 156,
    "returned": 10,

    "results": [
      {
        "rank": 1,
        "entity_id": "SUP001",
        "concept_type": "Supplier",
        "overall_score": 0.95,

        "score_breakdown": {
          "semantic_score": 0.92,
          "graph_score": 0.98
        },

        "matched_details": {
          "semantic": {
            "query_embedding_similarity": 0.92,
            "matched_text_fields": ["name", "description", "business_scope"]
          },
          "graph": {
            "matched_path": ["Supplier:supplies->Product:category='芯片'"],
            "path_length": 2,
            "intermediate_nodes": ["Product:芯片-001"]
          }
        },

        "attributes": {
          "name": "深圳芯片科技有限公司",
          "status": "ACTIVE",
          "credit_score": 85,
          "industry": "制造业"
        },

        "neighbors": [
          {
            "relation": "supplies",
            "entity_id": "PROD001",
            "concept_type": "Product",
            "attributes": {"name": "5G芯片", "category": "芯片"}
          }
        ],

        "matched_paths": [
          {
            "path": ["SUP001", "supplies", "PROD001"],
            "description": "该供应商通过 'supplies' 关系连接到芯片类产品"
          }
        ]
      },

      # ... more results
    ],

    "aggregation": {
      "by_concept_type": {"Supplier": 7, "Company": 3},
      "by_status": {"ACTIVE": 8, "INACTIVE": 2},
      "score_distribution": {"mean": 0.72, "median": 0.75}
    }
  },

  "meta": {
    "request_id": "req_20260409_001",
    "processing_time_ms": 45,
    "cache_hit": false
  }
}
```

### 2.3 向量语义实现

```python
class SemanticSearch:
    """向量语义搜索"""

    def __init__(self, embedder: Embedder, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    async def search(
        self,
        query: str,
        concept_types: list[str] | None,
        top_k: int,
        filters: dict | None = None
    ) -> list[SearchResult]:
        # 1. 生成查询向量
        query_vector = await self.embedder.embed(query)

        # 2. 向量检索
        candidates = await self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k * 3,  # 扩大候选集，过滤后再截断
            filters=filters
        )

        # 3. 属性过滤
        if filters:
            candidates = self._apply_attribute_filter(candidates, filters)

        # 4. 截断到 top_k
        return candidates[:top_k]

    async def _build_entity_text(self, entity: Entity) -> str:
        """构建实体的文本表示"""
        parts = [
            entity.concept_type,
            entity.attributes.get("name", ""),
            entity.attributes.get("description", ""),
            entity.attributes.get("business_scope", ""),
        ]
        return " | ".join(filter(None, parts))
```

### 2.4 图 Schema 匹配实现

```python
class GraphSchemaMatcher:
    """图 Schema 关系匹配"""

    def __init__(self, storage: GraphStore):
        self.storage = storage

    async def match(
        self,
        query_conditions: QueryConditions,
        top_k: int
    ) -> list[MatchResult]:
        # 1. 解析查询条件
        target_types = query_conditions.get_concept_types()
        relation_filters = query_conditions.get_relation_filters()

        # 2. 构建图匹配查询
        if relation_filters:
            # 关系过滤查询
            results = await self._match_with_relations(
                target_types, relation_filters, top_k
            )
        else:
            # 纯类型查询
            results = await self._match_by_types(target_types, top_k)

        return results

    async def _match_with_relations(
        self,
        target_types: list[str],
        relation_filters: list[RelationFilter],
        top_k: int
    ) -> list[MatchResult]:
        """
        带关系过滤的匹配

        示例: "supplies Product(category='芯片')"
        """
        results = []

        for rf in relation_filters:
            # 查询符合关系模式的实体
            matched = await self.storage.query(
                match_pattern={
                    "source": {
                        "concept_type": rf.source_type or target_types
                    },
                    "relation": rf.relation_type,
                    "target": {
                        "concept_type": rf.target_type,
                        "attributes": rf.target_attributes
                    }
                },
                limit=top_k * 2
            )

            for m in matched:
                results.append(MatchResult(
                    entity_id=m.source_id,
                    concept_type=m.source_type,
                    matched_relation=rf.relation_type,
                    matched_target=m.target_id,
                    graph_score=self._calculate_graph_score(m)
                ))

        # 按分数排序并截断
        results.sort(key=lambda x: x.graph_score, reverse=True)
        return results[:top_k]
```

### 2.5 混合融合

**权重策略（决策 #4）**：
- **Phase 1**：固定权重 `semantic:0.6 + graph:0.4`
- **Phase 2**：自适应权重（根据查询意图和结果质量动态调整）

```python
class HybridSearch:
    """混合搜索融合"""

    def __init__(
        self,
        semantic: SemanticSearch,
        graph: GraphSchemaMatcher,
        reranker: Reranker | None = None
    ):
        self.semantic = semantic
        self.graph = graph
        self.reranker = reranker
        # Phase 1: 固定权重
        self.default_weights = Weights(semantic=0.6, graph=0.4)

    async def search(
        self,
        query: str,
        match_mode: MatchMode,
        weights: Weights | None = None,
        top_k: int,
        filters: dict | None = None
    ) -> list[HybridResult]:
        # Phase 1: 使用传入权重或默认权重
        effective_weights = weights or self.default_weights

        if match_mode == MatchMode.SEMANTIC:
            return await self.semantic.search(query, filters, top_k)

        elif match_mode == MatchMode.GRAPH:
            return await self.graph.match(filters, top_k)

        elif match_mode == MatchMode.HYBRID:
            # 并行执行两种搜索
            semantic_results, graph_results = await asyncio.gather(
                self.semantic.search(query, filters, top_k * 2),
                self.graph.match(filters, top_k * 2)
            )

            # 分数融合
            fused = self._fuse_scores(
                semantic_results,
                graph_results,
                effective_weights
            )

            # 可选的 ReRank
            if self.reranker:
                fused = await self.reranker.rerank(query, fused, top_k)
            else:
                fused = fused[:top_k]

            return fused

    def _fuse_scores(
        self,
        semantic: list[SearchResult],
        graph: list[MatchResult],
        weights: Weights
    ) -> list[HybridResult]:
        """分数融合"""

        # 构建 ID → 结果映射
        semantic_map = {r.entity_id: r for r in semantic}
        graph_map = {r.entity_id: r for r in graph}

        # 合并
        all_ids = set(semantic_map.keys()) | set(graph_map.keys())

        results = []
        for entity_id in all_ids:
            sem_score = semantic_map.get(entity_id)
            gra_score = graph_map.get(entity_id)

            # 归一化分数 (Min-Max)
            norm_sem = sem_score.normalized_score if sem_score else 0
            norm_gra = gra_score.normalized_score if gra_score else 0

            # 加权融合
            final_score = (
                weights.semantic * norm_sem +
                weights.graph * norm_gra
            )

            results.append(HybridResult(
                entity_id=entity_id,
                overall_score=final_score,
                semantic_score=norm_sem,
                graph_score=norm_gra,
                details=semantic_map.get(entity_id) or graph_map.get(entity_id)
            ))

        # 排序
        results.sort(key=lambda x: x.overall_score, reverse=True)
        return results
```

---

## 三、Rule Trace (规则追溯)

### 3.1 追溯链路

```
Instance (实体)
    │
    ├─▶ L2: Categorization (归类分析)
    │       ├─ industry: 制造业
    │       ├─ company_scale: MEDIUM
    │       └─ risk_level: LOW
    │
    ├─▶ L4: Rule Groups (适用规则组)
    │       ├─ credit_assessment ✓ (matches categorization)
    │       └─ collateral_assessment ✓ (matches categorization)
    │
    └─▶ L4: Computation Tree (计算树)
            │
            ├─ R001 (precondition)
            │   └─ inputs: [L1_fact.status, L1_fact.credit_score]
            │
            ├─ R002 (compute)
            │   ├─ inputs:
            │   │   ├─ credit_score: {source: L3_metric, value: 78}
            │   │   └─ registered_capital: {source: L1_fact, value: 5000000}
            │   └─ formula: "min(registered_capital * 0.5, 10000000) * factor"
            │
            └─ R003 (decision)
                ├─ inputs: [R002.credit_limit]
                └─ output: {eligible, credit_limit, interest_rate}
```

### 3.2 请求/响应

#### 请求

```yaml
POST /agent/query/rule-trace

{
  "entity_id": "SUP001",
  "trace_mode": "full",       # categorization | rule | dependency | full

  "options": {
    "rule_group": "credit_assessment",  # 指定规则组，为空则全部

    "include_intermediate": true,        # 包含中间结果
    "include_formulas": true,           # 包含公式详情

    "depth": {
      "categorization": "all",          # all | first | none
      "rules": "all",                  # all | direct | none
      "dependencies": 5                # 数字表示依赖深度
    },

    "prune": {
      "unused_rules": true,            # 排除未触发的规则
      "constant_branches": false        # 保留常量分支
    }
  }
}
```

#### 响应 (full 模式)

```yaml
{
  "success": true,
  "data": {
    "entity_id": "SUP001",
    "trace_mode": "full",
    "generated_at": "2026-04-09T10:30:00Z",

    # L1: 实体信息
    "entity": {
      "id": "SUP001",
      "concept_type": "Supplier",
      "key_attributes": {
        "name": "深圳芯片科技有限公司",
        "registered_capital": {"value": 5000000, "currency": "CNY"},
        "status": "ACTIVE",
        "establishment_date": "2020-03-15"
      }
    },

    # L2: 归类分析
    "categorization": {
      "industry": {
        "dimension": "industry_category",
        "value": "制造业",
        "confidence": 1.0,
        "matched_rules": ["industry_from_business_scope"]
      },
      "company_scale": {
        "dimension": "company_scale",
        "value": "MEDIUM",
        "confidence": 0.95,
        "matched_rules": ["scale_from_revenue"]
      },
      "risk_level": {
        "dimension": "risk_level",
        "value": "LOW",
        "confidence": 0.88,
        "matched_rules": ["risk_from_negative_news"]
      }
    },

    # L4: 适用规则组
    "rule_groups": [
      {
        "name": "credit_assessment",
        "matched": true,
        "match_reason": "industry in ['C', 'F'] AND risk_level in [LOW, MEDIUM]",
        "preconditions_met": [
          {"id": "status_check", "result": true},
          {"id": "establishment_days", "result": true}
        ],
        "preconditions_failed": []
      },
      {
        "name": "collateral_assessment",
        "matched": false,
        "match_reason": "risk_level=HIGH not in allowed values"
      }
    ],

    # L4: 完整计算树
    "computation_tree": {
      "nodes": [
        {
          "id": "R001",
          "name": "基础准入检查",
          "type": "precondition",
          "layer": "L4",
          "inputs": [
            {
              "name": "status",
              "source_type": "L1_fact",
              "source_id": "SUP001",
              "attribute": "status",
              "value": "ACTIVE"
            },
            {
              "name": "credit_score",
              "source_type": "L3_metric",
              "metric_id": "credit_score",
              "value": 78
            }
          ],
          "condition": "status == 'ACTIVE' AND credit_score >= 60",
          "condition_evaluated": "ACTIVE == 'ACTIVE' AND 78 >= 60 = TRUE",
          "result": true,
          "output": {"eligible": true}
        },
        {
          "id": "R002",
          "name": "额度计算",
          "type": "compute",
          "layer": "L4",
          "depends_on": ["R001"],
          "inputs": [
            {
              "name": "registered_capital",
              "source_type": "L1_fact",
              "value": 5000000
            },
            {
              "name": "credit_score",
              "source_type": "L3_metric",
              "value": 78
            }
          ],
          "formula": "min(registered_capital * 0.5, 10000000) * credit_score / 100",
          "formula_evaluated": "min(2500000, 10000000) * 0.78",
          "calculation": "2500000 * 0.78 = 1950000",
          "result": {"credit_limit": 1950000}
        },
        {
          "id": "R003",
          "name": "利率定价",
          "type": "decision",
          "layer": "L4",
          "depends_on": ["R002"],
          "inputs": [
            {
              "name": "credit_limit",
              "source_type": "rule_output",
              "rule_id": "R002",
              "value": 1950000
            },
            {
              "name": "credit_score",
              "source_type": "L3_metric",
              "value": 78
            }
          ],
          "formula": "0.05 + (100 - credit_score) / 1000",
          "calculation": "0.05 + (100 - 78) / 1000 = 0.072",
          "result": {"interest_rate": 0.072}
        }
      ],

      "edges": [
        {"from": "R001", "to": "R002", "label": "depends_on"},
        {"from": "R002", "to": "R003", "label": "depends_on"}
      ],

      "execution_order": ["R001", "R002", "R003"]
    },

    # 原子指标
    "atomic_metrics": [
      {"id": "credit_score", "name": "信用评分", "value": 78, "source": "L3_metric"},
      {"id": "registered_capital", "name": "注册资本", "value": 5000000, "source": "L1_fact"}
    ],

    # 最终输出
    "final_output": {
      "eligible": true,
      "credit_limit": {"value": 1950000, "currency": "CNY"},
      "interest_rate": 0.072
    }
  }
}
```

---

## 四、Rule Execution (规则执行 + 可解释性)

### 4.1 执行流程

```
执行请求
    │
    ▼
1. 输入解析
    ├─ 获取实体数据 (L1)
    ├─ 计算分类标签 (L2)
    └─ 预计算 L3 指标
    │
    ▼
2. 规则匹配
    ├─ 检查 applies_to
    ├─ 检查 preconditions
    └─ 构建执行队列
    │
    ▼
3. DAG 执行
    ├─ 拓扑排序
    ├─ 按序执行规则
    └─ 记录中间结果
    │
    ▼
4. 结果组装
    ├─ 聚合 outputs
    └─ 生成解释
    │
    ▼
返回可解释结果
```

### 4.2 请求/响应

#### 请求

```yaml
POST /agent/execute/with-explain

{
  "entity_id": "SUP001",
  "rule_group": "credit_assessment",

  "explain_level": "full",     # minimal | intermediate | full

  "options": {
    "include_trace": true,     # 包含完整追溯信息
    "include_warnings": true, # 包含警告信息
    "include_suggestions": true,  # 包含优化建议

    "override_inputs": {       # 可选：覆盖输入
      "credit_score": 82
    },

    "dry_run": false           # 预览模式，不保存结果
  }
}
```

#### 响应 (full)

```yaml
{
  "success": true,
  "data": {
    "execution_id": "exec_20260409_001",

    # 执行摘要
    "summary": {
      "entity_id": "SUP001",
      "rule_group": "credit_assessment",
      "started_at": "2026-04-09T10:30:00Z",
      "duration_ms": 45,
      "rules_executed": 3,
      "rules_passed": 3,
      "rules_failed": 0,
      "status": "success"
    },

    # 最终输出
    "final_output": {
      "eligible": true,
      "credit_limit": {"value": 1950000, "currency": "CNY"},
      "interest_rate": 0.072
    },

    # 详细解释
    "explain": {
      "rules": [
        {
          "rule_id": "R001",
          "name": "基础准入检查",
          "status": "passed",

          "condition": {
            "original": "status == 'ACTIVE' AND credit_score >= 60",
            "evaluated": {
              "status": "ACTIVE == 'ACTIVE' = TRUE",
              "credit_score": "78 >= 60 = TRUE",
              "combined": "TRUE AND TRUE = TRUE"
            }
          },

          "action": {
            "type": "set_flag",
            "output": {"eligible": true}
          },

          "execution_time_ms": 2
        },
        {
          "rule_id": "R002",
          "name": "额度计算",
          "status": "passed",

          "inputs": {
            "registered_capital": {
              "value": 5000000,
              "source": "L1_fact",
              "path": "entity.attributes.registered_capital"
            },
            "credit_score": {
              "value": 78,
              "source": "L3_metric",
              "metric_id": "credit_score"
            }
          },

          "computation": {
            "formula": "min(registered_capital * 0.5, 10000000) * credit_score / 100",
            "steps": [
              {"step": 1, "operation": "registered_capital * 0.5", "result": 2500000},
              {"step": 2, "operation": "min(2500000, 10000000)", "result": 2500000},
              {"step": 3, "operation": "credit_score / 100", "result": 0.78},
              {"step": 4, "operation": "2500000 * 0.78", "result": 1950000}
            ],
            "final_result": 1950000
          },

          "output": {"credit_limit": 1950000},
          "execution_time_ms": 5
        }
      ],

      "data_sources": [
        {
          "field": "registered_capital",
          "layer": "L1",
          "source_type": "entity_fact",
          "entity_id": "SUP001",
          "raw_value": {"value": 5000000, "currency": "CNY"}
        },
        {
          "field": "credit_score",
          "layer": "L3",
          "source_type": "metric",
          "metric_id": "credit_score",
          "computed_at": "2026-04-09T10:30:00Z",
          "formula_used": "weighted_sum(...)",
          "value": 78
        }
      ],

      "warnings": [
        {
          "type": "low_confidence",
          "message": "信用评分 78 接近阈值 60，仅高出 30%",
          "affected_rules": ["R001"]
        }
      ],

      "suggestions": [
        {
          "type": "rule_optimization",
          "message": "建议将 R001 的信用评分阈值从 60 调整为 70",
          "expected_impact": "减少 15% 的高风险通过率",
          "effort": "low"
        }
      ]
    },

    # 操作历史 ID (用于反馈)
    "operation_id": "op_20260409_001"
  }
}
```

---

## 五、反馈闭环

**反馈驱动机制（决策 #5）**：反馈自动触发影响分析 + 生成变更建议，但执行必须人工确认。

### 5.1 反馈类型

```yaml
feedback_type:
  correction:    # 修正结果 (人工审核后)
  rejection:      # 拒绝结果
  suggestion:     # 改进建议
  success:        # 确认正确
```

### 5.1.1 反馈自动处理流程

```
反馈提交
    │
    ▼
1. 记录反馈
    │
    ▼
2. 自动触发影响分析
    ├─ 分析受影响的规则/指标/分类
    ├─ 计算影响范围（实体数量、规则组数量）
    └─ 评估变更风险等级
    │
    ▼
3. 生成变更建议
    ├─ 建议的 Schema 变更内容
    ├─ 受影响的下游规则
    └─ 回归测试建议
    │
    ▼
4. 等待人工确认
    ├─ 确认执行 → 应用变更
    ├─ 修改建议 → 重新分析
    └─ 拒绝 → 关闭反馈，记录原因
    
⚠️ 关键约束：反馈不自动执行任何知识更新，所有变更必须人工确认。
```

### 5.2 反馈接口

```yaml
POST /agent/feedback

{
  "operation_id": "op_20260409_001",  # 关联的操作

  "feedback_type": "correction",

  "target": {
    "type": "rule_result",      # rule_result | metric | categorization
    "entity_id": "SUP001",
    "rule_id": "R002",
    "field": "credit_limit",
    "actual_value": 1950000,
    "expected_value": 2200000
  },

  "reason": {
    "code": "ignored_collateral",
    "message": "未考虑抵押物价值",
    "details": "该企业有房产抵押，价值约500万"
  },

  "suggested_change": {
    "type": "input_override",
    "adjustments": {
      "R002": {
        "collateral_value": 5000000  # 新增输入
      }
    }
  },

  "metadata": {
    "submitted_by": "agent_or_user_id",
    "priority": "high",
    "tags": ["collateral", "credit_limit"]
  }
}
```

### 5.3 操作历史

```yaml
GET /agent/history/operations

{
  "filters": {
    "entity_id": "SUP001",
    "rule_group": "credit_assessment",
    "time_range": {
      "start": "2026-04-01",
      "end": "2026-04-09"
    },
    "feedback_type": ["correction", "rejection"],
    "status": ["success", "failed"]
  },

  "pagination": {
    "page": 1,
    "page_size": 20
  },

  "sort": {
    "field": "executed_at",
    "order": "desc"
  }
}
```

### 5.4 回退机制

```yaml
POST /agent/rollback

{
  "target": {
    "type": "rule_result",
    "entity_id": "SUP001",
    "rule_group": "credit_assessment",
    "operation_id": "op_20260409_001"
  },

  "rollback_to": {
    "type": "operation_id",
    "operation_id": "op_20260408_015"
  },

  "reason": "规则逻辑错误，需重新评估",

  "dry_run": true   # 预览影响
}
```

#### 回退影响预览

```yaml
{
  "rollback_id": "rb_001",
  "impact_analysis": {
    "will_revert": {
      "R001": {"eligible": true → null},
      "R002": {"credit_limit": 1950000 → null},
      "R003": {"interest_rate": 0.072 → null}
    },

    "dependent_rules": [
      {
        "rule_id": "R003_approval",
        "depends_on": "R003",
        "will_affected": true
      }
    ],

    "dependent_entities": [
      {
        "entity_id": "SUP002",
        "relation": "guaranteed_by",
        "reason": "依赖 SUP001 的信用评估结果"
      }
    ],

    "cascade_effects": {
      "approvals_to_revert": 2,
      "alerts_to_clear": 1,
      "notifications_sent": 3
    }
  },

  "requires_confirmation": true,
  "confirmation_message": "此操作将影响 2 个下游实体，是否继续？"
}
```

---

## 六、实现要点

### 6.1 缓存策略

```python
class RetrievalCache:
    """检索结果缓存"""

    def __init__(self, cache: Cache):
        self.cache = cache

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable,
        ttl: int = 3600
    ) -> Any:
        """缓存 + 失效策略"""
        # 1. 检查缓存
        cached = await self.cache.get(key)
        if cached and not self._is_stale(cached):
            return cached.value

        # 2. 计算
        result = await compute_fn()

        # 3. 写入缓存
        await self.cache.set(key, CacheEntry(
            value=result,
            computed_at=datetime.now(),
            ttl=ttl
        ))

        return result

    def _is_stale(self, entry: CacheEntry) -> bool:
        """判断缓存是否过期"""
        age = (datetime.now() - entry.computed_at).seconds
        return age > entry.ttl
```

### 6.2 性能目标

| 操作 | P50 | P95 | P99 |
|------|-----|-----|-----|
| 向量检索 | < 10ms | < 50ms | < 100ms |
| 图匹配 | < 20ms | < 100ms | < 200ms |
| 混合检索 | < 30ms | < 150ms | < 300ms |
| 规则追溯 | < 50ms | < 200ms | < 500ms |
| 规则执行 | < 100ms | < 500ms | < 1s |

---

## 七、自适应权重（Phase 2 规划）

> **决策 #4**：Phase 2 实现自适应权重，根据查询意图和结果质量动态调整。

### 7.1 查询意图识别

```python
class QueryIntentClassifier:
    """查询意图分类 → 权重策略"""
    
    INTENT_WEIGHTS = {
        "entity_lookup": Weights(semantic=0.3, graph=0.7),    # 实体查找 → 图优先
        "semantic_search": Weights(semantic=0.8, graph=0.2),   # 语义搜索 → 语义优先
        "relation_explore": Weights(semantic=0.2, graph=0.8),  # 关系探索 → 图优先
        "general": Weights(semantic=0.6, graph=0.4),           # 通用 → 均衡
    }
    
    def classify(self, query: str, filters: dict | None) -> str:
        """根据查询内容+过滤条件判断意图"""
        if filters and filters.get("concept_types"):
            return "entity_lookup"
        if len(query.split()) <= 3 and not filters:
            return "entity_lookup"
        if any(kw in query for kw in ["关系", "连接", "担保链", "关联"]):
            return "relation_explore"
        return "general"
```

### 7.2 结果质量反馈

```python
class AdaptiveWeightTuner:
    """基于结果质量自适应调整权重"""
    
    def tune(
        self,
        query: str,
        results: list[HybridResult],
        user_feedback: list[Feedback] | None = None
    ) -> Weights:
        """根据结果分数分布和用户反馈微调权重"""
        if not results:
            return self.default_weights
        
        # 分析两类分数的区分度
        semantic_scores = [r.semantic_score for r in results if r.semantic_score > 0]
        graph_scores = [r.graph_score for r in results if r.graph_score > 0]
        
        # 区分度高的通道权重提升
        sem_variance = variance(semantic_scores) if len(semantic_scores) > 1 else 0
        gra_variance = variance(graph_scores) if len(graph_scores) > 1 else 0
        
        total = sem_variance + gra_variance or 1
        return Weights(
            semantic=sem_variance / total,
            graph=gra_variance / total
        )
```
