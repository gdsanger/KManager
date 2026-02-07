# Article Creation Feature Implementation

## Overview

This document describes the implementation of the "Artikelneuanlage in Artikelverwaltung" (New Article Creation in Article Management) feature. This feature allows users to create new articles directly from the article management interface with optional product group preselection.

## Feature Description

The feature adds a "Neuer Artikel" (New Article) button to the article management page that opens a modal dialog for creating new articles. When accessed via URL with a group parameter (`/items/?group=<id>`), the modal automatically preselects the specified product group.

## Implementation Details

### Files Modified

1. **core/views.py**
   - Added `item_new_ajax` view function
   - Handles loading of new item creation form via AJAX
   - Supports optional group preselection via `?group=<id>` parameter

2. **core/urls.py**
   - Added URL route: `path('items/new-ajax/', views.item_new_ajax, name='item_new_ajax')`

3. **templates/core/item_management.html**
   - Added "Neuer Artikel" button to the page header
   - Enhanced JavaScript to handle new item creation
   - Added `loadNewItemInModal()` function
   - Dynamic modal title based on create vs. edit mode

4. **core/test_item_new_ajax.py** (new file)
   - Comprehensive test coverage for the new feature
   - Tests for group preselection, invalid group handling, and authentication

### Code Changes

#### New View Function (`item_new_ajax`)

```python
@login_required
def item_new_ajax(request):
    """
    Load item creation form for AJAX modal.
    Supports preselecting item_group via ?group=<id> parameter.
    Returns HTML partial for the modal body.
    """
    # Get group parameter for preselection
    group_id = request.GET.get('group', '')
    initial_data = {}
    
    if group_id:
        try:
            group = ItemGroup.objects.get(pk=group_id)
            initial_data['item_group'] = group
        except (ItemGroup.DoesNotExist, ValueError):
            pass
    
    form = ItemForm(initial=initial_data)
    
    return render(request, 'core/item_edit_form.html', {
        'form': form,
        'item': None,
    })
```

#### JavaScript Enhancement

Added event handler for the "New Article" button:

```javascript
document.getElementById('createNewItemBtn').addEventListener('click', function() {
    loadNewItemInModal();
});

function loadNewItemInModal() {
    currentItemId = null;
    formDirty = false;
    
    // Update modal title
    document.getElementById('itemEditModalLabel').innerHTML = 
        '<i class="bi bi-plus-circle"></i> Neuer Artikel';
    
    // Get current group filter from URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const groupId = urlParams.get('group');
    
    // Build URL with group parameter if present
    let url = '/items/new-ajax/';
    if (groupId) {
        url += `?group=${groupId}`;
    }
    
    // Load new item form via AJAX
    fetch(url)
        .then(response => response.text())
        .then(html => {
            document.getElementById('itemModalBody').innerHTML = html;
            attachFormHandlers();
        });
}
```

## Usage

### Basic Usage

1. Navigate to the article management page: `/items/`
2. Click the "Neuer Artikel" button in the page header
3. Fill in the article details in the modal dialog
4. Click "Speichern" to create the article

### With Product Group Preselection

1. Navigate to a specific product group: `/items/?group=<group_id>`
2. Click the "Neuer Artikel" button
3. The item group field will be automatically pre-selected
4. Fill in the remaining article details
5. Click "Speichern" to create the article

## Testing

### Automated Tests

The feature includes comprehensive automated tests in `core/test_item_new_ajax.py`:

- ✅ `test_item_new_ajax_without_group` - Verify form loads without group preselection
- ✅ `test_item_new_ajax_with_group` - Verify group preselection works correctly
- ✅ `test_item_new_ajax_with_invalid_group` - Verify graceful handling of invalid group IDs
- ✅ `test_item_new_ajax_requires_authentication` - Verify authentication is enforced

All tests pass successfully.

### Running Tests

```bash
python manage.py test core.test_item_new_ajax --settings=test_settings
```

## Security

### Security Measures

1. **Authentication**: The view is protected with `@login_required` decorator
2. **Input Validation**: Group ID is validated before use
3. **Form Validation**: Django's built-in form validation handles all input
4. **CSRF Protection**: Standard Django CSRF protection is in place

### Security Review

- ✅ Code review completed - no issues found
- ✅ CodeQL security scan completed - no vulnerabilities detected

## Integration

The feature integrates seamlessly with existing functionality:

- Reuses the existing `ItemForm` for form rendering
- Reuses the existing `item_edit_form.html` template
- Reuses the existing `item_save_ajax` view for saving
- Maintains the same modal UI as the edit functionality
- Compatible with existing filters and table views

## Benefits

1. **Improved User Experience**: Users can create articles without leaving the management page
2. **Workflow Optimization**: Group preselection saves time when creating multiple articles in the same group
3. **Consistency**: Same modal UI for both create and edit operations
4. **Minimal Code Changes**: Leverages existing components and templates

## Future Enhancements

Potential improvements for future iterations:

1. Add keyboard shortcuts for opening the new article modal (e.g., Ctrl+N)
2. Add validation to suggest similar article numbers if duplicates exist
3. Add quick create buttons directly in the group tree
4. Support bulk article creation from CSV/Excel

## Changelog

### Version 1.0 (2026-02-07)

- Initial implementation of new article creation feature
- Added support for product group preselection via URL parameter
- Added comprehensive test coverage
- Security review and vulnerability scan completed
