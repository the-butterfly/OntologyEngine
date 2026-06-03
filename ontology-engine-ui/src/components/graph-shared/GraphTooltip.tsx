import React from 'react';

interface GraphTooltipProps {
  x: number;
  y: number;
  visible: boolean;
  title?: string;
  items?: Array<{ label: string; value: string | number }>;
}

const GraphTooltip: React.FC<GraphTooltipProps> = ({ x, y, visible, title, items }) => {
  if (!visible) return null;
  return (
    <div
      style={{
        position: 'fixed',
        left: x + 12,
        top: y + 12,
        background: 'rgba(255,255,255,0.96)',
        border: '1px solid #e8e8e8',
        borderRadius: 4,
        padding: '8px 12px',
        fontSize: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        zIndex: 1000,
        maxWidth: 320,
        pointerEvents: 'none',
      }}
    >
      {title && <div style={{ fontWeight: 600, marginBottom: 4, color: '#262626' }}>{title}</div>}
      {items && items.map((item, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: '#595959' }}>
          <span>{item.label}</span>
          <span style={{ color: '#262626', fontWeight: 500 }}>{item.value}</span>
        </div>
      ))}
    </div>
  );
};

export default GraphTooltip;
