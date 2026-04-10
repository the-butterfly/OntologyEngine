import { Button, Space, Typography, Progress, Tag, Tooltip } from 'antd';
import { 
  StepBackwardOutlined, 
  StepForwardOutlined, 
  CaretRightOutlined, 
  PauseOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { EXECUTION_STATUS_COLORS } from '../../utils/colorSchemes';
import type { ExecutionStepSnapshot } from '../../types/visualization';

const { Text } = Typography;

interface ExecutionReplayProps {
  steps: ExecutionStepSnapshot[];
  currentStep: number;
  onStepChange: (step: number) => void;
}

export default function ExecutionReplay({ steps, currentStep, onStepChange }: ExecutionReplayProps) {
  const totalSteps = steps.length;
  const progress = totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0;
  
  const currentSnapshot = currentStep > 0 ? steps[currentStep - 1] : null;
  
  const handlePlay = () => {
    if (currentStep < totalSteps) {
      onStepChange(currentStep + 1);
    }
  };
  
  const handleReset = () => {
    onStepChange(0);
  };

  return (
    <div className="execution-replay" style={{
      padding: '12px 16px',
      background: '#fff',
      borderTop: '1px solid #f0f0f0',
    }}>
      {/* Controls */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        marginBottom: 12,
      }}>
        <Space>
          <Tooltip title="重置">
            <Button 
              icon={<ReloadOutlined />} 
              size="small"
              onClick={handleReset}
            />
          </Tooltip>
          <Tooltip title="上一步">
            <Button 
              icon={<StepBackwardOutlined />} 
              size="small"
              onClick={() => onStepChange(Math.max(0, currentStep - 1))}
              disabled={currentStep <= 0}
            />
          </Tooltip>
          <Button 
            type={currentStep < totalSteps ? "primary" : "default"}
            icon={currentStep >= totalSteps ? <PauseOutlined /> : <CaretRightOutlined />} 
            size="small"
            onClick={handlePlay}
            disabled={currentStep >= totalSteps}
          >
            {currentStep >= totalSteps ? '完成' : '执行'}
          </Button>
          <Tooltip title="下一步">
            <Button 
              icon={<StepForwardOutlined />} 
              size="small"
              onClick={() => onStepChange(Math.min(totalSteps, currentStep + 1))}
              disabled={currentStep >= totalSteps}
            />
          </Tooltip>
        </Space>
        
        <Space size="middle">
          <Text type="secondary" style={{ fontSize: 12 }}>
            步骤 {currentStep} / {totalSteps}
          </Text>
          {currentSnapshot && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {currentSnapshot.duration_ms.toFixed(2)}ms
            </Text>
          )}
        </Space>
      </div>
      
      {/* Progress bar */}
      <div style={{ marginBottom: 12 }}>
        <Progress 
          percent={progress} 
          showInfo={false}
          strokeColor={{
            '0%': '#1890ff',
            '100%': '#52c41a',
          }}
          size="small"
        />
      </div>
      
      {/* Timeline */}
      <div style={{ 
        display: 'flex', 
        gap: 4,
        overflowX: 'auto',
        paddingBottom: 4,
      }}>
        {steps.map((step, idx) => {
          const stepNum = idx + 1;
          const isActive = stepNum === currentStep;
          const isPast = stepNum < currentStep;
          const status = isActive ? 'executing' : isPast ? step.status : 'pending';
          const color = EXECUTION_STATUS_COLORS[status] || '#D9D9D9';
          
          return (
            <Tooltip 
              key={step.rule_id}
              title={
                <div style={{ fontSize: 12 }}>
                  <div style={{ fontWeight: 600 }}>{step.rule_name}</div>
                  <div style={{ color: '#999' }}>{step.rule_id}</div>
                  {isPast && (
                    <div style={{ 
                      color: step.status === 'passed' ? '#52c41a' : 
                             step.status === 'failed' ? '#f5222d' : '#fa8c16',
                      marginTop: 4,
                    }}>
                      {step.status === 'passed' ? '✓ 通过' : 
                       step.status === 'failed' ? '✗ 失败' : '⊘ 跳过'}
                    </div>
                  )}
                </div>
              }
            >
              <div
                onClick={() => onStepChange(stepNum)}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  background: isActive ? color : isPast ? color : '#f0f0f0',
                  border: `2px solid ${isActive ? color : isPast ? color : '#d9d9d9'}`,
                  color: isActive || isPast ? '#fff' : '#999',
                  fontSize: 11,
                  fontWeight: 600,
                  flexShrink: 0,
                  transition: 'all 0.2s',
                  boxShadow: isActive ? `0 0 8px ${color}` : 'none',
                }}
              >
                {isPast ? (
                  step.status === 'passed' ? '✓' : 
                  step.status === 'failed' ? '✗' : '⊘'
                ) : (
                  stepNum
                )}
              </div>
            </Tooltip>
          );
        })}
      </div>
      
      {/* Current step info */}
      {currentSnapshot && (
        <div style={{ 
          marginTop: 12,
          padding: '8px 12px',
          background: '#f6ffed',
          borderRadius: 6,
          border: '1px solid #b7eb8f',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text strong style={{ fontSize: 13 }}>
              {currentSnapshot.rule_name}
            </Text>
            <Tag size="small" color={EXECUTION_STATUS_COLORS[currentSnapshot.status] || 'default'}>
              {currentSnapshot.status === 'passed' ? '通过' : 
               currentSnapshot.status === 'failed' ? '失败' : 
               currentSnapshot.status === 'skipped' ? '跳过' : '执行中'}
            </Tag>
          </div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
            {currentSnapshot.rule_id}
          </Text>
        </div>
      )}
    </div>
  );
}
