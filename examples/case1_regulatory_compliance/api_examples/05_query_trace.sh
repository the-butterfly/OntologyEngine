#!/bin/bash
# Case 1 Step 5: 查询决策溯源
# 查看特定供应商的完整合规决策链和证据

ontology-cli query trace \
    --space space.supply_chain_finance \
    --entity-id SUP_C4 \
    --include-evidence true

# 期望输出:
# {
#     "entity_id": "SUP_C4",
#     "trace_id": "trace_20260421_001",
#     "decision": {"outcome": "FAILED", "reason": "担保金额超过上限"},
#     "rule_execution_path": [
#         {
#             "rule_id": "RD_C23_003",
#             "rule_name": "担保金额上限检查",
#             "status": "FAILED",
#             "input": {"guarantee_amount": 15000000, "ratio": 0.15},
#             "condition": "ratio <= 0.1",
#             "condition_result": false
#         }
#     ],
#     "evidence_chain": [
#         {"evidence_type": "guarantee_relation", "field": "guarantee_amount", "value": 15000000},
#         {"evidence_type": "fact_object", "field": "registered_capital", "value": 100000000}
#     ],
#     "mutual_index_links": [
#         {"from": "EntityInstance:SUP_C4", "to": "KnowledgeFragment:frag_guarantee", "relation": "extracted_from"},
#         {"from": "ExecutionStepSnapshot:RD_C23_003", "to": "KnowledgeFragment:frag_circular23_article_15", "relation": "trace_to"}
#     ]
# }
