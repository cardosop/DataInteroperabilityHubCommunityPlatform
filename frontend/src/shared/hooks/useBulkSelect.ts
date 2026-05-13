/**
 * Phase 278.E.2 — bulk multi-select state management hook.
 *
 * Tracks selected item IDs, provides select/deselect/toggle/clear,
 * and computed properties (selectedCount, allSelected, someSelected).
 *
 * Usage:
 *   const bulk = useBulkSelect({ items, getId: (item) => item.id });
 *   // In checkbox column:  <input checked={bulk.isSelected(item.id)} onChange={() => bulk.toggle(item.id)} />
 *   // In header:           <input checked={bulk.allSelected} onChange={bulk.toggleAll} />
 *   // Action bar:          {bulk.selectedCount > 0 && <BulkActionBar count={bulk.selectedCount} actions={...} />}
 */
import { useCallback, useMemo, useState } from 'react';

interface UseBulkSelectOptions<T> {
  /** All items on the current page. */
  items: T[];
  /** Extract a unique identifier from an item. */
  getId: (item: T) => string;
}

interface BulkSelectState {
  selectedIds: Set<string>;
  selectedCount: number;
  allSelected: boolean;
  someSelected: boolean;
  isSelected: (id: string) => boolean;
  toggle: (id: string) => void;
  toggleAll: () => void;
  selectAll: () => void;
  clearSelection: () => void;
}

export function useBulkSelect<T>({ items, getId }: UseBulkSelectOptions<T>): BulkSelectState {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const itemIds = useMemo(() => new Set(items.map(getId)), [items, getId]);

  const selectedCount = useMemo(
    () => {
      let count = 0;
      for (const id of itemIds) {
        if (selectedIds.has(id)) count++;
      }
      return count;
    },
    [selectedIds, itemIds],
  );

  const allSelected = selectedCount > 0 && selectedCount === itemIds.size && itemIds.size > 0;
  const someSelected = selectedCount > 0 && !allSelected;

  const isSelected = useCallback((id: string) => selectedIds.has(id), [selectedIds]);

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(itemIds));
  }, [itemIds]);

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(itemIds));
    }
  }, [allSelected, itemIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  return {
    selectedIds,
    selectedCount,
    allSelected,
    someSelected,
    isSelected,
    toggle,
    toggleAll,
    selectAll,
    clearSelection,
  };
}
