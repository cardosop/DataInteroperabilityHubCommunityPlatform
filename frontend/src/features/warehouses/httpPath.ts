/**
 * The 3.6 http_path derivation contract (openspec wire-databricks-dlt-movement
 * task 6.8, design D8) — the stored value is the DERIVED
 * `/sql/1.0/warehouses/{id}` path (the backend's `resolve_warehouse_id`
 * accepts both the bare id and this path form, sql_statements.py), never a
 * hand-typed string.
 */

export const DATABRICKS_HTTP_PATH_PREFIX = '/sql/1.0/warehouses/';

/** The stored value: `/sql/1.0/warehouses/{id}` — derived, never typed. */
export function deriveWarehouseHttpPath(warehouseId: string): string {
  return `${DATABRICKS_HTTP_PATH_PREFIX}${warehouseId}`;
}

/** Parse a stored path back to the warehouse id (undefined otherwise). */
export function warehouseIdFromHttpPath(
  path: string | undefined,
): string | undefined {
  if (!path?.startsWith(DATABRICKS_HTTP_PATH_PREFIX)) {
    return undefined;
  }
  const id = path.slice(DATABRICKS_HTTP_PATH_PREFIX.length);
  return id || undefined;
}
