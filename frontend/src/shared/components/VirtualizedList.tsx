/**
 * Virtualized List Component
 * Wrapper around react-window for efficient rendering of large lists
 */

import React from 'react';
import { FixedSizeList, ListChildComponentProps } from 'react-window';

export interface VirtualizedListProps<T> {
  items: T[];
  height: number;
  itemHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
  className?: string;
  'aria-label'?: string;
  'aria-labelledby'?: string;
}

export function VirtualizedList<T>({
  items,
  height,
  itemHeight,
  renderItem,
  className,
  'aria-label': ariaLabel,
  'aria-labelledby': ariaLabelledBy,
}: VirtualizedListProps<T>) {
  const Row = ({ index, style }: ListChildComponentProps) => (
    <div style={style} role="row">
      {renderItem(items[index], index)}
    </div>
  );

  return (
    <div className={className} role="list" aria-label={ariaLabel} aria-labelledby={ariaLabelledBy}>
      <FixedSizeList
        height={height}
        itemCount={items.length}
        itemSize={itemHeight}
        width="100%"
        overscanCount={5} // Render 5 extra items outside visible area for smoother scrolling
      >
        {Row}
      </FixedSizeList>
    </div>
  );
}
