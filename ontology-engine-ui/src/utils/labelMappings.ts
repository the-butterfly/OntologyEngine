// Chinese label mappings for display

export const METRIC_LABELS: Record<string, string> = {
  total_invoice_amount_90d: '近90天发票总额',
  invoice_count_90d: '近90天发票数',
  overdue_invoice_amount: '逾期发票金额',
  total_contract_amount: '合同总金额',
  avg_monthly_tax_revenue: '月均纳税额',
  tax_compliance_score: '税务合规评分',
  negative_news_count_90d: '近90天负面新闻数',
  core_enterprise_count: '合作核心企业数',
  overdue_invoice_ratio: '逾期发票占比',
  avg_invoice_amount: '平均发票金额',
  contract_utilization_rate: '合同执行率',
  business_stability_score: '业务稳定性评分',
  guarantee_chain_depth: '担保链深度',
  has_guarantee_circle: '是否存在担保圈',
  network_centrality_score: '网络中心性得分',
  credit_score: '综合信用评分',
  reputation_score: '声誉风险评分',
  guarantee_risk_score: '担保风险评分',
  credit_grade: '信用等级',
  eligible: '准入资格',
  credit_limit: '授信额度',
  interest_rate: '利率',
  final_decision: '最终决策',
  approved_credit_limit: '批准额度',
};

export const CONCEPT_LABELS: Record<string, string> = {
  Supplier: '供应商',
  CoreEnterprise: '核心企业',
  Invoice: '发票',
  Contract: '合同',
  LogisticsRecord: '物流记录',
  GuaranteeRelation: '担保关系',
};

export const CREDIT_SCORE_WEIGHTS: Record<string, number> = {
  business_stability_score: 0.30,
  tax_compliance_score: 0.25,
  network_centrality_score: 0.15,
  reputation_score: 0.15,
  guarantee_chain_depth: 0.15,
};

export function formatMoney(value: any): string {
  try {
    const num = typeof value === 'object' && value.value ? value.value : Number(value);
    if (num >= 100_000_000) return `${(num / 100_000_000).toFixed(2)}亿元`;
    if (num >= 10_000) return `${(num / 10_000).toFixed(2)}万元`;
    return `${num.toFixed(0)}元`;
  } catch {
    return String(value);
  }
}
