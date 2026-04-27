// components/rule/DependencyGraphPanel.tsx
// Dependency graph display panel for rule execution

import { ArrowRightOutlined } from '@ant-design/icons';
import {
  Alert, Card, Col, Empty, Row, Space, Spin, Statistic, Tag, Tooltip, Typography,
} from 'antd';

const { Text } = Typography;

const RULE_TYPE_COLORS: Record<string, string> = {
  constraint: 'orange',
  inference: 'blue',
  alert: 'red',
  decision: 'green',
  veto: 'magenta',
};

interface ElementRef {
  id: string;
  name?: string;
}

interface DependencyNode {
  id: string;
  label: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  input_elements: ElementRef[];
  output_elements: ElementRef[];
  logic_count: number;
}

interface DependencyEdge {
  id: string;
  source: string;
  target: string;
  element: string;
  type: string;
}

interface MutualExclusion {
  rule_a: string;
  rule_b: string;
  reason: string;
  type: string;
}

interface DependencyGraphData {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  mutual_exclusions: MutualExclusion[];
  execution_order: string[];
  stats: {
    total_rules: number;
    dependency_edges: number;
    exclusion_pairs: number;
  };
}

interface DependencyGraphPanelProps {
  dependencyGraph: DependencyGraphData | null;
  loading: boolean;
}

export default function DependencyGraphPanel({
  dependencyGraph,
  loading,
}: DependencyGraphPanelProps) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Spin />
      </div>
    );
  }

  if (!dependencyGraph) {
    return <Empty description="加载中" />;
  }

  const { nodes, edges, mutual_exclusions, execution_order, stats } = dependencyGraph;

  return (
    <div>
      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic title="规则总数" value={stats.total_rules} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic title="依赖边" value={stats.dependency_edges} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic title="互斥对" value={stats.exclusion_pairs} />
          </Card>
        </Col>
      </Row>

      {/* Execution Order */}
      <Card size="small" title="拓扑执行顺序" style={{ marginBottom: 16 }}>
        <Space wrap>
          {execution_order.map((ruleId, idx) => {
            const node = nodes.find((n) => n.id === ruleId);
            return (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {idx > 0 && <ArrowRightOutlined style={{ color: '#999', fontSize: 10 }} />}
                <Tooltip title={node?.label || ruleId}>
                  <Tag
                    color={RULE_TYPE_COLORS[node?.rule_type || ''] || 'default'}
                    style={{ cursor: 'default' }}
                  >
                    {idx + 1}. {(node?.label || ruleId).substring(0, 20)}
                  </Tag>
                </Tooltip>
              </div>
            );
          })}
        </Space>
      </Card>

      {/* Rule Nodes */}
      <Card size="small" title="规则节点详情" style={{ marginBottom: 16 }}>
        {nodes.map((node) => (
          <Card
            key={node.id}
            size="small"
            style={{
              marginBottom: 8,
              borderLeft: `3px solid ${
                node.rule_type === 'decision'
                  ? '#52c41a'
                  : node.rule_type === 'constraint'
                    ? '#fa8c16'
                    : node.rule_type === 'alert'
                      ? '#ff4d4f'
                      : '#1890ff'
              }`,
            }}
          >
            <Row align="middle" gutter={16}>
              <Col span={8}>
                <Text strong style={{ fontSize: 13 }}>
                  {node.label}
                </Text>
                <br />
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {node.id}
                </Text>
              </Col>
              <Col span={4}>
                <Tag color={RULE_TYPE_COLORS[node.rule_type] || 'default'}>{node.rule_type}</Tag>
                <br />
                <Text type="secondary" style={{ fontSize: 11 }}>
                  优先级: {node.priority}
                </Text>
              </Col>
              <Col span={6}>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
                  输入:
                </Text>
                <Space wrap size="small">
                  {(node.input_elements || []).map((e: ElementRef, i: number) => (
                    <Tag key={i} color="geekblue" style={{ fontSize: 10 }}>
                      {e.name || e.id}
                    </Tag>
                  ))}
                  {!node.input_elements?.length && (
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      无
                    </Text>
                  )}
                </Space>
              </Col>
              <Col span={6}>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
                  输出:
                </Text>
                <Space wrap size="small">
                  {(node.output_elements || []).map((e: ElementRef, i: number) => (
                    <Tag key={i} color="volcano" style={{ fontSize: 10 }}>
                      {e.name || e.id}
                    </Tag>
                  ))}
                  {!node.output_elements?.length && (
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      无
                    </Text>
                  )}
                </Space>
              </Col>
            </Row>
          </Card>
        ))}
      </Card>

      {/* Dependency Edges */}
      {edges.length > 0 && (
        <Card size="small" title="数据依赖关系" style={{ marginBottom: 16 }}>
          {edges.map((edge) => (
            <div
              key={edge.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 12px',
                marginBottom: 6,
                background: '#f0f5ff',
                borderRadius: 6,
                border: '1px solid #d6e4ff',
              }}
            >
              <Tag color="blue">{edge.source}</Tag>
              <ArrowRightOutlined />
              <Tag color="purple">{edge.element}</Tag>
              <ArrowRightOutlined />
              <Tag color="green">{edge.target}</Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>
                数据流依赖
              </Text>
            </div>
          ))}
        </Card>
      )}

      {/* Mutual Exclusions */}
      {mutual_exclusions.length > 0 && (
        <Card size="small" title="互斥规则对">
          {mutual_exclusions.map((pair, idx) => (
            <Alert
              key={idx}
              type="warning"
              message={
                <Space>
                  <Tag color="orange">{pair.rule_a}</Tag>
                  <Text>⊥</Text>
                  <Tag color="orange">{pair.rule_b}</Tag>
                  <Tag>{pair.type}</Tag>
                </Space>
              }
              description={pair.reason}
              showIcon
              style={{ marginBottom: 8 }}
            />
          ))}
        </Card>
      )}
    </div>
  );
}
