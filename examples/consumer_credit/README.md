# 个人消费信贷风险评估案例

> 端到端案例：基于借款人画像的贷款申请风险评估

## 概述

本案例演示 OntologyEngine **Schema v2** 在个人消费信贷场景下的完整推理链路：

```
Schema (schema.yaml) → 实例数据 → OntologyEngine → 审批决策
```

### 核心能力

- **五维评分卡**: 财务偿债力 / 历史还款 / 稳定性 / 行为风控 / 关系网络
- **多产品分流**: 快贷 / 分期贷 / 大额信贷 三套利率 + 审批规则
- **图算法指标**: 共借人/担保人关系网络风险传导
- **6 个验收 TC**: 覆盖正常路径 / 拒绝路径 / 产品分流 / 图算法 / What-if

## 核心概念

### L1 事实对象

| 实体 | 说明 |
|------|------|
| `Borrower` | 借款人（核心分析对象） |
| `LoanApplication` | 贷款申请单 |
| `RepaymentRecord` | 历史还款记录 |

### L2 分类维度

| 维度 ID | 业务场景 |
|---------|---------|
| `loan_risk_assessment` | 贷款申请提交时触发 |
| `overdue_monitoring` | 持续逾期监控 |
| `relationship_risk` | 关系网络风险传导 |

### L3 指标体系

| 类型 | 示例 |
|------|------|
| 原子 | `monthly_income_value`, `credit_bureau_score` |
| 派生 | `debt_to_income_ratio`, `repayment_rate_24m` |
| 复合 | `credit_risk_score`（五维加权） |
| 图 | `co_borrower_risk_count`, `network_risk_score` |

### L4 规则链路

| 规则 | 类型 | 说明 |
|------|------|------|
| RD101 | 一票否决 | 黑名单/当前逾期 → 直接拒绝 |
| RD102 | 基础准入 | 年龄/收入/就业稳定性 |
| RD103 | 偿债评估 | 贷后 DTI 压力测试 |
| RD104 | 信用评分 | 五维评分卡（按产品分流） |
| RD105 | 网络风险 | 共借人逾期预警 |
| RD106 | 利率定价 | 按风险等级 + 产品类型 |
| RD107 | 最终决策 | 审批结果 + 批准额度 |

## 测试用例

完整测试用例定义见 [`testcases.yaml`](./testcases.yaml)。

| TC ID | 场景 | 关键验证点 |
|--------|------|-----------|
| TC-C01 | 优质借款人分期贷 | 五维评分卡、APPROVED 路径 |
| TC-C02 | 优质借款人快贷 | 产品分流（RL104 快贷宽松评分） |
| TC-C03 | 中等风险快贷拒绝 | 收入不稳定 → REJECTED |
| TC-C04 | 中等风险大额拒绝 | 模拟模式、R4 拒绝逻辑 |
| TC-C05 | 关联风险图算法 | 共借人逾期 count=1 → 预警 + 减额批准 |
| TC-C06 | 黑名单一票否决 | 短路执行，仅执行 1 条规则 |

## 快速开始

```bash
# 加载 Schema
python -c "
import asyncio
from ontology_engine.core.schema.loader import SchemaLoader
from ontology_engine.storage.duckdb import DuckDBStorage
from ontology_engine.services.analysis_service import AnalysisService

async def main():
    loader = SchemaLoader('examples/consumer_credit/schema.yaml')
    space = await loader.load()
    print(f'Schema loaded: {len(space.layers.l1_fact_objects)} entities')

asyncio.run(main())
"
```

## 文件结构

```
examples/consumer_credit/
├── schema.yaml      # 完整 Schema v2 定义（canonical grammar）
├── testcases.yaml   # 6 个验收用例
└── README.md        # 本文件
```

## 相关文档

- **Schema 设计**: [`examples/supply_chain_finance/SCHEMA_DESIGN.md`](../supply_chain_finance/SCHEMA_DESIGN.md) — Schema v2 设计原理
- **Canonical Grammar**: [`docs/05-schema-v2/09-canonical-schema-spec.md`](../../docs/05-schema-v2/09-canonical-schema-spec.md)
- **案例审视报告**: [`docs/09-examples/REVIEW_REPORT.md`](../../docs/09-examples/REVIEW_REPORT.md)
