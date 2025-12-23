from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from .models import Dokument
from core.models import Adresse
from .forms import AdresseKundeForm


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
    
    # Create response - FileResponse handles file opening/closing automatically
    response = FileResponse(
        file_path.open('rb'),
        content_type=dokument.mime_type,
        as_attachment=True,
        filename=dokument.original_filename  # FileResponse handles proper escaping
    )
    
    return response
from .permissions import vermietung_required


@vermietung_required
def vermietung_home(request):
    """Vermietung dashboard/home page - requires Vermietung access."""
    return render(request, 'vermietung/home.html')


@vermietung_required
def vermietung_components(request):
    """UI Components reference page for developers."""
    return render(request, 'vermietung/components.html')


# Customer (Kunde) CRUD Views

@vermietung_required
def kunde_list(request):
    """
    List all customers (Adressen of type KUNDE) with search and pagination.
    """
    # Get search query
    search_query = request.GET.get('q', '').strip()
    
    # Base queryset: only KUNDE addresses
    kunden = Adresse.objects.filter(adressen_type='KUNDE')
    
    # Apply search filter if query provided
    if search_query:
        kunden = kunden.filter(
            Q(name__icontains=search_query) |
            Q(firma__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(strasse__icontains=search_query) |
            Q(ort__icontains=search_query) |
            Q(plz__icontains=search_query)
        )
    
    # Order by name
    kunden = kunden.order_by('name')
    
    # Pagination
    paginator = Paginator(kunden, 20)  # Show 20 customers per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'vermietung/kunden/list.html', context)


@vermietung_required
def kunde_detail(request, pk):
    """
    Show details of a specific customer.
    """
    kunde = get_object_or_404(Adresse, pk=pk, adressen_type='KUNDE')
    
    context = {
        'kunde': kunde,
    }
    
    return render(request, 'vermietung/kunden/detail.html', context)


@vermietung_required
def kunde_create(request):
    """
    Create a new customer.
    """
    if request.method == 'POST':
        form = AdresseKundeForm(request.POST)
        if form.is_valid():
            kunde = form.save()
            messages.success(request, f'Kunde "{kunde.full_name()}" wurde erfolgreich angelegt.')
            return redirect('vermietung:kunde_detail', pk=kunde.pk)
    else:
        form = AdresseKundeForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/kunden/form.html', context)


@vermietung_required
def kunde_edit(request, pk):
    """
    Edit an existing customer.
    """
    kunde = get_object_or_404(Adresse, pk=pk, adressen_type='KUNDE')
    
    if request.method == 'POST':
        form = AdresseKundeForm(request.POST, instance=kunde)
        if form.is_valid():
            kunde = form.save()
            messages.success(request, f'Kunde "{kunde.full_name()}" wurde erfolgreich aktualisiert.')
            return redirect('vermietung:kunde_detail', pk=kunde.pk)
    else:
        form = AdresseKundeForm(instance=kunde)
    
    context = {
        'form': form,
        'kunde': kunde,
        'is_create': False,
    }
    
    return render(request, 'vermietung/kunden/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def kunde_delete(request, pk):
    """
    Delete a customer.
    Only available in user area (not admin-only).
    """
    kunde = get_object_or_404(Adresse, pk=pk, adressen_type='KUNDE')
    kunde_name = kunde.full_name()
    
    try:
        kunde.delete()
        messages.success(request, f'Kunde "{kunde_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Kunden: {str(e)}')
    
    return redirect('vermietung:kunde_list')

