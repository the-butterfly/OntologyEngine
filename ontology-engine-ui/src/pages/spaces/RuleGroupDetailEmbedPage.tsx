// ontology-engine-ui/src/pages/spaces/RuleGroupDetailEmbedPage.tsx
// 规则组详情嵌入式页面 —— 内嵌于 SpaceDetailPage 右侧内容区
//
// 交互设计（2026-04-17）：
//   - "规则定义"：编辑 Schema 声明（基础信息、作用对象、输入输出要素）
//   - "编辑逻辑"：打开独立的 DAG 画布页面，编排计算节点
//   - 两个动作完全分离，规则逻辑通过路由跳转到 RuleLogicCanvasPage

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Tag, Space, Breadcrumb, Alert } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import RuleGroupDetailPanel from '../../components/rule/RuleGroupDetailPanel';

export interface RuleGroupDetailEmbedPageProps {
  spaceId?: string;
  groupId?: string;  // 在 L4 中为 definitionId
}

export const RuleGroupDetailEmbedPage: React.FC<RuleGroupDetailEmbedPageProps> = ({
  spaceId: propSpaceId,
  groupId: propGroupId,
}) => {
  const { spaceId: paramSpaceId, groupId: paramGroupId } = useParams<{
    spaceId: string;
    groupId: string;
  }>();
  const navigate = useNavigate();

  const spaceId = propSpaceId || paramSpaceId || '';
  const definitionId = decodeURIComponent(propGroupId || paramGroupId || '');

  const handleBackToList = () => {
    navigate(`/spaces/${spaceId}/rules`);
  };

  // ─── 规则类型配置 ──────────────────────────────────────────────────────────
  // Note: TYPE_COLOR and TYPE_LABEL are now accessed via the panel component
  // which derives them from the definition data

  // ─── 面包屑 ────────────────────────────────────────────────────────────────
  // Note: The breadcrumb is now handled within RuleGroupDetailPanel
  // This wrapper focuses on the header area

  // ─── 渲染 ───────────────────────────────────────────────────────────────────
  return (
    <div
      data-a2ui-component="rule-group-detail-embed"
      data-a2ui-space-id={spaceId}
      data-a2ui-group-id={definitionId}
      data-source="schema-l4"
      style={{ height: '100%' }}
    >
      {/* ── 内嵌子面包屑 + 返回按钮区域 ── */}
      {/* Note: This header section could be extracted further if needed */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginBottom: 16,
          padding: '8px 0',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Button
          type="text"
          size="small"
          icon={<ArrowLeftOutlined />}
          onClick={handleBackToList}
          style={{ color: '#666', padding: '0 4px' }}
        >
          规则列表
        </Button>
        <span style={{ color: '#d9d9d9' }}>/</span>
        <Breadcrumb
          style={{ flex: 1 }}
          items={[
            {
              title: (
                <span
                  style={{ cursor: 'pointer', color: '#1890ff' }}
                  onClick={handleBackToList}
                >
                  L4 业务规则
                </span>
              ),
            },
            { title: definitionId || '加载中...' },
          ]}
        />
      </div>

      {/* ── 详情面板 ── */}
      <RuleGroupDetailPanel
        spaceId={spaceId}
        definitionId={definitionId}
      />
    </div>
  );
};

export default RuleGroupDetailEmbedPage;
