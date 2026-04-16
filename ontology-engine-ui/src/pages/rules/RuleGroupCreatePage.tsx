// ontology-engine-ui/src/pages/rules/RuleGroupCreatePage.tsx
// Page for creating a new rule group with full validation and schemaId context awareness

import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card, Form, Input, Select, Button, message, Alert, InputNumber, Tag, Space, Divider,
} from 'antd';
import {
  BranchesOutlined, ArrowRightOutlined,
} from '@ant-design/icons';
import { RuleGroupLayout } from './RuleGroupLayout';
import { useRuleGroups } from '../../hooks/useRuleGroups';

const TYPE_OPTIONS = [
  {
    label: <Space><Tag color="green">决策</Tag><span style={{ fontSize: 12, color: '#666' }}>最终决策输出（审批/拒绝/条件审批）</span></Space>,
    value: 'decision',
  },
  {
    label: <Space><Tag color="blue">约束</Tag><span style={{ fontSize: 12, color: '#666' }}>一票否决型前置约束检查</span></Space>,
    value: 'constraint',
  },
  {
    label: <Space><Tag color="purple">推理</Tag><span style={{ fontSize: 12, color: '#666' }}>从原始数据推导中间变量</span></Space>,
    value: 'inference',
  },
  {
    label: <Space><Tag color="orange">告警</Tag><span style={{ fontSize: 12, color: '#666' }}>触发风险告警但不终止流程</span></Space>,
    value: 'alert',
  },
];

export const RuleGroupCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';
  const { createGroup, loading } = useRuleGroups(schemaId);
  const [form] = Form.useForm();

  const handleSubmit = async (values: {
    name: string;
    description?: string;
    type?: string;
    priority?: number;
  }) => {
    if (!schemaId) {
      message.error('请先从语义空间进入规则管理，再创建规则组');
      return;
    }
    try {
      const created = await createGroup({
        name: values.name,
        description: values.description,
        type: (values.type as 'decision' | 'constraint' | 'inference' | 'alert') || 'decision',
        priority: values.priority ?? 100,
        enabled: true,
        appliesTo: { factObjects: [], categories: {} },
        inputs: [],
        outputs: [],
        preconditions: [],
      });
      message.success(`规则组「${created.name}」创建成功，请继续配置四元素`);
      navigate(`/rules/${created.id}?schemaId=${schemaId}&pendingSetup=true`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败，请重试');
    }
  };

  const handleCancel = () => {
    navigate(`/rules?schemaId=${schemaId}`);
  };

  return (
    <RuleGroupLayout breadcrumbs={[{ label: '新建规则组' }]}>
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        {!schemaId && (
          <Alert
            type="warning"
            message="未指定语义空间"
            description={
              <div>
                规则组必须归属于某个语义空间。请从
                <Button type="link" size="small" onClick={() => navigate('/spaces')}>
                  空间列表
                </Button>
                进入后，点击「规则管理」再创建规则组。
              </div>
            }
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Card
          title={
            <Space>
              <BranchesOutlined style={{ color: '#1890ff' }} />
              <span>新建规则组</span>
            </Space>
          }
        >
          {/* Quick guide */}
          <div
            style={{
              background: '#f0f5ff',
              border: '1px solid #adc6ff',
              borderRadius: 6,
              padding: '10px 16px',
              marginBottom: 20,
              fontSize: 12,
              color: '#2f54eb',
            }}
          >
            <strong>创建流程：</strong> ①填写基本信息 → ②进入详情页配置作用对象/适用场景/I/O要素 → ③添加规则实例
          </div>

          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
            initialValues={{ type: 'decision', priority: 100 }}
          >
            <Form.Item
              label="规则组名称"
              name="name"
              rules={[
                { required: true, message: '请输入规则组名称' },
                { pattern: /^[a-z_][a-z0-9_]*$/, message: '名称只允许小写字母、数字和下划线，且以字母开头' },
              ]}
              extra="例如：credit_assessment_rules、supplier_risk_check"
            >
              <Input
                placeholder="请输入规则组名称（蛇形命名）"
                prefix={<BranchesOutlined style={{ color: '#d9d9d9' }} />}
              />
            </Form.Item>

            <Form.Item
              label="描述"
              name="description"
            >
              <Input.TextArea
                rows={2}
                placeholder="简要描述该规则组的业务用途（可选）"
              />
            </Form.Item>

            <Form.Item label="类型" name="type">
              <Select
                options={TYPE_OPTIONS}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item
              label="优先级"
              name="priority"
              extra="数值越小优先级越高。同类规则组按优先级顺序执行。"
            >
              <InputNumber
                min={1}
                max={9999}
                style={{ width: '100%' }}
                placeholder="100"
              />
            </Form.Item>

            <Divider style={{ margin: '16px 0' }} />

            <Form.Item style={{ marginBottom: 0 }}>
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  disabled={!schemaId}
                  icon={<ArrowRightOutlined />}
                >
                  创建并配置
                </Button>
                <Button onClick={handleCancel}>
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </RuleGroupLayout>
  );
};

export default RuleGroupCreatePage;
