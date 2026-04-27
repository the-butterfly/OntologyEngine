// components/rule/DecisionBadge.tsx
// Decision badge component for rule execution results

import { Tag } from 'antd';

interface DecisionBadgeProps {
  decision: string;
}

const DECISION_COLOR_MAP: Record<string, string> = {
  APPROVED: 'success',
  REJECTED: 'error',
  REVIEW: 'warning',
  APPROVE_WITH_CONDITIONS: 'warning',
};

export default function DecisionBadge({ decision }: DecisionBadgeProps) {
  return (
    <Tag
      color={DECISION_COLOR_MAP[decision] || 'default'}
      style={{ fontSize: 16, padding: '4px 12px', borderRadius: 8 }}
    >
      {decision}
    </Tag>
  );
}
