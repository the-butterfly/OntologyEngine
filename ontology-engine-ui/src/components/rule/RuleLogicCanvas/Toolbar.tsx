// ontology-engine-ui/src/components/rule/RuleLogicCanvas/Toolbar.tsx
// DAG 画布工具栏

import React, { useState } from 'react';
import { Dropdown, Badge, Space, Tooltip, Button, Modal, Input, Select, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  BarChartOutlined,
  StarOutlined,
  CalculatorOutlined,
  TableOutlined,
  RobotOutlined,
  RightOutlined,
  FunctionOutlined,
  PlusOutlined,
  InfoCircleOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import type { DAGNodeType } from '../../../types/dag';

interface ToolbarProps {
  onAddNode: (type: DAGNodeType, label?: string) => void;
  nodeStats: Record<string, number>;
}

// 算子元数据
const OPERATOR_ITEMS: Array<{
  type: DAGNodeType;
  label: string;
  icon: React.ReactNode;
  color: string;
  description: string;
  category: 'calculation' | 'decision' | 'ai' | 'variable';
}> = [
  {
    type: 'binning',
    label: '分箱',
    icon: <BarChartOutlined />,
    color: '#722ed1',
    description: '将连续值离散化为区间',
    category: 'calculation',
  },
  {
    type: 'scorecard',
    label: '评分卡',
    icon: <StarOutlined />,
    color: '#fa8c16',
    description: '多因素加权评分计算',
    category: 'calculation',
  },
  {
    type: 'weighted_sum',
    label: '加权计算',
    icon: <CalculatorOutlined />,
    color: '#f5222d',
    description: '多变量加权求和',
    category: 'calculation',
  },
  {
    type: 'decision_table',
    label: '决策表',
    icon: <TableOutlined />,
    color: '#faad14',
    description: '条件矩阵决策',
    category: 'decision',
  },
  {
    type: 'llm_judge',
    label: 'LLM定性分析',
    icon: <RobotOutlined />,
    color: '#13c2c2',
    description: '使用大语言模型进行定性判断',
    category: 'ai',
  },
  {
    type: 'switch',
    label: '条件分支',
    icon: <RightOutlined />,
    color: '#eb2f96',
    description: '根据条件执行不同分支',
    category: 'decision',
  },
  {
    type: 'compute',
    label: '公式计算',
    icon: <FunctionOutlined />,
    color: '#8c8c8c',
    description: '自定义公式计算',
    category: 'calculation',
  },
];

export const Toolbar: React.FC<ToolbarProps> = ({ onAddNode, nodeStats }) => {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  
  // 添加输入/输出节点的状态
  const [ioModalVisible, setIoModalVisible] = useState(false);
  const [ioModalType, setIoModalType] = useState<'input' | 'output'>('input');
  const [ioNodeName, setIoNodeName] = useState('');
  const [ioNodeLabel, setIoNodeLabel] = useState('');

  // 打开添加输入/输出节点弹窗
  const openIoModal = (type: 'input' | 'output') => {
    setIoModalType(type);
    setIoNodeName('');
    setIoNodeLabel('');
    setIoModalVisible(true);
  };

  // 确认添加输入/输出节点
  const handleAddIoNode = () => {
    if (!ioNodeName.trim()) {
      message.error('请输入要素名称');
      return;
    }
    // 使用输入的名称作为节点标签
    const label = ioNodeLabel.trim() || ioNodeName.trim();
    onAddNode(ioModalType, label);
    setIoModalVisible(false);
    message.success(`已添加${ioModalType === 'input' ? '输入' : '输出'}要素: ${label}`);
  };

  // IO 节点菜单项
  const ioMenuItems: MenuProps['items'] = [
    {
      key: 'input',
      label: (
        <Space>
          <ArrowLeftOutlined style={{ color: '#1890ff' }} />
          <span>添加输入要素</span>
        </Space>
      ),
      onClick: () => openIoModal('input'),
    },
    {
      key: 'output',
      label: (
        <Space>
          <ArrowRightOutlined style={{ color: '#52c41a' }} />
          <span>添加输出要素</span>
        </Space>
      ),
      onClick: () => openIoModal('output'),
    },
    { type: 'divider' },
    {
      key: 'variable',
      label: (
        <Space>
          <PlusOutlined style={{ color: '#8c8c8c' }} />
          <span>添加临时变量</span>
        </Space>
      ),
      onClick: () => onAddNode('compute', '临时变量'),
    },
  ];

  // 分类菜单
  const categoryMenuItems: MenuProps['items'] = [
    {
      key: 'all',
      label: '全部算子',
      onClick: () => setSelectedCategory(null),
    },
    { type: 'divider' },
    {
      key: 'calculation',
      label: '📊 计算类',
      onClick: () => setSelectedCategory('calculation'),
    },
    {
      key: 'decision',
      label: '🔀 决策类',
      onClick: () => setSelectedCategory('decision'),
    },
    {
      key: 'ai',
      label: '🤖 AI类',
      onClick: () => setSelectedCategory('ai'),
    },
    {
      key: 'variable',
      label: '📦 临时变量',
      onClick: () => setSelectedCategory('variable'),
    },
  ];

  // 过滤后的算子列表
  const filteredOperators = selectedCategory
    ? OPERATOR_ITEMS.filter((op) => op.category === selectedCategory)
    : OPERATOR_ITEMS;

  // 算子下拉菜单
  const operatorMenuItems: MenuProps['items'] = filteredOperators.map((op) => ({
    key: op.type,
    label: (
      <Space>
        <span style={{ color: op.color }}>{op.icon}</span>
        <span>{op.label}</span>
        <span style={{ color: '#8c8c8c', fontSize: 11 }}>{op.description}</span>
        {nodeStats[op.type] > 0 && (
          <Badge count={nodeStats[op.type]} size="small" style={{ marginLeft: 8 }} />
        )}
      </Space>
    ),
    onClick: () => onAddNode(op.type),
  }));

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 8,
        padding: 8,
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      {/* 添加输入/输出节点按钮 */}
      <Dropdown
        menu={{ items: ioMenuItems }}
        trigger={['click']}
        placement="bottomLeft"
      >
        <Button icon={<PlusOutlined />} size="small">
          添加要素
        </Button>
      </Dropdown>

      {/* 分隔线 */}
      <div style={{ width: 1, height: 20, background: '#d9d9d9' }} />

      {/* 添加算子按钮 */}
      <Dropdown
        menu={{ items: operatorMenuItems }}
        trigger={['click']}
        placement="bottomLeft"
      >
        <Button type="primary" icon={<PlusOutlined />} size="small">
          添加算子
        </Button>
      </Dropdown>

      {/* 分类筛选 */}
      <Dropdown
        menu={{ items: categoryMenuItems }}
        trigger={['click']}
        placement="bottomLeft"
      >
        <Button size="small">
          {selectedCategory
            ? {
                calculation: '📊 计算类',
                decision: '🔀 决策类',
                ai: '🤖 AI类',
                variable: '📦 临时变量',
              }[selectedCategory]
            : '全部算子'}
        </Button>
      </Dropdown>

      {/* 统计信息 */}
      <div style={{ borderLeft: '1px solid #d9d9d9', paddingLeft: 8, display: 'flex', gap: 12 }}>
        <Tooltip title="输入要素">
          <Space size={4}>
            <ArrowLeftOutlined style={{ color: '#1890ff', fontSize: 12 }} />
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>{nodeStats.input}</span>
          </Space>
        </Tooltip>
        <Tooltip title="输出要素">
          <Space size={4}>
            <ArrowRightOutlined style={{ color: '#52c41a', fontSize: 12 }} />
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>{nodeStats.output}</span>
          </Space>
        </Tooltip>
        <Tooltip title="计算类节点">
          <Space size={4}>
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>
              计算: {nodeStats.binning + nodeStats.scorecard + nodeStats.weighted_sum + nodeStats.compute}
            </span>
          </Space>
        </Tooltip>
        <Tooltip title="决策类节点">
          <Space size={4}>
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>
              决策: {nodeStats.decision_table + nodeStats.switch}
            </span>
          </Space>
        </Tooltip>
        <Tooltip title="AI类节点">
          <Space size={4}>
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>
              AI: {nodeStats.llm_judge}
            </span>
          </Space>
        </Tooltip>
      </div>

      {/* 帮助信息 */}
      <Tooltip title="拖拽节点到画布，或点击添加。连接节点表示计算顺序。">
        <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
      </Tooltip>

      {/* 添加输入/输出节点弹窗 */}
      <Modal
        title={ioModalType === 'input' ? '添加输入要素' : '添加输出要素'}
        open={ioModalVisible}
        onOk={handleAddIoNode}
        onCancel={() => setIoModalVisible(false)}
        okText="确认添加"
        cancelText="取消"
      >
        <div style={{ padding: '16px 0' }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
              要素名称 <span style={{ color: '#f5222d' }}>*</span>
            </label>
            <Input
              placeholder={ioModalType === 'input' ? '例如: age, income, score' : '例如: credit_score, risk_level'}
              value={ioNodeName}
              onChange={(e) => setIoNodeName(e.target.value)}
              onPressEnter={handleAddIoNode}
            />
            <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
              {ioModalType === 'input' ? '作为算子的输入变量' : '作为算子的输出结果'}
            </div>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
              显示标签（可选）
            </label>
            <Input
              placeholder="留空则使用要素名称"
              value={ioNodeLabel}
              onChange={(e) => setIoNodeLabel(e.target.value)}
              onPressEnter={handleAddIoNode}
            />
            <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
              自定义在节点上显示的名称
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Toolbar;
