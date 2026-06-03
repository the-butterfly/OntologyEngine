import React, { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Input, Button, Space, Card, Row, Col, Spin, Empty, Select, Drawer, Typography, Divider, Tag, message, Alert, Segmented } from 'antd';
import { SearchOutlined, ReloadOutlined, DatabaseOutlined, ApartmentOutlined, BulbOutlined } from '@ant-design/icons';
import { memoryApi } from '../../api/memoryApi';
import { spaceApi } from '../../api/spaceApi';
import MemoryTraceGraph from '../../components/explorer/MemoryTraceGraph';
import RetrievalTracePanel from '../../components/explorer/RetrievalTracePanel';
import {
  COGNITIVE_LAYER_COLORS,
  MEMORY_TYPE_COLORS,
} from '../../components/graph-shared';

const { Title, Text, Paragraph } = Typography;

type DataSource = 'memory' | 'instance';

interface RecallResult {
  id: string;
  memoryType?: string;
  text?: string;
  cognitiveLayer?: string;
  beliefStatus?: string;
  confidence?: number;
  score?: number;
  source?: string;
  rankScore?: number;
  typeWeight?: number;
  temporalProximity?: number;
  strengthBreakdown?: Record<string, number>;
  evidence?: Array<{ id: string; memoryType?: string; text?: string; edgeType?: string; confidence?: number; contribution?: number }>;
  [key: string]: unknown;
}

interface GraphEdge {
  edgeType: string;
  fromId: string;
  toId: string;
  properties?: Record<string, any>;
  createdAt?: string;
}

