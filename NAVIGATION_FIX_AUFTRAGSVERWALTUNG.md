# Navigation Fix - Auftragsverwaltung

## Issue
Navigation links in the Auftragsverwaltung module were broken, returning 404 errors with the message "No DocumentType matches the given query."

## Root Cause
There was a key mismatch between:
1. **Migration 0009**: Creates DocumentTypes with English keys (`quote`, `order`, `invoice`, `delivery`, `credit`)
2. **populate_documenttypes command**: Was using German keys (`angebot`, `auftrag`, `rechnung`, `lieferschein`, `gutschrift`)
3. **URL patterns**: Expect English keys

## Solution
Updated the `populate_documenttypes` management command to use English keys that match the migration and URL patterns.

### Changed Keys
| German Key (OLD) | English Key (NEW) | Display Name |
|------------------|-------------------|--------------|
| angebot | quote | Angebot |
| auftrag | order | Auftragsbestätigung |
| rechnung | invoice | Rechnung |
| lieferschein | delivery | Lieferschein |
| gutschrift | credit | Gutschrift |

### Changed Prefixes
| Document Type | Old Prefix | New Prefix |
|---------------|------------|------------|
| Angebot | A | AN |
| Gutschrift | RK | GS |

## Usage
To ensure DocumentTypes exist and are properly configured:

```bash
python manage.py populate_documenttypes
```

This command is idempotent and can be run multiple times safely. It will:
- Create missing DocumentTypes
- Update existing DocumentTypes to match the standard configuration
- Activate any inactive DocumentTypes

## Testing
Comprehensive tests have been added in `test_populate_documenttypes.py` to prevent regression.

Run tests:
```bash
python manage.py test auftragsverwaltung.test_populate_documenttypes
```

## Files Modified
- `auftragsverwaltung/management/commands/populate_documenttypes.py` - Fixed keys
- `auftragsverwaltung/test_populate_documenttypes.py` - New comprehensive tests
- Various test files - Updated to use `.get()` instead of `.create()` for standard DocumentTypes
