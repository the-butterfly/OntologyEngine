// ontology-engine-ui/src/pages/spaces/RulesEmbedPage.tsx
// 规则管理嵌入式页面 —— 内嵌于 SpaceDetailPage 右侧内容区
//
// 核心变化（2026-04-17）：
//   - 数据源从独立的 /v1/rule-groups 改为 Schema L4 API
//     /v1/management/{spaceId}/schema/L4/rules/definitions
//     /v1/management/{spaceId}/schema/L4/rules/logics
//   - 页面展示的规则组与 Schema L4 business_logic.rule_definitions 完全一致
//   - 旧数据层 useRuleGroups 已废弃，仅用于向后兼容
//
// 设计原则：
//   1. 不含独立的 Layout / 面包屑 / 返回按钮（由外层 SpaceDetailPage 提供）
//   2. 通过 spaceId URL param 获取上下文，而非 searchParams
//   3. 保留 embeddable 接口，未来可由 A2UI 直接渲染此卡片

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Select,
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
  Divider,
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
  RightOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useL4Rules } from '../../hooks/useL4Rules';
import { spaceApi } from '../../api/spaceApi';
import type { L4RuleDefinition } from '../../hooks/useL4Rules';

const { Title, Text } = Typography;
const { TextArea } = Input;

// ─── 预设示例路径 ─────────────────────────────────────────────────────────────
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

// ─── 规则类型配置 ─────────────────────────────────────────────────────────────
const TYPE_CONFIG: Record<string, { color: string; label: string }> = {
  constraint: { color: 'blue', label: '约束' },
  inference: { color: 'purple', label: '推理' },
  alert: { color: 'orange', label: '告警' },
  decision: { color: 'green', label: '决策' },
};

// ─── 组件 Props ──────────────────────────────────────────────────────────────
// A2UI 扩展点：外部宿主可通过这个 interface 注入 spaceId
export interface RulesEmbedPageProps {
  /** 由外层路由或 A2UI 宿主注入的语义空间 ID */
  spaceId?: string;
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────
export const RulesEmbedPage: React.FC<RulesEmbedPageProps> = ({ spaceId: propSpaceId }) => {
  const { spaceId: paramSpaceId } = useParams<{ spaceId: string }>();
  // 优先使用 prop 传入的 spaceId（A2UI 场景），其次从 URL param 获取
  const spaceId = propSpaceId || paramSpaceId || '';
  const navigate = useNavigate();

  const {
    loading,
    definitions,
    fetchRules,
    deleteDefinition,
    error,
    clearError,
  } = useL4Rules(spaceId);

  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importActiveTab, setImportActiveTab] = useState('path');
  const [importContent, setImportContent] = useState('');
  const [importPath, setImportPath] = useState('examples/supply_chain_finance/schema.yaml');
  const [importing, setImporting] = useState(false);
  const [spaceName, setSpaceName] = useState<string>('');

