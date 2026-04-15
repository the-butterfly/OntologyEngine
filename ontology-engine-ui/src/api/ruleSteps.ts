// ontology-engine-ui/src/api/ruleSteps.ts
// API client for rule steps (nested under rule groups)

import { apiClient } from './client';
import type { RuleStep } from '../types/rule';

export const ruleStepsApi = {
  /**
   * Get all steps for a rule group
   */
  list: async (ruleGroupName: string, schemaId: string): Promise<RuleStep[]> => {
    const response = await apiClient.get(
      `/rule-groups/${ruleGroupName}/steps?schema_id=${schemaId}`
    );
    return response.data.data.steps;
  },

  /**
   * Get a specific step
   */
  get: async (
    ruleGroupName: string,
    stepId: string,
    schemaId: string
  ): Promise<RuleStep> => {
    const response = await apiClient.get(
      `/rule-groups/${ruleGroupName}/steps/${stepId}?schema_id=${schemaId}`
    );
    return response.data.data.step;
  },

  /**
   * Create a new step
   */
  create: async (
    ruleGroupName: string,
    step: Partial<RuleStep>,
    schemaId: string
  ): Promise<RuleStep> => {
    const response = await apiClient.post(
      `/rule-groups/${ruleGroupName}/steps?schema_id=${schemaId}`,
      step
    );
    return response.data.data.step;
  },

  /**
   * Update an existing step
   */
  update: async (
    ruleGroupName: string,
    stepId: string,
    updates: Partial<RuleStep>,
    schemaId: string
  ): Promise<RuleStep> => {
    const response = await apiClient.put(
      `/rule-groups/${ruleGroupName}/steps/${stepId}?schema_id=${schemaId}`,
      updates
    );
    return response.data.data.step;
  },

  /**
   * Delete a step
   */
  delete: async (
    ruleGroupName: string,
    stepId: string,
    schemaId: string
  ): Promise<void> => {
    await apiClient.delete(
      `/rule-groups/${ruleGroupName}/steps/${stepId}?schema_id=${schemaId}`
    );
  },

  /**
   * Reorder steps within a rule group
   */
  reorder: async (
    ruleGroupName: string,
    stepIds: string[],
    schemaId: string
  ): Promise<void> => {
    await apiClient.put(
      `/rule-groups/${ruleGroupName}/steps/reorder?schema_id=${schemaId}`,
      { step_ids: stepIds }
    );
  },
};

export default ruleStepsApi;
