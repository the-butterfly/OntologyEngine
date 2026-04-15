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
  { key: 'schema', icon: <ApartmentOutlined />, label: 'Schema 声明', testId: 'menu-schema' },
  { key: 'rules/declarations', icon: <SettingOutlined />, label: '规则声明', testId: 'menu-rules-declarations' },
  { key: 'rules/logics', icon: <BranchesOutlined />, label: '规则逻辑', testId: 'menu-rules-logics' },
  { key: 'instances', icon: <DatabaseOutlined />, label: '数据实例', testId: 'menu-instances' },
  { key: 'versions', icon: <HistoryOutlined />, label: '版本历史', testId: 'menu-versions' },
  { key: 'visualize', icon: <ApartmentOutlined />, label: 'Schema 可视化', testId: 'menu-visualize' },
  { key: 'execute', icon: <BranchesOutlined />, label: '规则执行', testId: 'menu-execute' },
  { key: 'simulate', icon: <ExperimentOutlined />, label: 'What-If 模拟', testId: 'menu-simulate' },
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

  // Get current selected key from path - use exact suffix matching
  const getSelectedKey = () => {
    const path = location.pathname;
    // Exact matching to avoid ambiguity with badges that contain similar text
    if (path.endsWith('/rules/declarations')) return 'rules/declarations';
    if (path.endsWith('/rules/logics')) return 'rules/logics';
    if (path.endsWith('/schema')) return 'schema';
    if (path.endsWith('/instances')) return 'instances';
    if (path.endsWith('/versions')) return 'versions';
    if (path.endsWith('/visualize')) return 'visualize';
    if (path.endsWith('/execute')) return 'execute';
    if (path.endsWith('/simulate')) return 'simulate';
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
        <Tag color={activeSpace.status === 'active' ? 'green' : activeSpace.status === 'draft' ? 'orange' : 'default'}>
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
          description={
            <div>
              <p>请先激活空间以创建消费视图，才能使用可视化、规则执行和模拟功能。</p>
              {activeSpace.status !== 'active' && (
                <Button
                  type="primary"
                  size="small"
                  onClick={async () => {
                    try {
                      await useSpaceStore.getState().activateSpace(spaceId!);
                      message.success('空间已激活，正在刷新...');
                      await useSpaceStore.getState().setActiveSpace(spaceId!);
                    } catch (e) {
                      message.error('激活失败');
                    }
                  }}
                  style={{ marginTop: 8 }}
                >
                  一键激活空间
                </Button>
              )}
            </div>
          }
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {isConsumptionRoute() && activeSpace.view_id && activeSpace.status !== 'active' && (
        <Alert
          message="空间未激活"
          description={
            <div>
              <p>请先激活空间后才能使用消费视图功能。</p>
              <Button
                type="primary"
                size="small"
                onClick={async () => {
                  try {
                    await useSpaceStore.getState().activateSpace(spaceId!);
                    message.success('空间已激活，正在刷新...');
                    await useSpaceStore.getState().setActiveSpace(spaceId!);
                  } catch (e) {
                    message.error('激活失败');
                  }
                }}
                style={{ marginTop: 8 }}
              >
                激活空间
              </Button>
            </div>
          }
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
