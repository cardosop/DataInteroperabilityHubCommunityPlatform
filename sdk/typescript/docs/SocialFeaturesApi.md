# SocialFeaturesApi

All URIs are relative to */api/v1*

|Method | HTTP request | Description|
|------------- | ------------- | -------------|
|[**createOrJoinCommunity**](#createorjoincommunity) | **POST** /api/v1/social/communities/ | |
|[**socialCommentsList**](#socialcommentslist) | **GET** /api/v1/social/comments/ | |
|[**socialCommentsRetrieve**](#socialcommentsretrieve) | **GET** /api/v1/social/comments/{id}/ | |
|[**socialRatingsList**](#socialratingslist) | **GET** /api/v1/social/ratings/ | |
|[**socialReviewsList**](#socialreviewslist) | **GET** /api/v1/social/reviews/ | |
|[**socialReviewsRetrieve**](#socialreviewsretrieve) | **GET** /api/v1/social/reviews/{id}/ | |
|[**submitComment**](#submitcomment) | **POST** /api/v1/social/comments/ | |
|[**submitRating**](#submitrating) | **POST** /api/v1/social/ratings/ | |
|[**submitReview**](#submitreview) | **POST** /api/v1/social/reviews/ | |

# **createOrJoinCommunity**
> Community createOrJoinCommunity(communityRequest)

Create or join a community.  POST /api/v1/social/communities/  Users can create new communities or join existing ones.

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration,
    CommunityRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let communityRequest: CommunityRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.createOrJoinCommunity(
    communityRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **communityRequest** | **CommunityRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Community**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **socialCommentsList**
> Array<Comment> socialCommentsList()

List comments for an asset.  GET /api/v1/social/comments/?asset_id=xxx  Required for asset page comments display.

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let assetId: string; //Asset UUID (default to undefined)
let page: number; //Page number (optional) (default to undefined)
let pageSize: number; //Items per page (optional) (default to undefined)
let parentCommentId: string; //Filter by parent (for threaded replies) (optional) (default to undefined)

const { status, data } = await apiInstance.socialCommentsList(
    assetId,
    page,
    pageSize,
    parentCommentId
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID | defaults to undefined|
| **page** | [**number**] | Page number | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page | (optional) defaults to undefined|
| **parentCommentId** | [**string**] | Filter by parent (for threaded replies) | (optional) defaults to undefined|


### Return type

**Array<Comment>**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **socialCommentsRetrieve**
> Comment socialCommentsRetrieve()

Get comment by ID.  GET /api/v1/social/comments/{id}/

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.socialCommentsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**Comment**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **socialRatingsList**
> Array<Rating> socialRatingsList()

List ratings for an asset.  GET /api/v1/social/ratings/?asset_id=xxx  Required for asset page ratings display (E2E social.spec.ts).

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let assetId: string; //Asset UUID (default to undefined)
let page: number; //Page number (optional) (default to undefined)
let pageSize: number; //Items per page (optional) (default to undefined)

const { status, data } = await apiInstance.socialRatingsList(
    assetId,
    page,
    pageSize
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID | defaults to undefined|
| **page** | [**number**] | Page number | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page | (optional) defaults to undefined|


### Return type

**Array<Rating>**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **socialReviewsList**
> Array<Review> socialReviewsList()

List reviews for an asset.  GET /api/v1/social/reviews/?asset_id=xxx  Required for asset page reviews display (E2E social.spec.ts).

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let assetId: string; //Asset UUID (default to undefined)
let page: number; //Page number (optional) (default to undefined)
let pageSize: number; //Items per page (optional) (default to undefined)
let status: string; //Filter by status (APPROVED, PENDING, REJECTED) (optional) (default to undefined)

const { status, data } = await apiInstance.socialReviewsList(
    assetId,
    page,
    pageSize,
    status
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **assetId** | [**string**] | Asset UUID | defaults to undefined|
| **page** | [**number**] | Page number | (optional) defaults to undefined|
| **pageSize** | [**number**] | Items per page | (optional) defaults to undefined|
| **status** | [**string**] | Filter by status (APPROVED, PENDING, REJECTED) | (optional) defaults to undefined|


### Return type

**Array<Review>**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **socialReviewsRetrieve**
> Review socialReviewsRetrieve()

Get review by ID.  GET /api/v1/social/reviews/{id}/

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let id: string; // (default to undefined)

const { status, data } = await apiInstance.socialReviewsRetrieve(
    id
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **id** | [**string**] |  | defaults to undefined|


### Return type

**Review**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**200** |  |  -  |
|**400** | Bad Request - Validation error or invalid request data |  -  |
|**401** | Unauthorized - Authentication required |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **submitComment**
> Comment submitComment(commentRequest)

Submit comment on an asset via service layer (Phase 12.3.1).  POST /api/v1/social/comments/  Supports threaded comments (replies to comments). Comments support @mentions and moderation.

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration,
    CommentRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let commentRequest: CommentRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.submitComment(
    commentRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **commentRequest** | **CommentRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Comment**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **submitRating**
> Rating submitRating(ratingRequest)

Submit rating for an asset.  POST /api/v1/social/ratings/  Users can rate assets from 1-5 stars. Rate limit: 10 ratings per hour per user per asset.

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration,
    RatingRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let ratingRequest: RatingRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.submitRating(
    ratingRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **ratingRequest** | **RatingRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Rating**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **submitReview**
> Review submitReview(reviewRequest)

Submit review for an asset via service layer (Phase 12.3.1).  POST /api/v1/social/reviews/  Users can write detailed reviews for assets. Reviews support moderation workflow.

### Example

```typescript
import {
    SocialFeaturesApi,
    Configuration,
    ReviewRequest
} from './api';

const configuration = new Configuration();
const apiInstance = new SocialFeaturesApi(configuration);

let reviewRequest: ReviewRequest; //
let idempotencyKey: string; //Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. (optional) (default to undefined)

const { status, data } = await apiInstance.submitReview(
    reviewRequest,
    idempotencyKey
);
```

### Parameters

|Name | Type | Description  | Notes|
|------------- | ------------- | ------------- | -------------|
| **reviewRequest** | **ReviewRequest**|  | |
| **idempotencyKey** | [**string**] | Idempotency key for ensuring request idempotency. Provide a unique key (UUID or 8-256 alphanumeric characters) to prevent duplicate processing of the same request. The same key with the same request body will return the cached response. Required for POST, PUT, and PATCH operations. | (optional) defaults to undefined|


### Return type

**Review**

### Authorization

[APIKeyAuthentication](../README.md#APIKeyAuthentication), [BearerAuth](../README.md#BearerAuth)

### HTTP request headers

 - **Content-Type**: application/json, multipart/form-data, application/x-www-form-urlencoded
 - **Accept**: application/json


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
|**201** |  |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  * Idempotency-Replayed - Indicates whether the response was replayed from cache. Set to \&#39;true\&#39; when a cached response is returned for a duplicate request. Not present for new requests. <br>  |
|**400** | Bad Request - Validation error or invalid request data |  * Idempotency-Key - Echoes back the idempotency key provided in the request header. Present when an Idempotency-Key header was included in the request. <br>  |
|**401** | Unauthorized - Authentication required |  -  |
|**404** | Not Found - Resource not found |  -  |
|**403** | Forbidden - Insufficient permissions |  -  |
|**429** | Too Many Requests - Rate limit exceeded |  -  |
|**500** | Internal Server Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

