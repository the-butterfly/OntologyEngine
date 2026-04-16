// ontology-engine-ui/src/pages/rules/RuleGroupDetailPage.tsx
// Rule group detail page with three-column layout

import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Card, Row, Col, Spin, message, Button } from 'antd';
import { RuleGroupLayout } from './RuleGroupLayout';
import RuleGroupForm from '../../components/rule/RuleGroupForm';
import RuleStepList from '../../components/rule/RuleStepList';
import RuleChainDAG from '../../components/rule/RuleChainDAG';
import { useRuleGroups } from '../../hooks/useRuleGroups';
import { ruleGroupsApi } from '../../api/ruleGroups';
import type { RuleGroup, RuleStep } from '../../types/rule';
import type { RuleChainGraphData } from '../../types/visualization';

export const RuleGroupDetailPage: React.FC = () => {
  const { groupId } = useParams<{ groupId: string }>();
  const [searchParams] = useSearchParams();
  const schemaId = searchParams.get('schemaId') || '';

  const { ruleGroups, loading, error, fetchGroups } = useRuleGroups(schemaId);

  const [steps, setSteps] = useState<RuleStep[]>([]);
  const [loadingSteps, setLoadingSteps] = useState(false);
  const [currentGroup, setCurrentGroup] = useState<RuleGroup | null>(null);
  const [initialEditStep, setInitialEditStep] = useState<RuleStep | null>(null);
  const [highlightNodeId, setHighlightNodeId] = useState<string | undefined>(undefined);
  // Guard flag so the deep-link effect only fires on mount (editStepId in URL)
  const editStepIdProcessedRef = React.useRef(false);

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

  // Respond to pendingSetup from RuleGroupCreatePage redirect
  useEffect(() => {
    const pendingSetup = searchParams.get('pendingSetup') === 'true';
    if (pendingSetup && currentGroup) {
      message.info('请先完成规则组框架配置（作用对象/适用场景/I/O要素）');
    }
  }, [searchParams, currentGroup]);

  // Transform steps + inputs + outputs to RuleChainGraphData for the DAG
  const dagData = useMemo((): RuleChainGraphData | null => {
    if (!currentGroup || !steps.length) return null;

    const nodes: RuleChainGraphData['nodes'] = [];
    const edges: RuleChainGraphData['edges'] = [];

    // Virtual INPUT nodes (from group inputs)
    (currentGroup.inputs || []).forEach((input, idx) => {
      nodes.push({
        id: `INPUT:${input.name}`,
        position: { x: 100, y: 80 * idx },
        data: {
          ruleId: `INPUT:${input.name}`,
          ruleName: input.name,
          ruleType: 'input',
          priority: 0,
        },
      });
    });

    // STEP nodes
    steps.forEach((step, idx) => {
      nodes.push({
        id: step.id,
        position: { x: 300, y: 80 * idx },
        data: {
          ruleId: step.id,
          ruleName: step.name,
          ruleType: step.then?.operator?.toLowerCase() || 'compute',
          priority: idx + 1,
          when: step.when?.type === 'expression' ? step.when.expression : null,
        },
      });
      // Infer edges from inputs to step (heuristic: expression references input name)
      (currentGroup.inputs || []).forEach(input => {
        const expr = step.when?.type === 'expression' ? step.when.expression : '';
        if (expr.includes(input.name)) {
          edges.push({
            id: `EDGE:${input.name}->${step.id}`,
            source: `INPUT:${input.name}`,
            target: step.id,
            data: { type: 'input_ref' },
          });
        }
      });
    });

    // Virtual OUTPUT nodes (from group outputs)
    (currentGroup.outputs || []).forEach((output, idx) => {
      nodes.push({
        id: `OUTPUT:${output.name}`,
        position: { x: 500, y: 80 * idx },
        data: {
          ruleId: `OUTPUT:${output.name}`,
          ruleName: output.name,
          ruleType: 'output',
          priority: 0,
        },
      });
      // Infer edges from step to output (heuristic: step produces output name in then.params or outputMapping)
      steps.forEach(step => {
        const thenParams = step.then?.params || {};
        const thenOutputMapping = step.then?.outputMapping || {};
        const thenValues = Object.values(thenOutputMapping);
        if (
          JSON.stringify(thenParams).includes(output.name) ||
          thenValues.includes(output.name)
        ) {
          edges.push({
            id: `EDGE:${step.id}->${output.name}`,
            source: step.id,
            target: `OUTPUT:${output.name}`,
            data: { type: 'output_produces' },
          });
        }
      });
    });

    return {
      dimension: 'element_dependency',
      nodes,
      edges,
      dimension_info: {
        name: '要素依赖图',
        description: '输入要素 → 规则步骤 → 输出要素',
        applicable_entities: [],
        rule_count: nodes.length,
      },
    };
  }, [currentGroup, steps]);

  const handleDAGNodeClick = (nodeId: string) => {
    // Input/output nodes are virtual — don't open editor for them
    if (nodeId.startsWith('INPUT:') || nodeId.startsWith('OUTPUT:')) return;
    const step = steps.find(s => s.id === nodeId);
    if (step) {
      setInitialEditStep(step);
      // Allow the deep-link effect to fire again for this new step
      editStepIdProcessedRef.current = false;
    }
  };
  // Deep link effect: only fires when URL has editStepId AND steps are loaded
  useEffect(() => {
    const editStepId = searchParams.get('editStepId');
    if (editStepId && steps.length > 0 && !editStepIdProcessedRef.current) {
      const step = steps.find(s => s.id === editStepId);
      if (step) {
        setInitialEditStep(step);
        editStepIdProcessedRef.current = true;
      }
    }
  }, [searchParams, steps]);

  const handleStepsChange = (newSteps: RuleStep[]) => {
    setSteps(newSteps);
  };

  const handleReorder = async (stepIds: string[]) => {
    if (!currentGroup) return;
    await ruleGroupsApi.reorderSteps(currentGroup.name, stepIds, schemaId);
  };

  const handleStepHover = (stepId: string | undefined) => {
    setHighlightNodeId(stepId);
  };

  const handleSaveGroup = async (data: Partial<RuleGroup>) => {
    if (!currentGroup) return;
    await ruleGroupsApi.update(currentGroup.id, data, schemaId);
    fetchGroups();
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
              onDeleteStep={handleDeleteStep}
              onReorder={handleReorder}
              initialEditStep={initialEditStep}
              onHoverStep={handleStepHover}
            />
          )}
        </Col>

        {/* Right column: Element DAG */}
        <Col span={6}>
          <Card title="要素依赖图" style={{ height: '100%' }}>
            {dagData && dagData.nodes.length > 0 ? (
              <RuleChainDAG
                chainData={dagData}
                onNodeClick={handleDAGNodeClick}
                highlightNodeId={highlightNodeId}
                editable={true}
                onReorder={handleReorder}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                <p>要素依赖图</p>
                <p style={{ fontSize: 12 }}>
                  配置 I/O 要素后自动展示要素依赖关系
                </p>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </RuleGroupLayout>
  );
};

export default RuleGroupDetailPage;