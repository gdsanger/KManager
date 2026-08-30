"""
Test settings for KManager project.
Uses SQLite for testing instead of PostgreSQL.
"""

from kmanager.settings import *

# Override database settings for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Keine KI-Aufrufe aus Tests heraus. Tests, die die Normalisierung prüfen,
# schalten sie gezielt per @override_settings ein und mocken den AIRouter.
AI_TIME_ENTRY_NORMALIZATION_ENABLED = False
