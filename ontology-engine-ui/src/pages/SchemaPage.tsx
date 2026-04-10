import { useEffect, useRef, useState, useCallback } from 'react';
import { Segmented, Spin, Card, Space, Input, Checkbox, Button, Empty, Tag, Tooltip } from 'antd';
import { SearchOutlined, DownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { fetchSchemaGraph } from '../api/visualization';
import SchemaGraph from '../components/schema/SchemaGraph';
import type { SchemaGraphRef } from '../components/schema/SchemaGraph';
import NodeDetailPanel from '../components/schema/NodeDetailPanel';
import MetricScorecard from '../components/schema/MetricScorecard';
import type { SchemaGraphData, GraphNode } from '../types/visualization';
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
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const graphRef = useRef<SchemaGraphRef>(null);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchSchemaGraph(graphType, layerFilter);
      setData(result);
      setSelectedNode(null);
    } catch (e) {
      console.error('Failed to load schema graph:', e);
    } finally {
      setLoading(false);
    }
  }, [graphType, layerFilter]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  const handleSearch = () => {
    // Search functionality can be implemented to focus on nodes
    if (!searchText || !data) return;
    const found = data.nodes.find(n => 
      n.id.toLowerCase().includes(searchText.toLowerCase()) ||
      n.data?.label?.toLowerCase().includes(searchText.toLowerCase())
    );
    if (found) {
      setSelectedNode(found);
    }
  };

  const handleExport = async () => {
    // Use G6's built-in export method via ref
    if (graphRef.current) {
      const dataUrl = graphRef.current.exportImage();
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

  const showScorecard = selectedNode?.type === 'metric' && 
    (selectedNode.id === 'credit_score' || Object.keys(selectedNode.data?.weight_map || {}).length > 0);

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <Space size="middle">
          <Segmented 
            options={GRAPH_TYPES} 
            value={graphType} 
            onChange={(v) => setGraphType(v as string)}
            style={{ fontSize: 13 }}
          />
          <Tooltip title="实体关系=L1实体图; 指标依赖=L3指标勾稽图; 全景图=所有层级; 规则概览=L4规则图">
            <InfoCircleOutlined style={{ color: '#999' }} />
          </Tooltip>
        </Space>
        
        <Space size="middle">
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
            onChange={(v) => setLayerFilter(v as string[])}
          />
          <Button 
            icon={<DownloadOutlined />} 
            onClick={handleExport}
            size="middle"
          >
            导出
          </Button>
        </Space>
      </div>

      {/* Body */}
      <div className="page-body">
        {/* Graph Panel */}
        <div className="graph-panel">
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
          
          {/* Metadata stats overlay */}
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

        {/* Detail Panel */}
        <div className="detail-panel">
          {selectedNode ? (
            showScorecard ? (
              <MetricScorecard node={selectedNode} />
            ) : (
              <NodeDetailPanel 
                node={selectedNode}
                onMetricClick={(id) => {
                  const metric = data?.nodes.find(n => n.id === id);
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
                    在图谱中点击任意节点<br/>
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
