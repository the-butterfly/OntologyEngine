// services/memoryApi.ts
// Real API service for cognitive memory system — matches backend endpoints exactly

import type {
  CognitiveNode,
  AgentActivity,
  Contradiction,
  Correction,
  GraphData,
  Insight,
} from '../types/memory';
import type { AuditEntry } from '../types/api';
import type {
  RecallRequest,
  RecallResponse,
  ReflectRequest,
  ReflectResponse,
  MemoryStats,
  AuditResponse,
  DashboardData,
  HeatmapData,
} from '../types/api';
import { createApiService, ApiError } from './createApiService';

const memoryService = createApiService<unknown>({ basePath: '' });

function spacePath(spaceId: string, path: string = ''): string {
  return `/spaces/${spaceId}/memory${path}`;
}

export const memoryApi = {
  // ===== Core Operations =====

  /** POST /spaces/{space_id}/memory/remember */
  async remember(
    spaceId: string,
    content: string,
    memoryType: string = 'fragment',
    options: {
      tags?: string[];
      visibility?: string;
      autoConsolidate?: boolean;
      metadata?: Record<string, any>;
      confidence?: number;
      schemaRef?: string;
      supersedeTarget?: string;
      beliefStatus?: string;
    } = {}
  ): Promise<{ memory_id: string; node_id: string }> {
    return memoryService.post(spacePath(spaceId, '/remember'), {
      content,
      memory_type: memoryType,
      tags: options.tags,
      visibility: options.visibility,
      auto_consolidate: options.autoConsolidate,
      metadata: options.metadata,
      confidence: options.confidence,
      schema_ref: options.schemaRef,
      supersede_target: options.supersedeTarget,
      belief_status: options.beliefStatus,
    });
  },

  /** POST /spaces/{space_id}/memory/recall */
  async recall(spaceId: string, request: RecallRequest): Promise<RecallResponse> {
    return memoryService.post(spacePath(spaceId, '/recall'), {
      query: request.query,
      memory_type: request.memoryType,
      max_results: request.maxResults,
      include_evidence: request.includeEvidence,
      evidence_depth: request.evidenceDepth,
      as_of: request.asOf,
      token_budget: request.tokenBudget,
      belief_status_filter: request.beliefStatusFilter,
      audit_trail: request.auditTrail,
      user_id: request.userId,
      min_confidence: request.minConfidence,
      disposition_override: request.dispositionOverride,
      cognitive_layer: request.cognitiveLayer,
      include_superseded: request.includeSuperseded,
    });
  },

  /** POST /spaces/{space_id}/memory/reflect */
  async reflect(spaceId: string, request: ReflectRequest): Promise<ReflectResponse> {
    return memoryService.post(spacePath(spaceId, '/reflect'), {
      query: request.query,
      max_iterations: request.maxIterations,
      focus_types: request.focusTypes,
      async_mode: request.asyncMode,
      skip_consolidation: request.skipConsolidation,
      skip_forgetting: request.skipForgetting,
      cascade_depth: request.cascadeDepth,
      skip_correction_propagation: request.skipCorrectionPropagation,
    });
  },

  // ===== Approval & Correction =====

  /** POST /spaces/{space_id}/memory/approve */
  async approveNode(
    spaceId: string,
    nodeId: string,
    action: 'approve' | 'reject' = 'approve',
    modifierId: string = 'user',
    comment: string = ''
  ): Promise<void> {
    await memoryService.post(spacePath(spaceId, '/approve'), {
      node_id: nodeId,
      action,
      modifier_id: modifierId,
      comment,
    });
  },

  /** PATCH /spaces/{space_id}/memory/{node_id}/correct */
  async correctNode(
    spaceId: string,
    nodeId: string,
    correctedText: string,
    reason?: string,
    userId?: string
  ): Promise<void> {
    await memoryService.patch(spacePath(spaceId, `/${nodeId}/correct`), {
      corrected_text: correctedText,
      reason,
      user_id: userId,
    });
  },

  // ===== Maintenance Operations =====

  /** POST /spaces/{space_id}/memory/consolidate */
  async consolidate(spaceId: string): Promise<void> {
    await memoryService.post(spacePath(spaceId, '/consolidate'), {});
  },

  /** POST /spaces/{space_id}/memory/forget */
  async forget(spaceId: string, daysElapsed: number = 1): Promise<void> {
    await memoryService.post(spacePath(spaceId, '/forget'), { days_elapsed: daysElapsed });
  },

  // ===== Query Operations =====

  /** GET /spaces/{space_id}/memory/stats */
  async getMemoryStats(spaceId: string): Promise<MemoryStats> {
    return memoryService.get<MemoryStats>(spacePath(spaceId, '/stats'));
  },

  /** GET /spaces/{space_id}/memory/types */
  async getMemoryTypes(spaceId: string): Promise<string[]> {
    return memoryService.get<string[]>(spacePath(spaceId, '/types'));
  },

  /** GET /spaces/{space_id}/memory/audit */
  async getAuditTrail(spaceId: string, limit: number = 50): Promise<AuditEntry[]> {
    const response = await memoryService.get<AuditResponse>(spacePath(spaceId, '/audit'), { limit });
    return response.entries;
  },

  /** GET /spaces/{space_id}/memory/reflect_status */
  async getReflectStatus(reflectionId: string): Promise<{ status: string; progress?: number }> {
    return memoryService.get<{ status: string; progress?: number }>(
      `/memory/reflect_status`,
      { reflection_id: reflectionId }
    );
  },

  // ===== Frontend-specific helpers (map to available endpoints) =====

  /** Get memory graph — uses recall with wildcard query to get all nodes + edges */
  async getMemoryGraph(spaceId: string): Promise<GraphData> {
    const result = await memoryService.post<RecallResponse>(spacePath(spaceId, '/recall'), {
      query: '*',
      max_results: 1000,
      include_evidence: true,
    });
    const edges = (result as any).edges || [];
    return {
      nodes: result.results.map((node: CognitiveNode) => ({ id: node.id, data: node })),
      edges: edges.map((e: any) => ({
        source: e.source,
        target: e.target,
        edgeType: e.edge_type,
      })),
    };
  },

  /** Get agent activities — maps to audit trail */
  async getActivities(spaceId: string): Promise<AuditEntry[]> {
    const response = await memoryService.get<AuditResponse>(spacePath(spaceId, '/audit'), { limit: 50 });
    return response.entries;
  },

  /** Get pending reviews — filters recall results */
  async getPendingReviews(spaceId: string): Promise<CognitiveNode[]> {
    const result = await memoryService.post<RecallResponse>(spacePath(spaceId, '/recall'), {
      query: '*',
      belief_status_filter: 'pending_review',
      max_results: 100,
    });
    return result.results;
  },

  /** Get contradictions — uses /contradictions endpoint */
  async getContradictions(spaceId: string, severity?: string): Promise<Contradiction[]> {
    try {
      const params: Record<string, any> = { limit: 50 };
      if (severity) params.severity = severity;
      return memoryService.get<Contradiction[]>(spacePath(spaceId, '/contradictions'), params);
    } catch {
      return [];
    }
  },

  /** Get corrections — uses /corrections endpoint */
  async getCorrections(spaceId: string): Promise<Correction[]> {
    try {
      return memoryService.get<Correction[]>(spacePath(spaceId, '/corrections'), { limit: 50 });
    } catch {
      return [];
    }
  },

  /** Get evidence chain for a node */
  async getEvidence(spaceId: string, nodeId: string): Promise<any> {
    const response = await memoryService.get<any>(spacePath(spaceId, `/${nodeId}/evidence`));
    return response.data || response;
  },

  /** Get dashboard data — aggregates from stats + audit + recall */
  async getDashboard(spaceId: string): Promise<DashboardData> {
    const [stats, activities, pendingReviews] = await Promise.all([
      memoryService.get<MemoryStats>(spacePath(spaceId, '/stats')).catch(() => null),
      memoryService.get<AuditResponse>(spacePath(spaceId, '/audit'), { limit: 5 }).then(r => r.entries).catch(() => [] as AuditEntry[]),
      memoryService
        .post<RecallResponse>(spacePath(spaceId, '/recall'), {
          query: '*',
          belief_status_filter: 'pending_review',
          max_results: 100,
        })
        .then((r: RecallResponse) => r.results)
        .catch(() => []),
    ]);

    return {
      stats: stats || {
        total: 0,
        by_type: {},
        by_belief: {},
        by_layer: {},
        pending_review: 0,
        superseded: 0,
        expired: 0,
        open_contradictions: 0,
        total_corrections: 0,
        space_id: spaceId,
      },
      recentActivities: activities,
      pendingReviews: stats?.pending_review ?? pendingReviews.length,
      openContradictions: [],
      recentInsights: [],
      heatmapData: {
        layers: ['opinion', 'semantic', 'procedure', 'perception'],
        domains: ['user', 'task', 'world', 'self'],
        cells: [],
      },
    };
  },
};
