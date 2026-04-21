#!/bin/bash
# Case 3 Step 7: 生成决策报告
# 生成CFO级别的税务决策报告

ontology-cli report generate \
    --space "space.tax_apac_2026" \
    --simulation-id "sim_20260421_001" \
    --type tax_decision \
    --format pdf \
    --output "tax_decision_report_2026Q2.pdf"

# 期望输出:
# {
#     "report_id": "report_20260421_001",
#     "report_type": "tax_decision",
#     "format": "pdf",
#     "file_path": "expected_outputs/tax_decision_report_2026Q2.pdf",
#     "sections": [
#         "executive_summary",
#         "scenario_overview",
#         "comparison_matrix",
#         "effective_tax_rate_analysis",
#         "beps_risk_assessment",
#         "pillar2_impact_analysis",
#         "transfer_pricing_compliance",
#         "recommendations",
#         "appendix_data"
#     ],
#     "pages": 12,
#     "generated_at": "2026-04-21T10:15:00Z"
# }
