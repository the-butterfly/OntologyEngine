import React from 'react';
import { Button, Space, Tooltip as AntTooltip, Select } from 'antd';
import {
  ZoomInOutlined,
  ZoomOutOutlined,
  FullscreenOutlined,
  CameraOutlined,
  CompressOutlined,
} from '@ant-design/icons';

export type LayoutMode = 'force' | 'dagre' | 'concentric';

interface GraphToolbarProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onFitView?: () => void;
  onExportImage?: () => void;
  onFullscreen?: () => void;
  layoutMode?: LayoutMode;
  onLayoutChange?: (mode: LayoutMode) => void;
  showLayoutSwitch?: boolean;
}

const GraphToolbar: React.FC<GraphToolbarProps> = ({
  onZoomIn,
  onZoomOut,
  onFitView,
  onExportImage,
  onFullscreen,
  layoutMode,
  onLayoutChange,
  showLayoutSwitch = false,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 8px',
        background: '#fff',
        borderRadius: 6,
        border: '1px solid #f0f0f0',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      }}
    >
      <Space size={4}>
        <AntTooltip title="放大">
          <Button size="small" type="text" icon={<ZoomInOutlined />} onClick={onZoomIn} />
        </AntTooltip>
        <AntTooltip title="缩小">
          <Button size="small" type="text" icon={<ZoomOutOutlined />} onClick={onZoomOut} />
        </AntTooltip>
        <AntTooltip title="适应画布">
          <Button size="small" type="text" icon={<CompressOutlined />} onClick={onFitView} />
        </AntTooltip>
        <AntTooltip title="导出图片">
          <Button size="small" type="text" icon={<CameraOutlined />} onClick={onExportImage} />
        </AntTooltip>
        <AntTooltip title="全屏">
          <Button size="small" type="text" icon={<FullscreenOutlined />} onClick={onFullscreen} />
        </AntTooltip>
      </Space>
      {showLayoutSwitch && onLayoutChange && (
        <Select
          size="small"
          value={layoutMode || 'force'}
          onChange={onLayoutChange}
          style={{ width: 100, marginLeft: 8 }}
          options={[
            { label: '力导向', value: 'force' },
            { label: '分层', value: 'dagre' },
            { label: '同心圆', value: 'concentric' },
          ]}
        />
      )}
    </div>
  );
};

export default GraphToolbar;
