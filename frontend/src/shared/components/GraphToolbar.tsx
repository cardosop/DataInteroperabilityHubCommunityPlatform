/**
 * GraphToolbar — Phase 36 (34.4)
 *
 * Floating toolbar for React Flow canvas: zoom, fit, fullscreen, export.
 * Must be rendered inside a ReactFlowProvider.
 */

import { useCallback, useState } from 'react';
import { useReactFlow } from '@xyflow/react';
import { Icon } from './Icon';
import {
  ZoomIn, ZoomOut, Maximize2, Minimize2, Download,
} from '../config/iconRegistry';

export function GraphToolbar() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const [isFullscreen, setIsFullscreen] = useState(false);

  const handleFitView = useCallback(() => {
    fitView({ padding: 0.1 });
  }, [fitView]);

  const handleFullscreen = useCallback(() => {
    const el = document.querySelector('.graph-canvas-wrapper');
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen?.().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen?.().then(() => setIsFullscreen(false)).catch(() => {});
    }
  }, []);

  const handleExport = useCallback(() => {
    const svg = document.querySelector('.graph-canvas-wrapper .react-flow__renderer svg');
    if (!svg) return;
    const svgData = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'graph.svg';
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  return (
    <div className="graph-toolbar" style={{ position: 'absolute', top: 8, right: 8, display: 'flex', gap: 4, zIndex: 10, background: 'var(--color-background-primary, white)', borderRadius: 'var(--border-radius-md, 8px)', padding: '4px', boxShadow: 'var(--shadow-md)' }}>
      <button type="button" onClick={() => zoomIn()} title="Zoom in" aria-label="Zoom in" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
        <Icon icon={ZoomIn} size="sm" />
      </button>
      <button type="button" onClick={() => zoomOut()} title="Zoom out" aria-label="Zoom out" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
        <Icon icon={ZoomOut} size="sm" />
      </button>
      <button type="button" onClick={handleFitView} title="Fit view" aria-label="Fit view" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
        <Icon icon={Maximize2} size="sm" />
      </button>
      <button type="button" onClick={handleFullscreen} title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'} aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
        <Icon icon={isFullscreen ? Minimize2 : Maximize2} size="sm" />
      </button>
      <button type="button" onClick={handleExport} title="Export SVG" aria-label="Export SVG" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
        <Icon icon={Download} size="sm" />
      </button>
    </div>
  );
}
