"""
DQ Alerting

Configurable alerting rules for data quality metrics with threshold-based alerts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import structlog

from .models import DQRun, DQAlertingRule, DQAnomalySeverity, DQAlertChannel
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset

logger = structlog.get_logger(__name__)


class DQAlertingService:
    """
    Service for evaluating and triggering DQ alerting rules.
    """
    
    @staticmethod
    def evaluate_rules(
        dq_run: DQRun,
        metric_type: str = "quality_score"
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all applicable alerting rules for a DQ run.
        
        Args:
            dq_run: DQ run to evaluate
            metric_type: Type of metric to evaluate
        
        Returns:
            List of triggered alerts
        """
        triggered_alerts = []
        
        # Get metric value
        metric_value = DQAlertingService._get_metric_value(dq_run, metric_type)
        if metric_value is None:
            return triggered_alerts
        
        # Get applicable rules
        rules = DQAlertingService._get_applicable_rules(
            dq_run,
            metric_type
        )
        
        # Evaluate each rule
        for rule in rules:
            if rule.evaluate(metric_value):
                alert = DQAlertingService._create_alert(
                    rule,
                    dq_run,
                    metric_type,
                    metric_value
                )
                triggered_alerts.append(alert)
                
                # Trigger alert delivery
                DQAlertingService._deliver_alert(alert, rule)
        
        return triggered_alerts
    
    @staticmethod
    def _get_metric_value(dq_run: DQRun, metric_type: str) -> Optional[float]:
        """Get metric value from DQ run"""
        if metric_type == "quality_score":
            return dq_run.quality_score
        
        # Extract from details_json
        if dq_run.details_json and isinstance(dq_run.details_json, dict):
            return dq_run.details_json.get(metric_type)
        
        return None
    
    @staticmethod
    def _get_applicable_rules(
        dq_run: DQRun,
        metric_type: str
    ) -> List[DQAlertingRule]:
        """Get applicable alerting rules"""
        # Get asset-specific and global rules
        rules_query = DQAlertingRule.objects.filter(
            tenant=dq_run.tenant,
            enabled=True,
            metric_type=metric_type
        )
        
        # Asset-specific rules
        if dq_run.asset:
            asset_rules = rules_query.filter(asset=dq_run.asset)
        else:
            asset_rules = DQAlertingRule.objects.none()
        
        # Global rules (no asset specified)
        global_rules = rules_query.filter(asset__isnull=True)
        
        # Combine and return
        return list(asset_rules) + list(global_rules)
    
    @staticmethod
    def _create_alert(
        rule: DQAlertingRule,
        dq_run: DQRun,
        metric_type: str,
        metric_value: float
    ) -> Dict[str, Any]:
        """Create alert dictionary"""
        return {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "severity": rule.severity,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "threshold": rule.threshold,
            "comparison_operator": rule.comparison_operator,
            "dq_run_id": str(dq_run.id),
            "asset_id": str(dq_run.asset.id) if dq_run.asset else None,
            "dataset_id": str(dq_run.dataset.id) if dq_run.dataset else None,
            "triggered_at": timezone.now().isoformat(),
            "message": f"{rule.name}: {metric_type} {rule.comparison_operator} {rule.threshold} (actual: {metric_value})"
        }
    
    @staticmethod
    def _deliver_alert(
        alert: Dict[str, Any],
        rule: DQAlertingRule
    ):
        """Deliver alert through configured channels"""
        for channel in rule.alert_channels:
            try:
                if channel == DQAlertChannel.EMAIL:
                    DQAlertingService._send_email_alert(alert, rule)
                elif channel == DQAlertChannel.SLACK:
                    DQAlertingService._send_slack_alert(alert, rule)
                elif channel == DQAlertChannel.WEBHOOK:
                    DQAlertingService._send_webhook_alert(alert, rule)
                elif channel == DQAlertChannel.PAGERDUTY:
                    DQAlertingService._send_pagerduty_alert(alert, rule)
            except Exception as e:
                logger.error(
                    "Failed to deliver alert",
                    channel=channel,
                    rule_id=str(rule.id),
                    error=str(e),
                    exc_info=True
                )
    
    @staticmethod
    def _send_email_alert(alert: Dict[str, Any], rule: DQAlertingRule):
        """Send email alert"""
        # In production, integrate with email service
        # For now, just log
        emails = rule.channel_config.get("emails", [])
        if emails:
            logger.info(
                "Email alert would be sent",
                emails=emails,
                alert=alert
            )
            # TODO: Integrate with email service
            # send_email(emails, subject, body)
    
    @staticmethod
    def _send_slack_alert(alert: Dict[str, Any], rule: DQAlertingRule):
        """Send Slack alert"""
        # In production, integrate with Slack API
        # For now, just log
        webhook_url = rule.channel_config.get("webhook_url")
        if webhook_url:
            logger.info(
                "Slack alert would be sent",
                webhook_url=webhook_url,
                alert=alert
            )
            # TODO: Integrate with Slack API
            # send_slack_message(webhook_url, message)
    
    @staticmethod
    def _send_webhook_alert(alert: Dict[str, Any], rule: DQAlertingRule):
        """Send webhook alert"""
        # In production, make HTTP POST to webhook URL
        # For now, just log
        webhook_url = rule.channel_config.get("url")
        if webhook_url:
            logger.info(
                "Webhook alert would be sent",
                webhook_url=webhook_url,
                alert=alert
            )
            # TODO: Make HTTP POST request
            # requests.post(webhook_url, json=alert)
    
    @staticmethod
    def _send_pagerduty_alert(alert: Dict[str, Any], rule: DQAlertingRule):
        """Send PagerDuty alert"""
        # In production, integrate with PagerDuty API
        # For now, just log
        integration_key = rule.channel_config.get("integration_key")
        if integration_key:
            logger.info(
                "PagerDuty alert would be sent",
                integration_key=integration_key,
                alert=alert
            )
            # TODO: Integrate with PagerDuty API
            # send_pagerduty_event(integration_key, alert)
    
    @staticmethod
    def get_alert_history(
        tenant_id: str,
        asset_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get alert history (stored alerts would be in a separate table in production).
        
        Args:
            tenant_id: Tenant UUID
            asset_id: Optional asset UUID
            rule_id: Optional rule UUID
            days: Number of days to look back
        
        Returns:
            List of alert history entries
        """
        # In production, this would query a DQAlertHistory model
        # For now, return empty list
        return []

