"""
Audit Logging Utilities

Helper functions for creating audit events with PII redaction.
"""
import re
import hashlib
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from .models import AuditEvent

User = get_user_model()


def redact_pii(data: Dict[str, Any], visited: Optional[set] = None) -> Dict[str, Any]:
    """
    Redact PII from a dictionary recursively.
    
    Redacts:
    - Email addresses
    - Phone numbers
    - Credit card numbers
    - SSN
    - Passwords
    
    Args:
        data: Dictionary to redact
        visited: Set of object IDs already visited (for cycle detection)
    
    Returns:
        New dictionary with PII redacted.
    """
    if not isinstance(data, dict):
        return data
    
    # Initialize visited set for cycle detection
    if visited is None:
        visited = set()
    
    # Check for circular reference
    data_id = id(data)
    if data_id in visited:
        return '[CIRCULAR_REFERENCE]'
    visited.add(data_id)
    
    try:
        redacted = {}
        
        # Patterns for PII detection
        email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        phone_pattern = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\+?\d{10,15}\b')
        card_pattern = re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b')
        ssn_pattern = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
        
        # Fields that should always be redacted
        pii_fields = ['password', 'password_hash', 'api_key', 'token', 'secret', 'ssn', 'social_security_number']
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Always redact known PII fields
            if any(pii_field in key_lower for pii_field in pii_fields):
                redacted[key] = '[REDACTED]'
                continue
            
            # Handle different value types
            if isinstance(value, dict):
                # Recursively process nested dictionaries with cycle detection
                redacted[key] = redact_pii(value, visited)
            elif isinstance(value, list):
                # Process list items
                redacted_list = []
                for item in value:
                    if isinstance(item, dict):
                        redacted_list.append(redact_pii(item, visited))
                    else:
                        # Convert non-dict items to string safely
                        try:
                            redacted_list.append(redact_string(str(item)))
                        except (RecursionError, ValueError, TypeError):
                            redacted_list.append('[COMPLEX_OBJECT]')
                redacted[key] = redacted_list
            elif isinstance(value, str):
                redacted[key] = redact_string(value)
            else:
                # For complex objects (models, etc.), convert to string representation
                # but avoid recursion by not processing their internal structure
                try:
                    # Try to get a simple string representation
                    if hasattr(value, '__dict__'):
                        # For objects with __dict__, just use the type name
                        redacted[key] = f'[{type(value).__name__}]'
                    else:
                        redacted[key] = str(value)
                except (RecursionError, ValueError, TypeError):
                    redacted[key] = '[COMPLEX_OBJECT]'
        
        return redacted
    finally:
        # Remove from visited set when done processing this level
        visited.discard(data_id)


def redact_string(value: str) -> str:
    """
    Redact PII from a string.
    
    Returns redacted string with PII replaced by [REDACTED] or hashed values.
    """
    if not isinstance(value, str):
        return value
    
    # Email addresses
    value = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        lambda m: f"{m.group(0).split('@')[0][:2]}***@{m.group(0).split('@')[1]}",
        value
    )
    
    # Phone numbers (match various formats: 555-123-4567, 555.123.4567, 5551234567, +15551234567)
    value = re.sub(
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\+?\d{10,15}\b',
        '[REDACTED_PHONE]',
        value
    )
    
    # Credit card numbers
    value = re.sub(
        r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
        '[REDACTED_CARD]',
        value
    )
    
    # SSN
    value = re.sub(
        r'\b\d{3}-\d{2}-\d{4}\b',
        '[REDACTED_SSN]',
        value
    )
    
    return value


def create_audit_event(
    resource_type: str,
    action: str,
    actor_user: Optional[User] = None,
    tenant=None,
    resource_id: Optional[str] = None,
    result: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    request: Optional[HttpRequest] = None
) -> AuditEvent:
    """
    Create an audit event with automatic PII redaction.
    
    Args:
        resource_type: Type of resource (e.g., "TENANT", "USER", "CONTRACT", "AUTH")
        action: Action performed (e.g., "CREATED", "UPDATED", "DELETED", "LOGIN")
        actor_user: User who performed the action (optional)
        tenant: Tenant this event belongs to (optional, inferred from actor_user if not provided)
        resource_id: ID of the resource (optional)
        result: Result of the action ("SUCCESS", "FAILURE", "WARNING")
        details: Additional details as dictionary (will be redacted)
        request: HTTP request object (optional, for extracting IP address, user agent)
    
    Returns:
        Created AuditEvent instance
    """
    # Infer tenant from actor_user if not provided
    if tenant is None and actor_user and hasattr(actor_user, 'tenant'):
        tenant = actor_user.tenant
    
    # Prepare details with request metadata
    details_dict = details.copy() if details else {}
    
    if request:
        # Extract IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        if ip_address:
            details_dict['ip_address'] = ip_address
        
        # Extract user agent
        user_agent = request.META.get('HTTP_USER_AGENT')
        if user_agent:
            details_dict['user_agent'] = user_agent
        
        # Extract request ID if available
        request_id = getattr(request, 'request_id', None)
        if request_id:
            details_dict['request_id'] = str(request_id)
    
    # Redact PII from details
    redacted_details = redact_pii(details_dict)
    
    # Create audit event
    audit_event = AuditEvent.objects.create(
        tenant=tenant,
        actor_user=actor_user,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        result=result,
        details_json=redacted_details
    )
    
    return audit_event


def log_tenant_operation(
    action: str,
    tenant,
    actor_user: User,
    resource_id: Optional[str] = None,
    result: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    request: Optional[HttpRequest] = None
) -> AuditEvent:
    """Convenience function for logging tenant operations"""
    return create_audit_event(
        resource_type="TENANT",
        action=action,
        actor_user=actor_user,
        tenant=tenant,
        resource_id=resource_id or str(tenant.id) if tenant else None,
        result=result,
        details=details,
        request=request
    )


def log_user_operation(
    action: str,
    user: User,
    actor_user: User,
    result: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    request: Optional[HttpRequest] = None
) -> AuditEvent:
    """Convenience function for logging user operations"""
    return create_audit_event(
        resource_type="USER",
        action=action,
        actor_user=actor_user,
        tenant=user.tenant if hasattr(user, 'tenant') else None,
        resource_id=str(user.id),
        result=result,
        details=details,
        request=request
    )


def log_auth_operation(
    action: str,
    user: User,
    result: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    request: Optional[HttpRequest] = None
) -> AuditEvent:
    """Convenience function for logging authentication operations"""
    return create_audit_event(
        resource_type="AUTH",
        action=action,
        actor_user=user,
        tenant=user.tenant if hasattr(user, 'tenant') else None,
        resource_id=str(user.id),
        result=result,
        details=details,
        request=request
    )

