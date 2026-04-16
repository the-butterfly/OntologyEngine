// ontology-engine-ui/src/pages/rules/RuleGroupListPage.tsx
// Rule group list page with table, filtering, and YAML import/export

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
  Tabs,
  Alert,
  Tooltip,
  Badge,
  Statistic,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  ExportOutlined,
  ImportOutlined,
  FolderOpenOutlined,
  CopyOutlined,
  BranchesOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useRuleGroups } from '../../hooks/useRuleGroups';
import { spaceApi } from '../../api/spaceApi';
import type { RuleGroup } from '../../types/rule';

const { Title, Text } = Typography;
const { TextArea } = Input;

// Preset example paths for common use cases
const EXAMPLE_PATHS = [
  {
    label: '供应链金融 - Schema',
    value: 'examples/supply_chain_finance/schema.yaml',
    desc: '包含 L1-L4 全层级 Schema 定义',
  },
  {
    label: '供应链金融 - 实例',
    value: 'examples/supply_chain_finance/instances.yaml',
    desc: '供应商、发票等实体实例数据',
  },
  {
    label: '个人消费信贷 - Schema',
    value: 'examples/consumer_credit/schema.yaml',
    desc: '个人信贷评分卡规则体系',
  },
  {
    label: '个人消费信贷 - 实例',
    value: 'examples/consumer_credit/instances.yaml',
    desc: '消费者信贷实例数据',
  },
];

// Rule type color/label mapping
const TYPE_CONFIG: Record<string, { color: string; label: string }> = {
  constraint: { color: 'blue', label: '约束' },
  inference: { color: 'purple', label: '推理' },
  alert: { color: 'orange', label: '告警' },
  decision: { color: 'green', label: '决策' },
};

