// ontology-engine-ui/src/pages/rules/RuleGroupLayout.tsx
// Layout component for rule management pages

import React from 'react';
import { Layout, Breadcrumb, Space, Tag, Button } from 'antd';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { ArrowLeftOutlined } from '@ant-design/icons';

const { Content } = Layout;

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
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const schemaId = searchParams.get('schemaId') || '';

  // Build rule list link, preserving schemaId context
  const ruleListPath = schemaId ? `/rules?schemaId=${schemaId}` : '/rules';
  // Build space detail link if we know the schemaId
  const spaceDetailPath = schemaId ? `/spaces/${schemaId}/schema` : '/spaces';

  return (
    <Layout style={{ minHeight: '100%', background: '#f5f5f5' }}>
      {/* Top bar with breadcrumb + back button */}
      <div
        style={{
          background: '#fff',
          padding: '12px 24px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          size="small"
          onClick={() => navigate(ruleListPath)}
          style={{ color: '#666' }}
        >
          规则列表
        </Button>
        <div style={{ width: 1, height: 16, background: '#e8e8e8' }} />
        <Breadcrumb
          items={[
            { title: <Link to={spaceDetailPath}>语义空间</Link> },
            { title: <Link to={ruleListPath}>规则管理</Link> },
            ...breadcrumbs.map((b) => ({
              title: b.path ? <Link to={b.path}>{b.label}</Link> : b.label,
            })),
          ]}
        />
        {schemaId && (
          <Space style={{ marginLeft: 'auto' }}>
            <Tag color="blue" style={{ fontSize: 11 }}>
              空间: {schemaId}
            </Tag>
          </Space>
        )}
      </div>
      <Content style={{ padding: '24px' }}>{children}</Content>
    </Layout>
  );
};

export default RuleGroupLayout;
