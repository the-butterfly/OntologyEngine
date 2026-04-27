// L1FactObjectsTab.tsx - L1 Fact Objects management
import { Table, Tag, Space, Tooltip, Descriptions, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

const { Text } = Typography;

interface FactObject {
  id: string;
  name: string;
  description?: string;
  properties?: Array<{ name: string; type: string; required?: boolean; unique?: boolean; description?: string }>;
  relations?: Array<{ name: string; target: string; cardinality?: string; description?: string }>;
}

interface L1FactObjectsTabProps {
  items: FactObject[];
}

const l1Columns: ColumnsType<FactObject> = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 160, ellipsis: true },
  { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
  {
    title: '属性',
    key: 'properties',
    render: (_: any, record: FactObject) => {
      const props = record.properties || [];
      return (
        <Space size="small" wrap>
          {props.slice(0, 5).map((p, idx) => (
            <Tag key={idx} color={p.required ? 'red' : 'default'} style={{ fontSize: 11 }}>
              {p.name}: <Text type="secondary" style={{ fontSize: 11 }}>{p.type}</Text>
            </Tag>
          ))}
          {props.length > 5 && <Tag>+{props.length - 5}</Tag>}
        </Space>
      );
    },
  },
  {
    title: '关系',
    key: 'relations',
    width: 200,
    render: (_: any, record: FactObject) => {
      const rels = record.relations || [];
      if (!rels.length) return <Text type="secondary">无</Text>;
      return (
        <Space size="small" wrap>
          {rels.map((r, idx) => (
            <Tooltip key={idx} title={r.cardinality}>
              <Tag color="blue" style={{ fontSize: 11 }}>
                {r.name} → {r.target}
              </Tag>
            </Tooltip>
          ))}
        </Space>
      );
    },
  },
];

export default function L1FactObjectsTab({ items }: L1FactObjectsTabProps) {
  return (
    <Table
      columns={l1Columns}
      dataSource={items}
      rowKey="id"
      size="small"
      pagination={{ pageSize: 10 }}
      expandable={{
        expandedRowRender: (record: FactObject) => (
          <Descriptions size="small" column={2} style={{ margin: 8 }}>
            {record.description && <Descriptions.Item label="描述" span={2}>{record.description}</Descriptions.Item>}
            <Descriptions.Item label="属性数">{(record.properties || []).length}</Descriptions.Item>
            <Descriptions.Item label="关系数">{(record.relations || []).length}</Descriptions.Item>
            {(record.properties || []).map((p, i) => (
              <Descriptions.Item key={i} label={p.name}>
                <Tag color={p.required ? 'red' : 'default'}>{p.type}</Tag>
                {p.description && <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>{p.description}</Text>}
              </Descriptions.Item>
            ))}
          </Descriptions>
        ),
      }}
    />
  );
}
