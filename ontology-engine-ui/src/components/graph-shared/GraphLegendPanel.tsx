import React from 'react';

interface LegendItem {
  color: string;
  label: string;
  count?: number;
  type?: 'node' | 'edge';
  lineDash?: number[];
  borderColor?: string;
}

interface GraphLegendPanelProps {
  title?: string;
  items: LegendItem[];
  activeItems?: Set<string>;
  onItemClick?: (label: string) => void;
  style?: React.CSSProperties;
}

const GraphLegendPanel: React.FC<GraphLegendPanelProps> = ({
  title,
  items,
  activeItems,
  onItemClick,
  style,
}) => {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 6,
        border: '1px solid #f0f0f0',
        padding: '8px 12px',
        fontSize: 12,
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        ...style,
      }}
    >
      {title && <div style={{ fontWeight: 600, marginBottom: 6, color: '#262626' }}>{title}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {items.map((item) => {
          const isActive = !activeItems || activeItems.has(item.label);
          return (
            <div
              key={item.label}
              onClick={() => onItemClick?.(item.label)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                cursor: onItemClick ? 'pointer' : 'default',
                opacity: isActive ? 1 : 0.35,
                transition: 'opacity 0.2s',
              }}
            >
              {item.type === 'edge' ? (
                <svg width="20" height="10">
                  <line
                    x1="0" y1="5" x2="20" y2="5"
                    stroke={item.color}
                    strokeWidth={2}
                    strokeDasharray={item.lineDash?.join(',') || 'none'}
                  />
                </svg>
              ) : (
                <div
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: item.type === 'node' ? '50%' : 2,
                    background: item.color,
                    border: item.borderColor ? `2px solid ${item.borderColor}` : undefined,
                    flexShrink: 0,
                  }}
                />
              )}
              <span style={{ color: '#595959', flex: 1 }}>{item.label}</span>
              {item.count !== undefined && (
                <span style={{ color: '#8c8c8c' }}>{item.count}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default GraphLegendPanel;
