import { useCallback, useEffect, useRef, useState } from 'react';
import { Segmented, Spin, Space, Input, Checkbox, Button, Empty, Tag, Tooltip, Alert, Select } from 'antd';
import { SearchOutlined, DownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { fetchSchemaGraph, fetchVisualizationEntities, ApiError } from '../api/visualization';
import SchemaGraph from '../components/schema/SchemaGraph';
import type { SchemaGraphRef } from '../components/schema/SchemaGraph';
import NodeDetailPanel from '../components/schema/NodeDetailPanel';
import MetricScorecard from '../components/schema/MetricScorecard';
import type { SchemaGraphData, GraphNode, VisualizationEntityOption } from '../types/visualization';
import '../App.css';

const GRAPH_TYPES = [
  { label: '实体关系', value: 'entity_relation' },
  { label: '指标依赖(勾稽)', value: 'metric_dependency' },
  { label: '全景图', value: 'full' },
  { label: '规则概览', value: 'rule_overview' },
];

const LAYER_OPTIONS = [
  { label: 'L1 实体', value: 'L1' },
  { label: 'L3 指标', value: 'L3' },
  { label: 'L4 规则', value: 'L4' },
];

export default function SchemaPage() {
  const [graphType, setGraphType] = useState('entity_relation');
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchText, setSearchText] = useState('');
  const [layerFilter, setLayerFilter] = useState<string[]>(['L1', 'L3', 'L4']);
  const [data, setData] = useState<SchemaGraphData | null>(null);
  const [, setHoveredNode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [entityOptions, setEntityOptions] = useState<VisualizationEntityOption[]>([]);
  const [entityId, setEntityId] = useState<string>('');
  const [entityLoading, setEntityLoading] = useState(false);
  const graphRef = useRef<SchemaGraphRef>(null);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchSchemaGraph(graphType, layerFilter);
      setData(result);
      setSelectedNode(null);
    } catch (e) {
      const message = e instanceof ApiError ? e.message : 'Failed to load schema graph';
      setError(message);
      console.error('Failed to load schema graph:', e);
    } finally {
      setLoading(false);
    }
  }, [graphType, layerFilter]);

  const loadEntities = useCallback(async () => {
    setEntityLoading(true);
    try {
      const options = await fetchVisualizationEntities('Supplier', 'credit_assessment');
      setEntityOptions(options);
      setEntityId((prev) => {
        if (prev && options.some((item) => item.entity_id === prev)) {
          return prev;
        }
        return options[0]?.entity_id || '';
      });
    } catch (e) {
      const message = e instanceof ApiError ? e.message : 'Failed to load entities';
      setError(message);
      setEntityOptions([]);
      setEntityId('');
    } finally {
      setEntityLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  useEffect(() => {
    void loadEntities();
  }, [loadEntities]);

  const handleSearch = () => {
    if (!searchText || !data) return;
    const found = data.nodes.find((node) =>
      node.id.toLowerCase().includes(searchText.toLowerCase()) ||
      node.data?.label?.toLowerCase().includes(searchText.toLowerCase())
    );
    if (found) {
      setSelectedNode(found);
    }
  };

  const handleExport = async () => {
    if (graphRef.current) {
      const dataUrl = await graphRef.current.exportImage();
      if (dataUrl) {
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = `schema-${graphType}-${Date.now()}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        console.warn('Failed to export graph: no data URL generated');
      }
    } else {
      console.warn('Graph ref not available for export');
    }
  };

  const showScorecard =
    selectedNode?.type === 'metric' &&
    (selectedNode.id === 'credit_score' || Object.keys(selectedNode.data?.weight_map || {}).length > 0);

  return (
    <div className="page-container">
      <div className="page-header">
        <Space size="middle" wrap>
          <Space size="middle">
            <Segmented
              options={GRAPH_TYPES}
              value={graphType}
              onChange={(value) => setGraphType(value as string)}
              style={{ fontSize: 13 }}
            />
            <Tooltip title="实体关系=L1实体图; 指标依赖=L3指标勾稽图; 全景图=所有层级; 规则概览=L4规则图">
              <InfoCircleOutlined style={{ color: '#999' }} />
            </Tooltip>
          </Space>

          <Space size="middle" wrap>
            <Input
              placeholder="搜索节点..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onPressEnter={handleSearch}
              style={{ width: 180 }}
              size="middle"
            />
            <Checkbox.Group
              options={LAYER_OPTIONS}
              value={layerFilter}
              onChange={(value) => setLayerFilter(value as string[])}
            />
            <Select
              value={entityId || undefined}
              onChange={setEntityId}
              options={entityOptions.map((item) => ({ label: item.label, value: item.entity_id }))}
              style={{ width: 240 }}
              size="middle"
              placeholder="选择评分实体"
              loading={entityLoading}
              disabled={entityLoading || entityOptions.length === 0}
            />
            <Button icon={<DownloadOutlined />} onClick={handleExport} size="middle">
              导出
            </Button>
          </Space>
        </Space>
      </div>

      <div className="page-body">
        <div className="graph-panel">
          {error && (
            <Alert
              type="error"
              message="加载失败"
              description={error}
              showIcon
              closable
              style={{ margin: 16 }}
            />
          )}
          {loading ? (
            <div className="loading-container">
              <Spin size="large">
                <div style={{ padding: '40px 0' }}>加载知识图谱...</div>
              </Spin>
            </div>
          ) : (
            <SchemaGraph
              ref={graphRef}
              data={data}
              loading={loading}
              onNodeClick={setSelectedNode}
              onNodeHover={setHoveredNode}
            />
          )}

          {data?.metadata && (
            <div className="graph-stats">
              <Space size="small">
                <Tag color="blue">实体: {data.metadata.entity_count}</Tag>
                <Tag color="green">指标: {data.metadata.metric_count}</Tag>
                <Tag color="orange">规则: {data.metadata.rule_count}</Tag>
                <Tag>关系: {data.metadata.relation_count}</Tag>
              </Space>
            </div>
          )}
        </div>

        <div className="detail-panel">
          {selectedNode ? (
            showScorecard ? (
              <MetricScorecard node={selectedNode} entityId={entityId} />
            ) : (
              <NodeDetailPanel
                node={selectedNode}
                onMetricClick={(id) => {
                  const metric = data?.nodes.find((node) => node.id === id);
                  if (metric) setSelectedNode(metric);
                }}
              />
            )
          ) : (
            <Empty
              description={
                <span>
                  <div style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>
                    点击节点查看详情
                  </div>
                  <div style={{ fontSize: 12, color: '#999' }}>
                    在图谱中点击任意节点<br />
                    查看 Schema 定义详情
                  </div>
                </span>
              }
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </div>
      </div>
    </div>
  );
}
