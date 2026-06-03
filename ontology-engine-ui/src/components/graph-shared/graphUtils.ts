export interface GraphNodeData {
  id: string;
  label?: string;
  type?: string;
  [key: string]: unknown;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  type?: string;
  label?: string;
  [key: string]: unknown;
}

export interface GraphGrouping {
  concept_groups?: Record<string, string[]>;
  layer_groups?: Record<string, string[]>;
  belief_groups?: Record<string, string[]>;
  component_groups?: string[][];
  hop_groups?: Record<string, string[]>;
  result_groups?: Record<string, string[]>;
}

export interface GraphMetadata {
  node_count?: number;
  edge_count?: number;
  concept_counts?: Record<string, number>;
  layer_counts?: Record<string, number>;
  belief_counts?: Record<string, number>;
  edge_type_counts?: Record<string, number>;
  [key: string]: unknown;
}

export const COGNITIVE_LAYER_COLORS: Record<string, string> = {
  opinion: '#722ed1',
  semantic: '#1890ff',
  procedure: '#52c41a',
  perception: '#faad14',
};

export const BELIEF_STATUS_COLORS: Record<string, string> = {
  accepted: '#52c41a',
  pending_review: '#faad14',
  superseded: '#8c8c8c',
  rejected: '#ff4d4f',
  contradicted: '#ff4d4f',
};

export const EDGE_TYPE_COLORS: Record<string, string> = {
  CONSOLIDATED_INTO: '#1890ff',
  SUMMARIZED_AS: '#13c2c2',
  LEARNED_INTO: '#52c41a',
  SUPERSEDES: '#fa8c16',
  CONTRADICTS: '#ff4d4f',
  COGNITIVE_RELATES_TO: '#8c8c8c',
  CO_OCCURS_WITH: '#bfbfbf',
  COG_SUPPORTED_BY: '#2f54eb',
  SUPPORTS: '#1890ff',
  PART_OF: '#722ed1',
  RELATES_TO: '#8c8c8c',
};

export const MEMORY_TYPE_COLORS: Record<string, string> = {
  entity: '#1890ff',
  observation: '#722ed1',
  episode: '#13c2c2',
  fragment: '#faad14',
  mental_model: '#eb2f96',
  opinion: '#722ed1',
  procedure: '#52c41a',
  rule: '#2f54eb',
  commitment: '#fa541c',
  constraint: '#f5222d',
  self_experience: '#a0d911',
  task_state: '#ffc53d',
  relation: '#597ef7',
  metrics: '#95de64',
};

export const EDGE_TYPE_LINE_DASH: Record<string, number[]> = {
  SUPERSEDES: [6, 3],
  CONTRADICTS: [4, 4],
  CO_OCCURS_WITH: [2, 2],
};

export function getNodeColor(data: Record<string, unknown>): string {
  const layer = data.cognitive_layer as string;
  if (layer && COGNITIVE_LAYER_COLORS[layer]) return COGNITIVE_LAYER_COLORS[layer];
  const mType = data.memory_type as string;
  if (mType && MEMORY_TYPE_COLORS[mType]) return MEMORY_TYPE_COLORS[mType];
  const concept = data.concept as string;
  if (concept) {
    const colors = ['#1890ff', '#52c41a', '#faad14', '#722ed1', '#13c2c2', '#eb2f96', '#fa541c', '#2f54eb'];
    let hash = 0;
    for (let i = 0; i < concept.length; i++) hash = concept.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  }
  return '#1890ff';
}

export function getEdgeColor(edgeType: string): string {
  return EDGE_TYPE_COLORS[edgeType] || '#8c8c8c';
}

export function getEdgeLineDash(edgeType: string): number[] | undefined {
  return EDGE_TYPE_LINE_DASH[edgeType];
}

export function truncateLabel(text: string, maxLen: number = 20): string {
  if (!text) return '';
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text;
}

export function mapConfidenceToSize(confidence: number, min = 20, max = 50): number {
  const clamped = Math.max(0, Math.min(1, confidence));
  return min + (max - min) * clamped;
}
