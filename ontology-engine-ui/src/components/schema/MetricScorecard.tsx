import { useEffect, useMemo, useState } from 'react';
import { Alert, Card, Divider, Empty, Progress, Skeleton, Statistic, Tag, Typography } from 'antd';
import { fetchMetricSnapshot, ApiError } from '../../api/visualization';
import { METRIC_TYPE_COLORS } from '../../utils/colorSchemes';
import { CREDIT_SCORE_WEIGHTS } from '../../utils/labelMappings';
import type { GraphNode, MetricSnapshot } from '../../types/visualization';

const { Text, Paragraph } = Typography;

interface MetricScorecardProps {
  node: GraphNode;
  entityId?: string | null;
  dimension?: string;
}

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

  const points = entries.map(([key], index) => getPoint(index, values[key] || 0));
  const pathData = points.length > 0 ? `M ${points.map(p => `${p.x},${p.y}`).join(' L ')} Z` : '';
  const labelPoints = entries.map(([,], index) => getPoint(index, 120));

  return (
    <svg width={size} height={size} style={{ margin: '0 auto', display: 'block' }}>
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

      {pathData && (
        <path
          d={pathData}
          fill="rgba(114, 46, 209, 0.2)"
          stroke="#722ED1"
          strokeWidth={2}
        />
      )}

      {points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#722ED1" />
      ))}

      {entries.map(([key], index) => {
        const p = labelPoints[index];
        const label = key.slice(0, 4);
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

function extractNumeric(value: any): number {
  if (typeof value === 'number') return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  if (value && typeof value === 'object' && 'value' in value) {
    return extractNumeric(value.value);
  }
  return 0;
}

function normalizeMetricValue(metricKey: string, value: any): number {
  const numeric = extractNumeric(value);
  if (metricKey === 'guarantee_chain_depth') {
    return Math.max(0, Math.min(100, 100 - numeric * 20));
  }
  if (metricKey.includes('ratio') || metricKey.includes('rate')) {
    return Math.max(0, Math.min(100, numeric <= 1 ? numeric * 100 : numeric));
  }
  return Math.max(0, Math.min(100, numeric));
}

function formatMetricValue(value: any): string {
  if (value === null || value === undefined) return '--';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  if (value && typeof value === 'object' && 'value' in value) {
    return formatMetricValue(value.value);
  }
  return String(value);
}

export default function MetricScorecard({
  node,
  entityId,
  dimension = 'credit_assessment',
}: MetricScorecardProps) {
  const { data } = node;
  const isCreditScore = node.id === 'credit_score';
  const weights: Record<string, number> = isCreditScore
    ? CREDIT_SCORE_WEIGHTS
    : ((data.weight_map as Record<string, number> | undefined) ?? {});
  const hasWeights = Object.keys(weights).length > 0;
  const metricType = data.metric_type || 'atomic';
  const typeColor = METRIC_TYPE_COLORS[metricType]?.stroke || '#999';
  const typeLabel = METRIC_TYPE_COLORS[metricType]?.label || metricType;

  const [snapshot, setSnapshot] = useState<MetricSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSnapshot() {
      if (!entityId) {
        setSnapshot(null);
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const result = await fetchMetricSnapshot(entityId, dimension);
        if (!cancelled) {
          setSnapshot(result);
        }
      } catch (e) {
        if (!cancelled) {
          const message = e instanceof ApiError ? e.message : 'Failed to load metrics';
          setError(message);
          setSnapshot(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSnapshot();
    return () => {
      cancelled = true;
    };
  }, [dimension, entityId]);

  const metricValue = snapshot ? (snapshot.metrics[node.id] ?? snapshot.outputs[node.id]) : undefined;
  const gradeValue = snapshot ? (snapshot.outputs.credit_grade ?? snapshot.metrics.credit_grade) : undefined;

  const radarValues = useMemo(() => {
    if (!snapshot) return {} as Record<string, number>;
    return Object.fromEntries(
      Object.keys(weights).map((key) => [key, normalizeMetricValue(key, snapshot.metrics[key] ?? snapshot.outputs[key])])
    );
  }, [snapshot, weights]);

  const weightedPreview = useMemo(() => {
    return (Object.entries(weights) as Array<[string, number]>).reduce(
      (sum, [key, weight]) => sum + ((radarValues[key] || 0) * weight),
      0,
    );
  }, [radarValues, weights]);

  return (
    <div style={{ padding: 4 }}>
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <Tag color={typeColor} style={{ marginBottom: 8 }}>{typeLabel}</Tag>
        <h3 style={{ margin: '8px 0', fontSize: 18, fontWeight: 600 }}>
          {data.label || node.id}
        </h3>
        {entityId && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            当前实体: {entityId}
          </Text>
        )}
        {isCreditScore && !loading && snapshot && (
          <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 12 }}>
            <Statistic
              title="评分"
              value={extractNumeric(metricValue)}
              suffix="/ 100"
              valueStyle={{ color: '#722ED1', fontWeight: 600 }}
            />
            <Statistic
              title="等级"
              value={gradeValue || '--'}
              valueStyle={{ color: '#52C41A', fontWeight: 600 }}
            />
          </div>
        )}
        {!isCreditScore && !loading && snapshot && metricValue !== undefined && (
          <div style={{ marginTop: 12 }}>
            <Statistic
              title="当前值"
              value={formatMetricValue(metricValue)}
              valueStyle={{ color: '#722ED1', fontWeight: 600 }}
            />
          </div>
        )}
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {data.description && (
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 12 }}>
          {data.description}
        </Paragraph>
      )}

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

      {data.dependencies?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
            依赖指标 ({data.dependencies.length})
          </Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.dependencies.map((dep: string) => (
              <Tag key={dep} style={{ fontSize: 11 }}>
                {dep}
              </Tag>
            ))}
          </div>
        </div>
      )}

      {loading && <Skeleton active paragraph={{ rows: 6 }} />}

      {!loading && error && (
        <Alert type="error" message="指标加载失败" description={error} showIcon style={{ marginBottom: 16 }} />
      )}

      {!loading && !error && !entityId && (
        <Empty description="请选择实体查看真实指标" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}

      {!loading && !error && entityId && !snapshot && (
        <Empty description="暂无指标数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}

      {!loading && !error && snapshot && hasWeights && (
        <>
          <Divider style={{ margin: '16px 0' }} />
          <div>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>
              权重分布
            </Text>

            {isCreditScore && (
              <Card size="small" style={{ marginBottom: 12, background: '#fafafa' }}>
                <SimpleRadarChart values={radarValues} weights={weights} />
              </Card>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(weights).map(([key, weight]) => {
                const percent = (weight * 100).toFixed(0);
                const value = radarValues[key] || 0;
                const rawValue = snapshot.metrics[key] ?? snapshot.outputs[key];
                return (
                  <div key={key}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 12 }}>{key}</Text>
                      <Text strong style={{ fontSize: 12, color: '#722ED1' }}>{percent}%</Text>
                    </div>
                    <Progress
                      percent={value}
                      size="small"
                      strokeColor="#722ED1"
                      trailColor="#f0f0f0"
                      format={() => <span style={{ fontSize: 11 }}>{formatMetricValue(rawValue)}</span>}
                    />
                  </div>
                );
              })}
            </div>

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
                <div style={{ marginBottom: 4, fontWeight: 600 }}>权重贡献（展示归一化）:</div>
                {(Object.entries(weights) as Array<[string, number]>).map(([key, weight]) => (
                  <div key={key}>
                    {(weight * 100).toFixed(0)}% × {(radarValues[key] || 0).toFixed(1)} = {((radarValues[key] || 0) * weight).toFixed(2)}
                  </div>
                ))}
                <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px dashed #d3adf7', fontWeight: 600 }}>
                  展示合计: {weightedPreview.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
