"""
Create an asset from the Django CLI using the canonical service path.

Task 250.7.C:
- Reuse ``AssetService.create_asset(...)`` (single source of truth)
- Args: --tenant, --key, --name, --description, --domain,
  --actor-email, --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hub.apps.assets.services import AssetService
from hub.apps.core.services.base import ConflictError, ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class Command(BaseCommand):
    help = (
        "Create an asset via AssetService.create_asset. "
        "Supports dry-run validation without persisting."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=str,
            required=True,
            help="Tenant UUID for the created asset.",
        )
        parser.add_argument(
            "--key",
            type=str,
            required=True,
            help="Tenant-scoped asset key (lowercase + hyphens).",
        )
        parser.add_argument(
            "--name",
            type=str,
            required=True,
            help="Asset display name.",
        )
        parser.add_argument(
            "--description",
            type=str,
            default=None,
            help="Optional asset description.",
        )
        parser.add_argument(
            "--domain",
            type=str,
            default=None,
            help="Optional logical domain (e.g. finance).",
        )
        parser.add_argument(
            "--actor-email",
            type=str,
            required=True,
            help="Actor email used for created_by and audit attribution.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Validate and execute the service path but rollback "
                "persistence."
            ),
        )

    def handle(self, *args, **options):
        tenant_id = options["tenant"]
        key = options["key"]
        name = options["name"]
        description = options.get("description")
        domain = options.get("domain")
        actor_email = options["actor_email"]
        dry_run = bool(options.get("dry_run"))

        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant '{tenant_id}' not found") from exc

        try:
            actor = User.objects.get(email=actor_email)
        except User.DoesNotExist as exc:
            raise CommandError(f"Actor user '{actor_email}' not found") from exc

        if actor.tenant is None or str(actor.tenant.id) != str(tenant.id):
            raise CommandError(
                f"Actor '{actor_email}' does not belong to tenant '{tenant.id}'"
            )

        asset_service = AssetService(tenant_id=str(tenant.id), user_id=str(actor.id))

        try:
            with transaction.atomic():
                asset = asset_service.create_asset(
                    tenant_id=str(tenant.id),
                    user_id=str(actor.id),
                    key=key,
                    name=name,
                    description=description,
                    domain=domain,
                    created_by=actor,
                )

                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(
                    self.style.WARNING(  # keep runbook logs concise
                        "DRY RUN: asset validated and would be created "
                        f"with id={asset.id}, tenant={tenant.id}, key={key}"
                    )
                    )
                    return

                self.stdout.write(
                    self.style.SUCCESS(
                        "Created asset "
                        f"id={asset.id} tenant={tenant.id} key={asset.key}"
                    )
                )
        except ValidationError as exc:
            raise CommandError(f"Asset validation failed: {exc}") from exc
        except ConflictError as exc:
            raise CommandError(f"Asset creation conflict: {exc}") from exc
