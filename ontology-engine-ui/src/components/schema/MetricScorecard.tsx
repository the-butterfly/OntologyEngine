import { Card, Statistic, Tag, Progress, Divider, Typography, Row, Col } from 'antd';
import { METRIC_TYPE_COLORS } from '../../utils/colorSchemes';
import { METRIC_LABELS, CREDIT_SCORE_WEIGHTS } from '../../utils/labelMappings';
import type { GraphNode } from '../../types/visualization';

const { Text, Paragraph } = Typography;

interface MetricScorecardProps {
  node: GraphNode;
}

// Simple radar chart using CSS
function SimpleRadarChart({ values, weights }: { values: Record<string, number>; weights: Record<string, number> }) {
  const entries = Object.entries(weights);
  const count = entries.length;
  const size = 160;
  const center = size / 2;
  const radius = size * 0.35;
  
  const getPoint = (index: number, value: number) => {
    const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
    const r = radius * (value / 100);
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  const points = entries.map(([key, weight], index) => {
    const value = values[key] || 0;
    return getPoint(index, value);
  });

  const pathData = points.length > 0 
    ? `M ${points.map(p => `${p.x},${p.y}`).join(' L ')} Z`
    : '';

  const labelPoints = entries.map(([,], index) => getPoint(index, 120));

  return (
    <svg width={size} height={size} style={{ margin: '0 auto', display: 'block' }}>
      {/* Background grid */}
      {[0.2, 0.4, 0.6, 0.8, 1].map((ratio, i) => (
        <polygon
          key={i}
          points={entries.map((_, idx) => {
            const p = getPoint(idx, ratio * 100);
            return `${p.x},${p.y}`;
          }).join(' ')}
          fill="none"
          stroke="#e8e8e8"
          strokeWidth={1}
        />
      ))}
      
      {/* Axes */}
      {entries.map((_, index) => {
        const end = getPoint(index, 100);
        return (
          <line
            key={index}
            x1={center}
            y1={center}
            x2={end.x}
            y2={end.y}
            stroke="#e8e8e8"
            strokeWidth={1}
          />
        );
      })}
      
      {/* Data polygon */}
      {pathData && (
        <path
          d={pathData}
          fill="rgba(114, 46, 209, 0.2)"
          stroke="#722ED1"
          strokeWidth={2}
        />
      )}
      
      {/* Data points */}
      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#722ED1" />
      ))}
      
      {/* Labels */}
      {entries.map(([key], index) => {
        const p = labelPoints[index];
        const label = METRIC_LABELS[key]?.slice(0, 4) || key.slice(0, 4);
        return (
          <text
            key={key}
            x={p.x}
            y={p.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={10}
            fill="#666"
          >
            {label}
          </text>
        );
      })}
    </svg>
  );
}

export default function MetricScorecard({ node }: MetricScorecardProps) {
  const { data } = node;
  const weightMap = data.weight_map || {};
  const isCreditScore = node.id === 'credit_score';
  
  // Get weights from CREDIT_SCORE_WEIGHTS or from node data
  const weights = isCreditScore ? CREDIT_SCORE_WEIGHTS : weightMap;
  const hasWeights = Object.keys(weights).length > 0;
  
  // Mock values for radar chart (in real app, fetch from entity data)
  const mockValues: Record<string, number> = {
    business_stability_score: 85,
    tax_compliance_score: 90,
    network_centrality_score: 60,
    reputation_score: 95,
    guarantee_chain_depth: 70,
  };

  const metricType = data.metric_type || 'atomic';
  const typeColor = METRIC_TYPE_COLORS[metricType]?.stroke || '#999';
  const typeLabel = METRIC_TYPE_COLORS[metricType]?.label || metricType;

  return (
    <div style={{ padding: 4 }}>
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <Tag color={typeColor} style={{ marginBottom: 8 }}>{typeLabel}</Tag>
        <h3 style={{ margin: '8px 0', fontSize: 18, fontWeight: 600 }}>
          {data.label || METRIC_LABELS[node.id] || node.id}
        </h3>
        {isCreditScore && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 12 }}>
            <Statistic 
              title="评分" 
              value={92} 
              suffix="/ 100" 
              valueStyle={{ color: '#722ED1', fontWeight: 600 }}
            />
            <Statistic 
              title="等级" 
              value="AA" 
              valueStyle={{ color: '#52C41A', fontWeight: 600 }}
            />
          </div>
        )}
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {/* Description */}
      {data.description && (
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          {data.description}
        </Paragraph>
      )}

      {/* Formula */}
      {data.formula && (
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>计算公式</Text>
          <div style={{ 
            background: '#f6f0ff', 
            padding: '8px 12px', 
            borderRadius: 6,
            marginTop: 4,
            fontFamily: 'monospace',
            fontSize: 12,
            color: '#531dab',
            overflow: 'auto',
            maxHeight: 80,
          }}>
            {data.formula}
          </div>
        </div>
      )}

      {/* Dependencies */}
      {data.dependencies?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
            依赖指标 ({data.dependencies.length})
          </Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.dependencies.map((dep: string) => (
              <Tag key={dep} size="small" style={{ fontSize: 11 }}>
                {METRIC_LABELS[dep] || dep}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {/* Weight Distribution - Only for composite metrics with weights */}
      {hasWeights && (
        <>
          <Divider style={{ margin: '16px 0' }} />
          <div>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              权重分布
            </Text>
            
            {/* Radar Chart for credit score */}
            {isCreditScore && (
              <Card size="small" style={{ marginBottom: 12, background: '#fafafa' }}>
                <SimpleRadarChart values={mockValues} weights={weights} />
              </Card>
            )}
            
            {/* Weight bars */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(weights).map(([key, weight]) => {
                const percent = (weight * 100).toFixed(0);
                const value = mockValues[key] || 0;
                return (
                  <div key={key}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 12 }}>{METRIC_LABELS[key] || key}</Text>
                      <Text strong style={{ fontSize: 12, color: '#722ED1' }}>{percent}%</Text>
                    </div>
                    <Progress 
                      percent={value} 
                      size="small" 
                      strokeColor="#722ED1"
                      trailColor="#f0f0f0"
                      format={() => <span style={{ fontSize: 11 }}>{value}</span>}
                    />
                  </div>
                );
              })}
            </div>
            
            {/* Formula breakdown */}
            {isCreditScore && (
              <div style={{ 
                marginTop: 12,
                padding: 10,
                background: '#f9f0ff',
                borderRadius: 6,
                fontSize: 11,
                fontFamily: 'monospace',
                color: '#531dab',
                lineHeight: 1.6,
              }}>
                <div style={{ marginBottom: 4, fontWeight: 600 }}>计算过程:</div>
                {Object.entries(weights).map(([key, weight]) => (
                  <div key={key}>
                    {(weight * 100).toFixed(0)}% × {mockValues[key] || 0} = {((weight * 100) * (mockValues[key] || 0) / 100).toFixed(2)}
                  </div>
                ))}
                <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px dashed #d3adf7', fontWeight: 600 }}>
                  合计: 81.75
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
