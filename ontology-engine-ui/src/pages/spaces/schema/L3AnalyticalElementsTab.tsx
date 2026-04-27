// L3AnalyticalElementsTab.tsx - L3 Analytical Elements management
import { useState } from 'react';
import { Table, Tag, Space, Button, Modal, Form, Input, Select, message, Empty, Descriptions, Typography } from 'antd';
const { Text } = Typography;
import { PlusOutlined } from '@ant-design/icons';
import { spaceApi } from '../../../api/spaceApi';
import type { ColumnsType } from 'antd/es/table';

const { useForm } = Form;

const ELEM_TYPE_COLORS: Record<string, string> = {
  atomic: 'green',
  derived: 'orange',
  composite: 'purple',
  graph: 'red',
};

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

interface L3AnalyticalElementsTabProps {
  spaceId: string;
  items: AnalyticalElement[];
  onRefresh: () => void;
}

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

export default function L3AnalyticalElementsTab({ spaceId, items, onRefresh }: L3AnalyticalElementsTabProps) {
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = useForm();
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await spaceApi.createAnalyticalElement(spaceId, {
        id: values.id,
        name: values.name,
        description: values.description || undefined,
        type: values.element_type,
      });
      message.success('分析要素已创建');
      setCreateModalVisible(false);
      form.resetFields();
      onRefresh();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.message || '创建失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div style={{ marginBottom: 16, textAlign: 'right' }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
          创建要素
        </Button>
      </div>
      {items.length === 0 ? (
        <Empty description="暂无分析要素，点击上方按钮创建" />
      ) : (
        <Table
          columns={l3Columns}
          dataSource={items}
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
      )}

      <Modal
        title="创建分析要素"
        open={createModalVisible}
        onOk={handleCreate}
        onCancel={() => { setCreateModalVisible(false); form.resetFields(); }}
        confirmLoading={saving}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="id" label="要素ID" rules={[{ required: true, message: '请输入要素ID' }]}>
            <Input placeholder="如 credit_score" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如 信用评分" />
          </Form.Item>
          <Form.Item name="element_type" label="要素类型" rules={[{ required: true }]}>
            <Select
              placeholder="选择类型"
              options={[
                { value: 'atomic', label: 'atomic（原子要素）' },
                { value: 'derived', label: 'derived（推导要素）' },
                { value: 'composite', label: 'composite（组合要素）' },
                { value: 'graph', label: 'graph（图指标要素）' },
                { value: 'flag', label: 'flag（标志位）' },
                { value: 'score', label: 'score（评分）' },
                { value: 'limit', label: 'limit（额度）' },
              ]}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="要素描述（可选）" rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
