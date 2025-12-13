"""
Governance Views

REST API views for access analytics and certification.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .access_analytics import AccessAnalyticsService, AccessLog
from .access_certification import AccessCertificationService, AccessCertification


class AccessAnalyticsViewSet(viewsets.ViewSet):
    """
    ViewSet for access analytics dashboard.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def _get_tenant_id(self, request):
        """Get tenant ID from request"""
        if hasattr(request, "tenant_id") and request.tenant_id:
            return str(request.tenant_id)
        
        tenant = getattr(request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)
        
        return None
    
    @extend_schema(
        summary="Get access analytics dashboard",
        description="Get complete access analytics dashboard with patterns, anomalies, and security events",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='Start date (ISO format)',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='End date (ISO format)',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(description="Access analytics dashboard data"),
        },
        tags=['Access Analytics']
    )
    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """
        Get access analytics dashboard.
        
        GET /api/v1/access/analytics/dashboard/
        """
        tenant_id = self._get_tenant_id(request)
        
        # Parse date parameters
        start_date = None
        end_date = None
        
        if 'start_date' in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params['start_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")
        
        if 'end_date' in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params['end_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")
        
        dashboard_data = AccessAnalyticsService.get_analytics_dashboard(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return Response(dashboard_data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Get access patterns",
        description="Get access patterns for analysis",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='User UUID filter',
                required=False
            ),
            OpenApiParameter(
                name='resource_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Resource type filter',
                required=False
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='Start date (ISO format)',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='End date (ISO format)',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of access patterns"),
        },
        tags=['Access Analytics']
    )
    @action(detail=False, methods=['get'], url_path='patterns')
    def patterns(self, request):
        """
        Get access patterns.
        
        GET /api/v1/access/analytics/patterns/
        """
        tenant_id = self._get_tenant_id(request)
        user_id = request.query_params.get('user_id')
        resource_type = request.query_params.get('resource_type')
        
        start_date = None
        end_date = None
        
        if 'start_date' in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params['start_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")
        
        if 'end_date' in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params['end_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")
        
        patterns = AccessAnalyticsService.get_access_patterns(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date
        )
        
        return Response(patterns, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Get anomalies",
        description="Get detected access anomalies",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='Start date (ISO format)',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='End date (ISO format)',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of results (default: 100)',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of anomalies"),
        },
        tags=['Access Analytics']
    )
    @action(detail=False, methods=['get'], url_path='anomalies')
    def anomalies(self, request):
        """
        Get anomalies.
        
        GET /api/v1/access/analytics/anomalies/
        """
        tenant_id = self._get_tenant_id(request)
        limit = int(request.query_params.get('limit', 100))
        
        start_date = None
        end_date = None
        
        if 'start_date' in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params['start_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")
        
        if 'end_date' in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params['end_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")
        
        anomalies = AccessAnalyticsService.get_anomalies(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return Response(anomalies, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Get security events",
        description="Get security events (denied access, anomalies)",
        parameters=[
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='Start date (ISO format)',
                required=False
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description='End date (ISO format)',
                required=False
            ),
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Maximum number of results (default: 100)',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of security events"),
        },
        tags=['Access Analytics']
    )
    @action(detail=False, methods=['get'], url_path='security-events')
    def security_events(self, request):
        """
        Get security events.
        
        GET /api/v1/access/analytics/security-events/
        """
        tenant_id = self._get_tenant_id(request)
        limit = int(request.query_params.get('limit', 100))
        
        start_date = None
        end_date = None
        
        if 'start_date' in request.query_params:
            try:
                start_date = timezone.datetime.fromisoformat(
                    request.query_params['start_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid start_date format. Use ISO format.")
        
        if 'end_date' in request.query_params:
            try:
                end_date = timezone.datetime.fromisoformat(
                    request.query_params['end_date'].replace('Z', '+00:00')
                )
            except ValueError:
                raise ValidationError("Invalid end_date format. Use ISO format.")
        
        events = AccessAnalyticsService.get_security_events(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return Response(events, status=status.HTTP_200_OK)


class AccessCertificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for access certification management.
    """
    queryset = AccessCertification.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all certifications
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return AccessCertification.objects.all()
        
        # Get tenant from request
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            return AccessCertification.objects.none()
        
        return AccessCertification.objects.filter(tenant_id=tenant_id)
    
    def _get_tenant_id(self):
        """Get tenant ID from request"""
        if hasattr(self.request, "tenant_id") and self.request.tenant_id:
            return str(self.request.tenant_id)
        
        tenant = getattr(self.request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)
        
        return None
    
    @extend_schema(
        summary="Review certification",
        description="Review and approve/reject a certification",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'enum': ['APPROVED', 'REJECTED']},
                    'review_notes': {'type': 'string'}
                },
                'required': ['status']
            }
        },
        responses={
            200: OpenApiResponse(description="Certification reviewed"),
            400: OpenApiResponse(description="Invalid request"),
        },
        tags=['Access Certification']
    )
    @action(detail=True, methods=['post'], url_path='review')
    def review(self, request, id=None):
        """
        Review certification.
        
        POST /api/v1/access/certifications/{id}/review/
        """
        certification = self.get_object()
        
        status_value = request.data.get('status')
        review_notes = request.data.get('review_notes')
        
        if status_value not in ['APPROVED', 'REJECTED']:
            raise ValidationError("status must be 'APPROVED' or 'REJECTED'")
        
        updated = AccessCertificationService.review_certification(
            certification_id=str(certification.id),
            reviewer_id=str(request.user.id),
            status=status_value,
            review_notes=review_notes
        )
        
        return Response({
            'id': str(updated.id),
            'status': updated.status,
            'reviewed_by': str(updated.reviewer.id) if updated.reviewer else None,
            'review_notes': updated.review_notes
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Get expiring certifications",
        description="Get certifications expiring within specified days",
        parameters=[
            OpenApiParameter(
                name='days_ahead',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Days ahead to check (default: 30)',
                required=False
            ),
        ],
        responses={
            200: OpenApiResponse(description="List of expiring certifications"),
        },
        tags=['Access Certification']
    )
    @action(detail=False, methods=['get'], url_path='expiring')
    def expiring(self, request):
        """
        Get expiring certifications.
        
        GET /api/v1/access/certifications/expiring/
        """
        tenant_id = self._get_tenant_id()
        days_ahead = int(request.query_params.get('days_ahead', 30))
        
        certifications = AccessCertificationService.get_expiring_certifications(
            tenant_id=tenant_id,
            days_ahead=days_ahead
        )
        
        result = []
        for cert in certifications:
            result.append({
                'id': str(cert.id),
                'user_id': str(cert.user.id),
                'user_email': cert.user.email,
                'certification_type': cert.certification_type,
                'status': cert.status,
                'expires_at': cert.expires_at.isoformat(),
                'days_until_expiration': cert.days_until_expiration()
            })
        
        return Response(result, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Get certification summary",
        description="Get certification summary statistics",
        responses={
            200: OpenApiResponse(description="Certification summary"),
        },
        tags=['Access Certification']
    )
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Get certification summary.
        
        GET /api/v1/access/certifications/summary/
        """
        tenant_id = self._get_tenant_id()
        
        summary = AccessCertificationService.get_certification_summary(
            tenant_id=tenant_id
        )
        
        return Response(summary, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Initiate periodic review",
        description="Initiate a periodic access review for a user",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_id': {'type': 'string', 'format': 'uuid'},
                    'reviewer_id': {'type': 'string', 'format': 'uuid'}
                },
                'required': ['user_id', 'reviewer_id']
            }
        },
        responses={
            201: OpenApiResponse(description="Review initiated"),
            400: OpenApiResponse(description="Invalid request"),
        },
        tags=['Access Certification']
    )
    @action(detail=False, methods=['post'], url_path='initiate-review')
    def initiate_review(self, request):
        """
        Initiate periodic review.
        
        POST /api/v1/access/certifications/initiate-review/
        """
        tenant_id = self._get_tenant_id()
        user_id = request.data.get('user_id')
        reviewer_id = request.data.get('reviewer_id')
        
        if not user_id or not reviewer_id:
            raise ValidationError("user_id and reviewer_id are required")
        
        certification = AccessCertificationService.initiate_periodic_review(
            tenant_id=tenant_id,
            user_id=user_id,
            reviewer_id=reviewer_id
        )
        
        return Response({
            'id': str(certification.id),
            'user_id': str(certification.user.id),
            'status': certification.status,
            'reviewer_id': str(certification.reviewer.id) if certification.reviewer else None
        }, status=status.HTTP_201_CREATED)

