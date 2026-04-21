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

export interface ExecutableStep {
  step_id: string;
  step_name: string;
  rule_group_name: string;
  rule_group_type: 'constraint' | 'inference' | 'alert' | 'decision';
  condition: {
    type: 'expression' | 'all_of' | 'any_of';
    expression?: string;
    sub_conditions?: string[];
  };
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

export interface StepExecutionResult {
  step_id: string;
  step_name: string;
  layer_index: number;
  condition_result: boolean;
  condition_detail?: {
    type: string;
    expression?: string;
    result: boolean;
    explanation: string;
  };
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