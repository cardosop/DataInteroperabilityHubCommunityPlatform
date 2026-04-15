/**
 * useBulkSelection — 223.3.1.
 *
 * Encapsulates the selection state for a list/table row picker:
 *   - per-row toggle
 *   - select-all / deselect-all / toggleAll (header checkbox)
 *   - optional `isSelectable(id)` predicate so pages can forbid selecting
 *     non-eligible rows (e.g. only DRAFT assets can be bulk-deleted)
 *   - automatic pruning when `allIds` changes between renders (pagination,
 *     filter toggles): rows that disappeared from view are silently dropped
 *     from the selection so the page never tries to bulk-act on data the
 *     user hasn't seen.
 *
 * Returns primitives that can drive any checkbox UI — the hook is kept
 * pure (no DOM refs, no IDs beyond `allIds`) so the same hook powers
 * AccessRequestListPage, AssetListPage, and ContractListPage.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export interface UseBulkSelectionArgs {
  /** All ids currently visible in the list. Typically `results.map(r => r.id)`. */
  allIds: string[];
  /**
   * Predicate gating whether an id may be selected at all. Defaults to
   * "every id is selectable". When a row is not selectable, `toggle()`
   * is a no-op and `selectAll()` skips it.
   */
  isSelectable?: (id: string) => boolean;
}

export interface UseBulkSelectionResult {
  /** Ids the user has selected (intersected with `allIds`). */
  selectedIds: string[];
  selectedCount: number;
  isSelected: (id: string) => boolean;
  toggle: (id: string) => void;
  selectAll: () => void;
  deselectAll: () => void;
  toggleAll: () => void;
  /** `true` only when *every selectable id* is currently selected. */
  isAllSelected: boolean;
  /** `true` when *some* (but not all) selectable ids are selected. */
  isIndeterminate: boolean;
}

export function useBulkSelection({
  allIds,
  isSelectable,
}: UseBulkSelectionArgs): UseBulkSelectionResult {
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  // Stable snapshot of the predicate so effects don't loop if the caller
  // re-creates the function on every render.
  const isSelectableRef = useRef(isSelectable);
  isSelectableRef.current = isSelectable;

  // Prune selection when the visible id set changes. This handles
  // pagination, filter changes, and deletion races where a selected row
  // is no longer in the result set.
  useEffect(() => {
    setSelected((prev) => {
      const visible = new Set(allIds);
      let changed = false;
      const next = new Set<string>();
      for (const id of prev) {
        if (visible.has(id)) {
          next.add(id);
        } else {
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [allIds]);

  const selectableIds = useMemo(() => {
    const check = isSelectableRef.current;
    if (!check) return allIds;
    return allIds.filter(check);
  }, [allIds]);

  const toggle = useCallback(
    (id: string) => {
      const check = isSelectableRef.current;
      if (check && !check(id)) return;
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    },
    [],
  );

  const selectAll = useCallback(() => {
    setSelected(new Set(selectableIds));
  }, [selectableIds]);

  const deselectAll = useCallback(() => {
    setSelected(new Set());
  }, []);

  const selectedIds = useMemo(() => {
    const visible = new Set(allIds);
    return Array.from(selected).filter((id) => visible.has(id));
  }, [selected, allIds]);

  const isAllSelected =
    selectableIds.length > 0 && selectableIds.every((id) => selected.has(id));
  const isIndeterminate = selectedIds.length > 0 && !isAllSelected;

  const toggleAll = useCallback(() => {
    if (isAllSelected) {
      deselectAll();
    } else {
      selectAll();
    }
  }, [isAllSelected, selectAll, deselectAll]);

  const isSelected = useCallback((id: string) => selected.has(id), [selected]);

  return {
    selectedIds,
    selectedCount: selectedIds.length,
    isSelected,
    toggle,
    selectAll,
    deselectAll,
    toggleAll,
    isAllSelected,
    isIndeterminate,
  };
}
