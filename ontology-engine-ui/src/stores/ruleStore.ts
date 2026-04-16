// ontology-engine-ui/src/stores/ruleStore.ts
// Zustand store for rule orchestration state management

import { create } from 'zustand';
import { ruleGroupsApi } from '../api/ruleGroups';
import { ruleStepsApi } from '../api/ruleSteps';
import type { RuleGroup, RuleStep, SimulationResult, StepResult } from '../types/rule';

interface RuleStore {
  // ===== Data State =====
  currentRuleGroup: RuleGroup | null;
  ruleSteps: RuleStep[];
  loading: boolean;
  error: string | null;

  // ===== Simulation State =====
  simulationResult: SimulationResult | null;
  stepResults: StepResult[];
  simulationLoading: boolean;
  simulationError: string | null;

  // ===== Actions =====
  loadRuleGroup: (id: string, schemaId?: string) => Promise<void>;
  loadRuleSteps: (ruleGroupName: string, schemaId: string) => Promise<void>;
  createRuleGroup: (group: Partial<RuleGroup>, schemaId: string) => Promise<RuleGroup>;
  updateRuleGroup: (id: string, updates: Partial<RuleGroup>, schemaId?: string) => Promise<void>;
  deleteRuleGroup: (id: string, schemaId?: string) => Promise<void>;
  setCurrentRuleGroup: (group: RuleGroup | null) => void;

  // ===== Step Actions =====
  addRuleStep: (name: string, step: Partial<RuleStep>, schemaId: string) => Promise<void>;
  updateRuleStep: (name: string, stepId: string, updates: Partial<RuleStep>, schemaId: string) => Promise<void>;
  deleteRuleStep: (name: string, stepId: string, schemaId: string) => Promise<void>;
  reorderRuleSteps: (name: string, stepIds: string[], schemaId: string) => Promise<void>;

  // ===== Simulation Actions =====
  simulate: (ruleGroupName: string, schemaId: string, entityData: Record<string, unknown>) => Promise<void>;
  clearSimulation: () => void;

  // ===== YAML Actions =====
  exportYaml: (name: string, schemaId: string) => Promise<string>;
  importYaml: (yamlContent: string, schemaId: string) => Promise<RuleGroup>;

  // ===== UI State =====
  editingStepId: string | null;
  setEditingStepId: (id: string | null) => void;

  // ===== Error Handling =====
  clearError: () => void;
  reset: () => void;
}

const initialState = {
  currentRuleGroup: null,
  ruleSteps: [],
  loading: false,
  error: null,
  simulationResult: null,
  stepResults: [],
  simulationLoading: false,
  simulationError: null,
  editingStepId: null,
};

export const useRuleStore = create<RuleStore>((set, get) => ({
  ...initialState,

  // ===== Data Actions =====

  loadRuleGroup: async (id, schemaId) => {
    set({ loading: true, error: null });
    try {
      const group = await ruleGroupsApi.getById(id, schemaId);
      set({ currentRuleGroup: group, loading: false });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to load rule group';
      set({ error: message, loading: false });
    }
  },

  loadRuleSteps: async (ruleGroupName, schemaId) => {
    set({ loading: true, error: null });
    try {
      const steps = await ruleGroupsApi.getSteps(ruleGroupName, schemaId);
      set({ ruleSteps: steps, loading: false });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to load rule steps';
      set({ error: message, loading: false });
    }
  },

  createRuleGroup: async (group, schemaId) => {
    set({ loading: true, error: null });
    try {
      const created = await ruleGroupsApi.create(group, schemaId);
      return created;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to create rule group';
      set({ error: message, loading: false });
      throw e;
    } finally {
      set({ loading: false });
    }
  },

  updateRuleGroup: async (id, updates, schemaId) => {
    set({ loading: true, error: null });
    try {
      const updated = await ruleGroupsApi.update(id, updates, schemaId);
      set({ currentRuleGroup: updated, loading: false });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to update rule group';
      set({ error: message, loading: false });
    }
  },

  deleteRuleGroup: async (id, schemaId) => {
    set({ loading: true, error: null });
    try {
      await ruleGroupsApi.delete(id, schemaId);
      set({ currentRuleGroup: null, loading: false });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to delete rule group';
      set({ error: message, loading: false });
    }
  },

  setCurrentRuleGroup: (group) => set({ currentRuleGroup: group }),

  // ===== Step Actions =====

  addRuleStep: async (name, step, schemaId) => {
    set({ loading: true, error: null });
    try {
      const newStep = await ruleGroupsApi.addStep(name, step, schemaId);
      set((state) => ({
        ruleSteps: [...state.ruleSteps, newStep],
        loading: false,
      }));
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to add rule step';
      set({ error: message, loading: false });
    }
  },

  updateRuleStep: async (name, stepId, updates, schemaId) => {
    set({ loading: true, error: null });
    try {
      const updated = await ruleGroupsApi.updateStep(name, stepId, updates, schemaId);
      set((state) => ({
        ruleSteps: state.ruleSteps.map((s) => (s.id === stepId ? updated : s)),
        loading: false,
      }));
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to update rule step';
      set({ error: message, loading: false });
    }
  },

  deleteRuleStep: async (name, stepId, schemaId) => {
    set({ loading: true, error: null });
    try {
      await ruleGroupsApi.deleteStep(name, stepId, schemaId);
      set((state) => ({
        ruleSteps: state.ruleSteps.filter((s) => s.id !== stepId),
        loading: false,
      }));
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to delete rule step';
      set({ error: message, loading: false });
    }
  },

  reorderRuleSteps: async (name, stepIds, schemaId) => {
    try {
      // Call API to persist the reorder
      await ruleStepsApi.reorder(name, stepIds, schemaId);
      // Update local state with new order
      const currentSteps = get().ruleSteps;
      const stepMap = new Map(currentSteps.map((s) => [s.id, s]));
      const reordered = stepIds
        .map((id, index) => {
          const step = stepMap.get(id);
          return step ? { ...step, order: index } : null;
        })
        .filter(Boolean) as RuleStep[];

      set({ ruleSteps: reordered });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to reorder steps';
      set({ error: message });
      throw e;
    }
  },

  // ===== Simulation Actions =====

  simulate: async (ruleGroupName, schemaId, entityData) => {
    set({ simulationLoading: true, simulationError: null });
    try {
      const result = await ruleGroupsApi.simulate(ruleGroupName, schemaId, entityData);
      set({
        simulationResult: result,
        stepResults: result.steps || [],
        simulationLoading: false,
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Simulation failed';
      set({
        simulationError: message,
        simulationLoading: false,
      });
    }
  },

  clearSimulation: () => set({ simulationResult: null, stepResults: [] }),

  // ===== YAML Actions =====

  exportYaml: async (name, schemaId) => {
    set({ loading: true, error: null });
    try {
      const yaml = await ruleGroupsApi.exportYaml(name, schemaId);
      set({ loading: false });
      return yaml;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to export YAML';
      set({ error: message, loading: false });
      throw e;
    }
  },

  importYaml: async (yamlContent, schemaId) => {
    set({ loading: true, error: null });
    try {
      const imported = await ruleGroupsApi.importYaml(yamlContent, schemaId);
      set({ loading: false });
      return imported;
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to import YAML';
      set({ error: message, loading: false });
      throw e;
    }
  },

  // ===== UI State =====

  editingStepId: null,
  setEditingStepId: (id) => set({ editingStepId: id }),

  // ===== Error Handling =====

  clearError: () => set({ error: null, simulationError: null }),

  reset: () => set(initialState),
}));

export default useRuleStore;
