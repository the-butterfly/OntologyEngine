# Case 1: Regulatory Compliance — Circular 23

## 愿景旅程
**合规规则资产闭环**: 规则摄入 → 合规分析 → 版本管理 → 回滚 → 证据检索 → 分析总结

## 用户要求
- 用户是风控合规分析师，需要对企业供应链融资申请进行 Circular 23（银发〔2026〕23号）合规检查
- 需要支持规则版本管理、变更影响分析、回滚能力
- 检索结果必须精确、可排序、附带证据链

## 假设
- 核心企业白名单由监管机构定期发布
- 供应商合规检查涉及4个维度：白名单、发票验真、担保限制、风险集中度
- 规则变更需有完整的版本历史和回滚能力

## 项目工具增益
- **Schema/Instance 加载**: 通过 YAML 直接摄入规则和证据
- **版本管理**: 支持规则版本对比和回滚
- **证据检索**: 多跳关联规则条款与证据碎片
- **Reflect 分析**: 自动生成合规风险报告和行动建议

## 测试用例

| TC ID | 名称 | 验收标准 |
|-------|------|----------|
| TC-101 | Schema + instance loading | 白名单和证据碎片成功加载到空间 |
| TC-102 | Baseline compliance analysis | 5家供应商，1家通过（20%），4家失败 |
| TC-103 | Whitelist update + re-analysis | v2026.04.2新增试点企业，SUP_C5变为通过 |
| TC-104 | Version rollback | 回滚到v2026.04.1，SUP_C5恢复为失败 |
| TC-105 | Recall evidence fragments | 检索"银发〔2026〕23号 第八条"返回正确证据 |
| TC-106 | Reflect analysis summary | 生成包含关键发现、风险等级、行动建议的报告 |

## 资产文件

```
assets/
├── whitelist_v2026.04.yaml      # 核心企业白名单 v1（3家企业）
├── whitelist_v2026.04.2.yaml    # 核心企业白名单 v2（新增试点企业）
└── evidence_fragments.yaml      # 证据碎片（审批备忘录、发票OCR、担保合同）

expected_outputs/
├── baseline_v2026.04.1.json              # 基线分析结果（1 pass / 4 fail）
├── baseline_v2026.04.2.json              # 更新后分析结果（2 pass / 3 fail）
├── rollback_to_v2026.04.1.json           # 回滚后分析结果
├── version_diff_v2026.04.1_to_v2026.04.2.json  # 版本差异分析
├── recall_top5_whitelist.json            # 预期检索结果（Top 5）
└── reflect_analysis.json                 # 预期Reflect分析结果
```

## 运行方式

```bash
python examples/case1_regulatory_compliance/run_eval.py
```

## 验证策略说明

本案例使用 **OntologyEngine 模式** 进行验证：
1. 通过 `OntologyEngine.from_config()` 加载 schema.yaml
2. 通过 `engine.load_instances()` 加载 instances.yaml（解析为结构化实体和关系）
3. 通过 `engine.analyze()` 执行多维度分析（credit_assessment, circular23_compliance_check）
4. 通过 `engine.query_entities()` 查询结构化知识资产

**注意**: 本案例不使用 Memory API（`runner.remember()`）直接存储原始 YAML 文本，
而是通过 OntologyEngine 的 Ingestion Pipeline 将 YAML 加工为结构化知识图谱后再检索消费。

## 最终效果
- 合规分析师可在5分钟内完成5家供应商的 Circular 23 合规检查
- 规则变更影响自动分析，回滚能力确保合规安全
- 证据检索精确度≥0.85，支持多跳关联
