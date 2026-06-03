import React, { useState } from 'react';
import { Steps, Tag, Typography, Space, Collapse, Badge } from 'antd';
import {
  SearchOutlined,
  DatabaseOutlined,
  ForkOutlined,
  FilterOutlined,
  SortAscendingOutlined,
} from '@ant-design/icons';

const { Text, Paragraph } = Typography;

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
}

interface RetrievalTracePanelProps {
  query: string;
  queryType?: string;
  results: RecallResult[];
  totalResults?: number;
  selectedNodeId?: string | null;
  onResultClick?: (nodeId: string) => void;
  activeStep?: number;
  onStepChange?: (step: number) => void;
  filteredResults?: RecallResult[] | null;
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  layer_r: { label: 'Layer-R 向量', color: '#1890ff' },
  layer_s: { label: 'Layer-S 图', color: '#52c41a' },
  bm25: { label: 'BM25 关键词', color: '#faad14' },
  temporal: { label: '时序', color: '#722ed1' },
  unknown: { label: '未知', color: '#8c8c8c' },
};

const RetrievalTracePanel: React.FC<RetrievalTracePanelProps> = ({
  query,
  queryType,
  results,
  totalResults,
  selectedNodeId,
  onResultClick,
  activeStep: activeStepProp,
  onStepChange,
  filteredResults,
}) => {
  const [localActiveStep, setLocalActiveStep] = useState(-1);
  const activeStep = activeStepProp ?? localActiveStep;
  const displayResults = filteredResults || results;

  const sourceCounts: Record<string, number> = {};
  results.forEach((r) => {
    const src = r.source || 'unknown';
    sourceCounts[src] = (sourceCounts[src] || 0) + 1;
  });

  const resultsWithEvidence = results.filter((r) => r.evidence && r.evidence.length > 0);
  const totalEvidence = resultsWithEvidence.reduce((sum, r) => sum + (r.evidence?.length || 0), 0);
  const avgScore = results.length > 0 ? results.reduce((s, r) => s + (r.score || 0), 0) / results.length : 0;
  const typeWeights = results.filter((r) => r.typeWeight != null);
  const hasTemporal = results.some((r) => r.temporalProximity != null);
  const beliefCounts: Record<string, number> = {};
  results.forEach((r) => {
    const bs = r.beliefStatus || 'unknown';
    beliefCounts[bs] = (beliefCounts[bs] || 0) + 1;
  });

  const steps = [
    {
      title: '查询理解',
      icon: <SearchOutlined />,
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
          <div><Text type="secondary">查询文本: </Text><Text strong>{query}</Text></div>
          <div><Text type="secondary">识别类型: </Text><Tag color="blue">{queryType || 'factual'}</Tag></div>
          <div><Text type="secondary">结果数量: </Text><Text>{results.length} 条</Text></div>
        </div>
      ),
    },
    {
      title: '多路检索',
      icon: <DatabaseOutlined />,
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
          <Text type="secondary" style={{ marginBottom: 4 }}>各路检索来源命中数:</Text>
          <Space wrap>
            {Object.entries(sourceCounts).map(([src, count]) => (
              <Tag key={src} color={SOURCE_LABELS[src]?.color}>
                {SOURCE_LABELS[src]?.label || src}: {count}
              </Tag>
            ))}
          </Space>
          {Object.keys(sourceCounts).length === 0 && <Text type="secondary">无来源信息</Text>}
        </div>
      ),
    },
    {
      title: '融合排序',
      icon: <ForkOutlined />,
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
          <div><Text type="secondary">平均检索分: </Text><Text>{avgScore.toFixed(3)}</Text></div>
          {typeWeights.length > 0 && (
            <div><Text type="secondary">类型权重范围: </Text><Text>{Math.min(...typeWeights.map(r => r.typeWeight!)).toFixed(1)} ~ {Math.max(...typeWeights.map(r => r.typeWeight!)).toFixed(1)}</Text></div>
          )}
          {hasTemporal && (
            <div><Text type="secondary">时序邻近度: </Text><Text>已计算</Text></div>
          )}
          <div style={{ marginTop: 4 }}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>Top-3 排名:</Text>
            {[...results].sort((a, b) => (b.rankScore || b.score || 0) - (a.rankScore || a.score || 0)).slice(0, 3).map((r, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 4 }}>
                <Badge count={i + 1} style={{ backgroundColor: '#1890ff' }} size="small" />
                <Text ellipsis style={{ flex: 1, maxWidth: 160 }}>{r.text || r.id}</Text>
                <Text type="secondary">{(r.rankScore || r.score || 0).toFixed(3)}</Text>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: '过滤筛选',
      icon: <FilterOutlined />,
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
          <Text type="secondary" style={{ marginBottom: 4 }}>信念状态分布:</Text>
          <Space wrap>
            {Object.entries(beliefCounts).map(([bs, count]) => (
              <Tag key={bs} color={bs === 'accepted' ? 'green' : bs === 'superseded' ? 'default' : 'orange'}>{bs}: {count}</Tag>
            ))}
          </Space>
          <div style={{ marginTop: 4 }}>
            <Text type="secondary">置信度范围: </Text>
            <Text>{results.length > 0 ? Math.min(...results.map(r => r.confidence || 1)).toFixed(2) : '-'} ~ {results.length > 0 ? Math.max(...results.map(r => r.confidence || 0)).toFixed(2) : '-'}</Text>
          </div>
        </div>
      ),
    },
    {
      title: '证据展开',
      icon: <SortAscendingOutlined />,
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
          <div><Text type="secondary">含证据链结果: </Text><Text>{resultsWithEvidence.length} / {results.length}</Text></div>
          <div><Text type="secondary">证据边总数: </Text><Text>{totalEvidence}</Text></div>
          {resultsWithEvidence.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>证据类型分布:</Text>
              <Space wrap>
                {Object.entries(
                  resultsWithEvidence.reduce((acc, r) => {
                    r.evidence?.forEach((e) => {
                      acc[e.edgeType || 'unknown'] = (acc[e.edgeType || 'unknown'] || 0) + 1;
                    });
                    return acc;
                  }, {} as Record<string, number>)
                ).map(([et, count]) => (
                  <Tag key={et}>{et}: {count}</Tag>
                ))}
              </Space>
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <Text type="secondary">查询: </Text>
        <Text strong>{query}</Text>
        {queryType && <Tag color="blue" style={{ marginLeft: 8 }}>{queryType}</Tag>}
      </div>

      <Steps
        size="small"
        direction="vertical"
        current={activeStep}
        onChange={(current) => {
          const newStep = activeStep === current ? -1 : current;
          if (onStepChange) {
            onStepChange(newStep);
          } else {
            setLocalActiveStep(newStep);
          }
        }}
        items={steps.map((step, idx) => ({
          title: (
            <span style={{ cursor: 'pointer' }}>{step.title}</span>
          ),
          icon: <span style={{ cursor: 'pointer' }}>{step.icon}</span>,
          description: activeStep === idx ? step.content : undefined,
        }))}
      />

      <div>
        <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>结果列表 ({displayResults.length})</Text>
        <Collapse
          size="small"
          items={displayResults.slice(0, 20).map((r, idx) => ({
            key: r.id,
            label: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text type="secondary">#{idx + 1}</Text>
                <Text ellipsis style={{ maxWidth: 180 }}>{r.text || r.id}</Text>
                {r.source && <Tag color={SOURCE_LABELS[r.source]?.color} style={{ marginLeft: 'auto', fontSize: 10 }}>{r.source}</Tag>}
                {r.score != null && <Text type="secondary" style={{ fontSize: 11 }}>{r.score.toFixed(3)}</Text>}
              </div>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Paragraph ellipsis={{ rows: 3, expandable: true }} style={{ margin: 0 }}>{r.text}</Paragraph>
                <Space size={4} wrap>
                  <Tag>{r.memoryType}</Tag>
                  <Tag>{r.cognitiveLayer}</Tag>
                  <Tag color={r.beliefStatus === 'accepted' ? 'green' : r.beliefStatus === 'superseded' ? 'default' : 'orange'}>{r.beliefStatus}</Tag>
                </Space>
                <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                  {r.confidence != null && <span>置信度: {r.confidence.toFixed(2)}</span>}
                  {r.rankScore != null && <span>排名分: {r.rankScore.toFixed(3)}</span>}
                  {r.typeWeight != null && <span>类型权重: {r.typeWeight}</span>}
                </div>
                {r.evidence && r.evidence.length > 0 && (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>证据链 ({r.evidence.length}):</Text>
                    <div style={{ marginTop: 4, paddingLeft: 8, borderLeft: '2px solid #1890ff' }}>
                      {r.evidence.map((ev, ei) => (
                        <div key={ei} style={{ fontSize: 12, marginBottom: 4 }}>
                          <Tag style={{ fontSize: 10 }}>{ev.edgeType}</Tag>
                          <Text ellipsis style={{ maxWidth: 200 }}>{ev.text || ev.id}</Text>
                          <Text type="secondary"> 贡献:{ev.contribution?.toFixed(2) || '-'}</Text>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <a onClick={() => onResultClick?.(r.id)} style={{ fontSize: 12 }}>在图中定位 →</a>
              </div>
            ),
            style: r.id === selectedNodeId ? { borderLeft: '3px solid #1890ff' } : undefined,
          }))}
        />
      </div>
    </div>
  );
};

export default RetrievalTracePanel;
