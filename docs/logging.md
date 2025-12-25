# Logging Configuration

## Overview

The KManager application has a comprehensive logging system that logs to both file and console with the following features:

1. **File-based logging** to `/logs` directory
2. **Daily log rotation** with 7 days retention
3. **Multiple logging levels**: DEBUG, INFO, WARNING, and ERROR
4. **Sentry integration** for error tracking (optional)

## Log Levels

The application supports the following log levels:

- **DEBUG**: Detailed information for diagnosing problems (file only)
- **INFO**: General informational messages (file and console)
- **WARNING**: Warning messages for potentially harmful situations (file and console)
- **ERROR**: Error events that might still allow the application to continue (file, console, and Sentry)

## File Logging

### Location
All logs are stored in the `/logs` directory at the project root.

### File Rotation
- A new log file is created at **midnight** each day
- Log files are named `kmanager.log`
- Old log files are automatically renamed with a date suffix (e.g., `kmanager.log.2025-12-24`)
- The system keeps **7 days** of log history
- Older logs are automatically deleted

### Log Format
Each log entry includes:
- Log level (DEBUG, INFO, WARNING, ERROR)
- Timestamp
- Module name
- Process ID
- Thread ID
- Log message

Example:
```
ERROR 2025-12-25 11:11:44,611 test_logging_manual 3608 140444731785344 This is an ERROR message
```

## Sentry Integration

### Configuration
Sentry integration is **optional** and controlled via the `SENTRY_DSN` environment variable.

To enable Sentry:
1. Sign up for a Sentry account at https://sentry.io
2. Create a new project for KManager
3. Copy your Sentry DSN
4. Add it to your `.env` file:
   ```
   SENTRY_DSN=https://your-sentry-dsn-here
   ```

### Behavior
- **Only ERROR-level events** are sent to Sentry
- DEBUG, INFO, and WARNING messages are NOT sent to Sentry
- If `SENTRY_DSN` is empty or not set, Sentry integration is disabled
- The environment is automatically set based on `DEBUG` setting:
  - `development` when `DEBUG=True`
  - `production` when `DEBUG=False`

## Usage in Code

### Basic Usage

```python
import logging

# Get a logger for your module
logger = logging.getLogger(__name__)

# Log at different levels
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
```

### Example in Views

```python
import logging
from django.shortcuts import render

logger = logging.getLogger(__name__)

def my_view(request):
    logger.info(f"User {request.user} accessed my_view")
    try:
        # Your code here
        pass
    except Exception as e:
        logger.error(f"Error in my_view: {e}", exc_info=True)
        raise
```

### Example in Models

```python
import logging
from django.db import models

logger = logging.getLogger(__name__)

class MyModel(models.Model):
    def save(self, *args, **kwargs):
        logger.debug(f"Saving MyModel instance: {self.pk}")
        super().save(*args, **kwargs)
        logger.info(f"MyModel instance saved: {self.pk}")
```

## Testing

### Running Logging Tests

```bash
python manage.py test vermietung.test_logging
```

### Manual Testing

Run the manual test script to verify logging configuration:

```bash
python test_logging_manual.py
```

This will:
- Test all logging levels
- Verify log file creation
- Display recent log entries
- Show Sentry configuration status

## Configuration Details

The logging configuration is defined in `kmanager/settings.py`:

- **Root Logger**: Logs to both file and console at DEBUG level
- **Django Logger**: Logs at INFO level
- **App Loggers**: `vermietung` and `core` apps log at DEBUG level
- **File Handler**: Uses `TimedRotatingFileHandler` with midnight rotation
- **Console Handler**: Outputs INFO and above to console

## Troubleshooting

### Logs Not Being Written

1. Check that the `/logs` directory exists and is writable
2. Verify Django settings are loaded correctly
3. Check file permissions

### Sentry Not Receiving Errors

1. Verify `SENTRY_DSN` is set correctly in `.env`
2. Ensure the error is actually at ERROR level (not WARNING or INFO)
3. Check Sentry project settings and rate limits
4. Verify network connectivity to Sentry

### Log Files Growing Too Large

- The current configuration keeps 7 days of logs with daily rotation
- To change retention period, modify `backupCount` in `settings.py`
- To change rotation frequency, modify the `when` parameter

## Security Considerations

- **Never commit** the `.env` file containing `SENTRY_DSN` to version control
- The `/logs` directory is excluded from git via `.gitignore`
- Ensure log files don't contain sensitive information like passwords
- Review log retention policy based on your data protection requirements
