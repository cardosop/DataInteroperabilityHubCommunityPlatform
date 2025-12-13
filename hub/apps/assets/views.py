"""
Asset Views

REST API views for asset management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Asset, AssetStatus
from .serializers import (
    AssetSerializer,
    AssetCreateSerializer,
    AssetUpdateSerializer,
    AttachDatasetSerializer,
    AttachContractSerializer
)
from hub.apps.audit.utils import create_audit_event


class AssetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for asset management.
    
    Tenant-scoped: users can only see/manage assets in their tenant.
    """
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    filter_backends = [OrderingFilter, SearchFilter]
    ordering_fields = ['name', 'key', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering
    search_fields = ['name', 'key', 'description']
    
    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        user = self.request.user
        
        # Platform admins can see all assets
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = Asset.objects.all()
        else:
            # Get tenant from request (set by middleware/authentication) or user
            # Priority: request.tenant_id (most reliable) > request.tenant > user.tenant_id > user.tenant
            tenant_id = None
            
            # Try request.tenant_id first (set by authentication/middleware)
            if hasattr(self.request, "tenant_id") and self.request.tenant_id:
                tenant_id = self.request.tenant_id
                # Convert to UUID if it's a string
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None
            
            # Fallback to request.tenant object
            if not tenant_id and hasattr(self.request, "tenant") and self.request.tenant:
                tenant_id = self.request.tenant.id
            
            # Fallback to user.tenant_id (direct field access, most reliable)
            # CRITICAL: Refresh user from DB to get fresh tenant_id (important for thread safety)
            if not tenant_id and hasattr(user, "id") and user.id:
                # Query user from database to get fresh tenant_id (works in LiveServerTestCase)
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    db_user = User.objects.only('tenant_id').get(id=user.id)
                    if db_user.tenant_id:
                        tenant_id = db_user.tenant_id
                except User.DoesNotExist:
                    pass
            
            # Last resort: get from user.tenant relationship
            if not tenant_id and hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id
            
            # Regular users can only see assets in their tenant
            if tenant_id:
                # Use tenant_id for filtering (more reliable than tenant object)
                # Ensure tenant_id is a UUID for proper filtering
                if isinstance(tenant_id, str):
                    import uuid
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        return Asset.objects.none()
                # Filter by tenant_id - this is the most reliable way
                queryset = Asset.objects.filter(tenant_id=tenant_id)
            else:
                return Asset.objects.none()
        
        # Apply name filter if provided (exact match)
        name_filter = self.request.query_params.get('name')
        if name_filter:
            queryset = queryset.filter(name=name_filter)
        
        return queryset
    
    @transaction.atomic
    def create(self, request):
        """
        Create a new asset.
        
        POST /assets
        Body: {
            "key": "my-asset",
            "name": "My Asset",
            "description": "Asset description",
            "domain": "marketing",
            "visibility": "INTERNAL"
        }
        """
        serializer = AssetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        key = serializer.validated_data['key']
        name = serializer.validated_data['name']
        description = serializer.validated_data.get('description')
        domain = serializer.validated_data.get('domain')
        visibility = serializer.validated_data.get('visibility', 'INTERNAL')
        
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create assets'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if key already exists for tenant
        if Asset.objects.filter(tenant=tenant, key=key).exists():
            return Response(
                {'error': f'Asset with key "{key}" already exists for this tenant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create asset
        asset = Asset.objects.create(
            tenant=tenant,
            key=key,
            name=name,
            description=description,
            domain=domain,
            status=AssetStatus.DRAFT,
            visibility=visibility,
            created_by=request.user
        )
        
        # Log audit event
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(asset.id),
            details={
                'key': key,
                'name': name,
                'domain': domain
            },
            request=request
        )
        
        return Response(
            AssetSerializer(asset).data,
            status=status.HTTP_201_CREATED
        )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update an asset with optimistic locking.
        
        PATCH /assets/{id}
        Body: {
            "name": "Updated Name",
            "version": 1  // Required for optimistic locking
        }
        """
        asset = self.get_object()
        serializer = AssetUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Check optimistic locking
        if 'version' in serializer.validated_data:
            provided_version = serializer.validated_data['version']
            if provided_version != asset.version:
                return Response(
                    {
                        'error': 'Asset has been modified by another user',
                        'code': 'ASSET_CONCURRENT_MODIFICATION',
                        'current_version': asset.version,
                        'provided_version': provided_version
                    },
                    status=status.HTTP_409_CONFLICT
                )
        
        # Store old values for audit
        old_status = asset.status
        old_name = asset.name
        
        # Update fields
        if 'name' in serializer.validated_data:
            asset.name = serializer.validated_data['name']
        if 'description' in serializer.validated_data:
            asset.description = serializer.validated_data['description']
        if 'domain' in serializer.validated_data:
            asset.domain = serializer.validated_data['domain']
        if 'visibility' in serializer.validated_data:
            asset.visibility = serializer.validated_data['visibility']
        
        # Handle status update with validation
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            
            # Enforce ACTIVE status requirements
            if new_status == AssetStatus.ACTIVE:
                can_activate, blockers = asset.can_activate()
                if not can_activate:
                    return Response(
                        {
                            'error': 'Cannot activate asset: requirements not met',
                            'code': 'ASSET_ACTIVATION_BLOCKED',
                            'details': blockers
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            asset.status = new_status
        
        # Validate asset before saving
        try:
            asset.full_clean()
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Increment version for optimistic locking
        asset.increment_version()
        
        # Save the asset
        asset.save()
        
        # Log audit event
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_UPDATED",
            actor_user=request.user,
            tenant=asset.tenant,
            resource_id=str(asset.id),
            details={
                'old_status': old_status,
                'new_status': asset.status,
                'old_name': old_name,
                'new_name': asset.name
            },
            request=request
        )
        
        return Response(
            AssetSerializer(asset).data,
            status=status.HTTP_200_OK
        )
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete an asset (soft delete: set status to RETIRED).
        
        DELETE /assets/{id}
        """
        asset = self.get_object()
        
        # Soft delete: set status to RETIRED
        asset.status = AssetStatus.RETIRED
        asset.increment_version()
        asset.save()
        
        # Unpublish any marketplace listings for this asset
        from hub.apps.marketplace.models import Listing, ListingStatus
        Listing.objects.filter(
            asset=asset,
            status=ListingStatus.PUBLISHED
        ).update(status=ListingStatus.UNLISTED)
        
        # Log audit event
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_DELETED",
            actor_user=request.user,
            tenant=asset.tenant,
            resource_id=str(asset.id),
            details={
                'key': asset.key,
                'name': asset.name
            },
            request=request
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='datasets')
    def attach_dataset(self, request, id=None):
        """
        Attach a dataset to an asset.
        
        POST /assets/{id}/datasets
        Body: {
            "dataset_id": "uuid"
        }
        """
        asset = self.get_object()
        serializer = AttachDatasetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        dataset_id = serializer.validated_data['dataset_id']
        
        # Get dataset
        try:
            from hub.apps.datasets.models import Dataset
            dataset = Dataset.objects.get(id=dataset_id, tenant=asset.tenant)
        except Dataset.DoesNotExist:
            return Response(
                {'error': 'Dataset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Attach dataset to asset
        dataset.asset = asset
        
        # Get next version for asset
        latest_dataset = asset.datasets.order_by('-version').first()
        if latest_dataset:
            dataset.version = latest_dataset.version + 1
        else:
            dataset.version = 1
        
        dataset.save(update_fields=['asset', 'version'])
        
        # Log audit event
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_DATASET_ATTACHED",
            actor_user=request.user,
            tenant=asset.tenant,
            resource_id=str(asset.id),
            details={
                'dataset_id': str(dataset_id),
                'dataset_version': dataset.version
            },
            request=request
        )
        
        return Response(
            {
                'asset_id': str(asset.id),
                'dataset_id': str(dataset_id),
                'dataset_version': dataset.version,
                'message': 'Dataset attached successfully'
            },
            status=status.HTTP_200_OK
        )
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='contracts')
    def attach_contract(self, request, id=None):
        """
        Attach a contract to an asset.
        
        POST /assets/{id}/contracts
        Body: {
            "contract_id": "uuid"
        }
        """
        asset = self.get_object()
        serializer = AttachContractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        contract_id = serializer.validated_data['contract_id']
        
        # Get contract
        try:
            from hub.apps.contracts.models import Contract
            contract = Contract.objects.get(id=contract_id, tenant=asset.tenant)
        except Contract.DoesNotExist:
            return Response(
                {'error': 'Contract not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Attach contract to asset
        contract.asset = asset
        
        # Get next version for asset
        latest_contract = asset.contracts.order_by('-version').first()
        if latest_contract:
            contract.version = latest_contract.version + 1
        else:
            contract.version = 1
        
        contract.save(update_fields=['asset', 'version'])
        
        # Remap contract to semantic store to include fields now that asset is linked
        # Fields are only mapped when asset_uuid is available, so remapping is needed
        if contract.hub_contract_json:
            try:
                from hub.apps.semantic.utils import remap_contract_if_needed
                remap_contract_if_needed(contract, tenant=contract.tenant)
            except Exception as e:
                # Log error but don't fail the attachment
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to remap contract {contract.id} after asset attachment: {e}",
                    exc_info=True
                )
        
        # Log audit event
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CONTRACT_ATTACHED",
            actor_user=request.user,
            tenant=asset.tenant,
            resource_id=str(asset.id),
            details={
                'contract_id': str(contract_id),
                'contract_version': contract.version
            },
            request=request
        )
        
        return Response(
            {
                'asset_id': str(asset.id),
                'contract_id': str(contract_id),
                'contract_version': contract.version,
                'message': 'Contract attached successfully'
            },
            status=status.HTTP_200_OK
        )
    
    def list(self, request, *args, **kwargs):
        """List assets (tenant-scoped)"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve asset by ID"""
        return super().retrieve(request, *args, **kwargs)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, id=None):
        """
        Activate an asset.
        
        POST /assets/{id}/activate
        Body: {
            "version": 1  // Required for optimistic locking
        }
        
        Checks all activation requirements:
        - Contract: ACTIVE status, VALID/WARNING_ONLY validation, NORMALIZED_OK/WITH_WARNINGS
        - DQ: PASS or WARN (if dataset exists)
        - Compliance: PASS or WARN (if dataset exists)
        - Contract-only assets (no dataset) are allowed
        """
        asset = self.get_object()
        
        # Get version for optimistic locking
        version = request.data.get('version')
        if version is None:
            return Response(
                {
                    'error': 'version field is required for optimistic locking',
                    'code': 'VALIDATION_ERROR'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check optimistic locking
        if int(version) != asset.version:
            return Response(
                {
                    'error': 'Asset has been modified by another user',
                    'code': 'ASSET_CONCURRENT_MODIFICATION',
                    'current_version': asset.version,
                    'provided_version': version
                },
                status=status.HTTP_409_CONFLICT
            )
        
        # Check if already active
        if asset.status == AssetStatus.ACTIVE:
            return Response(
                {
                    'error': 'Asset is already ACTIVE',
                    'code': 'ASSET_ALREADY_ACTIVE'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if retired (cannot reactivate)
        if asset.status == AssetStatus.RETIRED:
            return Response(
                {
                    'error': 'Retired assets cannot be reactivated',
                    'code': 'ASSET_RETIRED'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check activation requirements
        can_activate, blockers = asset.can_activate()
        if not can_activate:
            return Response(
                {
                    'error': 'Cannot activate asset: requirements not met',
                    'code': 'ASSET_ACTIVATION_BLOCKED',
                    'details': blockers
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store old status for audit
        old_status = asset.status
        
        # Activate asset
        asset.status = AssetStatus.ACTIVE
        
        # Validate asset before saving
        try:
            asset.full_clean()
        except DjangoValidationError as e:
            return Response(
                {
                    'error': str(e),
                    'code': 'VALIDATION_ERROR'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Increment version and save status
        asset.increment_version()
        asset.save(update_fields=['status', 'updated_at'])
        
        # Trigger semantic mapping (async via job in production)
        try:
            from hub.apps.semantic.utils import map_asset_to_semantic
            map_asset_to_semantic(asset, tenant=asset.tenant)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Semantic mapping failed for asset {asset.id}: {e}", exc_info=True)
            # Don't fail activation if semantic mapping fails
        
        # Log audit event
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_ACTIVATED",
            actor_user=request.user,
            tenant=asset.tenant,
            resource_id=str(asset.id),
            details={
                'old_status': old_status,
                'new_status': AssetStatus.ACTIVE,
                'key': asset.key,
                'name': asset.name,
                'has_dataset': asset.datasets.exists(),
                'has_contract': asset.contracts.filter(status="ACTIVE").exists()
            },
            request=request
        )
        
        return Response(
            AssetSerializer(asset).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'], url_path='recommendations')
    def recommendations(self, request):
        """
        Get asset recommendations.
        
        GET /api/v1/assets/assets/recommendations/
        
        Query Parameters:
        - user_id: Optional user UUID for personalized recommendations
        - asset_id: Optional asset UUID for "similar to" recommendations
        - limit: Maximum number of recommendations (default: 10)
        - include_usage_patterns: Include usage-based recommendations (default: true)
        - include_lineage: Include lineage-based recommendations (default: true)
        - include_user_behavior: Include user behavior-based recommendations (default: true)
        """
        from .recommendations import AssetRecommendationService
        
        tenant_id = self._get_tenant_id()
        user_id = request.query_params.get('user_id')
        asset_id = request.query_params.get('asset_id')
        limit = int(request.query_params.get('limit', 10))
        include_usage_patterns = request.query_params.get('include_usage_patterns', 'true').lower() == 'true'
        include_lineage = request.query_params.get('include_lineage', 'true').lower() == 'true'
        include_user_behavior = request.query_params.get('include_user_behavior', 'true').lower() == 'true'
        
        recommendations = AssetRecommendationService.get_recommendations(
            tenant_id=str(tenant_id),
            user_id=user_id,
            asset_id=asset_id,
            limit=limit,
            include_usage_patterns=include_usage_patterns,
            include_lineage=include_lineage,
            include_user_behavior=include_user_behavior
        )
        
        return Response(recommendations, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='track-view')
    def track_view(self, request, id=None):
        """
        Track an asset view.
        
        POST /api/v1/assets/assets/{id}/track-view/
        """
        from .popularity import AssetPopularityService
        
        asset = self.get_object()
        tenant_id = self._get_tenant_id()
        
        AssetPopularityService.track_view(str(asset.id), str(tenant_id))
        
        return Response(
            {'status': 'view tracked'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'], url_path='track-download')
    def track_download(self, request, id=None):
        """
        Track an asset download.
        
        POST /api/v1/assets/assets/{id}/track-download/
        """
        from .popularity import AssetPopularityService
        
        asset = self.get_object()
        tenant_id = self._get_tenant_id()
        
        AssetPopularityService.track_download(str(asset.id), str(tenant_id))
        
        return Response(
            {'status': 'download tracked'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'], url_path='health-score')
    def health_score(self, request, id=None):
        """
        Get asset health score.
        
        GET /api/v1/assets/assets/{id}/health-score/
        
        Query Parameters:
        - recalculate: Recalculate health score (default: false)
        - breakdown: Include component breakdown (default: false)
        """
        from .health_score import AssetHealthScoreService
        
        asset = self.get_object()
        recalculate = request.query_params.get('recalculate', 'false').lower() == 'true'
        include_breakdown = request.query_params.get('breakdown', 'false').lower() == 'true'
        
        if recalculate:
            AssetHealthScoreService.calculate_health_score(asset)
            asset.refresh_from_db()
        
        response = {
            'asset_id': str(asset.id),
            'health_score': asset.health_score,
            'dq_status': asset.dq_status,
            'compliance_status': asset.compliance_status
        }
        
        if include_breakdown:
            breakdown = AssetHealthScoreService.get_health_score_breakdown(asset)
            response['breakdown'] = breakdown
        
        return Response(response, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='dependencies')
    def dependencies(self, request, id=None):
        """
        Get asset dependency graph.
        
        GET /api/v1/assets/assets/{id}/dependencies/
        
        Query Parameters:
        - direction: "upstream", "downstream", or "both" (default: "both")
        - max_depth: Maximum traversal depth (default: 10)
        - format: "json", "d3", "dot", or "mermaid" (default: "json")
        """
        from .dependencies import AssetDependencyService
        
        asset = self.get_object()
        tenant_id = self._get_tenant_id()
        
        direction = request.query_params.get('direction', 'both')
        max_depth = int(request.query_params.get('max_depth', 10))
        format_type = request.query_params.get('format', 'json')
        
        # Generate dependency graph
        graph = AssetDependencyService.generate_dependency_graph(
            asset_id=str(asset.id),
            tenant_id=str(tenant_id),
            direction=direction,
            max_depth=max_depth
        )
        
        # Get statistics
        stats = AssetDependencyService.get_dependency_stats(graph)
        
        # Format response
        if format_type == 'd3':
            response_data = graph.to_d3_format()
        elif format_type == 'dot':
            response_data = {"dot": graph.to_dot_format()}
        elif format_type == 'mermaid':
            response_data = {"mermaid": graph.to_mermaid_format()}
        else:  # json
            response_data = graph.to_dict()
        
        response_data['stats'] = stats
        
        return Response(response_data, status=status.HTTP_200_OK)

