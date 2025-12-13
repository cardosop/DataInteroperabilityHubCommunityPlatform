"""
Compliance Report Scheduler

Handles scheduled report generation and email delivery.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import ComplianceReport
from .compliance_reports import ComplianceReportGenerator


class ReportScheduler:
    """
    Schedules and generates compliance reports.
    """
    
    @staticmethod
    @transaction.atomic
    def generate_and_save_report(
        tenant_id: str,
        regulation: str,
        report_type: str = "STANDARD",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[str] = None
    ) -> ComplianceReport:
        """
        Generate and save a compliance report.
        
        Args:
            tenant_id: Tenant UUID
            regulation: Regulation (GDPR, HIPAA, SOX, LGPD, CCPA)
            report_type: Report type (STANDARD, SUMMARY, DETAILED)
            start_date: Start date (optional)
            end_date: End date (optional)
            user_id: User UUID who triggered generation (optional)
        
        Returns:
            ComplianceReport instance
        """
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Generate report based on regulation
        if regulation == "GDPR":
            report_data = ComplianceReportGenerator.generate_gdpr_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "HIPAA":
            report_data = ComplianceReportGenerator.generate_hipaa_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "SOX":
            report_data = ComplianceReportGenerator.generate_sox_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "LGPD":
            report_data = ComplianceReportGenerator.generate_lgpd_report(
                tenant_id, start_date, end_date
            )
        elif regulation == "CCPA":
            report_data = ComplianceReportGenerator.generate_ccpa_report(
                tenant_id, start_date, end_date
            )
        else:
            raise ValueError(f"Unknown regulation: {regulation}")
        
        # Create report record
        report = ComplianceReport.objects.create(
            tenant_id=tenant_id,
            regulation=regulation,
            report_type=report_type,
            report_data=report_data,
            start_date=start_date,
            end_date=end_date,
            created_by_id=user_id
        )
        
        return report
    
    @staticmethod
    @transaction.atomic
    def schedule_report(
        tenant_id: str,
        regulation: str,
        schedule_frequency: str,
        email_recipients: List[str],
        report_type: str = "STANDARD",
        user_id: Optional[str] = None
    ) -> ComplianceReport:
        """
        Schedule a recurring compliance report.
        
        Args:
            tenant_id: Tenant UUID
            regulation: Regulation (GDPR, HIPAA, SOX, LGPD, CCPA)
            schedule_frequency: Frequency (DAILY, WEEKLY, MONTHLY, QUARTERLY)
            email_recipients: List of email addresses
            report_type: Report type (STANDARD, SUMMARY, DETAILED)
            user_id: User UUID who created schedule (optional)
        
        Returns:
            ComplianceReport instance (template for scheduled reports)
        """
        # Calculate period based on frequency
        end_date = timezone.now()
        if schedule_frequency == "DAILY":
            start_date = end_date - timedelta(days=1)
        elif schedule_frequency == "WEEKLY":
            start_date = end_date - timedelta(days=7)
        elif schedule_frequency == "MONTHLY":
            start_date = end_date - timedelta(days=30)
        elif schedule_frequency == "QUARTERLY":
            start_date = end_date - timedelta(days=90)
        else:
            raise ValueError(f"Unknown schedule frequency: {schedule_frequency}")
        
        # Generate initial report
        report = ReportScheduler.generate_and_save_report(
            tenant_id=tenant_id,
            regulation=regulation,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id
        )
        
        # Mark as scheduled
        report.scheduled = True
        report.schedule_frequency = schedule_frequency
        report.email_recipients = email_recipients
        report.save()
        
        # Send initial report
        ReportScheduler.send_report_email(report)
        
        return report
    
    @staticmethod
    def send_report_email(report: ComplianceReport) -> bool:
        """
        Send compliance report via email.
        
        Args:
            report: ComplianceReport instance
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not report.email_recipients:
            return False
        
        try:
            # Generate email content
            subject = f"{report.regulation} Compliance Report - {report.tenant.name}"
            
            # Create email body (HTML)
            context = {
                'report': report,
                'regulation': report.regulation,
                'report_data': report.report_data,
                'start_date': report.start_date,
                'end_date': report.end_date,
                'tenant_name': report.tenant.name
            }
            
            # Try to render template, fallback to plain text
            try:
                html_message = render_to_string(
                    'governance/compliance_report_email.html',
                    context
                )
            except Exception:
                # Fallback to plain text
                html_message = None
            
            # Plain text message
            text_message = f"""
{report.regulation} Compliance Report

Period: {report.start_date.date()} to {report.end_date.date()}
Tenant: {report.tenant.name}

Compliance Summary:
- Total Runs: {report.report_data.get('compliance_runs', {}).get('total', 0)}
- Passed: {report.report_data.get('compliance_runs', {}).get('passed', 0)}
- Failed: {report.report_data.get('compliance_runs', {}).get('failed', 0)}
- Compliance Rate: {report.report_data.get('compliance_runs', {}).get('compliance_rate', 0):.1f}%

Generated at: {report.created_at}
"""
            
            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=report.email_recipients,
                html_message=html_message,
                fail_silently=False
            )
            
            # Update report
            report.email_sent = True
            report.email_sent_at = timezone.now()
            report.save()
            
            return True
        
        except Exception as e:
            # Log error but don't fail
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error(
                "Failed to send compliance report email",
                report_id=str(report.id),
                error=str(e)
            )
            return False
    
    @staticmethod
    def generate_scheduled_reports() -> Dict[str, Any]:
        """
        Generate all scheduled reports that are due.
        
        Returns:
            Dictionary with generation summary
        """
        now = timezone.now()
        results = {
            'generated': 0,
            'failed': 0,
            'emailed': 0,
            'details': []
        }
        
        # Get all scheduled reports
        scheduled_reports = ComplianceReport.objects.filter(
            scheduled=True
        )
        
        for template_report in scheduled_reports:
            try:
                # Calculate next report period
                end_date = now
                if template_report.schedule_frequency == "DAILY":
                    start_date = end_date - timedelta(days=1)
                elif template_report.schedule_frequency == "WEEKLY":
                    start_date = end_date - timedelta(days=7)
                elif template_report.schedule_frequency == "MONTHLY":
                    start_date = end_date - timedelta(days=30)
                elif template_report.schedule_frequency == "QUARTERLY":
                    start_date = end_date - timedelta(days=90)
                else:
                    continue
                
                # Check if report already exists for this period
                existing = ComplianceReport.objects.filter(
                    tenant_id=template_report.tenant_id,
                    regulation=template_report.regulation,
                    scheduled=False,
                    start_date__gte=start_date - timedelta(hours=1),
                    start_date__lte=start_date + timedelta(hours=1),
                    end_date__gte=end_date - timedelta(hours=1),
                    end_date__lte=end_date + timedelta(hours=1)
                ).exists()
                
                if existing:
                    continue  # Skip if already generated
                
                # Generate new report
                new_report = ReportScheduler.generate_and_save_report(
                    tenant_id=str(template_report.tenant_id),
                    regulation=template_report.regulation,
                    report_type=template_report.report_type,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Copy email recipients from template
                new_report.email_recipients = template_report.email_recipients
                new_report.save()
                
                # Send email
                email_sent = ReportScheduler.send_report_email(new_report)
                
                results['generated'] += 1
                if email_sent:
                    results['emailed'] += 1
                
                results['details'].append({
                    'report_id': str(new_report.id),
                    'regulation': new_report.regulation,
                    'email_sent': email_sent
                })
            
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'template_id': str(template_report.id),
                    'error': str(e)
                })
        
        return results

