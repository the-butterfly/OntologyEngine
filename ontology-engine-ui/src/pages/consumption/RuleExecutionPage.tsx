// ontology-engine-ui/src/pages/consumption/RuleExecutionPage.tsx
// Rule execution page - rule retrieval, dependency graph, execution with explanation

import { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Select, Tag, Space, Spin, message, Empty, Button,
  Tabs, Badge,
} from 'antd';
import {
  PlayCircleOutlined, BranchesOutlined, ApartmentOutlined,
} from '@ant-design/icons';
import { useSpaceStore } from '../../store/spaceStore';
import { spaceApi } from '../../api/spaceApi';
import type { EntityInstance } from '../../api/spaceApi';
import ExecutionResultCard from '../../components/rule/ExecutionResultCard';
import DependencyGraphPanel from '../../components/rule/DependencyGraphPanel';
import ApplicableRulesPanel, { ApplicableRulesData } from '../../components/rule/ApplicableRulesPanel';

const { Title, Text } = Typography;

interface ElementRef {
  id: string;
  name?: string;
}

interface DependencyNode {
  id: string;
  label: string;
  rule_type: string;
  priority: number;
  enabled: boolean;
  input_elements: ElementRef[];
  output_elements: ElementRef[];
  logic_count: number;
}

interface DependencyEdge {
  id: string;
  source: string;
  target: string;
  element: string;
  type: string;
}

interface MutualExclusion {
  rule_a: string;
  rule_b: string;
  reason: string;
  type: string;
}

interface DependencyStats {
  total_rules: number;
  dependency_edges: number;
  exclusion_pairs: number;
}

interface DependencyGraphData {
  nodes: DependencyNode[];
  edges: DependencyEdge[];
  mutual_exclusions: MutualExclusion[];
  execution_order: string[];
  stats: DependencyStats;
}

