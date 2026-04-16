// ontology-engine-ui/src/types/dag.ts
// DAG 画布数据类型定义

import type { Node, Edge } from '@xyflow/react';

// ─── 节点类型枚举 ────────────────────────────────────────────────────────────

export type DAGNodeType =
  | 'input'           // 输入要素节点
  | 'output'          // 输出要素节点
  | 'binning'         // 分箱离散化
  | 'scorecard'       // 评分卡计算
  | 'weighted_sum'    // 加权求和
  | 'decision_table'  // 决策矩阵
  | 'llm_judge'       // LLM定性分析
  | 'switch'          // 条件分支
  | 'compute';        // 公式计算

// ─── 算子配置接口 ────────────────────────────────────────────────────────────

/** 分箱配置 */
export interface BinningConfig {
  input: string;
  output: string;
  inclusive_max: boolean;
  bins: Array<{
    range: [number, number];
    label: string;
  }>;
}

/** 评分卡配置 */
export interface ScorecardConfig {
  output: string;
  baseline: number;
  post_formula?: string;
  variables: Array<{
    name: string;
    points: Record<string, number>;
  }>;
}

/** 加权计算配置 */
export interface WeightedSumConfig {
  output: string;
  weights: Array<{
    input: string;
    weight: number;
  }>;
  grade_multipliers?: Record<string, number>;
  grade_input?: string;
}

/** 决策表配置 */
export interface DecisionTableConfig {
  conditions: Array<{
    variable: string;
    format?: string;
  }>;
  output: string;
  matrix: Array<{
    when: Record<string, string>;
    result: string;
    default?: string;
  }>;
}

/** LLM定性分析配置 */
export interface LLMJudgeConfig {
  output: string;
  prompt_template: string;
  input_mapping: Record<string, string>;
  expected_format?: string;
  confidence_threshold?: number;
  timeout_ms?: number;
  fallback_value?: string;
}

/** 条件分支配置 */
export interface SwitchConfig {
  variable: string;
  cases: Array<{
    condition: string;
    operator: string;
    params: Record<string, unknown>;
  }>;
  default?: {
    operator: string;
    params: Record<string, unknown>;
  };
}

/** 计算公式配置 */
export interface ComputeConfig {
  formula: string;
  output_field: string;
}

/** 联合配置类型 */
export type OperatorConfig =
  | BinningConfig
  | ScorecardConfig
  | WeightedSumConfig
  | DecisionTableConfig
  | LLMJudgeConfig
  | SwitchConfig
  | ComputeConfig;

// ─── DAG 节点数据 ─────────────────────────────────────────────────────────────

export interface DAGNodeData {
  type: DAGNodeType;
  label: string;
  config: OperatorConfig;
  inputs: string[];    // 输入变量名列表
  outputs: string[];   // 输出变量名
  status: 'configured' | 'unconfigured' | 'error';
  error?: string;
  [key: string]: unknown; // Index signature for TypeScript compatibility
}

export type DAGNode = Node<DAGNodeData>;

// ─── DAG 边数据 ──────────────────────────────────────────────────────────────

export interface DAGEdgeData {
  sourceHandle?: string;
  targetHandle?: string;
  [key: string]: unknown; // Index signature for TypeScript compatibility
}

export type DAGEdge = Edge<DAGEdgeData>;

// ─── DAG 数据结构 ────────────────────────────────────────────────────────────

export interface DAGData {
  nodes: DAGNode[];
  edges: DAGEdge[];
}

// ─── 节点元数据 ──────────────────────────────────────────────────────────────

export interface NodeMeta {
  type: DAGNodeType;
  label: string;
  description: string;
  color: string;
  icon: string;
  category: 'input' | 'output' | 'calculation' | 'decision' | 'ai';
}

