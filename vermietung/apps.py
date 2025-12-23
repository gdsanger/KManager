from django.apps import AppConfig
from pathlib import Path


class VermietungConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vermietung'
    verbose_name = 'Vermietung'

    def ready(self):
        """
        Called when the app is ready.
        Ensures that required media directories exist.
        """
        from django.conf import settings
        
        # Ensure VERMIETUNG_DOCUMENTS_ROOT directory exists
        # This is critical for file uploads to work properly
        vermietung_docs_root = Path(settings.VERMIETUNG_DOCUMENTS_ROOT)
        if not vermietung_docs_root.exists():
            try:
                vermietung_docs_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                # Log the error but don't crash the application
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Failed to create VERMIETUNG_DOCUMENTS_ROOT directory "
                    f"at {vermietung_docs_root}: {e}"
                )
