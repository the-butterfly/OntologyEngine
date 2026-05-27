import React from 'react';
import { Space } from 'antd';

const CONCEPT_LEGEND = [
  { concept: 'Borrower', color: '#13c2c2', label: '借款人' },
  { concept: 'LoanApplication', color: '#eb2f96', label: '贷款申请' },
  { concept: 'RepaymentRecord', color: '#8c8c8c', label: '还款记录' },
  { concept: 'Supplier', color: '#1890ff', label: '供应商' },
  { concept: 'CoreEnterprise', color: '#52c41a', label: '核心企业' },
  { concept: 'Invoice', color: '#faad14', label: '发票' },
  { concept: 'Contract', color: '#722ed1', label: '合同' },
  { concept: 'GuaranteeRelation', color: '#ff4d4f', label: '担保关系' },
];

interface GraphLegendProps {
  conceptCounts: Record<string, number>;
  activeConcepts?: string[];
  onConceptClick?: (concept: string) => void;
}

export const GraphLegend: React.FC<GraphLegendProps> = ({ conceptCounts, activeConcepts = [], onConceptClick }) => {
  const visibleConcepts = CONCEPT_LEGEND.filter(c => conceptCounts[c.concept]);
  const hasActiveConcepts = activeConcepts.length > 0;

  const handleClick = (concept: string) => {
    onConceptClick?.(concept);
  };

  return (
    <div>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>图例说明{hasActiveConcepts && <span style={{ fontWeight: 'normal', color: '#1890ff', marginLeft: 8 }}>（点击图例切换高亮）</span>}</div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 12 }}>
        {visibleConcepts.map(item => {
          const isActive = hasActiveConcepts ? activeConcepts.includes(item.concept) : true;
          return (
            <Space
              key={item.concept}
              size={4}
              onClick={() => handleClick(item.concept)}
              style={{
                cursor: 'pointer',
                padding: '2px 6px',
                borderRadius: 4,
                background: isActive ? 'transparent' : 'rgba(0,0,0,0.04)',
                transition: 'background 0.2s',
              }}
            >
              <div style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: item.color,
                display: 'inline-block',
                opacity: isActive ? 1 : 0.2,
              }} />
              <span style={{ opacity: isActive ? 1 : 0.3 }}>{item.label} ({item.concept})</span>
              {hasActiveConcepts && (
                <span style={{ fontSize: 10, color: isActive ? '#1890ff' : '#bbb' }}>
                  {isActive ? '●' : '○'}
                </span>
              )}
            </Space>
          );
        })}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: 12, color: '#666', marginTop: 6 }}>
        <Space size={4}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#8c8c8c' }} />
            <span>小圆=低信用分</span>
          </div>
          <div style={{ width: 18, height: 18, borderRadius: '50%', background: '#8c8c8c' }} />
          <span>大圆=高信用分</span>
        </Space>
        <span>|</span>
        <Space size={4}>
          <div style={{ width: 30, height: 2, background: '#52c41a' }} />
          <span>不同关系类型颜色区分</span>
        </Space>
        <Space size={4}>
          <div style={{ width: 30, height: 3, background: '#ff4d4f' }} />
          <span>担保圈循环边</span>
        </Space>
      </div>
    </div>
  );
};
