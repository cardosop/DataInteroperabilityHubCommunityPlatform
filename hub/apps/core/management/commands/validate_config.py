"""
Validate startup configuration (database, Redis, ALLOWED_HOSTS, production).

Exits 0 if valid, 1 and prints error if invalid. Run before starting the server
in production (e.g. in container entrypoint). See docs/CONFIG_VALIDATION_DESIGN.md.
"""

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand

from hub.apps.core.config_validation import validate_all


class Command(BaseCommand):
    help = (
        "Validate required config (database, Redis, ALLOWED_HOSTS, secrets). "
        "Exit 0 if valid, 1 if invalid. See docs/CONFIG_VALIDATION_DESIGN.md."
    )

    def handle(self, *args, **options):
        try:
            validate_all()
            self.stdout.write(self.style.SUCCESS("Configuration valid."))
        except ImproperlyConfigured as e:
            self.stderr.write(self.style.ERROR(str(e)))
            raise SystemExit(1) from e
