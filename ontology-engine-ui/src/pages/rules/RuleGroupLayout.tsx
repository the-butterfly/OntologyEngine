// ontology-engine-ui/src/pages/rules/RuleGroupLayout.tsx
// Layout component for rule management pages

import React from 'react';
import { Layout, Breadcrumb } from 'antd';
import { Link } from 'react-router-dom';

const { Header, Content } = Layout;

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface RuleGroupLayoutProps {
  children: React.ReactNode;
  breadcrumbs?: BreadcrumbItem[];
}

export const RuleGroupLayout: React.FC<RuleGroupLayoutProps> = ({
  children,
  breadcrumbs = [],
}) => {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#fff',
          padding: '0 24px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Breadcrumb
          style={{ lineHeight: '64px' }}
          items={[
            {
              title: <Link to="/">首页</Link>,
            },
            {
              title: <Link to="/rules">规则管理</Link>,
            },
            ...breadcrumbs.map((b) => ({
              title: b.path ? <Link to={b.path}>{b.label}</Link> : b.label,
            })),
          ]}
        />
      </Header>
      <Content style={{ padding: '24px' }}>{children}</Content>
    </Layout>
  );
};

export default RuleGroupLayout;
