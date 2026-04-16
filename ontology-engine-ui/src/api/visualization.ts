// API client for visualization endpoints
import axios from 'axios';
import { spaceApi } from './spaceApi';
import type {
  ExecutionStepSnapshot,
  MetricSnapshot,
  RuleChainGraphData,
  SchemaGraphData,
  SimulationRequest,
  SimulationResult,
  VisualizationEntityOption,
} from '../types/visualization';

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
  viewId: string,
  graphType: string,
  layerFilter?: string[],
): Promise<SchemaGraphData> {
  try {
    return await spaceApi.getSchemaGraph(viewId, graphType, layerFilter?.join(','));
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchVisualizationEntities(
  viewId: string,
  concept = 'Supplier',
): Promise<VisualizationEntityOption[]> {
  try {
    const entities = await spaceApi.listViewEntities(viewId, concept);
    // Transform EntityInstance[] to VisualizationEntityOption[]
    return entities.map((e) => ({
      entity_id: e.entity_id,
      concept_type: e._concept || concept,
      label: ((e.properties as Record<string, unknown>)?.name as string) || e.entity_id,
      active_dimensions: [],
    }));
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchMetricSnapshot(
  viewId: string,
  entityId: string,
  dimension = 'credit_assessment',
): Promise<MetricSnapshot> {
  try {
    return await spaceApi.getMetricSnapshot(viewId, entityId, dimension);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchRuleChainGraph(
  viewId: string,
): Promise<RuleChainGraphData> {
  try {
    return await spaceApi.getRuleDependencyGraph(viewId);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function simulateExecution(
  viewId: string,
  req: SimulationRequest,
): Promise<SimulationResult> {
  try {
    // Uses spaceApi.executeSimulate which calls POST /v1/consumption/views/{viewId}/execute/simulate
    return await spaceApi.executeSimulate(viewId, req.entity_id, req.dimension, req.overrides);
  } catch (err) {
    normalizeAxiosError(err);
  }
}

export async function fetchExecutionTrace(
  viewId: string,
  entityId: string,
  dimension: string,
): Promise<ExecutionStepSnapshot[]> {
  try {
    // Uses spaceApi.executeAnalyze which calls POST /v1/consumption/views/{viewId}/execute/analyze
    return await spaceApi.executeAnalyze(viewId, entityId, dimension, true);
  } catch (err) {
    normalizeAxiosError(err);
  }
}
