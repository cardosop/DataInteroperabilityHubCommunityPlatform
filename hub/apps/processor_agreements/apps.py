from django.apps import AppConfig


class ProcessorAgreementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.processor_agreements"
    label = "processor_agreements"

    def ready(self) -> None:
        pass
