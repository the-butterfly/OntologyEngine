#!/bin/bash
# Case 3 Step 4: 定义What-If场景
# 定义三个税务架构场景进行对比分析

# 定义场景A: 香港总部模式
ontology-cli simulation define-scenario \
    --space "space.tax_apac_2026" \
    --scenario-id "scenario_A" \
    --scenario-name "香港总部模式" \
    --parameters '{
        "hq_location": "香港",
        "ip_location": "香港",
        "operation_location": "中国",
        "royalty_rate": 0.05,
        "dividend_wht": 0.05,
        "qdmt_applicable": true,
        "qdmt_jurisdiction": "香港"
    }'

# 定义场景B: 新加坡总部模式
ontology-cli simulation define-scenario \
    --space "space.tax_apac_2026" \
    --scenario-id "scenario_B" \
    --scenario-name "新加坡总部模式" \
    --parameters '{
        "hq_location": "新加坡",
        "ip_location": "新加坡",
        "operation_location": "中国",
        "royalty_rate": 0.07,
        "dividend_wht": 0.05,
        "qdmt_applicable": true,
        "qdmt_jurisdiction": "新加坡"
    }'

# 定义场景C: 混合架构模式
ontology-cli simulation define-scenario \
    --space "space.tax_apac_2026" \
    --scenario-id "scenario_C" \
    --scenario-name "混合架构模式" \
    --parameters '{
        "hq_location": "香港+新加坡",
        "ip_location": "香港",
        "operation_location": "新加坡",
        "royalty_rate": 0.05,
        "dividend_wht": 0.05,
        "qdmt_applicable": true,
        "qdmt_jurisdiction": "香港+新加坡"
    }'

# 期望输出:
# {
#     "space_id": "space.tax_apac_2026",
#     "scenarios_defined": [
#         {"scenario_id": "scenario_A", "name": "香港总部模式", "status": "CONFIGURED"},
#         {"scenario_id": "scenario_B", "name": "新加坡总部模式", "status": "CONFIGURED"},
#         {"scenario_id": "scenario_C", "name": "混合架构模式", "status": "CONFIGURED"}
#     ],
#     "total_scenarios": 3
# }