const KnowledgeExplorerPage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const [dataSource, setDataSource] = useState<DataSource>('memory');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [graphLoading, setGraphLoading] = useState(false);
  const [results, setResults] = useState<RecallResult[]>([]);
  const [queryType, setQueryType] = useState<string>('');
  const [graphNodes, setGraphNodes] = useState<RecallResult[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerData, setDrawerData] = useState<RecallResult | null>(null);
  const [filterLayer, setFilterLayer] = useState<string | undefined>();
  const [filterType, setFilterType] = useState<string | undefined>();
  const [highlightIds, setHighlightIds] = useState<Set<string>>(new Set());
  const [activeStep, setActiveStep] = useState(-1);

  const fetchMemoryGraph = useCallback(async () => {
    if (!spaceId) return null;
    try {
      const data = await memoryApi.getMemoryGraphFull(spaceId, {
        memoryType: filterType,
        beliefStatus: filterLayer,
      });
      const nodes = data.nodes.map((n: any) => ({ ...n, text: n.text || n.content }));
      if (nodes.length === 0) return null;
      return { nodes, edges: data.edges, source: 'memory' as const };
    } catch {
      return null;
    }
  }, [spaceId, filterType, filterLayer]);

  const fetchInstanceGraph = useCallback(async () => {
    if (!spaceId) return null;
    try {
      const data = await spaceApi.getInstanceGraph(spaceId, { max_hops: 3 });
      const nodes: RecallResult[] = (data.nodes || []).map((n: any) => ({
        id: n.id,
        memoryType: n.data?.concept || 'instance',
        text: n.data?.label || n.id,
        cognitiveLayer: 'semantic',
        beliefStatus: 'accepted',
        confidence: n.data?.credit_score ? Number(n.data.credit_score) / 100 : 0.5,
        ...n.data,
      }));
      const edges: GraphEdge[] = (data.edges || []).map((e: any, i: number) => ({
        edgeType: e.data?.relation_type || e.type || 'relation',
        fromId: e.source,
        toId: e.target,
        properties: e.data?.properties,
      }));
      if (nodes.length === 0) return null;
      return { nodes, edges, source: 'instance' as const };
    } catch {
      return null;
    }
  }, [spaceId]);

  const loadGraphData = useCallback(async () => {
    if (!spaceId) return;
    setGraphLoading(true);
    try {
      const [memData, instData] = await Promise.allSettled([
        fetchMemoryGraph(),
        fetchInstanceGraph(),
      ]);
      const memResult = memData.status === 'fulfilled' ? memData.value : null;
      const instResult = instData.status === 'fulfilled' ? instData.value : null;

      let chosen = dataSource === 'memory' ? memResult : instResult;
      if (!chosen) {
        chosen = memResult || instResult;
        if (chosen) setDataSource(chosen.source);
      }

      if (chosen) {
        setGraphNodes(chosen.nodes);
        setGraphEdges(chosen.edges);
      } else {
        setGraphNodes([]);
        setGraphEdges([]);
      }
    } catch (e: any) {
      message.error('加载图数据失败: ' + (e.message || '未知错误'));
    } finally {
      setGraphLoading(false);
    }
  }, [spaceId, dataSource, fetchMemoryGraph, fetchInstanceGraph]);

  useEffect(() => { loadGraphData(); }, [loadGraphData]);

  const handleSearch = useCallback(async () => {
    if (!spaceId || !query.trim()) return;
    setLoading(true);
    try {
      const response = await memoryApi.recall(spaceId, {
        query: query.trim(),
        maxResults: 20,
        includeEvidence: true,
        evidenceDepth: 2,
        minConfidence: 0.3,
      });
      const rawResults = (response as any).results || (response as any).data?.results || [];
      // transformNode converts 'text' → 'content', but RecallResult uses 'text'
      const resData: RecallResult[] = rawResults.map((r: any) => ({
        ...r,
        text: r.text || r.content || '',
        cognitiveLayer: r.cognitiveLayer || r.cognitive_layer,
        beliefStatus: r.beliefStatus || r.belief_status,
        memoryType: r.memoryType || r.memory_type,
      }));
      const qType = (response as any).queryType || (response as any).query_type || 'factual';
      setResults(resData);
      setQueryType(qType);

      const ids = new Set<string>();
      resData.forEach((r: any) => {
        ids.add(r.id);
        if (r.evidence) r.evidence.forEach((e: any) => ids.add(e.id));
      });
      setHighlightIds(ids);

      if (graphNodes.length === 0) {
        await loadGraphData();
      }
    } catch (e: any) {
      message.error('检索失败: ' + (e.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, [spaceId, query, graphNodes.length, loadGraphData]);

  const handleNodeClick = useCallback((nodeId: string, data: RecallResult) => {
    setSelectedNodeId(nodeId);
    setDrawerData(data);
    setDrawerVisible(true);
  }, []);

  const handleLocateInGraph = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    const node = graphNodes.find((n) => n.id === nodeId) || results.find((r) => r.id === nodeId);
    if (node) {
      setDrawerData(node);
      setDrawerVisible(true);
    }
  }, [graphNodes, results]);

  const handleLoadDemo = useCallback(async () => {
    if (!spaceId) return;
    setGraphLoading(true);
    try {
      const demoItems: Array<{ content: string; memoryType: string; confidence: number; tags: string[] }> = [
        { content: 'TechNova公司总部位于深圳南山区', memoryType: 'entity', confidence: 0.95, tags: ['company'] },
        { content: 'TechNova成立于2020年，是一家专注于AI的科技公司', memoryType: 'observation', confidence: 0.9, tags: ['company'] },
        { content: '王芳是TechNova技术负责人，拥有10年架构经验', memoryType: 'entity', confidence: 0.85, tags: ['person'] },
        { content: '王芳主导架构迁移到CloudGroup平台', memoryType: 'observation', confidence: 0.8, tags: ['architecture'] },
        { content: 'CloudGroup平台底层使用Kubernetes编排容器化服务', memoryType: 'observation', confidence: 0.85, tags: ['infrastructure'] },
        { content: 'TechNova架构变更须经安全委员会审批', memoryType: 'rule', confidence: 0.9, tags: ['governance'] },
        { content: '如果API错误率超过1%则触发告警通知运维团队', memoryType: 'constraint', confidence: 0.9, tags: ['operations'] },
        { content: 'TechNova的核心业务系统采用微服务架构', memoryType: 'mental_model', confidence: 0.75, tags: ['architecture'] },
        { content: '张明是TechNova的CEO，曾在Google工作8年', memoryType: 'entity', confidence: 0.9, tags: ['person'] },
        { content: 'TechNova 2024年营收达到5亿元，同比增长30%', memoryType: 'observation', confidence: 0.85, tags: ['finance'] },
        { content: '供应商准入规则：信用评分>=70且无重大违约记录', memoryType: 'rule', confidence: 0.95, tags: ['supply_chain'] },
        { content: 'TechNova采用GitFlow分支管理策略', memoryType: 'procedure', confidence: 0.8, tags: ['engineering'] },
      ];
      for (const item of demoItems) {
        await memoryApi.remember(spaceId, item.content, item.memoryType, {
          confidence: item.confidence,
          tags: item.tags,
        });
      }
      await memoryApi.consolidate(spaceId);
      message.success('示例数据加载成功');
      const result = await fetchMemoryGraph();
      if (result) {
        setGraphNodes(result.nodes);
        setGraphEdges(result.edges);
        setDataSource('memory');
      }
    } catch (e: any) {
      message.error('加载示例数据失败: ' + (e.message || '未知错误'));
    } finally {
      setGraphLoading(false);
    }
  }, [spaceId, fetchMemoryGraph]);

  const getStepFilteredData = useCallback((step: number, stepResults: RecallResult[]) => {
    if (step === -1 || stepResults.length === 0) {
      return { highlightIds: null as Set<string> | null, filteredResults: null as RecallResult[] | null };
    }

    let stepHighlightIds: Set<string>;
    let filteredResults: RecallResult[];

    switch (step) {
      case 0: // 查询理解 - all results
        stepHighlightIds = new Set(stepResults.map(r => r.id));
        filteredResults = stepResults;
        break;
      case 1: { // 多路检索 - all results, grouped by source in panel
        stepHighlightIds = new Set(stepResults.map(r => r.id));
        filteredResults = stepResults;
        break;
      }
      case 2: { // 融合排序 - all results sorted by rankScore (ranking doesn't reduce count)
        const sorted = [...stepResults].sort((a, b) => (b.rankScore || b.score || 0) - (a.rankScore || a.score || 0));
        stepHighlightIds = new Set(sorted.map(r => r.id));
        filteredResults = sorted;
        break;
      }
      case 3: { // 过滤筛选 - subset: accepted + confidence >= 0.5
        const sorted = [...stepResults].sort((a, b) => (b.rankScore || b.score || 0) - (a.rankScore || a.score || 0));
        const filtered = sorted.filter(r => r.beliefStatus === 'accepted' && (r.confidence || 0) >= 0.5);
        stepHighlightIds = new Set(filtered.map(r => r.id));
        filteredResults = filtered;
        break;
      }
      case 4: { // 证据展开 - only results with evidence + their evidence nodes
        stepHighlightIds = new Set<string>();
        const sorted = [...stepResults].sort((a, b) => (b.rankScore || b.score || 0) - (a.rankScore || a.score || 0));
        const withEvidence = sorted.filter(r => r.evidence && r.evidence.length > 0);
        withEvidence.forEach(r => {
          stepHighlightIds.add(r.id);
          r.evidence?.forEach(e => stepHighlightIds.add(e.id));
        });
        filteredResults = withEvidence;
        break;
      }
      default:
        stepHighlightIds = new Set();
        filteredResults = [];
    }

    return { highlightIds: stepHighlightIds, filteredResults };
  }, []);

  const stepFilteredData = getStepFilteredData(activeStep, results);
  const effectiveHighlightIds = stepFilteredData.highlightIds || highlightIds;

  return (
    <div style={{ padding: 16, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 12 }}>
        <Title level={4} style={{ margin: 0 }}>知识探索器</Title>
        <Text type="secondary">检索知识图谱，追踪溯源路径，探索证据链</Text>
      </div>

      <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <Input.Search
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onSearch={handleSearch}
          placeholder="输入查询，探索知识图谱..."
          enterButton={<><SearchOutlined /> 检索</>}
          size="large"
          style={{ flex: 1 }}
          loading={loading}
        />
        <Segmented
          value={dataSource}
          onChange={(v) => { setDataSource(v as DataSource); setGraphNodes([]); setGraphEdges([]); }}
          options={[
            { label: <><BulbOutlined /> 认知记忆</>, value: 'memory' },
            { label: <><ApartmentOutlined /> 实例图谱</>, value: 'instance' },
          ]}
        />
        {dataSource === 'memory' && (
          <>
            <Select
              placeholder="认知层"
              value={filterLayer}
              onChange={setFilterLayer}
              allowClear
              style={{ width: 120 }}
              options={[
                { label: 'opinion', value: 'opinion' },
                { label: 'semantic', value: 'semantic' },
                { label: 'procedure', value: 'procedure' },
                { label: 'perception', value: 'perception' },
              ]}
            />
            <Select
              placeholder="记忆类型"
              value={filterType}
              onChange={setFilterType}
              allowClear
              style={{ width: 120 }}
              options={[
                { label: 'entity', value: 'entity' },
                { label: 'observation', value: 'observation' },
                { label: 'fragment', value: 'fragment' },
                { label: 'rule', value: 'rule' },
                { label: 'mental_model', value: 'mental_model' },
                { label: 'opinion', value: 'opinion' },
                { label: 'procedure', value: 'procedure' },
                { label: 'constraint', value: 'constraint' },
              ]}
            />
          </>
        )}
        <Button icon={<ReloadOutlined />} onClick={loadGraphData} loading={graphLoading}>刷新</Button>
        {dataSource === 'memory' && (
          <Button icon={<DatabaseOutlined />} onClick={handleLoadDemo} loading={graphLoading}>加载示例数据</Button>
        )}
      </div>

      <Row gutter={12} style={{ flex: 1, minHeight: 0 }}>
        <Col span={16} style={{ height: '100%' }}>
          <Card styles={{ body: { padding: 0, height: '100%' } }} style={{ height: '100%' }}>
            {graphLoading && graphNodes.length === 0 ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><Spin size="large"><div style={{padding: 50, textAlign: 'center'}}>加载图数据...</div></Spin></div>
            ) : graphNodes.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 16 }}>
                <Empty description={dataSource === 'memory' ? '当前空间暂无认知记忆数据' : '当前空间暂无实例图谱数据'} />
                {dataSource === 'memory' && (
                  <Button type="primary" icon={<DatabaseOutlined />} onClick={handleLoadDemo}>加载示例数据</Button>
                )}
                <Alert
                  type="info"
                  showIcon
                  message={dataSource === 'memory' ? '尝试切换到「实例图谱」查看 Schema 实例数据' : '尝试切换到「认知记忆」查看 Agent 记忆数据'}
                  style={{ maxWidth: 400 }}
                />
              </div>
            ) : (
              <MemoryTraceGraph
                nodes={graphNodes}
                edges={graphEdges}
                highlightNodeIds={effectiveHighlightIds}
                height={560}
                onNodeClick={handleNodeClick}
              />
            )}
          </Card>
        </Col>
        <Col span={8} style={{ height: '100%', overflow: 'auto' }}>
          {results.length > 0 ? (
            <RetrievalTracePanel
              query={query}
              queryType={queryType}
              results={results}
              totalResults={results.length}
              selectedNodeId={selectedNodeId}
              onResultClick={handleLocateInGraph}
              activeStep={activeStep}
              onStepChange={setActiveStep}
              filteredResults={stepFilteredData.filteredResults}
            />
          ) : (
            <Card>
              <Empty description="输入查询开始检索" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              <Divider style={{ margin: '12px 0' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                知识探索器支持：语义检索、多跳推理、时序查询、证据链溯源。
                检索结果将在此面板分层展示，同时高亮图中的相关节点。
              </Text>
            </Card>
          )}
        </Col>
      </Row>

      <Drawer
        title="节点详情"
        placement="right"
        width={420}
        open={drawerVisible}
        onClose={() => { setDrawerVisible(false); setSelectedNodeId(null); }}
      >
        {drawerData && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Paragraph>{drawerData.text || drawerData.id}</Paragraph>
            <Space wrap>
              <Tag color={MEMORY_TYPE_COLORS[drawerData.memoryType || '']}>{drawerData.memoryType}</Tag>
              <Tag color={COGNITIVE_LAYER_COLORS[drawerData.cognitiveLayer || '']}>{drawerData.cognitiveLayer}</Tag>
              <Tag>{drawerData.beliefStatus}</Tag>
            </Space>
            <div>
              <Text type="secondary">置信度: </Text>
              <Text>{drawerData.confidence?.toFixed(2) || '-'}</Text>
            </div>
            {drawerData.score != null && (
              <div>
                <Text type="secondary">检索分数: </Text>
                <Text>{drawerData.score.toFixed(3)}</Text>
              </div>
            )}
            {drawerData.rankScore != null && (
              <div>
                <Text type="secondary">排名分数: </Text>
                <Text>{drawerData.rankScore.toFixed(3)}</Text>
              </div>
            )}
            {drawerData.strengthBreakdown && (
              <div>
                <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>记忆强度分解</Text>
                {Object.entries(drawerData.strengthBreakdown).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                    <Text type="secondary">{k}</Text>
                    <Text>{(v as number).toFixed(2)}</Text>
                  </div>
                ))}
              </div>
            )}
            {drawerData.evidence && drawerData.evidence.length > 0 && (
              <div>
                <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>证据链 ({drawerData.evidence.length})</Text>
                {drawerData.evidence.map((ev, i) => (
                  <Card key={i} size="small" style={{ marginBottom: 4 }}>
                    <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, fontSize: 12 }}>{ev.text || ev.id}</Paragraph>
                    <Space size={4} style={{ marginTop: 4 }}>
                      <Tag style={{ fontSize: 10 }}>{ev.edgeType}</Tag>
                      <Text type="secondary" style={{ fontSize: 10 }}>贡献: {ev.contribution?.toFixed(2) || '-'}</Text>
                    </Space>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default KnowledgeExplorerPage;
