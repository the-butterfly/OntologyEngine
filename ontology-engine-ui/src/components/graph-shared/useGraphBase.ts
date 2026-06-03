import { useEffect, useRef, useCallback } from 'react';
import { Graph } from '@antv/g6';

export interface GraphBaseConfig {
  container: HTMLElement | null;
  width?: number;
  height?: number;
  minimap?: boolean;
  tooltip?: boolean;
}

export function useGraphBase(config: GraphBaseConfig) {
  const graphRef = useRef<Graph | null>(null);
  const containerRef = useRef<HTMLElement | null>(null);

  const destroyGraph = useCallback(() => {
    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (graphRef.current && containerRef.current) {
        const { clientWidth, clientHeight } = containerRef.current;
        graphRef.current.resize(clientWidth, config.height || clientHeight);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [config.height]);

  useEffect(() => {
    return () => destroyGraph();
  }, [destroyGraph]);

  return {
    graphRef,
    containerRef,
    destroyGraph,
  };
}
