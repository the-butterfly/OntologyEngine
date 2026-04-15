import { Card, Descriptions, Tag, Space, Typography, Divider, Badge } from 'antd';
import { 
  DatabaseOutlined, 
  CalculatorOutlined, 
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import { METRIC_TYPE_COLORS, RULE_TYPE_COLORS } from '../../utils/colorSchemes';
import { CONCEPT_LABELS, METRIC_LABELS } from '../../utils/labelMappings';
import type { GraphNode } from '../../types/visualization';

const { Text, Paragraph } = Typography;

interface NodeDetailPanelProps {
  node: GraphNode;
  onMetricClick?: (metricId: string) => void;
}

export default function NodeDetailPanel({ node, onMetricClick }: NodeDetailPanelProps) {
  const { type, data, id } = node;

  // Entity Node Detail
  if (type === 'entity') {
    return (
      <div style={{ padding: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <DatabaseOutlined style={{ fontSize: 20, color: '#1890FF' }} />
          <div>
            <h4 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{data.label || CONCEPT_LABELS[id] || id}</h4>
            <Text type="secondary" style={{ fontSize: 11 }}>L1 实体定义</Text>
          </div>
        </div>

        <Card size="small" style={{ marginBottom: 12 }}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="实体ID">
              <code style={{ fontSize: 11 }}>{id}</code>
            </Descriptions.Item>
            <Descriptions.Item label="属性数量">
              <Badge count={data.attribute_count || 0} style={{ backgroundColor: '#1890FF' }} />
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {data.description && (
          <Card size="small" title="描述" style={{ marginBottom: 12 }}>
            <Paragraph style={{ fontSize: 12, margin: 0 }}>{data.description}</Paragraph>
          </Card>
        )}

        {data.key_attributes?.length > 0 && (
          <Card size="small" title="关键属性" style={{ marginBottom: 12 }}>
            <Space wrap>
              {data.key_attributes.map((attr: string) => (
                <Tag key={attr} color="blue" style={{ fontSize: 11 }}>{attr}</Tag>
              ))}
            </Space>
          </Card>
        )}

        {data.properties?.length > 0 && (
          <Card
            size="small"
            title={`属性定义 (${data.properties.length})`}
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px' } }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {data.properties.map((prop: any) => (
                <div
                  key={prop.name}
                  style={{
                    padding: '6px 8px',
                    background: '#fafafa',
                    borderRadius: 4,
                    borderLeft: prop.required ? '3px solid #ff4d4f' : '3px solid #d9d9d9',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <Text strong style={{ fontSize: 12 }}>{prop.name}</Text>
                    <Tag color={prop.required ? 'red' : 'default'} style={{ fontSize: 9, margin: 0, padding: '0 2px' }}>
                      {prop.type}
                    </Tag>
                    {prop.unique && <Tag color="purple" style={{ fontSize: 9, margin: 0, padding: '0 2px' }}>唯一</Tag>}
                  </div>
                  {prop.description && (
                    <Text type="secondary" style={{ fontSize: 11 }}>{prop.description}</Text>
                  )}
                  {prop.enum && (
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 10 }}>枚举值: </Text>
                      {prop.enum.map((v: string) => (
                        <Tag key={v} style={{ fontSize: 9 }}>{v}</Tag>
                      ))}
                    </div>
                  )}
                  {prop.validation?.pattern && (
                    <Text type="secondary" style={{ fontSize: 10, fontFamily: 'monospace' }}>
                      正则: {prop.validation.pattern}
                    </Text>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    );
  }

  // Category Node Detail
  if (type === 'category') {
    return (
      <div style={{ padding: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <DatabaseOutlined style={{ fontSize: 20, color: '#722ED1' }} />
          <div>
            <h4 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{data.label || id}</h4>
            <Text type="secondary" style={{ fontSize: 11 }}>L2 分类体系</Text>
          </div>
        </div>

        <Card size="small" style={{ marginBottom: 12 }}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="分类ID">
              <code style={{ fontSize: 11 }}>{id}</code>
            </Descriptions.Item>
            {data.taxonomy_type && (
              <Descriptions.Item label="分类类型">
                <Tag color="purple" style={{ fontSize: 11 }}>{data.taxonomy_type}</Tag>
              </Descriptions.Item>
            )}
            {data.classification_count != null && (
              <Descriptions.Item label="分类数量">
                <Badge count={data.classification_count} style={{ backgroundColor: '#722ED1' }} />
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>

        {data.description && (
          <Card size="small" title="描述" style={{ marginBottom: 12 }}>
            <Paragraph style={{ fontSize: 12, margin: 0 }}>{data.description}</Paragraph>
          </Card>
        )}

        {data.classifications?.length > 0 && (
          <Card
            size="small"
            title={`分类项 (${data.classifications.length})`}
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px' } }}
          >
            <Space wrap>
              {data.classifications.map((item: string) => (
                <Tag key={item} color="purple" style={{ fontSize: 11 }}>{item}</Tag>
              ))}
            </Space>
          </Card>
        )}
      </div>
    );
  }

  // Metric Node Detail
  if (type === 'metric') {
    const weightMap = data.weight_map || {};
    const hasWeights = Object.keys(weightMap).length > 0;
    const metricType = data.metric_type || 'atomic';
    const typeColor = METRIC_TYPE_COLORS[metricType];

    return (
      <div style={{ padding: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <CalculatorOutlined style={{ fontSize: 20, color: typeColor?.stroke || '#999' }} />
          <div>
            <h4 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{data.label || METRIC_LABELS[id] || id}</h4>
            <Space size={4}>
              <Tag color={typeColor?.stroke} style={{ fontSize: 10, padding: '0 4px' }}>
                {typeColor?.label || metricType}
              </Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>L3 指标</Text>
            </Space>
          </div>
        </div>

        {data.description && (
          <Card size="small" style={{ marginBottom: 12 }}>
            <Paragraph style={{ fontSize: 12, margin: 0 }}>{data.description}</Paragraph>
          </Card>
        )}

        {data.formula && (
          <Card 
            size="small" 
            title="计算公式" 
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px' } }}
          >
            <div style={{ 
              background: '#f6ffed', 
              padding: '8px 12px', 
              borderRadius: 6,
              fontFamily: 'monospace',
              fontSize: 11,
              color: '#389e0d',
              overflow: 'auto',
              maxHeight: 100,
            }}>
              {data.formula}
            </div>
          </Card>
        )}

        {data.dependencies?.length > 0 && (
          <Card 
            size="small" 
            title={`依赖指标 (${data.dependencies.length})`}
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px' } }}
          >
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              {data.dependencies.map((dep: string) => (
                <div 
                  key={dep}
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '4px 8px',
                    background: '#fafafa',
                    borderRadius: 4,
                  }}
                >
                  <Text style={{ fontSize: 12 }}>{METRIC_LABELS[dep] || dep}</Text>
                  {weightMap[dep] != null && (
                    <Tag color="purple" style={{ fontSize: 10, margin: 0 }}>
                      {(weightMap[dep] * 100).toFixed(0)}%
                    </Tag>
                  )}
                </div>
              ))}
            </Space>
          </Card>
        )}

        {hasWeights && (
          <Card 
            size="small" 
            title="权重分布" 
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px' } }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(Object.entries(weightMap as Record<string, number>) as Array<[string, number]>).map(([key, weight]) => (
                <div key={key}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <Text style={{ fontSize: 11 }}>{METRIC_LABELS[key] || key}</Text>
                    <Text strong style={{ fontSize: 11, color: '#722ED1' }}>
                      {(weight * 100).toFixed(0)}%
                    </Text>
                  </div>
                  <div style={{ 
                    height: 6, 
                    background: '#f0f0f0', 
                    borderRadius: 3,
                    overflow: 'hidden'
                  }}>
                    <div style={{ 
                      width: `${weight * 100 / 0.30}%`, 
                      height: '100%', 
                      background: '#722ED1',
                      borderRadius: 3,
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    );
  }

  // Rule Node Detail
  if (type === 'rule') {
    const ruleColor = RULE_TYPE_COLORS[data.rule_type];

    return (
      <div style={{ padding: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <SafetyCertificateOutlined style={{ fontSize: 20, color: ruleColor?.stroke || '#999' }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <h4 style={{ margin: 0, fontSize: 15, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {data.label || id}
            </h4>
            <Space size={4} wrap>
              <Tag color={ruleColor?.stroke} style={{ fontSize: 10, padding: '0 4px' }}>
                {ruleColor?.label || data.rule_type}
              </Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>L4 规则</Text>
            </Space>
          </div>
        </div>

        <Card size="small" style={{ marginBottom: 12 }}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="规则ID">
              <code style={{ fontSize: 10 }}>{id}</code>
            </Descriptions.Item>
            <Descriptions.Item label="优先级">
              <Badge 
                count={data.priority || 0} 
                style={{ backgroundColor: data.priority >= 90 ? '#f5222d' : data.priority >= 50 ? '#fa8c16' : '#52c41a' }} 
              />
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              {data.enabled ? (
                <Space size={4}>
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  <Text style={{ color: '#52c41a', fontSize: 12 }}>已启用</Text>
                </Space>
              ) : (
                <Space size={4}>
                  <CloseCircleOutlined style={{ color: '#f5222d' }} />
                  <Text style={{ color: '#f5222d', fontSize: 12 }}>已禁用</Text>
                </Space>
              )}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {data.condition_preview && (
          <Card 
            size="small" 
            title="触发条件 (WHEN)" 
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px', background: '#fff7e6' } }}
          >
            <div style={{ 
              background: '#fff7e6', 
              padding: '8px 12px', 
              borderRadius: 6,
              fontFamily: 'monospace',
              fontSize: 11,
              color: '#d46b08',
              overflow: 'auto',
              maxHeight: 120,
            }}>
              {data.condition_preview}
            </div>
          </Card>
        )}

        {data.action_preview && (
          <Card 
            size="small" 
            title="执行动作 (THEN)" 
            style={{ marginBottom: 12 }}
            styles={{ header: { fontSize: 12, padding: '4px 12px', background: '#f6ffed' } }}
          >
            <div style={{ 
              background: '#f6ffed', 
              padding: '8px 12px', 
              borderRadius: 6,
              fontFamily: 'monospace',
              fontSize: 11,
              color: '#389e0d',
              overflow: 'auto',
              maxHeight: 120,
            }}>
              {data.action_preview}
            </div>
          </Card>
        )}
      </div>
    );
  }

  return (
    <Card size="small">
      <Paragraph type="secondary">未知节点类型: {type}</Paragraph>
      <pre style={{ fontSize: 11, overflow: 'auto', maxHeight: 200 }}>
        {JSON.stringify(node, null, 2)}
      </pre>
    </Card>
  );
}
