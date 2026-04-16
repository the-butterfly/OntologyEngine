// ontology-engine-ui/src/pages/spaces/RuleGroupDetailEmbedPage.tsx
// 规则组详情嵌入式页面 —— 内嵌于 SpaceDetailPage 右侧内容区
//
// 交互设计（2026-04-17）：
//   - "规则定义"：编辑 Schema 声明（基础信息、作用对象、输入输出要素）
//   - "编辑逻辑"：打开独立的 DAG 画布页面，编排计算节点
//   - 两个动作完全分离，规则逻辑通过路由跳转到 RuleLogicCanvasPage

import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Row,
  Col,
  Spin,
  message,
  Button,
  Tag,
  Space,
  Typography,
  Breadcrumb,
  Alert,
  Table,
  Popconfirm,
  Empty,
} from 'antd';
import {
  ArrowLeftOutlined,
  BranchesOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  UpOutlined,
  DownOutlined,
  NodeExpandOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import RuleGroupForm from '../../components/rule/RuleGroupForm';
import RuleChainDAG from '../../components/rule/RuleChainDAG';
import { useL4Rules, L4RuleDefinition, L4RuleLogic } from '../../hooks/useL4Rules';
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

/** L4 规则逻辑列表项 */
interface LogicListItem {
  id: string;
  name: string;
  definition_id: string;
  priority: number;
  action_type: string;
  status: 'configured' | 'unconfigured';
}

// ─── 组件 Props ───────────────────────────────────────────────────────────────
export interface RuleGroupDetailEmbedPageProps {
  spaceId?: string;
  groupId?: string;  // 在 L4 中为 definitionId
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────
export const RuleGroupDetailEmbedPage: React.FC<RuleGroupDetailEmbedPageProps> = ({
  spaceId: propSpaceId,
  groupId: propGroupId,
}) => {
  const { spaceId: paramSpaceId, groupId: paramGroupId } = useParams<{
    spaceId: string;
    groupId: string;
  }>();
  const navigate = useNavigate();

  const spaceId = propSpaceId || paramSpaceId || '';
  const definitionId = decodeURIComponent(propGroupId || paramGroupId || '');

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

  // ─── 获取关联的规则逻辑 ──────────────────────────────────────────────────
  const relatedLogics = useMemo(() => {
    return logics
      .filter((l) => l.definition_id === definitionId)
      .sort((a, b) => (a.priority || 0) - (b.priority || 0));
  }, [logics, definitionId]);

  // ─── 构建规则逻辑列表 ─────────────────────────────────────────────────────
  const logicListItems: LogicListItem[] = useMemo(() => {
    return relatedLogics.map((logic) => ({
      id: logic.id,
      name: logic.name || logic.id,
      definition_id: logic.definition_id,
      priority: logic.priority || 100,
      action_type: logic.then_action?.action_type || '-',
      status: logic.then_action ? 'configured' : 'unconfigured',
    }));
  }, [relatedLogics]);

  // ─── 构建要素依赖 DAG ──────────────────────────────────────────────────────
  const dagData = useMemo((): RuleChainGraphData | null => {
    if (!currentRuleGroup || relatedLogics.length === 0) return null;

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
  }, [currentRuleGroup, relatedLogics]);

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
    // 跳转到 DAG 画布编辑页面
    navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(definitionId)}/logic/${logicId}`);
  };

  const handleAddLogic = () => {
    // 跳转到 DAG 画布新建页面
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
        <Alert type="warning" message="规则不存在或正在加载..." showIcon />
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

  // ─── 规则逻辑列表列定义 ─────────────────────────────────────────────────────
  const logicColumns: ColumnsType<LogicListItem> = [
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: number) => <Tag>{priority}</Tag>,
    },
    {
      title: '逻辑名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '算子类型',
      dataIndex: 'action_type',
      key: 'action_type',
      width: 120,
      render: (type: string) => (
        <Tag color={type === 'dag_execute' ? 'blue' : 'default'}>
          {type === 'dag_execute' ? 'DAG执行' : type}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={status === 'configured' ? 'green' : 'orange'}>
          {status === 'configured' ? '已配置' : '未配置'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: LogicListItem) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditLogic(record.id)}
            title="编辑逻辑"
          />
          <Popconfirm
            title="确定删除此逻辑？"
            onConfirm={() => handleDeleteLogic(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deletingLogicId === record.id}
              title="删除"
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ─── 渲染 ───────────────────────────────────────────────────────────────────
  return (
    <div
      data-a2ui-component="rule-group-detail-embed"
      data-a2ui-space-id={spaceId}
      data-a2ui-group-id={definitionId}
      data-source="schema-l4"
      style={{ height: '100%' }}
    >
      {/* ── 内嵌子面包屑 + 返回按钮区域 ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
          padding: '8px 0',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Button
          type="text"
          size="small"
          icon={<ArrowLeftOutlined />}
          onClick={handleBackToList}
          style={{ color: '#666', padding: '0 4px' }}
        >
          规则列表
        </Button>
        <span style={{ color: '#d9d9d9' }}>/</span>
        <Breadcrumb
          style={{ flex: 1 }}
          items={[
            {
              title: (
                <span
                  style={{ cursor: 'pointer', color: '#1890ff' }}
                  onClick={handleBackToList}
                >
                  L4 业务规则
                </span>
              ),
            },
            { title: currentDef.name },
          ]}
        />
        <Space>
          <Tag color={TYPE_COLOR[currentDef.rule_type] || 'default'}>
            {TYPE_LABEL[currentDef.rule_type] || currentDef.rule_type}
          </Tag>
          <Tag color={currentDef.enabled ? 'green' : 'default'}>
            {currentDef.enabled ? '启用' : '禁用'}
          </Tag>
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => fetchRules()}
            title="刷新"
          />
        </Space>
      </div>

      {/* ── 两栏内容区 ── */}
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
            {logicListItems.length > 0 ? (
              <Table
                columns={logicColumns}
                dataSource={logicListItems}
                rowKey="id"
                size="small"
                pagination={false}
                scroll={{ y: 'calc(100% - 40px)' }}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <span style={{ color: '#8c8c8c' }}>
                    暂无规则逻辑
                    <Button type="link" size="small" onClick={handleAddLogic}>
                      点击新增
                    </Button>
                  </span>
                }
                style={{ padding: '40px 0' }}
              />
            )}
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
    </div>
  );
};

export default RuleGroupDetailEmbedPage;
