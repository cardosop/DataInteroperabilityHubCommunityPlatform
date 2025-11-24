"""
Django management command to check for jobs that have exceeded their timeout.
"""
from django.core.management.base import BaseCommand
from hub.apps.jobs.tasks import check_job_timeouts


class Command(BaseCommand):
    help = 'Check for jobs that have exceeded their timeout and mark them as failed'

    def handle(self, *args, **options):
        """Execute the command"""
        self.stdout.write('Checking for timed-out jobs...')
        
        try:
            check_job_timeouts()
            self.stdout.write(self.style.SUCCESS('Successfully checked job timeouts'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking job timeouts: {str(e)}'))
            raise

