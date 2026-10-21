/**
 * useBulkSelection — 223.3.1 tests.
 */
import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useBulkSelection } from './useBulkSelection';

describe('useBulkSelection', () => {
  it('starts empty and reports nothing selected', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b', 'c'] }),
    );
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.isSelected('a')).toBe(false);
    expect(result.current.isAllSelected).toBe(false);
    expect(result.current.isIndeterminate).toBe(false);
  });

  it('toggles individual ids on and off', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b', 'c'] }),
    );
    act(() => result.current.toggle('a'));
    expect(result.current.isSelected('a')).toBe(true);
    expect(result.current.selectedCount).toBe(1);

    act(() => result.current.toggle('a'));
    expect(result.current.isSelected('a')).toBe(false);
    expect(result.current.selectedCount).toBe(0);
  });

  it('indeterminate when a subset is selected', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b', 'c'] }),
    );
    act(() => result.current.toggle('a'));
    expect(result.current.isIndeterminate).toBe(true);
    expect(result.current.isAllSelected).toBe(false);
  });

  it('selectAll selects every id; isAllSelected becomes true', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b', 'c'] }),
    );
    act(() => result.current.selectAll());
    expect(result.current.selectedCount).toBe(3);
    expect(result.current.isAllSelected).toBe(true);
    expect(result.current.isIndeterminate).toBe(false);
  });

  it('deselectAll clears everything', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b'] }),
    );
    act(() => result.current.selectAll());
    act(() => result.current.deselectAll());
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.isAllSelected).toBe(false);
  });

  it('toggleAll flips between all-selected and empty', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b'] }),
    );
    act(() => result.current.toggleAll());
    expect(result.current.isAllSelected).toBe(true);
    act(() => result.current.toggleAll());
    expect(result.current.selectedCount).toBe(0);
  });

  it('returns the current selection as an array in input order', () => {
    const { result } = renderHook(() =>
      useBulkSelection({ allIds: ['a', 'b', 'c'] }),
    );
    act(() => result.current.toggle('c'));
    act(() => result.current.toggle('a'));
    expect(result.current.selectedIds.sort()).toEqual(['a', 'c']);
  });

  it('prunes ids that disappear from allIds between renders', () => {
    const { result, rerender } = renderHook(
      ({ ids }: { ids: string[] }) => useBulkSelection({ allIds: ids }),
      { initialProps: { ids: ['a', 'b', 'c'] } },
    );
    act(() => {
      result.current.toggle('a');
      result.current.toggle('b');
    });
    expect(result.current.selectedCount).toBe(2);

    // Page turns → `b` is no longer visible; selection should drop it.
    rerender({ ids: ['a', 'd'] });
    expect(result.current.isSelected('a')).toBe(true);
    expect(result.current.isSelected('b')).toBe(false);
    expect(result.current.selectedCount).toBe(1);
  });

  it('honours an optional filter — only "selectable" ids respond to selectAll', () => {
    const { result } = renderHook(() =>
      useBulkSelection({
        allIds: ['a', 'b', 'c'],
        isSelectable: (id) => id !== 'b',
      }),
    );
    act(() => result.current.selectAll());
    expect(result.current.selectedIds.sort()).toEqual(['a', 'c']);
    expect(result.current.isSelected('b')).toBe(false);
  });
});
