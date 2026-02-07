from kmanager.settings import *

# Use file-based SQLite for test server
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/tmp/kmanager_test.db',
    }
}

# Allow all hosts for testing
ALLOWED_HOSTS = ['*']
DEBUG = True
