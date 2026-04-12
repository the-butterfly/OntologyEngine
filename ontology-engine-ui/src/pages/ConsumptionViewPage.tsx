// ontology-engine-ui/src/pages/ConsumptionViewPage.tsx
// Standalone consumption view page

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Breadcrumb, Menu, Tag, Space, Typography, Card, Spin, message, Alert, Tabs } from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  ExperimentOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../store/spaceStore';
import SchemaVisualizationPage from './consumption/SchemaVisualizationPage';
import RuleExecutionPage from './consumption/RuleExecutionPage';
import SimulationPage from './SimulationPage';

const { Title } = Typography;

export default function ConsumptionViewPage() {
  const { viewId } = useParams<{ viewId: string }>();
  const navigate = useNavigate();
  const { setActiveView } = useSpaceStore();
  const [loading, setLoading] = useState(true);
  const [viewInfo, setViewInfo] = useState<any>(null);
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

      <Space style={{ marginBottom: 16 }}>
        <Tag color={isActive ? 'green' : 'orange'}>
          {viewInfo.status.toUpperCase()}
        </Tag>
        <Tag color="purple">{viewId}</Tag>
        <Tag>{viewInfo.description}</Tag>
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
