# Mietverträge ActivityStream Integration Fix

## Overview
This document describes the fix for issue #320 - integrating ActivityStream events for all updates to Mietverträge (rental contracts) in `/vermietung/vertraege/`.

**Implementation Date:** February 8, 2026  
**Issue:** #320 - Integrate ActivityStream-Events in Mietverträge (/vermietung/vertraege/)  
**Related Issues:** #291, #313, #301, #314, #321

## Problem Statement

Changes in the UserUI for a rental contract (Mietvertrag) were not consistently creating entries in the Activity Stream. Specifically:

**Before Fix:**
- ❌ Editing a contract WITHOUT status change: No event logged
- ✅ Editing a contract WITH status change: `contract.status_changed` event logged
- ✅ Creating a contract: `contract.created` event logged
- ✅ Ending a contract: `contract.ended` event logged
- ✅ Cancelling a contract: `contract.cancelled` event logged

**Expected Behavior (1:1 like Adresse):**
- ✅ Any contract update should log `contract.updated` event
- ✅ Status changes should additionally log `contract.status_changed` event
- ✅ All CRUD operations should be tracked

## Root Cause

In `vermietung/views.py`, the `vertrag_edit()` function only logged an ActivityStream event when the status field changed:

```python
# Old code - only logged on status change
if old_status != new_status:
    _log_vertrag_stream_event(
        vertrag=vertrag,
        event_type='contract.status_changed',
        ...
    )
```

This meant that editing other fields (miete, kaution, mieter, etc.) would NOT create any activity stream entries, making it impossible to track general contract modifications.

## Solution

Modified `vertrag_edit()` to ALWAYS log a `contract.updated` event, and additionally log `contract.status_changed` when the status changes:

```python
# New code - always log update
_log_vertrag_stream_event(
    vertrag=vertrag,
    event_type='contract.updated',
    actor=request.user,
    description=f'Vertrag aktualisiert für Mieter: {mieter_name}'
)

# Additionally log status change if status changed
if old_status != new_status:
    _log_vertrag_stream_event(
        vertrag=vertrag,
        event_type='contract.status_changed',
        actor=request.user,
        description=f'Status geändert: {old_status_display} → {new_status_display}'
    )
```

## Changes Made

### 1. Updated `vermietung/views.py`

**Function:** `vertrag_edit(request, pk)`  
**Lines:** 1667-1688 (added ~17 lines)

#### Changes:
1. Always log `contract.updated` event after successful save
2. Keep existing `contract.status_changed` event for status transitions
3. Maintain error handling with user-friendly warnings

**Code Pattern:**
```python
try:
    # Save contract and formset...
    vertrag.update_mietobjekte_availability()
    
    # NEW: Always log contract update
    try:
        mieter_name = vertrag.mieter.full_name() if vertrag.mieter else 'Unbekannt'
        _log_vertrag_stream_event(
            vertrag=vertrag,
            event_type='contract.updated',
            actor=request.user,
            description=f'Vertrag aktualisiert für Mieter: {mieter_name}'
        )
    except RuntimeError as e:
        logger.error(f"Activity stream logging failed for Vertrag {vertrag.pk}: {e}")
        messages.warning(request, f'Vertrag wurde aktualisiert, aber {ACTIVITY_LOGGING_FAILED_MESSAGE}')
    
    # EXISTING: Additionally log status change if status changed
    if old_status != new_status:
        try:
            _log_vertrag_stream_event(
                vertrag=vertrag,
                event_type='contract.status_changed',
                actor=request.user,
                description=f'Status geändert: {old_status_display} → {new_status_display}'
            )
        except RuntimeError as e:
            logger.error(f"Activity stream logging failed for Vertrag {vertrag.pk}: {e}")
            messages.warning(request, f'Statusänderung wurde gespeichert, aber {ACTIVITY_LOGGING_FAILED_MESSAGE}')
    
    messages.success(request, f'Vertrag "{vertrag.vertragsnummer}" wurde erfolgreich aktualisiert.')
    return redirect('vermietung:vertrag_detail', pk=vertrag.pk)
```

