// ontology-engine-ui/src/pages/spaces/SpaceDetailPage.tsx
// Space detail layout - contains nested routes for space management

import { useEffect, useState } from 'react';
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
  BulbOutlined,
  BuildOutlined,
  ToolOutlined,
  SearchOutlined,
  SyncOutlined,
  NodeIndexOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';

const { Title } = Typography;

// Knowledge management menu items
const kmMenuItems = [
  { key: 'schema', icon: <ApartmentOutlined />, label: 'Schema 声明' },
  { key: 'rules', icon: <BranchesOutlined />, label: '规则管理' },
  { key: 'instances', icon: <DatabaseOutlined />, label: '数据实例' },
  { key: 'instance-graph', icon: <NodeIndexOutlined />, label: '实例图谱' },
  { key: 'versions', icon: <HistoryOutlined />, label: '版本历史' },
  { key: 'visualize', icon: <ApartmentOutlined />, label: 'Schema 可视化' },
  { key: 'execute', icon: <BranchesOutlined />, label: '规则执行' },
  { key: 'simulate', icon: <ExperimentOutlined />, label: 'What-If 模拟' },
  { key: 'explorer', icon: <SearchOutlined />, label: '知识探索' },
];

// Agent Memory menu items
const memoryMenuItems = [
  { key: 'memory', icon: <BulbOutlined />, label: '记忆总览' },
  { key: 'memory/build', icon: <BuildOutlined />, label: '记忆构建' },
  { key: 'memory/manage', icon: <ToolOutlined />, label: '记忆管理' },
  { key: 'memory/consume', icon: <SearchOutlined />, label: '记忆消费' },
  { key: 'memory/reflect', icon: <SyncOutlined />, label: '反思中心' },
  { key: 'explorer', icon: <SearchOutlined />, label: '知识探索' },
];

export default function SpaceDetailPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuCollapsed, setMenuCollapsed] = useState(false);
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
    // Agent Memory routes
    if (path.includes('/memory/reflect')) return 'memory/reflect';
    if (path.includes('/memory/consume')) return 'memory/consume';
    if (path.includes('/memory/manage')) return 'memory/manage';
    if (path.includes('/memory/build')) return 'memory/build';
    if (path.includes('/memory')) return 'memory';
    // rules 系列：/spaces/:id/rules、/spaces/:id/rules/:groupId、/spaces/:id/rules/new
    if (path.includes('/rules')) return 'rules';
    if (path.endsWith('/schema')) return 'schema';
    if (path.endsWith('/instances')) return 'instances';
    if (path.endsWith('/instance-graph')) return 'instance-graph';
    if (path.endsWith('/versions')) return 'versions';
    if (path.endsWith('/visualize')) return 'visualize';
    if (path.endsWith('/execute')) return 'execute';
    if (path.endsWith('/simulate')) return 'simulate';
    if (path.endsWith('/explorer')) return 'explorer';
    return 'schema';
  };

  const handleMenuClick = ({ key }: { key: string }) => {
    // rules 菜单：内嵌到管理面右侧内容区（不再跳出到独立 /rules 路由）
    navigate(`/spaces/${spaceId}/${key}`);
  };

  // Check if current route is a consumption operation
  const isConsumptionRoute = () => {
    const path = location.pathname;
    return path.includes('/visualize') || path.includes('/execute') || path.includes('/simulate');
  };

  // Check if current route is an Agent Memory route
  const isMemoryRoute = () => {
    const path = location.pathname;
    return path.includes('/memory');
  };

  // Select menu items based on route type
  const getMenuItems = () => {
    if (isMemoryRoute()) {
      return memoryMenuItems;
    }
    return kmMenuItems;
  };

  // Show loading only while fetching, but still render layout if space not found
  // This allows memory pages to work even when the space API fails
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      {activeSpace && !isMemoryRoute() && (
        <>
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
        </>
      )}

      {activeSpace && isMemoryRoute() && (
        <>
          <Breadcrumb
            items={[
              { title: <a onClick={() => navigate('/memory')}>Agent Memory</a> },
              { title: activeSpace.name },
            ]}
            style={{ marginBottom: 16 }}
          />
          <Space style={{ marginBottom: 16 }}>
            <Tag color="blue">v{activeSpace.version}</Tag>
            <Tag color={activeSpace.status === 'active' ? 'green' : 'orange'}>
              {activeSpace.status.toUpperCase()}
            </Tag>
          </Space>
        </>
      )}

      <Card>
        <div style={{ display: 'flex', gap: 24 }}>
          <div style={{ display: 'flex', flexDirection: 'column', width: menuCollapsed ? 56 : 200, flexShrink: 0 }}>
            <Menu
              mode="inline"
              inlineCollapsed={menuCollapsed}
              selectedKeys={[getSelectedKey()]}
              onClick={handleMenuClick}
              style={{ borderRight: '1px solid #f0f0f0', flex: 1 }}
              items={getMenuItems()}
            />
            <div style={{ textAlign: 'center', padding: '8px 0', borderTop: '1px solid #f0f0f0' }}>
              <Button
                type="text"
                icon={menuCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={() => setMenuCollapsed(!menuCollapsed)}
                style={{ fontSize: 14 }}
              />
            </div>
          </div>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <Outlet />
          </div>
        </div>
      </Card>
    </div>
  );
}
