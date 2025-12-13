"""
Webhook Service

Service for webhook delivery with retry logic and authentication.
"""
from __future__ import annotations

import json
import hmac
import hashlib
import requests
from typing import Any, Dict, Optional
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import structlog

from .models import Webhook, WebhookDelivery, WebhookStatus, DeliveryStatus, WebhookEventType

logger = structlog.get_logger(__name__)


class WebhookDeliveryService:
    """
    Service for delivering webhooks with retry logic.
    """
    
    DEFAULT_RETRY_INTERVALS = [1, 5, 30, 300, 1800]  # 1s, 5s, 30s, 5m, 30m
    REQUEST_TIMEOUT = 30  # seconds
    
    @staticmethod
    def trigger_webhook(
        tenant_id: str,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any]
    ) -> int:
        """
        Trigger webhook delivery for matching subscriptions.
        
        Args:
            tenant_id: Tenant UUID
            event_type: Event type (e.g., "contract.created")
            resource_type: Resource type (e.g., "CONTRACT", "ASSET")
            resource_id: Resource UUID
            event_data: Event data payload
        
        Returns:
            Number of webhooks triggered
        """
        # Find active webhooks for this event type
        webhooks = Webhook.objects.filter(
            tenant_id=tenant_id,
            status=WebhookStatus.ACTIVE,
            event_types__contains=[event_type]
        )
        
        count = 0
        for webhook in webhooks:
            WebhookDeliveryService._deliver_webhook(
                webhook,
                event_type,
                resource_type,
                resource_id,
                event_data
            )
            count += 1
        
        logger.info(
            "webhooks_triggered",
            tenant_id=tenant_id,
            event_type=event_type,
            count=count
        )
        
        return count
    
    @staticmethod
    def _deliver_webhook(
        webhook: Webhook,
        event_type: str,
        resource_type: str,
        resource_id: str,
        event_data: Dict[str, Any]
    ):
        """Create and deliver a webhook"""
        # Build payload
        payload = {
            "event_type": event_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timezone.now().isoformat(),
            "data": event_data
        }
        
        payload_json = json.dumps(payload, sort_keys=True)
        
        # Generate signature
        signature = webhook.generate_signature(payload_json)
        
        # Create delivery record
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=event_type,
            payload=payload,
            signature=signature,
            status=DeliveryStatus.PENDING,
            attempt_number=0
        )
        
        # Schedule delivery (async via job queue in production)
        WebhookDeliveryService._attempt_delivery(delivery)
    
    @staticmethod
    def _attempt_delivery(delivery: WebhookDelivery):
        """Attempt to deliver a webhook"""
        webhook = delivery.webhook
        
        # Check if webhook is still active
        if webhook.status != WebhookStatus.ACTIVE:
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = f"Webhook is {webhook.status}"
            delivery.save()
            return
        
        # Build payload
        payload_json = json.dumps(delivery.payload, sort_keys=True)
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": delivery.signature,
            "X-Webhook-Event-Type": delivery.event_type,
            "User-Agent": "DataInteroperabilityHub/1.0"
        }
        
        try:
            # Make HTTP request
            response = requests.post(
                webhook.url,
                data=payload_json,
                headers=headers,
                timeout=WebhookDeliveryService.REQUEST_TIMEOUT
            )
            
            # Update delivery record
            delivery.http_status_code = response.status_code
            delivery.response_body = response.text[:1000]  # Limit response body size
            
            if 200 <= response.status_code < 300:
                # Success
                delivery.status = DeliveryStatus.SUCCESS
                delivery.delivered_at = timezone.now()
                delivery.next_retry_at = None
                delivery.save()
                
                logger.info(
                    "webhook_delivered",
                    delivery_id=str(delivery.id),
                    webhook_id=str(webhook.id),
                    event_type=delivery.event_type,
                    status_code=response.status_code
                )
            else:
                # Failed - schedule retry
                WebhookDeliveryService._schedule_retry(delivery)
        
        except requests.exceptions.RequestException as e:
            # Network error - schedule retry
            delivery.error_message = str(e)[:500]  # Limit error message size
            delivery.save()
            
            WebhookDeliveryService._schedule_retry(delivery)
            
            logger.warning(
                "webhook_delivery_failed",
                delivery_id=str(delivery.id),
                webhook_id=str(webhook.id),
                error=str(e)
            )
    
    @staticmethod
    def _schedule_retry(delivery: WebhookDelivery):
        """Schedule a retry for failed delivery"""
        webhook = delivery.webhook
        
        # Check if max retries exceeded
        if delivery.attempt_number >= webhook.max_retries:
            delivery.status = DeliveryStatus.DEAD_LETTER
            delivery.next_retry_at = None
            delivery.save()
            
            logger.warning(
                "webhook_dead_letter",
                delivery_id=str(delivery.id),
                webhook_id=str(webhook.id),
                attempts=delivery.attempt_number
            )
            return
        
        # Calculate next retry time
        retry_intervals = webhook.retry_intervals or WebhookDeliveryService.DEFAULT_RETRY_INTERVALS
        attempt_index = min(delivery.attempt_number, len(retry_intervals) - 1)
        retry_interval = retry_intervals[attempt_index]
        
        next_retry_at = timezone.now() + timedelta(seconds=retry_interval)
        
        # Update delivery
        delivery.status = DeliveryStatus.FAILED
        delivery.attempt_number += 1
        delivery.next_retry_at = next_retry_at
        delivery.save()
    
    @staticmethod
    def retry_delivery(delivery_id: str) -> bool:
        """
        Manually retry a failed delivery.
        
        Args:
            delivery_id: Delivery UUID
        
        Returns:
            True if retry was scheduled, False otherwise
        """
        try:
            delivery = WebhookDelivery.objects.get(id=delivery_id)
        except WebhookDelivery.DoesNotExist:
            return False
        
        if delivery.status == DeliveryStatus.SUCCESS:
            return False  # Already succeeded
        
        if delivery.status == DeliveryStatus.DEAD_LETTER:
            # Reset for retry
            delivery.status = DeliveryStatus.PENDING
            delivery.attempt_number = 0
            delivery.next_retry_at = None
            delivery.save()
        
        WebhookDeliveryService._attempt_delivery(delivery)
        return True
    
    @staticmethod
    def process_pending_deliveries(limit: int = 100) -> int:
        """
        Process pending webhook deliveries.
        
        Args:
            limit: Maximum number of deliveries to process
        
        Returns:
            Number of deliveries processed
        """
        now = timezone.now()
        
        # Get pending deliveries ready for retry
        pending_deliveries = WebhookDelivery.objects.filter(
            status__in=[DeliveryStatus.PENDING, DeliveryStatus.FAILED],
            next_retry_at__lte=now
        )[:limit]
        
        count = 0
        for delivery in pending_deliveries:
            WebhookDeliveryService._attempt_delivery(delivery)
            count += 1
        
        return count

