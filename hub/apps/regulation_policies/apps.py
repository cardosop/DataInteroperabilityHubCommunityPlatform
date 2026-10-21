"""Django app holding cross-jurisdiction policy registries."""

from django.apps import AppConfig


class RegulationPoliciesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.regulation_policies"
    label = "regulation_policies"
    verbose_name = "Regulation Policies"
