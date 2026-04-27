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

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Typography, Divider, Space, Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useL4Rules } from '../../hooks/useL4Rules';
import { spaceApi } from '../../api/spaceApi';
import RuleList from '../../components/rule/RuleList';
import RuleEditor from '../../components/rule/RuleEditor';
import type { L4RuleDefinition } from '../../hooks/useL4Rules';

const { Title, Text } = Typography;

export interface RulesEmbedPageProps {
  /** 由外层路由或 A2UI 宿主注入的语义空间 ID */
  spaceId?: string;
}

export const RulesEmbedPage: React.FC<RulesEmbedPageProps> = ({ spaceId: propSpaceId }) => {
  const { spaceId: paramSpaceId } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();

  // 优先使用 prop 传入的 spaceId（A2UI 场景），其次从 URL param 获取
  const spaceId = propSpaceId || paramSpaceId || '';
  const [spaceName, setSpaceName] = useState<string>('');

  const { fetchRules } = useL4Rules(spaceId);

  // ─── 加载数据 ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (spaceId) {
      spaceApi.getSpace(spaceId).then((space) => {
        if (space) setSpaceName(space.name || spaceId);
      }).catch(() => setSpaceName(spaceId));
    }
  }, [spaceId]);

  // ─── 事件处理 ───────────────────────────────────────────────────────────────
  const handleEditRule = (def: L4RuleDefinition) => {
    navigate(`/spaces/${spaceId}/rules/${encodeURIComponent(def.id)}`);
  };

  const handleDeleteRule = async (def: L4RuleDefinition) => {
    // Delete is handled by RuleList component via useL4Rules hook
  };

  const handleCreateRule = () => {
    navigate(`/spaces/${spaceId}/rules/new`);
  };

  const handleImportSuccess = () => {
    fetchRules();
  };

  // ─── 渲染 ────────────────────────────────────────────────────────────────────
  return (
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
          <RuleEditor spaceId={spaceId} spaceName={spaceName} onImportSuccess={handleImportSuccess} />
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={handleCreateRule}
            disabled={!spaceId}
          >
            新建规则
          </Button>
        </Space>
      </div>

      <Divider style={{ margin: '0 0 16px' }} />

      {/* ── 规则列表 ── */}
      <RuleList
        spaceId={spaceId}
        spaceName={spaceName}
        onEditRule={handleEditRule}
        onDeleteRule={handleDeleteRule}
      />
    </div>
  );
};

export default RulesEmbedPage;
