// API client for visualization endpoints
import axios from 'axios';
import type {
  ExecutionStepSnapshot,
  MetricSnapshot,
  RuleChainGraphData,
  SchemaGraphData,
  SimulationRequest,
  SimulationResult,
  VisualizationEntityOption,
} from '../types/visualization';

const BASE_URL = '/v1/visualize';

export class ApiError extends Error {
  constructor(
    message: string,
    public code?: string,
    public statusCode?: number
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function handleResponse<T>(res: any): T {
  if (res.data && res.data.success === false) {
    const error = res.data.error;
    throw new ApiError(
      error?.message || 'Unknown error',
      error?.code,
      res.status
    );
  }
  return res.data.data;
}

function normalizeAxiosError(err: unknown): never {
  if (err instanceof ApiError) throw err;
  if (axios.isAxiosError(err)) {
    throw new ApiError(
      err.response?.data?.error?.message || err.message,
      err.response?.data?.error?.code,
      err.response?.status
    );
  }
  throw new ApiError('Network error');
}

export async function fetchSchemaGraph(
  graphType: string,
  layerFilter?: string[],
): Promise<SchemaGraphData> {
  try {
    const params = new URLSearchParams({ graph_type: graphType });
    if (layerFilter?.length) params.set('layer_filter', layerFilter.join(','));
    const res = await axios.get(`${BASE_URL}/schema/graph`, { params });
    return handleResponse<SchemaGraphData>(res);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchVisualizationEntities(
  concept = 'Supplier',
  dimension?: string,
): Promise<VisualizationEntityOption[]> {
  try {
    const params = new URLSearchParams();
    if (concept) params.set('concept', concept);
    if (dimension) params.set('dimension', dimension);
    const res = await axios.get(`${BASE_URL}/entities`, { params });
    return handleResponse<VisualizationEntityOption[]>(res);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchMetricSnapshot(
  entityId: string,
  dimension = 'credit_assessment',
): Promise<MetricSnapshot> {
  try {
    const params = new URLSearchParams({ dimension });
    const res = await axios.get(`${BASE_URL}/metrics/${entityId}`, { params });
    return handleResponse<MetricSnapshot>(res);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchRuleChainGraph(dimension: string): Promise<RuleChainGraphData> {
  try {
    const res = await axios.get(`${BASE_URL}/rule-chain/${dimension}`);
    return handleResponse<RuleChainGraphData>(res);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function simulateExecution(req: SimulationRequest): Promise<SimulationResult> {
  try {
    const res = await axios.post(`${BASE_URL}/simulate`, req);
    return handleResponse<SimulationResult>(res);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchExecutionTrace(
  entityId: string,
  dimension: string,
): Promise<ExecutionStepSnapshot[]> {
  try {
    const res = await axios.get(`${BASE_URL}/execution/${entityId}/${dimension}`);
    return handleResponse<ExecutionStepSnapshot[]>(res);
  } catch (err) {
    normalizeAxiosError(err);
  }
}
