// ontology-engine-ui/src/api/ruleGroups.ts
// API client for rule groups
// All endpoints require schema_id for semantic space isolation

import { apiClient } from './client';
import type { RuleGroup, RuleStep, SimulationResult } from '../types/rule';

// ---- Field mapping helpers (backend snake_case ↔ frontend camelCase) ----

/**
 * Generate a UUID v4 (for client-side ID generation when backend requires it).
 */
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Normalize a raw rule group from the backend (snake_case) to the frontend model (camelCase).
 * Handles both old and new backend field naming.
 */
function normalizeRuleGroup(raw: Record<string, unknown>): RuleGroup {
  // applies_to → appliesTo
  const rawAppliesTo = (raw['applies_to'] || raw['appliesTo'] || {}) as Record<string, unknown>;
  const appliesTo = {
    factObjects: (rawAppliesTo['fact_objects'] || rawAppliesTo['factObjects'] || []) as string[],
    categories: (rawAppliesTo['categories'] || {}) as Record<string, string[]>,
  };

  // preconditions
  const preconditions = ((raw['preconditions'] || []) as Array<Record<string, unknown>>).map((p) => ({
    expression: String(p['expression'] || ''),
    fail: p['fail'] as Record<string, unknown> | undefined,
  }));

  // inputs / outputs
  const inputs = ((raw['inputs'] || []) as Array<Record<string, unknown>>).map((i) => ({
    name: String(i['name'] || ''),
    type: i['type'] as string | undefined,
    metric: i['metric'] as string | undefined,
    attribute: i['attribute'] as string | undefined,
    description: i['description'] as string | undefined,
  }));
  const outputs = ((raw['outputs'] || []) as Array<Record<string, unknown>>).map((o) => ({
    name: String(o['name'] || ''),
    type: o['type'] as string | undefined,
  }));

  return {
    id: String(raw['id'] || ''),
    name: String(raw['name'] || ''),
    schemaId: String(raw['schema_id'] || raw['schemaId'] || ''),
    description: String(raw['description'] || ''),
    type: (raw['type'] || 'decision') as RuleGroup['type'],
    priority: Number(raw['priority'] || 100),
    appliesTo,
    inputs,
    outputs,
    preconditions,
    enabled: raw['enabled'] !== false,
  };
}

/**
 * Normalize a raw rule step from the backend.
 * Backend to_dict() returns: step_order (not order), output_mapping, sub_conditions, rule_group
 */
function normalizeRuleStep(raw: Record<string, unknown>): RuleStep {
  // when
  const rawWhen = (raw['when'] || { type: 'expression', expression: '' }) as Record<string, unknown>;
  let when: RuleStep['when'];
  if (rawWhen['type'] === 'all_of') {
    when = {
      type: 'all_of',
      subConditions: (rawWhen['sub_conditions'] || rawWhen['subConditions'] || []) as string[],
    };
  } else if (rawWhen['type'] === 'any_of') {
    when = {
      type: 'any_of',
      subConditions: (rawWhen['sub_conditions'] || rawWhen['subConditions'] || []) as string[],
    };
  } else {
    when = { type: 'expression', expression: String(rawWhen['expression'] || '') };
  }

  // then / else — backend uses output_mapping (snake_case)
  const normalizeAction = (a: Record<string, unknown> | undefined) => {
    if (!a) return undefined;
    return {
      operator: String(a['operator'] || 'COMPUTE'),
      params: (a['params'] || {}) as Record<string, unknown>,
      outputMapping: (a['output_mapping'] || a['outputMapping'] || {}) as Record<string, string>,
    };
  };

  return {
    id: String(raw['id'] || ''),
    // Backend to_dict() uses rule_group (snake_case)
    ruleGroup: String(raw['rule_group'] || raw['ruleGroup'] || ''),
    name: String(raw['name'] || ''),
    // Backend to_dict() uses step_order (not order)
    order: Number(raw['step_order'] ?? raw['order'] ?? 0),
    when,
    then: normalizeAction(raw['then'] as Record<string, unknown>) || { operator: 'COMPUTE', params: {}, outputMapping: {} },
    // Backend to_dict() uses 'else' key
    else: normalizeAction(raw['else'] as Record<string, unknown>),
    enabled: raw['enabled'] !== false,
    description: raw['description'] as string | undefined,
    tags: (raw['tags'] || []) as string[],
  };
}

