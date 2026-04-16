// ontology-engine-ui/src/hooks/useL4Rules.ts
// Hook for L4 Rule Definitions from Schema API
// 数据源：/v1/management/{spaceId}/schema/L4/rules/definitions
//         /v1/management/{spaceId}/schema/L4/rules/logics
//
// 与 useRuleGroups 的区别：
//   - useRuleGroups: 来自独立的 /v1/rule-groups 存储
//   - useL4Rules: 来自 Schema L4 层（与 Schema 声明一致的事实源）

import { useState, useCallback } from 'react';
import { spaceApi } from '../api/spaceApi';
import type { RuleDefinition, RuleLogic } from '../api/spaceApi';

// ─── L4 数据类型（与 Schema L4 API 对齐）─────────────────────────────────────

/** L4 规则定义 —— 与 Schema L4 business_logic.rule_definitions 对齐 */
export interface L4RuleDefinition {
  id: string;                    // 规则 ID，如 "RD001_basic_eligibility"
  name: string;                 // 规则名称，如 "基础准入检查"
  description?: string;         // 规则描述
  rule_type: 'constraint' | 'inference' | 'alert' | 'decision';
  priority: number;              // 优先级，数值越小越高
  applies_to: string[];          // 作用对象列表，如 ["Supplier"]
  applicable_categorizations: string[];  // 适用分类
  inputs: L4IOElement[];        // 输入要素
  outputs: L4IOElement[];        // 输出要素
  preconditions: L4Precondition[];  // 前置条件
  enabled: boolean;             // 是否启用
  logic_ids: string[];           // 关联的规则逻辑 ID 列表
}

/** L4 I/O 要素 —— Schema L4 中的 inputs/outputs 结构 */
export interface L4IOElement {
  id: string;                   // 要素 ID，如 "is_eligible"
  name: string;                  // 要素名称，如 "是否准入"
  type: string;                 // 要素类型：attribute / metric / flag / computed_value
  description?: string;          // 要素描述
}

/** L4 前置条件 */
export interface L4Precondition {
  expression: string;
  fail?: Record<string, unknown>;
}

/** L4 规则逻辑 —— 与 Schema L4 business_logic.rule_logics 对齐 */
export interface L4RuleLogic {
  id: string;                    // 逻辑 ID，如 "RL001_eligibility_standard"
  name?: string;                // 逻辑名称
  definition_id: string;        // 关联的规则定义 ID
  applicable_conditions: Array<{
    classification?: Record<string, string>;
    match_type?: string;
  }>;
  when?: {
    expression?: string;
    allOf?: unknown[];
    anyOf?: unknown[];
  };
  then_action?: {
    action_type?: string;
    output?: Record<string, unknown>;
  };
  else_action?: {
    action_type?: string;
    output?: Record<string, unknown>;
  };
  priority: number;
  version: number;
  environment: string;
}

/** 带关联逻辑的完整规则组视图 */
export interface L4RuleGroupWithLogics extends L4RuleDefinition {
  logics: L4RuleLogic[];
}

// ─── Normalizer：L4 API 数据 → 内部视图 ─────────────────────────────────────

function normalizeIO(raw: Record<string, unknown>): L4IOElement {
  return {
    id: String(raw['id'] || ''),
    name: String(raw['name'] || ''),
    type: String(raw['type'] || ''),
    description: raw['description'] as string | undefined,
  };
}

function normalizeDefinition(raw: Record<string, unknown>): L4RuleDefinition {
  return {
    id: String(raw['id'] || ''),
    name: String(raw['name'] || ''),
    description: raw['description'] as string | undefined,
    rule_type: (raw['rule_type'] || 'decision') as L4RuleDefinition['rule_type'],
    priority: Number(raw['priority'] || 100),
    applies_to: (raw['applies_to'] || []) as string[],
    applicable_categorizations: (raw['applicable_categorizations'] || []) as string[],
    inputs: ((raw['inputs'] || []) as Record<string, unknown>[]).map(normalizeIO),
    outputs: ((raw['outputs'] || []) as Record<string, unknown>[]).map(normalizeIO),
    preconditions: (raw['preconditions'] || []) as L4Precondition[],
    enabled: raw['enabled'] !== false,
    logic_ids: (raw['logic_ids'] || []) as string[],
  };
}

