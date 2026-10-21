/**
 * Phase 240.4.A audit-fix Gap 1 — extracted flattening logic.
 *
 * The CommandPalette consumes a flat ``PaletteItem[]`` (label + path).
 * The Sidebar's ``NavItem`` shape carries optional ``children`` for
 * sub-menus (Phase 240.4.A.9).  Without this flattening, ⌘K only ever
 * surfaces the top-level entries — the comment at the top of
 * ``navItems.ts`` calls itself "the single source of truth for both
 * the Sidebar AND the CommandPalette", but children were silently
 * dropped by the original ``.map((item) => ({ label, path }))``.
 *
 * Output rules:
 * - Each top-level item appears as ``{label, path}``.
 * - Each child appears as ``{label: "<parent> / <child>", path: <child.path>}``
 *   so the palette label disambiguates parent vs child (e.g.
 *   "Data Quality / Anomalies" rather than just "Anomalies").
 *
 * Pure function — no DOM / React / hook dependencies — so it can be
 * unit-tested in isolation without rendering the AppShell.
 */
import type { NavItem } from './navItems';

export interface PalettePageEntry {
  label: string;
  path: string;
}

export function flattenNavItemsForPalette(items: NavItem[]): PalettePageEntry[] {
  const out: PalettePageEntry[] = [];
  for (const item of items) {
    out.push({ label: item.label, path: item.path });
    if (item.children && item.children.length > 0) {
      for (const child of item.children) {
        out.push({
          label: `${item.label} / ${child.label}`,
          path: child.path,
        });
      }
    }
  }
  return out;
}
