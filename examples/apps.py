from django.apps import AppConfig


class ExamplesConfig(AppConfig):
    """The gallery of rendered examples shown to prospective customers."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "examples"
