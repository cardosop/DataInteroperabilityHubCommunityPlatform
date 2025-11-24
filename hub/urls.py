"""
URL configuration for hub project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from hub.apps.api.views import OpenAPISchemaView, SwaggerUIView, ReDocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('hub.apps.api.urls')),
    path('graphql/', include('hub.apps.graphql.urls')),
    path('health/', include('hub.apps.health.urls')),
    
    # Observability
    path('metrics/', include('hub.apps.observability.urls')),
    
    # API Documentation
    path('api-docs/openapi.json', OpenAPISchemaView.as_view(), name='openapi-schema'),
    path('api-docs/', SwaggerUIView.as_view(url_name='openapi-schema'), name='swagger-ui'),
    path('api-docs/redoc/', ReDocView.as_view(url_name='openapi-schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

