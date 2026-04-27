// Rule group detail panel component - shows rule definition details and logic list
import React, { useEffect, useMemo, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Spin,
  Button,
  Tag,
  Space,
  Typography,
  Breadcrumb,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  BranchesOutlined,
  ReloadOutlined,
  FileTextOutlined,
  AppstoreOutlined,
  UpOutlined,
  DownOutlined,
  NodeExpandOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import RuleGroupForm from './RuleGroupForm';
import RuleChainDAG from './RuleChainDAG';
import RuleLogicList from './RuleLogicList';
import { useL4Rules, L4RuleDefinition } from '../../hooks/useL4Rules';
import type { RuleGroup } from '../../types/rule';
import type { RuleChainGraphData } from '../../types/visualization';

const { Text } = Typography;

// ─── L4 数据适配器 ──────────────────────────────────────────────────────────

/** L4RuleDefinition → RuleGroup（适配 RuleGroupForm） */
function adaptL4ToRuleGroup(def: L4RuleDefinition): RuleGroup {
  return {
    id: def.id,
    name: def.name,
    schemaId: '',
    description: def.description || '',
    type: def.rule_type as RuleGroup['type'],
    priority: def.priority,
    appliesTo: {
      factObjects: def.applies_to || [],
      categories: {},
    },
    inputs: (def.inputs || []).map((i) => ({
      name: i.id,
      type: i.type,
      description: i.name,
    })),
    outputs: (def.outputs || []).map((o) => ({
      name: o.id,
      type: o.type,
      description: o.name,
    })),
    preconditions: (def.preconditions || []).map((p) => ({
      expression: p.expression,
    })),
    enabled: def.enabled,
  };
}

interface RuleGroupDetailPanelProps {
  spaceId: string;
  definitionId: string;
}

export const RuleGroupDetailPanel: React.FC<RuleGroupDetailPanelProps> = ({
  spaceId,
  definitionId,
}) => {
  const navigate = useNavigate();

  const {
    definitions,
    logics,
    loading,
    error,
    fetchRules,
    updateDefinition,
    deleteLogic,
    clearError,
  } = useL4Rules(spaceId);

  const [currentDef, setCurrentDef] = useState<L4RuleDefinition | null>(null);
  const [currentRuleGroup, setCurrentRuleGroup] = useState<RuleGroup | null>(null);
  const [deletingLogicId, setDeletingLogicId] = useState<string | null>(null);

  // 面板收起/展开状态
  const [definitionCollapsed, setDefinitionCollapsed] = useState(false);
  const [dagCollapsed, setDagCollapsed] = useState(false);

  // ─── 加载规则定义 ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (spaceId) fetchRules();
  }, [spaceId, fetchRules]);

  // ─── 从列表中找到当前规则定义 ─────────────────────────────────────────────
  useEffect(() => {
    if (!definitionId || definitions.length === 0) return;
    const found = definitions.find((d) => d.id === definitionId);
    if (found) {
      setCurrentDef(found);
      setCurrentRuleGroup(adaptL4ToRuleGroup(found));
    }
  }, [definitionId, definitions]);

  // ─── 构建要素依赖 DAG ──────────────────────────────────────────────────────
  const dagData = useMemo((): RuleChainGraphData | null => {
    if (!currentRuleGroup || logics.length === 0) return null;

    const relatedLogics = logics
      .filter((l) => l.definition_id === definitionId)
      .sort((a, b) => (a.priority || 0) - (b.priority || 0));

    if (relatedLogics.length === 0) return null;

    const nodes: RuleChainGraphData['nodes'] = [];
    const edges: RuleChainGraphData['edges'] = [];

    // 输入节点
    (currentRuleGroup.inputs || []).forEach((input, idx) => {
      nodes.push({
        id: `INPUT:${input.name}`,
        position: { x: 100, y: 80 * idx },
        data: {
          ruleId: `INPUT:${input.name}`,
          ruleName: input.name,
          ruleType: 'input',
          priority: 0,
        },
      });
    });

    // 规则逻辑节点
    relatedLogics.forEach((logic, idx) => {
      nodes.push({
        id: logic.id,
        position: { x: 300, y: 80 * idx },
        data: {
          ruleId: logic.id,
          ruleName: logic.name || logic.id,
          ruleType: logic.then_action?.action_type?.toLowerCase() || 'compute',
          priority: idx + 1,
          when: logic.when?.expression || null,
        },
      });

      // 连接输入到逻辑
      (currentRuleGroup.inputs || []).forEach((input) => {
        const expr = logic.when?.expression || '';
        if (expr.includes(input.name)) {
          edges.push({
            id: `EDGE:${input.name}->${logic.id}`,
            source: `INPUT:${input.name}`,
            target: logic.id,
            data: { type: 'input_ref' },
          });
        }
      });
    });

    // 输出节点
    (currentRuleGroup.outputs || []).forEach((output, idx) => {
      nodes.push({
        id: `OUTPUT:${output.name}`,
        position: { x: 500, y: 80 * idx },
        data: {
          ruleId: `OUTPUT:${output.name}`,
          ruleName: output.name,
          ruleType: 'output',
          priority: 0,
        },
      });

      // 连接逻辑到输出
      relatedLogics.forEach((logic) => {
        const thenAction = logic.then_action;
        if (thenAction?.output && JSON.stringify(thenAction.output).includes(output.name)) {
          edges.push({
            id: `EDGE:${logic.id}->${output.name}`,
            source: logic.id,
            target: `OUTPUT:${output.name}`,
            data: { type: 'output_produces' },
          });
        }
      });
    });

    return {
      dimension: 'element_dependency',
      nodes,
      edges,
      dimension_info: {
        name: '要素依赖图',
        description: '输入要素 → 规则逻辑 → 输出要素',
        applicable_entities: [],
        rule_count: nodes.length,
      },
    };
  }, [currentRuleGroup, logics, definitionId]);

  // ─── 事件处理 ───────────────────────────────────────────────────────────────
  const handleSaveGroup = async (data: Partial<RuleGroup>) => {
    if (!currentDef) return;
    await updateDefinition(currentDef.id, {
      name: currentDef.name,
      description: data.description,
      rule_type: data.type as L4RuleDefinition['rule_type'],
      priority: data.priority,
      enabled: data.enabled,
      applies_to: data.appliesTo?.factObjects || [],
      inputs: (data.inputs || []).map((i) => ({
        id: i.name,
        name: i.name,
        type: i.type || '',
      })),
      outputs: (data.outputs || []).map((o) => ({
        id: o.name,
        name: o.name,
        type: o.type || '',
      })),
    });
    fetchRules();
    message.success('规则定义已保存');
  };

  const handleDeleteLogic = async (logicId: string) => {
    setDeletingLogicId(logicId);
    try {
      await deleteLogic(logicId);
      message.success('规则逻辑已删除');
    } catch {
      message.error('删除失败');
    } finally {
      setDeletingLogicId(null);
    }
  };

  const handleEditLogic = (logicId: string) => {
    navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(definitionId)}/logic/${logicId}`);
  };

  const handleAddLogic = () => {
    navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(definitionId)}/logic/new`);
  };

  const handleBackToList = () => {
    navigate(`/spaces/${spaceId}/rules`);
  };

  // ─── 加载态 ─────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    message.error(error);
    clearError();
  }

  if (!currentDef) {
    return (
      <div>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          size="small"
          onClick={handleBackToList}
          style={{ marginBottom: 12 }}
        >
          返回规则列表
        </Button>
      </div>
    );
  }

  // ─── 规则类型配置 ──────────────────────────────────────────────────────────
  const TYPE_COLOR: Record<string, string> = {
    constraint: 'blue',
    inference: 'purple',
    alert: 'orange',
    decision: 'green',
  };
  const TYPE_LABEL: Record<string, string> = {
    constraint: '约束',
    inference: '推理',
    alert: '告警',
    decision: '决策',
  };

  // Get related logics count
  const logicListItems = logics
    .filter((l) => l.definition_id === definitionId)
    .sort((a, b) => (a.priority || 0) - (b.priority || 0));

  // ─── 渲染 ───────────────────────────────────────────────────────────────────
  return (
    <Row gutter={8} style={{ height: 'calc(100% - 48px)' }}>
      {/* ── 左栏：规则定义（可收起） ── */}
      <Col
        span={definitionCollapsed ? 1 : 7}
        style={{
          display: 'flex',
          flexDirection: 'column',
          transition: 'all 0.3s ease',
          minWidth: definitionCollapsed ? 48 : undefined,
        }}
      >
        <Card
          title={
            definitionCollapsed ? (
              <span style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                规则定义
              </span>
            ) : (
              <Space>
                <FileTextOutlined style={{ color: '#1890ff' }} />
                <span style={{ fontSize: 13 }}>规则定义</span>
              </Space>
            )
          }
          size="small"
          extra={
            <Button
              type="text"
              size="small"
              icon={definitionCollapsed ? <DownOutlined /> : <UpOutlined />}
              onClick={() => setDefinitionCollapsed(!definitionCollapsed)}
              title={definitionCollapsed ? '展开' : '收起'}
            />
          }
          style={{
            flex: 1,
            overflow: 'hidden',
            height: '100%',
          }}
          styles={{ body: { padding: definitionCollapsed ? 8 : 12, height: 'calc(100% - 42px)', overflow: 'auto' } }}
        >
          {!definitionCollapsed && currentRuleGroup && (
            <>
              <div style={{ marginBottom: 8, color: '#666', fontSize: 11 }}>
                <AppstoreOutlined style={{ marginRight: 4 }} />
                Schema 声明：基础信息、作用对象、I/O 要素
              </div>
              <RuleGroupForm
                schemaId={spaceId}
                ruleGroup={currentRuleGroup}
                onSave={handleSaveGroup}
              />
            </>
          )}
        </Card>
      </Col>

      {/* ── 右栏：规则逻辑（可收起） ── */}
      <Col
        span={definitionCollapsed ? 23 : 17}
        style={{
          display: 'flex',
          flexDirection: 'column',
          transition: 'all 0.3s ease',
        }}
      >
        {/* 规则逻辑列表 */}
        <Card
          title={
            <Space>
              <BranchesOutlined style={{ color: '#722ed1' }} />
              <span style={{ fontSize: 13 }}>规则逻辑</span>
              <Tag>{logicListItems.length}</Tag>
            </Space>
          }
          size="small"
          extra={
            <Space>
              <Button
                type="text"
                size="small"
                icon={dagCollapsed ? <DownOutlined /> : <UpOutlined />}
                onClick={() => setDagCollapsed(!dagCollapsed)}
                title={dagCollapsed ? '展开依赖图' : '收起依赖图'}
              />
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                onClick={handleAddLogic}
              >
                新增逻辑
              </Button>
            </Space>
          }
          style={{
            flex: 1,
            overflow: 'hidden',
          }}
          styles={{ body: { padding: 0, height: dagCollapsed ? 'calc(100% - 42px)' : 'calc(100% - 220px)', overflow: 'auto' } }}
        >
          <RuleLogicList
            definitionId={definitionId}
            logics={logics}
            onEditLogic={handleEditLogic}
            onDeleteLogic={handleDeleteLogic}
            onAddLogic={handleAddLogic}
            deletingLogicId={deletingLogicId}
          />
        </Card>

        {/* 要素依赖图（可收起） */}
        {!dagCollapsed && dagData && dagData.nodes.length > 0 && (
          <Card
            title={
              <Space>
                <NodeExpandOutlined style={{ color: '#13c2c2' }} />
                <span style={{ fontSize: 12 }}>要素依赖图</span>
              </Space>
            }
            size="small"
            style={{ marginTop: 8, flexShrink: 0 }}
            styles={{ body: { padding: 8, height: 180 } }}
          >
            <RuleChainDAG
              chainData={dagData}
              onNodeClick={(nodeId) => {
                if (!nodeId.startsWith('INPUT:') && !nodeId.startsWith('OUTPUT:')) {
                  handleEditLogic(nodeId);
                }
              }}
              editable={false}
              onReorder={() => {}}
            />
          </Card>
        )}
      </Col>
    </Row>
  );
};

export default RuleGroupDetailPanel;