function normalizeLogic(raw: Record<string, unknown>): L4RuleLogic {
  return {
    id: String(raw['id'] || ''),
    name: raw['name'] as string | undefined,
    definition_id: String(raw['definition_id'] || ''),
    applicable_conditions: (raw['applicable_conditions'] || []) as L4RuleLogic['applicable_conditions'],
    when: raw['when'] as L4RuleLogic['when'],
    then_action: raw['then_action'] as L4RuleLogic['then_action'],
    else_action: raw['else_action'] as L4RuleLogic['else_action'],
    priority: Number(raw['priority'] || 100),
    version: Number(raw['version'] || 1),
    environment: String(raw['environment'] || 'default'),
  };
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export const useL4Rules = (spaceId: string) => {
  const [loading, setLoading] = useState(false);
  const [definitions, setDefinitions] = useState<L4RuleDefinition[]>([]);
  const [logics, setLogics] = useState<L4RuleLogic[]>([]);
  const [error, setError] = useState<string | null>(null);

  /** 加载规则定义和规则逻辑（并行） */
  const fetchRules = useCallback(async () => {
    if (!spaceId) return;
    setLoading(true);
    setError(null);
    try {
      const [defsData, logicsData] = await Promise.all([
        spaceApi.listRuleDefinitions(spaceId),
        spaceApi.listRuleLogics(spaceId),
      ]);
      setDefinitions(defsData.map((d) => normalizeDefinition(d as unknown as Record<string, unknown>)));
      setLogics(logicsData.map((l) => normalizeLogic(l as unknown as Record<string, unknown>)));
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载规则失败');
    } finally {
      setLoading(false);
    }
  }, [spaceId]);

  /** 获取某个规则定义及其关联逻辑 */
  const getRuleWithLogics = useCallback(
    (definitionId: string): L4RuleGroupWithLogics | null => {
      const def = definitions.find((d) => d.id === definitionId);
      if (!def) return null;
      const relatedLogics = logics.filter((l) => l.definition_id === definitionId);
      return { ...def, logics: relatedLogics };
    },
    [definitions, logics]
  );

  /** 获取某个规则逻辑 */
  const getLogic = useCallback(
    (logicId: string): L4RuleLogic | null => {
      return logics.find((l) => l.id === logicId) || null;
    },
    [logics]
  );

  /** 创建规则定义（L4 API） */
  const createDefinition = useCallback(
    async (data: Partial<L4RuleDefinition>): Promise<L4RuleDefinition> => {
      if (!data.id) {
        throw new Error('规则定义 ID 不能为空');
      }
      const request: import('../api/spaceApi').CreateRuleDefinitionRequest = {
        id: data.id,
        name: data.name,
        description: data.description,
        rule_type: data.rule_type || 'decision',
        priority: data.priority || 100,
        applicable_scope: {
          scope_type: data.applicable_categorizations?.length ? 'by_classification' : 'global',
          classification_values: data.applicable_categorizations,
        },
        target_objects: (data.applies_to || []).map((o) => ({ concept: o })),
        input_elements: (data.inputs || []).map((i) => ({
          name: i.name,
          element_type: i.type,
        })),
        output_elements: (data.outputs || []).map((o) => ({
          name: o.name,
          element_type: o.type,
        })),
        enabled: data.enabled !== false,
      };
      const created = await spaceApi.createRuleDefinition(spaceId, request);
      const normalized = normalizeDefinition(created as unknown as Record<string, unknown>);
      setDefinitions((prev) => [...prev, normalized]);
      return normalized;
    },
    [spaceId]
  );

  /** 更新规则定义（L4 API） */
  const updateDefinition = useCallback(
    async (definitionId: string, data: Partial<L4RuleDefinition>): Promise<L4RuleDefinition> => {
      const request: Partial<import('../api/spaceApi').CreateRuleDefinitionRequest> = {};
      if (data.name !== undefined) request.name = data.name;
      if (data.description !== undefined) request.description = data.description;
      if (data.rule_type !== undefined) request.rule_type = data.rule_type;
      if (data.priority !== undefined) request.priority = data.priority;
      if (data.enabled !== undefined) request.enabled = data.enabled;
      if (data.applies_to !== undefined) {
        request.target_objects = data.applies_to.map((o) => ({ concept: o }));
      }
      if (data.inputs !== undefined) {
        request.input_elements = data.inputs.map((i) => ({
          name: i.name,
          element_type: i.type,
        }));
      }
      if (data.outputs !== undefined) {
        request.output_elements = data.outputs.map((o) => ({
          name: o.name,
          element_type: o.type,
        }));
      }
      const updated = await spaceApi.updateRuleDefinition(spaceId, definitionId, request as import('../api/spaceApi').CreateRuleDefinitionRequest);
      const normalized = normalizeDefinition(updated as unknown as Record<string, unknown>);
      setDefinitions((prev) => prev.map((d) => (d.id === definitionId ? normalized : d)));
      return normalized;
    },
    [spaceId]
  );

  /** 删除规则定义（L4 API） */
  const deleteDefinition = useCallback(
    async (definitionId: string): Promise<void> => {
      await spaceApi.deleteRuleDefinition(spaceId, definitionId);
      setDefinitions((prev) => prev.filter((d) => d.id !== definitionId));
      // 同时清理关联的逻辑（前端乐观更新）
      setLogics((prev) => prev.filter((l) => l.definition_id !== definitionId));
    },
    [spaceId]
  );

  /** 创建规则逻辑（L4 API） */
  const createLogic = useCallback(
    async (data: Partial<L4RuleLogic>): Promise<L4RuleLogic> => {
      const request: import('../api/spaceApi').CreateRuleLogicRequest = {
        id: data.id || '',
        name: data.name,
        definition_id: data.definition_id || '',
        applicable_conditions: data.applicable_conditions,
        when: data.when,
        then_action: data.then_action,
        else_action: data.else_action,
        version: data.version,
        environment: data.environment,
      };
      const created = await spaceApi.createRuleLogic(spaceId, request);
      const normalized = normalizeLogic(created as unknown as Record<string, unknown>);
      setLogics((prev) => [...prev, normalized]);
      return normalized;
    },
    [spaceId]
  );

  /** 更新规则逻辑（L4 API） */
  const updateLogic = useCallback(
    async (logicId: string, data: Partial<L4RuleLogic>): Promise<L4RuleLogic> => {
      const request: Partial<import('../api/spaceApi').CreateRuleLogicRequest> = {};
      if (data.name !== undefined) request.name = data.name;
      if (data.when !== undefined) request.when = data.when;
      if (data.then_action !== undefined) request.then_action = data.then_action;
      if (data.else_action !== undefined) request.else_action = data.else_action;
      if (data.applicable_conditions !== undefined) request.applicable_conditions = data.applicable_conditions;
      const updated = await spaceApi.updateRuleLogic(spaceId, logicId, request as import('../api/spaceApi').CreateRuleLogicRequest);
      const normalized = normalizeLogic(updated as unknown as Record<string, unknown>);
      setLogics((prev) => prev.map((l) => (l.id === logicId ? normalized : l)));
      return normalized;
    },
    [spaceId]
  );

  /** 删除规则逻辑（L4 API） */
  const deleteLogic = useCallback(
    async (logicId: string): Promise<void> => {
      await spaceApi.deleteRuleLogic(spaceId, logicId);
      setLogics((prev) => prev.filter((l) => l.id !== logicId));
    },
    [spaceId]
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    loading,
    definitions,
    logics,
    error,
    fetchRules,
    getRuleWithLogics,
    getLogic,
    createDefinition,
    updateDefinition,
    deleteDefinition,
    createLogic,
    updateLogic,
    deleteLogic,
    clearError,
  };
};
