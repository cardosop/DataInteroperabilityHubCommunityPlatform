"""
Contract Views

REST API views for contract management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Contract, ContractStatus, NormalizationStatus, ValidationStatus
from .serializers import ContractSerializer, ContractCreateSerializer, ContractUpdateSerializer
from .normalization import (
    normalize_contract,
    validate_hubcontract_schema
)
from .cli_client import (
    DataContractCLIClient,
    interpret_validation_status,
    group_errors_by_category,
    SYNC_TIMEOUT
)
from .migration_manager import ContractMigrationManager
from .migration import MigrationStrategy, get_current_hubcontract_version
from hub.apps.audit.utils import create_audit_event
from hub.apps.jobs.utils import create_job
from hub.apps.jobs.models import JobType


class ContractViewSet(viewsets.ModelViewSet):
    """
    ViewSet for contract management.
    
    Tenant-scoped: users can only see/manage contracts in their tenant.
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"
    
    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user
        
        # Platform admins can see all contracts
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return Contract.objects.all()
        
        # Regular users can only see contracts in their tenant
        if hasattr(user, "tenant") and user.tenant:
            return Contract.objects.filter(tenant=user.tenant)
        
        return Contract.objects.none()
    
    @transaction.atomic
    def create(self, request):
        """
        Create a new contract.
        
        POST /contracts
        Body: {
            "asset_id": "uuid" (optional),
            "original_raw": "contract content",
            "original_format": "JSON" or "YAML",
            "original_spec_type": "ODCS" or "DATACONTRACT_COM" (optional)
        }
        """
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        original_raw = serializer.validated_data['original_raw']
        original_format = serializer.validated_data['original_format']
        original_spec_type = serializer.validated_data.get('original_spec_type')
        asset_id = serializer.validated_data.get('asset_id')
        
        # Get tenant from user
        tenant = request.user.tenant if hasattr(request.user, 'tenant') and request.user.tenant else None
        if not tenant:
            return Response(
                {'error': 'User must belong to a tenant to create contracts'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get asset if provided
        asset = None
        if asset_id:
            try:
                from hub.apps.assets.models import Asset
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Exception:
                return Response(
                    {'error': 'Asset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get next version for asset (if asset provided)
        version = 1
        if asset:
            latest_contract = Contract.objects.filter(
                tenant=tenant,
                asset=asset
            ).order_by('-version').first()
            if latest_contract:
                version = latest_contract.version + 1
        
        # Normalize contract
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
            raw_contract=original_raw,
            format=original_format,
            spec_type=original_spec_type
        )
        
        # Use provided spec_type or detected
        final_spec_type = original_spec_type or detected_spec_type
        final_spec_version = detected_spec_version
        
        # Validate HubContract schema if normalization succeeded
        if hub_contract:
            is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
            if not is_valid:
                norm_status = NormalizationStatus.NORMALIZATION_FAILED
                norm_errors.extend(validation_errors)
                hub_contract = None
        
        # Create contract
        contract = Contract.objects.create(
            tenant=tenant,
            asset=asset,
            version=version,
            status=ContractStatus.DRAFT,
            original_spec_type=final_spec_type,
            original_spec_version=final_spec_version,
            original_format=original_format,
            original_raw=original_raw,
            hub_contract_version="1.0.0" if hub_contract else None,
            hub_contract_json=hub_contract,
            normalization_status=norm_status,
            normalization_errors=norm_errors,
            normalization_warnings=norm_warnings,
            created_by=request.user
        )
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(contract.id),
            details={
                'original_spec_type': final_spec_type,
                'original_spec_version': final_spec_version,
                'normalization_status': norm_status,
                'asset_id': str(asset_id) if asset_id else None
            },
            request=request
        )
        
        return Response(
            ContractSerializer(contract).data,
            status=status.HTTP_201_CREATED
        )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update a contract.
        
        PATCH /contracts/{id}
        Body: {
            "original_raw": "updated contract content" (optional),
            "original_format": "JSON" or "YAML" (optional),
            "status": "DRAFT" | "ACTIVE" | "RETIRED" (optional)
        }
        """
        contract = self.get_object()
        serializer = ContractUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Store old values for audit
        old_status = contract.status
        old_hub_contract_json = contract.hub_contract_json
        
        # Update original_raw if provided
        if 'original_raw' in serializer.validated_data:
            contract.original_raw = serializer.validated_data['original_raw']
            
            # Update format if provided
            if 'original_format' in serializer.validated_data:
                contract.original_format = serializer.validated_data['original_format']
            
            # Re-normalize contract
            hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = normalize_contract(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                spec_type=contract.original_spec_type
            )
            
            # Validate HubContract schema if normalization succeeded
            if hub_contract:
                is_valid, validation_errors = validate_hubcontract_schema(hub_contract)
                if not is_valid:
                    norm_status = NormalizationStatus.NORMALIZATION_FAILED
                    norm_errors.extend(validation_errors)
                    hub_contract = None
            
            # Update normalization fields
            contract.hub_contract_version = "1.0.0" if hub_contract else None
            contract.hub_contract_json = hub_contract
            contract.normalization_status = norm_status
            contract.normalization_errors = norm_errors
            contract.normalization_warnings = norm_warnings
            
            # Reset validation status (requires re-validation)
            contract.validation_status = None
            contract.validation_errors = []
            contract.validation_warnings = []
            contract.last_validated_at = None
        
        # Update status if provided
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            
            # Enforce ACTIVE status requirements
            if new_status == ContractStatus.ACTIVE:
                can_activate, reason = contract.can_activate()
                if not can_activate:
                    return Response(
                        {'error': f'Cannot activate contract: {reason}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            contract.status = new_status
        
        # Apply ON_WRITE migration if needed
        if contract.hub_contract_json and contract.hub_contract_version:
            migrated, migrated_hub_contract, migration_warnings = ContractMigrationManager.migrate_on_write(contract)
            if migrated:
                # Contract was migrated, refresh from DB
                contract.refresh_from_db()
        
        # Validate contract before saving
        try:
            contract.full_clean()
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contract.save()
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_UPDATED",
            actor_user=request.user,
            tenant=contract.tenant,
            resource_id=str(contract.id),
            details={
                'old_status': old_status,
                'new_status': contract.status,
                'normalization_status': contract.normalization_status,
                'old_hub_contract_json': old_hub_contract_json,
                'new_hub_contract_json': contract.hub_contract_json
            },
            request=request
        )
        
        return Response(
            ContractSerializer(contract).data,
            status=status.HTTP_200_OK
        )
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete a contract (soft delete: set status to RETIRED).
        
        DELETE /contracts/{id}
        """
        contract = self.get_object()
        
        # Soft delete: set status to RETIRED
        contract.status = ContractStatus.RETIRED
        contract.save()
        
        # Log audit event
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_DELETED",
            actor_user=request.user,
            tenant=contract.tenant,
            resource_id=str(contract.id),
            details={
                'original_spec_type': contract.original_spec_type,
                'original_spec_version': contract.original_spec_version
            },
            request=request
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def list(self, request, *args, **kwargs):
        """List contracts (tenant-scoped)"""
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve contract by ID.
        
        Applies ON_READ migration (lazy migration) if needed.
        """
        contract = self.get_object()
        
        # Apply ON_READ migration (lazy, in-memory)
        if contract.hub_contract_json and contract.hub_contract_version:
            migrated_hub_contract, migration_warnings = ContractMigrationManager.migrate_on_read(contract)
            
            # If migration was applied, return migrated version in response
            # (but don't update DB - that's the lazy part)
            if migrated_hub_contract != contract.hub_contract_json:
                # Create a temporary serializer with migrated contract
                serializer = self.get_serializer(contract)
                response_data = serializer.data
                # Override hub_contract_json with migrated version
                response_data['hub_contract_json'] = migrated_hub_contract
                if migration_warnings:
                    response_data['migration_warnings'] = migration_warnings
                return Response(response_data)
        
        return super().retrieve(request, *args, **kwargs)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='validate')
    def validate_contract(self, request, id=None):
        """
        Validate a contract using DataContract CLI.
        
        POST /contracts/{id}/validate
        Body: {
            "async": false (optional, default false for sync validation)
        }
        
        Returns validation result with status, errors, warnings.
        """
        contract = self.get_object()
        
        use_async = request.data.get('async', False)
        contract_size = len(contract.original_raw.encode('utf-8'))
        
        # Determine if async is needed based on size
        from django.conf import settings
        sync_size_limit = getattr(settings, 'DATACONTRACT_VALIDATION_SYNC_SIZE_LIMIT', 100 * 1024)
        
        if contract_size > sync_size_limit:
            use_async = True
        
        if use_async:
            # Create async validation job
            job = create_job(
                job_type=JobType.CONTRACT_VALIDATION,
                resource_type="CONTRACT",
                resource_id=str(contract.id),
                tenant=contract.tenant,
                created_by=request.user,
                details_json={
                    'contract_id': str(contract.id),
                    'validation_type': 'async'
                },
                queue_name='default'
            )
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_VALIDATION_STARTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={
                    'job_id': str(job.id),
                    'validation_type': 'async'
                },
                request=request
            )
            
            return Response(
                {
                    'job_id': str(job.id),
                    'status': 'pending',
                    'message': 'Validation job created. Poll /jobs/{job_id} for status.'
                },
                status=status.HTTP_202_ACCEPTED
            )
        else:
            # Synchronous validation
            try:
                cli_client = DataContractCLIClient()
                
                # Validate contract
                validation_result = cli_client.validate(
                    raw_contract=contract.original_raw,
                    format=contract.original_format,
                    tenant_id=str(contract.tenant.id) if contract.tenant else None,
                    use_cache=True,
                    timeout=SYNC_TIMEOUT
                )
                
                # Interpret validation status
                validation_status, errors, warnings = interpret_validation_status(validation_result)
                
                # Group errors by category
                grouped_errors = group_errors_by_category(errors)
                
                # Update contract with validation results
                contract.validation_status = validation_status
                contract.validation_errors = errors
                contract.validation_warnings = warnings
                contract.cli_version = validation_result.get('cli_version', 'unknown')
                contract.last_validated_at = timezone.now()
                contract.save(update_fields=[
                    'validation_status',
                    'validation_errors',
                    'validation_warnings',
                    'cli_version',
                    'last_validated_at',
                    'updated_at'
                ])
                
                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_COMPLETED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={
                        'validation_status': validation_status,
                        'error_count': len(errors),
                        'warning_count': len(warnings),
                        'cli_version': contract.cli_version
                    },
                    request=request
                )
                
                return Response(
                    {
                        'validation_status': validation_status,
                        'errors': errors,
                        'warnings': warnings,
                        'grouped_errors': grouped_errors,
                        'cli_version': contract.cli_version,
                        'validated_at': contract.last_validated_at.isoformat()
                    },
                    status=status.HTTP_200_OK
                )
            
            except Exception as e:
                # Mark validation as ERROR
                contract.validation_status = ValidationStatus.ERROR
                contract.validation_errors = [{'message': str(e), 'severity': 'ERROR'}]
                contract.last_validated_at = timezone.now()
                contract.save(update_fields=[
                    'validation_status',
                    'validation_errors',
                    'last_validated_at',
                    'updated_at'
                ])
                
                # Log audit event
                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_VALIDATION_FAILED",
                    actor_user=request.user,
                    tenant=contract.tenant,
                    resource_id=str(contract.id),
                    details={'error': str(e)},
                    request=request
                )
                
                return Response(
                    {'error': f'Validation failed: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    
    @action(detail=True, methods=['post'], url_path='lint')
    def lint_contract(self, request, id=None):
        """
        Lint a contract using DataContract CLI.
        
        POST /contracts/{id}/lint
        
        Returns linting result with issues.
        """
        contract = self.get_object()
        
        try:
            cli_client = DataContractCLIClient()
            
            # Lint contract
            lint_result = cli_client.lint(
                raw_contract=contract.original_raw,
                format=contract.original_format,
                timeout=SYNC_TIMEOUT
            )
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_LINTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={'issues_count': len(lint_result.get('issues', []))},
                request=request
            )
            
            return Response(
                {
                    'issues': lint_result.get('issues', []),
                    'cli_version': lint_result.get('cli_version', 'unknown')
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': f'Linting failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='convert')
    def convert_contract(self, request, id=None):
        """
        Convert a contract between formats.
        
        POST /contracts/{id}/convert
        Body: {
            "target_format": "JSON" or "YAML"
        }
        
        Returns converted contract.
        """
        contract = self.get_object()
        target_format = request.data.get('target_format', 'JSON')
        
        if target_format not in ['JSON', 'YAML']:
            return Response(
                {'error': 'target_format must be JSON or YAML'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cli_client = DataContractCLIClient()
            
            # Convert contract
            convert_result = cli_client.convert(
                raw_contract=contract.original_raw,
                source_format=contract.original_format,
                target_format=target_format,
                timeout=SYNC_TIMEOUT
            )
            
            # Log audit event
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_CONVERTED",
                actor_user=request.user,
                tenant=contract.tenant,
                resource_id=str(contract.id),
                details={
                    'source_format': contract.original_format,
                    'target_format': target_format
                },
                request=request
            )
            
            return Response(
                {
                    'converted_contract': convert_result.get('converted_contract', ''),
                    'target_format': convert_result.get('target_format', target_format),
                    'format': target_format,  # Keep for backward compatibility
                    'cli_version': convert_result.get('cli_version', 'unknown')
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': f'Conversion failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'], url_path='migrate')
    def migrate_contract(self, request, id=None):
        """
        Migrate contract to a new HubContract version.
        
        POST /contracts/{id}/migrate
        Body: {
            "target_hub_contract_version": "2.0.0" (optional, defaults to current),
            "migration_strategy": "ON_WRITE" | "ON_READ" | "BACKGROUND" (optional, default: "ON_WRITE")
        }
        
        Returns migration result or job ID for BACKGROUND strategy.
        """
        contract = self.get_object()
        
        target_version = request.data.get('target_hub_contract_version')
        if not target_version:
            target_version = get_current_hubcontract_version()
        
        strategy = request.data.get('migration_strategy', MigrationStrategy.ON_WRITE)
        
        if strategy not in [MigrationStrategy.ON_WRITE, MigrationStrategy.ON_READ, MigrationStrategy.BACKGROUND]:
            return Response(
                {'error': f'Invalid migration_strategy: {strategy}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if migration is needed
        if not contract.hub_contract_json or not contract.hub_contract_version:
            return Response(
                {'error': 'Contract is not normalized. Cannot migrate.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if contract.hub_contract_version == target_version:
            return Response(
                {
                    'contract': ContractSerializer(contract).data,
                    'migration_applied': False,
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'message': 'Contract is already at target version'
                    }
                },
                status=status.HTTP_200_OK
            )
        
        # Execute migration based on strategy
        if strategy == MigrationStrategy.ON_WRITE:
            migrated, migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_write(contract)
            
            if not migrated:
                # Migration not needed (already at target version) or failed
                # Check if it's because migration isn't needed
                from .migration import needs_migration
                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            'contract': ContractSerializer(contract).data,
                            'migration_applied': False,
                            'migration_details': {
                                'source_version': contract.hub_contract_version,
                                'target_version': target_version,
                                'message': 'Contract is already at target version'
                            }
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    # Migration failed
                    return Response(
                        {'error': 'Migration failed or not supported'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Refresh contract from DB
            contract.refresh_from_db()
            
            return Response(
                {
                    'contract': ContractSerializer(contract).data,
                    'migration_applied': True,
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'migration_strategy': strategy,
                        'warnings': warnings
                    }
                },
                status=status.HTTP_200_OK
            )
        
        elif strategy == MigrationStrategy.ON_READ:
            migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_read(contract)
            
            # Return migrated version (in-memory, not persisted)
            serializer = ContractSerializer(contract)
            response_data = serializer.data
            response_data['hub_contract_json'] = migrated_hub_contract
            
            return Response(
                {
                    'contract': response_data,
                    'migration_applied': True,
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'migration_strategy': strategy,
                        'warnings': warnings,
                        'note': 'Migration applied in-memory only (lazy migration)'
                    }
                },
                status=status.HTTP_200_OK
            )
        
        elif strategy == MigrationStrategy.BACKGROUND:
            job = ContractMigrationManager.migrate_background(contract, user=request.user)
            
            if not job:
                # Check if migration isn't needed (already at target version)
                from .migration import needs_migration
                if not needs_migration(contract.hub_contract_version):
                    # Already at target version - return success
                    return Response(
                        {
                            'contract': ContractSerializer(contract).data,
                            'migration_applied': False,
                            'migration_details': {
                                'source_version': contract.hub_contract_version,
                                'target_version': target_version,
                                'message': 'Contract is already at target version'
                            }
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    # Migration failed
                    return Response(
                        {'error': 'Migration failed or not needed'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response(
                {
                    'job': {
                        'id': str(job.id),
                        'type': job.type,
                        'status': job.status,
                        'resource_type': job.resource_type,
                        'resource_id': str(job.resource_id)
                    },
                    'migration_details': {
                        'source_version': contract.hub_contract_version,
                        'target_version': target_version,
                        'migration_strategy': strategy
                    }
                },
                status=status.HTTP_202_ACCEPTED
            )

