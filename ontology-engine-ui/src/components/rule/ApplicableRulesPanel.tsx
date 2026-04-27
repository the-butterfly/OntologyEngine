// components/rule/ApplicableRulesPanel.tsx
// Applicable rules panel for entity rule analysis

import { ArrowRightOutlined } from '@ant-design/icons';
import {
  Alert, Card, Col, Empty, Row, Space, Spin, Tag, Typography,
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

export interface ApplicableRulesData {
  entity_id: string;
  applicable_rules: Array<{
    id: string;
    name: string;
    rule_type: string;
    priority: number;
    input_elements?: ElementRef[];
    output_elements?: ElementRef[];
    matching_logics?: Array<{
      id: string;
      when?: { expression?: string };
    }>;
  }>;
  dependency_edges: Array<{
    from: string;
    via_element: string;
    to: string;
  }>;
  total: number;
  entity_concept: string;
}

interface ApplicableRulesPanelProps {
  applicableRules: ApplicableRulesData | null;
  loading: boolean;
}

export default function ApplicableRulesPanel({
  applicableRules,
  loading,
}: ApplicableRulesPanelProps) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Spin />
      </div>
    );
  }

  if (!applicableRules) {
    return <Empty description="选择实体后查看适用规则" />;
  }

  const { applicable_rules, dependency_edges, total, entity_concept } = applicableRules;

  return (
    <div>
      <Alert
        type="info"
        message={
          <Space>
            <Text>
              实体 <Text strong>{applicableRules.entity_id}</Text>
            </Text>
            <Text>
              类型: <Tag color="blue">{entity_concept}</Tag>
            </Text>
            <Text>
              适用 <Text strong>{total}</Text> 条规则
            </Text>
          </Space>
        }
        style={{ marginBottom: 16 }}
      />

      {applicable_rules.map((rule) => (
        <Card
          key={rule.id}
          size="small"
          style={{
            marginBottom: 12,
            borderLeft: `3px solid ${
              RULE_TYPE_COLORS[rule.rule_type] === 'green'
                ? '#52c41a'
                : RULE_TYPE_COLORS[rule.rule_type] === 'orange'
                  ? '#fa8c16'
                  : RULE_TYPE_COLORS[rule.rule_type] === 'red'
                    ? '#ff4d4f'
                    : '#1890ff'
            }`,
          }}
        >
          <Row align="middle" gutter={16}>
            <Col span={8}>
              <Text strong style={{ fontSize: 13 }}>
                {rule.name}
              </Text>
              <br />
              <Text type="secondary" style={{ fontSize: 11 }}>
                {rule.id}
              </Text>
              <br />
              <Tag color={RULE_TYPE_COLORS[rule.rule_type] || 'default'}>{rule.rule_type}</Tag>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {' '}
                P{rule.priority}
              </Text>
            </Col>
            <Col span={7}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                输入:
              </Text>
              <Space wrap size="small" style={{ display: 'block' }}>
                {(rule.input_elements || []).map((e: ElementRef, i: number) => (
                  <Tag key={i} color="geekblue" style={{ fontSize: 10 }}>
                    {e.name || e.id}
                  </Tag>
                ))}
                {!rule.input_elements?.length && (
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    无
                  </Text>
                )}
              </Space>
              <Text type="secondary" style={{ fontSize: 11 }}>
                输出:
              </Text>
              <Space wrap size="small">
                {(rule.output_elements || []).map((e: ElementRef, i: number) => (
                  <Tag key={i} color="volcano" style={{ fontSize: 10 }}>
                    {e.name || e.id}
                  </Tag>
                ))}
                {!rule.output_elements?.length && (
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    无
                  </Text>
                )}
              </Space>
            </Col>
            <Col span={9}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                匹配逻辑 ({rule.matching_logics?.length || 0}):
              </Text>
              {(rule.matching_logics || []).map((logic) => (
                <div
                  key={logic.id}
                  style={{
                    padding: '4px 8px',
                    marginTop: 4,
                    background: '#f6ffed',
                    borderRadius: 4,
                    border: '1px solid #b7eb8f',
                    fontSize: 11,
                  }}
                >
                  <Tag color="purple" style={{ fontSize: 10 }}>
                    {logic.id}
                  </Tag>
                  {logic.when?.expression && (
                    <Text code style={{ fontSize: 10, marginLeft: 4 }}>
                      {logic.when.expression.substring(0, 40)}
                    </Text>
                  )}
                </div>
              ))}
              {!rule.matching_logics?.length && (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  无匹配逻辑
                </Text>
              )}
            </Col>
          </Row>
        </Card>
      ))}

      {dependency_edges.length > 0 && (
        <Card size="small" title="规则间数据流">
          {dependency_edges.map((edge: { from: string; via_element: string; to: string }, idx: number) => (
            <div
              key={idx}
              style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}
            >
              <Tag color="blue">{edge.from}</Tag>
              <ArrowRightOutlined />
              <Tag color="geekblue">{edge.via_element}</Tag>
              <ArrowRightOutlined />
              <Tag color="green">{edge.to}</Tag>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