  // ─── 加载数据 ────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchRules();
    if (spaceId) {
      spaceApi.getSpace(spaceId).then((space) => {
        if (space) setSpaceName(space.name || spaceId);
      }).catch(() => setSpaceName(spaceId));
    }
  }, [spaceId, fetchRules]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error, clearError]);

  // ─── 过滤 ───────────────────────────────────────────────────────────────────
  const filteredDefinitions = useMemo(() => {
    return (definitions as L4RuleDefinition[]).filter((def) => {
      const matchText =
        def.name.toLowerCase().includes(searchText.toLowerCase()) ||
        (def.description || '').toLowerCase().includes(searchText.toLowerCase()) ||
        def.id.toLowerCase().includes(searchText.toLowerCase());
      const matchType = !typeFilter || def.rule_type === typeFilter;
      return matchText && matchType;
    });
  }, [definitions, searchText, typeFilter]);

  // ─── 统计数据 ───────────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const defs = definitions as L4RuleDefinition[];
    return {
      total: defs.length,
      active: defs.filter((d) => d.enabled).length,
      constraint: defs.filter((d) => d.rule_type === 'constraint').length,
      inference: defs.filter((d) => d.rule_type === 'inference').length,
      alert: defs.filter((d) => d.rule_type === 'alert').length,
      decision: defs.filter((d) => d.rule_type === 'decision').length,
    };
  }, [definitions]);

  // ─── 操作处理 ───────────────────────────────────────────────────────────────
  const handleEdit = useCallback(
    (def: L4RuleDefinition) => {
      // 内嵌路由：进入 /spaces/:spaceId/rules/:definitionId
      navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(def.id)}`);
    },
    [navigate, spaceId]
  );

  const handleCreate = useCallback(() => {
    navigate(`/spaces/${spaceId}/rules/new`);
  }, [navigate, spaceId]);

  const handleDelete = useCallback(
    async (def: L4RuleDefinition) => {
      try {
        await deleteDefinition(def.id);
        message.success(`规则「${def.name}」已删除`);
      } catch {
        // 由 hook 处理错误
      }
    },
    [deleteDefinition]
  );

  const handleExportYaml = useCallback(
    async (def: L4RuleDefinition) => {
      // L4 规则不支持导出为 Phase 2 YAML，直接展示 JSON
      const yamlContent = `# Schema L4 Rule Definition: ${def.id}\n# 导出时间: ${new Date().toLocaleString()}\n\nrule_definition:\n  id: ${def.id}\n  name: "${def.name}"\n  description: "${def.description || ''}"\n  rule_type: ${def.rule_type}\n  priority: ${def.priority}\n  applies_to:\n${def.applies_to.map((o) => `    - ${o}`).join('\n')}\n  inputs:\n${def.inputs.map((i) => `    - { id: ${i.id}, name: "${i.name}", type: ${i.type} }`).join('\n')}\n  outputs:\n${def.outputs.map((o) => `    - { id: ${o.id}, name: "${o.name}", type: ${o.type} }`).join('\n')}\n  enabled: ${def.enabled}`;
      const blob = new Blob([yamlContent], { type: 'text/yaml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${def.id}.yaml`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('YAML 已导出');
    },
    []
  );

  const handleImportByContent = useCallback(async () => {
    if (!importContent.trim()) {
      message.warning('请输入 YAML 内容');
      return;
    }
    message.info('L4 Schema YAML 请通过「从文件路径导入」使用 loadSchemaFromYaml 接口');
    setImportModalVisible(false);
    setImportContent('');
  }, [importContent]);

  const handleImportByPath = useCallback(async () => {
    if (!importPath.trim()) {
      message.warning('请选择或输入导入路径');
      return;
    }
    if (!spaceId) {
      message.warning('语义空间 ID 不能为空');
      return;
    }
    setImporting(true);
    try {
      await spaceApi.loadSchemaFromYaml(spaceId, importPath, true);
      message.success(`已从 ${importPath} 导入 Schema 数据`);
      setImportModalVisible(false);
      // 刷新规则列表
      fetchRules();
    } catch (e) {
      message.error(e instanceof Error ? e.message : '路径导入失败，请检查路径是否正确');
    } finally {
      setImporting(false);
    }
  }, [importPath, spaceId, fetchRules]);

  const handleImportOk = () => {
    if (importActiveTab === 'path') handleImportByPath();
    else handleImportByContent();
  };

  // ─── 表格列定义 ──────────────────────────────────────────────────────────────
  const columns = [
    {
      title: '规则名称',
      key: 'name',
      render: (_: unknown, record: L4RuleDefinition) => (
        <div>
          <Button
            type="link"
            style={{ padding: 0, fontWeight: 500 }}
            onClick={() => handleEdit(record)}
          >
            <BranchesOutlined style={{ marginRight: 6 }} />
            {record.name}
          </Button>
          <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
            ID: {record.id}
          </div>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 80,
      render: (type: string) => {
        const cfg = TYPE_CONFIG[type] || { color: 'default', label: type };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '作用对象',
      key: 'appliesTo',
      width: 140,
      render: (_: unknown, record: L4RuleDefinition) => {
        const objects = record.applies_to || [];
        return objects.length > 0 ? (
          <Space size={2} wrap>
            {objects.slice(0, 3).map((obj) => (
              <Tag key={obj} color="geekblue" style={{ fontSize: 11 }}>
                {obj}
              </Tag>
            ))}
            {objects.length > 3 && (
              <Tag style={{ fontSize: 11 }}>+{objects.length - 3}</Tag>
            )}
          </Space>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>
            未配置
          </Text>
        );
      },
    },
    {
      title: '适用分类',
      key: 'categorizations',
      width: 140,
      render: (_: unknown, record: L4RuleDefinition) => {
        const cats = record.applicable_categorizations || [];
        return cats.length > 0 ? (
          <Space size={2} wrap>
            {cats.slice(0, 2).map((cat) => (
              <Tag key={cat} color="purple" style={{ fontSize: 11 }}>
                {cat}
              </Tag>
            ))}
            {cats.length > 2 && (
              <Tag style={{ fontSize: 11 }}>+{cats.length - 2}</Tag>
            )}
          </Space>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>
            -
          </Text>
        );
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 70,
      sorter: (a: L4RuleDefinition, b: L4RuleDefinition) => a.priority - b.priority,
      render: (p: number) => (
        <Text style={{ fontSize: 12, fontFamily: 'monospace' }}>{p}</Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean) => (
        <Badge
          status={enabled ? 'success' : 'default'}
          text={enabled ? '启用' : '禁用'}
        />
      ),
    },
    {
      title: '逻辑数',
      key: 'logicCount',
      width: 70,
      render: (_: unknown, record: L4RuleDefinition) => (
        <Tooltip title={`关联 ${record.logic_ids?.length || 0} 个规则逻辑`}>
          <Tag color={record.logic_ids?.length ? 'cyan' : 'default'}>
            {record.logic_ids?.length || 0}
          </Tag>
        </Tooltip>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: { showTitle: false },
      render: (desc?: string) => (
        <Tooltip title={desc}>
          <Text ellipsis style={{ maxWidth: 160, fontSize: 12, color: '#666' }}>
            {desc || '-'}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: L4RuleDefinition) => (
        <Space size="small">
          <Tooltip title="编辑规则">
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
              onClick={() => handleExportYaml(record)}
            />
          </Tooltip>
          <Tooltip title="查看 Schema 声明">
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此规则？"
            description={`将同时删除关联的 ${record.logic_ids?.length || 0} 个规则逻辑，删除后无法恢复`}
            onConfirm={() => handleDelete(record)}
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
          <Tooltip title="进入详情">
            <Button
              type="text"
              size="small"
              icon={<RightOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  // ─── 渲染 ────────────────────────────────────────────────────────────────────
  return (
    // A2UI 扩展点：最外层 div 作为标准化卡片容器
    <div
      data-a2ui-component="rules-embed"
      data-a2ui-space-id={spaceId}
      data-source="schema-l4"
      style={{ height: '100%' }}
    >
      {/* ── 页头 ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
        }}
      >
        <div>
          <Title level={5} style={{ margin: 0 }}>
            L4 业务规则
          </Title>
          {spaceName && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {spaceName}
            </Text>
          )}
        </div>
        <Space>
          <Tooltip title="从 Schema YAML 文件导入（L1-L4 全量）">
            <Button
              icon={<ImportOutlined />}
              size="small"
              onClick={() => setImportModalVisible(true)}
            >
              导入 Schema
            </Button>
          </Tooltip>
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleCreate}
            disabled={!spaceId}
          >
            新建规则
          </Button>
        </Space>
      </div>

      <Divider style={{ margin: '0 0 16px' }} />

      {/* ── 统计条（按类型分布）─ */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <div
            style={{
              background: '#f0f9ff',
              borderRadius: 6,
              padding: '10px 14px',
              textAlign: 'center',
            }}
          >
            <Statistic
              title="规则总数"
              value={stats.total}
              valueStyle={{ fontSize: 20 }}
            />
          </div>
        </Col>
        <Col span={6}>
          <div
            style={{
              background: '#f6ffed',
              borderRadius: 6,
              padding: '10px 14px',
              textAlign: 'center',
            }}
          >
            <Statistic
              title="启用中"
              value={stats.active}
              valueStyle={{ fontSize: 20, color: '#52c41a' }}
            />
          </div>
        </Col>
        <Col span={6}>
          <div
            style={{
              background: '#fff7e6',
              borderRadius: 6,
              padding: '10px 14px',
              textAlign: 'center',
            }}
          >
            <Statistic
              title="约束/推理/告警"
              value={`${stats.constraint}/${stats.inference}/${stats.alert}`}
              valueStyle={{ fontSize: 18, color: '#fa8c16' }}
            />
          </div>
        </Col>
        <Col span={6}>
          <div
            style={{
              background: '#e6f4ff',
              borderRadius: 6,
              padding: '10px 14px',
              textAlign: 'center',
            }}
          >
            <Statistic
              title="决策类型"
              value={stats.decision}
              valueStyle={{ fontSize: 20, color: '#1890ff' }}
            />
          </div>
        </Col>
      </Row>

      {/* ── 过滤工具栏 ── */}
      <Space style={{ marginBottom: 12 }} wrap>
        <Input
          placeholder="搜索规则名称/描述/ID"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 220 }}
          size="small"
          allowClear
        />
        <Select
          placeholder="筛选类型"
          allowClear
          style={{ width: 120 }}
          size="small"
          value={typeFilter}
          onChange={setTypeFilter}
          options={[
            { label: '约束', value: 'constraint' },
            { label: '推理', value: 'inference' },
            { label: '告警', value: 'alert' },
            { label: '决策', value: 'decision' },
          ]}
        />
      </Space>

      {/* ── 数据表格（来源：Schema L4）─ */}
      <Table
        dataSource={filteredDefinitions as unknown as never[]}
        columns={columns as never[]}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{
          pageSize: 10,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 条（来源：Schema L4）`,
          size: 'small',
        }}
        locale={{
          emptyText: spaceId ? (
            <div style={{ padding: '20px 0', color: '#999' }}>
              <BranchesOutlined
                style={{ fontSize: 28, color: '#d9d9d9', display: 'block', marginBottom: 8 }}
              />
              <div>暂无 L4 业务规则</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                点击「导入 Schema」加载示例，或点击「新建规则」手动创建
              </div>
            </div>
          ) : (
            <Alert
              type="warning"
              message="未选择语义空间"
              description="请从语义空间列表选择一个空间后进入规则管理。"
              showIcon
              style={{ margin: '16px 0' }}
              action={
                <Button
                  size="small"
                  onClick={() => navigate('/spaces')}
                  icon={<InfoCircleOutlined />}
                >
                  前往空间列表
                </Button>
              }
            />
          ),
        }}
      />

      {/* ── 导入弹窗 ── */}
      <Modal
        title="导入 Schema（L1-L4 全量）"
        open={importModalVisible}
        onOk={handleImportOk}
        onCancel={() => {
          setImportModalVisible(false);
          setImportContent('');
        }}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
        width={660}
      >
        <Tabs
          activeKey={importActiveTab}
          onChange={setImportActiveTab}
          items={[
            {
              key: 'path',
              label: (
                <span>
                  <FolderOpenOutlined /> 从文件路径导入
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
                    description="此操作会将 Schema 文件（包含 L1-L4 层级定义）整体导入到当前语义空间，L4 业务规则将在导入后显示在此页面。"
                    style={{ marginTop: 8 }}
                  />
                </Form>
              ),
            },
            {
              key: 'content',
              label: (
                <span>
                  <ImportOutlined /> 粘贴 YAML 内容
                </span>
              ),
              children: (
                <Form layout="vertical" style={{ marginTop: 8 }}>
                  <Form.Item
                    label="YAML 内容"
                    required
                    help="粘贴 Schema YAML（L1-L4 完整格式），L4 业务规则将作为规则声明导入"
                  >
                    <TextArea
                      rows={12}
                      value={importContent}
                      onChange={(e) => setImportContent(e.target.value)}
                      placeholder={`schema_version: "2.0"\nsemantic_space:\n  id: "space_example"\n  name: "示例空间"\nbusiness_logic:\n  rule_definitions:\n    - id: RD001_example\n      name: "示例规则"\n      rule_type: constraint`}
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                    />
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
        <Text type="secondary" style={{ fontSize: 11 }}>
          提示：导入的 Schema 将属于当前语义空间（{spaceName || spaceId || '未选择'}），L4 规则自动同步到此页面
        </Text>
      </Modal>
    </div>
  );
};

export default RulesEmbedPage;
