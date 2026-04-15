// ontology-engine-ui/src/hooks/useRuleGroups.ts
// Custom hook for rule groups data management

import { useState, useCallback } from 'react';
import { ruleGroupsApi } from '../api/ruleGroups';
import type { RuleGroup, SimulationResult, StepResult } from '../types/rule';

export const useRuleGroups = (schemaId: string) => {
  const [loading, setLoading] = useState(false);
  const [ruleGroups, setRuleGroups] = useState<RuleGroup[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchGroups = useCallback(
    async (params?: { enabled?: boolean }) => {
      setLoading(true);
      setError(null);
      try {
        const data = await ruleGroupsApi.list(schemaId, params);
        setRuleGroups(data);
        return data;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to fetch rule groups';
        setError(message);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [schemaId]
  );

  const createGroup = useCallback(
    async (group: Partial<RuleGroup>) => {
      setLoading(true);
      setError(null);
      try {
        const created = await ruleGroupsApi.create(group, schemaId);
        setRuleGroups((prev) => [...prev, created]);
        return created;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to create rule group';
        setError(message);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [schemaId]
  );

  const updateGroup = useCallback(
    async (id: string, updates: Partial<RuleGroup>) => {
      setError(null);
      try {
        const updated = await ruleGroupsApi.update(id, updates, schemaId);
        setRuleGroups((prev) => prev.map((rg) => (rg.id === id ? updated : rg)));
        return updated;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to update rule group';
        setError(message);
        throw e;
      }
    },
    [schemaId]
  );

  const deleteGroup = useCallback(
    async (id: string) => {
      setError(null);
      try {
        await ruleGroupsApi.delete(id, schemaId);
        setRuleGroups((prev) => prev.filter((rg) => rg.id !== id));
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to delete rule group';
        setError(message);
        throw e;
      }
    },
    [schemaId]
  );

  const exportYaml = useCallback(
    async (name: string) => {
      setLoading(true);
      setError(null);
      try {
        const yaml = await ruleGroupsApi.exportYaml(name, schemaId);
        return yaml;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to export rule group';
        setError(message);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [schemaId]
  );

  const importYaml = useCallback(
    async (yamlContent: string) => {
      setLoading(true);
      setError(null);
      try {
        const imported = await ruleGroupsApi.importYaml(yamlContent, schemaId);
        setRuleGroups((prev) => [...prev, imported]);
        return imported;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to import rule group';
        setError(message);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [schemaId]
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    loading,
    ruleGroups,
    error,
    fetchGroups,
    createGroup,
    updateGroup,
    deleteGroup,
    exportYaml,
    importYaml,
    clearError,
  };
};

export const useSimulation = (ruleGroupName: string, schemaId: string) => {
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [stepResults, setStepResults] = useState<StepResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const simulate = useCallback(
    async (entityData: Record<string, unknown>) => {
      setLoading(true);
      setError(null);
      try {
        const res = await ruleGroupsApi.simulate(ruleGroupName, schemaId, entityData);
        setResult(res);
        setStepResults(res.steps || []);
        return res;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Simulation failed';
        setError(message);
        throw e;
      } finally {
        setLoading(false);
      }
    },
    [ruleGroupName, schemaId]
  );

  const clearResult = useCallback(() => {
    setResult(null);
    setStepResults([]);
  }, []);

  return {
    result,
    stepResults,
    loading,
    error,
    simulate,
    clearResult,
  };
};

export default useRuleGroups;
