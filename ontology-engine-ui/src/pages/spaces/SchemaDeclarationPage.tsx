// ontology-engine-ui/src/pages/spaces/SchemaDeclarationPage.tsx
// Schema declaration page - shows L1-L4 all layers in tabs

import { useState } from 'react';
import { Typography, Card, Table, Tag, Space, Spin, Empty, Tabs, Button, Modal, Input, message, Tooltip, Badge, Collapse, Descriptions } from 'antd';
import { ImportOutlined, InfoCircleOutlined, ApartmentOutlined, TagsOutlined, BarChartOutlined, BranchesOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text, Paragraph } = Typography;

interface FactObject {
  id: string;
  name: string;
  description?: string;
  properties?: Array<{ name: string; type: string; required?: boolean; unique?: boolean; description?: string }>;
  relations?: Array<{ name: string; target: string; cardinality?: string; description?: string }>;
}

interface CategorizationDef {
  id: string;
  name?: string;
  description?: string;
  applicable_to?: string[];
  triggers?: any[];
}

interface AnalyticalElement {
  id: string;
  name?: string;
  description?: string;
  element_type: string;
  formula?: string;
  dependencies?: string[];
  components?: Array<{ metric: string; weight: number }>;
  overridable?: boolean;
  source?: any;
  thresholds?: any;
}

interface RuleDefinitionEntry {
  id: string;
  name?: string;
  description?: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  target_objects?: string[];
  applicable_categorizations?: string[];
  input_elements?: any[];
  output_elements?: any[];
  logic_ids?: string[];
}

const ELEM_TYPE_COLORS: Record<string, string> = {
  atomic: 'green',
  derived: 'orange',
  composite: 'purple',
  graph: 'red',
};