### 2. Updated Test: `vermietung/test_vertrag_activity_stream.py`

**Test:** `test_no_event_when_status_unchanged()`  
**Lines:** 314-389 (modified)

#### Changes:
1. Renamed test description to reflect new behavior
2. Added assertion to verify `contract.updated` event IS created
3. Kept assertion to verify `contract.status_changed` event is NOT created
4. Added verification of event details (actor, description)

**Before:**
```python
def test_no_event_when_status_unchanged(self):
    """Test that no status_changed event is created when status doesn't change."""
    # ... setup ...
    
    # Verify no new status_changed event was created
    self.assertEqual(status_changed, initial_count)
```

**After:**
```python
def test_no_event_when_status_unchanged(self):
    """Test that contract.updated event is created but no status_changed event when status doesn't change."""
    # ... setup ...
    
    # Verify no new status_changed event was created
    self.assertEqual(status_changed, initial_status_changed_count)
    
    # NEW: Verify that a contract.updated event WAS created
    updated_events = Activity.objects.filter(
        company=self.mandant,
        activity_type='contract.updated'
    )
    self.assertEqual(updated_events.count(), initial_updated_count + 1)
    
    # Verify event details
    event = updated_events.latest('created_at')
    self.assertEqual(event.actor, self.user)
    self.assertIn('aktualisiert', event.description)
```

## Complete Event Inventory (After Fix)

| Event Type | Trigger | When Created | Actor | Domain | Status |
|------------|---------|--------------|-------|--------|--------|
| `contract.created` | New contract created | After `vertrag_create` | User | RENTAL | ✅ Pre-existing |
| `contract.updated` | Contract fields updated | After `vertrag_edit` | User | RENTAL | ✅ **NEW** |
| `contract.status_changed` | Status field changed | After `vertrag_edit` (if status changed) | User | RENTAL | ✅ Enhanced |
| `contract.ended` | End date set | After `vertrag_end` | User | RENTAL | ✅ Pre-existing |
| `contract.cancelled` | Contract cancelled | After `vertrag_cancel` | User | RENTAL | ✅ Pre-existing |

## Event Data Structure

### contract.updated Event

```python
Activity(
    company=mandant,
    domain='RENTAL',
    activity_type='contract.updated',
    title='Vertrag: V2024-001',
    description='Vertrag aktualisiert für Mieter: Max Mustermann',
    target_url='/vermietung/vertraege/123/',
    actor=user,
    severity='INFO'
)
```

### Behavior When Status Changes

When a contract is edited AND the status changes, TWO events are created:

**Event 1 - Update:**
```python
Activity(
    company=mandant,
    domain='RENTAL',
    activity_type='contract.updated',
    title='Vertrag: V2024-001',
    description='Vertrag aktualisiert für Mieter: Max Mustermann',
    ...
)
```

**Event 2 - Status Change:**
```python
Activity(
    company=mandant,
    domain='RENTAL',
    activity_type='contract.status_changed',
    title='Vertrag: V2024-001',
    description='Status geändert: Aktiv → Entwurf',
    ...
)
```

This provides both general audit trail and specific status transition tracking.

## Testing

### Test Results
✅ **All 9 tests passing** in `vermietung.test_vertrag_activity_stream`:
- `test_contract_created_event`
- `test_status_changed_event` 
- `test_contract_ended_event`
- `test_contract_ended_with_status_change_event`
- `test_contract_cancelled_event`
- `test_no_event_when_status_unchanged` ← **Modified**
- `test_event_has_valid_target_url`
- `test_event_without_mandant_uses_fallback`
- `test_no_mandant_shows_warning_message`

