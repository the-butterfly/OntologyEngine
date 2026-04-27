import { Card, Descriptions, Tag, Space, Typography, Divider, Badge, Collapse } from 'antd';
import { 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  PlayCircleOutlined,
  ArrowRightOutlined,
  BranchesOutlined,
} from '@ant-design/icons';
import { RULE_TYPE_COLORS, EXECUTION_STATUS_COLORS } from '../../utils/colorSchemes';
import type { ExecutionStepSnapshot, ConditionDetail } from '../../types/visualization';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

interface StepDetailPanelProps {
  snapshot: ExecutionStepSnapshot;
}

export default function StepDetailPanel({ snapshot }: StepDetailPanelProps) {
  const { 
    rule_id, 
    rule_name, 
    rule_type, 
    condition_details, 
    inputs, 
    outputs, 
    explanation, 
    status, 
    duration_ms,
    condition_expression,
    condition_result,
  } = snapshot;

  const ruleColor = RULE_TYPE_COLORS[rule_type];
  const statusColor = EXECUTION_STATUS_COLORS[status];

  return (
    <div style={{ padding: 4 }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'flex-start', 
        gap: 12, 
        marginBottom: 16,
        padding: '12px 16px',
        background: status === 'passed' ? '#f6ffed' : status === 'failed' ? '#fff1f0' : '#e6f7ff',
        borderRadius: 8,
        border: `1px solid ${statusColor}`,
      }}>
        <div style={{ fontSize: 24, color: statusColor, marginTop: 2 }}>
          {status === 'passed' ? <CheckCircleOutlined /> : 
           status === 'failed' ? <CloseCircleOutlined /> : 
           <PlayCircleOutlined />}
        </div>
        <div style={{ flex: 1 }}>
          <h4 style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 600 }}>
            {rule_name}
          </h4>
          <Space size={4}>
            <code style={{ fontSize: 11, color: '#666' }}>{rule_id}</code>
            <Tag color={ruleColor?.stroke} style={{ fontSize: 10, margin: 0 }}>
              {ruleColor?.label}
            </Tag>
          </Space>
        </div>
        <Text strong style={{ color: statusColor, fontSize: 16 }}>
          {status === 'passed' ? '通过' : status === 'failed' ? '失败' : status === 'skipped' ? '跳过' : '执行中'}
        </Text>
      </div>

      {/* Basic Info */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="执行耗时">
            <Badge 
              count={`${duration_ms.toFixed(2)}ms`} 
              style={{ 
                backgroundColor: duration_ms > 10 ? '#fa8c16' : '#52c41a',
                fontSize: 11,
              }} 
            />
          </Descriptions.Item>
          <Descriptions.Item label="条件结果">
            <Tag color={condition_result ? 'green' : condition_result === false ? 'red' : 'default'}>
              {condition_result ? '满足' : condition_result === false ? '不满足' : 'N/A'}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Condition Expression */}
      {condition_expression && (
        <Card
          size="small"
          title={
            <Space>
              <BranchesOutlined style={{ color: '#fa8c16' }} />
              <span>触发条件 (WHEN)</span>
            </Space>
          }
          style={{ marginBottom: 12 }}
          styles={{ header: { background: '#fff7e6', fontSize: 13 } }}
        >
          <div style={{ 
            background: '#fffbe6', 
            padding: '10px 12px', 
            borderRadius: 6,
            fontFamily: 'monospace',
            fontSize: 12,
            color: '#d46b08',
            overflow: 'auto',
            maxHeight: 100,
            border: '1px solid #ffe7ba',
          }}>
            {condition_expression}
          </div>
        </Card>
      )}

      {/* Condition Details */}
      {condition_details.length > 0 && (
        <Card
          size="small"
          title={
            <Space>
              <ExclamationCircleOutlined style={{ color: '#1890ff' }} />
              <span>条件拆解 ({condition_details.length})</span>
            </Space>
          }
          style={{ marginBottom: 12 }}
          styles={{ header: { background: '#e6f7ff', fontSize: 13 } }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {condition_details.map((detail: ConditionDetail, idx: number) => (
              <ConditionDetailItem key={idx} detail={detail} index={idx} />
            ))}
          </div>
        </Card>
      )}

      {/* Inputs */}
      {Object.keys(inputs).length > 0 && (
        <Card
          size="small"
          title={
            <Space>
              <span style={{ color: '#1890ff' }}>→</span>
              <span>输入数据 ({Object.keys(inputs).length})</span>
            </Space>
          }
          style={{ marginBottom: 12 }}
          styles={{ header: { background: '#f6ffed', fontSize: 13 } }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {Object.entries(inputs).map(([key, value]) => (
              <DataRow key={key} label={key} value={value} type="input" />
            ))}
          </div>
        </Card>
      )}

      {/* Outputs */}
      {Object.keys(outputs).length > 0 && (
        <Card
          size="small"
          title={
            <Space>
              <span style={{ color: '#52c41a' }}>→</span>
              <span>输出结果 ({Object.keys(outputs).length})</span>
            </Space>
          }
          style={{ marginBottom: 12 }}
          styles={{ header: { background: '#f6ffed', fontSize: 13 } }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {Object.entries(outputs).map(([key, value]) => (
              <DataRow key={key} label={key} value={value} type="output" />
            ))}
          </div>
        </Card>
      )}

      {/* Explanation */}
      {explanation && (
        <Card
          size="small"
          title={
            <Space>
              <span style={{ color: '#722ed1' }}>💡</span>
              <span>执行解释</span>
            </Space>
          }
          style={{ marginBottom: 12 }}
          styles={{ header: { background: '#f9f0ff', fontSize: 13 } }}
        >
          <Paragraph style={{ fontSize: 13, margin: 0, color: '#531dab' }}>
            {explanation}
          </Paragraph>
        </Card>
      )}
    </div>
  );
}

function ConditionDetailItem({ detail, index }: { detail: ConditionDetail; index: number }) {
  const { expression, resolved, result, explanation } = detail;
  
  return (
    <div style={{
      background: result ? '#f6ffed' : '#fff1f0',
      border: `1px solid ${result ? '#b7eb8f' : '#ffa39e'}`,
      borderRadius: 6,
      padding: '8px 12px',
    }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: 4,
      }}>
        <Space>
          <Tag color={result ? 'green' : 'red'} style={{ margin: 0 }}>
            条件{index + 1}
          </Tag>
          <code style={{ 
            fontSize: 11, 
            color: result ? '#389e0d' : '#cf1322',
            fontWeight: 600,
          }}>
            {result ? '✓ true' : '✗ false'}
          </code>
        </Space>
      </div>
      
      <div style={{ 
        fontFamily: 'monospace', 
        fontSize: 12, 
        color: '#666',
        background: 'rgba(255,255,255,0.7)',
        padding: '4px 8px',
        borderRadius: 4,
        marginBottom: 4,
      }}>
        {expression}
      </div>
      
      <div style={{ fontSize: 11, color: '#999' }}>
        解析: {resolved}
      </div>
      
      {explanation && (
        <div style={{ 
          fontSize: 12, 
          color: result ? '#389e0d' : '#cf1322',
          marginTop: 4,
          paddingTop: 4,
          borderTop: `1px dashed ${result ? '#b7eb8f' : '#ffa39e'}`,
        }}>
          {explanation}
        </div>
      )}
    </div>
  );
}

function DataRow({ label, value, type }: { label: string; value: any; type: 'input' | 'output' }) {
  const formattedValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
  const isNumeric = typeof value === 'number';
  
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '6px 10px',
      background: type === 'output' ? '#f6ffed' : '#fafafa',
      borderRadius: 4,
      border: `1px solid ${type === 'output' ? '#b7eb8f' : '#f0f0f0'}`,
    }}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {label}
      </Text>
      <Text 
        strong={type === 'output'} 
        style={{ 
          fontSize: 12, 
          color: type === 'output' ? '#389e0d' : '#666',
          fontFamily: isNumeric ? 'monospace' : 'inherit',
        }}
      >
        {isNumeric && typeof value === 'number' ? value.toFixed(2) : formattedValue}
      </Text>
    </div>
  );
}
