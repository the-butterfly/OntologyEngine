// Rule logic list component - displays rule logics in a table
import React, { useMemo } from 'react';
import {
  Table,
  Button,
  Space,
  Tag,
  Popconfirm,
  Empty,
} from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { L4RuleLogic } from '../../hooks/useL4Rules';

interface LogicListItem {
  id: string;
  name: string;
  definition_id: string;
  priority: number;
  action_type: string;
  status: 'configured' | 'unconfigured';
}

interface RuleLogicListProps {
  definitionId: string;
  logics: L4RuleLogic[];
  onEditLogic: (logicId: string) => void;
  onDeleteLogic: (logicId: string) => Promise<void>;
  onAddLogic: () => void;
  deletingLogicId?: string | null;
}

export const RuleLogicList: React.FC<RuleLogicListProps> = ({
  definitionId,
  logics,
  onEditLogic,
  onDeleteLogic,
  onAddLogic,
  deletingLogicId,
}) => {
  // ─── 构建规则逻辑列表 ─────────────────────────────────────────────────────
  const relatedLogics = useMemo(() => {
    return logics
      .filter((l) => l.definition_id === definitionId)
      .sort((a, b) => (a.priority || 0) - (b.priority || 0));
  }, [logics, definitionId]);

  const logicListItems: LogicListItem[] = useMemo(() => {
    return relatedLogics.map((logic) => ({
      id: logic.id,
      name: logic.name || logic.id,
      definition_id: logic.definition_id,
      priority: logic.priority || 100,
      action_type: logic.then_action?.action_type || '-',
      status: logic.then_action ? 'configured' : 'unconfigured',
    }));
  }, [relatedLogics]);

  // ─── 表格列定义 ─────────────────────────────────────────────────────────────
  const logicColumns: ColumnsType<LogicListItem> = [
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: number) => <Tag>{priority}</Tag>,
    },
    {
      title: '逻辑名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '算子类型',
      dataIndex: 'action_type',
      key: 'action_type',
      width: 120,
      render: (type: string) => (
        <Tag color={type === 'dag_execute' ? 'blue' : 'default'}>
          {type === 'dag_execute' ? 'DAG执行' : type}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={status === 'configured' ? 'green' : 'orange'}>
          {status === 'configured' ? '已配置' : '未配置'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: LogicListItem) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => onEditLogic(record.id)}
            title="编辑逻辑"
          />
          <Popconfirm
            title="确定删除此逻辑？"
            onConfirm={() => onDeleteLogic(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deletingLogicId === record.id}
              title="删除"
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ─── 渲染 ───────────────────────────────────────────────────────────────────
  return (
    <Table
      columns={logicColumns}
      dataSource={logicListItems}
      rowKey="id"
      size="small"
      pagination={false}
      scroll={{ y: 'calc(100% - 40px)' }}
      locale={{
        emptyText: (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span style={{ color: '#8c8c8c' }}>
                暂无规则逻辑
                <Button type="link" size="small" onClick={onAddLogic}>
                  点击新增
                </Button>
              </span>
            }
            style={{ padding: '40px 0' }}
          />
        ),
      }}
    />
  );
};

export default RuleLogicList;
