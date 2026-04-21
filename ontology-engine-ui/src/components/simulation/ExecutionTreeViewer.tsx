// ontology_engine-ui/src/components/simulation/ExecutionTreeViewer.tsx
import { Card, Tabs, Tag, Typography } from 'antd';
import type { ExecutionTree, ExecutableStep } from '../../types/simulation';

const { Text } = Typography;

interface ExecutionTreeViewerProps {
  tree: ExecutionTree;
  onStepClick?: (step: ExecutableStep) => void;
}

export function ExecutionTreeViewer({ tree, onStepClick }: ExecutionTreeViewerProps) {
  const tabItems = tree.layers.map((layer, idx) => ({
    key: String(idx),
    label: `Layer ${idx} (${layer.steps.length}步)`,
    children: (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        {layer.steps.map((step) => (
          <Card
            key={step.step_id}
            size="small"
            style={{ width: 240, cursor: 'pointer' }}
            onClick={() => onStepClick?.(step)}
          >
            <div style={{ marginBottom: 8 }}>
              <Tag color={getTypeColor(step.rule_group_type)}>
                {step.rule_group_name}
              </Tag>
            </div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              {step.step_name}
            </Text>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              条件: {step.condition.type === 'expression' ? step.condition.expression : `${step.condition.type}`}
            </div>
            <div style={{ fontSize: 12, color: '#1890ff' }}>
              → {step.action.operator}
            </div>
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
              输出: {step.output_names.join(', ')}
            </div>
          </Card>
        ))}
      </div>
    ),
  }));

  return (
    <Card title="执行树">
      <Tabs items={tabItems} />
    </Card>
  );
}

function getTypeColor(type: string): string {
  const colors: Record<string, string> = {
    constraint: 'blue',
    inference: 'purple',
    alert: 'orange',
    decision: 'green',
  };
  return colors[type] || 'default';
}