export const NODE_METADATA: Record<DAGNodeType, NodeMeta> = {
  input: {
    type: 'input',
    label: '输入要素',
    description: '从规则组继承的输入变量',
    color: '#1890ff',
    icon: 'Input',
    category: 'input',
  },
  output: {
    type: 'output',
    label: '输出要素',
    description: '从规则组继承的输出变量',
    color: '#52c41a',
    icon: 'Output',
    category: 'output',
  },
  binning: {
    type: 'binning',
    label: '分箱',
    description: '将连续值离散化为区间',
    color: '#722ed1',
    icon: 'BarChart',
    category: 'calculation',
  },
  scorecard: {
    type: 'scorecard',
    label: '评分卡',
    description: '多因素加权评分计算',
    color: '#fa8c16',
    icon: 'Star',
    category: 'calculation',
  },
  weighted_sum: {
    type: 'weighted_sum',
    label: '加权计算',
    description: '多变量加权求和',
    color: '#f5222d',
    icon: 'Calculator',
    category: 'calculation',
  },
  decision_table: {
    type: 'decision_table',
    label: '决策表',
    description: '条件矩阵决策',
    color: '#faad14',
    icon: 'Table',
    category: 'decision',
  },
  llm_judge: {
    type: 'llm_judge',
    label: 'LLM定性分析',
    description: '使用大语言模型进行定性判断',
    color: '#13c2c2',
    icon: 'Robot',
    category: 'ai',
  },
  switch: {
    type: 'switch',
    label: '条件分支',
    description: '根据条件执行不同分支',
    color: '#eb2f96',
    icon: 'ForkRight',
    category: 'decision',
  },
  compute: {
    type: 'compute',
    label: '公式计算',
    description: '自定义公式计算',
    color: '#8c8c8c',
    icon: 'Function',
    category: 'calculation',
  },
};

// ─── 工具函数 ────────────────────────────────────────────────────────────────

export function getDefaultConfig(type: DAGNodeType, defaultInput?: string, defaultOutput?: string): OperatorConfig {
  switch (type) {
    case 'binning':
      return {
        input: defaultInput || '',
        output: defaultOutput || '',
        inclusive_max: true,
        bins: [],
      } as BinningConfig;

    case 'scorecard':
      return {
        output: defaultOutput || '',
        baseline: 600,
        variables: [],
      } as ScorecardConfig;

    case 'weighted_sum':
      return {
        output: defaultOutput || '',
        weights: [],
      } as WeightedSumConfig;

    case 'decision_table':
      return {
        conditions: [],
        output: defaultOutput || '',
        matrix: [],
      } as DecisionTableConfig;

    case 'llm_judge':
      return {
        output: defaultOutput || '',
        prompt_template: '',
        input_mapping: {},
      } as LLMJudgeConfig;

    case 'switch':
      return {
        variable: defaultInput || '',
        cases: [],
      } as SwitchConfig;

    case 'compute':
      return {
        formula: '',
        output_field: defaultOutput || '',
      } as ComputeConfig;

    default:
      return {} as OperatorConfig;
  }
}

export function getNodeInputs(data: DAGNodeData): string[] {
  switch (data.type) {
    case 'binning':
      return [(data.config as BinningConfig).input].filter(Boolean);
    case 'scorecard':
      return (data.config as ScorecardConfig).variables.map(v => v.name);
    case 'weighted_sum':
      return (data.config as WeightedSumConfig).weights.map(w => w.input);
    case 'decision_table':
      return (data.config as DecisionTableConfig).conditions.map(c => c.variable);
    case 'llm_judge':
      return Object.values((data.config as LLMJudgeConfig).input_mapping);
    case 'switch':
      return [(data.config as SwitchConfig).variable].filter(Boolean);
    case 'compute':
      return []; // 从公式中解析
    case 'input':
    case 'output':
    default:
      return [];
  }
}

export function getNodeOutput(data: DAGNodeData): string | null {
  switch (data.type) {
    case 'binning':
      return (data.config as BinningConfig).output || null;
    case 'scorecard':
      return (data.config as ScorecardConfig).output || null;
    case 'weighted_sum':
      return (data.config as WeightedSumConfig).output || null;
    case 'decision_table':
      return (data.config as DecisionTableConfig).output || null;
    case 'llm_judge':
      return (data.config as LLMJudgeConfig).output || null;
    case 'compute':
      return (data.config as ComputeConfig).output_field || null;
    default:
      return null;
  }
}
