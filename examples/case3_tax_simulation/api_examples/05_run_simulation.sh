#!/bin/bash
# Case 3 Step 5: 执行干运行模拟
# 在内存中执行What-If模拟，不持久化任何数据

ontology-cli simulation run \
    --space "space.tax_apac_2026" \
    --mode dry_run \
    --scenarios "scenario_A,scenario_B,scenario_C"

# 期望输出:
# {
#     "simulation_id": "sim_20260421_001",
#     "space_id": "space.tax_apac_2026",
#     "mode": "dry_run",
#     "execution_mode": "in_memory_only",
#     "results": [
#         {
#             "scenario_id": "scenario_A",
#             "scenario_name": "香港总部模式",
#             "effective_tax_rate": 0.132,
#             "annual_tax_cost_cny": 45000000,
#             "beps_risk_level": "LOW",
#             "pillar2_exposure": false,
#             "tax_efficiency_score": 82
#         },
#         {
#             "scenario_id": "scenario_B",
#             "scenario_name": "新加坡总部模式",
#             "effective_tax_rate": 0.141,
#             "annual_tax_cost_cny": 52000000,
#             "beps_risk_level": "LOW",
#             "pillar2_exposure": false,
#             "tax_efficiency_score": 78
#         },
#         {
#             "scenario_id": "scenario_C",
#             "scenario_name": "混合架构模式",
#             "effective_tax_rate": 0.128,
#             "annual_tax_cost_cny": 48000000,
#             "beps_risk_level": "MEDIUM",
#             "pillar2_exposure": true,
#             "tax_efficiency_score": 75
#         }
#     ],
#     "total_execution_time_ms": 744,
#     "persistence": false
# }
