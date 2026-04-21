#!/bin/bash
# Case 1 Step 1: 加载扩展Schema
# 包含央行23号文合规检查所需的实体、指标和规则

ontology-cli schema load \
    --space space.supply_chain_finance \
    --file schema.yaml

# 期望输出:
# {
#     "schema_id": "schema.circ23.2026",
#     "space_id": "space.supply_chain_finance",
#     "fact_objects": 6,
#     "metrics": 12,
#     "rules": 8,
#     "new_rules_added": 4,
#     "status": "LOADED"
# }
