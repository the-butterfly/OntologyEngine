declare module 'dagre' {
  export interface Graph {
    setNode(nodeId: string, obj?: { width?: number; height?: number }): void;
    node(nodeId: string): { x: number; y: number; width?: number; height?: number } | undefined;
    edge(edgeId: string): any;
    setEdge(sourceId: string, targetId: string, obj?: any): void;
    setDefaultEdgeLabel(callback: () => any): void;
    setGraph(opts: { rankdir?: string; nodesep?: number; ranksep?: number; marginx?: number; marginy?: number }): void;
    graph(): { width?: number; height?: number };
  }

  export interface GraphLib {
    Graph: new () => Graph;
  }

  const dagre: {
    graphlib: GraphLib;
    layout(g: Graph, opts?: { rankdir?: string; nodesep?: number; ranksep?: number }): void;
  };

  export default dagre;
}
