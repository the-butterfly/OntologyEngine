// ontology-engine-ui/src/pages/spaces/SpaceDetailPage.tsx
// Space detail layout - contains nested routes for space management

import { useEffect } from 'react';
import { useParams, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Breadcrumb, Menu, Tag, Space, Typography, Card, Spin, message, Alert, Button, Tooltip } from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  DatabaseOutlined,
  HistoryOutlined,
  SettingOutlined,
  ExperimentOutlined,
  RocketOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';

const { Title } = Typography;

const menuItems = [
  { key: 'schema', icon: <ApartmentOutlined />, label: 'Schema 声明' },
  { key: 'rules/declarations', icon: <SettingOutlined />, label: '规则声明' },
  { key: 'rules/logics', icon: <BranchesOutlined />, label: '规则逻辑' },
  { key: 'instances', icon: <DatabaseOutlined />, label: '数据实例' },
  { key: 'versions', icon: <HistoryOutlined />, label: '版本历史' },
  { key: 'visualize', icon: <ApartmentOutlined />, label: 'Schema 可视化' },
  { key: 'execute', icon: <BranchesOutlined />, label: '规则执行' },
  { key: 'simulate', icon: <ExperimentOutlined />, label: 'What-If 模拟' },
];

export default function SpaceDetailPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const {
    activeSpace,
    activeSpaceId,
    loading,
    setActiveSpace,
    setActiveView,
    error,
    clearError,
  } = useSpaceStore();

  useEffect(() => {
    if (spaceId && spaceId !== activeSpaceId) {
      setActiveSpace(spaceId);
    }
  }, [spaceId]);

  // Set active view when space is loaded
  useEffect(() => {
    if (activeSpace?.view_id) {
      setActiveView(activeSpace.view_id);
    }
  }, [activeSpace?.view_id]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  // Get current selected key from path
  const getSelectedKey = () => {
    const path = location.pathname;
    const suffixes = ['schema', 'rules/declarations', 'rules/logics', 'instances', 'versions', 'visualize', 'execute', 'simulate'];
    for (const suffix of suffixes) {
      if (path.includes(`/${suffix}`)) {
        return suffix;
      }
    }
    return 'schema';
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(`/spaces/${spaceId}/${key}`);
  };

  // Check if current route is a consumption operation
  const isConsumptionRoute = () => {
    const path = location.pathname;
    return path.includes('/visualize') || path.includes('/execute') || path.includes('/simulate');
  };

  if (loading || !activeSpace) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb
        items={[
          { title: '语义空间', path: '/spaces' },
          { title: activeSpace.name },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Space style={{ marginBottom: 16 }}>
        <Tag color="blue">v{activeSpace.version}</Tag>
        <Tag color={activeSpace.status === 'active' ? 'green' : 'blue'}>
          {activeSpace.status.toUpperCase()}
        </Tag>
        <Tag>{activeSpace.entity_count} 实体</Tag>
        <Tag>{activeSpace.rule_definition_count} 规则声明</Tag>
        <Tag>{activeSpace.rule_logic_count} 规则逻辑</Tag>
        {activeSpace.view_id && (
          <Tag color="purple">视图: {activeSpace.view_id}</Tag>
        )}
        {activeSpace.status === 'active' && activeSpace.view_id && (
          <Tooltip title="进入消费视图">
            <Button
              type="link"
              icon={<RocketOutlined />}
              onClick={() => navigate(`/consumption/${activeSpace.view_id}`)}
            >
              消费视图
            </Button>
          </Tooltip>
        )}
        {activeSpace.status === 'active' && !activeSpace.view_id && (
          <Tag color="orange">未创建消费视图</Tag>
        )}
      </Space>

      {isConsumptionRoute() && !activeSpace.view_id && (
        <Alert
          message="消费视图未创建"
          description="请先激活空间以创建消费视图，才能使用可视化、规则执行和模拟功能。"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {isConsumptionRoute() && activeSpace.view_id && activeSpace.status !== 'active' && (
        <Alert
          message="空间未激活"
          description="请先激活空间后才能使用消费视图功能。"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <div style={{ display: 'flex', gap: 24 }}>
          <Menu
            mode="inline"
            selectedKeys={[getSelectedKey()]}
            onClick={handleMenuClick}
            style={{ width: 200, borderRight: '1px solid #f0f0f0' }}
            items={menuItems}
          />
          <div style={{ flex: 1, overflow: 'auto' }}>
            <Outlet />
          </div>
        </div>
      </Card>
    </div>
  );
}
