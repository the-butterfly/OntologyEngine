// components/rule/SubConditionList.tsx
// Sub-condition list component for rendering condition breakdown

import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { Tag, Typography } from 'antd';

const { Text } = Typography;

interface SubCondition {
  type: string;
  expr: string;
  result: boolean;
  error?: string;
}

interface SubConditionListProps {
  subConditions: SubCondition[];
}

export default function SubConditionList({ subConditions }: SubConditionListProps) {
  if (!subConditions?.length) return null;

  return (
    <div style={{ marginTop: 8 }}>
      {subConditions.map((sc, idx) => (
        <div
          key={idx}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 4,
            padding: '4px 8px',
            background: sc.result ? '#f6ffed' : '#fff1f0',
            borderRadius: 4,
            border: `1px solid ${sc.result ? '#b7eb8f' : '#ffccc7'}`,
          }}
        >
          {sc.result ? (
            <CheckCircleOutlined style={{ color: '#52c41a', flexShrink: 0 }} />
          ) : (
            <CloseCircleOutlined style={{ color: '#ff4d4f', flexShrink: 0 }} />
          )}
          <Tag style={{ margin: 0 }}>{sc.type}</Tag>
          <Text code style={{ fontSize: 11, flex: 1 }}>
            {sc.expr}
          </Text>
          <Text
            type={sc.result ? 'success' : 'danger'}
            style={{ fontSize: 11, flexShrink: 0 }}
          >
            {sc.result ? '✓' : '✗'}
          </Text>
          {sc.error && (
            <Text type="danger" style={{ fontSize: 11 }}>
              {sc.error}
            </Text>
          )}
        </div>
      ))}
    </div>
  );
}
