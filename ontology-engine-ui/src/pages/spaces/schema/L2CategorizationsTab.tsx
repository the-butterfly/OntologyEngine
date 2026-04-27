// L2CategorizationsTab.tsx - L2 Categorizations management
import { useState } from 'react';
import { Table, Tag, Space, Button, Modal, Form, Input, message, Badge, Empty, Typography } from 'antd';
const { Paragraph, Text } = Typography;
import { PlusOutlined } from '@ant-design/icons';
import { spaceApi } from '../../../api/spaceApi';
import type { ColumnsType } from 'antd/es/table';

const { useForm } = Form;

interface CategorizationDef {
  id: string;
  name?: string;
  description?: string;
  applicable_to?: string[];
  triggers?: any[];
}

interface L2CategorizationsTabProps {
  spaceId: string;
  items: CategorizationDef[];
  onRefresh: () => void;
}

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

export default function L2CategorizationsTab({ spaceId, items, onRefresh }: L2CategorizationsTabProps) {
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = useForm();
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await spaceApi.createCategorization(spaceId, {
        id: values.id,
        name: values.name,
        description: values.description || undefined,
        type: 'flat',
      });
      message.success('分类定义已创建');
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
          创建分类
        </Button>
      </div>
      {items.length === 0 ? (
        <Empty description="暂无分类定义，点击上方按钮创建" />
      ) : (
        <Table
          columns={l2Columns}
          dataSource={items}
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
      )}

      <Modal
        title="创建分类体系"
        open={createModalVisible}
        onOk={handleCreate}
        onCancel={() => { setCreateModalVisible(false); form.resetFields(); }}
        confirmLoading={saving}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="id" label="分类ID" rules={[{ required: true, message: '请输入分类ID' }]}>
            <Input placeholder="如 CAT001" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如 企业质量分级" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="分类描述（可选）" rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
