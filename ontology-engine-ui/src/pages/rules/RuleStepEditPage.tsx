// ontology-engine-ui/src/pages/rules/RuleStepEditPage.tsx
// Redirects to RuleGroupDetailPage with editStepId, passing step data via navigate state

import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Spin, message } from 'antd';
import { RuleGroupLayout } from './RuleGroupLayout';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { RuleStep } from '../../types/rule';

export const RuleStepEditPage: React.FC = () => {
  const { groupId, stepId } = useParams<{ groupId: string; stepId: string }>();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!groupId || !stepId) {
      navigate(`/rules/${groupId}?schemaId=${schemaId}`);
      return;
    }

    // Fetch the rule group's steps to find the step by id
    const fetchAndRedirect = async () => {
      try {
        const steps = await ruleGroupsApi.getSteps(groupId, schemaId);
        const step = steps.find((s: RuleStep) => s.id === stepId);
        if (step) {
          navigate(`/rules/${groupId}?schemaId=${schemaId}&editStepId=${stepId}`, { replace: true });
        } else {
          message.error('步骤不存在');
          navigate(`/rules/${groupId}?schemaId=${schemaId}`, { replace: true });
        }
      } catch {
        message.error('无法加载步骤');
        navigate(`/rules/${groupId}?schemaId=${schemaId}`, { replace: true });
      } finally {
        setLoading(false);
      }
    };

    fetchAndRedirect();
  }, [groupId, stepId, schemaId, navigate]);

  return (
    <RuleGroupLayout breadcrumbs={[
      { label: '规则组', path: `/rules/${groupId}?schemaId=${schemaId}` },
      { label: '编辑规则实例' },
    ]}>
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" tip={loading ? '正在加载...' : '正在跳转...'} />
      </div>
    </RuleGroupLayout>
  );
};

export default RuleStepEditPage;
