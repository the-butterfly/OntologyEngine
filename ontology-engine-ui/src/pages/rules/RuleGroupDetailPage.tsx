// ontology-engine-ui/src/pages/rules/RuleGroupDetailPage.tsx
// Rule group detail page with three-column layout

import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card, Row, Col, Spin, message, Button, Space } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { RuleGroupLayout } from './RuleGroupLayout';
import RuleGroupForm from '../../components/rule/RuleGroupForm';
import RuleStepList from '../../components/rule/RuleStepList';
import { useRuleGroups } from '../../hooks/useRuleGroups';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { RuleGroup, RuleStep } from '../../types/rule';

export const RuleGroupDetailPage: React.FC = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';

  const { ruleGroups, loading, error, fetchGroups } = useRuleGroups(schemaId);

  const [steps, setSteps] = useState<RuleStep[]>([]);
  const [loadingSteps, setLoadingSteps] = useState(false);
  const [currentGroup, setCurrentGroup] = useState<RuleGroup | null>(null);

  useEffect(() => {
    if (schemaId) {
      fetchGroups();
    }
  }, [schemaId, fetchGroups]);

  // Fetch rule group by ID
  useEffect(() => {
    if (!groupId || ruleGroups.length === 0) return;

    const found = ruleGroups.find(g => g.id === groupId);
    setCurrentGroup(found || null);
  }, [groupId, ruleGroups]);

  // Fetch steps when we have the group
  useEffect(() => {
    if (!currentGroup) return;

    const fetchSteps = async () => {
      setLoadingSteps(true);
      try {
        const ruleSteps = await ruleGroupsApi.getSteps(currentGroup.name, schemaId);
        setSteps(ruleSteps);
      } catch {
        message.error('Failed to load rule steps');
      } finally {
        setLoadingSteps(false);
      }
    };

    fetchSteps();
  }, [currentGroup, schemaId]);

  const handleStepsChange = (newSteps: RuleStep[]) => {
    setSteps(newSteps);
  };

  const handleReorder = async (stepIds: string[]) => {
    if (!currentGroup) return;
    await ruleGroupsApi.reorderSteps(currentGroup.name, stepIds, schemaId);
  };

  const handleSaveGroup = async (data: Partial<RuleGroup>) => {
    if (!currentGroup) return;
    await ruleGroupsApi.update(currentGroup.id, data, schemaId);
    fetchGroups();
  };

  const handleEditStep = (step: RuleStep) => {
    // Could navigate to step edit page
    console.log('Edit step:', step);
  };

  const handleDeleteStep = async (stepId: string) => {
    if (!currentGroup) return;
    await ruleGroupsApi.deleteStep(currentGroup.name, stepId, schemaId);
    setSteps(steps.filter(s => s.id !== stepId));
  };

  if (loading) {
    return (
      <RuleGroupLayout breadcrumbs={[{ label: '加载中...' }]}>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
        </div>
      </RuleGroupLayout>
    );
  }

  if (error) {
    message.error(error);
  }

  if (!currentGroup) {
    return (
      <RuleGroupLayout breadcrumbs={[{ label: '规则组详情' }]}>
        <Card>规则组不存在</Card>
      </RuleGroupLayout>
    );
  }

  return (
    <RuleGroupLayout
      breadcrumbs={[
        { label: '规则组', path: `/rules?schemaId=${schemaId}` },
        { label: currentGroup.name },
      ]}
    >
      <Row gutter={16}>
        {/* Left column: Framework config */}
        <Col span={8}>
          <Card
            title="规则组框架"
            style={{ height: '100%' }}
            extra={
              <Button size="small" onClick={() => fetchGroups()}>
                刷新
              </Button>
            }
          >
            <RuleGroupForm
              schemaId={schemaId}
              ruleGroup={currentGroup}
              onSave={handleSaveGroup}
            />
          </Card>
        </Col>

        {/* Middle column: Rule step list */}
        <Col span={10}>
          {loadingSteps ? (
            <Card title="规则实例">
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <Spin />
              </div>
            </Card>
          ) : (
            <RuleStepList
              schemaId={schemaId}
              ruleGroupName={currentGroup.name}
              steps={steps}
              inputs={currentGroup.inputs}
              outputs={currentGroup.outputs}
              onStepsChange={handleStepsChange}
              onEditStep={handleEditStep}
              onDeleteStep={handleDeleteStep}
              onReorder={handleReorder}
            />
          )}
        </Col>

        {/* Right column: Element DAG */}
        <Col span={6}>
          <Card title="要素依赖图" style={{ height: '100%' }}>
            {/* TODO: ElementDAGGraph component - integrate with DAG visualization */}
            <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
              <p>要素依赖图</p>
              <p style={{ fontSize: 12 }}>
                展示输入要素 → 规则步骤 → 输出要素的依赖关系
              </p>
            </div>
          </Card>
        </Col>
      </Row>
    </RuleGroupLayout>
  );
};

export default RuleGroupDetailPage;