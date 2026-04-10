import { useState } from 'react';
import { Layout, Menu, Typography } from 'antd';
import {
  ApartmentOutlined,
  BranchesOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import SchemaPage from './pages/SchemaPage';
import RuleChainPage from './pages/RuleChainPage';
import SimulationPage from './pages/SimulationPage';
import './App.css';

const { Header, Content } = Layout;
const { Title } = Typography;

type PageKey = 'schema' | 'rules' | 'simulate';

function App() {
  const [currentPage, setCurrentPage] = useState<PageKey>('schema');

  const pages: Record<PageKey, React.ReactNode> = {
    schema: <SchemaPage />,
    rules: <RuleChainPage />,
    simulate: <SimulationPage />,
  };

  return (
    <Layout style={{ height: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', background: '#fff', borderBottom: '1px solid #f0f0f0', padding: '0 24px' }}>
        <Title level={4} style={{ margin: 0, marginRight: 40, color: '#1890FF' }}>
          🏗️ OntologyEngine
        </Title>
        <Menu
          mode="horizontal"
          selectedKeys={[currentPage]}
          onClick={({ key }) => setCurrentPage(key as PageKey)}
          items={[
            { key: 'schema', icon: <ApartmentOutlined />, label: 'Schema 可视化' },
            { key: 'rules', icon: <BranchesOutlined />, label: '规则链' },
            { key: 'simulate', icon: <ExperimentOutlined />, label: 'What-if 模拟' },
          ]}
          style={{ flex: 1, border: 'none' }}
        />
      </Header>
      <Content style={{ padding: 0, overflow: 'hidden' }}>
        {pages[currentPage]}
      </Content>
    </Layout>
  );
}

export default App;
