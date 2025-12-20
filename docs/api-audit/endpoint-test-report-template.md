# API Endpoint Test Report Template

**Generated**: {timestamp}  
**Base URL**: {base_url}  
**Tested By**: {username}  
**Environment**: {environment}

---

## Summary

- **Total Endpoints**: {total}
- **Tested**: {tested}
- **Working**: {working} ✅
- **Broken**: {broken} ❌
- **Deprecated**: {deprecated} ⚠️
- **Skipped**: {skipped} ⏭️

### Performance Metrics

- **Average Response Time**: {avg_ms}ms
- **P50 (Median)**: {p50_ms}ms
- **P95**: {p95_ms}ms
- **P99**: {p99_ms}ms

---

## Working Endpoints

| Endpoint | Method | Status Code | Response Time (ms) | Performance Grade |
|----------|--------|-------------|-------------------|-------------------|
| `/api/v1/auth/login/` | POST | 200 | 245 | ✅ Excellent |
| `/api/v1/assets/` | GET | 200 | 180 | ✅ Excellent |

**Performance Grades**:
- ✅ Excellent: < 200ms
- ✅ Good: 200-500ms
- ⚠️ Acceptable: 500-1000ms
- ❌ Slow: > 1000ms

---

## Broken Endpoints

| Endpoint | Method | Status Code | Error | Root Cause | Fix Required |
|----------|--------|-------------|-------|------------|--------------|
| `/api/v1/example/` | GET | 500 | Internal Server Error | Database connection issue | Yes |

---

## Deprecated Endpoints

| Endpoint | Method | Status Code | Deprecation Notice | Migration Path |
|----------|--------|-------------|---------------------|----------------|
| `/api/v1/old-endpoint/` | GET | 410 | Use `/api/v1/new-endpoint/` instead | Update clients |

---

## Skipped Endpoints

| Endpoint | Method | Reason |
|----------|--------|--------|
| `/api/v1/admin/` | GET | Requires admin authentication |
| `/api/v1/private/` | GET | Requires special permissions |

---

## Detailed Results

### POST `/api/v1/auth/login/`

- **Status**: ✅ working
- **Status Code**: 200
- **Response Time**: 245ms
- **Performance Grade**: ✅ Excellent
- **Tested At**: 2025-12-13T18:00:00Z
- **Notes**: Authentication successful

---

## Recommendations

### Performance Improvements

1. **Slow Endpoints** (> 1000ms):
   - `/api/v1/slow-endpoint/` - Consider caching or optimization

### Broken Endpoints

1. **Critical Issues**:
   - Fix database connection issues
   - Resolve authentication problems

### Deprecated Endpoints

1. **Migration Required**:
   - Update clients to use new endpoints
   - Remove deprecated endpoints in next major version

---

**Report Generated**: {timestamp}  
**Next Test**: Recommended weekly or before releases

