// ontology-engine-ui/src/pages/rules/RuleGroupListPage.tsx
// Rule group list page with table, filtering, and actions

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Select,
  Card,
  Tag,
  Typography,
  message,
  Popconfirm,
  Modal,
  Form,
  Input as InputAnt,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  ExportOutlined,
  ImportOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useRuleGroups } from '../../hooks/useRuleGroups';
import type { RuleGroup } from '../../types/rule';

const { Title, Text } = Typography;
const { TextArea } = InputAnt;

interface RuleGroupListPageProps {
  schemaId: string;
  onCreate?: () => void;
  onEdit?: (group: RuleGroup) => void;
}

export const RuleGroupListPage: React.FC<RuleGroupListPageProps> = ({
  schemaId,
  onCreate,
  onEdit,
}) => {
  const navigate = useNavigate();
  const {
    loading,
    ruleGroups,
    fetchGroups,
    deleteGroup,
    exportYaml,
    importYaml,
    error,
    clearError,
  } = useRuleGroups(schemaId);

  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importContent, setImportContent] = useState('');
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    fetchGroups();
  }, [schemaId, typeFilter, fetchGroups]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error, clearError]);

  const filteredGroups = ruleGroups.filter((g) =>
    g.name.toLowerCase().includes(searchText.toLowerCase())
  );

  const handleEdit = useCallback(
    (group: RuleGroup) => {
      if (onEdit) {
        onEdit(group);
      } else {
        navigate(`/rules/${group.id}?schemaId=${schemaId}`);
      }
    },
    [navigate, onEdit, schemaId]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteGroup(id);
        message.success('规则组已删除');
      } catch {
        // Error handled by hook
      }
    },
    [deleteGroup]
  );

  const handleExport = useCallback(
    async (group: RuleGroup) => {
      try {
        const yaml = await exportYaml(group.name);
        // Create download
        const blob = new Blob([yaml], { type: 'text/yaml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${group.name}.yaml`;
        a.click();
        URL.revokeObjectURL(url);
        message.success('YAML 已导出');
      } catch {
        // Error handled by hook
      }
    },
    [exportYaml]
  );

  const handleImport = useCallback(async () => {
    if (!importContent.trim()) {
      message.warning('请输入 YAML 内容');
      return;
    }
    setImporting(true);
    try {
      const imported = await importYaml(importContent);
      message.success(`规则组「${imported.name}」已导入`);
      setImportModalVisible(false);
      setImportContent('');
      fetchGroups();
    } catch {
      // Error handled by hook
    } finally {
      setImporting(false);
    }
  // Note: schemaId is captured in importYaml closure - no need to add to deps
  }, [importContent, importYaml, fetchGroups]);

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: RuleGroup) => (
        <Button type="link" onClick={() => handleEdit(record)}>
          {name}
        </Button>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          constraint: 'blue',
          inference: 'purple',
          alert: 'orange',
          decision: 'green',
        };
        const labelMap: Record<string, string> = {
          constraint: '约束',
          inference: '推理',
          alert: '告警',
          decision: '决策',
        };
        return <Tag color={colorMap[type] || 'default'}>{labelMap[type] || type}</Tag>;
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: RuleGroup, b: RuleGroup) => a.priority - b.priority,
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean) => (enabled ? '是' : '否'),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (desc?: string) => desc || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: RuleGroup) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            title="编辑"
          />
          <Button
            type="text"
            size="small"
            icon={<ExportOutlined />}
            onClick={() => handleExport(record)}
            title="导出 YAML"
          />
          <Popconfirm
            title="确定删除此规则组？"
            description="删除后无法恢复"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              title="删除"
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={<Title level={4} style={{ margin: 0 }}>规则组</Title>}
        extra={
          <Space>
            <Button
              icon={<ImportOutlined />}
              onClick={() => setImportModalVisible(true)}
            >
              导入
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={onCreate}
            >
              新建规则组
            </Button>
          </Space>
        }
      >
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索规则组名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Select
            placeholder="筛选类型"
            allowClear
            style={{ width: 120 }}
            onChange={setTypeFilter}
            options={[
              { label: '决策', value: 'decision' },
              { label: '约束', value: 'constraint' },
              { label: '推理', value: 'inference' },
              { label: '告警', value: 'alert' },
            ]}
          />
        </Space>
        <Table
          dataSource={filteredGroups}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          locale={{ emptyText: '暂无规则组' }}
        />
      </Card>

      {/* Import Modal */}
      <Modal
        title="导入规则组"
        open={importModalVisible}
        onOk={handleImport}
        onCancel={() => {
          setImportModalVisible(false);
          setImportContent('');
        }}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
        width={600}
      >
        <Form layout="vertical">
          <Form.Item
            label="YAML 内容"
            required
            help="粘贴规则组的 YAML 定义"
          >
            <TextArea
              rows={15}
              value={importContent}
              onChange={(e) => setImportContent(e.target.value)}
              placeholder={`rule_group:
  name: example_rule
  type: decision
  priority: 1
  ...`}
            />
          </Form.Item>
        </Form>
        <Text type="secondary" style={{ fontSize: 12 }}>
          提示：导入的规则组将属于当前语义空间
        </Text>
      </Modal>
    </div>
  );
};

export default RuleGroupListPage;
