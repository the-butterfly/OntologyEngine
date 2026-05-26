// ontology-engine-ui/src/api/spaceApi.ts
// API client for semantic spaces

import axios from 'axios';

const BASE_URL = '/v1';

export interface ViewInfo {
  id: string;
  name: string;
  status: string;
}

// ============================================================================
// Schema Layer Types (L1-L4)
// ============================================================================

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
}

export interface Categorization {
  id: string;
  name?: string;
  description?: string;
  applicable_to?: string[];
  triggers?: unknown[];
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
}

// ============================================================================
// Graph Visualization Types
// ============================================================================

export interface GraphNode {
  id: string;
  type: 'entity' | 'category' | 'metric' | 'rule';
  data: {
    label?: string;
    layer?: string;
    [key: string]: unknown;
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  data?: {
    label?: string;
    [key: string]: unknown;
  };
}

export interface SchemaGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ============================================================================
// Execution Types
// ============================================================================

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

// ============================================================================
// Dependency Graph Types
// ============================================================================

export interface DependencyNode {
  id: string;
  label: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  input_elements: unknown[];
  output_elements: unknown[];
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

export interface DependencyGraph {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  mutual_exclusions: MutualExclusion[];
  execution_order: string[];
  stats: unknown;
}

// ============================================================================
// View Types
// ============================================================================

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

// ============================================================================
// Metric Snapshot Type
// ============================================================================

export interface MetricSnapshot {
  entity_id: string;
  dimension: string;
  metrics: Record<string, unknown>;
  timestamp: string;
}

// ============================================================================
// Instance Graph Visualization Types
// ============================================================================

export interface InstanceGraphNode {
  id: string;
  type: 'entity_instance';
  data: {
    label: string;
    concept: string;
    entity_id: string;
    credit_score?: number | string;
    status?: string;
    result_group?: 'approved' | 'rejected' | 'pending' | 'unknown';
    component_id?: number;
    hop?: number;
    properties: Record<string, unknown>;
  };
  style: {
    fill: string;
    size: number;
  };
}

export interface InstanceGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  data: {
    label: string;
    relation_type: string;
    is_guarantee: boolean;
    is_cycle_edge: boolean;
    properties: Record<string, unknown>;
  };
  style: {
    stroke: string;
    line_width: number;
  };
}

export interface InstanceGraphData {
  space_id: string;
  graph_type: 'instance_graph';
  nodes: InstanceGraphNode[];
  edges: InstanceGraphEdge[];
  grouping: {
    concept_groups: Record<string, string[]>;
    component_groups: string[][];
    hop_groups: Record<string, string[]>;
    result_groups: Record<string, string[]>;
  };
  layout_config: {
    type: 'hybrid';
    primary: 'dagre';
    secondary: 'force';
    seed_entity_id?: string;
  };
  metadata: {
    entity_count: number;
    relation_count: number;
    cycle_count: number;
    concept_counts: Record<string, number>;
    component_count: number;
  };
}

// ============================================================================
// Existing Interfaces (kept for reference)
// ============================================================================

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
  view_id?: string; // Associated consumption view ID
  view?: ViewInfo; // Consumption view details
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

class SpaceApi {
  // Space CRUD (uses /spaces prefix)
  async listSpaces(): Promise<SpaceResponse[]> {
    const response = await axios.get(`${BASE_URL}/spaces`);
    return response.data.data;
  }

  async createSpace(request: CreateSpaceRequest): Promise<SpaceResponse> {
    const response = await axios.post(`${BASE_URL}/spaces`, request);
    return response.data.data;
  }

