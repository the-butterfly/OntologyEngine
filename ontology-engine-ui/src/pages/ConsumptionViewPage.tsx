// ontology-engine-ui/src/pages/ConsumptionViewPage.tsx
// Standalone consumption view page

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Breadcrumb, Tag, Space, Typography, Card, Spin, message, Alert, Tabs } from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../store/spaceStore';
import { spaceApi } from '../api/spaceApi';
import SchemaVisualizationPage from './consumption/SchemaVisualizationPage';
import RuleExecutionPage from './consumption/RuleExecutionPage';
import SimulationPage from './SimulationPage';
import ViewEntitiesPage from './consumption/ViewEntitiesPage';

const { Title } = Typography;

interface ViewStats {
  entity_count: number;
  relation_count: number;
  rule_definition_count: number;
  rule_logic_count: number;
}

export default function ConsumptionViewPage() {
  const { viewId } = useParams<{ viewId: string }>();
  const navigate = useNavigate();
  const { setActiveView } = useSpaceStore();
  const [loading, setLoading] = useState(true);
  const [viewInfo, setViewInfo] = useState<any>(null);
  const [viewStats, setViewStats] = useState<ViewStats>({
    entity_count: 0,
    relation_count: 0,
    rule_definition_count: 0,
    rule_logic_count: 0,
  });
  const [activeTab, setActiveTab] = useState('visualize');

  // Set active view ID when page loads
  useEffect(() => {
    if (viewId) {
      setActiveView(viewId);
    }
  }, [viewId, setActiveView]);

  useEffect(() => {
    if (viewId) {
      // Load view info
      fetch(`/v1/consumption/views/${viewId}`)
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setViewInfo(data.data);
          }
          setLoading(false);
        })
        .catch(() => {
          message.error('无法加载消费视图');
          setLoading(false);
        });

      // Load view statistics in parallel
      Promise.all([
        spaceApi.listViewEntities(viewId),
        spaceApi.getRuleDependencyGraph(viewId),
      ])
        .then(([entities, graph]) => {
          setViewStats({
            entity_count: entities.length,
            relation_count: graph.dependency_edges?.length || 0,
            rule_definition_count: graph.nodes?.length || 0,
            rule_logic_count: graph.execution_order?.length || 0,
          });
        })
        .catch(() => {});
    }
  }, [viewId]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!viewInfo) {
    return (
      <div style={{ padding: 24 }}>
        <Alert message="消费视图不存在或已被删除" type="error" />
      </div>
    );
  }

  const isActive = viewInfo.status === 'active';

  const tabItems = [
    {
      key: 'visualize',
      label: <span><ApartmentOutlined /> Schema 可视化</span>,
      children: isActive ? <SchemaVisualizationPage /> : null,
    },
    {
      key: 'execute',
      label: <span><BranchesOutlined /> 规则执行</span>,
      children: isActive ? <RuleExecutionPage /> : null,
    },
    {
      key: 'instances',
      label: <span><DatabaseOutlined /> 数据实例</span>,
      children: isActive ? <ViewEntitiesPage /> : null,
    },
    {
      key: 'simulate',
      label: <span><ExperimentOutlined /> What-If 模拟</span>,
      children: isActive ? <SimulationPage /> : null,
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb
        items={[
          { title: <a onClick={() => navigate('/spaces')}>管理面</a> },
          { title: '消费视图' },
          { title: viewInfo.name },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Space style={{ marginBottom: 16 }} wrap>
        <Tag color={isActive ? 'green' : 'orange'}>
          {viewInfo.status.toUpperCase()}
        </Tag>
        <Tag color="purple">{viewId}</Tag>
        <Tag>{viewInfo.description}</Tag>
        <Tag color="blue">实体: {viewStats.entity_count}</Tag>
        <Tag color="cyan">关系: {viewStats.relation_count}</Tag>
        <Tag color="orange">规则: {viewStats.rule_logic_count}</Tag>
      </Space>

      {!isActive && (
        <Alert
          message="消费视图未激活"
          description="请在管理面激活空间后使用消费视图功能。"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      </Card>
    </div>
  );
}
