"""invite_beta_cohort — Phase U.6 / WS-6: invite the internal beta cohort.

Reads a cohort CSV and issues REAL invitations through the canonical service
path used by POST /api/v1/users/ (``UserService.invite_user_to_tenant`` +
invitation token + ``send_invitation_email``). No mock/stub: emails leave
through the configured SMTP relay (MailHog in compose staging) and are
verifiable in its UI.

Idempotent: an already-invited email is reported as ``skipped``, not re-sent.
Cross-tenant by design — iterates tenants under ``tenant_context()`` per the
RLS contract (CLAUDE.md); a missing tenant in the CSV is a hard error, never
a silent cross-tenant write.

CSV format (header row required):
    tenant_slug,email,display_name,role_names
    acme-corp,beta1@example.com,Beta One,"TENANT_ADMIN,DATA_PROVIDER"
    acme-corp,beta2@example.com,Beta Two,

``role_names`` resolves against the TENANT's own Role rows (roles are
tenant-scoped); unknown names are reported per-row and the invite proceeds
with no roles — never a silent wrong-tenant role assignment.

Usage:
    python hub/manage.py invite_beta_cohort --csv cohort.csv
    python hub/manage.py invite_beta_cohort --csv cohort.csv --dry-run
    python hub/manage.py invite_beta_cohort --csv cohort.csv --no-send-email
    python hub/manage.py invite_beta_cohort --csv cohort.csv \
        --actor-email admin@staging.hub.example.com
"""

import csv
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from hub.apps.auth.utils import sha256_hex
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.users.models import User, UserStatus

CSV_FIELDS = ("tenant_slug", "email", "display_name", "role_names")


