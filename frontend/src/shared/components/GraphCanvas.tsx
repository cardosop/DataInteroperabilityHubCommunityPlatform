/**
 * GraphCanvas — Phase 36 (34.5)
 *
 * Reusable React Flow wrapper with background, minimap, controls,
 * toolbar, loading/error states, and auto-fitView on first data load.
 */

import { useEffect, useRef, type ComponentType } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  Controls,
  useReactFlow,
  ReactFlowProvider,
  type Node,
  type Edge,
} from '@xyflow/react';
import { GraphToolbar } from './GraphToolbar';
import { Skeleton } from './Skeleton';
import { ErrorDisplay } from './ErrorDisplay';

interface GraphCanvasProps {
  nodes: Node[];
  edges: Edge[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- React Flow's internal EdgeTypes/NodeTypes use complex generics that don't expose a usable public type
  nodeTypes?: Record<string, ComponentType<any>>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  edgeTypes?: Record<string, ComponentType<any>>;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  onNodeClick?: (event: React.MouseEvent, node: Node) => void;
  className?: string;
}

function GraphCanvasInner({
  nodes,
  edges,
  nodeTypes,
  edgeTypes,
  loading,
  error,
  onRetry,
  onNodeClick,
  className,
}: GraphCanvasProps) {
  const { fitView } = useReactFlow();
  const prevNodeCount = useRef(0);

  // Re-fit when nodes arrive or change count (handles async data loading).
  // React Flow needs time to measure DOM nodes before fitView can calculate
  // the correct viewport — 300ms accommodates slow staging environments.
  useEffect(() => {
    if (nodes.length > 0 && nodes.length !== prevNodeCount.current) {
      prevNodeCount.current = nodes.length;
      const t = setTimeout(() => fitView({ padding: 0.1 }), 300);
      return () => clearTimeout(t);
    }
  }, [nodes.length, fitView]);

  if (loading) {
    return <Skeleton.Block height="600px" borderRadius="var(--border-radius-md, 8px)" />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load graph" onRetry={onRetry} />;
  }

  return (
    <div
      className={`graph-canvas-wrapper ${className ?? ''}`}
      // React Flow requires a concrete parent height; min-height alone can yield
      // a 0px internal viewport in some browsers/layouts (nodes exist in DOM but
      // the plot is not visible). Keep both fixed and minimum height for safety.
      style={{ height: 600, minHeight: 600, position: 'relative', width: '100%' }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.1 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} />
        <MiniMap />
        <Controls />
        <GraphToolbar />
      </ReactFlow>
    </div>
  );
}

export function GraphCanvas(props: GraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
