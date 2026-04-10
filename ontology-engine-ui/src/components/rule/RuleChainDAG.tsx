import { useEffect, useRef, useCallback } from 'react';
import { Graph } from '@antv/g6';
import { RULE_TYPE_COLORS, EXECUTION_STATUS_COLORS } from '../../utils/colorSchemes';
import type { RuleChainGraphData, ExecutionStepSnapshot, RuleChainNode, RuleChainEdge } from '../../types/visualization';

interface RuleChainDAGProps {
  chainData: RuleChainGraphData;
  executionSteps?: ExecutionStepSnapshot[];
  currentStep?: number;
  onNodeClick?: (nodeId: string) => void;
}

export default function RuleChainDAG({ 
  chainData, 
  executionSteps = [],
  currentStep = 0,
  onNodeClick 
}: RuleChainDAGProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isDestroyedRef = useRef(false);

  const getStepStatus = useCallback((nodeId: string): string => {
    const stepIndex = executionSteps.findIndex(s => s.rule_id === nodeId);
    if (stepIndex === -1) return 'pending';
    if (stepIndex + 1 === currentStep) return 'executing';
    if (stepIndex + 1 < currentStep) return executionSteps[stepIndex].status;
    return 'pending';
  }, [executionSteps, currentStep]);

  const renderGraph = useCallback(async () => {
    if (!containerRef.current) return;
    if (isDestroyedRef.current) return;

    // Validate data
    if (!chainData || !chainData.nodes || chainData.nodes.length === 0) {
      console.warn('RuleChainDAG: No valid data to render');
      return;
    }

    // Destroy existing graph
    if (graphRef.current) {
      try {
        graphRef.current.destroy();
      } catch (e) {
        // Ignore destroy errors
      }
      graphRef.current = null;
    }

    if (isDestroyedRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    const g6Data = transformToG6(chainData, getStepStatus);
    
    if (!g6Data.nodes || g6Data.nodes.length === 0) {
      console.warn('RuleChainDAG: No nodes after transform');
      return;
    }

    try {
      const graph = new Graph({
        container,
        width,
        height,
        autoFit: 'view',
        padding: [40, 40, 40, 40],
        data: g6Data,
        node: {
          type: 'rect',
          style: {
            size: [200, 90],
            radius: 8,
            fill: (d: any) => getNodeFill(d.data, getStepStatus(d.id)),
            stroke: (d: any) => getNodeStroke(d.data, getStepStatus(d.id)),
            lineWidth: (d: any) => {
              const status = getStepStatus(d.id);
              return status === 'executing' ? 3 : 2;
            },
            shadowColor: (d: any) => {
              const status = getStepStatus(d.id);
              if (status === 'executing') return '#1890ff';
              if (status === 'passed') return '#52c41a';
              return 'rgba(0,0,0,0.1)';
            },
            shadowBlur: (d: any) => {
              const status = getStepStatus(d.id);
              return status === 'executing' ? 16 : 4;
            },
            shadowOffsetX: 0,
            shadowOffsetY: 2,
            labelText: (d: any) => '', // We'll use custom rendering
          },
        },
        edge: {
          style: {
            stroke: '#A0A0A0',
            lineWidth: 1.5,
            endArrow: true,
            labelText: (d: any) => d.data?.description || '',
            labelFontSize: 10,
            labelFill: '#666',
            labelBackground: true,
            labelBackgroundFill: '#fff',
            labelBackgroundRadius: 4,
          },
        },
        layout: {
          type: 'dagre',
          rankdir: 'TB',
          nodesep: 60,
          ranksep: 100,
          controlPoints: true,
        },
        behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
      });

      if (isDestroyedRef.current) {
        graph.destroy();
        return;
      }

      // Add custom node rendering for rich content
      graph.on('node:click', (evt: any) => {
        const nodeId = evt.target?.id;
        if (nodeId && !isDestroyedRef.current) {
          onNodeClick?.(nodeId);
        }
      });

      await graph.render();
      
      if (!isDestroyedRef.current) {
        graphRef.current = graph;
        // After render, add HTML overlays for rich node content
        addNodeOverlays(graph, chainData, getStepStatus);
      } else {
        graph.destroy();
      }
    } catch (e) {
      console.error('Failed to render rule chain graph:', e);
    }
  }, [chainData, getStepStatus, onNodeClick]);

  useEffect(() => {
    isDestroyedRef.current = false;
    renderGraph();

    return () => {
      isDestroyedRef.current = true;
      if (graphRef.current) {
        try {
          graphRef.current.destroy();
        } catch (e) {
          // Ignore destroy errors
        }
        graphRef.current = null;
      }
    };
  }, [renderGraph]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current && !isDestroyedRef.current) {
        try {
          graphRef.current.resize(
            containerRef.current.clientWidth,
            containerRef.current.clientHeight
          );
        } catch (e) {
          // Ignore resize errors
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div 
      ref={containerRef} 
      style={{ 
        width: '100%', 
        height: '100%',
        background: '#fafafa',
        borderRadius: 8,
        position: 'relative',
      }} 
    />
  );
}

// Add HTML overlays for rich node content
function addNodeOverlays(
  graph: Graph, 
  chainData: RuleChainGraphData,
  getStepStatus: (id: string) => string
) {
  try {
    const container = graph.getContainer();
    if (!container) return;
    
    // Remove existing overlays
    container.querySelectorAll('.rule-node-overlay').forEach(el => el.remove());
    
    chainData.nodes.forEach(node => {
      try {
        const graphNode = graph.getNodeData(node.id);
        if (!graphNode) return;
        
        const { x, y } = graphNode.style || { x: 0, y: 0 };
        const status = getStepStatus(node.id);
        const statusColor = EXECUTION_STATUS_COLORS[status] || '#D9D9D9';
        const ruleTypeColor = RULE_TYPE_COLORS[node.data.ruleType as string];
        
        const overlay = document.createElement('div');
        overlay.className = 'rule-node-overlay';
        overlay.style.cssText = `
          position: absolute;
          left: ${x - 100}px;
          top: ${y - 45}px;
          width: 200px;
          height: 90px;
          pointer-events: none;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: 8px 12px;
          box-sizing: border-box;
        `;
        
        overlay.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
            <span style="font-size: 11px; color: #666; font-weight: 500;">${node.data.ruleId}</span>
            <span style="
              width: 8px; 
              height: 8px; 
              border-radius: 50%; 
              background: ${statusColor};
              box-shadow: 0 0 4px ${statusColor};
            "></span>
          </div>
          <div style="
            font-size: 13px; 
            font-weight: 600; 
            color: #333;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-bottom: 4px;
          ">${node.data.ruleName}</div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <span style="
              font-size: 10px;
              padding: 1px 6px;
              border-radius: 4px;
              background: ${ruleTypeColor?.fill || '#f0f0f0'};
              color: ${ruleTypeColor?.stroke || '#666'};
              border: 1px solid ${ruleTypeColor?.stroke || '#d9d9d9'};
            ">${ruleTypeColor?.label || node.data.ruleType}</span>
            <span style="font-size: 10px; color: #999;">P${node.data.priority}</span>
          </div>
        `;
        
        container.appendChild(overlay);
      } catch (e) {
        // Ignore individual node errors
      }
    });
  } catch (e) {
    // Ignore overlay errors
  }
}

function transformToG6(
  data: RuleChainGraphData,
  getStepStatus: (id: string) => string
) {
  if (!data) {
    return { nodes: [], edges: [] };
  }

  const nodes = data.nodes || [];
  const edges = data.edges || [];
  
  // Build node id set to filter edges
  const nodeIds = new Set(nodes.map(n => n.id));
  
  return {
    nodes: nodes.map(node => ({
      id: node.id,
      data: {
        ...node.data,
        status: getStepStatus(node.id),
      },
      style: {
        x: node.position?.x || 0,
        y: node.position?.y || 0,
      },
    })),
    edges: edges
      .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: edge.data,
      })),
  };
}

function getNodeFill(data: any, status: string): string {
  if (status === 'executing') return '#e6f7ff';
  if (status === 'passed') return '#f6ffed';
  if (status === 'failed') return '#fff1f0';
  if (status === 'skipped') return '#fff7e6';
  return RULE_TYPE_COLORS[data?.ruleType]?.fill || '#f0f0f0';
}

function getNodeStroke(data: any, status: string): string {
  if (status === 'executing') return '#1890ff';
  if (status === 'passed') return '#52c41a';
  if (status === 'failed') return '#f5222d';
  if (status === 'skipped') return '#fa8c16';
  return RULE_TYPE_COLORS[data?.ruleType]?.stroke || '#d9d9d9';
}
