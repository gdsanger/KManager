from kmanager.settings import *

# Use SQLite for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Allow testserver in ALLOWED_HOSTS for testing
ALLOWED_HOSTS = ['*']

# Keine KI-Aufrufe aus Tests heraus. Tests, die die Normalisierung prüfen,
# schalten sie gezielt per @override_settings ein und mocken den AIRouter.
AI_TIME_ENTRY_NORMALIZATION_ENABLED = False
