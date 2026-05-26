import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Input, Button, Form, App, Typography, List, Tag, Progress, Collapse, Descriptions, Space, Alert } from 'antd';
import { SyncOutlined, WarningOutlined, BulbOutlined, FileTextOutlined } from '@ant-design/icons';
import { memoryApi } from '../../../api/memoryApi';
import type { ReflectResponse } from '../../../types/api';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

const ReflectCenterPage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState<ReflectResponse[]>([]);
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);

  const handleReflect = async (values: any) => {
    if (!spaceId) return;
    setLoading(true);
    try {
      const result = await memoryApi.reflect(spaceId, {
        query: values.query,
        maxIterations: values.maxIterations || 10,
        focusTypes: values.focusTypes ? values.focusTypes.split(',').map((t: string) => t.trim()) : undefined,
      });
      message.success('反思任务已启动');
      setTasks([result, ...tasks]);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '反思失败');
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (taskId: string) => {
    setExpandedTaskId(expandedTaskId === taskId ? null : taskId);
  };

  const renderTaskDetails = (task: ReflectResponse) => {
    const { report } = task;
    if (!report) return <Text type="secondary">报告生成中...</Text>;

    return (
      <div style={{ marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 8 }}>
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="总迭代数">{report.totalIterations}</Descriptions.Item>
          <Descriptions.Item label="处理节点数">{report.processedNodes}</Descriptions.Item>
          <Descriptions.Item label="新增节点数">{report.newNodes}</Descriptions.Item>
          <Descriptions.Item label="更新节点数">{report.updatedNodes}</Descriptions.Item>
        </Descriptions>

        {report.summary && (
          <Alert
            message="反思摘要"
            description={report.summary}
            type="info"
            showIcon
            icon={<FileTextOutlined />}
            style={{ marginTop: 16 }}
          />
        )}

        {report.insights && report.insights.length > 0 && (
          <Card title={<span><BulbOutlined /> 洞察 ({report.insights.length})</span>} size="small" style={{ marginTop: 16 }}>
            <List
              dataSource={report.insights}
              renderItem={(insight, idx) => (
                <List.Item>
                  <List.Item.Meta
                    title={`洞察 #${idx + 1}: ${insight.type}`}
                    description={insight.description}
                  />
                  <Tag color="blue">置信度: {insight.confidence}</Tag>
                </List.Item>
              )}
            />
          </Card>
        )}

        {report.contradictions && report.contradictions.length > 0 && (
          <Card title={<span><WarningOutlined /> 发现矛盾 ({report.contradictions.length})</span>} size="small" style={{ marginTop: 16 }}>
            <List
              dataSource={report.contradictions}
              renderItem={(contradiction, idx) => (
                <List.Item>
                  <List.Item.Meta
                    title={`矛盾 #${idx + 1}`}
                    description={contradiction.description}
                  />
                  <Space>
                    <Tag color="red">严重度: {contradiction.severity}</Tag>
                    <Tag>涉及: {contradiction.involvedNodes?.length || 0} 节点</Tag>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}

        {report.consolidatedNodes && report.consolidatedNodes.length > 0 && (
          <Card title="整合节点" size="small" style={{ marginTop: 16 }}>
            {report.consolidatedNodes.map((nodeId) => (
              <Tag key={nodeId} style={{ margin: 4 }}>{nodeId}</Tag>
            ))}
          </Card>
        )}
      </div>
    );
  };

  return (
    <div>
      <Title level={3}>反思中心</Title>
      <Card title="发起反思" style={{ marginBottom: 24 }}>
        <Form form={form} layout="vertical" onFinish={handleReflect}>
          <Form.Item name="query" label="反思主题" rules={[{ required: true }]}>
            <TextArea rows={3} placeholder="输入反思主题或问题..." />
          </Form.Item>
          <Form.Item name="maxIterations" label="最大迭代数" initialValue={10}>
            <Input type="number" min={1} max={100} />
          </Form.Item>
          <Form.Item name="focusTypes" label="聚焦类型 (逗号分隔)">
            <Input placeholder="observation, opinion, entity" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} icon={<SyncOutlined />}>
              启动反思
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="Reflect 任务">
        {tasks.length === 0 ? (
          <Text type="secondary">暂无反思任务</Text>
        ) : (
          <List
            dataSource={tasks}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button size="small" onClick={() => toggleExpand(item.taskId)}>
                    {expandedTaskId === item.taskId ? '收起' : '展开详情'}
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <span>
                      反思任务: {item.taskId}
                      <Tag color={item.status === 'completed' ? 'green' : 'blue'} style={{ marginLeft: 8 }}>
                        {item.status}
                      </Tag>
                    </span>
                  }
                  description={item.report?.summary || '处理中...'}
                />
                {item.status === 'processing' && <Progress percent={50} size="small" />}
                {expandedTaskId === item.taskId && renderTaskDetails(item)}
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
};

export default ReflectCenterPage;
