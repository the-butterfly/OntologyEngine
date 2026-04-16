// ontology-engine-ui/src/App.tsx
// Main application with React Router

import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Layout, Menu, Typography } from 'antd';
import {
  DatabaseOutlined,
  RocketOutlined,
} from '@ant-design/icons';

// Management Pages
import SpaceListPage from './pages/spaces/SpaceListPage';
import SpaceDetailPage from './pages/spaces/SpaceDetailPage';
import SchemaDeclarationPage from './pages/spaces/SchemaDeclarationPage';
import InstanceDataPage from './pages/spaces/InstanceDataPage';
import VersionHistoryPage from './pages/spaces/VersionHistoryPage';

// Consumption Pages
import SchemaVisualizationPage from './pages/consumption/SchemaVisualizationPage';
import RuleExecutionPage from './pages/consumption/RuleExecutionPage';
import SimulationPage from './pages/SimulationPage'; // Reuse existing
import ConsumptionViewPage from './pages/ConsumptionViewPage';
import ConsumptionViewListPage from './pages/consumption/ConsumptionViewListPage';

// Rule Pages (Phase 2)
import { RuleGroupListPage } from './pages/rules/RuleGroupListPage';
import { RuleGroupDetailPage } from './pages/rules/RuleGroupDetailPage';
import { RuleGroupCreatePage } from './pages/rules/RuleGroupCreatePage';
import { RuleStepEditPage } from './pages/rules/RuleStepEditPage';

import './App.css';

const { Header, Content } = Layout;
const { Title } = Typography;

function App() {
  return (
    <BrowserRouter>
      <Layout style={{ height: '100vh' }}>
        <Header style={{ display: 'flex', alignItems: 'center', background: '#fff', borderBottom: '1px solid #f0f0f0', padding: '0 24px' }}>
          <Link to="/spaces">
            <Title level={4} style={{ margin: 0, marginRight: 40, color: '#1890FF' }}>
              OntologyEngine
            </Title>
          </Link>
          <Menu
            mode="horizontal"
            selectedKeys={[]}
            items={[
              { key: 'spaces', icon: <DatabaseOutlined />, label: <Link to="/spaces">管理面</Link> },
              { key: 'consumption', icon: <RocketOutlined />, label: <Link to="/consumption">消费面</Link> },
            ]}
            style={{ flex: 1, border: 'none' }}
          />
        </Header>
        <Content style={{ padding: 0, overflow: 'auto' }}>
          <Routes>
            {/* Management Routes */}
            <Route path="/spaces" element={<SpaceListPage />} />
            <Route path="/spaces/:spaceId" element={<SpaceDetailPage />}>
              <Route index element={<Navigate to="schema" replace />} />
              <Route path="schema" element={<SchemaDeclarationPage />} />
              <Route path="instances" element={<InstanceDataPage />} />
              <Route path="versions" element={<VersionHistoryPage />} />
              <Route path="visualize" element={<SchemaVisualizationPage />} />
              <Route path="execute" element={<RuleExecutionPage />} />
              <Route path="simulate" element={<SimulationPage />} />
            </Route>

            {/* Consumption View Route */}
            <Route path="/consumption" element={<ConsumptionViewListPage />} />
            <Route path="/consumption/:viewId" element={<ConsumptionViewPage />} />

            {/* Rule Management Routes (Phase 2) */}
            <Route path="/rules" element={<RuleGroupListPage />} />
            <Route path="/rules/new" element={<RuleGroupCreatePage />} />
            <Route path="/rules/:groupId" element={<RuleGroupDetailPage />} />
            <Route path="/rules/:groupId/steps/:stepId/edit" element={<RuleStepEditPage />} />

            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/spaces" replace />} />
            <Route path="*" element={<Navigate to="/spaces" replace />} />
          </Routes>
        </Content>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
