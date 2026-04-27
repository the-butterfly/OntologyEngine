// ontology-engine-ui/src/store/spaceStore.ts
// Zustand store for semantic spaces

import { create } from 'zustand';
import {
  spaceApi,
  SpaceResponse,
  RuleDefinition,
  RuleLogic,
  SpaceVersion,
  EntityInstance,
  CreateSpaceRequest,
  CreateRuleDefinitionRequest,
  CreateRuleLogicRequest,
} from '../api/spaceApi';

interface SpaceState {
  // Current active space
  activeSpaceId: string | null;
  activeSpace: SpaceResponse | null;
  activeViewId: string | null; // Consumption view ID

  // Lists
  spaces: SpaceResponse[];
  views: any[]; // Consumption views
  ruleDefinitions: RuleDefinition[];
  ruleLogics: RuleLogic[];
  versions: SpaceVersion[];
  entities: EntityInstance[];

  // L1 Fact Objects
  factObjects: any[];

  // L2 Categorizations (dimensions)
  categorizations: any[];

  // Execution data (consumption surface)
  schemaGraph: any | null;
  ruleChainGraph: any | null;
  executionResult: any | null;
  simulationResult: any | null;

  // Loading states
  loading: boolean;
  spacesLoading: boolean;
  definitionsLoading: boolean;
  logicsLoading: boolean;
  versionsLoading: boolean;
  entitiesLoading: boolean;
  executeLoading: boolean;

  // Error
  error: string | null;

  // Actions
  loadSpaces: () => Promise<void>;
  loadViews: () => Promise<void>;
  setActiveSpace: (spaceId: string) => Promise<void>;
  setActiveView: (viewId: string) => void;
  createSpace: (request: CreateSpaceRequest) => Promise<SpaceResponse>;
  updateSpace: (spaceId: string, updates: Partial<CreateSpaceRequest & { status: string }>) => Promise<void>;
  deleteSpace: (spaceId: string) => Promise<void>;
  activateSpace: (spaceId: string) => Promise<void>;
  deactivateSpace: (spaceId: string) => Promise<void>;

  // L1 Fact Objects
  loadFactObjects: (spaceId: string) => Promise<void>;
  createFactObject: (spaceId: string, factObject: any) => Promise<void>;

  // L2 Categorizations
  loadCategorizations: (spaceId: string) => Promise<void>;

  // Rule Definitions
  loadRuleDefinitions: (spaceId: string) => Promise<void>;
  createRuleDefinition: (spaceId: string, request: CreateRuleDefinitionRequest) => Promise<RuleDefinition>;
  updateRuleDefinition: (spaceId: string, ruleId: string, request: CreateRuleDefinitionRequest) => Promise<void>;
  deleteRuleDefinition: (spaceId: string, ruleId: string) => Promise<void>;

  // Rule Logics
  loadRuleLogics: (spaceId: string) => Promise<void>;
  createRuleLogic: (spaceId: string, request: CreateRuleLogicRequest) => Promise<RuleLogic>;
  updateRuleLogic: (spaceId: string, logicId: string, request: CreateRuleLogicRequest) => Promise<void>;
  deleteRuleLogic: (spaceId: string, logicId: string) => Promise<void>;

  // Versions
  loadVersions: (spaceId: string) => Promise<void>;
  createVersion: (spaceId: string, description?: string) => Promise<void>;
  rollbackToVersion: (spaceId: string, version: number) => Promise<void>;

  // Entities
  loadEntities: (spaceId: string, concept?: string) => Promise<void>;

  // Visualization (Consumption Surface) - uses viewId
  loadSchemaGraph: (viewId: string, graphType?: string, layerFilter?: string) => Promise<void>;

  // Execution (Consumption Surface) - uses viewId
  executeAnalyze: (viewId: string, entityId: string, dimension?: string) => Promise<void>;
  executeSimulate: (viewId: string, entityId: string, dimension?: string, overrides?: Record<string, any>) => Promise<void>;

  // Clear
  clearError: () => void;
  clearExecutionResult: () => void;
  reset: () => void;
}

const initialState = {
  activeSpaceId: null,
  activeSpace: null,
  activeViewId: null,
  spaces: [],
  views: [],
  ruleDefinitions: [],
  ruleLogics: [],
  versions: [],
  entities: [],
  factObjects: [],
  categorizations: [],
  schemaGraph: null,
  ruleChainGraph: null,
  executionResult: null,
  simulationResult: null,
  loading: false,
  spacesLoading: false,
  definitionsLoading: false,
  logicsLoading: false,
  versionsLoading: false,
  entitiesLoading: false,
  executeLoading: false,
  error: null,
};