export default function RuleExecutionPage() {
  const {
    activeSpace,
    activeViewId,
    activeSpaceId,
    executionResult,
    executeAnalyze,
    executeLoading,
    error,
    clearError,
  } = useSpaceStore();

  // Use view entities (from consumption surface), not management entities
  const [viewEntities, setViewEntities] = useState<EntityInstance[]>([]);
  const [entitiesLoading, setEntitiesLoading] = useState(false);

  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [selectedDimension, setSelectedDimension] = useState<string>('credit_assessment');
  const [activeTab, setActiveTab] = useState('execute');

  // Categorizations (dimensions) from L2
  const [categorizations, setCategorizations] = useState<any[]>([]);

  // Dependency graph state
  const [dependencyGraph, setDependencyGraph] = useState<DependencyGraphData | null>(null);
  const [depGraphLoading, setDepGraphLoading] = useState(false);

  // Applicable rules for selected entity
  const [applicableRules, setApplicableRules] = useState<ApplicableRulesData | null>(null);
  const [rulesLoading, setRulesLoading] = useState(false);

  useEffect(() => {
    if (activeViewId) {
      setEntitiesLoading(true);
      spaceApi.listViewEntities(activeViewId)
        .then(setViewEntities)
        .catch(() => message.error('加载实体列表失败'))
        .finally(() => setEntitiesLoading(false));
    }
  }, [activeViewId]);

  // Load categorizations (dimensions) when space changes - only when spaceId is stable
  useEffect(() => {
    if (!activeSpaceId) return;
    spaceApi.listCategorizations(activeSpaceId)
      .then(setCategorizations)
      .catch(console.error);
  }, [activeSpaceId]);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error]);

  const loadDependencyGraph = useCallback(async () => {
    if (!activeViewId) return;
    setDepGraphLoading(true);
    try {
      const data = await spaceApi.getRuleDependencyGraph(activeViewId);
      setDependencyGraph(data);
    } catch (e) {
      message.error('加载规则依赖图失败');
    } finally {
      setDepGraphLoading(false);
    }
  }, [activeViewId]);

  const loadApplicableRules = useCallback(async (entityId: string) => {
    if (!activeViewId || !entityId) return;
    setRulesLoading(true);
    try {
      const data = await spaceApi.getRulesForEntity(activeViewId, entityId);
      setApplicableRules(data);
    } catch (e) {
      console.error('Failed to load applicable rules');
    } finally {
      setRulesLoading(false);
    }
  }, [activeViewId]);

  // Load dependency graph on tab switch
  const handleTabChange = (key: string) => {
    setActiveTab(key);
    if (key === 'dependency' && !dependencyGraph) {
      loadDependencyGraph();
    }
    if (key === 'applicable' && selectedEntity) {
      loadApplicableRules(selectedEntity);
    }
  };

  // Load applicable rules when entity changes
  useEffect(() => {
    if (selectedEntity && activeTab === 'applicable') {
      loadApplicableRules(selectedEntity);
    }
  }, [selectedEntity, activeTab, loadApplicableRules]);

  const handleExecute = async () => {
    if (!activeViewId || !selectedEntity) {
      message.warning('请选择要分析的实体');
      return;
    }
    await executeAnalyze(activeViewId, selectedEntity, selectedDimension);
    setActiveTab('result');
  };

  if (!activeViewId) {
    return (
      <Card>
        <Empty description="请先激活空间以创建消费视图" />
      </Card>
    );
  }

  const tabItems = [
    {
      key: 'execute',
      label: (
        <span>
          <PlayCircleOutlined /> 规则执行
        </span>
      ),
      children: (
        <div>
          <Space style={{ marginBottom: 16 }} wrap>
            <Select
              placeholder="选择评估维度"
              value={selectedDimension}
              onChange={setSelectedDimension}
              style={{ width: 160 }}
              options={categorizations.map((cat) => ({
                value: cat.id,
                label: cat.name || cat.id,
              }))}
            />
            <Select
              placeholder="选择实体"
              value={selectedEntity}
              onChange={(v) => {
                setSelectedEntity(v);
                if (activeTab === 'applicable') loadApplicableRules(v);
              }}
              style={{ width: 280 }}
              allowClear
              showSearch
              loading={entitiesLoading}
              options={viewEntities.map((e) => ({
                value: e.entity_id,
                label: `${e.entity_id} (${e._concept})`,
              }))}
            />
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleExecute}
              disabled={!selectedEntity || executeLoading}
              loading={executeLoading}
            >
              执行分析
            </Button>
            <Button
              icon={<BranchesOutlined />}
              onClick={() => {
                setActiveTab('applicable');
                if (selectedEntity) loadApplicableRules(selectedEntity);
              }}
              disabled={!selectedEntity}
            >
              查看适用规则
            </Button>
          </Space>
          {executeLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" />
              <div style={{ marginTop: 16 }}>规则执行中...</div>
            </div>
          ) : !executionResult ? (
            <Empty description="选择实体和维度后执行分析">
              <Text type="secondary" style={{ fontSize: 12 }}>
                执行后将显示每条规则的执行路径、条件拆解和输入输出追踪
              </Text>
            </Empty>
          ) : (
            <ExecutionResultCard executionResult={executionResult} />
          )}
        </div>
      ),
    },
    {
      key: 'result',
      label: (
        <span>
          执行结果
          {executionResult && (
            <Tag
              color={
                executionResult.decision === 'APPROVED'
                  ? 'success'
                  : executionResult.decision === 'REJECTED'
                    ? 'error'
                    : 'warning'
              }
              style={{ marginLeft: 6, fontSize: 11 }}
            >
              {executionResult.decision}
            </Tag>
          )}
        </span>
      ),
      children: <ExecutionResultCard executionResult={executionResult} />,
    },
    {
      key: 'applicable',
      label: (
        <span>
          <ApartmentOutlined /> 适用规则
          {selectedEntity && applicableRules && (
            <Badge count={applicableRules.total} style={{ marginLeft: 6 }} />
          )}
        </span>
      ),
      children: <ApplicableRulesPanel applicableRules={applicableRules} loading={rulesLoading} />,
    },
    {
      key: 'dependency',
      label: (
        <span>
          <BranchesOutlined /> 规则依赖图
        </span>
      ),
      children: <DependencyGraphPanel dependencyGraph={dependencyGraph} loading={depGraphLoading} />,
    },
  ];

  return (
    <Card title={<Title level={5}>规则执行 & 依赖分析</Title>}>
      <Tabs items={tabItems} activeKey={activeTab} onChange={handleTabChange} />
    </Card>
  );
}
