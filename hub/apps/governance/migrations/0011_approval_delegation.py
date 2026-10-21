"""
Phase 272.6 — ApprovalDelegation model + RLS policy.

Tracks temporary delegation of approval authority from one user
(delegator) to another (delegate) within a time window.
"""
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0010_revocation_reason"),
        ("tenants", "0067_phase_272_compliance_gate"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalDelegation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        primary_key=True,
                        default=uuid.uuid4,
                        editable=False,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        "tenants.Tenant",
                        on_delete=models.CASCADE,
                        related_name="approval_delegations",
                    ),
                ),
                (
                    "delegator",
                    models.ForeignKey(
                        "users.User",
                        on_delete=models.CASCADE,
                        related_name="delegations_given",
                        help_text="User delegating their approval authority",
                    ),
                ),
                (
                    "delegate",
                    models.ForeignKey(
                        "users.User",
                        on_delete=models.CASCADE,
                        related_name="delegations_received",
                        help_text="User receiving delegated approval authority",
                    ),
                ),
                ("start_at", models.DateTimeField(help_text="Delegation window start")),
                ("end_at", models.DateTimeField(help_text="Delegation window end")),
                (
                    "reason",
                    models.TextField(
                        null=True,
                        blank=True,
                        help_text="Reason for delegation",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "approval_delegations",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["delegate", "start_at", "end_at"],
                        name="delegation_active_window_idx",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE approval_delegations ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON approval_delegations;
            CREATE POLICY tenant_isolation ON approval_delegations
            USING (
                current_setting('app.rls_approval_delegations_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON approval_delegations;
            ALTER TABLE approval_delegations DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
