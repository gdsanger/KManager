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
