// ontology-engine-ui/src/pages/rules/RuleGroupCreatePage.tsx
// Page for creating a new rule group

import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, Form, Input, Select, Button, message } from 'antd';
import { RuleGroupLayout } from './RuleGroupLayout';
import { useRuleGroups } from '../../hooks/useRuleGroups';

export const RuleGroupCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';
  const { createGroup, loading } = useRuleGroups(schemaId);
  const [form] = Form.useForm();

  const handleSubmit = async (values: { name: string; description?: string; type?: string; priority?: number }) => {
    try {
      const created = await createGroup({
        name: values.name,
        description: values.description,
        type: (values.type as 'decision' | 'constraint' | 'inference' | 'alert') || 'decision',
        priority: values.priority || 100,
        enabled: true,
      });
      navigate(`/rules/${created.id}?schemaId=${schemaId}&pendingSetup=true`);
    } catch (err) {
      console.error('[RuleGroupCreate] 创建失败:', err);
      try {
        message.error('创建失败');
      } catch {
        // message API may fail outside App context
      }
    }
  };

  return (
    <RuleGroupLayout breadcrumbs={[{ label: '新建规则组' }]}>
      <Card title="创建规则组">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{ type: 'decision', priority: 100 }}
        >
          <Form.Item
            label="规则组名称"
            name="name"
            rules={[{ required: true, message: '请输入规则组名称' }]}
          >
            <Input placeholder="请输入规则组名称" />
          </Form.Item>

          <Form.Item
            label="描述"
            name="description"
          >
            <Input.TextArea rows={3} placeholder="请输入描述" />
          </Form.Item>

          <Form.Item
            label="类型"
            name="type"
          >
            <Select>
              <Select.Option value="decision">决策</Select.Option>
              <Select.Option value="constraint">约束</Select.Option>
              <Select.Option value="inference">推理</Select.Option>
              <Select.Option value="alert">告警</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="优先级"
            name="priority"
          >
            <Input type="number" placeholder="100" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              创建
            </Button>
            <Button onClick={() => navigate(-1)} style={{ marginLeft: 8 }}>
              取消
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </RuleGroupLayout>
  );
};

export default RuleGroupCreatePage;
