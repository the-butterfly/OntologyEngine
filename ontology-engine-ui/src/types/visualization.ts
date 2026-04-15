// Visualization API response types

export interface GraphNode {
  id: string;
  type: 'entity' | 'category' | 'metric' | 'rule';
  data: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'relation' | 'metric_dep' | 'rule_input' | 'dependency' | 'component' | 'data_dependency';
  data: Record<string, any>;
}

export interface LayoutConfig {
  type: string;
  rankdir: string;
  nodesep: number;
  ranksep: number;
}

export interface GraphMetadata {
  entity_count: number;
  relation_count: number;
  metric_count: number;
  rule_count: number;
}

export interface SchemaGraphData {
  view_id?: string;
  schema_id?: string;
  graph_type: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout_config?: LayoutConfig;
  metadata: GraphMetadata;
}

export interface RuleChainNode {
  id: string;
  position: { x: number; y: number };
  data: Record<string, any>;
}

export interface RuleChainEdge {
  id: string;
  source: string;
  target: string;
  data: Record<string, any>;
}

export interface DimensionInfo {
  name: string;
  description: string | null;
  applicable_entities: string[];
  rule_count: number;
}

export interface RuleChainGraphData {
  dimension: string;
  nodes: RuleChainNode[];
  edges: RuleChainEdge[];
  dimension_info: DimensionInfo;
}

export interface VisualizationEntityOption {
  entity_id: string;
  concept_type: string;
  label: string;
  active_dimensions: string[];
}

export interface MetricSnapshot {
  entity_id: string;
  dimension: string;
  metrics: Record<string, any>;
  outputs: Record<string, any>;
  decision: string | null;
  decision_reasoning: string | null;
}

export interface ConditionDetail {
  expression: string;
  resolved: string;
  result: boolean;
  explanation: string;
}

export interface ExecutionStepSnapshot {
  step: number;
  rule_id: string;
  rule_name: string;
  rule_type: string;
  condition_expression: string;
  condition_result: boolean | null;
  condition_details: ConditionDetail[];
  context_before: Record<string, any>;
  context_after: Record<string, any>;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
  status: 'pending' | 'executing' | 'passed' | 'failed' | 'skipped';
  duration_ms: number;
  explanation: string;
  affected_metrics: string[];
}

export interface DiffEntry {
  field: string;
  baseline_value: any;
  simulated_value: any;
  change_type: string;
  change_magnitude: number | null;
  impact: string;
}

export interface ImpactChain {
  source_field: string;
  affected_fields: string[];
  description: string;
}

export interface ComparisonResult {
  baseline: Record<string, any>;
  simulated: Record<string, any>;
  diffs: DiffEntry[];
  impact_chains: ImpactChain[];
}

export interface SimulationResult {
  entity_id: string;
  dimension: string;
  simulation_type: string;
  steps: ExecutionStepSnapshot[];
  execution_path: string[];
  skipped_rules: string[];
  final_outputs: Record<string, any>;
  decision: string | null;
  decision_reasoning: string | null;
  alerts: Record<string, any>[];
  comparison: ComparisonResult | null;
  final_context?: {
    entity_data: Record<string, any>;
    computed_metrics: Record<string, any>;
  };
}

export interface SimulationRequest {
  entity_id: string;
  dimension: string;
  overrides?: Record<string, any>;
  dry_run?: boolean;
}
