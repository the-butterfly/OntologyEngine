import React from 'react';
import { Card, Descriptions, Tag, Space, Typography, Divider } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;

interface InstanceNodeDetailProps {
  nodeId: string;
  nodeData: {
    label: string;
    concept: string;
    entity_id: string;
    credit_score?: number | string;
    status?: string;
    result_group?: string;
    hop?: number;
    properties: Record<string, unknown>;
  };
}

const RESULT_ICONS = {
  approved: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  rejected: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
  pending: <QuestionCircleOutlined style={{ color: '#faad14' }} />,
  unknown: null,
};

const RESULT_COLORS = {
  approved: 'green',
  rejected: 'red',
  pending: 'orange',
  unknown: 'default',
};

const RESULT_LABELS = {
  approved: '已通过',
  rejected: '已拒绝',
  pending: '待审核',
  unknown: '未确定',
};

export const InstanceNodeDetail: React.FC<InstanceNodeDetailProps> = ({ nodeId, nodeData }) => {
  const skipKeys = new Set(['entity_id', '_fact_object', '_concept', 'layer', 'valid_from', 'valid_to']);

  const properties = Object.entries(nodeData.properties || {})
    .filter(([key]) => !skipKeys.has(key))
    .map(([key, value]) => ({
      key,
      value: value !== null && value !== undefined ? String(value) : '-',
    }));

  return (
    <Card size="small" style={{ overflow: 'auto', height: '100%' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={5} style={{ margin: 0 }}>{nodeData.label}</Title>
          {nodeData.result_group && RESULT_ICONS[nodeData.result_group as keyof typeof RESULT_ICONS] && (
            <Tag color={RESULT_COLORS[nodeData.result_group as keyof typeof RESULT_COLORS]}>
              {RESULT_ICONS[nodeData.result_group as keyof typeof RESULT_ICONS]}
              {' '}{RESULT_LABELS[nodeData.result_group as keyof typeof RESULT_LABELS]}
            </Tag>
          )}
        </div>

        <Descriptions size="small" column={1} bordered>
          <Descriptions.Item label="实体ID">{nodeData.entity_id}</Descriptions.Item>
          <Descriptions.Item label="概念类型">{nodeData.concept}</Descriptions.Item>
          {nodeData.credit_score !== undefined && (
            <Descriptions.Item label="信用评分">{nodeData.credit_score}</Descriptions.Item>
          )}
          {nodeData.status && (
            <Descriptions.Item label="状态">{nodeData.status}</Descriptions.Item>
          )}
          {nodeData.hop !== undefined && (
            <Descriptions.Item label="跳数">{nodeData.hop === 0 ? '种子' : `${nodeData.hop} 跳`}</Descriptions.Item>
          )}
        </Descriptions>

        <Divider style={{ margin: '12px 0' }} />
        <Text strong>属性详情</Text>

        <Descriptions size="small" column={1} bordered>
          {properties.map(({ key, value }) => (
            <Descriptions.Item key={key} label={key}>{value}</Descriptions.Item>
          ))}
        </Descriptions>
      </Space>
    </Card>
  );
};

export default InstanceNodeDetail;
