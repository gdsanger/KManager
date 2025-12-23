# Dokumente UI Implementation Summary

## Overview
This document describes the implementation of the document upload/download/delete UI for the Vermietung (rental management) module.

## Features Implemented

### 1. Document Upload
- **Location**: Available on detail pages for all entities (Vertrag, MietObjekt, Adresse, Übergabeprotokoll)
- **UI Component**: Bootstrap 5 modal dialog with file input and description field
- **Validation**: 
  - Server-side validation of file size (max 10 MB)
  - Server-side validation of file type (PDF, PNG, JPG/JPEG, GIF, DOCX)
  - MIME type detection using python-magic library
- **Storage**: Files stored in `/data/vermietung/<entity_type>/<entity_id>/` directory structure
- **Features**:
  - File input with accept attribute to filter file types
  - Optional description field
  - User-friendly error messages
  - Automatic redirection back to detail page after upload

### 2. Document Download
- **Location**: Download button in document tables on all entity detail pages
- **Security**: Auth-protected route requiring login
- **Features**:
  - Serves files through Django (not direct filesystem access)
  - Proper Content-Type headers based on stored MIME type
  - Original filename preservation for downloads

### 3. Document Delete
- **Location**: Delete button next to each document in tables
- **Permission**: Available to all authenticated users in Vermietung area
- **Features**:
  - JavaScript confirmation dialog before deletion
  - Automatic file cleanup from filesystem
  - Automatic cleanup of empty directories
  - Cascade deletion when parent entity is deleted
  - User-friendly success/error messages

## Technical Implementation

### Backend Components

#### 1. Forms (vermietung/forms.py)
```python
class DokumentUploadForm(forms.ModelForm):
    - Handles file upload
    - Validates file size and type
    - Associates document with entity
    - Stores uploaded_by user
```

#### 2. Views (vermietung/views.py)
```python
@vermietung_required
def dokument_upload(request, entity_type, entity_id):
    - Validates entity type and existence
    - Processes file upload
    - Handles validation errors
    - Returns to entity detail page

@vermietung_required
@require_http_methods(["POST"])
def dokument_delete(request, dokument_id):
    - Deletes document record
    - Removes file from filesystem
    - Returns to entity detail page
```

#### 3. URLs (vermietung/urls.py)
```python
path('dokument/<int:dokument_id>/loeschen/', views.dokument_delete, name='dokument_delete')
path('dokument/upload/<str:entity_type>/<int:entity_id>/', views.dokument_upload, name='dokument_upload')
```

### Frontend Components

#### 1. Upload Modal
Each entity detail page includes a Bootstrap modal:
- File input with accept filter
- Description textarea (optional)
- Form with multipart/form-data encoding
- Styled with Bootstrap 5 dark theme

#### 2. Document Table
Documents displayed in responsive tables with:
- Filename (with description preview)
- File size (formatted)
- Upload date and user
- Download button
- Delete button with confirmation

#### 3. JavaScript Functions
```javascript
function confirmDeleteDokument(dokumentId, filename) {
    // Shows confirmation dialog
    // Submits delete form on confirmation
}
```

## File Structure

### Directory Structure
```
/data/vermietung/
├── vertrag/
│   ├── 1/
│   │   ├── document1.pdf
│   │   └── document2.jpg
│   └── 2/
│       └── contract.pdf
├── mietobjekt/
│   └── 1/
│       └── floor_plan.png
├── adresse/
│   └── 1/
│       └── id_document.pdf
└── uebergabeprotokoll/
    └── 1/
        └── protocol.pdf
```

## Validation Rules

### File Size
- Maximum: 10 MB (10,485,760 bytes)
- Validated server-side in `validate_file_size()` function
- User-friendly error message showing actual size and limit

### File Types
Allowed MIME types and extensions:
- `application/pdf` → `.pdf`
- `image/png` → `.png`
- `image/jpeg` → `.jpg`, `.jpeg`
- `image/gif` → `.gif`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → `.docx`

Validation performed in `validate_file_type()` function:
1. Reads file content to detect actual MIME type (using python-magic)
2. Verifies extension matches detected MIME type
3. Prevents MIME type spoofing

## Security Features

1. **Authentication Required**: All document operations require login
2. **Permission Checks**: Uses `@vermietung_required` decorator
3. **File Type Validation**: Server-side MIME type detection
4. **File Size Limits**: Prevents large file uploads
5. **Path Sanitization**: Uses Path objects and proper validation
6. **No Direct File Access**: Files served through Django views
7. **CSRF Protection**: All POST forms include CSRF token

## User Experience

### Success Scenarios
- Upload: "Dokument 'filename.pdf' wurde erfolgreich hochgeladen."
- Delete: "Dokument 'filename.pdf' wurde erfolgreich gelöscht."
- Download: File downloaded with original filename

### Error Handling
- Invalid file type: Shows allowed types
- File too large: Shows actual size and limit
- Missing file: 404 error with user-friendly message
- Server errors: Generic error message with exception details

## Testing

### Automated Tests
- 161 tests passing in vermietung app
- Existing document model tests cover:
  - File validation (size, type)
  - Storage path generation
  - Cascade deletion
  - Entity association validation

### Manual Testing Checklist
- [✓] UI elements present in all templates
- [ ] Upload valid PDF file
- [ ] Upload valid image files (PNG, JPG, GIF)
- [ ] Upload valid DOCX file
- [ ] Upload file exceeding 10 MB (should fail)
- [ ] Upload invalid file type (should fail)
- [ ] Download uploaded document
- [ ] Delete document
- [ ] Verify file cleanup after deletion

## Templates Modified

1. `templates/vermietung/vertraege/detail.html`
   - Added upload modal
   - Added delete buttons
   - Added JavaScript for confirmation

2. `templates/vermietung/mietobjekte/detail.html`
   - Added upload modal
   - Added delete buttons
   - Added JavaScript for confirmation

3. `templates/vermietung/uebergabeprotokolle/detail.html`
   - Added upload modal
   - Added delete buttons
   - Added JavaScript for confirmation
   - Moved documents section out of conditional (always show with upload option)

4. `templates/vermietung/kunden/detail.html`
   - Added documents section
   - Added upload modal
   - Added delete buttons
   - Added JavaScript for confirmation

## Database Schema

No changes to database schema required - uses existing Dokument model from migration 0005_dokument.

## Acceptance Criteria Status

- [✓] Upload validiert Größe und Typ serverseitig
- [✓] Dokumente können heruntergeladen werden (auth-geschützt)
- [✓] Dokumente können im Userbereich gelöscht werden
- [✓] Dokumente erscheinen in den Detailseiten der jeweiligen Entität

## Future Enhancements (Out of Scope)

- Drag-and-drop file upload
- Multiple file upload at once
- File preview (PDF, images)
- Document versioning
- Document categories/tags
- Search/filter documents
- Bulk download as ZIP
- Admin-only delete restriction (currently all users can delete)
