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
