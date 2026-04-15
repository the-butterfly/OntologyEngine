// ontology-engine-ui/src/pages/rules/RuleStepEditPage.tsx
// Page for editing a rule step

import React from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card } from 'antd';
import { RuleGroupLayout } from './RuleGroupLayout';

export const RuleStepEditPage: React.FC = () => {
  const { groupId, stepId } = useParams<{ groupId: string; stepId: string }>();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';

  return (
    <RuleGroupLayout breadcrumbs={[
      { label: '规则组', path: `/rules/${groupId}?schemaId=${schemaId}` },
      { label: '编辑规则实例' }
    ]}>
      <Card title={`编辑规则实例: ${stepId}`}>
        {/* TODO: RuleEditorModal with ConditionEditor, ActionEditor, SimulationPanel */}
        <p>规则编辑器 - 待实现</p>
        <p>groupId: {groupId}</p>
        <p>stepId: {stepId}</p>
        <p>schemaId: {schemaId}</p>
      </Card>
    </RuleGroupLayout>
  );
};

export default RuleStepEditPage;
