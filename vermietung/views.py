from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from datetime import timedelta
from .models import Dokument, MietObjekt, Vertrag, Uebergabeprotokoll, OBJEKT_TYPE
from core.models import Adresse
from .forms import AdresseKundeForm, MietObjektForm, VertragForm, VertragEndForm, UebergabeprotokollForm, DokumentUploadForm
from .permissions import vermietung_required


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


@vermietung_required
def vermietung_home(request):
    """Vermietung dashboard/home page - requires Vermietung access."""
    # Calculate KPIs
    total_mietobjekte = MietObjekt.objects.count()
    verfuegbare_mietobjekte = MietObjekt.objects.filter(verfuegbar=True).count()
    active_vertraege = Vertrag.objects.currently_active().count()
    total_kunden = Adresse.objects.filter(adressen_type='KUNDE').count()
    
    # Get recently created contracts (last 10)
    recent_vertraege = Vertrag.objects.select_related('mietobjekt', 'mieter').order_by('-id')[:10]
    
    # Get contracts expiring soon (within next 60 days, excluding those without end date)
    today = timezone.now().date()
    expiring_soon_date = today + timedelta(days=60)
    expiring_vertraege = Vertrag.objects.select_related('mietobjekt', 'mieter').filter(
        status='active',
        ende__isnull=False,
        ende__gte=today,
        ende__lte=expiring_soon_date
    ).order_by('ende')[:10]
    
    context = {
        'total_mietobjekte': total_mietobjekte,
        'verfuegbare_mietobjekte': verfuegbare_mietobjekte,
        'active_vertraege': active_vertraege,
        'total_kunden': total_kunden,
        'recent_vertraege': recent_vertraege,
        'expiring_vertraege': expiring_vertraege,
    }
    
    return render(request, 'vermietung/home.html', context)


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
    
    # Get related documents with pagination
    dokumente = kunde.dokumente.select_related('uploaded_by').order_by('-uploaded_at')
    dokumente_paginator = Paginator(dokumente, 10)
    dokumente_page = request.GET.get('dokumente_page', 1)
    dokumente_page_obj = dokumente_paginator.get_page(dokumente_page)
    
    context = {
        'kunde': kunde,
        'dokumente_page_obj': dokumente_page_obj,
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


# MietObjekt (Rental Object) CRUD Views

@vermietung_required
def mietobjekt_list(request):
    """
    List all MietObjekt with search, filtering and pagination.
    Supports filtering by type, availability, and location.
    """
    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '')
    verfuegbar_filter = request.GET.get('verfuegbar', '')
    standort_filter = request.GET.get('standort', '')
    
    # Base queryset with related data
    mietobjekte = MietObjekt.objects.select_related('standort').all()
    
    # Apply search filter
    if search_query:
        mietobjekte = mietobjekte.filter(
            Q(name__icontains=search_query) |
            Q(beschreibung__icontains=search_query) |
            Q(standort__ort__icontains=search_query) |
            Q(standort__strasse__icontains=search_query)
        )
    
    # Apply type filter
    if type_filter:
        mietobjekte = mietobjekte.filter(type=type_filter)
    
    # Apply availability filter
    if verfuegbar_filter:
        if verfuegbar_filter == 'true':
            mietobjekte = mietobjekte.filter(verfuegbar=True)
        elif verfuegbar_filter == 'false':
            mietobjekte = mietobjekte.filter(verfuegbar=False)
    
    # Apply location filter
    if standort_filter:
        mietobjekte = mietobjekte.filter(standort_id=standort_filter)
    
    # Order by name
    mietobjekte = mietobjekte.order_by('name')
    
    # Pagination
    paginator = Paginator(mietobjekte, 20)  # Show 20 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all standorte for filter dropdown only if needed
    # Always fetch for display consistency
    standorte = Adresse.objects.filter(adressen_type='STANDORT').order_by('name')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'type_filter': type_filter,
        'verfuegbar_filter': verfuegbar_filter,
        'standort_filter': standort_filter,
        'standorte': standorte,
        'objekt_types': OBJEKT_TYPE,
    }
    
    return render(request, 'vermietung/mietobjekte/list.html', context)


