# PaymentTerm Admin Fix - Summary

## Issue Fixed
**Title:** Fehler bei Zahlungsbedingungen (PaymentTerm) in Admin UI  
**Issue Type:** Bug  
**Agira Item ID:** 270

## Problem Description
The Django Admin interface for `PaymentTerm` at `/admin/core/paymentterm/` was throwing a `ProgrammingError`:
```
Exception Type: ProgrammingError
Exception Value: Spalte core_paymentterm.company_id existiert nicht
```

The error occurred because the admin was trying to access a `company_id` column that doesn't exist in the `PaymentTerm` model, as PaymentTerm is designed to be a **global** model (not company-specific).

## Root Cause
1. **Model Definition:** The `PaymentTerm` model in `core/models.py` correctly does NOT have a `company` field (it's global)
2. **Migration History:** 
   - Migration 0014 initially created PaymentTerm WITH a company field
   - Migration 0015 removed the company field to make it global
3. **Test Mismatch:** The test file `core/test_paymentterm.py` still referenced the old `company` field
4. **Database State:** The database needed migration 0015 to be applied

## Solution Implemented

### 1. Test File Updates
**File:** `core/test_paymentterm.py`
- Removed all references to `company` parameter in `PaymentTerm.objects.create()` calls
- Removed company-related tests:
  - `test_multiple_defaults_different_companies`
  - `test_get_default_different_companies`
  - `test_company_cascade_protection`
- Updated remaining tests to reflect global PaymentTerm model
- Removed 4 tests, updated 22 tests to be company-agnostic
- Removed unnecessary empty `setUp()` method

**Changes:**
- Before: Tests created PaymentTerms with `company=self.company1`
- After: Tests create PaymentTerms without company parameter
- Before: `PaymentTerm.get_default(company)` - company-specific
- After: `PaymentTerm.get_default()` - global default

### 2. New Admin Test File
**File:** `core/test_paymentterm_admin.py` (NEW)
Created comprehensive admin tests to prevent regression:
- `test_changelist_loads_without_error()` - Verifies admin changelist loads successfully
- `test_list_display()` - Ensures 'company' is NOT in list_display
- `test_list_filter()` - Ensures only 'is_default' filter exists
- `test_search_fields()` - Ensures no company-related search fields
- `test_discount_info_display()` - Tests discount display method
- `test_queryset_has_no_company_filter()` - Verifies no ProgrammingError on queryset execution

### 3. Database Migration
Applied migration 0015 which:
- Removed `company` ForeignKey field
- Removed company-related indexes
- Changed constraint from per-company default to global default
- Updated model ordering from `['company', 'name']` to `['name']`

### 4. Admin Configuration Verification
**File:** `core/admin.py` (already correct, no changes needed)
```python
@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_info', 'net_days', 'is_default')
    list_filter = ('is_default',)  # No company filter
    search_fields = ('name',)  # No company relations
    ordering = ('name',)  # No company ordering
```

## Test Results

### Before Fix
- Tests failed due to company field references
- Admin raised ProgrammingError when accessing changelist

### After Fix
- ✅ **32 tests passing** (26 model tests + 6 admin tests)
- ✅ Admin changelist loads successfully at `/admin/core/paymentterm/`
- ✅ No ProgrammingError exceptions
- ✅ PaymentTerms display correctly with all fields
- ✅ CodeQL security scan: 0 alerts
- ✅ Code review completed with all suggestions addressed

## Visual Verification

The admin interface now works correctly and displays:
- Payment term name
- Discount information (Skonto)
- Net days (Zahlungsziel)
- Default flag (Standard)
- Filter by "is_default"

![PaymentTerm Admin Screenshot](https://github.com/user-attachments/assets/43d257e4-3188-4d7b-b53b-c315789fff7e)

## Acceptance Criteria Status

All acceptance criteria from the issue have been met:

- ✅ `GET /admin/core/paymentterm/` loads without exception
- ✅ No join/filter on `core_mandant`/`company` in PaymentTerm admin
- ✅ PaymentTerm remains global (no `company` FK, no migration to add `company_id`)
- ✅ Automated tests cover the fix and prevent regression

## Technical Implementation Details

### Model Structure
PaymentTerm is a **global** model with:
- `name` - Payment term name
- `discount_days` - Optional discount period in days
- `discount_rate` - Optional discount rate (e.g., 0.02 for 2%)
- `net_days` - Payment due days
- `is_default` - Global default flag (only one can be True)

### Constraint Changes
- **Old constraint:** One default per company
  ```python
  models.UniqueConstraint(
      fields=('company',),
      condition=models.Q(is_default=True),
      name='unique_default_payment_term_per_company'
  )
  ```
- **New constraint:** One global default
  ```python
  models.UniqueConstraint(
      fields=('is_default',),
      condition=models.Q(is_default=True),
      name='unique_default_payment_term'
  )
  ```

### Default Handling
The model's `save()` method ensures only one default exists globally:
```python
def save(self, *args, **kwargs):
    if self.is_default:
        # Deactivate any existing default
        PaymentTerm.objects.filter(
            is_default=True
        ).exclude(pk=self.pk).update(is_default=False)
    super().save(*args, **kwargs)
```

## Files Modified

1. **core/test_paymentterm.py**
   - Removed company references
   - Updated 22 tests
   - Removed 4 company-specific tests
   - Removed empty setUp method

2. **core/test_paymentterm_admin.py** (NEW)
   - Added 6 admin tests
   - Prevents regression
   - Tests admin functionality

3. **.gitignore**
   - Added temporary test files

## Migration Applied

**Migration:** `core/0015_alter_paymentterm_options_and_more.py`

This migration:
- Removes `company` field from PaymentTerm
- Updates model ordering
- Updates constraint for global default
- Removes company-related indexes

## Testing Instructions

To test this fix:

```bash
# Run PaymentTerm tests
python manage.py test core.test_paymentterm core.test_paymentterm_admin -v 2

# Apply migrations
python manage.py migrate

# Start development server
python manage.py runserver

# Access admin at: http://localhost:8000/admin/core/paymentterm/
```

## Related Issues

- Similar to issue #3 (Kostenarten Admin error)
- Pull request #4 may contain similar patterns

## Conclusion

The fix successfully resolves the ProgrammingError in the PaymentTerm admin interface by ensuring the model, tests, and database schema are all aligned on PaymentTerm being a **global** model without company relationships. The admin interface now loads correctly and displays all PaymentTerms as expected.
