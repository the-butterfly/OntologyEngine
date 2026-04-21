import React, { createContext, useContext, useEffect, useRef, useCallback, useMemo } from 'react';
import type { SimulationResult } from '../../types/simulation';

interface SimulationContextValue {
  schemaId: string;
  sessionId: string | null;
  result: SimulationResult | null;
  // AGUI postMessage预留
  postMessage: (type: string, payload: unknown) => void;
}

const SimulationContext = createContext<SimulationContextValue | null>(null);

export function SimulationProvider({
  schemaId,
  children,
}: {
  schemaId: string;
  children: React.ReactNode;
}) {
  const sessionIdRef = useRef<string | null>(null);

  // postMessage预留 - 未来Agent集成
  const postMessage = useCallback((type: string, payload: unknown) => {
    if (typeof window !== 'undefined' && window.parent !== window) {
      window.parent.postMessage({ type, payload }, '*');
    }
  }, []);

  // Listen for postMessage from parent (AGUI预留)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const { type, payload } = event.data || {};
      // Future: handle INIT, UPDATE_INPUT, RUN commands from Agent
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const value = useMemo<SimulationContextValue>(() => ({
    schemaId,
    sessionId: sessionIdRef.current,
    result: null,
    postMessage,
  }), [schemaId, postMessage]);

  return (
    <SimulationContext.Provider value={value}>
      {children}
    </SimulationContext.Provider>
  );
}

export function useSimulationContext() {
  const context = useContext(SimulationContext);
  if (!context) {
    throw new Error('useSimulationContext must be used within SimulationProvider');
  }
  return context;
}