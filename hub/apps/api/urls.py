from django.urls import path, include, re_path
from .views import OpenAPISchemaView, SwaggerUIView, ReDocView, api_info, api_not_found

urlpatterns = [
    # API info endpoint
    path('', api_info, name='api-info'),
    
    # API v1 endpoints
    path('auth/', include('hub.apps.auth.urls')),
    path('tenants/', include('hub.apps.tenants.urls')),
    path('users/', include('hub.apps.users.urls')),
    path('audit/', include('hub.apps.audit.urls')),
    path('files/', include('hub.apps.files.urls')),
    path('datasets/', include('hub.apps.datasets.urls')),
    path('jobs/', include('hub.apps.jobs.urls')),
    path('contracts/', include('hub.apps.contracts.urls')),
    path('assets/', include('hub.apps.assets.urls')),
    path('dq/', include('hub.apps.dq.urls')),
    path('compliance/', include('hub.apps.compliance.urls')),
    path('semantic/', include('hub.apps.semantic.urls')),
    path('marketplace/', include('hub.apps.marketplace.urls')),
    
    # Catch-all for non-existent API endpoints (must be last)
    # This will only match if none of the above patterns matched
    # Use a more specific pattern that doesn't interfere with router actions
    re_path(r'^(?!auth/|tenants/|users/|audit/|files/|datasets/|jobs/|contracts/|assets/|dq/|compliance/|semantic/|marketplace/).*$', api_not_found, name='api-not-found'),
]