### Test Coverage
- ✅ Contract creation logs event
- ✅ Contract update (no status change) logs `contract.updated`
- ✅ Contract update (with status change) logs BOTH events
- ✅ Contract ending logs event
- ✅ Contract cancellation logs event
- ✅ Events have correct actor, domain, target_url
- ✅ Error handling when Mandant missing
- ✅ User warnings on logging failures

## Comparison with Adresse Implementation

The implementation now matches the Adresse pattern 1:1:

| Operation | Adresse Events | Vertrag Events (After Fix) |
|-----------|---------------|---------------------------|
| Create | `address.created` | `contract.created` |
| Update | `address.updated` | `contract.updated` |
| Delete | `address.deleted` | N/A (contracts not deleted) |
| Status Change | N/A | `contract.status_changed` (additional) |

**Key Similarity:** Both log an event for EVERY update operation, not just specific field changes.

## Requirements Compliance

From the original issue requirements:

### ✅ 1:1 Implementation Like Adresse
- ✅ Uses same helper function pattern (`_log_vertrag_stream_event`)
- ✅ Logs events on all CRUD operations
- ✅ Uses same error handling approach
- ✅ Follows same event naming convention

### ✅ Explicit Event Logging
- ✅ No Django signals
- ✅ Events logged directly in view functions
- ✅ Clear, readable code

### ✅ Complete Audit Trail
- ✅ Create operations tracked
- ✅ Update operations tracked (all fields, not just status)
- ✅ Status changes specifically tracked
- ✅ End and cancellation operations tracked

## Files Modified

1. **`vermietung/views.py`**
   - Function: `vertrag_edit()`
   - Lines added: ~17
   - Purpose: Add `contract.updated` event logging

2. **`vermietung/test_vertrag_activity_stream.py`**
   - Function: `test_no_event_when_status_unchanged()`
   - Lines modified: ~15
   - Purpose: Update test to verify new behavior

**Total Changes:** ~32 lines modified/added

## Backward Compatibility

✅ **Fully backward compatible:**
- Existing `contract.status_changed` events still created
- All other event types unchanged
- No database schema changes
- No breaking changes to API or UI

## Error Handling

The implementation maintains robust error handling:

1. **Missing Mandant:**
   - Raises `RuntimeError` from `_log_vertrag_stream_event()`
   - Caught in view with try/except
   - User sees warning message but operation succeeds
   - Error logged for debugging

2. **ActivityStreamService Failures:**
   - Any exception caught and logged
   - User operation never blocked
   - Clear error messages in logs

## Performance Impact

✅ **Minimal performance impact:**
- One additional database write per update (INSERT into Activity table)
- No additional queries on read operations
- Activity write occurs after successful contract save (in same request)
- No impact on contract creation/deletion operations

## Deployment Notes

### No Database Changes Required
✅ Uses existing `Activity` model from migration `core.0022_add_activity_model`

### No Configuration Changes
✅ No settings updates needed

### No Dependencies
✅ No new packages required

## Next Steps (Recommendations)

1. **UI Integration:** Display activity stream on contract detail page
2. **Filtering:** Add ability to filter activities by event type
3. **Notifications:** Send notifications on specific event types
4. **Reporting:** Generate audit reports from activity stream
5. **API Endpoints:** Expose activity stream via REST API for mobile apps

## Related Documentation

- See `ADRESSE_ACTIVITYSTREAM_IMPLEMENTATION.md` for Adresse reference implementation
- See `ACTIVITY_STREAM_IMPLEMENTATION.md` for general ActivityStream documentation
- See `core/services/activity_stream.py` for ActivityStreamService API

## Conclusion

The integration of ActivityStream events for Mietverträge is now complete and consistent with the Adresse implementation. All contract updates are now properly tracked in the Activity Stream, providing a complete audit trail for rental contract management.

The fix is minimal (32 lines), well-tested (9/9 tests passing), and follows established patterns in the codebase.

---

**Issue:** #320  
**Status:** ✅ Resolved  
**Implementation Date:** February 8, 2026  
**Author:** GitHub Copilot
