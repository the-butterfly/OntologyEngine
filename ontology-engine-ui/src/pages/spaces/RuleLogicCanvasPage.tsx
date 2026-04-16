// ontology-engine-ui/src/pages/spaces/RuleLogicCanvasPage.tsx
// 规则逻辑画布页面 - 独立的 DAG 可视化编辑界面
//
// 功能：
//   1. 展示规则逻辑的 DAG 可视化图
//   2. 支持添加、编辑、删除计算节点
//   3. 配置节点参数
//   4. 保存逻辑到 Schema L4 API

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Spin,
  message,
  Button,
  Space,
  Breadcrumb,
  Tag,
} from 'antd';
import {
  ArrowLeftOutlined,
  UndoOutlined,
  RedoOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { ReactFlowProvider } from '@xyflow/react';
import { DAGCanvas } from '../../components/rule/RuleLogicCanvas';
import { spaceApi } from '../../api/spaceApi';
import { useL4Rules, L4RuleDefinition } from '../../hooks/useL4Rules';
import type { DAGNodeData, DAGNodeType } from '../../types/dag';

interface RuleLogicCanvasPageProps {
  spaceId?: string;
  definitionId?: string;
  logicId?: string;
}

export const RuleLogicCanvasPage: React.FC<RuleLogicCanvasPageProps> = ({
  spaceId: propSpaceId,
  definitionId: propDefinitionId,
  logicId: propLogicId,
}) => {
  const { spaceId: paramSpaceId, definitionId: paramDefinitionId, logicId: paramLogicId } = useParams<{
    spaceId: string;
    definitionId: string;
    logicId?: string;
  }>();

  const spaceId = propSpaceId || paramSpaceId || '';
  const definitionId = propDefinitionId || '';
  const navigate = useNavigate();

  // 使用 useL4Rules 获取数据
  const { definitions, loading, fetchRules } = useL4Rules(spaceId);

  // 从 definitions 中找到当前规则定义
  const definition = useMemo(() => {
    const found = definitions.find((d) => d.id === decodeURIComponent(definitionId));
    return found || null;
  }, [definitions, definitionId]);

  // 加载规则定义
  useEffect(() => {
    if (spaceId) {
      fetchRules();
    }
  }, [spaceId, fetchRules]);

  // 保存逻辑
  const [saving, setSaving] = useState(false);
  const handleSave = useCallback(
    async (nodes: any[], edges: any[]) => {
      if (!spaceId || !definitionId) {
        message.error('缺少必要参数');
        return;
      }

      setSaving(true);
      try {
        const logicData = {
          id: paramLogicId || `rl_${Date.now()}`,
          definition_id: decodeURIComponent(definitionId),
          when: {
            expression: '',
          },
          then_action: {
            action_type: 'dag_execute',
            output: {
              nodes: nodes.map((n) => ({
                id: n.id,
                type: n.data?.type,
                config: n.data?.config,
              })),
              edges: edges.map((e) => ({
                source: e.source,
                target: e.target,
              })),
            },
          },
        };

        if (paramLogicId) {
          await spaceApi.updateRuleLogic(spaceId, paramLogicId, logicData as any);
          message.success('逻辑更新成功');
        } else {
          await spaceApi.createRuleLogic(spaceId, logicData as any);
          message.success('逻辑创建成功');
        }

        navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(definitionId)}`);
      } catch (err) {
        console.error('保存失败:', err);
        message.error('保存失败，请重试');
      } finally {
        setSaving(false);
      }
    },
    [spaceId, definitionId, paramLogicId, navigate]
  );

  // 返回规则详情页
  const handleBack = () => {
    navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(definitionId)}`);
  };

  // 初始化输入/输出节点
  const initialNodes = React.useMemo(() => {
    if (!definition) return [];

    const ioNodes: any[] = [];

    // 添加输入节点（从 L4RuleDefinition.inputs 继承）
    (definition.inputs || []).forEach((input, idx) => {
      ioNodes.push({
        id: `input-${input.id}`,
        type: 'base',
        position: { x: 50, y: 100 + idx * 80 },
        data: {
          type: 'input' as DAGNodeType,
          label: input.name,
          config: {},
          inputs: [],
          outputs: [input.id],
          status: 'configured' as const,
        },
      });
    });

    // 添加输出节点（从 L4RuleDefinition.outputs 继承）
    (definition.outputs || []).forEach((output, idx) => {
      ioNodes.push({
        id: `output-${output.id}`,
        type: 'base',
        position: { x: 700, y: 100 + idx * 80 },
        data: {
          type: 'output' as DAGNodeType,
          label: output.name,
          config: {},
          inputs: [output.id],
          outputs: [],
          status: 'configured' as const,
        },
      });
    });

    return ioNodes;
  }, [definition]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载规则逻辑..." />
      </div>
    );
  }

  return (
    <div
      data-a2ui-component="rule-logic-canvas"
      data-a2ui-space-id={spaceId}
      style={{ 
        height: '100vh',  // 使用视口高度
        display: 'flex', 
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* 顶部导航 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          background: '#fff',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={handleBack}
              style={{ color: '#666' }}
            >
              返回
            </Button>
            <Breadcrumb
              items={[
                {
                  title: (
                    <span
                      style={{ cursor: 'pointer', color: '#1890ff' }}
                      onClick={() => navigate(`/spaces/${spaceId}/rules`)}
                    >
                      规则管理
                    </span>
                  ),
                },
                {
                  title: definition?.name || '规则逻辑',
                },
                {
                  title: paramLogicId ? '编辑逻辑' : '新建逻辑',
                },
              ]}
            />
          </Space>

          <Space>
            <Tag color="blue">
              {definition?.rule_type === 'decision'
                ? '决策'
                : definition?.rule_type === 'constraint'
                ? '约束'
                : definition?.rule_type === 'inference'
                ? '推理'
                : '告警'}
            </Tag>
            <Button icon={<UndoOutlined />} disabled>
              撤销
            </Button>
            <Button icon={<RedoOutlined />} disabled>
              重做
            </Button>
            <Button icon={<PlayCircleOutlined />} disabled>
              预览
            </Button>
          </Space>
        </div>

        {/* 规则信息（继承输入输出要素） */}
        {definition && (
          <div style={{ marginTop: 12, padding: '8px 12px', background: '#f5f5f5', borderRadius: 6 }}>
            <Space size={16}>
              <span style={{ fontSize: 13 }}>
                <strong>输入要素：</strong>
                {(definition.inputs || []).map((i) => i.name).join(', ') || '无'}
              </span>
              <span style={{ fontSize: 13 }}>
                <strong>输出要素：</strong>
                {(definition.outputs || []).map((o) => o.name).join(', ') || '无'}
              </span>
            </Space>
          </div>
        )}
      </div>

      {/* DAG 画布 - 需要 ReactFlowProvider 包裹以支持 useReactFlow hook */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <ReactFlowProvider>
          <DAGCanvas
            initialNodes={initialNodes}
            initialEdges={[]}
            onSave={handleSave}
            availableInputs={(definition?.inputs || []).map(i => i.name)}
            availableOutputs={(definition?.outputs || []).map(o => o.name)}
          />
        </ReactFlowProvider>
      </div>
    </div>
  );
};

export default RuleLogicCanvasPage;
