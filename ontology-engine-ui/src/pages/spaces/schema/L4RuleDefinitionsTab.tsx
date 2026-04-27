// L4RuleDefinitionsTab.tsx - L4 Rule Definitions management
import { Table, Tag, Space, Badge, Collapse, Descriptions, Empty, Typography } from 'antd';
const { Text } = Typography;
import type { ColumnsType } from 'antd/es/table';

const RULE_TYPE_COLORS: Record<string, string> = {
  constraint: 'orange',
  inference: 'blue',
  alert: 'red',
  decision: 'green',
  veto: 'magenta',
};

interface RuleDefinitionEntry {
  id: string;
  name?: string;
  description?: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  target_objects?: string[];
  applicable_categorizations?: string[];
  input_elements?: any[];
  output_elements?: any[];
  logic_ids?: string[];
}

interface RuleLogic {
  id: string;
  name?: string;
  when?: { expression?: string };
  then_action?: { action_type?: string; output?: any };
  applicable_conditions?: any[];
}

interface L4RuleDefinitionsTabProps {
  items: RuleDefinitionEntry[];
  ruleLogics: RuleLogic[];
}

const l4Columns: ColumnsType<RuleDefinitionEntry> = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 180, ellipsis: true },
  { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
  {
    title: '类型',
    dataIndex: 'rule_type',
    key: 'rule_type',
    width: 90,
    render: (t: string) => <Tag color={RULE_TYPE_COLORS[t] || 'default'}>{t}</Tag>,
  },
  {
    title: '优先级',
    dataIndex: 'priority',
    key: 'priority',
    width: 80,
    sorter: (a, b) => a.priority - b.priority,
  },
  {
    title: '状态',
    dataIndex: 'enabled',
    key: 'enabled',
    width: 70,
    render: (v: boolean) => v ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>,
  },
  {
    title: '输入元素',
    dataIndex: 'input_elements',
    key: 'inputs',
    render: (elems: any[]) => (
      <Space wrap size="small">
        {(elems || []).map((e, i) => (
          <Tag key={i} color="geekblue" style={{ fontSize: 11 }}>{e.name || e.id}</Tag>
        ))}
      </Space>
    ),
  },
  {
    title: '输出元素',
    dataIndex: 'output_elements',
    key: 'outputs',
    render: (elems: any[]) => (
      <Space wrap size="small">
        {(elems || []).map((e, i) => (
          <Tag key={i} color="volcano" style={{ fontSize: 11 }}>{e.name || e.id}</Tag>
        ))}
      </Space>
    ),
  },
  {
    title: '逻辑数',
    dataIndex: 'logic_ids',
    key: 'logic_ids',
    width: 70,
    render: (ids: string[]) => <Badge count={(ids || []).length} color="purple" />,
  },
];

export default function L4RuleDefinitionsTab({ items, ruleLogics }: L4RuleDefinitionsTabProps) {
  // Helper to build logic collapse items
  const buildLogicCollapseItems = (logicIds: string[]) => {
    const logics = (ruleLogics || []).filter(
      (rl: any) => (logicIds || []).includes(rl.id)
    );
    if (logics.length === 0) {
      return [{ key: 'empty', label: '无', children: <Empty description="无绑定的规则逻辑" /> }];
    }
    return logics.map((logic: any) => ({
      key: logic.id,
      label: <span><Tag color="purple">{logic.id}</Tag>{logic.name || ''}</span>,
      children: (
        <Descriptions size="small" column={1}>
          {logic.when?.expression && (
            <Descriptions.Item label="条件">
              <Text code>{logic.when.expression}</Text>
            </Descriptions.Item>
          )}
          {logic.then_action && (
            <Descriptions.Item label="动作">
              <Tag color={RULE_TYPE_COLORS[logic.then_action.action_type || ''] || 'default'}>
                {logic.then_action.action_type}
              </Tag>
              {logic.then_action.output && (
                <Text code style={{ marginLeft: 8, fontSize: 11 }}>
                  {JSON.stringify(logic.then_action.output)}
                </Text>
              )}
            </Descriptions.Item>
          )}
          {(logic.applicable_conditions || []).length > 0 && (
            <Descriptions.Item label="适用条件">
              <Text type="secondary" style={{ fontSize: 11 }}>
                {JSON.stringify(logic.applicable_conditions)}
              </Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      ),
    }));
  };

  return (
    <Table
      columns={l4Columns}
      dataSource={items}
      rowKey="id"
      size="small"
      pagination={{ pageSize: 10 }}
      expandable={{
        expandedRowRender: (record: RuleDefinitionEntry) => (
          <Collapse size="small" style={{ margin: 8 }} items={buildLogicCollapseItems(record.logic_ids || [])} />
        ),
      }}
    />
  );
}
