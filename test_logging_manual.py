"""
Manual test script to verify logging configuration.
This script tests that logging works correctly with all levels
and that log files are created in the correct location.
"""

import os
import sys
from pathlib import Path

# Set up Django settings - use environment variable or default to test_settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('DJANGO_SETTINGS_MODULE', 'test_settings'))

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import django
django.setup()

import logging
from django.conf import settings

# Get the logger
logger = logging.getLogger('vermietung')

print("=" * 80)
print("Logging Configuration Test")
print("=" * 80)
print(f"\nLogs directory: {settings.LOGS_DIR}")
print(f"Directory exists: {settings.LOGS_DIR.exists()}")

# Test all logging levels
print("\n" + "-" * 80)
print("Testing all logging levels:")
print("-" * 80)

logger.debug("This is a DEBUG message - should appear in file")
print("✓ DEBUG message logged")

logger.info("This is an INFO message - should appear in file and console")
print("✓ INFO message logged")

logger.warning("This is a WARNING message - should appear in file and console")
print("✓ WARNING message logged")

logger.error("This is an ERROR message - should appear in file and console")
print("✓ ERROR message logged")

# Check if log file was created
log_file = settings.LOGS_DIR / 'kmanager.log'
print("\n" + "-" * 80)
print("Log file verification:")
print("-" * 80)
print(f"Log file path: {log_file}")
print(f"Log file exists: {log_file.exists()}")

if log_file.exists():
    print(f"Log file size: {log_file.stat().st_size} bytes")
    print("\n" + "-" * 80)
    print("Last 10 lines of log file:")
    print("-" * 80)
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[-10:]:
            print(line.rstrip())

# Test Sentry configuration
print("\n" + "-" * 80)
print("Sentry configuration:")
print("-" * 80)
print(f"SENTRY_DSN configured: {bool(settings.SENTRY_DSN)}")
if settings.SENTRY_DSN:
    print(f"Sentry DSN: {settings.SENTRY_DSN[:20]}...")
else:
    print("Sentry is not configured (SENTRY_DSN is empty)")
    print("To enable Sentry, set SENTRY_DSN in your .env file")

print("\n" + "=" * 80)
print("Logging test completed successfully!")
print("=" * 80)
