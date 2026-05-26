import { create } from 'zustand';
import { spaceApi } from '../api/spaceApi';
import type {
  SpaceResponse,
  RuleDefinition,
  RuleLogic,
  SpaceVersion,
  EntityInstance,
  CreateSpaceRequest,
  CreateRuleDefinitionRequest,
  CreateRuleLogicRequest,
  ViewDetails,
  FactObject,
  Categorization,
  SchemaGraphData as ApiSchemaGraphData,
  DependencyGraph,
} from '../api/spaceApi';
import type { ExecutionResult } from '../types/space';

interface SpaceState {
  activeSpaceId: string | null;
  activeSpace: SpaceResponse | null;
  activeViewId: string | null;

  spaces: SpaceResponse[];
  views: ViewDetails[];
  ruleDefinitions: RuleDefinition[];
  ruleLogics: RuleLogic[];
  versions: SpaceVersion[];
  entities: EntityInstance[];

  factObjects: FactObject[];
  categorizations: Categorization[];

  schemaGraph: ApiSchemaGraphData | null;
  ruleChainGraph: DependencyGraph | null;
  executionResult: ExecutionResult | null;
  simulationResult: ExecutionResult | null;

  loading: boolean;
  spacesLoading: boolean;
  definitionsLoading: boolean;
  logicsLoading: boolean;
  versionsLoading: boolean;
  entitiesLoading: boolean;
  executeLoading: boolean;

  error: string | null;

  loadSpaces: () => Promise<void>;
  loadViews: () => Promise<void>;
  setActiveSpace: (spaceId: string) => Promise<void>;
  setActiveView: (viewId: string) => void;
  createSpace: (request: CreateSpaceRequest) => Promise<SpaceResponse>;
  updateSpace: (spaceId: string, updates: Partial<CreateSpaceRequest & { status: string }>) => Promise<void>;
  deleteSpace: (spaceId: string) => Promise<void>;
  activateSpace: (spaceId: string) => Promise<void>;
  deactivateSpace: (spaceId: string) => Promise<void>;

  loadFactObjects: (spaceId: string) => Promise<void>;
  createFactObject: (spaceId: string, factObject: Partial<FactObject>) => Promise<void>;

  loadCategorizations: (spaceId: string) => Promise<void>;

  loadRuleDefinitions: (spaceId: string) => Promise<void>;
  createRuleDefinition: (spaceId: string, request: CreateRuleDefinitionRequest) => Promise<RuleDefinition>;
  updateRuleDefinition: (spaceId: string, ruleId: string, request: CreateRuleDefinitionRequest) => Promise<void>;
  deleteRuleDefinition: (spaceId: string, ruleId: string) => Promise<void>;

  loadRuleLogics: (spaceId: string) => Promise<void>;
  createRuleLogic: (spaceId: string, request: CreateRuleLogicRequest) => Promise<RuleLogic>;
  updateRuleLogic: (spaceId: string, logicId: string, request: CreateRuleLogicRequest) => Promise<void>;
  deleteRuleLogic: (spaceId: string, logicId: string) => Promise<void>;

  loadVersions: (spaceId: string) => Promise<void>;
  createVersion: (spaceId: string, description?: string) => Promise<void>;
  rollbackToVersion: (spaceId: string, version: number) => Promise<void>;

  loadEntities: (spaceId: string, concept?: string) => Promise<void>;

  loadSchemaGraph: (viewId: string, graphType?: string, layerFilter?: string) => Promise<void>;

  executeAnalyze: (viewId: string, entityId: string, dimension?: string) => Promise<void>;
  executeSimulate: (viewId: string, entityId: string, dimension?: string, overrides?: Record<string, any>) => Promise<void>;

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

  clearError: () => set({ error: null }),

  reset: () => set(initialState),

  loadSpaces: async () => {
    set({ spacesLoading: true, error: null });
    try {
      const spaces = await spaceApi.listSpaces();
      set({ spaces, spacesLoading: false });
    } catch (error: any) {
      set({ error: error.message, spacesLoading: false });
    }
  },

  loadViews: async () => {
    set({ loading: true, error: null });
    try {
      const views = await spaceApi.listViews();
      set({ views, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  setActiveView: (viewId: string) => {
    set({ activeViewId: viewId });
  },

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

  loadFactObjects: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      const factObjects = await spaceApi.listFactObjects(spaceId);
      set({ factObjects, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

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

  loadCategorizations: async (spaceId: string) => {
    set({ loading: true, error: null });
    try {
      const categorizations = await spaceApi.listCategorizations(spaceId);
      set({ categorizations, loading: false });
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  loadRuleDefinitions: async (spaceId: string) => {
    set({ definitionsLoading: true, error: null });
    try {
      const definitions = await spaceApi.listRuleDefinitions(spaceId);
      set({ ruleDefinitions: definitions, definitionsLoading: false });
    } catch (error: any) {
      set({ error: error.message, definitionsLoading: false });
    }
  },

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

  loadRuleLogics: async (spaceId: string) => {
    set({ logicsLoading: true, error: null });
    try {
      const logics = await spaceApi.listRuleLogics(spaceId);
      set({ ruleLogics: logics, logicsLoading: false });
    } catch (error: any) {
      set({ error: error.message, logicsLoading: false });
    }
  },

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

  loadVersions: async (spaceId: string) => {
    set({ versionsLoading: true, error: null });
    try {
      const versions = await spaceApi.listVersions(spaceId);
      set({ versions, versionsLoading: false });
    } catch (error: any) {
      set({ error: error.message, versionsLoading: false });
    }
  },

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

  loadEntities: async (spaceId: string, concept?: string) => {
    set({ entitiesLoading: true, error: null });
    try {
      const entities = await spaceApi.listEntities(spaceId, concept);
      set({ entities, entitiesLoading: false });
    } catch (error: any) {
      set({ error: error.message, entitiesLoading: false });
    }
  },

  loadSchemaGraph: async (viewId: string, graphType?: string, layerFilter?: string) => {
    set({ executeLoading: true, error: null });
    try {
      const graph = await spaceApi.getSchemaGraph(viewId, graphType, layerFilter);
      set({ schemaGraph: graph, executeLoading: false });
    } catch (error: any) {
      set({ error: error.message, executeLoading: false });
    }
  },

  executeAnalyze: async (viewId: string, entityId: string, dimension?: string) => {
    set({ executeLoading: true, error: null });
    try {
      const result = await spaceApi.executeAnalyze(viewId, entityId, dimension);
      set({ executionResult: result, executeLoading: false });
    } catch (error: any) {
      set({ error: error.message, executeLoading: false });
    }
  },

  executeSimulate: async (viewId: string, entityId: string, dimension?: string, overrides?: Record<string, any>) => {
    set({ executeLoading: true, error: null });
    try {
      const result = await spaceApi.executeSimulate(viewId, entityId, dimension, overrides);
      set({ simulationResult: result, executeLoading: false });
    } catch (error: any) {
      set({ error: error.message, executeLoading: false });
    }
  },

  clearExecutionResult: () => set({ executionResult: null, simulationResult: null }),
}));
