"""
Management command to check service availability.

Usage:
    python manage.py check_services
    python manage.py check_services --service dq-service
    python manage.py check_services --verbose
"""

from django.core.management.base import BaseCommand

from hub.apps.core.services.availability import (
    check_all_services,
    check_service_availability,
    get_all_service_configs,
)


class Command(BaseCommand):
    help = "Check availability of all microservices"

    def add_arguments(self, parser):
        parser.add_argument(
            "--service",
            type=str,
            help="Check specific service only (e.g., dq-service, compliance-service)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed information for each service",
        )

    def handle(self, *args, **options):
        service_name = options.get("service")
        verbose = options.get("verbose", False)

        if service_name:
            # Check single service
            configs = get_all_service_configs()
            if service_name not in configs:
                self.stdout.write(self.style.ERROR(f"Unknown service: {service_name}"))
                self.stdout.write(f"Available services: {', '.join(configs.keys())}")
                return

            config = configs[service_name]
            is_available, error_msg = check_service_availability(
                service_name=service_name,
                service_url=config["url"],
                health_path=config.get("health_path", "/health"),
                timeout=config.get("timeout", 5),
            )

            if is_available:
                self.stdout.write(self.style.SUCCESS(f"✓ {service_name} is available and healthy"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ {service_name} is not available"))
                if verbose and error_msg:
                    self.stdout.write(f"  Error: {error_msg}")
        else:
            # Check all services
            self.stdout.write("Checking service availability...\n")
            results = check_all_services()

            available_count = sum(1 for is_avail, _ in results.values() if is_avail)
            total_count = len(results)

            for service_name, (is_available, error_msg) in results.items():
                if is_available:
                    self.stdout.write(self.style.SUCCESS(f"✓ {service_name}"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ {service_name}"))
                    if verbose and error_msg:
                        self.stdout.write(f"  Error: {error_msg}")

            self.stdout.write(f"\nSummary: {available_count}/{total_count} services available")

            if available_count < total_count:
                unavailable = [name for name, (is_avail, _) in results.items() if not is_avail]
                self.stdout.write(
                    self.style.WARNING(f"Unavailable services: {', '.join(unavailable)}")
                )
