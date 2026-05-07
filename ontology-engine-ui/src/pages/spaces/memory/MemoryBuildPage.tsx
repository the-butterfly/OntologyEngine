import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Input, Select, Button, Form, message, Typography, List, Tag, Space, Popconfirm } from 'antd';
import { BuildOutlined, CheckOutlined, CloseOutlined, EditOutlined, EyeOutlined } from '@ant-design/icons';
import { memoryApi } from '../../../services/memoryApi';
import type { CognitiveNode } from '../../../types/memory';
import { MemoryDetailDrawer } from '../../../components/memory';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const BELIEF_STATUS_COLORS: Record<string, string> = {
  accepted: 'green',
  rejected: 'red',
  pending_review: 'orange',
  superseded: 'purple',
  under_review: 'blue',
};

const MemoryBuildPage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [pendingReviews, setPendingReviews] = useState<CognitiveNode[]>([]);
  const [detailNodeId, setDetailNodeId] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [correctModalVisible, setCorrectModalVisible] = useState(false);
  const [correctingNode, setCorrectingNode] = useState<CognitiveNode | null>(null);
  const [correctForm] = Form.useForm();

  useEffect(() => {
    if (!spaceId) return;
    loadPendingReviews();
  }, [spaceId]);

  const loadPendingReviews = async () => {
    if (!spaceId) return;
    try {
      const reviews = await memoryApi.getPendingReviews(spaceId);
      setPendingReviews(reviews);
    } catch (e) {
      message.error('加载待审区失败');
    }
  };

  const handleSubmit = async (values: any) => {
    if (!spaceId) return;
    setLoading(true);
    try {
      const result = await memoryApi.remember(spaceId, values.content, values.memoryType, {
        confidence: values.confidence,
        tags: values.tags ? values.tags.split(',').map((t: string) => t.trim()) : undefined,
      });
      message.success(`记忆创建成功: ${result.memory_id}`);
      form.resetFields();
      await loadPendingReviews();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '创建失败');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (nodeId: string) => {
    if (!spaceId) return;
    try {
      await memoryApi.approveNode(spaceId, nodeId, 'approve');
      message.success('已批准');
      await loadPendingReviews();
    } catch (e) {
      message.error('批准失败');
    }
  };

  const handleReject = async (nodeId: string) => {
    if (!spaceId) return;
    try {
      await memoryApi.approveNode(spaceId, nodeId, 'reject');
      message.success('已拒绝');
      await loadPendingReviews();
    } catch (e) {
      message.error('拒绝失败');
    }
  };

  const handleCorrect = (node: CognitiveNode) => {
    setCorrectingNode(node);
    correctForm.setFieldsValue({ correctedText: node.content, reason: '' });
    setCorrectModalVisible(true);
  };

  const handleCorrectSubmit = async (values: { correctedText: string; reason: string }) => {
    if (!spaceId || !correctingNode) return;
    try {
      await memoryApi.correctNode(spaceId, correctingNode.id, values.correctedText, values.reason);
      message.success('更正已提交');
      setCorrectModalVisible(false);
      correctForm.resetFields();
      await loadPendingReviews();
    } catch (e) {
      message.error('更正失败');
    }
  };

  const handleOpenDetail = (nodeId: string) => {
    setDetailNodeId(nodeId);
    setDetailVisible(true);
  };

  return (
    <div>
      <Title level={3}>记忆构建</Title>
      <Card title="创建新记忆" style={{ marginBottom: 24 }}>
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="content" label="记忆内容" rules={[{ required: true }]}>
            <TextArea rows={4} placeholder="输入记忆内容..." />
          </Form.Item>
          <Form.Item name="memoryType" label="记忆类型" initialValue="observation">
            <Select>
              <Option value="observation">观察</Option>
              <Option value="opinion">观点</Option>
              <Option value="entity">实体</Option>
              <Option value="rule">规则</Option>
              <Option value="episode">事件</Option>
              <Option value="procedure">流程</Option>
            </Select>
          </Form.Item>
          <Form.Item name="confidence" label="置信度" initialValue={0.8}>
            <Input type="number" min={0} max={1} step={0.1} />
          </Form.Item>
          <Form.Item name="tags" label="标签 (逗号分隔)">
            <Input placeholder="tag1, tag2, tag3" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} icon={<BuildOutlined />}>
              创建记忆
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="待审区队列">
        {pendingReviews.length === 0 ? (
          <Text type="secondary">暂无待审核记忆</Text>
        ) : (
          <List
            dataSource={pendingReviews}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button size="small" icon={<EyeOutlined />} onClick={() => handleOpenDetail(item.id)}>查看</Button>,
                  <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => handleApprove(item.id)}>确认</Button>,
                  <Button size="small" icon={<EditOutlined />} onClick={() => handleCorrect(item)}>更正</Button>,
                  <Popconfirm title="确定拒绝此记忆？" onConfirm={() => handleReject(item.id)} okText="拒绝" cancelText="取消">
                    <Button size="small" danger icon={<CloseOutlined />}>拒绝</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={item.content.substring(0, 80) + (item.content.length > 80 ? '...' : '')}
                  description={
                    <Space>
                      <Tag>{item.memoryType}</Tag>
                      <Tag color={BELIEF_STATUS_COLORS[item.beliefStatus] || 'default'}>{item.beliefStatus}</Tag>
                      <Tag>置信度: {item.confidence}</Tag>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      <MemoryDetailDrawer
        nodeId={detailNodeId}
        spaceId={spaceId || ''}
        visible={detailVisible}
        onClose={() => setDetailVisible(false)}
        onUpdate={loadPendingReviews}
      />

      <Card title="更正记忆" style={{ display: correctModalVisible ? 'block' : 'none', marginTop: 24 }}>
        {correctModalVisible && (
          <Form form={correctForm} layout="vertical" onFinish={handleCorrectSubmit}>
            <Form.Item name="correctedText" label="更正后内容" rules={[{ required: true }]}>
              <TextArea rows={4} />
            </Form.Item>
            <Form.Item name="reason" label="更正原因" rules={[{ required: true }]}>
              <Input placeholder="输入更正原因..." />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">提交更正</Button>
                <Button onClick={() => setCorrectModalVisible(false)}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Card>
    </div>
  );
};

export default MemoryBuildPage;
