// ontology-engine-ui/src/api/simulation.ts
// API client for simulation endpoints

import { apiClient } from './client';
import type {
  ExecutionTree,
  SimulationResult,
  CreateSimulationRequest,
  UpdateSimulationRequest,
} from '../types/simulation';

export interface CreateSimulationResponse {
  session_id: string;
  execution_tree: ExecutionTree;
  required_inputs: string[];
  current_inputs: Record<string, unknown>;
}

export interface GetSessionResponse {
  session_id: string;
  execution_tree: ExecutionTree;
  current_inputs: Record<string, unknown>;
  result: SimulationResult | null;
}

export interface UpdateSimulationResponse {
  session_id: string;
  updated_inputs: Record<string, unknown>;
  result: SimulationResult | null;
  missing_inputs: string[];
}

export const simulationApi = {
  /**
   * Create a new simulation session and build execution tree
   */
  createTree: async (request: CreateSimulationRequest): Promise<CreateSimulationResponse> => {
    const response = await apiClient.post('/simulation/tree', request);
    return response.data.data;
  },

  /**
   * Get current simulation session state
   */
  getSession: async (sessionId: string): Promise<GetSessionResponse> => {
    const response = await apiClient.get(`/simulation/${sessionId}`);
    return response.data.data;
  },

  /**
   * Update simulation inputs (partial or full override)
   */
  updateInputs: async (sessionId: string, request: UpdateSimulationRequest): Promise<UpdateSimulationResponse> => {
    const response = await apiClient.patch(`/simulation/${sessionId}`, request);
    return response.data.data;
  },

  /**
   * Delete a simulation session
   */
  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/simulation/${sessionId}`);
  },
};

export default simulationApi;