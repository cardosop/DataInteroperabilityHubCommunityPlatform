# File Upload Performance Fix - Root Cause Analysis & Solution

**Date**: 2026-01-27
**Status**: ✅ **ROOT CAUSE FIXED**

## Root Cause Identified

The file upload was failing with **403 Forbidden** errors because:

1. **Presigned URLs used Docker service name**: Backend generated presigned URLs with `http://minio:9000` (Docker service name)
2. **Browser can't resolve Docker service names**: Browser runs on host machine and cannot resolve `minio` hostname
3. **URL replacement broke signature**: Simply replacing `minio:9000` with `localhost:9000` broke the AWS signature validation

## Solution Implemented

### 1. ✅ Generate Presigned URLs with Correct Endpoint for Browser
**File**: `hub/apps/files/storage.py`
- Added `for_browser` parameter to `generate_presigned_upload_url()`
- When `for_browser=True`, create a temporary S3 client with `localhost:9000` endpoint
- Generate presigned URL using this client, ensuring signature is valid for `localhost:9000`

### 2. ✅ Use PUT Method for Simple Browser Uploads
**File**: `hub/apps/files/storage.py`
- Changed from presigned POST (with fields) to presigned PUT (simpler, direct upload)
- PUT method is more straightforward for direct file uploads
- Frontend already uses PUT method, so this aligns the backend with frontend

### 3. ✅ Calculate and Send SHA-256 Hash
**File**: `frontend/src/features/files/services/fileService.ts`
- Added `calculateFileHash()` method using Web Crypto API
- Calculate hash before upload (to avoid reading file twice)
- Send hash in complete request as required by backend

### 4. ✅ Add Success State to FileUpload Component
**File**: `frontend/src/features/files/components/FileUpload.tsx`
- Added `uploadSuccess` state
- Show success message for 10 seconds after upload completes
- Added CSS styling for success state

## Performance Results

**Before Fix**:
- Upload failed with 403 Forbidden
- Timeout after 30+ seconds

**After Fix**:
- ✅ Upload completes in **~447ms** for 7-byte file
- ✅ Upload completes in **~618ms** for typical CSV files
- ✅ All upload steps working: init → upload → complete

## Test Results

### ✅ Isolated File Upload Test
- **Status**: PASSING
- **Upload Time**: 447ms
- **All Steps**: ✅ Init → ✅ Upload to S3 → ✅ Complete

### ⚠️ Complete Journey Test
- **Status**: Needs optimization (file upload now works, but test has other timing issues)
- **File Upload**: ✅ Working (fast, ~600ms)
- **Remaining Issues**: Dataset creation redirect timing, contract page loading

## Files Modified

### Backend
1. `hub/apps/files/storage.py`
   - Added `for_browser` parameter to `generate_presigned_upload_url()`
   - Create temporary S3 client with localhost endpoint for browser uploads
   - Use PUT method for simple uploads

2. `hub/apps/files/views.py`
   - Pass `for_browser=True` when `upload_method == 'browser'`
   - Store `upload_method` in file metadata for chunk uploads
   - Fix chunk upload URL generation for browser

### Frontend
1. `frontend/src/features/files/services/fileService.ts`
   - Added `calculateFileHash()` method
   - Calculate hash before upload
   - Send hash in complete request

2. `frontend/src/features/files/components/FileUpload.tsx`
   - Added `uploadSuccess` state
   - Show success message after upload
   - Added console logging for debugging

3. `frontend/src/features/files/components/FileUpload.css`
   - Added success state styling

4. `frontend/src/shared/types/files.ts`
   - Updated `FileCompleteRequest` to include `content_sha256` and `parts`

5. `frontend/e2e/phase2-catalog-journey.spec.ts`
   - Improved wait conditions for upload completion
   - Wait for Create Dataset button to be enabled (reliable indicator)

## Technical Details

### Presigned URL Generation
```python
# For browser uploads, create client with localhost endpoint
if for_browser and 'minio:9000' in self.endpoint_url:
    browser_endpoint = self.endpoint_url.replace('minio:9000', 'localhost:9000')
    browser_client = boto3.client('s3', endpoint_url=browser_endpoint, ...)
    client_to_use = browser_client

# Generate presigned PUT URL
upload_url = client_to_use.generate_presigned_url('put_object', ...)
```

### SHA-256 Hash Calculation
```typescript
async calculateFileHash(file: File | Blob): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
```

## Verification

✅ **Isolated Upload Test**: Passing (447ms)
✅ **S3 Upload**: Working (200 status)
✅ **Complete Step**: Working (200 status with hash)
✅ **File Upload Component**: Shows success state

## Next Steps

1. **Complete Journey Test**: Optimize wait conditions for dataset creation redirect
2. **Performance Monitoring**: Add metrics for upload times
3. **Error Handling**: Improve error messages for upload failures

## Summary

The root cause was **presigned URLs using Docker service names that browsers can't resolve**. The fix generates presigned URLs with `localhost:9000` from the start for browser uploads, ensuring valid signatures. File uploads now complete in **< 1 second** for typical files.
