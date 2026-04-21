#!/bin/bash
# Case 1 Step 6: 生成合规审计报告
# 生成符合监管要求的审计报告

ontology-cli report generate \
    --space space.supply_chain_finance \
    --analysis-id analysis_20260421_001 \
    --type compliance_audit \
    --period Q1-2026 \
    --format pdf

# 期望输出:
# {
#     "report_id": "report_c23_2026Q1",
#     "report_type": "compliance_audit",
#     "period": "Q1-2026",
#     "format": "pdf",
#     "sections": [
#         "executive_summary",
#         "regulation_overview",
#         "entities_analyzed",
#         "compliance_results",
#         "failed_entities_detail",
#         "evidence_chains",
#         "recommendations",
#         "appendix"
#     ],
#     "retention_years": 7,
#     "regulatory_reference": "银发〔2025〕77号"
# }
