// ontology-engine-ui/src/api/ruleGroups.ts
// API client for rule groups
// All endpoints require schema_id for semantic space isolation

import { apiClient } from './client';
import type { RuleGroup, RuleStep, SimulationResult } from '../types/rule';

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
    return response.data.data.rule_groups;
  },

  /**
   * Get a rule group by ID
   */
  getById: async (id: string, schemaId?: string): Promise<RuleGroup> => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    const response = await apiClient.get(`/rule-groups/${id}${query}`);
    return response.data.data.rule_group;
  },

  /**
   * Create a new rule group
   */
  create: async (ruleGroup: Partial<RuleGroup>, schemaId: string): Promise<RuleGroup> => {
    const response = await apiClient.post('/rule-groups', {
      ...ruleGroup,
      schema_id: schemaId,
    });
    return response.data.data.rule_group;
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
    const response = await apiClient.put(`/rule-groups/${id}${query}`, updates);
    return response.data.data.rule_group;
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
    return response.data.data.steps;
  },

  /**
   * Add a step to a rule group
   */
  addStep: async (
    name: string,
    step: Partial<RuleStep>,
    schemaId: string
  ): Promise<RuleStep> => {
    const response = await apiClient.post(
      `/rule-groups/${name}/steps?schema_id=${schemaId}`,
      step
    );
    return response.data.data.step;
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
    const response = await apiClient.put(
      `/rule-groups/${name}/steps/${stepId}?schema_id=${schemaId}`,
      updates
    );
    return response.data.data.step;
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
   * Import rule group from YAML
   */
  importYaml: async (yamlContent: string, schemaId: string): Promise<RuleGroup> => {
    const response = await apiClient.post('/rule-groups/import', {
      yaml_content: yamlContent,
      schema_id: schemaId,
    });
    return response.data.data.rule_group;
  },
};

export default ruleGroupsApi;
