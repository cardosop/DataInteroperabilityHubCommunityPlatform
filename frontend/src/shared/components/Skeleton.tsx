/**
 * Skeleton — Phase 40 (38.1)
 *
 * Namespace with three sub-components: Skeleton.Line, Skeleton.Circle, Skeleton.Block.
 * Uses CSS custom properties --skeleton-base, --skeleton-highlight, --skeleton-animation-duration.
 */

import './Skeleton.css';

/* ---------- Line ---------- */
interface LineProps {
  width?: string;
  height?: string;
}

function Line({ width = '100%', height = 'var(--font-size-sm, 14px)' }: LineProps) {
  return (
    <div
      className="skeleton skeleton-line"
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

/* ---------- Circle ---------- */
interface CircleProps {
  size?: string;
}

function Circle({ size = '40px' }: CircleProps) {
  return (
    <div
      className="skeleton skeleton-circle"
      style={{ width: size, height: size }}
      aria-hidden="true"
    />
  );
}

/* ---------- Block ---------- */
interface BlockProps {
  width?: string;
  height: string;
  borderRadius?: string;
}

function Block({ width = '100%', height, borderRadius }: BlockProps) {
  return (
    <div
      className="skeleton skeleton-block"
      style={{ width, height, borderRadius }}
      aria-hidden="true"
    />
  );
}

/* ---------- Namespace export ---------- */
export const Skeleton = { Line, Circle, Block } as const;
