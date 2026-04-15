// ontology-engine-ui/src/api/operators.ts
// API client for rule operators

import { apiClient } from './client';
import type { OperatorName } from '../types/rule';

export interface OperatorInfo {
  name: OperatorName;
  description: string;
  category: 'basic' | 'advanced';
}

export interface OperatorSchema {
  name: OperatorName;
  description: string;
  parameters: OperatorParameter[];
  outputFields: string[];
}

export interface OperatorParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  required: boolean;
  defaultValue?: unknown;
  description?: string;
  options?: string[];  // For enum-like parameters
}

export const operatorsApi = {
  /**
   * List all available operators
   */
  list: async (): Promise<OperatorInfo[]> => {
    const response = await apiClient.get('/operators');
    return response.data.data.operators;
  },

  /**
   * Get the schema (parameters) for a specific operator
   */
  getSchema: async (operatorName: string): Promise<OperatorSchema> => {
    const response = await apiClient.get(`/operators/${operatorName}/schema`);
    return response.data.data.schema;
  },
};

export default operatorsApi;