@vermietung_required
def mietobjekt_detail(request, pk):
    """
    Show details of a specific MietObjekt with related data.
    Shows contracts, handover protocols, and documents in tabs with pagination.
    """
    mietobjekt = get_object_or_404(MietObjekt.objects.select_related('standort'), pk=pk)
    
    # Get related contracts with pagination
    vertraege = mietobjekt.vertraege.select_related('mieter').order_by('-start')
    vertraege_paginator = Paginator(vertraege, 10)
    vertraege_page = request.GET.get('vertraege_page', 1)
    vertraege_page_obj = vertraege_paginator.get_page(vertraege_page)
    
    # Get related handover protocols with pagination
    uebergaben = mietobjekt.uebergabeprotokolle.select_related('vertrag').order_by('-uebergabetag')
    uebergaben_paginator = Paginator(uebergaben, 10)
    uebergaben_page = request.GET.get('uebergaben_page', 1)
    uebergaben_page_obj = uebergaben_paginator.get_page(uebergaben_page)
    
    # Get related documents with pagination
    dokumente = mietobjekt.dokumente.select_related('uploaded_by').order_by('-uploaded_at')
    dokumente_paginator = Paginator(dokumente, 10)
    dokumente_page = request.GET.get('dokumente_page', 1)
    dokumente_page_obj = dokumente_paginator.get_page(dokumente_page)
    
    context = {
        'mietobjekt': mietobjekt,
        'vertraege_page_obj': vertraege_page_obj,
        'uebergaben_page_obj': uebergaben_page_obj,
        'dokumente_page_obj': dokumente_page_obj,
    }
    
    return render(request, 'vermietung/mietobjekte/detail.html', context)


@vermietung_required
def mietobjekt_create(request):
    """
    Create a new MietObjekt.
    """
    if request.method == 'POST':
        form = MietObjektForm(request.POST)
        if form.is_valid():
            mietobjekt = form.save()
            messages.success(request, f'Mietobjekt "{mietobjekt.name}" wurde erfolgreich angelegt.')
            return redirect('vermietung:mietobjekt_detail', pk=mietobjekt.pk)
    else:
        form = MietObjektForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/mietobjekte/form.html', context)


