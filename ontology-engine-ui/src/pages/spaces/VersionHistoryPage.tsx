// ontology-engine-ui/src/pages/spaces/VersionHistoryPage.tsx
// Version history page

import React, { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Table, Button, Tag, Space, Typography, Card, message, Modal, Input } from 'antd';
import { PlusOutlined, RollbackOutlined } from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import type { ColumnsType } from 'antd/es/table';
import type { SpaceVersion } from '../../api/spaceApi';

const { Title } = Typography;
const { TextArea } = Input;

export default function VersionHistoryPage() {
  const { spaceId } = useParams<{ spaceId: string }>();
  const {
    activeSpaceId,
    activeSpace,
    versions,
    versionsLoading,
    loadVersions,
    createVersion,
    rollbackToVersion,
    error,
    clearError,
  } = useSpaceStore();

  const [description, setDescription] = React.useState('');

  useEffect(() => {
    if (activeSpaceId) {
      loadVersions(activeSpaceId);
    }
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const handleCreateVersion = async () => {
    if (!activeSpaceId) return;
    try {
      await createVersion(activeSpaceId, description);
      message.success('版本快照创建成功');
      setDescription('');
    } catch {
      // Error handled by store
    }
  };

  const handleRollback = (version: number) => {
    if (!activeSpaceId) return;
    Modal.confirm({
      title: '确认回滚',
      content: `确定要回滚到版本 ${version} 吗？当前版本的所有更改将会丢失。`,
      onOk: () => rollbackToVersion(activeSpaceId, version),
    });
  };

  const columns: ColumnsType<SpaceVersion> = [
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
      render: (v) => <Tag color="blue">v{v}</Tag>,
    },
    {
      title: '稳定',
      dataIndex: 'is_stable',
      key: 'is_stable',
      width: 80,
      render: (stable: boolean) => (
        <Tag color={stable ? 'green' : 'default'}>
          {stable ? '是' : '否'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '创建者',
      dataIndex: 'created_by',
      key: 'created_by',
      render: (by) => by || '-',
    },
    {
      title: '变更说明',
      dataIndex: 'change_description',
      key: 'change_description',
      render: (desc) => desc || '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          {record.version !== activeSpace?.version && (
            <Button
              size="small"
              icon={<RollbackOutlined />}
              onClick={() => handleRollback(record.version)}
            >
              回滚
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title={<Title level={5}>版本历史</Title>}
        extra={
          <Space>
            <TextArea
              placeholder="版本说明（可选）"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={1}
              style={{ width: 200 }}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateVersion}>
              创建快照
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={versions}
          rowKey="version"
          loading={versionsLoading}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
}
