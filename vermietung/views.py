from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from .models import Dokument
import mimetypes


@login_required
def download_dokument(request, dokument_id):
    """
    Auth-protected view to download a document.
    
    Only authenticated users can download documents.
    The file is served through Django, not directly via nginx.
    
    Args:
        request: HTTP request
        dokument_id: ID of the document to download
    
    Returns:
        FileResponse with the document file
    
    Raises:
        Http404: If document not found or file doesn't exist
    """
    # Get document from database
    dokument = get_object_or_404(Dokument, pk=dokument_id)
    
    # Get absolute file path
    file_path = dokument.get_absolute_path()
    
    # Check if file exists
    if not file_path.exists():
        raise Http404("Datei wurde nicht gefunden im Filesystem.")
    
    # Create response with file path (FileResponse handles opening/closing)
    response = FileResponse(open(file_path, 'rb'), content_type=dokument.mime_type)
    
    # Set content disposition to trigger download with properly escaped filename
    # Use ASCII-safe filename in Content-Disposition header
    safe_filename = dokument.original_filename.encode('ascii', 'ignore').decode('ascii')
    if not safe_filename:
        safe_filename = 'document'
    response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
    response['Content-Length'] = dokument.file_size
    
    return response

