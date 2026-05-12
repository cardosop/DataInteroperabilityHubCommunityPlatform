"""
Phase 272.1 — AccessRequestComment model + RLS policy.

AccessRequestComment allows approvers and requesters to leave
threaded comments on an access request. Comments can be added
standalone or embedded in approve/reject payloads.
"""
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0006_retention_auto_enforcer_fields"),
        ("tenants", "0066_phase_271_1_tenant_connect_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessRequestComment",
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
                        related_name="access_request_comments",
                        help_text="Tenant this comment belongs to",
                    ),
                ),
                (
                    "access_request",
                    models.ForeignKey(
                        "AccessRequest",
                        on_delete=models.CASCADE,
                        related_name="comments",
                        help_text="Access request this comment is attached to",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        "users.User",
                        on_delete=models.SET_NULL,
                        related_name="access_request_comments",
                        null=True,
                        blank=True,
                        help_text="User who wrote this comment",
                    ),
                ),
                (
                    "body",
                    models.TextField(
                        help_text="Comment body text",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "access_request_comments",
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(
                        fields=["access_request", "created_at"],
                        name="ar_comment_thread_idx",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE access_request_comments ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON access_request_comments;
            CREATE POLICY tenant_isolation ON access_request_comments
            USING (
                current_setting('app.rls_access_request_comments_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON access_request_comments;
            ALTER TABLE access_request_comments DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
