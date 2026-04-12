// ontology-engine-ui/src/pages/consumption/SchemaVisualizationPage.tsx
// Schema visualization page for consumption surface with G6 graph

import { useEffect, useRef, useState, useCallback } from 'react';
import { Segmented, Spin, Space, Input, Button, Empty, Tag, Tooltip, Alert, Card, Typography, Select } from 'antd';
import { SearchOutlined, DownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import SchemaGraph from '../../components/schema/SchemaGraph';
import type { SchemaGraphRef } from '../../components/schema/SchemaGraph';
import NodeDetailPanel from '../../components/schema/NodeDetailPanel';
import { useSpaceStore } from '../../store/spaceStore';
import type { GraphNode } from '../../types/visualization';
import '../../App.css';

const { Title, Text } = Typography;

const GRAPH_TYPES = [
  { label: '实体关系', value: 'entity_relation' },
  { label: '指标依赖', value: 'metric_dependency' },
  { label: '全景图', value: 'full' },
  { label: '规则概览', value: 'rule_overview' },
];

const LAYER_OPTIONS = [
  { label: 'L1 实体', value: 'L1' },
  { label: 'L3 指标', value: 'L3' },
  { label: 'L4 规则', value: 'L4' },
];

export default function SchemaVisualizationPage() {
  const {
    activeViewId,
    schemaGraph,
    loadSchemaGraph,
    executeLoading,
    error,
    clearError,
  } = useSpaceStore();

  const [graphType, setGraphType] = useState('entity_relation');
  const [layerFilter, setLayerFilter] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchText, setSearchText] = useState('');
  const [, setHoveredNode] = useState<string | null>(null);
  const graphRef = useRef<SchemaGraphRef>(null);

  const loadGraph = useCallback(() => {
    if (activeViewId) {
      loadSchemaGraph(activeViewId, graphType, layerFilter || undefined);
    }
  }, [activeViewId, graphType, layerFilter, loadSchemaGraph]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  useEffect(() => {
    if (error) {
      clearError();
    }
  }, [error]);

  const handleSearch = () => {
    if (!searchText || !schemaGraph) return;
    const found = schemaGraph.nodes?.find((node: GraphNode) =>
      node.id.toLowerCase().includes(searchText.toLowerCase()) ||
      node.data?.label?.toLowerCase().includes(searchText.toLowerCase())
    );
    if (found) {
      setSelectedNode(found);
    }
  };

  const handleExport = async () => {
    if (graphRef.current) {
      try {
        const dataUrl = await graphRef.current.exportImage();
        if (dataUrl) {
          const a = document.createElement('a');
          a.href = dataUrl;
          a.download = `schema-${graphType}-${Date.now()}.png`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
        }
      } catch (e) {
        console.error('Failed to export:', e);
      }
    }
  };

  if (!activeViewId) {
    return (
      <Card>
        <Empty description="请先激活空间以创建消费视图" />
      </Card>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <Space size="middle" wrap>
          <Space size="middle">
            <Segmented
              options={GRAPH_TYPES}
              value={graphType}
              onChange={(value) => {
                setGraphType(value as string);
                setSelectedNode(null);
              }}
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
            <Select
              value={layerFilter}
              onChange={(value) => {
                setLayerFilter(value);
                setSelectedNode(null);
              }}
              options={[
                { label: '全部层级', value: '' },
                { label: 'L1 事实对象', value: 'L1' },
                { label: 'L2 分类体系', value: 'L2' },
                { label: 'L3 分析要素', value: 'L3' },
                { label: 'L4 业务逻辑', value: 'L4' },
              ]}
              style={{ width: 150 }}
              size="middle"
              placeholder="选择层级"
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
          {executeLoading ? (
            <div className="loading-container">
              <Spin size="large">
                <div style={{ padding: '40px 0' }}>加载知识图谱...</div>
              </Spin>
            </div>
          ) : schemaGraph ? (
            <SchemaGraph
              ref={graphRef}
              data={schemaGraph}
              loading={executeLoading}
              onNodeClick={setSelectedNode}
              onNodeHover={setHoveredNode}
            />
          ) : (
            <Empty
              description="暂无可视化数据"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}

          {schemaGraph?.metadata && (
            <div className="graph-stats">
              <Space size="small">
                <Tag color="blue">实体: {schemaGraph.metadata.entity_count || 0}</Tag>
                <Tag color="green">指标: {schemaGraph.metadata.metric_count || 0}</Tag>
                <Tag color="orange">规则: {schemaGraph.metadata.rule_count || 0}</Tag>
              </Space>
            </div>
          )}
        </div>

        <div className="detail-panel">
          {selectedNode ? (
            <NodeDetailPanel
              node={selectedNode}
              onMetricClick={(id) => {
                const metric = schemaGraph?.nodes?.find((node: GraphNode) => node.id === id);
                if (metric) setSelectedNode(metric);
              }}
            />
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
