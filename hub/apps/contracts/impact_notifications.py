"""
Impact Notifications

Sends notifications for high-impact changes via email and optional Slack integration.
"""
from typing import Dict, List, Any, Optional
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import structlog

from .impact_analysis import ImpactAnalyzer, ImpactScorer
from .impact_visualization import ImpactVisualizer

logger = structlog.get_logger(__name__)


class ImpactNotifier:
    """
    Sends notifications for high-impact changes.
    """
    
    # Severity thresholds for notifications
    NOTIFY_CRITICAL = True  # Always notify for CRITICAL
    NOTIFY_HIGH = True      # Always notify for HIGH
    NOTIFY_MEDIUM = False   # Optional notification for MEDIUM
    NOTIFY_LOW = False      # Don't notify for LOW
    
    @staticmethod
    def send_impact_notification(
        impact_result: Dict[str, Any],
        recipients: List[str],
        change_description: Optional[str] = None,
        change_type: str = "UPDATE"
    ) -> bool:
        """
        Send email notification for high-impact changes.
        
        Args:
            impact_result: Impact analysis result
            recipients: List of email addresses
            change_description: Description of the change
            change_type: Type of change (CREATE, UPDATE, DELETE)
        
        Returns:
            True if notification sent successfully
        """
        if not recipients:
            return False
        
        summary = impact_result.get("summary", {})
        severity_dist = summary.get("severity_distribution", {})
        
        # Check if notification is needed
        if not ImpactNotifier._should_notify(severity_dist):
            logger.info(
                "Impact notification not needed",
                severity_distribution=severity_dist
            )
            return False
        
        try:
            source = impact_result.get("source", {})
            contract_name = source.get("contract_name", "Unknown")
            
            # Generate subject
            max_severity = ImpactNotifier._get_max_severity(severity_dist)
            subject = f"Impact Analysis Alert: {max_severity} Impact Detected - {contract_name}"
            
            # Generate email body
            context = {
                "impact_result": impact_result,
                "summary": summary,
                "source": source,
                "change_description": change_description,
                "change_type": change_type,
                "max_severity": max_severity,
                "total_affected": impact_result.get("total_affected", 0),
                "severity_distribution": severity_dist
            }
            
            # Try to render HTML template
            try:
                html_message = render_to_string(
                    'contracts/impact_notification_email.html',
                    context
                )
            except Exception:
                html_message = None
            
            # Plain text message
            text_message = f"""
Impact Analysis Alert: {max_severity} Impact Detected

Source Contract: {contract_name}
Contract ID: {source.get('contract_id')}
Model: {source.get('model_name', 'N/A')}
Field: {source.get('field_name', 'N/A')}

Change Type: {change_type}
Change Description: {change_description or 'N/A'}

Impact Summary:
- Total Affected Resources: {impact_result.get('total_affected', 0)}
- Critical: {severity_dist.get('CRITICAL', 0)}
- High: {severity_dist.get('HIGH', 0)}
- Medium: {severity_dist.get('MEDIUM', 0)}
- Low: {severity_dist.get('LOW', 0)}
- Max Impact Score: {summary.get('max_impact_score', 0.0):.2f}
- Average Impact Score: {summary.get('avg_impact_score', 0.0):.2f}

Please review the impact analysis to understand affected resources.

Generated at: {timezone.now()}
"""
            
            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(
                "Impact notification sent",
                recipients=recipients,
                max_severity=max_severity,
                total_affected=impact_result.get("total_affected", 0)
            )
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to send impact notification",
                error=str(e),
                recipients=recipients
            )
            return False
    
    @staticmethod
    def _should_notify(severity_distribution: Dict[str, int]) -> bool:
        """Check if notification should be sent based on severity distribution"""
        if ImpactNotifier.NOTIFY_CRITICAL and severity_distribution.get("CRITICAL", 0) > 0:
            return True
        if ImpactNotifier.NOTIFY_HIGH and severity_distribution.get("HIGH", 0) > 0:
            return True
        if ImpactNotifier.NOTIFY_MEDIUM and severity_distribution.get("MEDIUM", 0) > 0:
            return True
        return False
    
    @staticmethod
    def _get_max_severity(severity_distribution: Dict[str, int]) -> str:
        """Get maximum severity from distribution"""
        if severity_distribution.get("CRITICAL", 0) > 0:
            return "CRITICAL"
        elif severity_distribution.get("HIGH", 0) > 0:
            return "HIGH"
        elif severity_distribution.get("MEDIUM", 0) > 0:
            return "MEDIUM"
        else:
            return "LOW"
    
    @staticmethod
    def send_slack_notification(
        impact_result: Dict[str, Any],
        webhook_url: str,
        change_description: Optional[str] = None
    ) -> bool:
        """
        Send Slack notification for high-impact changes (optional).
        
        Args:
            impact_result: Impact analysis result
            webhook_url: Slack webhook URL
            change_description: Description of the change
        
        Returns:
            True if notification sent successfully
        """
        try:
            import requests
            
            summary = impact_result.get("summary", {})
            severity_dist = summary.get("severity_distribution", {})
            
            if not ImpactNotifier._should_notify(severity_dist):
                return False
            
            source = impact_result.get("source", {})
            max_severity = ImpactNotifier._get_max_severity(severity_dist)
            
            # Build Slack message
            color_map = {
                "CRITICAL": "#FF0000",
                "HIGH": "#FF8800",
                "MEDIUM": "#FFAA00",
                "LOW": "#00AA00"
            }
            
            payload = {
                "attachments": [
                    {
                        "color": color_map.get(max_severity, "#CCCCCC"),
                        "title": f"Impact Analysis Alert: {max_severity} Impact Detected",
                        "fields": [
                            {
                                "title": "Source Contract",
                                "value": source.get("contract_name", "Unknown"),
                                "short": True
                            },
                            {
                                "title": "Total Affected",
                                "value": str(impact_result.get("total_affected", 0)),
                                "short": True
                            },
                            {
                                "title": "Critical",
                                "value": str(severity_dist.get("CRITICAL", 0)),
                                "short": True
                            },
                            {
                                "title": "High",
                                "value": str(severity_dist.get("HIGH", 0)),
                                "short": True
                            }
                        ],
                        "text": change_description or "High-impact change detected",
                        "footer": "Data Interoperability Hub",
                        "ts": int(timezone.now().timestamp())
                    }
                ]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(
                "Slack impact notification sent",
                max_severity=max_severity,
                total_affected=impact_result.get("total_affected", 0)
            )
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to send Slack impact notification",
                error=str(e)
            )
            return False

