// ontology-engine-ui/src/components/rule/RuleLocatePanel.tsx
// Cross-group rule location panel - find rule groups that produce specific outputs
// Uses /rule-groups/locate endpoint

import { useState, useCallback } from 'react';
import { Card, Select, Input, Button, Space, Table, Tag, Typography, Spin, message, Empty } from 'antd';
import { SearchOutlined, BranchesOutlined } from '@ant-design/icons';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { LocateRuleGroupsResponse } from '../../types/rule';

const { Text } = Typography;

interface RuleLocatePanelProps {
  schemaId?: string;
  onSelectRuleGroup?: (name: string) => void;
}

export default function RuleLocatePanel({ schemaId, onSelectRuleGroup }: RuleLocatePanelProps) {
  const [outputName, setOutputName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LocateRuleGroupsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    if (!outputName.trim()) {
      message.warning('请输入要查找的输出要素名称');
      return;
    }

    setLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const data = await ruleGroupsApi.locateRuleGroups(outputName.trim(), schemaId);
      setResult(data);
      if (data.rule_groups.length === 0) {
        message.info(`未找到产出「${outputName}」的规则组`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '查找失败');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [outputName, schemaId]);

  const columns = [
    {
      title: '规则组',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <Button
          type="link"
          style={{ padding: 0, fontWeight: 500 }}
          onClick={() => onSelectRuleGroup?.(name)}
        >
          <BranchesOutlined style={{ marginRight: 6 }} />
          {name}
        </Button>
      ),
    },
    {
      title: '产出要素',
      key: 'outputs',
      render: (_: unknown, record: { outputs: Array<{ name: string; type: string }> }) => (
        <Space wrap size="small">
          {record.outputs.map((o) => (
            <Tag key={o.name} color="geekblue">{o.name}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '依赖关系',
      dataIndex: 'depends_on',
      key: 'depends_on',
      render: (deps: string[]) => (
        deps.length > 0 ? (
          <Space size="small" wrap>
            {deps.slice(0, 3).map((d) => (
              <Tag key={d} color="orange" style={{ fontSize: 10 }}>{d}</Tag>
            ))}
            {deps.length > 3 && <Tag style={{ fontSize: 10 }}>+{deps.length - 3}</Tag>}
          </Space>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>无</Text>
        )
      ),
    },
  ];

  return (
    <Card
      size="small"
      title={
        <Space>
          <SearchOutlined />
          <span>规则组定位</span>
        </Space>
      }
      extra={
        <Text type="secondary" style={{ fontSize: 11 }}>
          跨规则组查找产出特定输出的规则组
        </Text>
      }
      style={{ marginBottom: 16 }}
    >
      <Space style={{ marginBottom: 12 }}>
        <Input
          placeholder="输入输出要素名称（如 decision, eligible）"
          value={outputName}
          onChange={(e) => setOutputName(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 260 }}
          prefix={<SearchOutlined style={{ color: '#d9d9d9' }} />}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>
          查找
        </Button>
      </Space>

      {loading && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spin />
        </div>
      )}

      {!loading && error && (
        <div style={{ color: '#ff4d4f', textAlign: 'center', padding: '12px' }}>
          {error}
        </div>
      )}

      {!loading && hasSearched && result && (
        <div>
          {result.rule_groups.length > 0 ? (
            <>
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  找到 {result.rule_groups.length} 个规则组产出「{result.output}」
                </Text>
              </div>
              <Table
                dataSource={result.rule_groups}
                columns={columns}
                rowKey="name"
                size="small"
                pagination={false}
              />
            </>
          ) : (
            <Empty description={`未找到产出「${result.output}」的规则组`} image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      )}

      {!loading && !hasSearched && (
        <Text type="secondary" style={{ fontSize: 12, display: 'block', textAlign: 'center', padding: '12px' }}>
          输入要查找的输出要素名称，点击查找按钮搜索相关规则组
        </Text>
      )}
    </Card>
  );
}
