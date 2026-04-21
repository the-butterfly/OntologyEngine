// Simulation types for frontend

export interface SimulationSession {
  session_id: string;
  schema_id: string;
  entity_id: string;
  target_output: string;
  created_at: string;
}

export interface ExecutionTree {
  schema_id: string;
  target_output: string;
  layers: ExecutionLayer[];
  total_steps: number;
  rule_group_count: number;
}

export interface ExecutionLayer {
  layer_index: number;
  rule_groups: string[];
  steps: ExecutableStep[];
  output_names: string[];
  input_requirements: InputRequirement[];
}

export type Condition =
  | { type: 'expression'; expression: string }
  | { type: 'all_of'; sub_conditions: string[] }
  | { type: 'any_of'; sub_conditions: string[] };

export interface ExecutableStep {
  step_id: string;
  step_name: string;
  rule_group_name: string;
  rule_group_type: 'constraint' | 'inference' | 'alert' | 'decision';
  condition: Condition;
  action: {
    operator: string;
    params: Record<string, unknown>;
  };
  output_names: string[];
  depends_on: string[];
}

export interface InputRequirement {
  name: string;
  type: 'attribute' | 'metric' | 'flag';
  required: boolean;
  default_value?: unknown;
  description?: string;
}

export interface SimulationResult {
  session_id: string;
  final_output: Record<string, unknown>;
  steps: StepExecutionResult[];
  alerts: Alert[];
  errors: string[];
  execution_time_ms: number;
}

export type ConditionDetail =
  | { type: 'expression'; expression: string; result: boolean; explanation: string }
  | { type: 'all_of'; sub_conditions: string[]; result: boolean; explanation: string }
  | { type: 'any_of'; sub_conditions: string[]; result: boolean; explanation: string };

export interface StepExecutionResult {
  step_id: string;
  step_name: string;
  layer_index: number;
  condition_result: boolean;
  condition_detail?: ConditionDetail;
  action_taken: string;
  output: Record<string, unknown>;
  input_values_used: Record<string, unknown>;
  error?: string;
  duration_ms: number;
}

export interface Alert {
  level: 'info' | 'warning' | 'high' | 'critical';
  type: string;
  message: string;
  source_step?: string;
}

// API Request/Response types
export interface CreateSimulationRequest {
  schema_id: string;
  entity_id?: string;
  target_output: string;
  input_values?: Record<string, unknown>;
}

export interface UpdateSimulationRequest {
  input_values: Record<string, unknown>;
  full_override?: boolean;
}