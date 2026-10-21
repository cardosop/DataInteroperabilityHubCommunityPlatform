/**
 * Virtualized List Component
 * Wrapper around react-window List for efficient rendering of large lists
 */

import React from 'react';
import { List } from 'react-window';

export interface VirtualizedListProps<T> {
  items: T[];
  height: number;
  itemHeight: number;
  renderItem: (item: T, index: number) => React.ReactNode;
  className?: string;
  'aria-label'?: string;
  'aria-labelledby'?: string;
}

interface RowProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
}

function RowComponent<T>({
  index,
  style,
  items,
  renderItem,
}: {
  index: number;
  style: React.CSSProperties;
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
}) {
  return (
    <div style={style} role="row">
      {renderItem(items[index], index)}
    </div>
  );
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
  const rowProps: RowProps<T> = { items, renderItem };

  return (
    <div className={className} role="list" aria-label={ariaLabel} aria-labelledby={ariaLabelledBy}>
      <List<RowProps<T>>
        rowCount={items.length}
        rowHeight={itemHeight}
        rowComponent={(props) => (
          <RowComponent
            index={props.index}
            style={props.style}
            items={rowProps.items}
            renderItem={rowProps.renderItem}
          />
        )}
        rowProps={rowProps}
        style={{ height, width: '100%' }}
        overscanCount={5}
      />
    </div>
  );
}