const RULE_TYPE_COLORS: Record<string, string> = {
  constraint: 'orange',
  inference: 'blue',
  alert: 'red',
  decision: 'green',
  veto: 'magenta',
};

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

  // L1 columns
  const l1Columns: ColumnsType<FactObject> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 160, ellipsis: true },
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    {
      title: '属性',
      key: 'properties',
      render: (_: any, record: FactObject) => {
        const props = record.properties || [];
        return (
          <Space size="small" wrap>
            {props.slice(0, 5).map((p, idx) => (
              <Tag key={idx} color={p.required ? 'red' : 'default'} style={{ fontSize: 11 }}>
                {p.name}: <Text type="secondary" style={{ fontSize: 11 }}>{p.type}</Text>
              </Tag>
            ))}
            {props.length > 5 && <Tag>+{props.length - 5}</Tag>}
          </Space>
        );
      },
    },
    {
      title: '关系',
      key: 'relations',
      width: 200,
      render: (_: any, record: FactObject) => {
        const rels = record.relations || [];
        if (!rels.length) return <Text type="secondary">无</Text>;
        return (
          <Space size="small" wrap>
            {rels.map((r, idx) => (
              <Tooltip key={idx} title={r.cardinality}>
                <Tag color="blue" style={{ fontSize: 11 }}>
                  {r.name} → {r.target}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        );
      },
    },
  ];

  // L2 columns
  const l2Columns: ColumnsType<CategorizationDef> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 200, ellipsis: true },
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    {
      title: '适用对象',
      dataIndex: 'applicable_to',
      key: 'applicable_to',
      render: (v: string[]) => (v || []).map((t, i) => <Tag key={i} color="cyan">{t}</Tag>),
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '触发器',
      dataIndex: 'triggers',
      key: 'triggers',
      width: 80,
      render: (v: any[]) => <Badge count={(v || []).length} color="blue" />,
    },
  ];

  // L3 columns
  const l3Columns: ColumnsType<AnalyticalElement> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 200, ellipsis: true },
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    {
      title: '类型',
      dataIndex: 'element_type',
      key: 'element_type',
      width: 90,
      render: (t: string) => <Tag color={ELEM_TYPE_COLORS[t] || 'default'}>{t}</Tag>,
    },
    {
      title: '公式/来源',
      key: 'formula',
      render: (_: any, r: AnalyticalElement) => {
        if (r.formula) return <Text code style={{ fontSize: 11 }}>{r.formula}</Text>;
        if (r.source) return <Tag color="geekblue">{r.source.type}</Tag>;
        if (r.components?.length) return <Text type="secondary">{r.components.length} 个组件</Text>;
        return <Text type="secondary">-</Text>;
      },
    },
    {
      title: '依赖',
      dataIndex: 'dependencies',
      key: 'dependencies',
      render: (deps: string[]) => {
        const list = deps || [];
        return (
          <Space wrap size="small">
            {list.slice(0, 3).map((d, i) => <Tag key={i} style={{ fontSize: 11 }}>{d}</Tag>)}
            {list.length > 3 && <Tag>+{list.length - 3}</Tag>}
          </Space>
        );
      },
    },
    {
      title: '可覆盖',
      dataIndex: 'overridable',
      key: 'overridable',
      width: 80,
      render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag>,
    },
  ];

  // L4 columns
  const l4Columns: ColumnsType<RuleDefinitionEntry> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 180, ellipsis: true },
    { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 90,
      render: (t: string) => <Tag color={RULE_TYPE_COLORS[t] || 'default'}>{t}</Tag>,
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a, b) => a.priority - b.priority,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (v: boolean) => v ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>,
    },
    {
      title: '输入元素',
      dataIndex: 'input_elements',
      key: 'inputs',
      render: (elems: any[]) => (
        <Space wrap size="small">
          {(elems || []).map((e, i) => (
            <Tag key={i} color="geekblue" style={{ fontSize: 11 }}>{e.name || e.id}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '输出元素',
      dataIndex: 'output_elements',
      key: 'outputs',
      render: (elems: any[]) => (
        <Space wrap size="small">
          {(elems || []).map((e, i) => (
            <Tag key={i} color="volcano" style={{ fontSize: 11 }}>{e.name || e.id}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '逻辑数',
      dataIndex: 'logic_ids',
      key: 'logic_ids',
      width: 70,
      render: (ids: string[]) => <Badge count={(ids || []).length} color="purple" />,
    },
  ];

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
          <Badge count={overview.L1.count} style={{ marginLeft: 6, backgroundColor: '#1890ff' }} />
        </span>
      ),
      children: (
        <Table
          columns={l1Columns}
          dataSource={overview.L1.items}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 10 }}
          expandable={{
            expandedRowRender: (record: FactObject) => (
              <Descriptions size="small" column={2} style={{ margin: 8 }}>
                {record.description && <Descriptions.Item label="描述" span={2}>{record.description}</Descriptions.Item>}
                <Descriptions.Item label="属性数">{(record.properties || []).length}</Descriptions.Item>
                <Descriptions.Item label="关系数">{(record.relations || []).length}</Descriptions.Item>
                {(record.properties || []).map((p, i) => (
                  <Descriptions.Item key={i} label={p.name}>
                    <Tag color={p.required ? 'red' : 'default'}>{p.type}</Tag>
                    {p.description && <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>{p.description}</Text>}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            ),
          }}
        />
      ),
    },
    {
      key: 'L2',
      label: (
        <span>
          <TagsOutlined />
          {' '}L2 分类体系
          <Badge count={overview.L2.count} style={{ marginLeft: 6, backgroundColor: '#52c41a' }} />
        </span>
      ),
      children: overview.L2.count === 0 ? (
        <Empty description="暂无分类定义" />
      ) : (
        <Table
          columns={l2Columns}
          dataSource={overview.L2.items}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 10 }}
          expandable={{
            expandedRowRender: (record: CategorizationDef) => (
              <div style={{ padding: '8px 16px' }}>
                {record.description && (
                  <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
                    {record.description}
                  </Paragraph>
                )}
                <Text type="secondary" style={{ fontSize: 12 }}>触发器（分类条件）：</Text>
                {(record.triggers || []).length === 0 ? (
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>无</Text>
                ) : (
                  <div style={{ marginTop: 6 }}>
                    {(record.triggers || []).map((trigger: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '4px 10px', marginBottom: 4,
                          background: '#f6ffed', borderRadius: 4, border: '1px solid #b7eb8f',
                          fontSize: 12,
                        }}
                      >
                        <Tag color="green" style={{ fontSize: 11 }}>{trigger.result_value || trigger.category_value || `分类${idx + 1}`}</Tag>
                        {trigger.condition?.expression && (
                          <Text code style={{ fontSize: 11 }}>
                            {trigger.condition.expression}
                          </Text>
                        )}
                        {trigger.condition?.allOf && (
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            满足全部 {trigger.condition.allOf.length} 个条件
                          </Text>
                        )}
                        {trigger.condition?.anyOf && (
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            满足任一 {trigger.condition.anyOf.length} 个条件
                          </Text>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ),
          }}
        />
      ),
    },
    {
      key: 'L3',
      label: (
        <span>
          <BarChartOutlined />
          {' '}L3 分析要素
          <Badge count={overview.L3.count} style={{ marginLeft: 6, backgroundColor: '#fa8c16' }} />
        </span>
      ),
      children: overview.L3.count === 0 ? (
        <Empty description="暂无分析要素" />
      ) : (
        <Table
          columns={l3Columns}
          dataSource={overview.L3.items}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 15 }}
          expandable={{
            expandedRowRender: (record: AnalyticalElement) => (
              <Descriptions size="small" column={2} style={{ padding: '8px 16px' }}>
                {record.description && (
                  <Descriptions.Item label="描述" span={2}>{record.description}</Descriptions.Item>
                )}
                <Descriptions.Item label="类型">
                  <Tag color={ELEM_TYPE_COLORS[record.element_type] || 'default'}>{record.element_type}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="可覆盖">
                  {record.overridable ? <Tag color="green">是（L4 可覆盖）</Tag> : <Tag>否</Tag>}
                </Descriptions.Item>
                {record.formula && (
                  <Descriptions.Item label="计算公式" span={2}>
                    <Text code>{record.formula}</Text>
                  </Descriptions.Item>
                )}
                {record.source && (
                  <Descriptions.Item label="数据来源" span={2}>
                    <Tag color="geekblue">{record.source.type}</Tag>
                    {record.source.path && <Text code style={{ marginLeft: 8, fontSize: 11 }}>{record.source.path}</Text>}
                    {record.source.field && <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>字段: {record.source.field}</Text>}
                  </Descriptions.Item>
                )}
                {record.components && record.components.length > 0 && (
                  <Descriptions.Item label="组合权重" span={2}>
                    <Space wrap size="small">
                      {record.components.map((c: any, i: number) => (
                        <Tag key={i} color="purple" style={{ fontSize: 11 }}>
                          {c.metric}: <Text strong style={{ color: '#722ed1' }}>{(c.weight * 100).toFixed(0)}%</Text>
                        </Tag>
                      ))}
                    </Space>
                  </Descriptions.Item>
                )}
                {record.dependencies && record.dependencies.length > 0 && (
                  <Descriptions.Item label="依赖要素" span={2}>
                    <Space wrap size="small">
                      {record.dependencies.map((dep: string, i: number) => (
                        <Tag key={i} style={{ fontSize: 11 }}>{dep}</Tag>
                      ))}
                    </Space>
                  </Descriptions.Item>
                )}
                {record.thresholds && (
                  <Descriptions.Item label="阈值配置" span={2}>
                    <Text code style={{ fontSize: 11 }}>{JSON.stringify(record.thresholds)}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            ),
          }}
        />
      ),
    },
    {
      key: 'L4',
      label: (
        <span>
          <BranchesOutlined />
          {' '}L4 业务规则
          <Badge count={overview.L4.rule_definitions_count} style={{ marginLeft: 6, backgroundColor: '#722ed1' }} />
        </span>
      ),
      children: (
        <div>
          <Table
            columns={l4Columns}
            dataSource={overview.L4.rule_definitions}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 10 }}
            expandable={{
              expandedRowRender: (record: RuleDefinitionEntry) => {
                const logics = (overview.L4.rule_logics || []).filter(
                  (rl: any) => (record.logic_ids || []).includes(rl.id)
                );
                return (
                  <Collapse size="small" style={{ margin: 8 }}>
                    {logics.map((logic: any) => (
                      <Collapse.Panel
                        key={logic.id}
                        header={<span><Tag color="purple">{logic.id}</Tag>{logic.name || ''}</span>}
                      >
                        <Descriptions size="small" column={1}>
                          {logic.when?.expression && (
                            <Descriptions.Item label="条件">
                              <Text code>{logic.when.expression}</Text>
                            </Descriptions.Item>
                          )}
                          {logic.then_action && (
                            <Descriptions.Item label="动作">
                              <Tag color={RULE_TYPE_COLORS[logic.then_action.action_type || ''] || 'default'}>
                                {logic.then_action.action_type}
                              </Tag>
                              {logic.then_action.output && (
                                <Text code style={{ marginLeft: 8, fontSize: 11 }}>
                                  {JSON.stringify(logic.then_action.output)}
                                </Text>
                              )}
                            </Descriptions.Item>
                          )}
                          {(logic.applicable_conditions || []).length > 0 && (
                            <Descriptions.Item label="适用条件">
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                {JSON.stringify(logic.applicable_conditions)}
                              </Text>
                            </Descriptions.Item>
                          )}
                        </Descriptions>
                      </Collapse.Panel>
                    ))}
                    {logics.length === 0 && <Empty description="无绑定的规则逻辑" />}
                  </Collapse>
                );
              },
            }}
          />
        </div>
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
