/**
 * API type definitions for Agent Memory operations.
 */

import type { CognitiveNode, AgentActivity, Contradiction, Correction, Insight, GraphData, DispositionProfile } from './memory';

export interface RecallRequest {
  query: string;
  memoryType?: string;
  maxResults?: number;
  includeEvidence?: boolean;
  evidenceDepth?: number;
  asOf?: string;
  tokenBudget?: number;
  beliefStatusFilter?: string;
  auditTrail?: boolean;
  userId?: string;
  minConfidence?: number;
  dispositionOverride?: Partial<DispositionProfile>;
  cognitiveLayer?: string;
  includeSuperseded?: boolean;
}

export interface RecallResponse {
  query: string;
  results: CognitiveNode[];
  totalCount: number;
  executionTimeMs: number;
  layers?: string[];
}

export interface ReflectRequest {
  query: string;
  maxIterations?: number;
  focusTypes?: string[];
  asyncMode?: boolean;
  skipConsolidation?: boolean;
  skipForgetting?: boolean;
  cascadeDepth?: number;
  skipCorrectionPropagation?: boolean;
}

export interface ReflectResponse {
  taskId: string;
  status: string;
  report?: {
    summary: string;
    insights: Insight[];
    contradictions: Contradiction[];
    consolidatedNodes: string[];
    forgottenNodes: string[];
    totalIterations?: number;
    processedNodes?: number;
    newNodes?: number;
    updatedNodes?: number;
  };
}

export interface MemoryStats {
  total: number;
  by_type: Record<string, number>;
  by_belief: Record<string, number>;
  by_layer: Record<string, number>;
  space_id: string;
  pending_review?: number;
  superseded?: number;
  expired?: number;
  open_contradictions?: number;
  total_corrections?: number;
}

export interface AuditEntry {
  id: string;
  memory_type: string;
  content: string;
  belief_status: string;
  superseded_by?: string;
  updated_at: string;
}

export interface AuditResponse {
  entries: AuditEntry[];
  space_id: string;
}

export interface DashboardData {
  stats: MemoryStats;
  recentActivities: AuditEntry[];
  pendingReviews: number;
  openContradictions: Contradiction[];
  recentInsights: Insight[];
  heatmapData: HeatmapData;
}

export interface HeatmapData {
  layers: string[];
  domains: string[];
  cells: Array<{
    layer: string;
    domain: string;
    averageConfidence: number;
    intensity: number;
  }>;
}

export interface RememberRequest {
  content: string;
  spaceId: string;
  memoryType: string;
  visibility?: string;
  createdBy?: string;
  confidence?: number;
  beliefStatus?: string;
  occurredAt?: string;
  schemaRef?: string;
  validFrom?: string;
  validTo?: string;
  recordedAt?: string;
  tags?: string[];
  metadata?: Record<string, any>;
  modelDomain?: string;
  sourceTrustTier?: string;
  scope?: Record<string, any>;
  autoConsolidate?: boolean;
  supersedeTarget?: string;
  supersedeReason?: string;
}
