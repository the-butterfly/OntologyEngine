#!/bin/bash
# Case 3 Step 3: 导入子公司及交易数据
# 批量导入子公司、关联交易、转让定价记录

ontology-cli entities batch-import \
    --space "space.tax_apac_2026" \
    --file "instances.yaml"

# 期望输出:
# {
#     "space_id": "space.tax_apac_2026",
#     "entities_imported": {
#         "Subsidiary": 3,
#         "IntercompanyTransaction": 6,
#         "TransferPricingRecord": 6,
#         "TaxTreaty": 3,
#         "PermanentEstablishment": 2
#     },
#     "total_entities": 20,
#     "relations_created": 42,
#     "validation_passed": true
# }