/**
 * Convert a camelCase RuleGroup to snake_case for the backend.
 */
function serializeRuleGroup(rg: Partial<RuleGroup>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...rg };
  // appliesTo → applies_to
  if (rg.appliesTo) {
    out['applies_to'] = {
      fact_objects: rg.appliesTo.factObjects || [],
      categories: rg.appliesTo.categories || {},
    };
    delete out['appliesTo'];
  }
  // schemaId → schema_id (handled separately)
  delete out['schemaId'];
  return out;
}

/**
 * Convert a camelCase RuleStep to the backend's RuleStepCreateRequest format.
 * Backend requires: id (required!), name, step_order, when, then, else_ (optional)
 */
function serializeRuleStepForCreate(step: Partial<RuleStep>): Record<string, unknown> {
  const serializeCondition = (c: RuleStep['when'] | undefined): Record<string, unknown> => {
    if (!c) return { type: 'expression', expression: '' };
    if (c.type === 'expression') return { type: 'expression', expression: c.expression };
    return { type: c.type, sub_conditions: c.subConditions || [] };
  };

  const serializeAction = (
    a: { operator: string; params: Record<string, unknown>; outputMapping: Record<string, string> } | undefined
  ): Record<string, unknown> | undefined => {
    if (!a) return undefined;
    return {
      operator: a.operator,
      params: a.params || {},
      output_mapping: a.outputMapping || {},
    };
  };

  return {
    id: step.id || generateUUID(),            // Backend requires id (client-generated UUID)
    name: step.name || '',
    step_order: step.order ?? 0,              // Backend expects step_order (not order)
    when: serializeCondition(step.when),
    then: serializeAction(step.then) || { operator: 'COMPUTE', params: {}, output_mapping: {} },
    else_: serializeAction(step.else),        // Backend Pydantic field is else_ (maps to 'else' key)
    enabled: step.enabled !== false,
    description: step.description || '',
    tags: step.tags || [],
  };
}

/**
 * Convert a camelCase RuleStep to the backend's RuleStepUpdateRequest format.
 * Update fields are all optional.
 */
function serializeRuleStepForUpdate(step: Partial<RuleStep>): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  if (step.name !== undefined) out['name'] = step.name;
  if (step.order !== undefined) out['step_order'] = step.order;
  if (step.enabled !== undefined) out['enabled'] = step.enabled;
  if (step.description !== undefined) out['description'] = step.description;
  if (step.tags !== undefined) out['tags'] = step.tags;

  if (step.when) {
    if (step.when.type === 'expression') {
      out['when'] = { type: 'expression', expression: step.when.expression };
    } else {
      out['when'] = { type: step.when.type, sub_conditions: step.when.subConditions || [] };
    }
  }
  if (step.then) {
    out['then'] = {
      operator: step.then.operator,
      params: step.then.params || {},
      output_mapping: step.then.outputMapping || {},
    };
  }
  if (step.else !== undefined) {
    if (step.else) {
      out['else_'] = {
        operator: step.else.operator,
        params: step.else.params || {},
        output_mapping: step.else.outputMapping || {},
      };
    } else {
      out['else_'] = null;
    }
  }

  return out;
}

