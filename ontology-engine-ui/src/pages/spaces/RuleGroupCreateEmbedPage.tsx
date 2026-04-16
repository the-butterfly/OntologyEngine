// ontology-engine-ui/src/pages/spaces/RuleGroupCreateEmbedPage.tsx
// 规则组创建嵌入式页面 —— 内嵌于 SpaceDetailPage 右侧内容区
//
// 设计原则：
//   1. 无独立 Layout / 全局面包屑
//   2. 含内嵌子面包屑（返回规则列表 / 新建规则组）
//   3. spaceId 从 URL params 获取，也可由 A2UI 宿主通过 prop 注入
//   4. 数据源：Schema L4 API（/v1/management/{spaceId}/schema/L4/rules/definitions）
//      与 Schema 声明保持一致

import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  message,
  Alert,
  InputNumber,
  Tag,
  Space,
  Divider,
  Breadcrumb,
} from 'antd';
import {
  BranchesOutlined,
  ArrowRightOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { useL4Rules } from '../../hooks/useL4Rules';
import type { L4RuleDefinition } from '../../hooks/useL4Rules';

const TYPE_OPTIONS = [
  {
    label: (
      <Space>
        <Tag color="green">决策</Tag>
        <span style={{ fontSize: 12, color: '#666' }}>最终决策输出（审批/拒绝/条件审批）</span>
      </Space>
    ),
    value: 'decision',
  },
  {
    label: (
      <Space>
        <Tag color="blue">约束</Tag>
        <span style={{ fontSize: 12, color: '#666' }}>一票否决型前置约束检查</span>
      </Space>
    ),
    value: 'constraint',
  },
  {
    label: (
      <Space>
        <Tag color="purple">推理</Tag>
        <span style={{ fontSize: 12, color: '#666' }}>从原始数据推导中间变量</span>
      </Space>
    ),
    value: 'inference',
  },
  {
    label: (
      <Space>
        <Tag color="orange">告警</Tag>
        <span style={{ fontSize: 12, color: '#666' }}>触发风险告警但不终止流程</span>
      </Space>
    ),
    value: 'alert',
  },
];

// ─── 组件 Props ───────────────────────────────────────────────────────────────
export interface RuleGroupCreateEmbedPageProps {
  spaceId?: string;
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────
export const RuleGroupCreateEmbedPage: React.FC<RuleGroupCreateEmbedPageProps> = ({
  spaceId: propSpaceId,
}) => {
  const { spaceId: paramSpaceId } = useParams<{ spaceId: string }>();
  const spaceId = propSpaceId || paramSpaceId || '';
  const navigate = useNavigate();

  const { createDefinition, loading } = useL4Rules(spaceId);
  const [form] = Form.useForm();

  const handleSubmit = async (values: {
    name: string;
    description?: string;
    type?: string;
    priority?: number;
  }) => {
    if (!spaceId) {
      message.error('请先从语义空间进入规则管理，再创建规则组');
      return;
    }
    try {
      // 生成 L4 格式的规则定义数据
      // ID 格式：rd_{name}_{timestamp}（小写 + 下划线）
      const ruleId = `rd_${values.name.toLowerCase().replace(/\s+/g, '_')}_${Date.now()}`;
      const newDefinition: Partial<L4RuleDefinition> = {
        id: ruleId,
        name: values.name,
        description: values.description,
        rule_type: (values.type as L4RuleDefinition['rule_type']) || 'decision',
        priority: values.priority ?? 100,
        applies_to: [],           // 详情页再配置作用对象
        applicable_categorizations: [], // 详情页再配置适用分类
        inputs: [],              // 详情页再配置输入要素
        outputs: [],             // 详情页再配置输出要素
        preconditions: [],
        enabled: true,
        logic_ids: [],
      };
      const created = await createDefinition(newDefinition);
      message.success(`规则组「${created.name}」创建成功，请继续配置四要素`);
      // 内嵌路由：进入嵌入式详情页，使用 encodeURIComponent 处理特殊字符
      navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(created.id)}`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '创建失败，请重试');
    }
  };

  const handleBackToList = () => {
    navigate(`/spaces/${spaceId}/rules`);
  };

  return (
    // A2UI 扩展点：标准化容器
    <div
      data-a2ui-component="rule-group-create-embed"
      data-a2ui-space-id={spaceId}
    >
      {/* ── 内嵌子面包屑 ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
          padding: '8px 0',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Button
          type="text"
          size="small"
          icon={<ArrowLeftOutlined />}
          onClick={handleBackToList}
          style={{ color: '#666', padding: '0 4px' }}
        >
          规则列表
        </Button>
        <span style={{ color: '#d9d9d9' }}>/</span>
        <Breadcrumb
          items={[
            {
              title: (
                <span
                  style={{ cursor: 'pointer', color: '#1890ff' }}
                  onClick={handleBackToList}
                >
                  规则管理
                </span>
              ),
            },
            { title: '新建规则组' },
          ]}
        />
      </div>

      {/* ── 主体内容 ── */}
      <div style={{ maxWidth: 580, margin: '0 auto' }}>
        {!spaceId && (
          <Alert
            type="warning"
            message="未指定语义空间"
            description={
              <div>
                规则组必须归属于某个语义空间。请从
                <Button
                  type="link"
                  size="small"
                  onClick={() => navigate('/spaces')}
                >
                  空间列表
                </Button>
                进入后再创建规则组。
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
          size="small"
        >
          {/* 快速引导 */}
          <div
            style={{
              background: '#f0f5ff',
              border: '1px solid #adc6ff',
              borderRadius: 6,
              padding: '8px 14px',
              marginBottom: 16,
              fontSize: 12,
              color: '#2f54eb',
            }}
          >
            <strong>创建流程：</strong>
            ①填写基本信息 → ②进入详情页配置作用对象/适用场景/I/O要素 → ③添加规则实例
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
                {
                  pattern: /^[a-z_][a-z0-9_]*$/,
                  message: '名称只允许小写字母、数字和下划线，且以字母开头',
                },
              ]}
              extra="例如：credit_assessment_rules、supplier_risk_check"
            >
              <Input
                placeholder="请输入规则组名称（蛇形命名）"
                prefix={<BranchesOutlined style={{ color: '#d9d9d9' }} />}
              />
            </Form.Item>

            <Form.Item label="描述" name="description">
              <Input.TextArea
                rows={2}
                placeholder="简要描述该规则组的业务用途（可选）"
              />
            </Form.Item>

            <Form.Item label="类型" name="type">
              <Select options={TYPE_OPTIONS} style={{ width: '100%' }} />
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

            <Divider style={{ margin: '12px 0' }} />

            <Form.Item style={{ marginBottom: 0 }}>
              <Space>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  disabled={!spaceId}
                  icon={<ArrowRightOutlined />}
                >
                  创建并配置
                </Button>
                <Button onClick={handleBackToList}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  );
};

export default RuleGroupCreateEmbedPage;
