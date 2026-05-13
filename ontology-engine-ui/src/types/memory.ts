/**
 * Core type definitions for Agent Memory system.
 */

export type MemoryType =
  | 'observation'
  | 'opinion'
  | 'mental_model'
  | 'episode'
  | 'procedure'
  | 'entity'
  | 'rule'
  | 'commitment'
  | 'constraint'
  | 'self_experience'
  | 'task_state'
  | 'fragment';

export type CognitiveLayer = 'opinion' | 'semantic' | 'procedure' | 'perception';

export type BeliefStatus = 'accepted' | 'rejected' | 'pending_review' | 'superseded' | 'under_review';

export type ModelDomain = 'user' | 'task' | 'world' | 'self' | 'system';

export type Visibility = 'private' | 'shared' | 'public';

export type SourceTrustTier = 'high' | 'medium' | 'low' | 'unverified';

export interface CognitiveNode {
  id: string;
  memoryType: MemoryType;
  cognitiveLayer: CognitiveLayer;
  content: string;
  domainId: string;
  spaceId: string;
  visibility: Visibility;
  createdBy: string;
  confidence: number;
  beliefStatus: BeliefStatus;
  occurredAt?: string;
  schemaRef?: string;
  validFrom?: string;
  validTo?: string;
  recordedAt?: string;
  tags: string[];
  attributes: Record<string, string>;
  modelDomain?: ModelDomain;
  sourceTrustTier?: SourceTrustTier;
  scope?: Record<string, any>;
  supersededBy?: string;
  sourceFragmentIds?: string[];
  extractionHint?: string;
}

export interface CognitiveEdge {
  id?: string;
  edgeType: string;
  fromId: string;
  toId: string;
  properties?: Record<string, any>;
}

export interface GraphNode {
  id: string;
  data: CognitiveNode;
}

export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  edgeType: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AgentActivity {
  id: string;
  spaceId: string;
  agentName: string;
  activityType: string;
  timestamp: string;
  operation: string;
  result: string;
  nodeIds: string[];
  durationMs: number;
  success: boolean;
  description?: string;
  metadata?: Record<string, any>;
}

export interface Contradiction {
  id: string;
  nodeId?: string;
  oldValue?: string;
  newValue?: string;
  field?: string;
  description?: string;
  severity?: string;
  involvedNodes?: string[];
  status: 'pending' | 'resolved' | 'ignored' | 'under_review' | 'superseded';
  detectedAt: string;
  resolvedAt?: string;
  resolution?: string;
}

export interface Correction {
  id: string;
  appliedAt: string;
  correctionType: string;
  reason: string;
  originalNodeId: string;
  correctedNodeId: string;
  status: string;
  appliedBy: string;
}

export interface Insight {
  id: string;
  insightType?: string;
  type?: string;
  description: string;
  relatedNodeIds?: string[];
  generatedAt?: string;
  confidence: number;
}

export interface EvidenceChain {
  rootNodeId: string;
  nodes: CognitiveNode[];
  edges: CognitiveEdge[];
  confidence: number;
}

export interface DispositionProfile {
  recencyWeight: number;
  relevanceWeight: number;
  confidenceWeight: number;
  domainWeights: Record<string, number>;
  layerWeights: Record<string, number>;
}

export interface ValidationCase {
  id: string;
  name: string;
  description: string;
  steps: ValidationStep[];
  expectedResults: string[];
}

export interface ValidationStep {
  order: number;
  action: string;
  params: Record<string, any>;
  description: string;
}
