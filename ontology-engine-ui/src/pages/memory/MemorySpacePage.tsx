import React, { useEffect } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Spin, Result, Button } from 'antd';
import { useSpaceStore } from '../../store/spaceStore';

const MemorySpacePage: React.FC = () => {
  const navigate = useNavigate();
  const { spaces, spacesLoading: loading, error, loadSpaces } = useSpaceStore();

  useEffect(() => {
    if (spaces.length === 0 && !loading) {
      loadSpaces?.();
    }
  }, [spaces.length, loading, loadSpaces]);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="正在进入 Agent Memory..." />
      </div>
    );
  }

  if (error) {
    return (
      <Result
        status="error"
        title="加载失败"
        subTitle={error}
        extra={
          <Button type="primary" onClick={() => navigate('/spaces')}>
            前往语义空间
          </Button>
        }
      />
    );
  }

  if (spaces.length > 0) {
    const firstSpaceId = spaces[0].id;
    return <Navigate to={`/spaces/${firstSpaceId}/memory`} replace />;
  }

  return (
    <Result
      status="info"
      title="暂无语义空间"
      subTitle="请先创建语义空间以使用 Agent Memory 功能"
      extra={
        <Button type="primary" onClick={() => navigate('/spaces')}>
          前往创建
        </Button>
      }
    />
  );
};

export default MemorySpacePage;
