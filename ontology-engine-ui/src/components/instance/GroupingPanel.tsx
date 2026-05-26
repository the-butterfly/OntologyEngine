import React, { useState } from 'react';
import { Card, Space, Tag, Button, Typography, Collapse, Radio } from 'antd';
import {
  GroupOutlined,
  ClusterOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

interface GroupingPanelProps {
  grouping: {
    concept_groups: Record<string, string[]>;
    component_groups: string[][];
    hop_groups: Record<string, string[]>;
    result_groups: Record<string, string[]>;
  };
  metadata: {
    entity_count: number;
    relation_count: number;
    cycle_count: number;
    concept_counts: Record<string, number>;
    component_count: number;
  };
  onGroupClick?: (groupType: string, groupId: string, nodeIds: string[]) => void;
  activeGroupType?: string;
}

const CONCEPT_COLORS: Record<string, string> = {
  Supplier: 'blue',
  CoreEnterprise: 'green',
  Invoice: 'orange',
  Contract: 'purple',
  GuaranteeRelation: 'red',
  Borrower: 'cyan',
  LoanApplication: 'magenta',
  RepaymentRecord: 'gray',
};

export const GroupingPanel: React.FC<GroupingPanelProps> = ({
  grouping,
  metadata,
  onGroupClick,
  activeGroupType,
}) => {
  const [viewMode, setViewMode] = useState('concept');

  const renderConceptGroups = () => {
    const { concept_groups } = grouping;
    const { concept_counts } = metadata;
    return Object.entries(concept_groups).map(([concept, nodeIds]) => {
      const color = CONCEPT_COLORS[concept] || 'default';
      const count = concept_counts[concept] || nodeIds.length;
      return (
        <div key={concept} style={{ marginBottom: 8 }}>
          <Space>
            <Tag color={color} style={{ cursor: 'pointer' }} onClick={() => onGroupClick?.('concept', concept, nodeIds)}>
              {concept} ({count})
            </Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {nodeIds.length} 个实例
            </Text>
          </Space>
        </div>
      );
    });
  };

  const renderComponentGroups = () => {
    const { component_groups } = grouping;
    if (component_groups.length <= 1) {
      return <Text type="secondary">所有节点在同一个连通分量中</Text>;
    }
    return component_groups.map((comp, idx) => (
      <div key={idx} style={{ marginBottom: 8 }}>
        <Tag
          color="geekblue"
          style={{ cursor: 'pointer' }}
          onClick={() => onGroupClick?.('component', `comp_${idx}`, comp)}
        >
          分量 {idx + 1} ({comp.length} 节点)
        </Tag>
      </div>
    ));
  };

  const renderHopGroups = () => {
    const { hop_groups } = grouping;
    const entries = Object.entries(hop_groups).sort(([a], [b]) => Number(a) - Number(b));
    if (entries.length === 0) {
      return <Text type="secondary">未启用跳数分组，点击节点可激活</Text>;
    }
    return entries.map(([hop, nodeIds]) => (
      <div key={hop} style={{ marginBottom: 8 }}>
        <Tag
          color={Number(hop) === 0 ? 'green' : Number(hop) === 1 ? 'blue' : Number(hop) === 2 ? 'orange' : 'default'}
          style={{ cursor: 'pointer' }}
          onClick={() => onGroupClick?.('hops', `hop_${hop}`, nodeIds)}
        >
          {Number(hop) === 0 ? '种子节点' : `${hop} 跳`} ({nodeIds.length})
        </Tag>
      </div>
    ));
  };

  const renderResultGroups = () => {
    const { result_groups } = grouping;
    const icons = {
      approved: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      rejected: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
      pending: <QuestionCircleOutlined style={{ color: '#faad14' }} />,
      unknown: <GroupOutlined />,
    };
    const colors = {
      approved: 'green',
      rejected: 'red',
      pending: 'orange',
      unknown: 'default',
    };
    const labels = {
      approved: '已通过',
      rejected: '已拒绝',
      pending: '待审核',
      unknown: '未确定',
    };

    return Object.entries(result_groups).map(([result, nodeIds]) => (
      <div key={result} style={{ marginBottom: 8 }}>
        <Tag
          color={colors[result as keyof typeof colors]}
          style={{ cursor: 'pointer' }}
          onClick={() => onGroupClick?.('result', result, nodeIds)}
        >
          {icons[result as keyof typeof icons]} {labels[result as keyof typeof labels]} ({nodeIds.length})
        </Tag>
      </div>
    ));
  };

  return (
    <Card size="small" title="逻辑分组" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space size="middle" style={{ marginBottom: 12 }}>
          <Text strong style={{ fontSize: 13 }}>统计</Text>
          <Tag color="blue">{metadata.entity_count} 实体</Tag>
          <Tag color="green">{metadata.relation_count} 关系</Tag>
          {metadata.cycle_count > 0 && <Tag color="red">{metadata.cycle_count} 担保圈</Tag>}
          <Tag color="purple">{metadata.component_count} 连通分量</Tag>
        </Space>

        <Radio.Group value={viewMode} onChange={e => setViewMode(e.target.value)} size="small">
          <Radio.Button value="concept"><ClusterOutlined /> 概念类型</Radio.Button>
          <Radio.Button value="component"><GroupOutlined /> 连通分量</Radio.Button>
          <Radio.Button value="hops"><BranchesOutlined /> 检索路径</Radio.Button>
          <Radio.Button value="result"><CheckCircleOutlined /> 业务结果</Radio.Button>
        </Radio.Group>

        <Collapse
          defaultActiveKey={[]}
          size="small"
          items={[
            {
              key: 'groups',
              label: '分组详情',
              children: (
                <div style={{ maxHeight: 300, overflow: 'auto' }}>
                  {viewMode === 'concept' && renderConceptGroups()}
                  {viewMode === 'component' && renderComponentGroups()}
                  {viewMode === 'hops' && renderHopGroups()}
                  {viewMode === 'result' && renderResultGroups()}
                </div>
              ),
            },
          ]}
        />
      </Space>
    </Card>
  );
};

export default GroupingPanel;
