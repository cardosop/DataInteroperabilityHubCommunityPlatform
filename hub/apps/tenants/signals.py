"""
Tenant Signals

Handles post-creation tasks like default role creation.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Tenant


@receiver(post_save, sender=Tenant)
def create_default_roles(sender, instance, created, **kwargs):
    """
    Create default roles when a new tenant is created.
    
    Default roles:
    - TENANT_ADMIN: Full administrative access within tenant
    - DATA_PROVIDER: Can create and manage data assets
    - DATA_CONSUMER: Can request and access data assets
    - AUDITOR: Read-only access to compliance/DQ reports and audit logs
    """
    if created:
        # Import here to avoid circular imports
        # This will be implemented when users app is ready
        try:
            from hub.apps.users.models import Role
            
            default_roles = [
                {
                    "name": "TENANT_ADMIN",
                    "description": "Full administrative access within tenant"
                },
                {
                    "name": "DATA_PROVIDER",
                    "description": "Can create and manage data assets"
                },
                {
                    "name": "DATA_CONSUMER",
                    "description": "Can request and access data assets"
                },
                {
                    "name": "AUDITOR",
                    "description": "Read-only access to compliance/DQ reports and audit logs"
                }
            ]
            
            # Create roles in a transaction
            for role_data in default_roles:
                Role.objects.create(
                    tenant=instance,
                    name=role_data["name"],
                    description=role_data["description"]
                )
        except ImportError:
            # Role model doesn't exist yet, skip role creation
            # This will be handled when users app is implemented
            pass