class Command(BaseCommand):
    help = "Invite the beta cohort from a CSV (tenant_slug,email,display_name,role_names)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Path to the cohort CSV.")
        parser.add_argument(
            "--actor-email",
            default="",
            help=(
                "Email of the tenant member acting as inviter. Default: the "
                "tenant's first TENANT_ADMIN-role user, else its first ACTIVE "
                "user. Fails when the tenant has no eligible actor."
            ),
        )
        parser.add_argument(
            "--no-send-email",
            action="store_true",
            default=False,
            help="Create invitations without enqueueing the invitation email.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Validate rows and print the plan without writing anything.",
        )

    def handle(self, **options):
        rows = self._load_csv(options["csv"])
        created = skipped = failed = 0
        summary = []

        for row_no, row in enumerate(rows, start=2):
            tenant_slug = (row.get("tenant_slug") or "").strip()
            email = (row.get("email") or "").strip().lower()
            display_name = (row.get("display_name") or "").strip() or None
            role_names = [n.strip() for n in (row.get("role_names") or "").split(",") if n.strip()]

            if not tenant_slug or not email or "@" not in email:
                self.stderr.write(f"row {row_no}: invalid tenant_slug/email — skipping")
                failed += 1
                continue

            try:
                tenant = Tenant.objects.get(slug=tenant_slug)
            except Tenant.DoesNotExist:
                self.stderr.write(
                    f"row {row_no}: tenant '{tenant_slug}' does not exist — "
                    "provision it first (hub/manage.py provision_tenant)"
                )
                failed += 1
                continue

            if options["dry_run"]:
                summary.append(
                    f"  [DRY-RUN] row {row_no}: {email} → tenant {tenant_slug}"
                    f" roles={role_names or '[]'}"
                )
                continue

            with tenant_context(str(tenant.id)):
                try:
                    outcome = self._invite_one(
                        tenant=tenant,
                        email=email,
                        display_name=display_name,
                        role_names=role_names,
                        actor_email=options["actor_email"],
                        send_email=not options["no_send_email"],
                    )
                except CommandError as exc:
                    outcome = {"error": str(exc)}
            created += outcome.get("created", 0)
            skipped += outcome.get("skipped", 0)
            if outcome.get("error"):
                failed += 1
                summary.append(f"  FAIL row {row_no}: {email} — {outcome['error']}")
            else:
                summary.append(
                    f"  row {row_no}: {email} → tenant {tenant_slug} — {outcome['status']}"
                )

        for line in summary:
            self.stdout.write(line)
        self.stdout.write(
            self.style.SUCCESS(
                f"invite_beta_cohort complete: created={created} skipped={skipped} "
                f"failed={failed} (rows={len(rows)})"
            )
        )
        if failed:
            raise CommandError(f"{failed} cohort row(s) failed — see output above.")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _load_csv(self, path: str) -> list[dict]:
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                missing = [f for f in CSV_FIELDS if f not in (reader.fieldnames or [])]
                if missing:
                    raise CommandError(
                        f"CSV is missing required column(s): {', '.join(missing)}. "
                        f"Expected header: {','.join(CSV_FIELDS)}"
                    )
                rows = list(reader)
        except OSError as exc:
            raise CommandError(f"Cannot read CSV '{path}': {exc}") from exc
        if not rows:
            raise CommandError(f"CSV '{path}' contains no data rows.")
        return rows

    def _resolve_actor(self, tenant: Tenant, actor_email: str):
        """The member who 'sends' the invitation (audit actor)."""
        from hub.apps.users.models import Role

        if actor_email:
            try:
                return User.objects.get(email__iexact=actor_email, tenant=tenant)
            except User.DoesNotExist:
                raise CommandError(
                    f"actor {actor_email} is not a member of tenant {tenant.slug}"
                ) from None
        admin_role_ids = Role.objects.filter(tenant=tenant, name="TENANT_ADMIN").values_list(
            "id", flat=True
        )
        actor = (
            User.objects.filter(
                user_roles__role_id__in=admin_role_ids,
                status=UserStatus.ACTIVE,
            )
            .distinct()
            .first()
        )
        if actor is None:
            actor = User.objects.filter(tenant=tenant, status=UserStatus.ACTIVE).first()
        if actor is None:
            raise CommandError(
                f"tenant {tenant.slug} has no eligible inviter user — "
                "provision the tenant admin first (hub/manage.py provision_tenant)"
            )
        return actor

    def _invite_one(self, *, tenant, email, display_name, role_names, actor_email, send_email):
        from hub.apps.users.models import Role
        from hub.apps.users.services import UserService

        actor = self._resolve_actor(tenant, actor_email)
        role_ids = list(
            Role.objects.filter(tenant=tenant, name__in=role_names).values_list("id", flat=True)
        )
        unknown_roles = set(role_names) - {
            r.name for r in Role.objects.filter(tenant=tenant, name__in=role_names)
        }
        if unknown_roles:
            self.stdout.write(
                f"  note: {email}: unknown roles in tenant {tenant.slug} ignored: "
                f"{sorted(unknown_roles)}"
            )

        service = UserService(tenant_id=str(tenant.id), user_id=str(actor.id))
        user, created = service.invite_user_to_tenant(
            tenant_id=str(tenant.id),
            actor_user_id=str(actor.id),
            email=email,
            display_name=display_name,
            role_ids=role_ids,
            send_invitation=send_email,
        )
        if not created:
            return {"status": "skipped (already a member)", "skipped": 1}

        # Parity with POST /api/v1/users/: token (SHA-256 at rest, 7-day TTL)
        # + enqueue the invitation email through the configured relay.
        plaintext = str(uuid.uuid4())
        user.invitation_token = sha256_hex(plaintext)
        user.invitation_token_expires_at = timezone.now() + timedelta(days=7)
        user.save(update_fields=["invitation_token", "invitation_token_expires_at"])
        if send_email:
            from hub.apps.notifications.tasks import send_invitation_email

            send_invitation_email.delay(user_id=str(user.id), plaintext_token=plaintext)
        return {"status": "invited", "created": 1}
