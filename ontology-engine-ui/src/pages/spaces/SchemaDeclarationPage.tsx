// ontology-engine-ui/src/pages/spaces/SchemaDeclarationPage.tsx
// Schema declaration page - shows L1-L4 all layers in tabs

import { useState } from 'react';
import { Typography, Card, Tabs, Tag, Space, Spin, Empty, Button, Modal, Input, message } from 'antd';
import { ImportOutlined, ApartmentOutlined, TagsOutlined, BarChartOutlined, BranchesOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';

import L1FactObjectsTab from './schema/L1FactObjectsTab';
import L2CategorizationsTab from './schema/L2CategorizationsTab';
import L3AnalyticalElementsTab from './schema/L3AnalyticalElementsTab';
import L4RuleDefinitionsTab from './schema/L4RuleDefinitionsTab';

const { Title, Paragraph } = Typography;

export default function SchemaDeclarationPage() {
  const { activeSpaceId, factObjects, loading, setActiveSpace } = useSpaceStore();
  const [schemaOverview, setSchemaOverview] = useState<any>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [yamlPath, setYamlPath] = useState('examples/supply_chain_finance/schema.yaml');
  const [importing, setImporting] = useState(false);

  // Load full schema overview when space is active
  const loadOverview = async () => {
    if (!activeSpaceId) return;
    setOverviewLoading(true);
    try {
      const data = await spaceApi.getSchemaOverview(activeSpaceId);
      setSchemaOverview(data);
    } catch (e) {
      console.error('Failed to load schema overview', e);
    } finally {
      setOverviewLoading(false);
    }
  };

  // Load overview if we have a space
  if (activeSpaceId && !schemaOverview && !overviewLoading) {
    loadOverview();
  }

  const handleImport = async () => {
    if (!activeSpaceId || !yamlPath) return;
    setImporting(true);
    try {
      const data = await spaceApi.loadSchemaFromYaml(activeSpaceId, yamlPath, true);
      message.success(`导入成功: ${JSON.stringify(data.loaded)}`);
      setImportModalVisible(false);
      setSchemaOverview(null); // Reload
      await setActiveSpace(activeSpaceId);
    } catch (e: any) {
      message.error(e?.response?.data?.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  if (!activeSpaceId) {
    return <Card><Empty description="请先选择一个空间" /></Card>;
  }

  if (loading || overviewLoading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>加载 Schema...</div>
        </div>
      </Card>
    );
  }

  const overview = schemaOverview || {
    L1: { count: factObjects.length, items: factObjects },
    L2: { count: 0, items: [] },
    L3: { count: 0, items: [] },
    L4: { rule_definitions_count: 0, rule_logics_count: 0, rule_definitions: [], rule_logics: [] },
  };

  const tabItems = [
    {
      key: 'L1',
      label: (
        <span>
          <ApartmentOutlined />
          {' '}L1 事实对象
          <Tag count={overview.L1.count} style={{ marginLeft: 6, backgroundColor: '#1890ff' }} />
        </span>
      ),
      children: <L1FactObjectsTab items={overview.L1.items} />,
    },
    {
      key: 'L2',
      label: (
        <span>
          <TagsOutlined />
          {' '}L2 分类体系
          <Tag count={overview.L2.count} style={{ marginLeft: 6, backgroundColor: '#52c41a' }} />
        </span>
      ),
      children: (
        <L2CategorizationsTab
          spaceId={activeSpaceId}
          items={overview.L2.items}
          onRefresh={loadOverview}
        />
      ),
    },
    {
      key: 'L3',
      label: (
        <span>
          <BarChartOutlined />
          {' '}L3 分析要素
          <Tag count={overview.L3.count} style={{ marginLeft: 6, backgroundColor: '#fa8c16' }} />
        </span>
      ),
      children: (
        <L3AnalyticalElementsTab
          spaceId={activeSpaceId}
          items={overview.L3.items}
          onRefresh={loadOverview}
        />
      ),
    },
    {
      key: 'L4',
      label: (
        <span>
          <BranchesOutlined />
          {' '}L4 业务规则
          <Tag count={overview.L4.rule_definitions_count} style={{ marginLeft: 6, backgroundColor: '#722ed1' }} />
        </span>
      ),
      children: (
        <L4RuleDefinitionsTab
          items={overview.L4.rule_definitions}
          ruleLogics={overview.L4.rule_logics}
        />
      ),
    },
  ];

  return (
    <Card
      title={<Title level={5}>Schema 声明 (L1-L4 四层)</Title>}
      extra={
        <Space>
          <Tag color="blue">L1: {overview.L1.count}</Tag>
          <Tag color="green">L2: {overview.L2.count}</Tag>
          <Tag color="orange">L3: {overview.L3.count}</Tag>
          <Tag color="purple">L4: {overview.L4.rule_definitions_count} 规则 / {overview.L4.rule_logics_count} 逻辑</Tag>
          <Button
            icon={<ImportOutlined />}
            size="small"
            onClick={() => setImportModalVisible(true)}
          >
            YAML 导入
          </Button>
        </Space>
      }
    >
      <Tabs items={tabItems} />

      <Modal
        title="从 YAML 导入 Schema"
        open={importModalVisible}
        onOk={handleImport}
        onCancel={() => setImportModalVisible(false)}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
      >
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          输入 KGML v2 格式的 YAML Schema 文件路径（相对于项目根目录或绝对路径）
        </Paragraph>
        <Input
          value={yamlPath}
          onChange={e => setYamlPath(e.target.value)}
          placeholder="examples/supply_chain_finance/schema.yaml"
          addonBefore="路径"
        />
        <Space style={{ marginTop: 8 }} wrap>
          <Button size="small" onClick={() => setYamlPath('examples/supply_chain_finance/schema.yaml')}>供应链金融</Button>
          <Button size="small" onClick={() => setYamlPath('examples/consumer_credit/schema.yaml')}>个人消费信贷</Button>
        </Space>
      </Modal>
    </Card>
  );
}
