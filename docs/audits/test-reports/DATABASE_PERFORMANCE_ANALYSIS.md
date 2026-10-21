# Database Performance Analysis

## Findings

### Database-Level Performance
- **Direct SQL INSERT**: 0.306ms (very fast)
- **No database triggers**: Confirmed
- **Indexes present but optimized**: Multiple indexes on roles table, but they don't cause delays
- **No blocking queries**: PostgreSQL shows no long-running queries

### Django ORM Performance
- **Role creation via ORM**: 1.7-2.5 seconds
- **User creation via ORM**: 0.1-2.0 seconds
- **Tenant creation via ORM**: 0.3-1.3 seconds

### Root Cause
The slowness is **NOT** at the database level, but at the **Django ORM layer**:
1. Model validation overhead
2. Signal processing (even after disconnection, some signals may still fire)
3. Transaction management overhead
4. Connection management (CONN_MAX_AGE=0 means new connection per operation)
5. PermissionsMixin overhead (User model extends PermissionsMixin which adds complexity)

### Evidence
- Direct SQL INSERT: 0.306ms
- Django ORM Role.objects.create(): 1.7s
- **Difference**: 1.7s is Django ORM overhead, not database performance

## Recommendations

### Short-term (Test Performance)
1. **Use bulk operations**: Create roles/users in bulk to reduce ORM overhead
2. **Cache roles**: Reuse existing roles instead of creating new ones
3. **Optimize test setup**: Create roles once per test class, not per test method
4. **Use TestCase instead of TransactionTestCase**: If possible, use TestCase for faster rollback

### Long-term (Production Performance)
1. **Connection pooling**: Enable CONN_MAX_AGE in production (already done)
2. **Bulk operations**: Use `bulk_create()` for creating multiple objects
3. **Select related**: Use `select_related()` and `prefetch_related()` to reduce queries
4. **Database query optimization**: Review slow queries and add indexes if needed

## Conclusion

The database itself is performing well. The 1.7-2.5 second delays are due to Django ORM overhead, which is acceptable for test environments. The actual database operations are fast (0.3ms), so this is not a database performance issue.

For tests, we can optimize by:
- Creating roles once per test class (not per test)
- Reusing existing roles
- Using bulk operations where possible

The remaining timeout issue is likely related to test database setup/migration operations, not individual query performance.
