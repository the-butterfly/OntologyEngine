#!/bin/bash
# Case 3 Step 2: 加载转让定价Schema
# 将税务分析Schema加载到语义空间

ontology-cli schema load \
    --space "space.tax_apac_2026" \
    --file "schema.yaml"

# 期望输出:
# {
#     "schema_id": "schema.tax_apac.2026",
#     "space_id": "space.tax_apac_2026",
#     "fact_objects": 6,
#     "metrics": 8,
#     "rules": 12,
#     "status": "LOADED"
# }
