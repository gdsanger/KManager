from django.apps import AppConfig


class AuftragsverwaltungConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auftragsverwaltung'

    def ready(self):
        # Rücknahme der Projektabrechnung beim Löschen von Entwurfspositionen
        from auftragsverwaltung import signals  # noqa: F401
