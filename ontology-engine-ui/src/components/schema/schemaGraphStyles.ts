// ============================================================================
// Layer Configuration Constants
// ============================================================================

export type LayerType = 'entity' | 'category' | 'metric' | 'rule';

export interface LayerConfig {
  size: [number, number];
  fill: string;
  stroke: string;
  lineWidth: number;
  radius: number;
  rotation: number;
  labelInside: boolean;
  labelOffsetY: number;
  labelFontSize: number;
  labelColor: string;
}

export const LAYER_CONFIG: Record<LayerType, LayerConfig> = {
  entity: {
    size: [140, 56],
    fill: '#E8F4FD',
    stroke: '#1890FF',
    lineWidth: 2,
    radius: 28, // Full capsule - half of height for pill shape
    rotation: 0,
    labelInside: true,
    labelOffsetY: 0,
    labelFontSize: 12,
    labelColor: '#096DD9',
  },
  category: {
    size: [72, 72],
    fill: '#F9F0FF',
    stroke: '#722ED1',
    lineWidth: 2.5,
    radius: 0,
    rotation: 45,
    labelInside: false,
    labelOffsetY: 14,
    labelFontSize: 11,
    labelColor: '#722ED1',
  },
  metric: {
    size: [52, 52],
    fill: '#F6FFED',
    stroke: '#52C41A',
    lineWidth: 2,
    radius: 26,
    rotation: 0,
    labelInside: false,
    labelOffsetY: 12,
    labelFontSize: 11,
    labelColor: '#389E0D',
  },
  rule: {
    size: [160, 72],
    fill: '#E6F7FF',
    stroke: '#1890FF',
    lineWidth: 2,
    radius: 6,
    rotation: 0,
    labelInside: true,
    labelOffsetY: 0,
    labelFontSize: 12,
    labelColor: '#096DD9',
  },
};

// Edge colors by type
export const EDGE_COLORS: Record<string, string> = {
  relation: '#91D5FF',
  dependency: '#87E8DE',
  component: '#BAE7FF',
  rule_input: '#FFA39E',
  data_dependency: '#FF7B45',
};
