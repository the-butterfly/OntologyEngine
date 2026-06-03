// ontology-engine-ui/src/App.tsx
// Main application with React Router

import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { Layout, Menu, Typography } from 'antd';
import {
  DatabaseOutlined,
  RocketOutlined,
  BulbOutlined,
} from '@ant-design/icons';

// Management Pages
import SpaceListPage from './pages/spaces/SpaceListPage';
import SpaceDetailPage from './pages/spaces/SpaceDetailPage';
import SchemaDeclarationPage from './pages/spaces/SchemaDeclarationPage';
import InstanceDataPage from './pages/spaces/InstanceDataPage';
import InstanceGraphPage from './pages/spaces/InstanceGraphPage';
import VersionHistoryPage from './pages/spaces/VersionHistoryPage';

// Agent Memory Pages
import {
  MemoryOverviewPage,
  MemoryBuildPage,
  MemoryManagePage,
  MemoryConsumePage,
  ReflectCenterPage,
} from './pages/spaces/memory';

// Memory Landing Page (top-level "记忆空间" entry)
import MemorySpacePage from './pages/memory/MemorySpacePage';
import { KnowledgeExplorerPage } from './pages/explorer';

// Rule Embed Pages（内嵌于 SpaceDetailPage 右侧内容区）
import RulesEmbedPage from './pages/spaces/RulesEmbedPage';
import RuleGroupDetailEmbedPage from './pages/spaces/RuleGroupDetailEmbedPage';
import RuleGroupCreateEmbedPage from './pages/spaces/RuleGroupCreateEmbedPage';
import RuleLogicCanvasPage from './pages/spaces/RuleLogicCanvasPage';

// Consumption Pages
import SchemaVisualizationPage from './pages/consumption/SchemaVisualizationPage';
import RuleExecutionPage from './pages/consumption/RuleExecutionPage';
import SimulationPage from './pages/SimulationPage'; // Reuse existing
import ConsumptionViewPage from './pages/ConsumptionViewPage';
import ConsumptionViewListPage from './pages/consumption/ConsumptionViewListPage';
import SimulationEmbedPage from './pages/simulation/SimulationEmbedPage';

// Rule Pages —— 保留独立路由以兼容直链 / 外部工具跳转 (Phase 2 遗留)
import { RuleGroupListPage } from './pages/rules/RuleGroupListPage';
import { RuleGroupDetailPage } from './pages/rules/RuleGroupDetailPage';
import { RuleGroupCreatePage } from './pages/rules/RuleGroupCreatePage';
import { RuleStepEditPage } from './pages/rules/RuleStepEditPage';

import './App.css';

const { Header, Content } = Layout;
const { Title } = Typography;

function App() {
  return (
    <BrowserRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
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
              { key: 'spaces', icon: <DatabaseOutlined />, label: <Link to="/spaces">知识管理</Link> },
              { key: 'memory', icon: <BulbOutlined />, label: <Link to="/memory">记忆空间</Link> },
              { key: 'consumption', icon: <RocketOutlined />, label: <Link to="/consumption">知识消费</Link> },
            ]}
            style={{ flex: 1, border: 'none' }}
          />
        </Header>
        <Content style={{ padding: 0, overflow: 'auto' }}>
          <Routes>
            {/* ── 知识管理路由 ── */}
            <Route path="/spaces" element={<SpaceListPage />} />
            <Route path="/spaces/:spaceId" element={<SpaceDetailPage />}>
              <Route index element={<Navigate to="schema" replace />} />
              <Route path="schema" element={<SchemaDeclarationPage />} />
              <Route path="instances" element={<InstanceDataPage />} />
              <Route path="instance-graph" element={<InstanceGraphPage />} />
              <Route path="versions" element={<VersionHistoryPage />} />
              <Route path="visualize" element={<SchemaVisualizationPage />} />
              <Route path="execute" element={<RuleExecutionPage />} />
              <Route path="simulate" element={<SimulationPage />} />

              {/*
               * ── 规则管理内嵌路由 ──────────────────────────────────────────────
               * 设计原则：
               *   - 管理面的面包屑和左侧菜单由 SpaceDetailPage 提供
               *   - 右侧 <Outlet /> 渲染下列三个嵌入式规则组件
               *   - 组件内仅含"规则列表 / 新建 / 详情"的内部导航
               *
               * A2UI 扩展说明：
               *   未来若 A2UI 需要独立渲染规则管理模块，
               *   直接 import RulesEmbedPage / RuleGroupDetailEmbedPage
               *   并传入 spaceId / groupId prop 即可，无需嵌套在此路由树下。
               * ────────────────────────────────────────────────────────────────
               */}
              <Route path="rules" element={<RulesEmbedPage />} />
              <Route path="rules/new" element={<RuleGroupCreateEmbedPage />} />
              <Route path="rules/:groupId" element={<RuleGroupDetailEmbedPage />} />
              {/* 规则逻辑 DAG 画布 */}
              <Route path="rules/:groupId/logic/:logicId" element={<RuleLogicCanvasPage />} />
              <Route path="rules/:groupId/logic/new" element={<RuleLogicCanvasPage />} />

              {/* Agent Memory Routes (保留在 space 下用于空间内访问) */}
              <Route path="memory" element={<MemoryOverviewPage />} />
              <Route path="memory/build" element={<MemoryBuildPage />} />
              <Route path="memory/manage" element={<MemoryManagePage />} />
              <Route path="memory/consume" element={<MemoryConsumePage />} />
              <Route path="memory/reflect" element={<ReflectCenterPage />} />
              <Route path="explorer" element={<KnowledgeExplorerPage />} />
            </Route>

            {/* 记忆空间入口 — Agent Memory 空间选择页 */}
            <Route path="/memory" element={<MemorySpacePage />} />

            {/* ── 知识消费路由 ── */}
            <Route path="/consumption" element={<ConsumptionViewListPage />} />
            <Route path="/consumption/:viewId" element={<ConsumptionViewPage />} />
            <Route path="/simulation/embed" element={<SimulationEmbedPage />} />

            {/*
             * ── 独立规则管理路由（兼容保留）──────────────────────────────────────
             * 保留此组路由，供以下场景使用：
             *   1. 外部系统直链 /rules?schemaId=xxx
             *   2. 开发期独立调试规则管理模块
             *   3. 未来平台化时的独立部署
             * ───────────────────────────────────────────────────────────────────
             */}
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

