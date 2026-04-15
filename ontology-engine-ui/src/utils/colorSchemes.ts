// Color schemes for visualization components

// L1 Fact Objects - Blue theme
export const ENTITY_TYPE_COLORS: Record<string, { fill: string; stroke: string; label: string }> = {
  standard: { fill: '#E8F4FD', stroke: '#1890FF', label: '标准实体' },
  concept: { fill: '#E6F7FF', stroke: '#096DD9', label: '概念实体' },
};

// L2 Categorizations - Purple theme
export const CATEGORY_TYPE_COLORS: Record<string, { fill: string; stroke: string; label: string }> = {
  classification: { fill: '#F9F0FF', stroke: '#722ED1', label: '分类体系' },
  taxonomy: { fill: '#FFE7FF', stroke: '#B37FEB', label: '分类法' },
};

// L3 Analytical Elements - varies by metric type
export const METRIC_TYPE_COLORS: Record<string, { fill: string; stroke: string; label: string }> = {
  atomic: { fill: '#F6FFED', stroke: '#52C41A', label: '原子指标' },
  derived: { fill: '#FFF7E6', stroke: '#FA8C16', label: '派生指标' },
  composite: { fill: '#F9F0FF', stroke: '#722ED1', label: '复合指标' },
  graph: { fill: '#FFF1F0', stroke: '#F5222D', label: '图指标' },
};

// L4 Business Logic - varies by rule type
export const RULE_TYPE_COLORS: Record<string, { fill: string; stroke: string; label: string }> = {
  constraint: { fill: '#FFF1F0', stroke: '#F5222D', label: '约束规则' },
  inference: { fill: '#E6F7FF', stroke: '#1890FF', label: '推理规则' },
  alert: { fill: '#FFF7E6', stroke: '#FA8C16', label: '预警规则' },
  decision: { fill: '#F6FFED', stroke: '#52C41A', label: '决策规则' },
};

export const EXECUTION_STATUS_COLORS: Record<string, string> = {
  pending: '#D9D9D9',
  executing: '#1890FF',
  passed: '#52C41A',
  failed: '#F5222D',
  skipped: '#FA8C16',
};

export const EDGE_TYPE_STYLES: Record<string, { stroke: string; lineWidth: number; lineDash: number[]; endArrow: boolean }> = {
  relation: { stroke: '#A0A0A0', lineWidth: 1.5, lineDash: [], endArrow: true },
  metric_dep: { stroke: '#722ED1', lineWidth: 1, lineDash: [4, 4], endArrow: true },
  rule_input: { stroke: '#1890FF', lineWidth: 1, lineDash: [2, 2], endArrow: true },
  rule_flow: { stroke: '#FA8C16', lineWidth: 1.5, lineDash: [], endArrow: true },
};

export const DECISION_COLORS: Record<string, string> = {
  APPROVE: '#52C41A',
  APPROVE_WITH_CONDITIONS: '#FA8C16',
  APPROVE_RESTRICTED: '#FA8C16',
  REVIEW: '#FAAD14',
  REJECT: '#F5222D',
};

export const CHANGE_TYPE_COLORS: Record<string, string> = {
  increased: '#F5222D',
  decreased: '#52C41A',
  new: '#1890FF',
  removed: '#999',
  unchanged: '#D9D9D9',
  changed: '#722ED1',
};