export const useSpaceStore = create<SpaceState>((set, get) => ({
  ...initialState,

  // Clear error
  clearError: () => set({ error: null }),

  // Reset store
  reset: () => set(initialState),

  // Load all spaces
  loadSpaces: async () => {
    set({ spacesLoading: true, error: null });
    try {
      const spaces = await spaceApi.listSpaces();
      set({ spaces, spacesLoading: false });
    } catch (error: any) {
      set({ error: error.message, spacesLoading: false });
    }
  },

  // Load all consumption views
  loadViews: async () => {
    set({ loading: true, error: null });
    try {
      const views = await spaceApi.listViews();
      set({ views, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Set active view ID
  setActiveView: (viewId: string) => {
    set({ activeViewId: viewId });
  },

  // Set active space and load its data
  setActiveSpace: async (spaceId: string) => {
    set({ activeSpaceId: spaceId, loading: true, error: null });
    try {
      const [space, definitions, logics, versions, factObjects, entities] = await Promise.all([
        spaceApi.getSpace(spaceId),
        spaceApi.listRuleDefinitions(spaceId),
        spaceApi.listRuleLogics(spaceId),
        spaceApi.listVersions(spaceId),
        spaceApi.listFactObjects(spaceId),
        spaceApi.listEntities(spaceId),
      ]);
      set({
        activeSpace: space,
        ruleDefinitions: definitions,
        ruleLogics: logics,
        versions,
        factObjects,
        entities,
        loading: false,
      });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Create space
  createSpace: async (request: CreateSpaceRequest) => {
    set({ loading: true, error: null });
    try {
      const space = await spaceApi.createSpace(request);
      set((state) => ({
        spaces: [...state.spaces, space],
        loading: false,
      }));
      return space;
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Update space
  updateSpace: async (spaceId: string, updates: Partial<CreateSpaceRequest & { status: string }>) => {
    set({ loading: true, error: null });
    try {
      const space = await spaceApi.updateSpace(spaceId, updates);
      set((state) => ({
        activeSpace: space,
        spaces: state.spaces.map((s) => (s.id === spaceId ? space : s)),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Delete space
  deleteSpace: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      await spaceApi.deleteSpace(spaceId);
      set((state) => ({
        spaces: state.spaces.filter((s) => s.id !== spaceId),
        activeSpaceId: state.activeSpaceId === spaceId ? null : state.activeSpaceId,
        activeSpace: state.activeSpaceId === spaceId ? null : state.activeSpace,
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Activate space
  activateSpace: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      const space = await spaceApi.activateSpace(spaceId);
      set((state) => ({
        activeSpace: space,
        spaces: state.spaces.map((s) => (s.id === spaceId ? space : s)),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Deactivate space
  deactivateSpace: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      const space = await spaceApi.deactivateSpace(spaceId);
      set((state) => ({
        activeSpace: space,
        spaces: state.spaces.map((s) => (s.id === spaceId ? space : s)),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Load fact objects
  loadFactObjects: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      const factObjects = await spaceApi.listFactObjects(spaceId);
      set({ factObjects, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Create fact object
  createFactObject: async (spaceId: string, factObject: any) => {
    set({ loading: true, error: null });
    try {
      const created = await spaceApi.createFactObject(spaceId, factObject);
      set((state) => ({
        factObjects: [...state.factObjects, created],
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Load categorizations (dimensions)
  loadCategorizations: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      const categorizations = await spaceApi.listCategorizations(spaceId);
      set({ categorizations, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Load rule definitions
  loadRuleDefinitions: async (spaceId: string) => {
    set({ definitionsLoading: true, error: null });
    try {
      const definitions = await spaceApi.listRuleDefinitions(spaceId);
      set({ ruleDefinitions: definitions, definitionsLoading: false });
    } catch (error: any) {
      set({ error: error.message, definitionsLoading: false });
    }
  },

  // Create rule definition
  createRuleDefinition: async (spaceId: string, request: CreateRuleDefinitionRequest) => {
    set({ loading: true, error: null });
    try {
      const definition = await spaceApi.createRuleDefinition(spaceId, request);
      set((state) => ({
        ruleDefinitions: [...state.ruleDefinitions, definition],
        loading: false,
      }));
      return definition;
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Update rule definition
  updateRuleDefinition: async (spaceId: string, ruleId: string, request: CreateRuleDefinitionRequest) => {
    set({ loading: true, error: null });
    try {
      const definition = await spaceApi.updateRuleDefinition(spaceId, ruleId, request);
      set((state) => ({
        ruleDefinitions: state.ruleDefinitions.map((d) => (d.id === ruleId ? definition : d)),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Delete rule definition
  deleteRuleDefinition: async (spaceId: string, ruleId: string) => {
    set({ loading: true, error: null });
    try {
      await spaceApi.deleteRuleDefinition(spaceId, ruleId);
      set((state) => ({
        ruleDefinitions: state.ruleDefinitions.filter((d) => d.id !== ruleId),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Load rule logics
  loadRuleLogics: async (spaceId: string) => {
    set({ logicsLoading: true, error: null });
    try {
      const logics = await spaceApi.listRuleLogics(spaceId);
      set({ ruleLogics: logics, logicsLoading: false });
    } catch (error: any) {
      set({ error: error.message, logicsLoading: false });
    }
  },

  // Create rule logic
  createRuleLogic: async (spaceId: string, request: CreateRuleLogicRequest) => {
    set({ loading: true, error: null });
    try {
      const logic = await spaceApi.createRuleLogic(spaceId, request);
      set((state) => ({
        ruleLogics: [...state.ruleLogics, logic],
        loading: false,
      }));
      return logic;
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  // Update rule logic
  updateRuleLogic: async (spaceId: string, logicId: string, request: CreateRuleLogicRequest) => {
    set({ loading: true, error: null });
    try {
      const logic = await spaceApi.updateRuleLogic(spaceId, logicId, request);
      set((state) => ({
        ruleLogics: state.ruleLogics.map((l) => (l.id === logicId ? logic : l)),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Delete rule logic
  deleteRuleLogic: async (spaceId: string, logicId: string) => {
    set({ loading: true, error: null });
    try {
      await spaceApi.deleteRuleLogic(spaceId, logicId);
      set((state) => ({
        ruleLogics: state.ruleLogics.filter((l) => l.id !== logicId),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Load versions
  loadVersions: async (spaceId: string) => {
    set({ versionsLoading: true, error: null });
    try {
      const versions = await spaceApi.listVersions(spaceId);
      set({ versions, versionsLoading: false });
    } catch (error: any) {
      set({ error: error.message, versionsLoading: false });
    }
  },

  // Create version snapshot
  createVersion: async (spaceId: string, description?: string) => {
    set({ loading: true, error: null });
    try {
      const version = await spaceApi.createVersion(spaceId, description);
      set((state) => ({
        versions: [...state.versions, version],
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Rollback to version
  rollbackToVersion: async (spaceId: string, version: number) => {
    set({ loading: true, error: null });
    try {
      const space = await spaceApi.rollbackToVersion(spaceId, version);
      set((state) => ({
        activeSpace: space,
        spaces: state.spaces.map((s) => (s.id === spaceId ? space : s)),
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  // Load entities
  loadEntities: async (spaceId: string, concept?: string) => {
    set({ entitiesLoading: true, error: null });
    try {
      const entities = await spaceApi.listEntities(spaceId, concept);
      set({ entities, entitiesLoading: false });
    } catch (error: any) {
      set({ error: error.message, entitiesLoading: false });
    }
  },

  // Load schema graph (Consumption - uses viewId)
  loadSchemaGraph: async (viewId: string, graphType?: string, layerFilter?: string) => {
    set({ executeLoading: true, error: null });
    try {
      const graph = await spaceApi.getSchemaGraph(viewId, graphType, layerFilter);
      set({ schemaGraph: graph, executeLoading: false });
    } catch (error: any) {
      set({ error: error.message, executeLoading: false });
    }
  },

  // Execute analyze (Consumption - uses viewId)
  executeAnalyze: async (viewId: string, entityId: string, dimension?: string) => {
    set({ executeLoading: true, error: null });
    try {
      const result = await spaceApi.executeAnalyze(viewId, entityId, dimension);
      set({ executionResult: result, executeLoading: false });
    } catch (error: any) {
      set({ error: error.message, executeLoading: false });
    }
  },

  // Execute simulate (Consumption - uses viewId)
  executeSimulate: async (viewId: string, entityId: string, dimension?: string, overrides?: Record<string, any>) => {
    set({ executeLoading: true, error: null });
    try {
      const result = await spaceApi.executeSimulate(viewId, entityId, dimension, overrides);
      set({ simulationResult: result, executeLoading: false });
    } catch (error: any) {
      set({ error: error.message, executeLoading: false });
    }
  },

  // Clear execution result
  clearExecutionResult: () => set({ executionResult: null, simulationResult: null }),
}));