@vermietung_required
def mietobjekt_edit(request, pk):
    """
    Edit an existing MietObjekt.
    """
    mietobjekt = get_object_or_404(MietObjekt, pk=pk)
    
    if request.method == 'POST':
        form = MietObjektForm(request.POST, instance=mietobjekt)
        if form.is_valid():
            mietobjekt = form.save()
            messages.success(request, f'Mietobjekt "{mietobjekt.name}" wurde erfolgreich aktualisiert.')
            return redirect('vermietung:mietobjekt_detail', pk=mietobjekt.pk)
    else:
        form = MietObjektForm(instance=mietobjekt)
    
    context = {
        'form': form,
        'mietobjekt': mietobjekt,
        'is_create': False,
    }
    
    return render(request, 'vermietung/mietobjekte/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def mietobjekt_delete(request, pk):
    """
    Delete a MietObjekt.
    Only available if no active contracts exist.
    """
    mietobjekt = get_object_or_404(MietObjekt, pk=pk)
    mietobjekt_name = mietobjekt.name
    
    # Check if there are any active contracts
    if mietobjekt.vertraege.currently_active().exists():
        messages.error(request, f'Mietobjekt "{mietobjekt_name}" kann nicht gelöscht werden, da es aktive Verträge hat.')
        return redirect('vermietung:mietobjekt_detail', pk=pk)
    
    try:
        mietobjekt.delete()
        messages.success(request, f'Mietobjekt "{mietobjekt_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Mietobjekts: {str(e)}')
        return redirect('vermietung:mietobjekt_detail', pk=pk)
    
    return redirect('vermietung:mietobjekt_list')


# Vertrag (Contract) CRUD Views

@vermietung_required
def vertrag_list(request):
    """
    List all contracts (Verträge) with search and pagination.
    """
    # Get search query
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    
    # Base queryset with related data
    vertraege = Vertrag.objects.select_related('mietobjekt', 'mieter').all()
    
    # Apply search filter
    if search_query:
        vertraege = vertraege.filter(
            Q(vertragsnummer__icontains=search_query) |
            Q(mieter__name__icontains=search_query) |
            Q(mieter__firma__icontains=search_query) |
            Q(mietobjekt__name__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        vertraege = vertraege.filter(status=status_filter)
    
    # Order by start date (newest first)
    vertraege = vertraege.order_by('-start')
    
    # Pagination
    paginator = Paginator(vertraege, 20)  # Show 20 contracts per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'vermietung/vertraege/list.html', context)


@vermietung_required
def vertrag_detail(request, pk):
    """
    Show details of a specific contract.
    """
    vertrag = get_object_or_404(
        Vertrag.objects.select_related('mietobjekt', 'mieter'),
        pk=pk
    )
    
    # Get related handover protocols with pagination
    uebergaben = vertrag.uebergabeprotokolle.select_related('mietobjekt').order_by('-uebergabetag')
    uebergaben_paginator = Paginator(uebergaben, 10)
    uebergaben_page = request.GET.get('uebergaben_page', 1)
    uebergaben_page_obj = uebergaben_paginator.get_page(uebergaben_page)
    
    # Get related documents with pagination
    dokumente = vertrag.dokumente.select_related('uploaded_by').order_by('-uploaded_at')
    dokumente_paginator = Paginator(dokumente, 10)
    dokumente_page = request.GET.get('dokumente_page', 1)
    dokumente_page_obj = dokumente_paginator.get_page(dokumente_page)
    
    context = {
        'vertrag': vertrag,
        'uebergaben_page_obj': uebergaben_page_obj,
        'dokumente_page_obj': dokumente_page_obj,
    }
    
    return render(request, 'vermietung/vertraege/detail.html', context)


@vermietung_required
def vertrag_create(request):
    """
    Create a new contract.
    """
    if request.method == 'POST':
        form = VertragForm(request.POST)
        if form.is_valid():
            try:
                vertrag = form.save()
                messages.success(
                    request,
                    f'Vertrag "{vertrag.vertragsnummer}" wurde erfolgreich angelegt.'
                )
                return redirect('vermietung:vertrag_detail', pk=vertrag.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        form = VertragForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/vertraege/form.html', context)


@vermietung_required
def vertrag_edit(request, pk):
    """
    Edit an existing contract.
    Only editable fields can be modified.
    """
    vertrag = get_object_or_404(Vertrag, pk=pk)
    
    if request.method == 'POST':
        form = VertragForm(request.POST, instance=vertrag)
        if form.is_valid():
            try:
                vertrag = form.save()
                messages.success(
                    request,
                    f'Vertrag "{vertrag.vertragsnummer}" wurde erfolgreich aktualisiert.'
                )
                return redirect('vermietung:vertrag_detail', pk=vertrag.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        form = VertragForm(instance=vertrag)
    
    context = {
        'form': form,
        'vertrag': vertrag,
        'is_create': False,
    }
    
    return render(request, 'vermietung/vertraege/form.html', context)


@vermietung_required
def vertrag_end(request, pk):
    """
    End a contract by setting the end date.
    This sets the 'ende' field and updates the rental object availability.
    """
    vertrag = get_object_or_404(Vertrag, pk=pk)
    
    # Check if contract can be ended
    if vertrag.status == 'cancelled':
        messages.error(request, 'Ein stornierter Vertrag kann nicht beendet werden.')
        return redirect('vermietung:vertrag_detail', pk=pk)
    
    if vertrag.ende:
        messages.warning(
            request,
            f'Dieser Vertrag hat bereits ein Enddatum: {vertrag.ende}'
        )
    
    if request.method == 'POST':
        form = VertragEndForm(request.POST, vertrag=vertrag)
        if form.is_valid():
            try:
                vertrag.ende = form.cleaned_data['ende']
                # If end date is in the past or today, set status to 'ended'
                if vertrag.ende <= timezone.now().date():
                    vertrag.status = 'ended'
                vertrag.save()
                messages.success(
                    request,
                    f'Vertrag "{vertrag.vertragsnummer}" wurde auf den {vertrag.ende} beendet.'
                )
                return redirect('vermietung:vertrag_detail', pk=vertrag.pk)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = VertragEndForm(vertrag=vertrag)
    
    context = {
        'form': form,
        'vertrag': vertrag,
    }
    
    return render(request, 'vermietung/vertraege/end.html', context)


@vermietung_required
@require_http_methods(["POST"])
def vertrag_cancel(request, pk):
    """
    Cancel a contract by changing status to 'cancelled'.
    This updates the rental object availability.
    """
    vertrag = get_object_or_404(Vertrag, pk=pk)
    
    # Check if contract can be cancelled
    if vertrag.status == 'cancelled':
        messages.warning(request, 'Dieser Vertrag ist bereits storniert.')
        return redirect('vermietung:vertrag_detail', pk=pk)
    
    if vertrag.status == 'ended':
        messages.error(request, 'Ein beendeter Vertrag kann nicht storniert werden.')
        return redirect('vermietung:vertrag_detail', pk=pk)
    
    try:
        vertrag.status = 'cancelled'
        vertrag.save()
        messages.success(
            request,
            f'Vertrag "{vertrag.vertragsnummer}" wurde storniert.'
        )
    except Exception as e:
        messages.error(request, f'Fehler beim Stornieren des Vertrags: {str(e)}')
    
    return redirect('vermietung:vertrag_detail', pk=pk)


# Uebergabeprotokoll (Handover Protocol) CRUD Views

@vermietung_required
def uebergabeprotokoll_list(request):
    """
    List all handover protocols (Übergabeprotokolle) with search and pagination.
    """
    # Get search query and filter parameters
    search_query = request.GET.get('q', '').strip()
    typ_filter = request.GET.get('typ', '')
    
    # Base queryset with related data
    protokolle = Uebergabeprotokoll.objects.select_related(
        'vertrag', 'mietobjekt', 'vertrag__mieter'
    ).all()
    
    # Apply search filter
    if search_query:
        protokolle = protokolle.filter(
            Q(vertrag__vertragsnummer__icontains=search_query) |
            Q(mietobjekt__name__icontains=search_query) |
            Q(vertrag__mieter__name__icontains=search_query) |
            Q(person_vermieter__icontains=search_query) |
            Q(person_mieter__icontains=search_query)
        )
    
    # Apply typ filter
    if typ_filter:
        protokolle = protokolle.filter(typ=typ_filter)
    
    # Order by uebergabetag (newest first)
    protokolle = protokolle.order_by('-uebergabetag')
    
    # Pagination
    paginator = Paginator(protokolle, 20)  # Show 20 protocols per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'typ_filter': typ_filter,
    }
    
    return render(request, 'vermietung/uebergabeprotokolle/list.html', context)


@vermietung_required
def uebergabeprotokoll_detail(request, pk):
    """
    Show details of a specific handover protocol.
    """
    protokoll = get_object_or_404(
        Uebergabeprotokoll.objects.select_related('vertrag', 'mietobjekt', 'vertrag__mieter'),
        pk=pk
    )
    
    # Get related documents with pagination
    dokumente = protokoll.dokumente.select_related('uploaded_by').order_by('-uploaded_at')
    dokumente_paginator = Paginator(dokumente, 10)
    dokumente_page = request.GET.get('dokumente_page', 1)
    dokumente_page_obj = dokumente_paginator.get_page(dokumente_page)
    
    context = {
        'protokoll': protokoll,
        'dokumente_page_obj': dokumente_page_obj,
    }
    
    return render(request, 'vermietung/uebergabeprotokolle/detail.html', context)


@vermietung_required
def uebergabeprotokoll_create(request):
    """
    Create a new handover protocol (standalone).
    """
    if request.method == 'POST':
        form = UebergabeprotokollForm(request.POST)
        if form.is_valid():
            try:
                protokoll = form.save()
                messages.success(
                    request,
                    f'Übergabeprotokoll wurde erfolgreich angelegt.'
                )
                return redirect('vermietung:uebergabeprotokoll_detail', pk=protokoll.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        form = UebergabeprotokollForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/uebergabeprotokolle/form.html', context)


@vermietung_required
def uebergabeprotokoll_create_from_vertrag(request, vertrag_pk):
    """
    Create a new handover protocol from a contract (guided flow).
    Pre-fills vertrag and mietobjekt fields.
    """
    vertrag = get_object_or_404(Vertrag.objects.select_related('mietobjekt'), pk=vertrag_pk)
    
    if request.method == 'POST':
        form = UebergabeprotokollForm(request.POST, vertrag=vertrag)
        if form.is_valid():
            try:
                protokoll = form.save()
                messages.success(
                    request,
                    f'Übergabeprotokoll wurde erfolgreich angelegt.'
                )
                return redirect('vermietung:uebergabeprotokoll_detail', pk=protokoll.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        # Pre-fill form with vertrag data
        form = UebergabeprotokollForm(
            vertrag=vertrag,
            initial={
                'uebergabetag': timezone.now().date(),
            }
        )
    
    context = {
        'form': form,
        'vertrag': vertrag,
        'is_create': True,
        'from_vertrag': True,
    }
    
    return render(request, 'vermietung/uebergabeprotokolle/form.html', context)


@vermietung_required
def uebergabeprotokoll_edit(request, pk):
    """
    Edit an existing handover protocol.
    """
    protokoll = get_object_or_404(Uebergabeprotokoll, pk=pk)
    
    if request.method == 'POST':
        form = UebergabeprotokollForm(request.POST, instance=protokoll)
        if form.is_valid():
            try:
                protokoll = form.save()
                messages.success(
                    request,
                    f'Übergabeprotokoll wurde erfolgreich aktualisiert.'
                )
                return redirect('vermietung:uebergabeprotokoll_detail', pk=protokoll.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        form = UebergabeprotokollForm(instance=protokoll)
    
    context = {
        'form': form,
        'protokoll': protokoll,
        'is_create': False,
    }
    
    return render(request, 'vermietung/uebergabeprotokolle/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def uebergabeprotokoll_delete(request, pk):
    """
    Delete a handover protocol.
    """
    protokoll = get_object_or_404(Uebergabeprotokoll, pk=pk)
    protokoll_info = str(protokoll)
    
    try:
        protokoll.delete()
        messages.success(request, f'Übergabeprotokoll "{protokoll_info}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Übergabeprotokolls: {str(e)}')
        return redirect('vermietung:uebergabeprotokoll_detail', pk=pk)
    
    return redirect('vermietung:uebergabeprotokoll_list')


# Document Upload/Delete Views

@vermietung_required
def dokument_upload(request, entity_type, entity_id):
    """
    Upload a document for a specific entity.
    
    Args:
        request: HTTP request
        entity_type: Type of entity (vertrag, mietobjekt, adresse, uebergabeprotokoll)
        entity_id: ID of the entity
    
    Returns:
        Redirects back to entity detail page with success/error message
    """
    # Validate entity type
    valid_entity_types = ['vertrag', 'mietobjekt', 'adresse', 'uebergabeprotokoll']
    if entity_type not in valid_entity_types:
        messages.error(request, f'Ungültiger Entity-Typ: {entity_type}')
        return redirect('vermietung:home')
    
    # Get the entity to ensure it exists
    entity = None
    entity_name = ''
    redirect_url = ''
    
    if entity_type == 'vertrag':
        entity = get_object_or_404(Vertrag, pk=entity_id)
        entity_name = f'Vertrag {entity.vertragsnummer}'
        redirect_url = 'vermietung:vertrag_detail'
    elif entity_type == 'mietobjekt':
        entity = get_object_or_404(MietObjekt, pk=entity_id)
        entity_name = f'Mietobjekt {entity.name}'
        redirect_url = 'vermietung:mietobjekt_detail'
    elif entity_type == 'adresse':
        entity = get_object_or_404(Adresse, pk=entity_id)
        entity_name = f'Adresse {entity.full_name()}'
        redirect_url = 'vermietung:kunde_detail'
    elif entity_type == 'uebergabeprotokoll':
        entity = get_object_or_404(Uebergabeprotokoll, pk=entity_id)
        entity_name = f'Übergabeprotokoll {entity}'
        redirect_url = 'vermietung:uebergabeprotokoll_detail'
    
    if request.method == 'POST':
        form = DokumentUploadForm(
            request.POST,
            request.FILES,
            entity_type=entity_type,
            entity_id=entity_id,
            user=request.user
        )
        
        if form.is_valid():
            try:
                dokument = form.save()
                messages.success(
                    request,
                    f'Dokument "{dokument.original_filename}" wurde erfolgreich hochgeladen.'
                )
                return redirect(redirect_url, pk=entity_id)
            except ValidationError as e:
                # Handle validation errors from file validators with user-friendly messages
                error_message = str(e)
                if isinstance(e.message, str):
                    error_message = e.message
                elif isinstance(e.messages, list) and e.messages:
                    error_message = '; '.join(e.messages)
                messages.error(request, f'Fehler beim Hochladen: {error_message}')
            except Exception as e:
                messages.error(request, f'Fehler beim Hochladen: {str(e)}')
        else:
            # Display form errors with translated field names
            for field, errors in form.errors.items():
                field_label = form.fields.get(field).label if field in form.fields else field
                for error in errors:
                    messages.error(request, f'{field_label}: {error}')
    
    # Redirect back to detail page (GET or failed POST)
    return redirect(redirect_url, pk=entity_id)


@vermietung_required
@require_http_methods(["POST"])
def dokument_delete(request, dokument_id):
    """
    Delete a document.
    Available to all authenticated users in vermietung area.
    
    Args:
        request: HTTP request
        dokument_id: ID of the document to delete
    
    Returns:
        Redirects back to entity detail page with success/error message
    """
    dokument = get_object_or_404(Dokument, pk=dokument_id)
    
    # Determine redirect URL based on entity type
    entity_type = dokument.get_entity_type()
    entity_id = dokument.get_entity_id()
    
    redirect_url = 'vermietung:home'
    if entity_type == 'vertrag':
        redirect_url = 'vermietung:vertrag_detail'
    elif entity_type == 'mietobjekt':
        redirect_url = 'vermietung:mietobjekt_detail'
    elif entity_type == 'adresse':
        redirect_url = 'vermietung:kunde_detail'
    elif entity_type == 'uebergabeprotokoll':
        redirect_url = 'vermietung:uebergabeprotokoll_detail'
    
    dokument_name = dokument.original_filename
    
    try:
        dokument.delete()
        messages.success(request, f'Dokument "{dokument_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Dokuments: {str(e)}')
    
    return redirect(redirect_url, pk=entity_id)


