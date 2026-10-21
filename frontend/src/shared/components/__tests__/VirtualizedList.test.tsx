/**
 * VirtualizedList component tests — Phase 111.4
 */
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { VirtualizedList } from '../VirtualizedList';

describe('VirtualizedList', () => {
  const items = Array.from({ length: 100 }, (_, i) => ({ id: i, name: `Item ${i}` }));

  it('renders without crashing', () => {
    const { container } = render(
      <VirtualizedList
        items={items}
        height={400}
        itemHeight={40}
        renderItem={(item: { id: number; name: string }) => <div>{item.name}</div>}
      />
    );
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('renders visible items', () => {
    const { container } = render(
      <VirtualizedList
        items={items}
        height={400}
        itemHeight={40}
        renderItem={(item: { id: number; name: string }) => <div>{item.name}</div>}
      />
    );
    // react-window renders only visible items
    expect(container.textContent).toContain('Item');
  });
});
