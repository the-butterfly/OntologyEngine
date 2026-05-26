export interface ViewInfo {
  id: string;
  name: string;
  status: string;
}

export interface Property {
  name: string;
  type: string;
  required?: boolean;
  unique?: boolean;
  description?: string;
}

export interface Relation {
  name: string;
  target: string;
  cardinality?: string;
  description?: string;
}

export interface FactObject {
  id: string;
  name: string;
  description?: string;
  properties?: Property[];
  relations?: Relation[];
  [key: string]: unknown;
}

export interface Categorization {
  id: string;
  name?: string;
  description?: string;
  applicable_to?: string[];
  triggers?: unknown[];
  [key: string]: unknown;
}

export interface AnalyticalElement {
  id: string;
  name?: string;
  description?: string;
  element_type: 'atomic' | 'derived' | 'composite' | 'graph';
  formula?: string;
  dependencies?: string[];
  components?: Array<{ metric: string; weight: number }>;
  overridable?: boolean;
  source?: unknown;
  thresholds?: unknown;
  [key: string]: unknown;
}

export interface SchemaOverview {
  L1: {
    fact_objects: FactObject[];
  };
  L2: {
    categorizations: Categorization[];
  };
  L3: {
    analytical_elements: AnalyticalElement[];
  };
  L4: {
    rule_definitions: RuleDefinition[];
    rule_logics: RuleLogic[];
  };
  loaded?: Record<string, unknown>;
}

export interface ExecutionStepConditionSubCondition {
  type: string;
  expr: string;
  result: boolean;
  error?: string;
}

export interface ExecutionStepInput {
  name: string;
  value: unknown;
  element_type?: string;
}

export interface ExecutionStepOutput {
  name: string;
  value: unknown;
}

export interface ExecutionStep {
  step: number;
  rule_id: string;
  rule_name: string;
  rule_type: string;
  condition_expression?: string;
  condition_result?: boolean;
  condition_sub_conditions?: ExecutionStepConditionSubCondition[];
  context_before?: Record<string, unknown>;
  context_after?: Record<string, unknown>;
  inputs?: ExecutionStepInput[];
  outputs?: ExecutionStepOutput[];
  status: 'passed' | 'skipped' | 'failed';
  explanation: string;
}

export interface ExecutionResult {
  decision: string;
  entity_id: string;
  execution_path?: string[];
  skipped_rules?: string[];
  final_outputs?: Record<string, unknown>;
  steps?: ExecutionStep[];
}

export interface DependencyNode {
  id: string;
  label: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  input_elements: Array<{ id: string; name?: string }>;
  output_elements: Array<{ id: string; name?: string }>;
  logic_count: number;
}

export interface DependencyEdge {
  id: string;
  source: string;
  target: string;
  element: string;
  type: string;
}

export interface MutualExclusion {
  rule_a: string;
  rule_b: string;
  reason: string;
  type: string;
}

export interface DependencyStats {
  total_rules: number;
  dependency_edges: number;
  exclusion_pairs: number;
}

export interface DependencyGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  dependency_edges?: DependencyEdge[];
  mutual_exclusions: MutualExclusion[];
  execution_order: string[];
  stats: DependencyStats;
}

export interface ViewDetails {
  id: string;
  name: string;
  status: string;
  space_id: string;
  dimension?: string;
  entity_count?: number;
  created_at: string;
  updated_at: string;
}

export interface SpaceResponse {
  id: string;
  name: string;
  description?: string;
  domain?: string;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
  entity_count: number;
  relation_count: number;
  rule_definition_count: number;
  rule_logic_count: number;
  view_id?: string;
  view?: ViewInfo;
}

export interface CreateSpaceRequest {
  name: string;
  description?: string;
  domain?: string;
}

export interface RuleDefinition {
  id: string;
  name?: string;
  description?: string;
  rule_type: string;
  priority: number;
  applicable_scope: {
    scope_type: 'global' | 'by_classification';
    classification_path?: string;
    classification_values?: string[];
  };
  target_objects: Array<{
    concept: string;
    filters?: Record<string, unknown>;
  }>;
  input_elements: Array<{
    name: string;
    element_type: string;
    source?: string;
    path?: string;
    required?: boolean;
  }>;
  output_elements: Array<{
    name: string;
    element_type: string;
    destination?: string;
  }>;
  enabled: boolean;
  logic_ids?: string[];
  when?: unknown;
  then_action?: unknown;
  else_action?: unknown;
}

export interface RuleLogic {
  id: string;
  name?: string;
  definition_id: string;
  applicable_conditions: Array<{
    classification?: Record<string, string>;
    match_type?: string;
  }>;
  when?: { expression?: string; allOf?: any[] };
  then_action?: { action_type?: string; output?: Record<string, any> };
  else_action?: { action_type?: string; output?: Record<string, any> };
  version: number;
  environment: string;
  priority?: number;
}

export interface CreateRuleDefinitionRequest {
  id: string;
  name?: string;
  description?: string;
  rule_type?: string;
  priority?: number;
  applicable_scope?: RuleDefinition['applicable_scope'];
  target_objects?: RuleDefinition['target_objects'];
  input_elements?: RuleDefinition['input_elements'];
  output_elements?: RuleDefinition['output_elements'];
  enabled?: boolean;
  logic_ids?: string[];
  when?: unknown;
  then_action?: unknown;
  else_action?: unknown;
}

export interface CreateRuleLogicRequest {
  id: string;
  name?: string;
  definition_id: string;
  applicable_conditions?: RuleLogic['applicable_conditions'];
  when?: unknown;
  then_action?: unknown;
  else_action?: unknown;
  version?: number;
  environment?: string;
}

export interface SpaceVersion {
  version: number;
  space_id: string;
  snapshot_path?: string;
  created_at: string;
  created_by?: string;
  change_description?: string;
  is_stable: boolean;
}

export interface EntityInstance {
  entity_id: string;
  _concept: string;
  [key: string]: unknown;
}

export interface RelationInstance {
  relation_type: string;
  from_entity_id: string;
  to_entity_id: string;
  [key: string]: unknown;
}