export const ruleGroupsApi = {
  /**
   * List rule groups for a schema
   */
  list: async (schemaId: string, params?: { enabled?: boolean }): Promise<RuleGroup[]> => {
    const query = new URLSearchParams({ schema_id: schemaId });
    if (params?.enabled !== undefined) {
      query.set('enabled', String(params.enabled));
    }
    const response = await apiClient.get(`/rule-groups?${query}`);
    const raws: Record<string, unknown>[] = response.data.data.rule_groups || [];
    return raws.map(normalizeRuleGroup);
  },

  /**
   * Get a rule group by ID
   */
  getById: async (id: string, schemaId?: string): Promise<RuleGroup> => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    const response = await apiClient.get(`/rule-groups/${id}${query}`);
    return normalizeRuleGroup(response.data.data.rule_group);
  },

  /**
   * Create a new rule group
   */
  create: async (ruleGroup: Partial<RuleGroup>, schemaId: string): Promise<RuleGroup> => {
    const body = serializeRuleGroup(ruleGroup);
    body['schema_id'] = schemaId;
    const response = await apiClient.post('/rule-groups', body);
    return normalizeRuleGroup(response.data.data.rule_group);
  },

  /**
   * Update an existing rule group
   */
  update: async (
    id: string,
    updates: Partial<RuleGroup>,
    schemaId?: string
  ): Promise<RuleGroup> => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    const body = serializeRuleGroup(updates);
    const response = await apiClient.put(`/rule-groups/${id}${query}`, body);
    return normalizeRuleGroup(response.data.data.rule_group);
  },

  /**
   * Delete a rule group
   */
  delete: async (id: string, schemaId?: string): Promise<void> => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    await apiClient.delete(`/rule-groups/${id}${query}`);
  },

  // ===== Nested resources: Rule Steps =====

  /**
   * Get steps for a rule group (by name)
   */
  getSteps: async (name: string, schemaId: string): Promise<RuleStep[]> => {
    const response = await apiClient.get(
      `/rule-groups/${name}/steps?schema_id=${schemaId}`
    );
    const raws: Record<string, unknown>[] = response.data.data.steps || [];
    return raws.map(normalizeRuleStep);
  },

  /**
   * Add a step to a rule group.
   * Backend requires: id (client-provided UUID), name, step_order, when, then, else_
   */
  addStep: async (
    name: string,
    step: Partial<RuleStep>,
    schemaId: string
  ): Promise<RuleStep> => {
    const body = serializeRuleStepForCreate(step);
    const response = await apiClient.post(
      `/rule-groups/${name}/steps?schema_id=${schemaId}`,
      body
    );
    return normalizeRuleStep(response.data.data.step);
  },

  /**
   * Update a step in a rule group
   */
  updateStep: async (
    name: string,
    stepId: string,
    updates: Partial<RuleStep>,
    schemaId: string
  ): Promise<RuleStep> => {
    const body = serializeRuleStepForUpdate(updates);
    const response = await apiClient.put(
      `/rule-groups/${name}/steps/${stepId}?schema_id=${schemaId}`,
      body
    );
    return normalizeRuleStep(response.data.data.step);
  },

  /**
   * Delete a step from a rule group
   */
  deleteStep: async (
    name: string,
    stepId: string,
    schemaId: string
  ): Promise<void> => {
    await apiClient.delete(
      `/rule-groups/${name}/steps/${stepId}?schema_id=${schemaId}`
    );
  },

  /**
   * Reorder steps within a rule group
   */
  reorderSteps: async (
    name: string,
    stepIds: string[],
    schemaId: string
  ): Promise<void> => {
    await apiClient.put(
      `/rule-groups/${name}/steps/reorder?schema_id=${schemaId}`,
      { step_ids: stepIds }
    );
  },

  // ===== Simulation =====

  /**
   * Simulate rule execution
   */
  simulate: async (
    name: string,
    schemaId: string,
    entityData: Record<string, unknown>
  ): Promise<SimulationResult> => {
    const response = await apiClient.post(
      `/rule-groups/${name}/simulate?schema_id=${schemaId}`,
      { entity_data: entityData }
    );
    return response.data;
  },

  // ===== YAML Import/Export =====

  /**
   * Export rule group as YAML
   */
  exportYaml: async (name: string, schemaId: string): Promise<string> => {
    const response = await apiClient.get(
      `/rule-groups/${name}/export?schema_id=${schemaId}`
    );
    return response.data.data.yaml_content;
  },

  /**
   * Import rule group from YAML content string
   */
  importYaml: async (yamlContent: string, schemaId: string): Promise<RuleGroup> => {
    const response = await apiClient.post('/rule-groups/import', {
      yaml_content: yamlContent,
      schema_id: schemaId,
    });
    return normalizeRuleGroup(response.data.data.rule_group);
  },

  /**
   * Import rule group from a YAML file path (server-side path via management API)
   */
  importYamlFromPath: async (filePath: string, schemaId: string): Promise<unknown> => {
    const loadResponse = await apiClient.post(
      `/management/schemas/${schemaId}/load-from-yaml`,
      { file_path: filePath, overwrite: false }
    );
    return loadResponse.data;
  },
};

export default ruleGroupsApi;
