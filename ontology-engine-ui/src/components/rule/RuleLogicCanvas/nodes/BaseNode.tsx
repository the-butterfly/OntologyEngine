// ontology-engine-ui/src/components/rule/RuleLogicCanvas/nodes/BaseNode.tsx
// 基础节点组件 - 美化版

import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Tag, Space } from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  BarChartOutlined,
  StarOutlined,
  CalculatorOutlined,
  TableOutlined,
  RobotOutlined,
  RightOutlined,
  FunctionOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import type { DAGNodeData, DAGNodeType } from '../../../../types/dag';

interface BaseNodeProps {
  data: DAGNodeData;
  selected?: boolean;
  showInputHandle?: boolean;
  showOutputHandle?: boolean;
  isReadOnly?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

const ICON_MAP: Record<DAGNodeType, React.ReactNode> = {
  input: <ArrowLeftOutlined />,
  output: <ArrowRightOutlined />,
  binning: <BarChartOutlined />,
  scorecard: <StarOutlined />,
  weighted_sum: <CalculatorOutlined />,
  decision_table: <TableOutlined />,
  llm_judge: <RobotOutlined />,
  switch: <RightOutlined />,
  compute: <FunctionOutlined />,
};

const NODE_META: Record<DAGNodeType, { color: string; bgColor: string; label: string }> = {
  input: { color: '#1890ff', bgColor: '#e6f4ff', label: '输入要素' },
  output: { color: '#52c41a', bgColor: '#f6ffed', label: '输出要素' },
  binning: { color: '#722ed1', bgColor: '#f9f0ff', label: '分箱' },
  scorecard: { color: '#fa8c16', bgColor: '#fff7e6', label: '评分卡' },
  weighted_sum: { color: '#f5222d', bgColor: '#fff1f0', label: '加权计算' },
  decision_table: { color: '#faad14', bgColor: '#fffbe6', label: '决策表' },
  llm_judge: { color: '#13c2c2', bgColor: '#e6fffb', label: 'LLM定性' },
  switch: { color: '#eb2f96', bgColor: '#fff0f6', label: '条件分支' },
  compute: { color: '#8c8c8c', bgColor: '#f5f5f5', label: '公式计算' },
};

export const BaseNode: React.FC<BaseNodeProps> = memo(({
  data,
  selected,
  showInputHandle = true,
  showOutputHandle = true,
  isReadOnly = false,
}) => {
  const { type, label, status } = data;
  const meta = NODE_META[type] || { color: '#8c8c8c', bgColor: '#f5f5f5', label: '未知' };

  const statusConfig = {
    configured: { color: '#52c41a', text: '已配置' },
    unconfigured: { color: '#faad14', text: '未配置' },
    error: { color: '#f5222d', text: '错误' },
  }[status] || { color: '#8c8c8c', text: '未知' };

  const nodeIcon = ICON_MAP[type] || <FunctionOutlined />;

  const dragHandleProps = isReadOnly ? undefined : {
    style: { cursor: 'grab' } as React.CSSProperties,
  };

  return (
    <div
      className={`rule-canvas-node ${selected ? 'selected' : ''}`}
      style={{
        background: meta.bgColor,
        border: selected ? `2px solid ${meta.color}` : `1px solid ${meta.color}40`,
        borderRadius: 12,
        minWidth: 180,
        maxWidth: 220,
        boxShadow: selected 
          ? `0 8px 24px ${meta.color}30, 0 0 0 1px ${meta.color}` 
          : '0 2px 8px rgba(0,0,0,0.08)',
        overflow: 'hidden',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        fontFamily: "'SF Pro Text', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
      {...dragHandleProps}
    >
      {/* 顶部渐变色条 */}
      <div
        style={{
          height: 4,
          background: `linear-gradient(90deg, ${meta.color}, ${meta.color}80)`,
        }}
      />

      {/* 头部 */}
      <div
        style={{
          padding: '10px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(255,255,255,0.7)',
        }}
      >
        <Space size={8}>
          <span 
            style={{ 
              color: meta.color, 
              fontSize: 18,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {nodeIcon}
          </span>
          <span 
            style={{ 
              fontWeight: 600, 
              fontSize: 13,
              color: '#262626',
              maxWidth: 120,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={label}
          >
            {label}
          </span>
        </Space>
        {!isReadOnly && (
          <MoreOutlined
            style={{ color: '#bfbfbf', cursor: 'pointer', fontSize: 14 }}
            onClick={(e) => {
              e.stopPropagation();
            }}
          />
        )}
      </div>

      {/* 节点类型标签 */}
      <div style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.5)' }}>
        <Tag 
          color={meta.color} 
          style={{ 
            margin: 0, 
            fontSize: 11,
            borderRadius: 4,
            border: 'none',
            fontWeight: 500,
          }}
        >
          {meta.label}
        </Tag>
      </div>

      {/* 节点内容区域（算子节点显示更多） */}
      {type !== 'input' && type !== 'output' && (
        <div style={{ 
          padding: '8px 12px', 
          background: '#fff',
          fontSize: 11,
          color: '#8c8c8c',
          borderTop: '1px dashed #e8e8e8',
        }}>
          {status === 'configured' ? '✓ 已配置' : '○ 待配置'}
        </div>
      )}

      {/* 输入端口 */}
      {showInputHandle && type !== 'input' && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            background: meta.color,
            width: 12,
            height: 12,
            border: '2px solid #fff',
            boxShadow: `0 2px 4px ${meta.color}50`,
            left: -7,
          }}
          id="input"
        />
      )}

      {/* 输出端口 */}
      {showOutputHandle && type !== 'output' && (
        <Handle
          type="source"
          position={Position.Right}
          style={{
            background: meta.color,
            width: 12,
            height: 12,
            border: '2px solid #fff',
            boxShadow: `0 2px 4px ${meta.color}50`,
            right: -7,
          }}
          id="output"
        />
      )}

      {/* 底部状态条 */}
      <div
        style={{
          padding: '6px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(255,255,255,0.7)',
          borderTop: '1px solid #f0f0f0',
        }}
      >
        <span style={{ fontSize: 11, color: '#8c8c8c' }}>
          {statusConfig.text}
        </span>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: statusConfig.color,
            boxShadow: `0 0 6px ${statusConfig.color}60`,
          }}
        />
      </div>
    </div>
  );
});

BaseNode.displayName = 'BaseNode';

export default BaseNode;
