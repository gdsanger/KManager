from kmanager.settings import *

# Use SQLite file for manual testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'manual_test.db',
    }
}

# Allow all hosts for testing
ALLOWED_HOSTS = ['*']
