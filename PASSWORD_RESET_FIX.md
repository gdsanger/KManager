# Password Reset Feature - Infinite Loading Fix

## Problem
When using the "Kennwort zurücksetzen" (Password Reset) admin action introduced in PR #128, the admin interface would show an infinite loading spinner (hourglass) and never complete. No password change occurred and no email was sent.

## Root Cause
The SMTP mail service in `core/mailing/service.py` did not specify a timeout when creating SMTP connections. When the SMTP server was unreachable or non-existent (e.g., localhost:587 with no server running), the connection attempt would hang indefinitely, causing the admin action to never return.

## Solution
Added a 10-second timeout to all SMTP connection attempts in `core/mailing/service.py`:

```python
# Before (infinite hang on unreachable server)
server = smtplib.SMTP(smtp_settings.host, smtp_settings.port)

# After (times out after 10 seconds)
server = smtplib.SMTP(smtp_settings.host, smtp_settings.port, timeout=10)
```

## Behavior After Fix

### Scenario 1: SMTP Server Unreachable
- **Before**: Infinite loading spinner, no response
- **After**: Returns within ~10 seconds with error message:
  - "Kennwort geändert, aber Mailversand fehlgeschlagen - Fehler beim Versenden der E-Mail: timed out"
  - Password is still changed (as per requirements)
  - Admin receives clear error notification

### Scenario 2: User Has No Email
- **Before & After**: Error message immediately
  - "Keine E-Mail-Adresse hinterlegt"
  - Password is NOT changed
  - No email attempt is made

### Scenario 3: SMTP Configured Correctly
- **Before & After**: Success
  - Password is changed
  - Email is sent successfully
  - Success message: "Neues Kennwort wurde per E-Mail versendet."

## Technical Details

### Files Modified
1. **core/mailing/service.py**
   - Lines 112, 116: Added `timeout=10` parameter to `smtplib.SMTP()` calls
   
2. **core/test_mail_service.py**
   - Added `test_smtp_connection_timeout()` test to verify timeout behavior

### Error Handling
The timeout integrates seamlessly with existing error handling:
- SMTP timeouts are caught by the generic `except Exception as e:` clause
- They raise `MailSendError` with the message "Fehler beim Versenden der E-Mail: timed out"
- The admin action catches this and displays it to the user
- Password change is preserved (no rollback on mail failure, as per spec)

### Testing
All tests pass:
- 11 password reset tests ✓
- 12 mail service tests (including new timeout test) ✓
- New test verifies connection timeout occurs within 15 seconds ✓
- CodeQL security scan: No issues ✓

### Manual Verification
Tested with:
1. Unreachable IP (192.0.2.1): Times out in ~10 seconds ✓
2. Refused connection (localhost:587): Fails immediately ✓
3. Both cases show proper error messages to admin ✓
4. Password is changed in all cases (except when user has no email) ✓

## Configuration Notes

### SMTP Settings
The system uses `SmtpSettings` model (singleton) configured in Django admin:
- Default: `localhost:587` (created automatically if not exists)
- For production: Configure with actual SMTP server details
- Settings are stored in database (core_smtpsettings table)

### BASE_URL Setting
The password reset email template uses `BASE_URL` from settings:
- Default: `http://localhost:8000`
- Production: Set via environment variable `BASE_URL`
- Used in email template to provide login link

## Recommendations

1. **Configure SMTP in Production**
   - Navigate to Admin → SMTP Einstellungen
   - Set correct SMTP server, port, credentials
   - Test by resetting a test user's password

2. **Set BASE_URL Environment Variable**
   ```bash
   export BASE_URL=https://app.ebner-vermietung.de
   ```

3. **Monitor Mail Delivery**
   - Check logs for SMTP errors
   - Verify users receive reset emails
   - Adjust timeout if needed (currently 10 seconds)

## Related Issues/PRs
- Issue #127: Original feature request
- PR #128: Initial implementation
- Current PR: Bug fix for infinite loading issue
