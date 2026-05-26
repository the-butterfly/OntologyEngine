import React, { useEffect, useState, useCallback } from 'react';
import { Spin, Empty, Alert, Card, Space, Select, Input, Button, Tooltip, message, Segmented, Drawer } from 'antd';
import { SearchOutlined, DownloadOutlined, InfoCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import InstanceGraphView from '../../components/instance/InstanceGraphView';
import GroupingPanel from '../../components/instance/GroupingPanel';
import InstanceNodeDetail from '../../components/instance/InstanceNodeDetail';
import { spaceApi } from '../../api/spaceApi';
import type { InstanceGraphData, InstanceGraphNode } from '../../api/spaceApi';
import { useSpaceStore } from '../../store/spaceStore';

const LAYOUT_OPTIONS = [
  { label: '力导向', value: 'force' },
  { label: 'DAG分层', value: 'dagre' },
  { label: '同心圆', value: 'concentric' },
];

export default function InstanceGraphPage() {
  const { activeSpace, activeSpaceId } = useSpaceStore();
  const [graphData, setGraphData] = useState<InstanceGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<{ id: string; data: any } | null>(null);
  const [layoutMode, setLayoutMode] = useState<'force' | 'dagre' | 'concentric'>('force');
  const [seedEntityId, setSeedEntityId] = useState<string>('');
  const [maxHops, setMaxHops] = useState<number>(3);
  const [conceptFilter, setConceptFilter] = useState<string>('');
  const [highlightPath, setHighlightPath] = useState<string[]>([]);
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(new Set());
  const [searchText, setSearchText] = useState('');
  const [visibleConcepts, setVisibleConcepts] = useState<string[]>([]);
  const [layoutLocked, setLayoutLocked] = useState(false);
  const [activeConcepts, setActiveConcepts] = useState<string[]>([]);

  const loadGraph = useCallback(async () => {
    if (!activeSpaceId) return;
    setLoading(true);
    setError(null);
    try {
      const params: any = { max_hops: maxHops };
      if (seedEntityId) params.seed_entity_id = seedEntityId;
      if (conceptFilter) params.concept_filter = conceptFilter;
      const data = await spaceApi.getInstanceGraph(activeSpaceId, params);
      setGraphData(data);
      setVisibleConcepts(Object.keys(data.metadata.concept_counts));
    } catch (e: any) {
      setError(e.message || '加载图数据失败');
      message.error('加载图数据失败');
    } finally {
      setLoading(false);
    }
  }, [activeSpaceId, seedEntityId, maxHops, conceptFilter]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  const handleNodeClick = (nodeId: string, nodeData: any) => {
    setSelectedNode({ id: nodeId, data: nodeData });
  };

  const handleExport = () => {
    if (!graphData) return;
    const data = JSON.stringify(graphData, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `instance-graph-${activeSpaceId}-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleGroupClick = (groupType: string, groupId: string, nodeIds: string[]) => {
    setHighlightPath(nodeIds.slice(0, 10));
    message.success(`已高亮 ${groupType} 分组: ${groupId} (${nodeIds.length} 节点)`);
  };

  const handleSearch = () => {
    if (!searchText || !graphData) return;
    const term = searchText.toLowerCase();
    const found = graphData.nodes.find(n =>
      n.id.toLowerCase().includes(term) ||
      n.data.label.toLowerCase().includes(term) ||
      n.data.concept.toLowerCase().includes(term)
    );
    if (found) {
      setSelectedNode({ id: found.id, data: found.data });
      setHighlightPath([found.id]);
    } else {
      message.warning('未找到匹配的节点');
    }
  };

  const handleConceptFilterChange = (values: string[]) => {
    setConceptFilter(values.join(','));
  };

  const handleLegendClick = (concept: string) => {
    setActiveConcepts(prev => {
      if (prev.includes(concept)) {
        const next = prev.filter(c => c !== concept);
        if (next.length === 0) return [];
        return next;
      }
      return [...prev, concept];
    });
  };

  if (!activeSpaceId) {
    return (
      <Card>
        <Empty description="请先选择语义空间" />
      </Card>
    );
  }

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 16 }}>
        <Space size="middle" wrap>
          <Segmented
            options={LAYOUT_OPTIONS}
            value={layoutMode}
            onChange={v => setLayoutMode(v as typeof layoutMode)}
            size="middle"
          />

          <Input
            placeholder="种子实体ID..."
            prefix={<SearchOutlined />}
            value={seedEntityId}
            onChange={e => setSeedEntityId(e.target.value)}
            onPressEnter={loadGraph}
            style={{ width: 200 }}
            allowClear
          />

          <Select
            value={maxHops}
            onChange={setMaxHops}
            options={[
              { label: '1 跳', value: 1 },
              { label: '2 跳', value: 2 },
              { label: '3 跳', value: 3 },
              { label: '5 跳', value: 5 },
            ]}
            style={{ width: 100 }}
          />

          <Select
            mode="multiple"
            placeholder="概念过滤"
            value={visibleConcepts}
            onChange={handleConceptFilterChange}
            options={Object.keys(graphData?.metadata.concept_counts || {}).map(c => ({ label: c, value: c }))}
            style={{ width: 200 }}
            allowClear
          />

          <Input
            placeholder="搜索节点..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 140 }}
            allowClear
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>

          <Button icon={<ReloadOutlined />} onClick={loadGraph} loading={loading}>
            刷新
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleExport} disabled={!graphData}>
            导出
          </Button>

          <Tooltip title="力导向=自由探索; DAG分层=数据流/检索流层级; 同心圆=以种子为中心辐射">
            <InfoCircleOutlined style={{ color: '#999' }} />
          </Tooltip>
        </Space>
      </div>

      {error && (
        <Alert
          type="error"
          message="加载失败"
          description={error}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      {graphData && graphData.nodes.length > 0 && (
        <GroupingPanel
          grouping={graphData.grouping}
          metadata={graphData.metadata}
          onGroupClick={handleGroupClick}
        />
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 560 }}>
          <Spin size="large">
            <div style={{ padding: '40px 0' }}>加载实例图谱...</div>
          </Spin>
        </div>
      ) : graphData && graphData.nodes.length > 0 ? (
        <InstanceGraphView
          nodes={graphData.nodes}
          edges={graphData.edges}
          graphData={graphData}
          height={560}
          layoutMode={layoutMode}
          highlightPath={highlightPath}
          hiddenNodeIds={hiddenNodeIds}
          layoutLocked={layoutLocked}
          activeConcepts={activeConcepts}
          onNodeClick={handleNodeClick}
          onLegendClick={handleLegendClick}
          onLayoutLockedChange={setLayoutLocked}
        />
      ) : (
        <Card>
          <Empty
            description="暂无实例数据"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </Card>
      )}

      {graphData?.metadata && (
        <div style={{ marginTop: 12 }}>
          <Space size="small">
            {Object.entries(graphData.metadata.concept_counts).map(([concept, count]) => (
              <span key={concept}>{concept}: {count}</span>
            ))}
            <span style={{ color: '#999' }}>|</span>
            <span>{graphData.metadata.entity_count} 实体</span>
            <span>{graphData.metadata.relation_count} 关系</span>
            {graphData.metadata.cycle_count > 0 && (
              <span style={{ color: '#ff4d4f' }}>{graphData.metadata.cycle_count} 担保圈</span>
            )}
          </Space>
        </div>
      )}

      <Drawer
        title="节点详情"
        placement="right"
        width={360}
        open={!!selectedNode}
        onClose={() => setSelectedNode(null)}
        destroyOnClose
      >
        {selectedNode && (
          <InstanceNodeDetail
            nodeId={selectedNode.id}
            nodeData={selectedNode.data}
          />
        )}
      </Drawer>
    </div>
  );
}
