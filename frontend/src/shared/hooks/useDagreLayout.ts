/**
 * useDagreLayout — Phase 36 (34.2)
 *
 * Pure function that computes Dagre layout positions for React Flow nodes.
 * Call during render (not in useEffect) — it has no side effects.
 */

import dagre from '@dagrejs/dagre';
import type { Node, Edge } from '@xyflow/react';

interface DagreLayoutOptions {
  direction?: 'LR' | 'TB';
  nodeWidth?: number;
  nodeHeight?: number;
}

export function useDagreLayout(
  nodes: Node[],
  edges: Edge[],
  options: DagreLayoutOptions = {},
): Node[] {
  const { direction = 'LR', nodeWidth = 160, nodeHeight = 60 } = options;

  if (nodes.length === 0) return [];

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction });

  for (const node of nodes) {
    g.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: {
        x: (pos?.x ?? 0) - nodeWidth / 2,
        y: (pos?.y ?? 0) - nodeHeight / 2,
      },
    };
  });
}