export const RuleGroupListPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';
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
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importActiveTab, setImportActiveTab] = useState('path');
  const [importContent, setImportContent] = useState('');
  const [importPath, setImportPath] = useState('examples/supply_chain_finance/schema.yaml');
  const [importing, setImporting] = useState(false);
  // Space info for display
  const [spaceName, setSpaceName] = useState<string>('');

  useEffect(() => {
    fetchGroups();
    if (schemaId) {
      // Fetch space info for breadcrumb
      spaceApi.getSpace(schemaId).then((space) => {
        if (space) setSpaceName(space.name || schemaId);
      }).catch(() => setSpaceName(schemaId));
    }
  }, [schemaId, fetchGroups]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error, clearError]);

  const filteredGroups = ruleGroups.filter((g) => {
    const matchText = g.name.toLowerCase().includes(searchText.toLowerCase()) ||
      (g.description || '').toLowerCase().includes(searchText.toLowerCase());
    const matchType = !typeFilter || g.type === typeFilter;
    return matchText && matchType;
  });

  // ---- Statistics ----
  const stats = {
    total: ruleGroups.length,
    active: ruleGroups.filter((g) => g.enabled).length,
    decision: ruleGroups.filter((g) => g.type === 'decision').length,
  };

  const handleEdit = useCallback(
    (group: RuleGroup) => {
      navigate(`/rules/${group.id}?schemaId=${schemaId}`);
    },
    [navigate, schemaId]
  );

  const handleCreate = useCallback(() => {
    navigate(`/rules/new?schemaId=${schemaId}`);
  }, [navigate, schemaId]);

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

  const handleImportByContent = useCallback(async () => {
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
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导入失败');
    } finally {
      setImporting(false);
    }
  }, [importContent, importYaml, fetchGroups]);

  const handleImportByPath = useCallback(async () => {
    if (!importPath.trim()) {
      message.warning('请选择或输入导入路径');
      return;
    }
    if (!schemaId) {
      message.warning('请先选择语义空间（schemaId 不能为空）');
      return;
    }
    setImporting(true);
    try {
      // Use the management schema load endpoint to import from path
      await spaceApi.loadSchemaFromYaml(schemaId, importPath, true);
      message.success(`已从 ${importPath} 导入 Schema 数据`);
      setImportModalVisible(false);
      fetchGroups();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '路径导入失败，请检查路径是否正确');
    } finally {
      setImporting(false);
    }
  }, [importPath, schemaId, fetchGroups]);

  const handleImportOk = () => {
    if (importActiveTab === 'path') {
      handleImportByPath();
    } else {
      handleImportByContent();
    }
  };

  const columns = [
    {
      title: '规则组名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: RuleGroup) => (
        <Button type="link" style={{ padding: 0, fontWeight: 500 }} onClick={() => handleEdit(record)}>
          <BranchesOutlined style={{ marginRight: 6 }} />
          {name}
        </Button>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 90,
      render: (type: string) => {
        const cfg = TYPE_CONFIG[type] || { color: 'default', label: type };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '作用对象',
      key: 'appliesTo',
      width: 160,
      render: (_: unknown, record: RuleGroup) => {
        const objects = record.appliesTo?.factObjects || [];
        return objects.length > 0 ? (
          <Space size={2} wrap>
            {objects.slice(0, 3).map((obj) => (
              <Tag key={obj} color="geekblue" style={{ fontSize: 11 }}>{obj}</Tag>
            ))}
            {objects.length > 3 && <Tag style={{ fontSize: 11 }}>+{objects.length - 3}</Tag>}
          </Space>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>未配置</Text>
        );
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: RuleGroup, b: RuleGroup) => a.priority - b.priority,
      render: (p: number) => <Text style={{ fontSize: 12 }}>{p}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean) => (
        <Badge status={enabled ? 'success' : 'default'} text={enabled ? '启用' : '禁用'} />
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: { showTitle: false },
      render: (desc?: string) => (
        <Tooltip title={desc}>
          <Text ellipsis style={{ maxWidth: 200, fontSize: 12, color: '#666' }}>
            {desc || '-'}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: RuleGroup) => (
        <Space size="small">
          <Tooltip title="编辑规则组">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Tooltip title="导出 YAML">
            <Button
              type="text"
              size="small"
              icon={<ExportOutlined />}
              onClick={() => handleExport(record)}
            />
          </Tooltip>
          <Tooltip title="复制规则组（开发中）">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              disabled
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此规则组？"
            description="删除后无法恢复，关联规则步骤也将一并删除"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '0 24px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, paddingTop: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            规则组管理
          </Title>
          {schemaId && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              语义空间: {spaceName || schemaId}
            </Text>
          )}
        </div>
        <Space>
          <Tooltip title="从文件或文本导入规则组">
            <Button icon={<ImportOutlined />} onClick={() => setImportModalVisible(true)}>
              导入
            </Button>
          </Tooltip>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
            disabled={!schemaId}
          >
            新建规则组
          </Button>
        </Space>
      </div>

      {!schemaId && (
        <Alert
          type="warning"
          message="请先选择一个语义空间"
          description="规则组必须归属于某个语义空间。请从管理面的空间列表进入后点击「规则管理」，或在 URL 中提供 schemaId 参数。"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={() => navigate('/spaces')}>
              前往空间列表
            </Button>
          }
        />
      )}

      {/* Statistics Bar */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic title="规则组总数" value={stats.total} valueStyle={{ fontSize: 20 }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic title="启用中" value={stats.active} valueStyle={{ fontSize: 20, color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic title="决策类型" value={stats.decision} valueStyle={{ fontSize: 20, color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" style={{ textAlign: 'center', cursor: 'pointer' }} onClick={() => navigate('/spaces')}>
            <Statistic
              title="切换空间"
              value=" "
              prefix={<InfoCircleOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ fontSize: 14, color: '#1890ff' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Table */}
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索规则组名称/描述"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 240 }}
            allowClear
          />
          <Select
            placeholder="筛选类型"
            allowClear
            style={{ width: 130 }}
            value={typeFilter}
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
          size="middle"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          locale={{
            emptyText: schemaId ? (
              <div style={{ padding: '24px 0', color: '#999' }}>
                <BranchesOutlined style={{ fontSize: 32, color: '#d9d9d9', display: 'block', marginBottom: 8 }} />
                <div>暂无规则组</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  点击「导入」从 examples 导入示例规则，或点击「新建规则组」手动创建
                </div>
              </div>
            ) : '请先选择语义空间',
          }}
        />
      </Card>

      <Modal
        title="导入规则组"
        open={importModalVisible}
        onOk={handleImportOk}
        onCancel={() => {
          setImportModalVisible(false);
          setImportContent('');
        }}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
        width={680}
      >
        <Tabs
          activeKey={importActiveTab}
          onChange={setImportActiveTab}
          items={[
            {
              key: 'path',
              label: (
                <span>
                  <FolderOpenOutlined />
                  从文件路径导入
                </span>
              ),
              children: (
                <Form layout="vertical" style={{ marginTop: 8 }}>
                  <Form.Item label="选择预设示例">
                    <Select
                      style={{ width: '100%' }}
                      placeholder="选择示例文件"
                      onChange={(val) => setImportPath(val)}
                      options={EXAMPLE_PATHS.map((p) => ({
                        label: (
                          <div>
                            <div style={{ fontWeight: 500 }}>{p.label}</div>
                            <div style={{ fontSize: 11, color: '#999' }}>{p.value}</div>
                          </div>
                        ),
                        value: p.value,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item label="或手动输入路径">
                    <Input
                      value={importPath}
                      onChange={(e) => setImportPath(e.target.value)}
                      placeholder="examples/supply_chain_finance/schema.yaml"
                      prefix={<FolderOpenOutlined />}
                    />
                  </Form.Item>
                  <Alert
                    type="info"
                    showIcon
                    message="路径导入说明"
                    description="此操作会将 Schema 文件（包含 L1-L4 层级定义）导入到当前语义空间。导入规则组时，请确保相关 Schema 已导入。"
                    style={{ marginTop: 8 }}
                  />
                </Form>
              ),
            },
            {
              key: 'content',
              label: (
                <span>
                  <ImportOutlined />
                  粘贴 YAML 内容
                </span>
              ),
              children: (
                <Form layout="vertical" style={{ marginTop: 8 }}>
                  <Form.Item
                    label="YAML 内容"
                    required
                    help="粘贴规则组的 YAML 定义（rule_group: ... 格式）"
                  >
                    <TextArea
                      rows={14}
                      value={importContent}
                      onChange={(e) => setImportContent(e.target.value)}
                      placeholder={`rule_group:
  name: example_rule
  type: decision
  priority: 100
  applies_to:
    fact_objects:
      - Supplier
  inputs:
    - name: credit_score
      type: number
  outputs:
    - name: decision
      type: string
  steps:
    - name: check_score
      when:
        type: expression
        expression: "credit_score >= 80"
      then:
        operator: DECISION_TABLE
        params: {}`}
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                    />
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
        <Text type="secondary" style={{ fontSize: 11 }}>
          提示：导入的规则组将属于当前语义空间（{spaceName || schemaId || '未选择'}）
        </Text>
      </Modal>
    </div>
  );
};

export default RuleGroupListPage;
