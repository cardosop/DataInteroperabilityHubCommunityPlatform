"""
Management command to validate ODCS to ODPS migration (Task 9.1.2).

This command validates that contract migrations are successful and complete:
- Verifies all contracts migrated successfully
- Verifies no data loss (compare HubContract before/after)
- Verifies links are correct (bidirectional validation)
- Verifies marketplace metadata preserved
- Generates migration report with statistics

Usage:
    # Validate all migrations
    python manage.py validate_migration

    # Validate for specific tenant
    python manage.py validate_migration --tenant-id <uuid>

    # Validate specific contracts
    python manage.py validate_migration --contract-ids <id1>,<id2>,<id3>

    # Save report to file
    python manage.py validate_migration --report-path /path/to/report.json

    # Output format
    python manage.py validate_migration --format json
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from hub.apps.contracts.migration_validation import MigrationValidator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Validate ODCS to ODPS contract migrations (Task 9.1.2)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help="Validate migrations for specific tenant only",
        )
        parser.add_argument(
            "--contract-ids",
            type=str,
            default=None,
            help="Comma-separated list of ODCS contract IDs to validate",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            default=None,
            help="Path to save validation report (JSON format)",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["text", "json"],
            default="text",
            help="Output format: text (default) or json",
        )
        parser.add_argument(
            "--include-statistics",
            action="store_true",
            default=True,
            help="Include detailed statistics in report (default: True)",
        )

    def handle(self, *args, **options):
        tenant_id = options.get("tenant_id")
        contract_ids_str = options.get("contract_ids")
        report_path = options.get("report_path")
        output_format = options.get("format", "text")
        include_statistics = options.get("include_statistics", True)

        # Parse contract IDs if provided
        contract_ids = None
        if contract_ids_str:
            contract_ids = [cid.strip() for cid in contract_ids_str.split(",") if cid.strip()]

        self.stdout.write(self.style.SUCCESS("Starting migration validation..."))

        try:
            # Initialize validator
            validator = MigrationValidator(tenant_id=tenant_id)

            # Run validation
            report = validator.validate_migration(
                odcs_contract_ids=contract_ids, include_statistics=include_statistics
            )

            # Generate and output report
            if output_format == "json":
                report_text = validator.generate_report_json(report)
                if report_path:
                    with open(report_path, "w") as f:
                        f.write(report_text)
                    self.stdout.write(self.style.SUCCESS(f"JSON report saved to: {report_path}"))
                else:
                    self.stdout.write(report_text)
            else:
                report_text = validator.generate_report_text(report)
                self.stdout.write(report_text)

                # Also save JSON if path specified
                if report_path:
                    json_report = validator.generate_report_json(report)
                    with open(report_path, "w") as f:
                        f.write(json_report)
                    self.stdout.write(
                        self.style.SUCCESS(f"\nJSON report also saved to: {report_path}")
                    )

            # Exit with appropriate code
            if report.errors > 0:
                self.stdout.write(
                    self.style.ERROR(f"\nValidation completed with {report.errors} error(s)")
                )
                raise CommandError(f"Validation found {report.errors} error(s)")
            elif report.warnings > 0:
                self.stdout.write(
                    self.style.WARNING(f"\nValidation completed with {report.warnings} warning(s)")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("\nValidation completed successfully - no issues found")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Validation failed: {e!s}"))
            logger.exception("Migration validation command failed")
            raise CommandError(f"Validation failed: {e!s}") from e
