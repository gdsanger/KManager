# Aktivitaet Attachment Upload Fix

## Issue Summary
Fixed three issues with file attachment uploads for Aktivitäten (Activities):

1. **File upload redirecting incorrectly** - Files not being uploaded, page redirecting to wrong location
2. **Upload not available during Create mode** - Users couldn't upload files when creating new activities  
3. **No drag-and-drop support** - Users had to use traditional file browser

## Root Cause
The attachment upload form was **nested inside** the main aktivitaet form, which is invalid HTML. Browsers behave unpredictably with nested forms, often submitting the outer form instead of the inner form.

### Before (Invalid HTML):
```html
<form method="post" novalidate>  <!-- Main form starts -->
    <!-- Activity fields -->
    
    <form method="post" enctype="multipart/form-data" action="upload_url">  <!-- NESTED FORM! -->
        <input type="file" name="attachments" multiple>
        <button type="submit">Upload</button>
    </form>
    
    <button type="submit">Save Activity</button>
</form>  <!-- Main form ends -->
```

### After (Valid HTML):
```html
<form method="post" novalidate>  <!-- Main form -->
    <!-- Activity fields -->
    <button type="submit">Save Activity</button>
</form>  <!-- Main form ends -->

<!-- Attachment form is now separate -->
<form method="post" enctype="multipart/form-data" action="upload_url">
    <div class="file-drop-area">
        <input type="file" name="attachments" multiple>
        <!-- Drag-and-drop zone -->
    </div>
    <button type="submit">Upload</button>
</form>
```

## Changes Made

### 1. Template Structure (`templates/vermietung/aktivitaeten/form.html`)
- **Moved attachment upload form outside main form** (after line 397)
- Form is now only visible in edit mode (`{% if not is_create %}`)
- Upload form posts to `aktivitaet_attachment_upload` view
- Main form posts to `aktivitaet_edit` view

### 2. Drag-and-Drop Implementation
Added JavaScript functionality:
- Visual drop zone with hover effects
- File preview before upload (shows filename and size)
- Drag-and-drop event handlers
- File size formatting
- Visual feedback when dragging files over the drop zone

CSS enhancements:
- Styled drop zone with dashed border
- Hover/active states with color changes
- Smooth transitions
- Responsive design

### 3. Create Workflow Enhancement (`vermietung/views.py`)
Changed redirect after creating an aktivitaet:
- **Before**: Redirected to kanban view (no way to upload attachments)
- **After**: Redirects to edit page (allows immediate attachment upload)

```python
# Old code
return redirect('vermietung:aktivitaet_kanban')

# New code  
return redirect('vermietung:aktivitaet_edit', pk=aktivitaet.pk)
```

## User Experience Improvements

### Before:
1. Create activity → redirected to kanban view
2. Find activity in kanban
3. Click to edit
4. Click upload button → nothing happens (nested form issue)

### After:
1. Create activity → redirected to edit page automatically
2. Drag-and-drop files or click to browse
3. See file preview before upload
4. Click upload → files are uploaded successfully
5. Stay on edit page to upload more files if needed

## Testing
All existing tests pass:
- ✓ 19 attachment upload tests
- ✓ 6 form validation tests

## Technical Details

### Upload Flow:
1. User is on aktivitaet edit page (`/vermietung/aktivitaeten/<id>/bearbeiten/`)
2. Drags files onto drop zone or clicks to browse
3. Files are previewed in a list (name + size)
4. Clicks "Hochladen" button
5. Form submits to `/vermietung/aktivitaeten/<id>/anhaenge/hochladen/`
6. View validates and saves files
7. Redirects back to edit page with success message

### File Upload Restrictions:
- Maximum file size: 5 MB per file
- Blocked file types: executable files (.exe, .bat, .js, etc.)
- Supports multiple file upload
- Files stored in: `/data/vermietung/aktivitaet/<id>/attachments/`

## Browser Compatibility
The drag-and-drop functionality uses standard HTML5 APIs:
- `dragenter`, `dragover`, `dragleave`, `drop` events
- `DataTransfer` API for file handling
- Works in all modern browsers (Chrome, Firefox, Safari, Edge)

## Security
- All file uploads are validated server-side
- File type validation prevents malicious files
- File size limits prevent DoS attacks
- Files served through authenticated views only
- No changes to security model
