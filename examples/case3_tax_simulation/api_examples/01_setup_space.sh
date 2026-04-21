#!/bin/bash
# Case 3 Step 1: 创建税务分析语义空间
# 通过CLI接口创建新的语义空间

ontology-cli space create \
    --name "tax_analysis_apac" \
    --description "2026年亚太区总部税务架构分析"

# 期望输出:
# {
#     "space_id": "space.tax_apac_2026",
#     "name": "tax_analysis_apac",
#     "description": "2026年亚太区总部税务架构分析",
#     "status": "CREATED",
#     "created_at": "2026-04-21T10:00:00Z"
# }
