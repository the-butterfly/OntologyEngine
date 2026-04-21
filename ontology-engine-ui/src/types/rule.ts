// ontology-engine-ui/src/types/rule.ts
// TypeScript type definitions for rule orchestration system
// Aligned with backend RuleGroupDefinition model

// 核心类型定义 - 与后端 RuleGroupDefinition 完全对齐

export interface RuleGroup {
  id: string;                        // UUID
  name: string;                      // 业务名称
  schemaId: string;                  // 语义空间 ID
  description?: string;
  type: 'constraint' | 'inference' | 'alert' | 'decision';
  priority: number;
  appliesTo: AppliesToConfig;
  inputs: IOElement[];
  outputs: IOElement[];
  preconditions: Precondition[];
  enabled: boolean;
}

export interface AppliesToConfig {
  factObjects: string[];
  categories: Record<string, string[]>;
}

export interface IOElement {
  name: string;
  type?: string;
  metric?: string;
  attribute?: string;
  description?: string;
}

export interface Precondition {
  expression: string;
  fail?: Record<string, unknown>;
}

// 条件从句类型
export type ConditionClause =
  | { type: 'expression'; expression: string }
  | { type: 'all_of'; subConditions: string[] }
  | { type: 'any_of'; subConditions: string[] };

// 动作从句类型
export interface ActionClause {
  operator: string;
  params: Record<string, unknown>;
  outputMapping: Record<string, string>;
}

// 规则步骤 - 对应后端 RuleStep
export interface RuleStep {
  id: string;
  ruleGroup: string;                 // 关联 RuleGroup name
  name: string;
  order: number;
  when: ConditionClause;
  then: ActionClause;
  else?: ActionClause;
  enabled: boolean;
  description?: string;
  tags: string[];
}

// 算子类型
export type OperatorName =
  | 'SET_FLAG' | 'REJECT' | 'COMPUTE' | 'TRIGGER_ALERT'
  | 'BINNING' | 'SCORECARD' | 'WEIGHTED_SUM'
  | 'DECISION_TABLE' | 'LLM_JUDGE';

// 模拟结果类型
export interface SimulationResult {
  rule_group_name: string;
  steps: StepResult[];
  final_output: Record<string, unknown>;
  alerts: unknown[];
  errors: string[];
}

export interface StepResult {
  step_id: string;
  step_name: string;
  condition_result: boolean;
  condition_detail?: {
    type: string;
    expression?: string;
    sub_conditions: unknown[];
    result: boolean;
    explain: string;
  };
  action_taken?: string;
  output: Record<string, unknown>;
  error?: string;
  duration_ms: number;
}

// API 请求/响应类型
export interface ListRuleGroupsParams {
  enabled?: boolean;
}

export interface CreateRuleGroupRequest {
  name: string;
  description?: string;
  type: RuleGroup['type'];
  priority?: number;
  appliesTo?: AppliesToConfig;
  inputs?: IOElement[];
  outputs?: IOElement[];
  preconditions?: Precondition[];
  enabled?: boolean;
}

export type UpdateRuleGroupRequest = Partial<CreateRuleGroupRequest>;

export interface CreateRuleStepRequest {
  name: string;
  order?: number;
  when: ConditionClause;
  then: ActionClause;
  else?: ActionClause;
  enabled?: boolean;
  description?: string;
  tags?: string[];
}

export type UpdateRuleStepRequest = Partial<CreateRuleStepRequest>;

// DAG Execution Types (aligned with backend ExecutionDAG)
export interface DAGNode {
  id: string;
  name: string;
  depends_on: string[];
  in_degree: number;
}

export interface DAGLayer {
  index: number;
  steps: DAGNode[];
}

export interface RuleGroupDagResponse {
  rule_group_name: string;
  total_steps: number;
  total_layers: number;
  layers: DAGLayer[];
}

// Rule Location (Cross-Group Search)
export interface RuleGroupLocateResult {
  name: string;
  outputs: Array<{ name: string; type: string }>;
  depends_on: string[];
}

export interface LocateRuleGroupsResponse {
  output: string;
  rule_groups: RuleGroupLocateResult[];
}
