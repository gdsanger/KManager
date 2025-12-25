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
