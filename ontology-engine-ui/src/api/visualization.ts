// API client for visualization endpoints
import axios from 'axios';
import type {
  SchemaGraphData,
  RuleChainGraphData,
  SimulationResult,
  SimulationRequest,
  ExecutionStepSnapshot,
} from '../types/visualization';

const BASE_URL = '/v1/visualize';

export async function fetchSchemaGraph(
  graphType: string,
  layerFilter?: string[],
): Promise<SchemaGraphData> {
  const params = new URLSearchParams({ graph_type: graphType });
  if (layerFilter?.length) params.set('layer_filter', layerFilter.join(','));
  const res = await axios.get(`${BASE_URL}/schema/graph`, { params });
  return res.data.data;
}

export async function fetchRuleChainGraph(dimension: string): Promise<RuleChainGraphData> {
  const res = await axios.get(`${BASE_URL}/rule-chain/${dimension}`);
  return res.data.data;
}

export async function simulateExecution(req: SimulationRequest): Promise<SimulationResult> {
  const res = await axios.post(`${BASE_URL}/simulate`, req);
  return res.data.data;
}

export async function fetchExecutionTrace(
  entityId: string,
  dimension: string,
): Promise<ExecutionStepSnapshot[]> {
  const res = await axios.get(`${BASE_URL}/execution/${entityId}/${dimension}`);
  return res.data.data;
}
