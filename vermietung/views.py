from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404, FileResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from datetime import timedelta, datetime, date
import tempfile
import os
from .models import (
    Dokument, MietObjekt, Vertrag, Uebergabeprotokoll, MietObjektBild, Aktivitaet, 
    Zaehler, Zaehlerstand, OBJEKT_TYPE, Eingangsrechnung, EingangsrechnungAufteilung, 
    EINGANGSRECHNUNG_STATUS
)
from core.models import Adresse, Mandant
from .forms import (
    AdresseKundeForm, AdresseStandortForm, AdresseLieferantForm, AdresseForm, MietObjektForm, VertragForm, VertragEndForm, 
    UebergabeprotokollForm, DokumentUploadForm, MietObjektBildUploadForm, AktivitaetForm, VertragsObjektFormSet,
    ZaehlerForm, ZaehlerstandForm, EingangsrechnungForm, EingangsrechnungAufteilungFormSet
)
from core.mailing.service import send_mail, MailServiceError
from .permissions import vermietung_required
from core.services.ai.invoice_extraction import InvoiceExtractionService
from core.services.ai.supplier_matching import SupplierMatchingService


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
    
    # Get all rental objects with prefetched related data to avoid N+1 queries
    all_mietobjekte = MietObjekt.objects.select_related('standort').all()
    
    # Calculate total available units and create breakdown list
    # We iterate once through all objects to avoid multiple queries
    verfuegbare_einheiten_gesamt = 0
    mietobjekte_mit_einheiten = []
    
    for obj in all_mietobjekte:
        verfuegbare = obj.get_available_units_count()
        gebuchte = obj.get_active_units_count()
        
        # Add to total
        verfuegbare_einheiten_gesamt += verfuegbare
        
        # Add to breakdown list
        mietobjekte_mit_einheiten.append({
            'objekt': obj,
            'verfuegbare_einheiten': verfuegbare,
            'gebuchte_einheiten': gebuchte,
            'gesamt_einheiten': obj.verfuegbare_einheiten,
        })
    
    # Sort by available units (descending), then by name
    mietobjekte_mit_einheiten.sort(
        key=lambda x: (-x['verfuegbare_einheiten'], x['objekt'].name)
    )
    
    active_vertraege = Vertrag.objects.currently_active().count()
    # Count all activities that are NOT 'ABGEBROCHEN' or 'ERLEDIGT' (i.e., OFFEN and IN_BEARBEITUNG)
    offene_aktivitaeten = Aktivitaet.objects.exclude(
        status__in=['ABGEBROCHEN', 'ERLEDIGT']
    ).count()
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
        'verfuegbare_einheiten_gesamt': verfuegbare_einheiten_gesamt,
        'active_vertraege': active_vertraege,
        'offene_aktivitaeten': offene_aktivitaeten,
        'total_kunden': total_kunden,
        'recent_vertraege': recent_vertraege,
        'expiring_vertraege': expiring_vertraege,
        'mietobjekte_mit_einheiten': mietobjekte_mit_einheiten,
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
    
    # Get related aktivitaeten with pagination
    aktivitaeten = kunde.aktivitaeten.select_related('assigned_user', 'assigned_supplier').order_by('-created_at')
    aktivitaeten_paginator = Paginator(aktivitaeten, 10)
    aktivitaeten_page = request.GET.get('aktivitaeten_page', 1)
    aktivitaeten_page_obj = aktivitaeten_paginator.get_page(aktivitaeten_page)
    
    context = {
        'kunde': kunde,
        'dokumente_page_obj': dokumente_page_obj,
        'aktivitaeten_page_obj': aktivitaeten_page_obj,
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


# Standort (Location) CRUD Views

@vermietung_required
def standort_list(request):
    """
    List all locations (Adressen of type STANDORT) with search and pagination.
    """
    # Get search query
    search_query = request.GET.get('q', '').strip()
    
    # Base queryset: only STANDORT addresses
    standorte = Adresse.objects.filter(adressen_type='STANDORT')
    
    # Apply search filter if query provided
    if search_query:
        standorte = standorte.filter(
            Q(name__icontains=search_query) |
            Q(strasse__icontains=search_query) |
            Q(ort__icontains=search_query) |
            Q(plz__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Order by name
    standorte = standorte.order_by('name')
    
    # Pagination
    paginator = Paginator(standorte, 20)  # Show 20 locations per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'vermietung/standorte/list.html', context)


@vermietung_required
def standort_detail(request, pk):
    """
    Show details of a specific location.
    """
    standort = get_object_or_404(Adresse, pk=pk, adressen_type='STANDORT')
    
    # Get related mietobjekte (rental objects at this location) with pagination
    mietobjekte = standort.mietobjekt_set.all().order_by('name')
    mietobjekte_paginator = Paginator(mietobjekte, 10)
    mietobjekte_page = request.GET.get('mietobjekte_page', 1)
    mietobjekte_page_obj = mietobjekte_paginator.get_page(mietobjekte_page)
    
    context = {
        'standort': standort,
        'mietobjekte_page_obj': mietobjekte_page_obj,
    }
    
    return render(request, 'vermietung/standorte/detail.html', context)


@vermietung_required
def standort_create(request):
    """
    Create a new location.
    """
    if request.method == 'POST':
        form = AdresseStandortForm(request.POST)
        if form.is_valid():
            standort = form.save()
            messages.success(request, f'Standort "{standort.name}" wurde erfolgreich angelegt.')
            return redirect('vermietung:standort_detail', pk=standort.pk)
    else:
        form = AdresseStandortForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/standorte/form.html', context)


@vermietung_required
def standort_edit(request, pk):
    """
    Edit an existing location.
    """
    standort = get_object_or_404(Adresse, pk=pk, adressen_type='STANDORT')
    
    if request.method == 'POST':
        form = AdresseStandortForm(request.POST, instance=standort)
        if form.is_valid():
            standort = form.save()
            messages.success(request, f'Standort "{standort.name}" wurde erfolgreich aktualisiert.')
            return redirect('vermietung:standort_detail', pk=standort.pk)
    else:
        form = AdresseStandortForm(instance=standort)
    
    context = {
        'form': form,
        'standort': standort,
        'is_create': False,
    }
    
    return render(request, 'vermietung/standorte/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def standort_delete(request, pk):
    """
    Delete a location.
    Only available in user area (not admin-only).
    """
    standort = get_object_or_404(Adresse, pk=pk, adressen_type='STANDORT')
    standort_name = standort.name
    
    # Check if there are any rental objects at this location
    if standort.mietobjekt_set.exists():
        messages.error(request, f'Standort "{standort_name}" kann nicht gelöscht werden, da es noch Mietobjekte an diesem Standort gibt.')
        return redirect('vermietung:standort_detail', pk=pk)
    
    try:
        standort.delete()
        messages.success(request, f'Standort "{standort_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Standorts: {str(e)}')
        return redirect('vermietung:standort_detail', pk=pk)
    
    return redirect('vermietung:standort_list')


# Lieferant (Supplier) CRUD Views

@vermietung_required
def lieferant_list(request):
    """
    List all suppliers (Adressen of type LIEFERANT) with search and pagination.
    """
    # Get search query
    search_query = request.GET.get('q', '').strip()
    
    # Base queryset: only LIEFERANT addresses
    lieferanten = Adresse.objects.filter(adressen_type='LIEFERANT')
    
    # Apply search filter if query provided
    if search_query:
        lieferanten = lieferanten.filter(
            Q(name__icontains=search_query) |
            Q(firma__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(strasse__icontains=search_query) |
            Q(ort__icontains=search_query) |
            Q(plz__icontains=search_query)
        )
    
    # Order by name
    lieferanten = lieferanten.order_by('name')
    
    # Pagination
    paginator = Paginator(lieferanten, 20)  # Show 20 suppliers per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'vermietung/lieferanten/list.html', context)


@vermietung_required
def lieferant_detail(request, pk):
    """
    Show details of a specific supplier.
    """
    lieferant = get_object_or_404(Adresse, pk=pk, adressen_type='LIEFERANT')
    
    # Get related documents with pagination
    dokumente = lieferant.dokumente.select_related('uploaded_by').order_by('-uploaded_at')
    dokumente_paginator = Paginator(dokumente, 10)
    dokumente_page = request.GET.get('dokumente_page', 1)
    dokumente_page_obj = dokumente_paginator.get_page(dokumente_page)
    
    context = {
        'lieferant': lieferant,
        'dokumente_page_obj': dokumente_page_obj,
    }
    
    return render(request, 'vermietung/lieferanten/detail.html', context)


@vermietung_required
def lieferant_create(request):
    """
    Create a new supplier.
    """
    if request.method == 'POST':
        form = AdresseLieferantForm(request.POST)
        if form.is_valid():
            lieferant = form.save()
            messages.success(request, f'Lieferant "{lieferant.full_name()}" wurde erfolgreich angelegt.')
            return redirect('vermietung:lieferant_detail', pk=lieferant.pk)
    else:
        form = AdresseLieferantForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/lieferanten/form.html', context)


@vermietung_required
def lieferant_edit(request, pk):
    """
    Edit an existing supplier.
    """
    lieferant = get_object_or_404(Adresse, pk=pk, adressen_type='LIEFERANT')
    
    if request.method == 'POST':
        form = AdresseLieferantForm(request.POST, instance=lieferant)
        if form.is_valid():
            lieferant = form.save()
            messages.success(request, f'Lieferant "{lieferant.full_name()}" wurde erfolgreich aktualisiert.')
            return redirect('vermietung:lieferant_detail', pk=lieferant.pk)
    else:
        form = AdresseLieferantForm(instance=lieferant)
    
    context = {
        'form': form,
        'lieferant': lieferant,
        'is_create': False,
    }
    
    return render(request, 'vermietung/lieferanten/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def lieferant_delete(request, pk):
    """
    Delete a supplier.
    Only available in user area (not admin-only).
    """
    lieferant = get_object_or_404(Adresse, pk=pk, adressen_type='LIEFERANT')
    lieferant_name = lieferant.full_name()
    
    try:
        lieferant.delete()
        messages.success(request, f'Lieferant "{lieferant_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Lieferanten: {str(e)}')
    
    return redirect('vermietung:lieferant_list')


# Adresse (Generic Address) CRUD Views

@vermietung_required
def adresse_list(request):
    """
    List all addresses (Adressen of type Adresse) with search and pagination.
    """
    # Get search query
    search_query = request.GET.get('q', '').strip()
    
    # Base queryset: only Adresse addresses
    adressen = Adresse.objects.filter(adressen_type='Adresse')
    
    # Apply search filter if query provided
    if search_query:
        adressen = adressen.filter(
            Q(name__icontains=search_query) |
            Q(firma__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(strasse__icontains=search_query) |
            Q(ort__icontains=search_query) |
            Q(plz__icontains=search_query)
        )
    
    # Order by name
    adressen = adressen.order_by('name')
    
    # Pagination
    paginator = Paginator(adressen, 20)  # Show 20 addresses per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'vermietung/adressen/list.html', context)


@vermietung_required
def adresse_detail(request, pk):
    """
    Show details of a specific address.
    """
    adresse = get_object_or_404(Adresse, pk=pk, adressen_type='Adresse')
    
    # Get related documents with pagination
    dokumente = adresse.dokumente.select_related('uploaded_by').order_by('-uploaded_at')
    dokumente_paginator = Paginator(dokumente, 10)
    dokumente_page = request.GET.get('dokumente_page', 1)
    dokumente_page_obj = dokumente_paginator.get_page(dokumente_page)
    
    context = {
        'adresse': adresse,
        'dokumente_page_obj': dokumente_page_obj,
    }
    
    return render(request, 'vermietung/adressen/detail.html', context)


@vermietung_required
def adresse_create(request):
    """
    Create a new address.
    """
    if request.method == 'POST':
        form = AdresseForm(request.POST)
        if form.is_valid():
            adresse = form.save()
            messages.success(request, f'Adresse "{adresse.full_name()}" wurde erfolgreich angelegt.')
            return redirect('vermietung:adresse_detail', pk=adresse.pk)
    else:
        form = AdresseForm()
    
    context = {
        'form': form,
        'is_create': True,
    }
    
    return render(request, 'vermietung/adressen/form.html', context)


@vermietung_required
def adresse_edit(request, pk):
    """
    Edit an existing address.
    """
    adresse = get_object_or_404(Adresse, pk=pk, adressen_type='Adresse')
    
    if request.method == 'POST':
        form = AdresseForm(request.POST, instance=adresse)
        if form.is_valid():
            adresse = form.save()
            messages.success(request, f'Adresse "{adresse.full_name()}" wurde erfolgreich aktualisiert.')
            return redirect('vermietung:adresse_detail', pk=adresse.pk)
    else:
        form = AdresseForm(instance=adresse)
    
    context = {
        'form': form,
        'adresse': adresse,
        'is_create': False,
    }
    
    return render(request, 'vermietung/adressen/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def adresse_delete(request, pk):
    """
    Delete an address.
    Only available in user area (not admin-only).
    """
    adresse = get_object_or_404(Adresse, pk=pk, adressen_type='Adresse')
    adresse_name = adresse.full_name()
    
    try:
        adresse.delete()
        messages.success(request, f'Adresse "{adresse_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen der Adresse: {str(e)}')
    
    return redirect('vermietung:adresse_list')


# MietObjekt (Rental Object) CRUD Views

@vermietung_required
def mietobjekt_list(request):
    """
    List all MietObjekt with search, filtering and pagination.
    Supports filtering by type, availability, location, and mandant.
    """
    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '')
    verfuegbar_filter = request.GET.get('verfuegbar', '')
    standort_filter = request.GET.get('standort', '')
    mandant_filter = request.GET.get('mandant', '')
    
    # Base queryset with related data
    mietobjekte = MietObjekt.objects.select_related('standort', 'mandant').all()
    
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
    
    # Apply mandant filter
    if mandant_filter:
        mietobjekte = mietobjekte.filter(mandant_id=mandant_filter)
    
    # Order by name
    mietobjekte = mietobjekte.order_by('name')
    
    # Pagination
    paginator = Paginator(mietobjekte, 20)  # Show 20 items per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all standorte for filter dropdown only if needed
    # Always fetch for display consistency
    standorte = Adresse.objects.filter(adressen_type='STANDORT').order_by('name')
    
    # Get all mandanten for filter dropdown
    mandanten = Mandant.objects.all().order_by('name')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'type_filter': type_filter,
        'verfuegbar_filter': verfuegbar_filter,
        'standort_filter': standort_filter,
        'mandant_filter': mandant_filter,
        'standorte': standorte,
        'mandanten': mandanten,
        'objekt_types': OBJEKT_TYPE,
    }
    
    return render(request, 'vermietung/mietobjekte/list.html', context)


@vermietung_required
def mietobjekt_detail(request, pk):
    """
    Show details of a specific MietObjekt with related data.
    Shows contracts, handover protocols, documents, images, activities, and Zähler (meters) in tabs with pagination.
    """
    mietobjekt = get_object_or_404(MietObjekt.objects.select_related('standort'), pk=pk)
    
    # Get related contracts with pagination
    # Query contracts through both new VertragsObjekt relationship and legacy relationship
    vertraege = mietobjekt.get_all_vertraege().select_related('mieter').order_by('-start')
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
    
    # Get related images with pagination
    bilder = mietobjekt.bilder.select_related('uploaded_by').order_by('-uploaded_at')
    bilder_paginator = Paginator(bilder, 12)  # Show 12 images per page (3x4 grid)
    bilder_page = request.GET.get('bilder_page', 1)
    bilder_page_obj = bilder_paginator.get_page(bilder_page)
    
    # Get related aktivitaeten with pagination
    aktivitaeten = mietobjekt.aktivitaeten.select_related('assigned_user', 'assigned_supplier').order_by('-created_at')
    aktivitaeten_paginator = Paginator(aktivitaeten, 10)
    aktivitaeten_page = request.GET.get('aktivitaeten_page', 1)
    aktivitaeten_page_obj = aktivitaeten_paginator.get_page(aktivitaeten_page)
    
    # Get related meters (zaehler) - organize hierarchically (parent meters with their sub-meters)
    # Only get parent meters (no parent field set) and prefetch sub-meters
    parent_zaehler = mietobjekt.zaehler.filter(parent__isnull=True).prefetch_related('sub_zaehler', 'staende').order_by('typ', 'bezeichnung')
    
    # Get related incoming invoices (eingangsrechnungen) with pagination
    eingangsrechnungen = mietobjekt.eingangsrechnungen.select_related('lieferant').prefetch_related('aufteilungen').order_by('-belegdatum')
    eingangsrechnungen_paginator = Paginator(eingangsrechnungen, 10)
    eingangsrechnungen_page = request.GET.get('eingangsrechnungen_page', 1)
    eingangsrechnungen_page_obj = eingangsrechnungen_paginator.get_page(eingangsrechnungen_page)
    
    context = {
        'mietobjekt': mietobjekt,
        'vertraege_page_obj': vertraege_page_obj,
        'uebergaben_page_obj': uebergaben_page_obj,
        'dokumente_page_obj': dokumente_page_obj,
        'bilder_page_obj': bilder_page_obj,
        'aktivitaeten_page_obj': aktivitaeten_page_obj,
        'parent_zaehler': parent_zaehler,
        'eingangsrechnungen_page_obj': eingangsrechnungen_page_obj,
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
    if mietobjekt.has_active_contracts():
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
    Supports filtering by status and mandant.
    """
    # Get search query
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    mandant_filter = request.GET.get('mandant', '')
    
    # Base queryset with related data
    vertraege = Vertrag.objects.select_related('mietobjekt', 'mieter', 'mandant').all()
    
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
    
    # Apply mandant filter
    if mandant_filter:
        vertraege = vertraege.filter(mandant_id=mandant_filter)
    
    # Order by start date (newest first)
    vertraege = vertraege.order_by('-start')
    
    # Pagination
    paginator = Paginator(vertraege, 20)  # Show 20 contracts per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all mandanten for filter dropdown
    mandanten = Mandant.objects.all().order_by('name')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'mandant_filter': mandant_filter,
        'mandanten': mandanten,
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
    
    # Get related aktivitaeten with pagination
    aktivitaeten = vertrag.aktivitaeten.select_related('assigned_user', 'assigned_supplier').order_by('-created_at')
    aktivitaeten_paginator = Paginator(aktivitaeten, 10)
    aktivitaeten_page = request.GET.get('aktivitaeten_page', 1)
    aktivitaeten_page_obj = aktivitaeten_paginator.get_page(aktivitaeten_page)
    
    context = {
        'vertrag': vertrag,
        'uebergaben_page_obj': uebergaben_page_obj,
        'dokumente_page_obj': dokumente_page_obj,
        'aktivitaeten_page_obj': aktivitaeten_page_obj,
    }
    
    return render(request, 'vermietung/vertraege/detail.html', context)


@vermietung_required
def vertrag_create(request):
    """
    Create a new contract with rental objects.
    Uses inline formset for managing VertragsObjekt entries.
    """
    if request.method == 'POST':
        form = VertragForm(request.POST)
        formset = VertragsObjektFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                # Save the contract first (without committing to DB yet)
                vertrag = form.save(commit=False)
                vertrag.save()
                
                # Save formset with the contract
                formset.instance = vertrag
                formset.save()
                
                # Calculate and update total miete from all VertragsObjekt items
                vertrag.miete = vertrag.berechne_gesamtmiete()
                vertrag.save(update_fields=['miete'])
                
                # Update availability of all affected mietobjekte
                vertrag.update_mietobjekte_availability()
                
                messages.success(
                    request,
                    f'Vertrag "{vertrag.vertragsnummer}" wurde erfolgreich angelegt.'
                )
                return redirect('vermietung:vertrag_detail', pk=vertrag.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    messages.error(request, str(e))
    else:
        form = VertragForm()
        formset = VertragsObjektFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'is_create': True,
    }
    
    return render(request, 'vermietung/vertraege/form.html', context)


@vermietung_required
def vertrag_edit(request, pk):
    """
    Edit an existing contract with rental objects.
    Uses inline formset for managing VertragsObjekt entries.
    """
    vertrag = get_object_or_404(Vertrag, pk=pk)
    
    if request.method == 'POST':
        form = VertragForm(request.POST, instance=vertrag)
        formset = VertragsObjektFormSet(request.POST, instance=vertrag)
        
        if form.is_valid() and formset.is_valid():
            try:
                # Save the contract and formset
                vertrag = form.save()
                formset.save()
                
                # Calculate and update total miete from all VertragsObjekt items
                vertrag.miete = vertrag.berechne_gesamtmiete()
                vertrag.save(update_fields=['miete'])
                
                # Update availability of all affected mietobjekte
                vertrag.update_mietobjekte_availability()
                
                messages.success(
                    request,
                    f'Vertrag "{vertrag.vertragsnummer}" wurde erfolgreich aktualisiert.'
                )
                return redirect('vermietung:vertrag_detail', pk=vertrag.pk)
            except ValidationError as e:
                # Handle validation errors from model's clean() method
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field, error)
                else:
                    messages.error(request, str(e))
    else:
        form = VertragForm(instance=vertrag)
        formset = VertragsObjektFormSet(instance=vertrag)
    
    context = {
        'form': form,
        'formset': formset,
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
    valid_entity_types = ['vertrag', 'mietobjekt', 'adresse', 'uebergabeprotokoll', 'eingangsrechnung']
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
    elif entity_type == 'eingangsrechnung':
        entity = get_object_or_404(Eingangsrechnung, pk=entity_id)
        entity_name = f'Eingangsrechnung {entity.belegnummer}'
        redirect_url = 'vermietung:eingangsrechnung_detail'
    
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

# MietObjekt Image Views

@vermietung_required
def mietobjekt_bild_upload(request, pk):
    """
    Upload images for a specific MietObjekt.
    Supports multiple file upload.
    
    Args:
        request: HTTP request
        pk: ID of the MietObjekt
    
    Returns:
        Redirects back to mietobjekt detail page with success/error message
    """
    mietobjekt = get_object_or_404(MietObjekt, pk=pk)
    
    if request.method == 'POST':
        form = MietObjektBildUploadForm(
            request.POST,
            request.FILES,
            mietobjekt=mietobjekt,
            user=request.user
        )
        
        # Get multiple files from request
        files = request.FILES.getlist('bilder')
        
        if not files:
            messages.error(request, 'Bitte wählen Sie mindestens ein Bild aus.')
            return redirect('vermietung:mietobjekt_detail', pk=pk)
        
        if form.is_valid():
            try:
                bilder = form.save(files)
                
                if len(bilder) == 1:
                    messages.success(
                        request,
                        f'Bild "{bilder[0].original_filename}" wurde erfolgreich hochgeladen.'
                    )
                else:
                    messages.success(
                        request,
                        f'{len(bilder)} Bilder wurden erfolgreich hochgeladen.'
                    )
                return redirect('vermietung:mietobjekt_detail', pk=pk)
            except ValidationError as e:
                # Handle validation errors from file validators
                if isinstance(e.messages, list):
                    for error in e.messages:
                        messages.error(request, error)
                else:
                    messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Fehler beim Hochladen: {str(e)}')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    
    # Redirect back to detail page (GET or failed POST)
    return redirect('vermietung:mietobjekt_detail', pk=pk)


@vermietung_required
def serve_mietobjekt_bild(request, bild_id, mode='thumbnail'):
    """
    Auth-protected view to serve MietObjekt images.
    
    Args:
        request: HTTP request
        bild_id: ID of the MietObjektBild
        mode: 'thumbnail' or 'original'
    
    Returns:
        FileResponse with the image file
    
    Raises:
        Http404: If image not found or file doesn't exist
    """
    # Get image from database
    bild = get_object_or_404(MietObjektBild, pk=bild_id)
    
    # Get file path based on mode
    if mode == 'thumbnail':
        file_path = bild.get_thumbnail_absolute_path()
        content_type = 'image/jpeg'  # Thumbnails are always JPEG
    else:  # original
        file_path = bild.get_absolute_path()
        content_type = bild.mime_type
    
    # Check if file exists
    if not file_path.exists():
        raise Http404("Bilddatei wurde nicht gefunden im Filesystem.")
    
    # Create response - FileResponse handles file opening/closing automatically
    # For images, we don't want to force download, so as_attachment=False
    response = FileResponse(
        file_path.open('rb'),
        content_type=content_type,
        as_attachment=False
    )
    
    return response


@vermietung_required
@require_http_methods(["POST"])
def mietobjekt_bild_delete(request, bild_id):
    """
    Delete a MietObjekt image.
    Available to all authenticated users in vermietung area.
    
    Args:
        request: HTTP request
        bild_id: ID of the MietObjektBild to delete
    
    Returns:
        Redirects back to mietobjekt detail page with success/error message
    """
    bild = get_object_or_404(MietObjektBild, pk=bild_id)
    mietobjekt_id = bild.mietobjekt_id
    bild_name = bild.original_filename
    
    try:
        bild.delete()
        messages.success(request, f'Bild "{bild_name}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen des Bildes: {str(e)}')
    
    return redirect('vermietung:mietobjekt_detail', pk=mietobjekt_id)


# Aktivitaet (Activity/Task) Views

@vermietung_required
def aktivitaet_kanban(request):
    """
    Kanban view for all activities grouped by status.
    This is the default view for activities accessible from main navigation.
    """
    # Get all activities with related data
    aktivitaeten = Aktivitaet.objects.select_related(
        'assigned_user', 'assigned_supplier', 
        'mietobjekt', 'vertrag', 'kunde'
    ).all()
    
    # Group by status
    aktivitaeten_offen = aktivitaeten.filter(status='OFFEN').order_by('-prioritaet', 'faellig_am')
    aktivitaeten_in_bearbeitung = aktivitaeten.filter(status='IN_BEARBEITUNG').order_by('-prioritaet', 'faellig_am')
    aktivitaeten_erledigt = aktivitaeten.filter(status='ERLEDIGT').order_by('-updated_at')[:20]  # Limit completed
    aktivitaeten_abgebrochen = aktivitaeten.filter(status='ABGEBROCHEN').order_by('-updated_at')[:20]  # Limit cancelled
    
    context = {
        'aktivitaeten_offen': aktivitaeten_offen,
        'aktivitaeten_in_bearbeitung': aktivitaeten_in_bearbeitung,
        'aktivitaeten_erledigt': aktivitaeten_erledigt,
        'aktivitaeten_abgebrochen': aktivitaeten_abgebrochen,
    }
    
    return render(request, 'vermietung/aktivitaeten/kanban.html', context)


@vermietung_required
def aktivitaet_list(request):
    """
    List view for all activities with search and filtering.
    """
    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    prioritaet_filter = request.GET.get('prioritaet', '')
    assigned_user_filter = request.GET.get('assigned_user', '')
    
    # Base queryset with related data
    aktivitaeten = Aktivitaet.objects.select_related(
        'assigned_user', 'assigned_supplier',
        'mietobjekt', 'vertrag', 'kunde'
    ).all()
    
    # Apply search filter
    if search_query:
        aktivitaeten = aktivitaeten.filter(
            Q(titel__icontains=search_query) |
            Q(beschreibung__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        aktivitaeten = aktivitaeten.filter(status=status_filter)
    
    # Apply priority filter
    if prioritaet_filter:
        aktivitaeten = aktivitaeten.filter(prioritaet=prioritaet_filter)
    
    # Apply assigned user filter
    if assigned_user_filter:
        aktivitaeten = aktivitaeten.filter(assigned_user_id=assigned_user_filter)
    
    # Order by priority and due date
    aktivitaeten = aktivitaeten.order_by('-prioritaet', 'faellig_am', '-created_at')
    
    # Pagination
    paginator = Paginator(aktivitaeten, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'prioritaet_filter': prioritaet_filter,
        'assigned_user_filter': assigned_user_filter,
    }
    
    return render(request, 'vermietung/aktivitaeten/list.html', context)


@vermietung_required
def aktivitaet_assigned_list(request):
    """
    List view for activities assigned to the current user.
    Shows only non-completed and non-cancelled activities.
    """
    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    prioritaet_filter = request.GET.get('prioritaet', '')
    
    # Base queryset: activities assigned to current user
    aktivitaeten = Aktivitaet.objects.select_related(
        'assigned_user', 'assigned_supplier', 'ersteller',
        'mietobjekt', 'vertrag', 'kunde'
    ).filter(
        assigned_user=request.user
    ).exclude(
        status__in=['ERLEDIGT', 'ABGEBROCHEN']
    )
    
    # Apply search filter
    if search_query:
        aktivitaeten = aktivitaeten.filter(
            Q(titel__icontains=search_query) |
            Q(beschreibung__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        aktivitaeten = aktivitaeten.filter(status=status_filter)
    
    # Apply priority filter
    if prioritaet_filter:
        aktivitaeten = aktivitaeten.filter(prioritaet=prioritaet_filter)
    
    # Order by priority and due date
    aktivitaeten = aktivitaeten.order_by('-prioritaet', 'faellig_am', '-created_at')
    
    # Pagination
    paginator = Paginator(aktivitaeten, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'prioritaet_filter': prioritaet_filter,
        'view_type': 'assigned',
        'page_title': 'Meine zugewiesenen Aktivitäten',
    }
    
    return render(request, 'vermietung/aktivitaeten/list.html', context)


@vermietung_required
def aktivitaet_created_list(request):
    """
    List view for activities created by the current user.
    Shows only non-completed and non-cancelled activities by default.
    """
    # Get filter parameters
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    prioritaet_filter = request.GET.get('prioritaet', '')
    assigned_user_filter = request.GET.get('assigned_user', '')
    
    # Base queryset: activities created by current user
    aktivitaeten = Aktivitaet.objects.select_related(
        'assigned_user', 'assigned_supplier', 'ersteller',
        'mietobjekt', 'vertrag', 'kunde'
    ).filter(
        ersteller=request.user
    ).exclude(
        status__in=['ERLEDIGT', 'ABGEBROCHEN']
    )
    
    # Apply search filter
    if search_query:
        aktivitaeten = aktivitaeten.filter(
            Q(titel__icontains=search_query) |
            Q(beschreibung__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        aktivitaeten = aktivitaeten.filter(status=status_filter)
    
    # Apply priority filter
    if prioritaet_filter:
        aktivitaeten = aktivitaeten.filter(prioritaet=prioritaet_filter)
    
    # Apply assigned user filter
    if assigned_user_filter:
        aktivitaeten = aktivitaeten.filter(assigned_user_id=assigned_user_filter)
    
    # Order by priority and due date
    aktivitaeten = aktivitaeten.order_by('-prioritaet', 'faellig_am', '-created_at')
    
    # Pagination
    paginator = Paginator(aktivitaeten, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'prioritaet_filter': prioritaet_filter,
        'assigned_user_filter': assigned_user_filter,
        'view_type': 'created',
        'page_title': 'Meine erstellten Aktivitäten',
    }
    
    return render(request, 'vermietung/aktivitaeten/list.html', context)


@vermietung_required
def aktivitaet_create(request, context_type=None, context_id=None):
    """
    Create a new activity.
    Can be called with context (from Vertrag, MietObjekt, or Kunde) or standalone.
    
    Args:
        context_type: Type of context ('vertrag', 'mietobjekt', or 'kunde')
        context_id: ID of the context object
    """
    # Validate context if provided
    context_obj = None
    redirect_url = 'vermietung:aktivitaet_kanban'
    
    if context_type and context_id:
        if context_type == 'vertrag':
            context_obj = get_object_or_404(Vertrag, pk=context_id)
            redirect_url = 'vermietung:vertrag_detail'
        elif context_type == 'mietobjekt':
            context_obj = get_object_or_404(MietObjekt, pk=context_id)
            redirect_url = 'vermietung:mietobjekt_detail'
        elif context_type == 'kunde':
            context_obj = get_object_or_404(Adresse, pk=context_id, adressen_type='KUNDE')
            redirect_url = 'vermietung:kunde_detail'
        else:
            messages.error(request, f'Ungültiger Kontext-Typ: {context_type}')
            return redirect('vermietung:aktivitaet_kanban')
    
    if request.method == 'POST':
        form = AktivitaetForm(
            request.POST,
            context_type=context_type,
            context_id=context_id,
            current_user=request.user
        )
        if form.is_valid():
            try:
                aktivitaet = form.save()
                messages.success(
                    request,
                    f'Aktivität "{aktivitaet.titel}" wurde erfolgreich angelegt.'
                )
                
                # If redirecting to context detail, pass the context_id
                if context_id:
                    return redirect(redirect_url, pk=context_id)
                else:
                    return redirect('vermietung:aktivitaet_kanban')
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        form = AktivitaetForm(
            context_type=context_type,
            context_id=context_id,
            current_user=request.user
        )
    
    context = {
        'form': form,
        'context_obj': context_obj,
        'context_type': context_type,
        'is_create': True,
    }
    
    return render(request, 'vermietung/aktivitaeten/form.html', context)


@vermietung_required
def aktivitaet_edit(request, pk):
    """
    Edit an existing activity.
    Email notifications are sent automatically via signals when:
    - assigned_user changes
    - status changes to ERLEDIGT
    """
    aktivitaet = get_object_or_404(Aktivitaet, pk=pk)
    
    if request.method == 'POST':
        form = AktivitaetForm(request.POST, instance=aktivitaet, current_user=request.user)
        if form.is_valid():
            try:
                aktivitaet = form.save()
                messages.success(
                    request,
                    f'Aktivität "{aktivitaet.titel}" wurde erfolgreich aktualisiert.'
                )
                return redirect('vermietung:aktivitaet_kanban')
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field, error)
    else:
        form = AktivitaetForm(instance=aktivitaet, current_user=request.user)
    
    # Get list of available users for assignment modal
    available_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
    
    context = {
        'form': form,
        'aktivitaet': aktivitaet,
        'is_create': False,
        'available_users': available_users,
    }
    
    return render(request, 'vermietung/aktivitaeten/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_delete(request, pk):
    """
    Delete an activity.
    """
    aktivitaet = get_object_or_404(Aktivitaet, pk=pk)
    aktivitaet_titel = aktivitaet.titel
    
    try:
        aktivitaet.delete()
        messages.success(request, f'Aktivität "{aktivitaet_titel}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen der Aktivität: {str(e)}')
    
    return redirect('vermietung:aktivitaet_kanban')


@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_mark_completed(request, pk):
    """
    Mark an activity as completed (ERLEDIGT).
    Triggers email notification to the creator via signal.
    """
    aktivitaet = get_object_or_404(Aktivitaet, pk=pk)
    
    if aktivitaet.status == 'ERLEDIGT':
        messages.info(request, 'Diese Aktivität ist bereits als erledigt markiert.')
    else:
        try:
            aktivitaet.status = 'ERLEDIGT'
            aktivitaet.save()
            messages.success(
                request,
                f'Aktivität "{aktivitaet.titel}" wurde als erledigt markiert. '
                f'Der Ersteller wurde per E-Mail benachrichtigt.'
            )
        except Exception as e:
            messages.error(request, f'Fehler beim Markieren der Aktivität: {str(e)}')
    
    return redirect('vermietung:aktivitaet_edit', pk=pk)


@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_assign(request, pk):
    """
    Assign an activity to a new user.
    Triggers email notification to the new assignee via signal.
    """
    aktivitaet = get_object_or_404(Aktivitaet, pk=pk)
    
    # Get the new assigned user from POST data
    assigned_user_id = request.POST.get('assigned_user')
    
    if not assigned_user_id:
        messages.error(request, 'Bitte wählen Sie einen Verantwortlichen aus.')
        return redirect('vermietung:aktivitaet_edit', pk=pk)
    
    try:
        new_user = User.objects.get(pk=assigned_user_id, is_active=True)
        
        # Check if assignment actually changes
        if aktivitaet.assigned_user == new_user:
            messages.info(request, f'Die Aktivität ist bereits {new_user.get_full_name() or new_user.username} zugewiesen.')
        else:
            aktivitaet.assigned_user = new_user
            aktivitaet.save()
            
            # Signal will automatically send email
            messages.success(
                request,
                f'Aktivität "{aktivitaet.titel}" wurde {new_user.get_full_name() or new_user.username} zugewiesen. '
                f'Eine E-Mail-Benachrichtigung wurde versendet.'
            )
    except User.DoesNotExist:
        messages.error(request, 'Der ausgewählte Benutzer wurde nicht gefunden.')
    except Exception as e:
        messages.error(request, f'Fehler beim Zuweisen der Aktivität: {str(e)}')
    
    return redirect('vermietung:aktivitaet_edit', pk=pk)


@vermietung_required
@require_http_methods(["POST"])
def aktivitaet_update_status(request, pk):
    """
    Quick update of activity status (for Kanban drag & drop).
    Expects 'status' in POST data.
    """
    from .models import AKTIVITAET_STATUS
    
    aktivitaet = get_object_or_404(Aktivitaet, pk=pk)
    new_status = request.POST.get('status')
    
    # Validate status using model choices
    valid_statuses = [choice[0] for choice in AKTIVITAET_STATUS]
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Ungültiger Status'}, status=400)
    
    try:
        aktivitaet.status = new_status
        aktivitaet.save()
        return JsonResponse({
            'success': True,
            'message': f'Status wurde auf "{aktivitaet.get_status_display()}" geändert.'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# Zaehler (Meter) Views
# =============================================================================

@vermietung_required
def zaehler_create(request, mietobjekt_pk):
    """Create a new meter for a MietObjekt."""
    mietobjekt = get_object_or_404(MietObjekt, pk=mietobjekt_pk)
    
    if request.method == 'POST':
        form = ZaehlerForm(request.POST, mietobjekt=mietobjekt)
        if form.is_valid():
            zaehler = form.save(commit=False)
            zaehler.mietobjekt = mietobjekt
            try:
                zaehler.save()
                messages.success(request, f'Zähler "{zaehler.bezeichnung}" wurde erfolgreich angelegt.')
                return redirect('vermietung:mietobjekt_detail', pk=mietobjekt.pk)
            except ValidationError as e:
                messages.error(request, f'Fehler beim Speichern: {e}')
    else:
        form = ZaehlerForm(mietobjekt=mietobjekt)
    
    context = {
        'form': form,
        'mietobjekt': mietobjekt,
        'is_create': True,
    }
    
    return render(request, 'vermietung/zaehler/form.html', context)


@vermietung_required
def zaehler_edit(request, pk):
    """Edit an existing meter."""
    zaehler = get_object_or_404(Zaehler.objects.select_related('mietobjekt'), pk=pk)
    mietobjekt = zaehler.mietobjekt
    
    if request.method == 'POST':
        form = ZaehlerForm(request.POST, instance=zaehler, mietobjekt=mietobjekt)
        if form.is_valid():
            try:
                zaehler = form.save()
                messages.success(request, f'Zähler "{zaehler.bezeichnung}" wurde erfolgreich aktualisiert.')
                return redirect('vermietung:mietobjekt_detail', pk=mietobjekt.pk)
            except ValidationError as e:
                messages.error(request, f'Fehler beim Speichern: {e}')
    else:
        form = ZaehlerForm(instance=zaehler, mietobjekt=mietobjekt)
    
    context = {
        'form': form,
        'zaehler': zaehler,
        'mietobjekt': mietobjekt,
        'is_create': False,
    }
    
    return render(request, 'vermietung/zaehler/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def zaehler_delete(request, pk):
    """Delete a meter."""
    zaehler = get_object_or_404(Zaehler.objects.select_related('mietobjekt'), pk=pk)
    mietobjekt = zaehler.mietobjekt
    bezeichnung = zaehler.bezeichnung
    
    try:
        zaehler.delete()
        messages.success(request, f'Zähler "{bezeichnung}" wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen: {e}')
    
    return redirect('vermietung:mietobjekt_detail', pk=mietobjekt.pk)


@vermietung_required
def zaehlerstand_create(request, zaehler_pk):
    """Create a new meter reading for a meter."""
    zaehler = get_object_or_404(Zaehler.objects.select_related('mietobjekt'), pk=zaehler_pk)
    mietobjekt = zaehler.mietobjekt
    
    if request.method == 'POST':
        form = ZaehlerstandForm(request.POST)
        if form.is_valid():
            zaehlerstand = form.save(commit=False)
            zaehlerstand.zaehler = zaehler
            try:
                zaehlerstand.save()
                messages.success(request, f'Zählerstand wurde erfolgreich erfasst.')
                return redirect('vermietung:zaehler_detail', pk=zaehler.pk)
            except ValidationError as e:
                messages.error(request, f'Fehler beim Speichern: {e}')
    else:
        form = ZaehlerstandForm()
    
    context = {
        'form': form,
        'zaehler': zaehler,
        'mietobjekt': mietobjekt,
        'is_create': True,
    }
    
    return render(request, 'vermietung/zaehler/zaehlerstand_form.html', context)


@vermietung_required
@vermietung_required
def zaehler_detail(request, pk):
    """Show details of a meter including all readings."""
    zaehler = get_object_or_404(
        Zaehler.objects.select_related('mietobjekt', 'parent').prefetch_related('sub_zaehler', 'staende'),
        pk=pk
    )
    
    # Get all readings for this meter, ordered by date descending
    staende_list = list(zaehler.staende.order_by('-datum'))
    
    # Calculate consumption for each reading (difference from previous reading)
    for i, stand in enumerate(staende_list):
        if i < len(staende_list) - 1:
            # There's a previous reading (next in list since we're ordered descending)
            previous_stand = staende_list[i + 1]
            stand.verbrauch = stand.wert - previous_stand.wert
        else:
            stand.verbrauch = None
    
    # Paginate
    staende_paginator = Paginator(staende_list, 20)
    staende_page = request.GET.get('page', 1)
    staende_page_obj = staende_paginator.get_page(staende_page)
    
    context = {
        'zaehler': zaehler,
        'mietobjekt': zaehler.mietobjekt,
        'staende_page_obj': staende_page_obj,
    }
    
    return render(request, 'vermietung/zaehler/detail.html', context)



@vermietung_required
@require_http_methods(["POST"])
def zaehlerstand_delete(request, pk):
    """Delete a meter reading."""
    zaehlerstand = get_object_or_404(Zaehlerstand.objects.select_related('zaehler'), pk=pk)
    zaehler = zaehlerstand.zaehler
    
    try:
        zaehlerstand.delete()
        messages.success(request, f'Zählerstand vom {zaehlerstand.datum} wurde erfolgreich gelöscht.')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen: {e}')
    
    return redirect('vermietung:zaehler_detail', pk=zaehler.pk)


# ============================================================================
# EINGANGSRECHNUNG (Incoming Invoice) Views
# ============================================================================

@vermietung_required
def eingangsrechnung_list(request):
    """
    List all incoming invoices with search, filter and pagination.
    """
    # Get search query and filters
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    mietobjekt_filter = request.GET.get('mietobjekt', '').strip()
    
    # Base queryset
    rechnungen = Eingangsrechnung.objects.select_related(
        'lieferant', 'mietobjekt'
    ).prefetch_related('aufteilungen')
    
    # Apply search filter if query provided
    if search_query:
        rechnungen = rechnungen.filter(
            Q(belegnummer__icontains=search_query) |
            Q(betreff__icontains=search_query) |
            Q(lieferant__name__icontains=search_query) |
            Q(lieferant__firma__icontains=search_query) |
            Q(referenznummer__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        rechnungen = rechnungen.filter(status=status_filter)
    
    # Apply mietobjekt filter
    if mietobjekt_filter:
        rechnungen = rechnungen.filter(mietobjekt_id=mietobjekt_filter)
    
    # Order by date (newest first)
    rechnungen = rechnungen.order_by('-belegdatum', '-erstellt_am')
    
    # Pagination
    paginator = Paginator(rechnungen, 20)  # Show 20 invoices per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all mietobjekte for filter dropdown
    mietobjekte = MietObjekt.objects.all().order_by('name')
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'mietobjekt_filter': mietobjekt_filter,
        'mietobjekte': mietobjekte,
        'status_choices': EINGANGSRECHNUNG_STATUS,
    }
    
    return render(request, 'vermietung/eingangsrechnungen/list.html', context)


@vermietung_required
def eingangsrechnung_detail(request, pk):
    """
    Show details of a specific incoming invoice with all allocations.
    """
    rechnung = get_object_or_404(
        Eingangsrechnung.objects.select_related('lieferant', 'mietobjekt'),
        pk=pk
    )
    
    # Get all allocations
    aufteilungen = rechnung.aufteilungen.select_related(
        'kostenart1', 'kostenart2'
    ).all()
    
    context = {
        'rechnung': rechnung,
        'aufteilungen': aufteilungen,
    }
    
    return render(request, 'vermietung/eingangsrechnungen/detail.html', context)


@vermietung_required
def eingangsrechnung_create(request):
    """
    Create a new incoming invoice with allocations.
    """
    if request.method == 'POST':
        form = EingangsrechnungForm(request.POST)
        formset = EingangsrechnungAufteilungFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            rechnung = form.save()
            formset.instance = rechnung
            formset.save()
            messages.success(
                request,
                f'Eingangsrechnung "{rechnung.belegnummer}" wurde erfolgreich angelegt.'
            )
            return redirect('vermietung:eingangsrechnung_detail', pk=rechnung.pk)
    else:
        form = EingangsrechnungForm()
        formset = EingangsrechnungAufteilungFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'is_create': True,
    }
    
    return render(request, 'vermietung/eingangsrechnungen/form.html', context)


@vermietung_required
def eingangsrechnung_create_from_pdf(request):
    """
    Create a new incoming invoice from a PDF upload with AI extraction.
    
    This view:
    1. Accepts a PDF upload
    2. Extracts invoice data using AI
    3. Matches the supplier
    4. Creates the invoice with pre-filled data
    5. Attaches the PDF to the invoice
    
    If AI extraction fails, the invoice is still created with empty fields.
    """
    if request.method == 'POST':
        # Handle PDF file upload
        if 'pdf_file' not in request.FILES:
            messages.error(request, 'Bitte wählen Sie eine PDF-Datei aus.')
            return redirect('vermietung:eingangsrechnung_create')
        
        pdf_file = request.FILES['pdf_file']
        
        # Validate file type
        if not pdf_file.name.lower().endswith('.pdf'):
            messages.error(request, 'Bitte laden Sie nur PDF-Dateien hoch.')
            return redirect('vermietung:eingangsrechnung_create')
        
        # Get mandatory mietobjekt from form
        mietobjekt_id = request.POST.get('mietobjekt')
        if not mietobjekt_id:
            messages.error(request, 'Bitte wählen Sie ein Mietobjekt aus.')
            return redirect('vermietung:eingangsrechnung_create')
        
        try:
            mietobjekt = MietObjekt.objects.get(pk=mietobjekt_id)
        except MietObjekt.DoesNotExist:
            messages.error(request, 'Ungültiges Mietobjekt.')
            return redirect('vermietung:eingangsrechnung_create')
        
        # Save PDF temporarily to extract data
        temp_pdf_path = None
        try:
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                for chunk in pdf_file.chunks():
                    temp_file.write(chunk)
                temp_pdf_path = temp_file.name
            
            # Extract invoice data using AI
            extraction_service = InvoiceExtractionService()
            invoice_data = None
            lieferant = None
            
            try:
                invoice_data = extraction_service.extract_invoice_data(
                    pdf_path=temp_pdf_path,
                    user=request.user,
                    client_ip=request.META.get('REMOTE_ADDR')
                )
                
                if invoice_data:
                    messages.info(request, 'Rechnungsdaten wurden erfolgreich durch KI extrahiert.')
                    
                    # Validate extracted data
                    validated_data = invoice_data.validate()
                    
                    # Match supplier if data available
                    if invoice_data.lieferant_name:
                        matching_service = SupplierMatchingService()
                        lieferant = matching_service.match_supplier_with_ai_fallback(
                            name=invoice_data.lieferant_name,
                            strasse=invoice_data.lieferant_strasse,
                            plz=invoice_data.lieferant_plz,
                            ort=invoice_data.lieferant_ort,
                            land=invoice_data.lieferant_land,
                            user=request.user,
                            client_ip=request.META.get('REMOTE_ADDR')
                        )
                        
                        if lieferant:
                            messages.success(
                                request,
                                f'Lieferant "{lieferant.full_name()}" wurde automatisch zugeordnet.'
                            )
                        else:
                            messages.warning(
                                request,
                                f'Lieferant "{invoice_data.lieferant_name}" konnte nicht automatisch zugeordnet werden. '
                                'Bitte manuell auswählen.'
                            )
                else:
                    messages.warning(
                        request,
                        'KI-Extraktion fehlgeschlagen oder keine Daten gefunden. '
                        'Bitte Felder manuell ausfüllen.'
                    )
            
            except Exception as e:
                messages.warning(
                    request,
                    f'KI-Extraktion fehlgeschlagen: {str(e)}. Bitte Felder manuell ausfüllen.'
                )
                invoice_data = None
            
            # Create invoice with extracted data (or empty if extraction failed)
            # Use defaults for required fields that weren't extracted
            rechnung_data = {
                'mietobjekt': mietobjekt,
                'belegdatum': date.today(),  # Default to today
                'faelligkeit': date.today() + timedelta(days=30),  # Default to 30 days from today
                'belegnummer': 'UNBEKANNT-' + timezone.now().strftime('%Y%m%d%H%M%S'),  # Placeholder - user MUST update
                'betreff': 'Automatisch aus PDF erstellt',
            }
            
            # Override with extracted data if available
            if invoice_data:
                validated_data = invoice_data.validate()
                
                if 'belegdatum' in validated_data:
                    rechnung_data['belegdatum'] = datetime.strptime(validated_data['belegdatum'], '%Y-%m-%d').date()
                
                if 'faelligkeit' in validated_data:
                    rechnung_data['faelligkeit'] = datetime.strptime(validated_data['faelligkeit'], '%Y-%m-%d').date()
                
                if 'belegnummer' in validated_data:
                    rechnung_data['belegnummer'] = validated_data['belegnummer']
                
                if 'betreff' in validated_data:
                    rechnung_data['betreff'] = validated_data['betreff']
                
                if 'referenznummer' in validated_data:
                    rechnung_data['referenznummer'] = validated_data['referenznummer']
                
                if 'leistungszeitraum_von' in validated_data:
                    rechnung_data['leistungszeitraum_von'] = datetime.strptime(
                        validated_data['leistungszeitraum_von'], '%Y-%m-%d'
                    ).date()
                
                if 'leistungszeitraum_bis' in validated_data:
                    rechnung_data['leistungszeitraum_bis'] = datetime.strptime(
                        validated_data['leistungszeitraum_bis'], '%Y-%m-%d'
                    ).date()
                
                if 'notizen' in validated_data:
                    rechnung_data['notizen'] = validated_data['notizen']
            
            # Set lieferant if matched
            if lieferant:
                rechnung_data['lieferant'] = lieferant
            else:
                # Use first available supplier as fallback (to satisfy NOT NULL constraint)
                # User will need to correct this manually
                # Order by ID for deterministic behavior
                fallback_lieferant = Adresse.objects.filter(adressen_type='LIEFERANT').order_by('id').first()
                if fallback_lieferant:
                    rechnung_data['lieferant'] = fallback_lieferant
                    messages.warning(
                        request,
                        'Kein Lieferant gefunden. Bitte manuell zuordnen.'
                    )
                else:
                    messages.error(request, 'Keine Lieferanten im System. Bitte zuerst einen Lieferanten anlegen.')
                    return redirect('vermietung:eingangsrechnung_create')
            
            # Create the invoice
            rechnung = Eingangsrechnung(**rechnung_data)
            rechnung.save()
            
            # Upload PDF and link to invoice
            # Reset file pointer
            pdf_file.seek(0)
            
            storage_path, mime_type = Dokument.save_uploaded_file(
                pdf_file,
                'eingangsrechnung',
                rechnung.id
            )
            
            dokument = Dokument(
                original_filename=pdf_file.name,
                storage_path=storage_path,
                file_size=pdf_file.size,
                mime_type=mime_type,
                uploaded_by=request.user,
                beschreibung='Automatisch hochgeladen bei Rechnungserstellung',
                eingangsrechnung=rechnung
            )
            dokument.save()
            
            # Add warning if invoice number was not extracted
            if rechnung.belegnummer.startswith('UNBEKANNT-'):
                messages.warning(
                    request,
                    'WICHTIG: Belegnummer konnte nicht extrahiert werden und wurde automatisch generiert. '
                    'Bitte manuell aktualisieren!'
                )
            
            messages.success(
                request,
                f'Eingangsrechnung "{rechnung.belegnummer}" wurde erfolgreich angelegt und PDF hochgeladen.'
            )
            
            return redirect('vermietung:eingangsrechnung_detail', pk=rechnung.pk)
        
        except ValidationError as e:
            messages.error(request, f'Validierungsfehler: {str(e)}')
            return redirect('vermietung:eingangsrechnung_create')
        
        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen der Rechnung: {str(e)}')
            return redirect('vermietung:eingangsrechnung_create')
        
        finally:
            # Clean up temporary file
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
    
    else:
        # GET request - show upload form
        mietobjekte = MietObjekt.objects.all().order_by('name')
        
        context = {
            'mietobjekte': mietobjekte,
            'is_pdf_upload': True,
        }
        
        return render(request, 'vermietung/eingangsrechnungen/pdf_upload_form.html', context)


@vermietung_required
def eingangsrechnung_edit(request, pk):
    """
    Edit an existing incoming invoice and its allocations.
    """
    rechnung = get_object_or_404(Eingangsrechnung, pk=pk)
    
    if request.method == 'POST':
        form = EingangsrechnungForm(request.POST, instance=rechnung)
        formset = EingangsrechnungAufteilungFormSet(request.POST, instance=rechnung)
        
        if form.is_valid() and formset.is_valid():
            rechnung = form.save()
            formset.save()
            messages.success(
                request,
                f'Eingangsrechnung "{rechnung.belegnummer}" wurde erfolgreich aktualisiert.'
            )
            return redirect('vermietung:eingangsrechnung_detail', pk=rechnung.pk)
    else:
        form = EingangsrechnungForm(instance=rechnung)
        formset = EingangsrechnungAufteilungFormSet(instance=rechnung)
    
    context = {
        'form': form,
        'formset': formset,
        'rechnung': rechnung,
        'is_create': False,
    }
    
    return render(request, 'vermietung/eingangsrechnungen/form.html', context)


@vermietung_required
@require_http_methods(["POST"])
def eingangsrechnung_delete(request, pk):
    """
    Delete an incoming invoice.
    """
    rechnung = get_object_or_404(Eingangsrechnung, pk=pk)
    belegnummer = rechnung.belegnummer
    
    try:
        rechnung.delete()
        messages.success(request, f'Eingangsrechnung "{belegnummer}" wurde erfolgreich gelöscht.')
        return redirect('vermietung:eingangsrechnung_list')
    except Exception as e:
        messages.error(request, f'Fehler beim Löschen der Eingangsrechnung: {str(e)}')
        return redirect('vermietung:eingangsrechnung_detail', pk=pk)


@vermietung_required
def eingangsrechnung_mark_paid(request, pk):
    """
    Mark an invoice as paid.
    
    GET: Show form to enter payment date
    POST: Save payment date and mark as paid
    """
    rechnung = get_object_or_404(Eingangsrechnung, pk=pk)
    
    # Check if already paid
    if rechnung.status == 'BEZAHLT':
        messages.warning(request, 'Diese Rechnung wurde bereits als bezahlt markiert.')
        return redirect('vermietung:eingangsrechnung_detail', pk=pk)
    
    if request.method == 'POST':
        zahlungsdatum_str = request.POST.get('zahlungsdatum')
        if zahlungsdatum_str:
            try:
                zahlungsdatum = datetime.strptime(zahlungsdatum_str, '%Y-%m-%d').date()
                rechnung.mark_as_paid(zahlungsdatum)
                messages.success(
                    request,
                    f'Eingangsrechnung "{rechnung.belegnummer}" wurde als bezahlt markiert.'
                )
                return redirect('vermietung:eingangsrechnung_detail', pk=rechnung.pk)
            except ValueError:
                messages.error(request, 'Ungültiges Datumsformat.')
        else:
            messages.error(request, 'Bitte geben Sie ein Zahlungsdatum an.')
    
    # GET: Show form
    context = {
        'rechnung': rechnung,
        'heute': timezone.now().date(),
    }
    
    return render(request, 'vermietung/eingangsrechnungen/mark_paid.html', context)
