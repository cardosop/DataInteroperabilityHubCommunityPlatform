"""
Retention Policy Enforcement

Handles time-based and event-based retention policies with legal hold support.
"""
from typing import List, Optional, Dict, Any
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from .models import (
    RetentionPolicy,
    RetentionPolicyType,
    RetentionAction
)
from hub.apps.files.storage import S3StorageClient


class RetentionPolicyEnforcer:
    """
    Enforces retention policies for assets, datasets, and files.
    
    Supports:
    - Time-based retention (days since creation)
    - Event-based retention (triggered by events)
    - Legal hold (prevents deletion)
    - Soft delete (grace period)
    - Hard delete (permanent removal)
    - Archive (cold storage)
    """
    
    @staticmethod
    def get_policies_to_enforce(
        tenant_id: Optional[str] = None
    ) -> List[RetentionPolicy]:
        """
        Get all enabled retention policies that need enforcement.
        
        Args:
            tenant_id: Optional tenant ID to filter by
        
        Returns:
            List of RetentionPolicy instances
        """
        queryset = RetentionPolicy.objects.filter(enabled=True)
        
        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Filter out policies under legal hold
        from django.db.models import Q
        now = timezone.now()
        queryset = queryset.filter(
            Q(legal_hold=False) |
            Q(legal_hold=True, legal_hold_expires_at__lte=now)
        )
        
        return list(queryset)
    
    @staticmethod
    def enforce_time_based_policy(
        policy: RetentionPolicy
    ) -> Dict[str, Any]:
        """
        Enforce a time-based retention policy.
        
        Args:
            policy: RetentionPolicy instance
        
        Returns:
            Dictionary with enforcement results
        """
        from django.db import models
        
        result = {
            'policy_id': str(policy.id),
            'policy_name': policy.name,
            'action': None,
            'resource_type': None,
            'resource_id': None,
            'success': False,
            'error': None
        }
        
        # Get resource
        resource = policy.asset or policy.dataset or policy.file
        if not resource:
            result['error'] = "No resource found for policy"
            return result
        
        result['resource_type'] = resource.__class__.__name__
        result['resource_id'] = str(resource.id)
        
        # Check if retention period has expired
        retention_date = resource.created_at + timedelta(days=policy.retention_period_days)
        
        if timezone.now() < retention_date:
            # Not yet expired
            result['action'] = 'NO_ACTION'
            result['success'] = True
            return result
        
        # Check grace period for soft delete
        if policy.action == RetentionAction.SOFT_DELETE:
            grace_date = retention_date + timedelta(days=policy.grace_period_days)
            if timezone.now() < grace_date:
                # Still in grace period
                result['action'] = 'GRACE_PERIOD'
                result['success'] = True
                return result
        
        # Enforce action
        try:
            if policy.action == RetentionAction.SOFT_DELETE:
                RetentionPolicyEnforcer._soft_delete_resource(resource)
                result['action'] = 'SOFT_DELETE'
            elif policy.action == RetentionAction.HARD_DELETE:
                RetentionPolicyEnforcer._hard_delete_resource(resource)
                result['action'] = 'HARD_DELETE'
            elif policy.action == RetentionAction.ARCHIVE:
                RetentionPolicyEnforcer._archive_resource(resource)
                result['action'] = 'ARCHIVE'
            
            # Update policy
            policy.last_enforced_at = timezone.now()
            policy.save()
            
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    def enforce_event_based_policy(
        policy: RetentionPolicy,
        event_occurred: bool = False
    ) -> Dict[str, Any]:
        """
        Enforce an event-based retention policy.
        
        Args:
            policy: RetentionPolicy instance
            event_occurred: Whether the trigger event has occurred
        
        Returns:
            Dictionary with enforcement results
        """
        result = {
            'policy_id': str(policy.id),
            'policy_name': policy.name,
            'action': None,
            'resource_type': None,
            'resource_id': None,
            'success': False,
            'error': None
        }
        
        if not event_occurred:
            result['action'] = 'NO_ACTION'
            result['success'] = True
            return result
        
        # Get resource
        resource = policy.asset or policy.dataset or policy.file
        if not resource:
            result['error'] = "No resource found for policy"
            return result
        
        result['resource_type'] = resource.__class__.__name__
        result['resource_id'] = str(resource.id)
        
        # Enforce action
        try:
            if policy.action == RetentionAction.SOFT_DELETE:
                RetentionPolicyEnforcer._soft_delete_resource(resource)
                result['action'] = 'SOFT_DELETE'
            elif policy.action == RetentionAction.HARD_DELETE:
                RetentionPolicyEnforcer._hard_delete_resource(resource)
                result['action'] = 'HARD_DELETE'
            elif policy.action == RetentionAction.ARCHIVE:
                RetentionPolicyEnforcer._archive_resource(resource)
                result['action'] = 'ARCHIVE'
            
            # Update policy
            policy.last_enforced_at = timezone.now()
            policy.save()
            
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    def _soft_delete_resource(resource):
        """Soft delete a resource (mark as deleted but keep data)"""
        if hasattr(resource, 'deleted_at'):
            resource.deleted_at = timezone.now()
            resource.save()
        elif hasattr(resource, 'status'):
            # Mark as deleted/inactive
            resource.status = 'DELETED'
            resource.save()
    
    @staticmethod
    def _hard_delete_resource(resource):
        """Hard delete a resource (permanent removal)"""
        # Delete associated files from storage
        if hasattr(resource, 'file'):
            file_obj = resource.file
            if file_obj:
                try:
                    storage_client = S3StorageClient()
                    storage_client.delete_file(file_obj.storage_path)
                except Exception:
                    pass  # Continue even if storage deletion fails
        
        # Delete the resource
        resource.delete()
    
    @staticmethod
    def _archive_resource(resource):
        """Archive a resource (move to cold storage)"""
        # Mark as archived
        if hasattr(resource, 'archived_at'):
            resource.archived_at = timezone.now()
            resource.save()
        elif hasattr(resource, 'status'):
            resource.status = 'ARCHIVED'
            resource.save()
        
        # Move file to cold storage (if applicable)
        if hasattr(resource, 'file'):
            file_obj = resource.file
            if file_obj:
                try:
                    storage_client = S3StorageClient()
                    # Move to archive storage class
                    storage_client.archive_file(file_obj.storage_path)
                except Exception:
                    pass  # Continue even if archive fails
    
    @staticmethod
    @transaction.atomic
    def enforce_all_policies(
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enforce all applicable retention policies.
        
        Args:
            tenant_id: Optional tenant ID to filter by
        
        Returns:
            Dictionary with enforcement summary
        """
        policies = RetentionPolicyEnforcer.get_policies_to_enforce(tenant_id)
        
        results = {
            'total_policies': len(policies),
            'enforced': 0,
            'failed': 0,
            'no_action': 0,
            'details': []
        }
        
        for policy in policies:
            if policy.policy_type == RetentionPolicyType.TIME_BASED:
                result = RetentionPolicyEnforcer.enforce_time_based_policy(policy)
            elif policy.policy_type == RetentionPolicyType.EVENT_BASED:
                # Event-based policies require external trigger
                # For now, skip (would be triggered by events)
                result = {
                    'policy_id': str(policy.id),
                    'action': 'NO_ACTION',
                    'success': True,
                    'error': 'Event-based policies require external triggers'
                }
            else:
                result = {
                    'policy_id': str(policy.id),
                    'action': 'NO_ACTION',
                    'success': False,
                    'error': 'Unknown policy type'
                }
            
            results['details'].append(result)
            
            if result['success']:
                if result['action'] in ['SOFT_DELETE', 'HARD_DELETE', 'ARCHIVE']:
                    results['enforced'] += 1
                else:
                    results['no_action'] += 1
            else:
                results['failed'] += 1
        
        return results

