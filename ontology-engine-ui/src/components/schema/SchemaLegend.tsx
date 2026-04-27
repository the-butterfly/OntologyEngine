// ============================================================================
// Legend Component
// ============================================================================

export default function SchemaLegend() {
  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        background: '#fff',
        borderRadius: 8,
        padding: '10px 14px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
        zIndex: 10,
        fontSize: 12,
        minWidth: 140,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8, color: '#333', fontSize: 13 }}>层级图例</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 28, height: 12, background: '#E8F4FD',
            border: '2px solid #1890FF', borderRadius: 6, // Capsule shape
          }} />
          <div>
            <div style={{ color: '#333', lineHeight: 1.2 }}>事实对象</div>
            <div style={{ color: '#999', fontSize: 10 }}>L1 Entity</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 16, height: 16, background: '#F9F0FF',
            border: '2px solid #722ED1', transform: 'rotate(45deg)',
          }} />
          <div>
            <div style={{ color: '#333', lineHeight: 1.2 }}>分类体系</div>
            <div style={{ color: '#999', fontSize: 10 }}>L2 Category</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 16, height: 16, background: '#F6FFED',
            border: '2px solid #52C41A', borderRadius: '50%',
          }} />
          <div>
            <div style={{ color: '#333', lineHeight: 1.2 }}>分析要素</div>
            <div style={{ color: '#999', fontSize: 10 }}>L3 Metric</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 28, height: 14, background: '#E6F7FF',
            border: '2px solid #1890FF', borderRadius: 3,
          }} />
          <div>
            <div style={{ color: '#333', lineHeight: 1.2 }}>业务逻辑</div>
            <div style={{ color: '#999', fontSize: 10 }}>L4 Rule</div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid #f0f0f0' }}>
        <div style={{ fontWeight: 600, marginBottom: 6, color: '#333', fontSize: 11 }}>边类型</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: '#91D5FF' }} />
            <span style={{ color: '#666' }}>关联关系</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: '#87E8DE' }} />
            <span style={{ color: '#666' }}>依赖关系</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: '#FFA39E' }} />
            <span style={{ color: '#666' }}>要素输入</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: '#FF7B45' }} />
            <span style={{ color: '#666' }}>规则依赖</span>
          </div>
        </div>
      </div>
    </div>
  );
}
