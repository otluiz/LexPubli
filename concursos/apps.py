from django.apps import AppConfig


class ConcursosConfig(AppConfig):
    name = "concursos"
    verbose_name = "Concursos"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401
