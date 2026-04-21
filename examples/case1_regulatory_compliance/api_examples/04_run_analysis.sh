#!/bin/bash
# Case 1 Step 4: 执行合规分析
# 对所有供应商执行央行23号文合规检查

ontology-cli analyze \
    --space space.supply_chain_finance \
    --entity-type Supplier \
    --category compliance_assessment \
    --dimension circular23_compliance

# 期望输出:
# {
#     "analysis_id": "analysis_20260421_001",
#     "entities_analyzed": 5,
#     "results": [
#         {"entity_id": "SUP_C1", "compliance_status": "PASSED", "score": 95},
#         {"entity_id": "SUP_C2", "compliance_status": "FAILED", "score": 45},
#         {"entity_id": "SUP_C3", "compliance_status": "FAILED", "score": 50},
#         {"entity_id": "SUP_C4", "compliance_status": "FAILED", "score": 40},
#         {"entity_id": "SUP_C5", "compliance_status": "FAILED", "score": 35}
#     ],
#     "summary": {"total": 5, "passed": 1, "failed": 4, "pass_rate": "20%"}
# }
