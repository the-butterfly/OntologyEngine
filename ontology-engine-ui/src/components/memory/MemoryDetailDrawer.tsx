import React, { useState, useEffect } from 'react';
import { Drawer, Descriptions, Tag, Button, Space, App, Popconfirm, Input, Form, Modal } from 'antd';
import type { CognitiveNode } from '../../types/memory';
import { memoryApi } from '../../api/memoryApi';

interface MemoryDetailDrawerProps {
  nodeId: string | null;
  spaceId: string;
  visible: boolean;
  onClose: () => void;
  onUpdate?: () => void;
}

const BELIEF_STATUS_COLORS: Record<string, string> = {
  accepted: 'green',
  rejected: 'red',
  pending_review: 'orange',
  superseded: 'purple',
  under_review: 'blue',
};

const LAYER_COLORS: Record<string, string> = {
  opinion: '#722ed1',
  semantic: '#1890ff',
  procedure: '#52c41a',
  perception: '#faad14',
};

export const MemoryDetailDrawer: React.FC<MemoryDetailDrawerProps> = ({
  nodeId,
  spaceId,
  visible,
  onClose,
  onUpdate,
}) => {
  const { message } = App.useApp();
  const [node, setNode] = useState<CognitiveNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [correctModalVisible, setCorrectModalVisible] = useState(false);
  const [correctForm] = Form.useForm();

  useEffect(() => {
    if (visible && nodeId && spaceId) {
      loadNode();
    }
  }, [visible, nodeId, spaceId]);

  const loadNode = async () => {
    if (!nodeId || !spaceId) return;
    setLoading(true);
    try {
      const node = await memoryApi.getNode(spaceId, nodeId);
      setNode(node);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '加载失败');
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!node || !spaceId) return;
    try {
      await memoryApi.approveNode(spaceId, node.id, 'approve');
      message.success('已批准');
      loadNode();
      onUpdate?.();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleReject = async () => {
    if (!node || !spaceId) return;
    try {
      await memoryApi.approveNode(spaceId, node.id, 'reject');
      message.success('已拒绝');
      loadNode();
      onUpdate?.();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleDelete = async () => {
    if (!node || !spaceId) return;
    try {
      message.warning('删除功能待后端 API 确认');
      onClose();
      onUpdate?.();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleCorrectSubmit = async (values: { correctedText: string; reason: string }) => {
    if (!node || !spaceId) return;
    try {
      await memoryApi.correctNode(spaceId, node.id, values.correctedText, values.reason);
      message.success('更正已提交');
      setCorrectModalVisible(false);
      correctForm.resetFields();
      loadNode();
      onUpdate?.();
    } catch (e) {
      message.error('更正失败');
    }
  };

  const renderActions = () => {
    if (!node) return null;
    return (
      <Space wrap>
        {node.beliefStatus === 'pending_review' && (
          <>
            <Button type="primary" onClick={handleApprove}>确认晋升</Button>
            <Button danger onClick={handleReject}>拒绝</Button>
          </>
        )}
        <Button onClick={() => setCorrectModalVisible(true)}>更正</Button>
        <Popconfirm title="确定删除此记忆？" onConfirm={handleDelete} okText="删除" cancelText="取消">
          <Button danger>删除</Button>
        </Popconfirm>
      </Space>
    );
  };

  return (
    <>
      <Drawer
        title="记忆详情"
        width={600}
        open={visible}
        onClose={onClose}
        footer={renderActions()}
      >
        {node && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">
              <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{node.id}</span>
            </Descriptions.Item>
            <Descriptions.Item label="内容">
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{node.content}</div>
            </Descriptions.Item>
            <Descriptions.Item label="记忆类型">
              <Tag>{node.memoryType}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="认知层级">
              <Tag color={LAYER_COLORS[node.cognitiveLayer] || 'default'}>{node.cognitiveLayer}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="信念状态">
              <Tag color={BELIEF_STATUS_COLORS[node.beliefStatus] || 'default'}>{node.beliefStatus}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              {node.confidence}
            </Descriptions.Item>
            <Descriptions.Item label="可见性">
              {node.visibility}
            </Descriptions.Item>
            <Descriptions.Item label="创建者">
              {node.createdBy}
            </Descriptions.Item>
            <Descriptions.Item label="空间ID">
              {node.spaceId}
            </Descriptions.Item>
            <Descriptions.Item label="标签">
              {node.tags?.map((tag) => <Tag key={tag}>{tag}</Tag>) || '无'}
            </Descriptions.Item>
            <Descriptions.Item label="属性">
              {Object.keys(node.attributes || {}).length > 0
                ? Object.entries(node.attributes).map(([k, v]) => (
                    <div key={k}><strong>{k}:</strong> {v}</div>
                  ))
                : '无'}
            </Descriptions.Item>
            {node.schemaRef && (
              <Descriptions.Item label="Schema引用">{node.schemaRef}</Descriptions.Item>
            )}
            {node.occurredAt && (
              <Descriptions.Item label="发生时间">{node.occurredAt}</Descriptions.Item>
            )}
            {node.recordedAt && (
              <Descriptions.Item label="记录时间">{node.recordedAt}</Descriptions.Item>
            )}
            {node.validFrom && (
              <Descriptions.Item label="有效起始">{node.validFrom}</Descriptions.Item>
            )}
            {node.validTo && (
              <Descriptions.Item label="有效截止">{node.validTo}</Descriptions.Item>
            )}
            {node.supersededBy && (
              <Descriptions.Item label="被替代">
                <Tag color="purple">被 {node.supersededBy} 替代</Tag>
              </Descriptions.Item>
            )}
            {node.sourceTrustTier && (
              <Descriptions.Item label="来源信任等级">{node.sourceTrustTier}</Descriptions.Item>
            )}
            {node.modelDomain && (
              <Descriptions.Item label="模型域">{node.modelDomain}</Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>

      <Modal
        title="更正记忆"
        open={correctModalVisible}
        onCancel={() => setCorrectModalVisible(false)}
        onOk={() => correctForm.submit()}
      >
        <Form form={correctForm} layout="vertical" onFinish={handleCorrectSubmit}>
          <Form.Item name="correctedText" label="更正后内容" rules={[{ required: true }]}>
            <Input.TextArea rows={4} defaultValue={node?.content} />
          </Form.Item>
          <Form.Item name="reason" label="更正原因" rules={[{ required: true }]}>
            <Input placeholder="输入更正原因..." />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default MemoryDetailDrawer;
