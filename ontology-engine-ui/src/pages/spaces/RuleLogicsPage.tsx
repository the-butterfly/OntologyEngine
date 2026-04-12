// ontology-engine-ui/src/pages/spaces/RuleLogicsPage.tsx
// Rule logics management page

import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Tag, Space, Typography, Card, message, Modal, Form, Input, Select, InputNumber, Button, Segmented, Empty } from 'antd';
import { PlusOutlined, AppstoreOutlined, BarsOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import RuleChainDAG from '../../components/rule/RuleChainDAG';
import type { ColumnsType } from 'antd/es/table';
import type { RuleLogic } from '../../api/spaceApi';
import type { RuleChainGraphData } from '../../types/visualization';

const { Title } = Typography;

export default function RuleLogicsPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const {
    activeSpaceId,
    ruleDefinitions,
    ruleLogics,
    logicsLoading,
    loadRuleLogics,
    createRuleLogic,
    error,
    clearError,
  } = useSpaceStore();

  const [viewMode, setViewMode] = useState<'table' | 'dag'>('table');
  const [form] = Form.useForm();

  useEffect(() => {
    if (activeSpaceId) {
      loadRuleLogics(activeSpaceId);
    }
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  // Transform rule logics to DAG data
  const dagData = useMemo((): RuleChainGraphData | null => {
    if (!ruleLogics.length || !ruleDefinitions.length) return null;

    const nodes = ruleLogics.map(logic => {
      const def = ruleDefinitions.find(d => d.id === logic.definition_id);
      return {
        id: logic.id,
        position: { x: 0, y: 0 },
        data: {
          ruleId: logic.id,
          ruleName: logic.name || logic.id,
          ruleType: def?.rule_type || 'unknown',
          priority: logic.priority || def?.priority || 100,
          definitionId: logic.definition_id,
          definitionName: def?.name || def?.id || logic.definition_id,
          when: logic.when?.expression || null,
          thenAction: logic.then_action?.action_type || null,
          elseAction: logic.else_action?.action_type || null,
        },
      };
    });

    // Create edges from logic to its definition
    const edges = ruleLogics.map(logic => ({
      id: `${logic.definition_id}->${logic.id}`,
      source: logic.definition_id,
      target: logic.id,
      data: { type: 'logic_of' },
    }));

    return {
      dimension: 'rule_logic_view',
      nodes,
      edges,
      dimension_info: {
        name: '规则逻辑',
        description: '规则逻辑 DAG 视图',
        applicable_entities: [],
        rule_count: nodes.length,
      },
    };
  }, [ruleLogics, ruleDefinitions]);

  const handleCreate = async (values: any) => {
    if (!activeSpaceId) return;
    try {
      await createRuleLogic(activeSpaceId, {
        id: values.id,
        definition_id: values.definition_id,
        name: values.name,
        applicable_conditions: [],
        when: null,
        then_action: null,
        else_action: null,
        version: 1,
        environment: 'default',
      });
      message.success('规则逻辑创建成功');
    } catch {
      // Error handled by store
    }
  };

  const showCreateModal = () => {
    Modal.confirm({
      title: '创建规则逻辑',
      icon: null,
      content: (
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="id" label="逻辑ID" rules={[{ required: true }]}>
            <Input placeholder="如 R001_logic_v1" />
          </Form.Item>
          <Form.Item name="definition_id" label="关联声明" rules={[{ required: true }]}>
            <Select
              placeholder="选择规则声明"
              options={ruleDefinitions.map((d) => ({ value: d.id, label: `${d.id} - ${d.name || '未命名'}` }))}
            />
          </Form.Item>
          <Form.Item name="name" label="名称">
            <Input placeholder="逻辑名称" />
          </Form.Item>
          <Form.Item name="version" label="版本" initialValue={1}>
            <InputNumber min={1} />
          </Form.Item>
        </Form>
      ),
      onOk: () => {
        form.validateFields().then(handleCreate);
      },
      onCancel: () => form.resetFields(),
    });
  };

  const getDefinitionName = (definitionId: string) => {
    const def = ruleDefinitions.find((d) => d.id === definitionId);
    return def?.name || def?.id || definitionId;
  };

  const columns: ColumnsType<RuleLogic> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 180,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text) => text || '-',
    },
    {
      title: '关联声明',
      dataIndex: 'definition_id',
      key: 'definition_id',
      render: (id) => <Tag color="blue">{getDefinitionName(id)}</Tag>,
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
      render: (v) => <Tag>v{v}</Tag>,
    },
    {
      title: '环境',
      dataIndex: 'environment',
      key: 'environment',
      width: 100,
    },
    {
      title: '条件',
      dataIndex: 'when',
      key: 'when',
      render: (when: any) => when?.expression ? <Tag>有</Tag> : '-',
    },
    {
      title: '动作',
      dataIndex: 'then_action',
      key: 'then_action',
      render: (action: any) => action?.action_type || '-',
    },
  ];

  return (
    <div>
      <Card
        title={<Title level={5}>规则逻辑</Title>}
        extra={
          <Space>
            <Segmented
              value={viewMode}
              onChange={(v) => setViewMode(v as 'table' | 'dag')}
              options={[
                { value: 'table', icon: <BarsOutlined />, label: '表格' },
                { value: 'dag', icon: <AppstoreOutlined />, label: 'DAG 图' },
              ]}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={showCreateModal}>
              创建逻辑
            </Button>
          </Space>
        }
      >
        {viewMode === 'table' ? (
          <Table
            columns={columns}
            dataSource={ruleLogics}
            rowKey="id"
            loading={logicsLoading}
            pagination={{ pageSize: 10 }}
          />
        ) : (
          dagData ? (
            <div style={{ height: 400 }}>
              <RuleChainDAG chainData={dagData} />
            </div>
          ) : (
            <Empty description="暂无规则逻辑数据" />
          )
        )}
      </Card>
    </div>
  );
}
