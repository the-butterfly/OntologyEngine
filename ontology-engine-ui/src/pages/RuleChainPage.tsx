import { useEffect, useRef, useState, useCallback } from 'react';
import { Select, Spin, Card, Space, Tag, Empty, Typography, Tabs, Badge } from 'antd';
import { fetchRuleChainGraph, simulateExecution } from '../api/visualization';
import RuleChainDAG from '../components/rule/RuleChainDAG';
import ExecutionReplay from '../components/rule/ExecutionReplay';
import StepDetailPanel from '../components/rule/StepDetailPanel';
import type { RuleChainGraphData, ExecutionStepSnapshot, SimulationResult } from '../types/visualization';
import '../App.css';

const { Text } = Typography;

const DIMENSIONS = [
  { label: '融资授信评估', value: 'credit_assessment' },
  { label: '交易监控', value: 'transaction_monitoring' },
  { label: '风险预警', value: 'risk_early_warning' },
];

export default function RuleChainPage() {
  const [dimension, setDimension] = useState('credit_assessment');
  const [chainData, setChainData] = useState<RuleChainGraphData | null>(null);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('dag');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [chain, sim] = await Promise.all([
        fetchRuleChainGraph(dimension),
        simulateExecution({ entity_id: 'SUP_2024_001', dimension, dry_run: true }),
      ]);
      setChainData(chain);
      setSimulation(sim);
      setCurrentStep(0);
    } catch (e) {
      console.error('Failed to load rule chain:', e);
    } finally {
      setLoading(false);
    }
  }, [dimension]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleStepChange = (step: number) => {
    setCurrentStep(step);
  };

  const currentSnapshot = currentStep > 0 ? simulation?.steps?.[currentStep - 1] : null;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <Space size="large">
          <Space>
            <span style={{ fontWeight: 500 }}>评估维度:</span>
            <Select
              value={dimension}
              onChange={setDimension}
              options={DIMENSIONS}
              style={{ width: 180 }}
              size="middle"
            />
          </Space>
          
          {chainData?.dimension_info && (
            <Space size="middle">
              <Badge 
                count={chainData.dimension_info.rule_count} 
                style={{ backgroundColor: '#1890ff' }} 
              />
              <Text type="secondary" style={{ fontSize: 13 }}>
                条规则
              </Text>
              {chainData.dimension_info.description && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ({chainData.dimension_info.description})
                </Text>
              )}
            </Space>
          )}
        </Space>
      </div>

      {/* Body */}
      <div className="page-body">
        {/* Left: Visualization */}
        <div className="graph-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            style={{ margin: '0 16px' }}
            items={[
              { 
                key: 'dag', 
                label: '规则DAG图',
                children: null,
              },
              { 
                key: 'list', 
                label: '执行列表',
                children: null,
              },
            ]}
          />
          
          <div style={{ flex: 1, overflow: 'hidden', padding: '0 16px 16px' }}>
            {loading ? (
              <div className="loading-container">
                <Spin size="large">
                  <div style={{ padding: '40px 0' }}>加载规则链...</div>
                </Spin>
              </div>
            ) : activeTab === 'dag' && chainData ? (
              <RuleChainDAG
                chainData={chainData}
                executionSteps={simulation?.steps || []}
                currentStep={currentStep}
                onNodeClick={(nodeId) => {
                  const stepIndex = simulation?.steps?.findIndex(s => s.rule_id === nodeId);
                  if (stepIndex !== undefined && stepIndex >= 0) {
                    setCurrentStep(stepIndex + 1);
                  }
                }}
              />
            ) : activeTab === 'list' && simulation?.steps ? (
              <RuleChainList
                steps={simulation.steps}
                currentStep={currentStep}
                onStepClick={handleStepChange}
              />
            ) : (
              <Empty description="暂无数据" />
            )}
          </div>
          
          {/* Execution Replay Controls */}
          {simulation?.steps && simulation.steps.length > 0 && (
            <ExecutionReplay
              steps={simulation.steps}
              currentStep={currentStep}
              onStepChange={handleStepChange}
            />
          )}
        </div>

        {/* Right: Detail Panel */}
        <div className="detail-panel">
          {currentSnapshot ? (
            <StepDetailPanel snapshot={currentSnapshot} />
          ) : (
            <Empty
              description={
                <span>
                  <div style={{ fontSize: 14, color: '#666', marginBottom: 8 }}>
                    选择步骤查看详情
                  </div>
                  <div style={{ fontSize: 12, color: '#999' }}>
                    点击执行时间线上的步骤<br/>
                    或点击DAG图中的节点<br/>
                    查看规则执行详情
                  </div>
                </span>
              }
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// List view as fallback
function RuleChainList({
  steps,
  currentStep,
  onStepClick,
}: {
  steps: ExecutionStepSnapshot[];
  currentStep: number;
  onStepClick: (step: number) => void;
}) {
  return (
    <div style={{ 
      height: '100%', 
      overflowY: 'auto',
      padding: '0 8px',
    }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {steps.map((step, idx) => {
          const stepNum = idx + 1;
          const isActive = stepNum === currentStep;
          const isPast = stepNum < currentStep;
          
          return (
            <Card
              key={step.rule_id}
              size="small"
              onClick={() => onStepClick(stepNum)}
              style={{
                cursor: 'pointer',
                borderColor: isActive ? '#1890ff' : isPast ? '#b7eb8f' : '#f0f0f0',
                background: isActive ? '#e6f7ff' : '#fff',
                boxShadow: isActive ? '0 2px 8px rgba(24,144,255,0.2)' : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: step.status === 'passed' ? '#f6ffed' : 
                             step.status === 'failed' ? '#fff1f0' : 
                             step.status === 'skipped' ? '#fff7e6' : '#f0f0f0',
                  border: `2px solid ${
                    step.status === 'passed' ? '#52c41a' : 
                    step.status === 'failed' ? '#f5222d' : 
                    step.status === 'skipped' ? '#fa8c16' : '#d9d9d9'
                  }`,
                  color: step.status === 'passed' ? '#52c41a' : 
                        step.status === 'failed' ? '#f5222d' : 
                        step.status === 'skipped' ? '#fa8c16' : '#999',
                  fontSize: 12,
                  fontWeight: 600,
                }}>
                  {stepNum}
                </div>
                
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>
                    {step.rule_name}
                  </div>
                  <div style={{ fontSize: 11, color: '#999' }}>
                    {step.rule_id}
                  </div>
                </div>
                
                <Space direction="vertical" size={0} style={{ alignItems: 'flex-end' }}>
                  <Tag size="small" style={{ fontSize: 10 }}>
                    {step.duration_ms.toFixed(1)}ms
                  </Tag>
                  {step.condition_result !== null && (
                    <span style={{ 
                      fontSize: 11,
                      color: step.condition_result ? '#52c41a' : '#f5222d',
                    }}>
                      {step.condition_result ? '✓ 通过' : '✗ 未通过'}
                    </span>
                  )}
                </Space>
              </div>
              
              {step.condition_expression && (
                <div style={{
                  marginTop: 8,
                  padding: '6px 10px',
                  background: '#fafafa',
                  borderRadius: 4,
                  fontSize: 11,
                  color: '#666',
                  fontFamily: 'monospace',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {step.condition_expression}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
