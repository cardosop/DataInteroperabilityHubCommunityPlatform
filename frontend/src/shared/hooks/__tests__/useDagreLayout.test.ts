/**
 * useDagreLayout tests — Phase 36 (34.3)
 */
import { describe, it, expect } from 'vitest';
import { useDagreLayout } from '../useDagreLayout';
import type { Node, Edge } from '@xyflow/react';

function makeNode(id: string): Node {
  return { id, position: { x: 0, y: 0 }, data: { label: id } };
}

function makeEdge(source: string, target: string): Edge {
  return { id: `${source}-${target}`, source, target };
}

describe('useDagreLayout', () => {
  it('returns [] for empty input without crash or NaN', () => {
    const result = useDagreLayout([], []);
    expect(result).toEqual([]);
  });

  it('single node returns numeric position', () => {
    const result = useDagreLayout([makeNode('a')], []);
    expect(result).toHaveLength(1);
    expect(typeof result[0].position.x).toBe('number');
    expect(typeof result[0].position.y).toBe('number');
    expect(Number.isNaN(result[0].position.x)).toBe(false);
    expect(Number.isNaN(result[0].position.y)).toBe(false);
  });

  it('two connected nodes have distinct x positions in LR direction', () => {
    const nodes = [makeNode('a'), makeNode('b')];
    const edges = [makeEdge('a', 'b')];
    const result = useDagreLayout(nodes, edges, { direction: 'LR' });
    expect(result).toHaveLength(2);
    expect(result[0].position.x).not.toBe(result[1].position.x);
  });

  it('TB direction produces distinct y positions', () => {
    const nodes = [makeNode('a'), makeNode('b')];
    const edges = [makeEdge('a', 'b')];
    const result = useDagreLayout(nodes, edges, { direction: 'TB' });
    expect(result).toHaveLength(2);
    expect(result[0].position.y).not.toBe(result[1].position.y);
  });
});
