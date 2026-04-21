#!/bin/bash
# Case 1 Step 3: 热点更新合规规则
# 加载央行23号文合规检查规则，秒级生效

ontology-cli rules hot-update \
    --space space.supply_chain_finance \
    --file rules/RD_circular23_compliance.yaml

# 期望输出:
# {
#     "rules_loaded": [
#         {"rule_id": "RD_C23_001", "name": "核心企业白名单检查", "status": "ACTIVE"},
#         {"rule_id": "RD_C23_002", "name": "发票真实性核验", "status": "ACTIVE"},
#         {"rule_id": "RD_C23_003", "name": "担保金额上限检查", "status": "ACTIVE"},
#         {"rule_id": "RD_C23_004", "name": "风险集中度检查", "status": "ACTIVE"},
#         {"rule_id": "RD_C23_005", "name": "综合合规评估", "status": "ACTIVE"}
#     ],
#     "activation_time_ms": 847,
#     "effective_immediately": true,
#     "regulatory_reference": "银发〔2025〕77号"
# }
