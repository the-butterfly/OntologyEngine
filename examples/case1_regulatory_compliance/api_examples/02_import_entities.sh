#!/bin/bash
# Case 1 Step 2: 导入供应商数据
# 批量导入供应商、核心企业、发票、合同等数据

ontology-cli entities batch-import \
    --space space.supply_chain_finance \
    --file instances.yaml

# 期望输出:
# {
#     "space_id": "space.supply_chain_finance",
#     "entities_imported": {
#         "Supplier": 5,
#         "CoreEnterprise": 3,
#         "Invoice": 23,
#         "Contract": 10,
#         "GuaranteeRelation": 4
#     },
#     "total_entities": 45,
#     "relations_created": 67
# }
