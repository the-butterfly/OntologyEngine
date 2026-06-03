// ontology-engine-ui/src/pages/spaces/InstanceDataPage.tsx
// Instance data management page with batch import and relations

import { useState } from 'react';
import { Typography, Card, Table, Tag, Space, Spin, Empty, Button, Modal, Input, message, Tabs, Badge, Tooltip, Statistic, Row, Col } from 'antd';
import { ImportOutlined, DatabaseOutlined, ShareAltOutlined, ReloadOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';
import { spaceApi } from '../../api/spaceApi';
import type { EntityInstance } from '../../api/spaceApi';

const { Title, Text, Paragraph } = Typography;

interface RelationInstance {
  from_entity_id: string;
  to_entity_id: string;
  relation_type: string;
  [key: string]: unknown;
}

export default function InstanceDataPage() {
  const { activeSpaceId, entities, entitiesLoading, loadEntities, setActiveSpace } = useSpaceStore();
  const [relations, setRelations] = useState<RelationInstance[]>([]);
  const [relationsLoading, setRelationsLoading] = useState(false);
  const [relationsLoaded, setRelationsLoaded] = useState(false);

  const [importModalVisible, setImportModalVisible] = useState(false);
  const [yamlPath, setYamlPath] = useState('examples/supply_chain_finance/instances.yaml');
  const [importing, setImporting] = useState(false);
  const [activeTab, setActiveTab] = useState('entities');

  const loadRelations = async () => {
    if (!activeSpaceId) return;
    setRelationsLoading(true);
    try {
      const data = await spaceApi.listRelations(activeSpaceId);
      setRelations(data || []);
      setRelationsLoaded(true);
    } catch (e) {
      message.error('加载关系实例失败');
    } finally {
      setRelationsLoading(false);
    }
  };

  // Load relations on tab switch
  const handleTabChange = (key: string) => {
    setActiveTab(key);
    if (key === 'relations' && !relationsLoaded && activeSpaceId) {
      loadRelations();
    }
  };

  const handleImport = async () => {
    if (!activeSpaceId || !yamlPath) return;
    setImporting(true);
    try {
      const data = await spaceApi.loadInstancesFromYaml(activeSpaceId, yamlPath, true);
      message.success(
        `导入成功：${data.added_entities} 个实体，${data.added_relations} 条关系`
      );
      setImportModalVisible(false);
      setRelationsLoaded(false);
      // Reload
      await loadEntities(activeSpaceId);
      if (activeTab === 'relations') {
        await loadRelations();
      }
    } catch (e: any) {
      message.error(e?.response?.data?.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  // Get concept distribution
  const conceptDistribution = entities.reduce<Record<string, number>>((acc, e) => {
    const concept = e._concept as string || 'Unknown';
    acc[concept] = (acc[concept] || 0) + 1;
    return acc;
  }, {});

  const entityColumns: ColumnsType<EntityInstance> = [
    {
      title: '实体ID',
      dataIndex: 'entity_id',
      key: 'entity_id',
      width: 160,
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: '_concept',
      key: '_concept',
      width: 130,
      filters: Object.keys(conceptDistribution).map(c => ({ text: c, value: c })),
      onFilter: (value, record) => record._concept === value,
      render: (concept: string) => <Tag color="blue">{concept}</Tag>,
    },
    {
      title: '属性',
      key: 'properties',
      render: (_: any, record: EntityInstance) => {
        const excludeKeys = ['entity_id', '_concept'];
        const propertyKeys = Object.keys(record).filter(k => !excludeKeys.includes(k));
        return (
          <Space size="small" wrap>
            {propertyKeys.slice(0, 6).map(key => {
              const val = record[key];
              const displayVal = typeof val === 'object' && val !== null
                ? JSON.stringify(val).substring(0, 20) + '...'
                : String(val ?? '');
              return (
                <Tooltip key={key} title={`${key}: ${displayVal}`}>
                  <Tag style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 11 }}>
                    {key}: {displayVal.substring(0, 15)}
                  </Tag>
                </Tooltip>
              );
            })}
            {propertyKeys.length > 6 && (
              <Tag>+{propertyKeys.length - 6}</Tag>
            )}
          </Space>
        );
      },
    },
  ];

  const relationColumns: ColumnsType<RelationInstance> = [
    {
      title: '关系类型',
      dataIndex: 'relation_type',
      key: 'relation_type',
      width: 160,
      render: (t: string) => <Tag color="purple">{t}</Tag>,
    },
    {
      title: '起始实体',
      dataIndex: 'from_entity_id',
      key: 'from_entity_id',
      width: 160,
      ellipsis: true,
    },
    {
      title: '目标实体',
      dataIndex: 'to_entity_id',
      key: 'to_entity_id',
      width: 160,
      ellipsis: true,
    },
    {
      title: '附加属性',
      key: 'extra',
      render: (_: any, record: RelationInstance) => {
        const excluded = ['from_entity_id', 'to_entity_id', 'relation_type'];
        const extra = Object.entries(record).filter(([k]) => !excluded.includes(k));
        if (!extra.length) return <Text type="secondary">无</Text>;
        return (
          <Space size="small" wrap>
            {extra.map(([k, v]) => (
              <Tag key={k} style={{ fontSize: 11 }}>{k}: {String(v)}</Tag>
            ))}
          </Space>
        );
      },
    },
  ];

  if (!activeSpaceId) {
    return <Card><Empty description="请先选择一个空间" /></Card>;
  }

  const tabItems = [
    {
      key: 'entities',
      label: (
        <span>
          <DatabaseOutlined />
          {' '}实体实例
          <Badge count={entities.length} style={{ marginLeft: 6, backgroundColor: '#1890ff' }} />
        </span>
      ),
      children: entitiesLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>加载实体...</div>
        </div>
      ) : (
        <div>
          {/* Concept distribution */}
          {Object.keys(conceptDistribution).length > 0 && (
            <Row gutter={12} style={{ marginBottom: 16 }}>
              {Object.entries(conceptDistribution).map(([concept, count]) => (
                <Col key={concept}>
                  <Card size="small" style={{ minWidth: 100, textAlign: 'center' }}>
                    <Statistic
                      title={concept}
                      value={count}
                      valueStyle={{ fontSize: 18, color: '#1890ff' }}
                    />
                  </Card>
                </Col>
              ))}
            </Row>
          )}
          <Table
            columns={entityColumns}
            dataSource={entities}
            rowKey="entity_id"
            pagination={{ pageSize: 10 }}
            size="small"
            expandable={{
              expandedRowRender: (record: EntityInstance) => {
                const excluded = ['entity_id', '_concept'];
                const props = Object.entries(record).filter(([k]) => !excluded.includes(k));
                return (
                  <div style={{ padding: '8px 16px', background: '#fafafa', borderRadius: 6 }}>
                    <Space wrap size={8}>
                      {props.map(([key, value]) => (
                        <div key={key} style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>{key}:</Text>
                          <Text style={{ fontSize: 11 }}>
                            {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}
                          </Text>
                        </div>
                      ))}
                    </Space>
                  </div>
                );
              },
            }}
          />
        </div>
      ),
    },
    {
      key: 'relations',
      label: (
        <span>
          <ShareAltOutlined />
          {' '}关系实例
          {relationsLoaded && (
            <Badge count={relations.length} style={{ marginLeft: 6, backgroundColor: '#722ed1' }} />
          )}
        </span>
      ),
      children: relationsLoading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>加载关系...</div>
        </div>
      ) : !relationsLoaded ? (
        <Empty description="切换到此标签页后自动加载" />
      ) : relations.length === 0 ? (
        <Empty description="暂无关系实例" />
      ) : (
        <Table
          columns={relationColumns}
          dataSource={relations}
          rowKey={(r) => `${r.relation_type}_${r.from_entity_id}_${r.to_entity_id}`}
          pagination={{ pageSize: 10 }}
          size="small"
        />
      ),
    },
  ];

  return (
    <Card
      title={<Title level={5}>数据实例</Title>}
      extra={
        <Space>
          <Tag color="blue">{entities.length} 实体</Tag>
          {relationsLoaded && <Tag color="purple">{relations.length} 关系</Tag>}
          <Button
            icon={<ReloadOutlined />}
            size="small"
            onClick={async () => {
              await loadEntities(activeSpaceId!);
              setRelationsLoaded(false);
            }}
          >
            刷新
          </Button>
          <Button
            type="primary"
            icon={<ImportOutlined />}
            size="small"
            onClick={() => setImportModalVisible(true)}
          >
            批量导入
          </Button>
        </Space>
      }
    >
      <Tabs items={tabItems} onChange={handleTabChange} activeKey={activeTab} />

      <Modal
        title="从 YAML 批量导入实例"
        open={importModalVisible}
        onOk={handleImport}
        onCancel={() => setImportModalVisible(false)}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
      >
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          输入实例数据 YAML 文件路径（相对于项目根目录或绝对路径）
        </Paragraph>
        <Input
          value={yamlPath}
          onChange={e => setYamlPath(e.target.value)}
          placeholder="examples/supply_chain_finance/instances.yaml"
          addonBefore="路径"
        />
        <Space style={{ marginTop: 8 }} wrap>
          <Button size="small" onClick={() => setYamlPath('examples/supply_chain_finance/instances.yaml')}>
            供应链金融
          </Button>
          <Button size="small" onClick={() => setYamlPath('examples/consumer_credit/instances.yaml')}>
            个人消费信贷
          </Button>
        </Space>
      </Modal>
    </Card>
  );
}
