import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Input, Button, List, Tag, Slider, Form, message, Typography, Collapse, Descriptions, Space, Tree, Spin, Empty } from 'antd';
import { SearchOutlined, EyeOutlined, LinkOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { memoryApi } from '../../../services/memoryApi';
import type { CognitiveNode } from '../../../types/memory';
import { MemoryDetailDrawer } from '../../../components/memory';

const { Title, Text } = Typography;
const { Panel } = Collapse;

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

interface EvidenceNode {
  title: string;
  key: string;
  children?: EvidenceNode[];
  icon?: React.ReactNode;
}

const MemoryConsumePage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CognitiveNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [disposition, setDisposition] = useState({
    recency: 0.5,
    relevance: 0.5,
    confidence: 0.5,
  });
  const [detailNodeId, setDetailNodeId] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [evidenceMap, setEvidenceMap] = useState<Record<string, any>>({});
  const [evidenceLoading, setEvidenceLoading] = useState<Record<string, boolean>>({});

  const handleSearch = async () => {
    if (!spaceId || !query.trim()) {
      message.warning('请输入搜索内容');
      return;
    }
    setLoading(true);
    try {
      // [T2.1] Disposition 滑块值传入 recall API
      // 后端支持 disposition_override 参数（scene name 模式）
      // 根据滑块值选择最匹配的 scene
      const minConfidence = disposition.confidence > 0.7 ? 0.6 : disposition.confidence > 0.3 ? 0.3 : 0.1;
      let dispositionScene: string | undefined;
      if (disposition.recency > 0.7 && disposition.relevance > 0.7) {
        dispositionScene = 'high_relevance';
      } else if (disposition.recency > 0.7) {
        dispositionScene = 'high_recency';
      } else if (disposition.confidence > 0.7) {
        dispositionScene = 'high_confidence';
      }
      const response = await memoryApi.recall(spaceId, {
        query,
        maxResults: 20,
        minConfidence,
        dispositionOverride: dispositionScene as any,
      });
      setResults(response.results || []);
    } catch (e) {
      message.error(e instanceof Error ? e.message : '搜索失败');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (nodeId: string) => {
    if (!spaceId) return;
    try {
      await memoryApi.approveNode(spaceId, nodeId, 'approve');
      message.success('已批准');
      setResults(results.map((r) => (r.id === nodeId ? { ...r, beliefStatus: 'accepted' } : r)));
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleOpenDetail = (nodeId: string) => {
    setDetailNodeId(nodeId);
    setDetailVisible(true);
  };

  const loadEvidence = async (nodeId: string) => {
    if (!spaceId) return;
    setEvidenceLoading((prev) => ({ ...prev, [nodeId]: true }));
    try {
      const data = await memoryApi.getEvidence(spaceId, nodeId);
      setEvidenceMap((prev) => ({ ...prev, [nodeId]: data }));
    } catch (e) {
      message.error('加载证据链失败');
    } finally {
      setEvidenceLoading((prev) => ({ ...prev, [nodeId]: false }));
    }
  };

  const buildEvidenceTree = (nodeId: string): EvidenceNode[] => {
    const data = evidenceMap[nodeId];
    if (!data) return [];

    const nodes: EvidenceNode[] = [];

    // Source fragments
    if (data.source_fragments && data.source_fragments.length > 0) {
      nodes.push({
        title: `来源碎片 (${data.source_fragments.length})`,
        key: `${nodeId}-fragments`,
        icon: <LinkOutlined />,
        children: data.source_fragments.map((f: any, idx: number) => ({
          title: f.content ? `${f.content.substring(0, 40)}...` : `碎片 ${idx + 1}`,
          key: `${nodeId}-frag-${idx}`,
          icon: <CheckCircleOutlined />,
        })),
      });
    }

    // Supporting nodes
    if (data.supporting_nodes && data.supporting_nodes.length > 0) {
      nodes.push({
        title: `支持节点 (${data.supporting_nodes.length})`,
        key: `${nodeId}-supporting`,
        icon: <LinkOutlined />,
        children: data.supporting_nodes.map((n: any, idx: number) => ({
          title: n.content ? `${n.content.substring(0, 40)}...` : `节点 ${idx + 1}`,
          key: `${nodeId}-sup-${idx}`,
          icon: <CheckCircleOutlined />,
        })),
      });
    }

    // Consolidated into
    if (data.consolidated_into && data.consolidated_into.length > 0) {
      nodes.push({
        title: `巩固为 (${data.consolidated_into.length})`,
        key: `${nodeId}-consolidated`,
        icon: <LinkOutlined />,
        children: data.consolidated_into.map((c: any, idx: number) => ({
          title: `→ ${c.target_id?.slice(0, 16)}...`,
          key: `${nodeId}-cons-${idx}`,
          icon: <CheckCircleOutlined />,
        })),
      });
    }

    return nodes;
  };

  // Group results by cognitive layer for layered display
  const groupedResults = results.reduce((acc, node) => {
    const layer = node.cognitiveLayer || 'unknown';
    if (!acc[layer]) acc[layer] = [];
    acc[layer].push(node);
    return acc;
  }, {} as Record<string, CognitiveNode[]>);

  const layerOrder = ['opinion', 'semantic', 'procedure', 'perception'];
  const sortedLayers = layerOrder.filter((l) => groupedResults[l]).concat(
    Object.keys(groupedResults).filter((l) => !layerOrder.includes(l))
  );

  return (
    <div>
      <Title level={3}>记忆消费</Title>
      <Card title="分层检索" style={{ marginBottom: 24 }}>
        <Input.Search
          placeholder="输入查询内容..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onSearch={handleSearch}
          loading={loading}
          enterButton={<><SearchOutlined /> 搜索</>}
        />
      </Card>

      <Card title="Disposition Profile" style={{ marginBottom: 24 }}>
        <Form layout="vertical">
          <Form.Item label="时效性权重">
            <Slider value={disposition.recency} onChange={(v) => setDisposition({ ...disposition, recency: v })} min={0} max={1} step={0.1} />
          </Form.Item>
          <Form.Item label="相关性权重">
            <Slider value={disposition.relevance} onChange={(v) => setDisposition({ ...disposition, relevance: v })} min={0} max={1} step={0.1} />
          </Form.Item>
          <Form.Item label="置信度权重">
            <Slider value={disposition.confidence} onChange={(v) => setDisposition({ ...disposition, confidence: v })} min={0} max={1} step={0.1} />
          </Form.Item>
        </Form>
      </Card>

      <Card title="检索结果">
        {results.length === 0 ? (
          <Text type="secondary">暂无结果，请输入查询内容</Text>
        ) : (
          <Collapse defaultActiveKey={sortedLayers}>
            {sortedLayers.map((layer) => (
              <Panel
                header={
                  <Space>
                    <Tag color={LAYER_COLORS[layer] || 'default'}>{layer}</Tag>
                    <Text>{groupedResults[layer].length} 条结果</Text>
                  </Space>
                }
                key={layer}
              >
                <List
                  dataSource={groupedResults[layer]}
                  renderItem={(item) => (
                    <List.Item
                      actions={[
                        <Button size="small" icon={<EyeOutlined />} onClick={() => handleOpenDetail(item.id)}>查看详情</Button>,
                        <Button
                          size="small"
                          icon={<LinkOutlined />}
                          onClick={() => loadEvidence(item.id)}
                          loading={evidenceLoading[item.id]}
                        >
                          证据链
                        </Button>,
                        item.beliefStatus === 'pending_review' && (
                          <Button size="small" type="primary" onClick={() => handleApprove(item.id)}>批准</Button>
                        ),
                      ]}
                    >
                      <List.Item.Meta
                        title={
                          <span>
                            {item.content.substring(0, 100)}
                            {item.content.length > 100 && '...'}
                            <Tag color="blue" style={{ marginLeft: 8 }}>{item.memoryType}</Tag>
                            <Tag color={BELIEF_STATUS_COLORS[item.beliefStatus] || 'default'}>{item.beliefStatus}</Tag>
                          </span>
                        }
                        description={
                          <Space>
                            <Text type="secondary">置信度: {item.confidence}</Text>
                            <Text type="secondary">层级: {item.cognitiveLayer}</Text>
                            {item.tags && item.tags.length > 0 && (
                              <span>{item.tags.map((t) => <Tag key={t}>{t}</Tag>)}</span>
                            )}
                          </Space>
                        }
                      />
                      {evidenceMap[item.id] && (
                        <div style={{ marginTop: 12, padding: 12, background: '#fafafa', borderRadius: 8 }}>
                          <Text strong>证据链</Text>
                          {evidenceLoading[item.id] ? (
                            <Spin size="small" />
                          ) : (
                            <Tree
                              treeData={buildEvidenceTree(item.id)}
                              defaultExpandAll
                              showIcon
                            />
                          )}
                        </div>
                      )}
                    </List.Item>
                  )}
                />
              </Panel>
            ))}
          </Collapse>
        )}
      </Card>

      <MemoryDetailDrawer
        nodeId={detailNodeId}
        spaceId={spaceId || ''}
        visible={detailVisible}
        onClose={() => setDetailVisible(false)}
        onUpdate={handleSearch}
      />
    </div>
  );
};

export default MemoryConsumePage;
