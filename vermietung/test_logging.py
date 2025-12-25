"""
Tests for logging configuration.
"""

import logging
import os
from pathlib import Path
from django.test import TestCase
from django.conf import settings


class LoggingConfigurationTests(TestCase):
    """Tests to verify logging configuration is working correctly."""
    
    def setUp(self):
        """Set up test logger."""
        self.logger = logging.getLogger('vermietung')
        self.logs_dir = settings.LOGS_DIR
    
    def test_logs_directory_exists(self):
        """Test that the logs directory exists."""
        self.assertTrue(self.logs_dir.exists())
        self.assertTrue(self.logs_dir.is_dir())
    
    def test_logging_configuration_exists(self):
        """Test that LOGGING configuration is set in settings."""
        self.assertIsNotNone(settings.LOGGING)
        self.assertIn('version', settings.LOGGING)
        self.assertEqual(settings.LOGGING['version'], 1)
    
    def test_file_handler_configured(self):
        """Test that file handler is configured."""
        self.assertIn('handlers', settings.LOGGING)
        self.assertIn('file', settings.LOGGING['handlers'])
        file_handler = settings.LOGGING['handlers']['file']
        self.assertEqual(file_handler['level'], 'DEBUG')
        self.assertEqual(file_handler['backupCount'], 7)
    
    def test_logger_can_log_debug(self):
        """Test that logger can log debug messages."""
        # This should not raise an exception
        self.logger.debug("Test debug message")
    
    def test_logger_can_log_info(self):
        """Test that logger can log info messages."""
        # This should not raise an exception
        self.logger.info("Test info message")
    
    def test_logger_can_log_warning(self):
        """Test that logger can log warning messages."""
        # This should not raise an exception
        self.logger.warning("Test warning message")
    
    def test_logger_can_log_error(self):
        """Test that logger can log error messages."""
        # This should not raise an exception
        self.logger.error("Test error message")
    
    def test_vermietung_logger_configured(self):
        """Test that vermietung logger is specifically configured."""
        self.assertIn('loggers', settings.LOGGING)
        self.assertIn('vermietung', settings.LOGGING['loggers'])
        vermietung_logger = settings.LOGGING['loggers']['vermietung']
        self.assertEqual(vermietung_logger['level'], 'DEBUG')
        self.assertIn('file', vermietung_logger['handlers'])
    
    def test_core_logger_configured(self):
        """Test that core logger is specifically configured."""
        self.assertIn('core', settings.LOGGING['loggers'])
        core_logger = settings.LOGGING['loggers']['core']
        self.assertEqual(core_logger['level'], 'DEBUG')
    
    def test_sentry_dsn_environment_variable(self):
        """Test that SENTRY_DSN can be read from environment."""
        # This should not raise an exception
        sentry_dsn = settings.SENTRY_DSN
        # SENTRY_DSN should be a string (empty or with value)
        self.assertIsInstance(sentry_dsn, str)
