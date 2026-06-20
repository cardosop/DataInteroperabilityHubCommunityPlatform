"""285.14.8.9 — Show JWT signing key information.

Usage:
    python manage.py show_jwt_key_info
    python manage.py show_jwt_key_info --verbose
"""

import hashlib

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Display current JWT signing key metadata."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose", action="store_true", default=False, help="Show additional key details."
        )

    def handle(self, *args, **options):
        verbose = options["verbose"]

        jwt_key = getattr(settings, "JWT_SIGNING_KEY", None)
        if not jwt_key:
            self.stderr.write("JWT_SIGNING_KEY is not configured.")
            return

        # Show key metadata without exposing key material
        key_len = len(jwt_key) if isinstance(jwt_key, str) else len(jwt_key.encode())
        key_hash = hashlib.sha256(
            jwt_key.encode() if isinstance(jwt_key, str) else jwt_key
        ).hexdigest()[:16]

        self.stdout.write("JWT signing key configured: yes")
        self.stdout.write(f"Key length: {key_len} bytes")
        self.stdout.write(f"Key fingerprint (first 16 hex): {key_hash}")

        if verbose:
            algorithm = getattr(settings, "JWT_ALGORITHM", "RS256")
            issuer = getattr(settings, "JWT_ISSUER", "meshant")
            self.stdout.write(f"Algorithm: {algorithm}")
            self.stdout.write(f"Issuer: {issuer}")

        # Check AWS Secrets Manager if key is fetched from there
        secret_name = getattr(settings, "JWT_SECRET_NAME", None)
        if secret_name:
            self.stdout.write(f"AWS Secrets Manager secret: {secret_name}")