  async getSpace(spaceId: string): Promise<SpaceResponse> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}`);
    return response.data.data;
  }

  async updateSpace(spaceId: string, updates: Partial<CreateSpaceRequest & { status: string }>): Promise<SpaceResponse> {
    const response = await axios.put(`${BASE_URL}/spaces/${spaceId}`, updates);
    return response.data.data;
  }

  async deleteSpace(spaceId: string): Promise<void> {
    await axios.delete(`${BASE_URL}/spaces/${spaceId}`);
  }

  async activateSpace(spaceId: string): Promise<SpaceResponse> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/activate`);
    return response.data.data;
  }

  async deactivateSpace(spaceId: string): Promise<SpaceResponse> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/deactivate`);
    return response.data.data;
  }

  // L1 Fact Objects (uses /{space_id} prefix)
  async listFactObjects(spaceId: string): Promise<FactObject[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L1/fact-objects`);
    return response.data.data;
  }

  async createFactObject(spaceId: string, factObject: Omit<FactObject, 'id'>): Promise<FactObject> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/schema/L1/fact-objects`, factObject);
    return response.data.data;
  }

  // L2 Categorizations
  async listCategorizations(spaceId: string): Promise<Categorization[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L2/categorizations`);
    return response.data.data;
  }

  async createCategorization(spaceId: string, categorization: Omit<Categorization, 'id'>): Promise<Categorization> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/schema/L2/categorizations`, categorization);
    return response.data.data;
  }

  async deleteCategorization(spaceId: string, categorizationId: string): Promise<void> {
    await axios.delete(`${BASE_URL}/spaces/${spaceId}/schema/L2/categorizations/${categorizationId}`);
  }

  // L3 Analytical Elements
  async listAnalyticalElements(spaceId: string): Promise<AnalyticalElement[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L3/analytical-elements`);
    return response.data.data;
  }

  async createAnalyticalElement(spaceId: string, element: Omit<AnalyticalElement, 'id'>): Promise<AnalyticalElement> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/schema/L3/analytical-elements`, element);
    return response.data.data;
  }

  async deleteAnalyticalElement(spaceId: string, elementId: string): Promise<void> {
    await axios.delete(`${BASE_URL}/spaces/${spaceId}/schema/L3/analytical-elements/${elementId}`);
  }

  // Rule Definitions L4 (uses /{space_id} prefix)
  async listRuleDefinitions(spaceId: string): Promise<RuleDefinition[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/definitions`);
    return response.data.data;
  }

  async createRuleDefinition(spaceId: string, request: CreateRuleDefinitionRequest): Promise<RuleDefinition> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/definitions`, request);
    return response.data.data;
  }

  async getRuleDefinition(spaceId: string, ruleId: string): Promise<RuleDefinition> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/definitions/${ruleId}`);
    return response.data.data;
  }

  async updateRuleDefinition(spaceId: string, ruleId: string, request: CreateRuleDefinitionRequest): Promise<RuleDefinition> {
    const response = await axios.put(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/definitions/${ruleId}`, request);
    return response.data.data;
  }

  async deleteRuleDefinition(spaceId: string, ruleId: string): Promise<void> {
    await axios.delete(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/definitions/${ruleId}`);
  }

  // Rule Logics L4 (uses /{space_id} prefix)
  async listRuleLogics(spaceId: string): Promise<RuleLogic[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/logics`);
    return response.data.data;
  }

  async createRuleLogic(spaceId: string, request: CreateRuleLogicRequest): Promise<RuleLogic> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/logics`, request);
    return response.data.data;
  }

  async getRuleLogic(spaceId: string, logicId: string): Promise<RuleLogic> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/logics/${logicId}`);
    return response.data.data;
  }

  async updateRuleLogic(spaceId: string, logicId: string, request: CreateRuleLogicRequest): Promise<RuleLogic> {
    const response = await axios.put(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/logics/${logicId}`, request);
    return response.data.data;
  }

  async deleteRuleLogic(spaceId: string, logicId: string): Promise<void> {
    await axios.delete(`${BASE_URL}/spaces/${spaceId}/schema/L4/rules/logics/${logicId}`);
  }

  // Versions (uses /{space_id}/versions)
  async listVersions(spaceId: string): Promise<SpaceVersion[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/versions`);
    return response.data.data;
  }

  async createVersion(spaceId: string, description?: string): Promise<SpaceVersion> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/versions`, { description });
    return response.data.data;
  }

  async rollbackToVersion(spaceId: string, version: number): Promise<SpaceResponse> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/versions/${version}/rollback`);
    return response.data.data;
  }

  // Instances (uses /{space_id} prefix)
  async listEntities(spaceId: string, concept?: string): Promise<EntityInstance[]> {
    const params = concept ? { concept } : {};
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/instances/entities`, { params });
    return response.data.data;
  }

  async createEntity(spaceId: string, entity: EntityInstance): Promise<EntityInstance> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/instances/entities`, entity);
    return response.data.data;
  }

  async listRelations(spaceId: string): Promise<RelationInstance[]> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/instances/relations`);
    return response.data.data;
  }

  async createRelation(spaceId: string, relation: RelationInstance): Promise<RelationInstance> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/instances/relations`, relation);
    return response.data.data;
  }

  // Consumption Views
  async listViews(): Promise<ViewDetails[]> {
    const response = await axios.get('/v1/views');
    return response.data.data;
  }

  async getView(viewId: string): Promise<ViewDetails> {
    const response = await axios.get(`/v1/views/${viewId}`);
    return response.data.data;
  }

  // Visualization (Consumption Surface)
  async getSchemaGraph(viewId: string, graphType?: string, layerFilter?: string): Promise<SchemaGraphData> {
    const params: Record<string, string> = {};
    if (graphType) params.graph_type = graphType;
    if (layerFilter) params.layer_filter = layerFilter;
    const response = await axios.get(`/v1/views/${viewId}/schema-graph`, { params });
    return response.data.data;
  }

  // Execution (Consumption Surface)
  async executeAnalyze(viewId: string, entityId: string, dimension?: string, includeTrace?: boolean): Promise<ExecutionResult> {
    const response = await axios.post(`/v1/views/${viewId}/execute/analyze`, {
      entity_id: entityId,
      dimension: dimension || 'credit_assessment',
      include_trace: includeTrace !== false,
    });
    return response.data.data;
  }

  async executeSimulate(viewId: string, entityId: string, dimension?: string, overrides?: Record<string, unknown>): Promise<ExecutionResult> {
    const response = await axios.post(`/v1/views/${viewId}/execute/simulate`, {
      entity_id: entityId,
      dimension: dimension || 'credit_assessment',
      overrides: overrides || null,
      include_trace: true,
    });
    return response.data.data;
  }

  // Consumption view entities
  async listViewEntities(viewId: string, concept?: string): Promise<EntityInstance[]> {
    const params = concept ? { concept } : {};
    const response = await axios.get(`/v1/views/${viewId}/entities`, { params });
    return response.data.data;
  }

  // Rule dependency graph for consumption view
  async getRuleDependencyGraph(viewId: string): Promise<DependencyGraph> {
    const response = await axios.get(`/v1/views/${viewId}/rules/dependency-graph`);
    return response.data.data;
  }

  // Applicable rules for an entity in a consumption view
  async getRulesForEntity(viewId: string, entityId: string, dimension?: string): Promise<RuleDefinition[]> {
    const params = dimension ? { dimension } : {};
    const response = await axios.get(`/v1/views/${viewId}/rules/for-entity/${entityId}`, { params });
    return response.data.data;
  }

  // Metric snapshot for an entity in a consumption view
  async getMetricSnapshot(viewId: string, entityId: string, dimension?: string): Promise<MetricSnapshot> {
    const params = dimension ? { dimension } : {};
    const response = await axios.get(`/v1/views/${viewId}/metrics/${entityId}/snapshot`, { params });
    return response.data.data;
  }

  // Instance Graph Visualization
  async getInstanceGraph(
    spaceId: string,
    params?: {
      seed_entity_id?: string;
      max_hops?: number;
      concept_filter?: string;
      group_by?: string;
    },
  ): Promise<InstanceGraphData> {
    const queryParams: Record<string, string | number> = {};
    if (params?.seed_entity_id) queryParams.seed_entity_id = params.seed_entity_id;
    if (params?.max_hops) queryParams.max_hops = params.max_hops;
    if (params?.concept_filter) queryParams.concept_filter = params.concept_filter;
    if (params?.group_by) queryParams.group_by = params.group_by;
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/instances/graph`, { params: queryParams });
    return response.data.data;
  }

  // Schema YAML import
  async loadSchemaFromYaml(spaceId: string, yamlPath: string, overwrite = false): Promise<SchemaOverview> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/schema/load-yaml`, {
      yaml_path: yamlPath,
      overwrite,
    });
    return response.data.data;
  }

  // Instance YAML import
  async loadInstancesFromYaml(spaceId: string, yamlPath: string, overwrite = false): Promise<{ success: boolean; count: number }> {
    const response = await axios.post(`${BASE_URL}/spaces/${spaceId}/instances/load-yaml`, {
      yaml_path: yamlPath,
      overwrite,
    });
    return response.data.data;
  }

  // Schema overview (all layers)
  async getSchemaOverview(spaceId: string): Promise<SchemaOverview> {
    const response = await axios.get(`${BASE_URL}/spaces/${spaceId}/schema`);
    return response.data.data;
  }
}

export const spaceApi = new SpaceApi();
