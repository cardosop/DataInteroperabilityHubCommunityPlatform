"""
Webhook Serializers

Serializers for webhook models.
"""
from rest_framework import serializers
from .models import Webhook, WebhookDelivery, WebhookEventType


class WebhookSerializer(serializers.ModelSerializer):
    """Serializer for Webhook model"""
    
    class Meta:
        model = Webhook
        fields = [
            'id',
            'name',
            'url',
            'event_types',
            'status',
            'max_retries',
            'retry_intervals',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_event_types(self, value):
        """Validate event types"""
        if not value:
            raise serializers.ValidationError("At least one event type must be specified")
        
        valid_event_types = [choice[0] for choice in WebhookEventType.choices]
        for event_type in value:
            if event_type not in valid_event_types:
                raise serializers.ValidationError(f"Invalid event type: {event_type}")
        
        return value
    
    def validate_retry_intervals(self, value):
        """Validate retry intervals"""
        if not value:
            return [1, 5, 30, 300, 1800]  # Default
        
        if not isinstance(value, list):
            raise serializers.ValidationError("retry_intervals must be a list")
        
        if not all(isinstance(x, int) and x > 0 for x in value):
            raise serializers.ValidationError("All retry intervals must be positive integers")
        
        return value


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Serializer for WebhookDelivery model"""
    
    webhook_name = serializers.CharField(source='webhook.name', read_only=True)
    webhook_url = serializers.URLField(source='webhook.url', read_only=True)
    
    class Meta:
        model = WebhookDelivery
        fields = [
            'id',
            'webhook',
            'webhook_name',
            'webhook_url',
            'event_type',
            'payload',
            'signature',
            'status',
            'attempt_number',
            'http_status_code',
            'response_body',
            'error_message',
            'delivered_at',
            'next_retry_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'signature',
            'status',
            'attempt_number',
            'http_status_code',
            'response_body',
            'error_message',
            'delivered_at',
            'next_retry_at',
            'created_at',
            'updated_at'
        ]

