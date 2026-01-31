from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        Import report templates on app ready to ensure registration.
        """
        # Import reports to trigger template registration
        try:
            import reports
        except ImportError:
            pass
