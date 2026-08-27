from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum, Max
from django.http import Http404, JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.conf import settings
from django.urls import reverse
from datetime import datetime, timedelta, date
from decimal import Decimal
from django_tables2 import RequestConfig
import json
import logging
from django.utils import timezone
from django.utils.html import strip_tags

from .models import SalesDocument, DocumentType, SalesDocumentLine, Contract, ContractLine, ContractRun, TextTemplate, TimeEntry
from .tables import SalesDocumentTable, ContractTable, TextTemplateTable, OutgoingInvoiceJournalTable, TimeEntryTable
from .filters import SalesDocumentFilter, ContractFilter, TextTemplateFilter, OutgoingInvoiceJournalFilter, TimeEntryFilter
from .services import (
    DocumentCalculationService,
    TaxDeterminationService,
    PaymentTermTextService,
    get_next_number,
    ContractBillingService,
)
from .utils import sanitize_html
from .printing import SalesDocumentInvoiceContextBuilder
from core.models import Mandant, Adresse, Item, PaymentTerm, TaxRate, Kostenart, Unit, Projekt
from core.services.activity_stream import ActivityStreamService
from core.printing import PdfRenderService, get_static_base_url
from finanzen.models import OutgoingInvoiceJournalEntry

# Initialize logger
logger = logging.getLogger(__name__)


def normalize_foreign_key_id(value):
    """
    Normalize foreign key ID values for database insertion.
    
    Converts empty strings, 'null' strings, and None to None.
    This is needed because form submissions may send empty strings
    instead of null values, which can cause database integrity issues.
    
    Args:
        value: The foreign key ID value (could be int, str, or None)
    
    Returns:
        The value if valid, None if empty/null
    """
    if value in [None, '', 'null']:
        return None
    return value


def _build_contract_line_description(short_text_1, short_text_2='', long_text=''):
    """
    Build the (secondary) description of a contract line from its short texts.

    short_text_1 and long_text are the leading, user-facing fields; description is a
    generated convenience/fallback field and must never replace short_text_1. The
    long_text may contain sanitized HTML, so tags are stripped for the plain-text
    description.

    Returns:
        str: newline-joined non-empty parts, or '' if nothing is set.
    """
    parts = []
    if short_text_1:
        parts.append(short_text_1)
    if short_text_2:
        parts.append(short_text_2)
    if long_text:
        stripped = strip_tags(long_text).strip()
        if stripped:
            parts.append(stripped)
    return '\n'.join(parts)


def normalize_decimal_input(value):
    """
    Normalize decimal input from various formats (German and English).
    
    Handles German decimal format (comma as decimal separator, optional dot as thousands separator)
    and English decimal format (dot as decimal separator, optional comma as thousands separator).
    
    Examples:
        - "1,0000" → Decimal("1.0000")  # German format with comma
        - "99,00" → Decimal("99.00")    # German format
        - "1.234,56" → Decimal("1234.56")  # German with thousands separator
        - "99.00" → Decimal("99.00")    # English format
        - "1,234.56" → Decimal("1234.56")  # English with thousands separator
        - 1.5 → Decimal("1.5")          # Numeric input
    
    Args:
        value: The decimal value to normalize (str, int, float, or Decimal)
    
    Returns:
        Decimal: The normalized decimal value
    
    Raises:
        ValueError: If the value cannot be parsed as a decimal
        TypeError: If the value type is unsupported
    """
    if value is None or value == '':
        raise ValueError("Decimal value cannot be None or empty string")
    
    # If already a Decimal, return as-is
    if isinstance(value, Decimal):
        return value
    
    # Convert to string for processing
    value_str = str(value).strip()
    
    if not value_str:
        raise ValueError("Decimal value cannot be empty")
    
    # Detect format based on last occurrence of comma vs dot
    last_comma = value_str.rfind(',')
    last_dot = value_str.rfind('.')
    
    # German format: comma is decimal separator (1.234,56 or 1,56)
    if last_comma > last_dot:
        # Remove thousands separator (dot) and replace comma with dot
        normalized = value_str.replace('.', '').replace(',', '.')
    # English format or no separator: dot is decimal separator (1,234.56 or 1.56)
    else:
        # Remove thousands separator (comma)
        normalized = value_str.replace(',', '')
    
    try:
        return Decimal(normalized)
    except Exception:
        raise ValueError(f"Ungültiges Dezimalformat: '{value}'")


@login_required
def auftragsverwaltung_home(request):
    """
    Dashboard for Auftragsverwaltung (Order Management)
    
    Shows:
    - KPIs (open documents, unpaid invoices, new documents, open amount)
    - Open sales documents table
    - Latest 10 documents
    - Activity stream (last 25 entries)
    
    All metrics and data are shown across ALL companies.
    """
    # KPI 1: Count of open documents (DRAFT, SENT, APPROVED) - across all companies
    kpi_open_documents = SalesDocument.objects.filter(
        status__in=['DRAFT', 'SENT', 'APPROVED']
    ).count()
    
    # KPI 2: Count of unpaid invoices (documents marked as invoice, not paid, not cancelled)
    kpi_unpaid_invoices = SalesDocument.objects.filter(
        document_type__is_invoice=True,
        paid_at__isnull=True,
        status__in=['SENT', 'APPROVED', 'OVERDUE']
    ).exclude(status='CANCELLED').count()
    
    # KPI 3: New documents in the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    kpi_new_documents_30d = SalesDocument.objects.filter(
        issue_date__gte=thirty_days_ago.date()
    ).count()
    
    # KPI 4: Total open amount (sum of unpaid invoices)
    open_amount_aggregate = SalesDocument.objects.filter(
        document_type__is_invoice=True,
        paid_at__isnull=True,
        status__in=['SENT', 'APPROVED', 'OVERDUE']
    ).exclude(status='CANCELLED').aggregate(total=Sum('total_gross'))
    
    kpi_open_amount = open_amount_aggregate['total'] or Decimal('0.00')
    
    # Get open sales documents (DRAFT, SENT, APPROVED) - across all companies
    open_sales_documents = SalesDocument.objects.filter(
        status__in=['DRAFT', 'SENT', 'APPROVED']
    ).select_related('document_type', 'company').order_by('-issue_date')[:20]
    
    # Get latest 10 documents - across all companies
    latest_documents = SalesDocument.objects.select_related(
        'document_type', 'company'
    ).order_by('-issue_date', '-id')[:10]
    
    today = timezone.now().date()
    due_contracts = Contract.objects.filter(
        is_active=True,
        next_run_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).select_related('customer', 'company').order_by('next_run_date', 'name')[:20]
    
    # Get activity stream (last 25 activities from ALL domains and ALL companies)
    # Show global activities across all modules and all companies
    activities = ActivityStreamService.latest(n=25)
    
    context = {
        'kpi_open_documents': kpi_open_documents,
        'kpi_unpaid_invoices': kpi_unpaid_invoices,
        'kpi_new_documents_30d': kpi_new_documents_30d,
        'kpi_open_amount': kpi_open_amount,
        'open_sales_documents': open_sales_documents,
        'latest_documents': latest_documents,
        'due_contracts': due_contracts,
        'activities': activities,
    }
    
    return render(request, 'auftragsverwaltung/home.html', context)


@login_required
def document_list(request, doc_key):
    """
    Generic list view for sales documents filtered by document type.
    
    Args:
        doc_key: The document type key (e.g., 'quote', 'order', 'invoice', 'delivery', 'credit')
    
    Displays a filterable, sortable, paginated list of sales documents.
    """
    # Get the document type or 404
    document_type = get_object_or_404(DocumentType, key=doc_key, is_active=True)
    
    # Base queryset with optimized select/prefetch
    # Show documents from ALL companies (all users can work with all companies)
    queryset = SalesDocument.objects.select_related(
        'document_type', 'company', 'customer'
    ).filter(
        document_type=document_type
    )
    
    # Apply filters
    filter_set = SalesDocumentFilter(request.GET, queryset=queryset)
    
    # Create table with filtered data
    table = SalesDocumentTable(filter_set.qs)
    
    # Set default ordering to -issue_date
    table.order_by = request.GET.get('sort', '-issue_date')
    
    # Configure pagination (25 per page)
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    # Prepare context
    context = {
        'table': table,
        'filter': filter_set,
        'document_type': document_type,
        'doc_key': doc_key,
    }
    
    return render(request, 'auftragsverwaltung/documents/list.html', context)


@login_required
def document_detail(request, doc_key, pk):
    """
    Detail view for a sales document
    
    Shows document header, lines, totals, and text sections.
    Provides edit capabilities for all document fields.
    
    Args:
        doc_key: Document type key (e.g., 'quote', 'invoice')
        pk: Primary key of the document
    """
    document = get_object_or_404(SalesDocument, pk=pk)
    document_type = get_object_or_404(DocumentType, key=doc_key, is_active=True)
    
    # Verify document belongs to the correct type
    if document.document_type != document_type:
        return redirect('auftragsverwaltung:document_list', doc_key=doc_key)
    
    # Get company (for now, first available)
    company = Mandant.objects.first()
    
    # Get all available customers, payment terms, and tax rates
    customers = Adresse.objects.filter(adressen_type='KUNDE').order_by('name')
    payment_terms = PaymentTerm.objects.all().order_by('name')
    tax_rates = TaxRate.objects.filter(is_active=True).order_by('code')
    companies = Mandant.objects.all().order_by('name')
    kostenarten1 = Kostenart.objects.filter(parent__isnull=True).order_by('name')  # Main cost types only
    units = Unit.objects.all().order_by('name')  # All available units
    copy_document_types = DocumentType.objects.filter(
        key__in=['quote', 'order', 'delivery', 'invoice'],
        is_active=True
    ).order_by('name')
    
    # Get document lines (ordered by position_no)
    lines = document.lines.select_related('item', 'tax_rate', 'kostenart1', 'kostenart2', 'unit').order_by('position_no')
    
    # Get available text templates for this company
    header_templates = TextTemplate.objects.filter(
        company=company,
        is_active=True,
        type__in=['HEADER', 'BOTH']
    ).order_by('sort_order', 'title')
    
    footer_templates = TextTemplate.objects.filter(
        company=company,
        is_active=True,
        type__in=['FOOTER', 'BOTH']
    ).order_by('sort_order', 'title')
    
    context = {
        'document': document,
        'document_type': document_type,
        'doc_key': doc_key,
        'company': company,
        'companies': companies,
        'customers': customers,
        'payment_terms': payment_terms,
        'tax_rates': tax_rates,
        'kostenarten1': kostenarten1,
        'units': units,
        'lines': lines,
        'header_templates': header_templates,
        'footer_templates': footer_templates,
        'status_choices': SalesDocument.STATUS_CHOICES,  # Add for template consistency
        'copy_document_types': copy_document_types,
    }
    
    return render(request, 'auftragsverwaltung/documents/detail.html', context)


@login_required
def document_create(request, doc_key):
    """
    Create a new sales document
    
    GET: Show empty form for creating a new document
    POST: Create the document and redirect to detail view
    
    Args:
        doc_key: Document type key (e.g., 'quote', 'invoice')
    """
    document_type = get_object_or_404(DocumentType, key=doc_key, is_active=True)
    company = Mandant.objects.first()
    
    if request.method == 'POST':
        # Get company from form
        company_id = request.POST.get('company_id')
        if company_id:
            company = get_object_or_404(Mandant, pk=company_id)
        else:
            company = Mandant.objects.first()
        
        # Create new document from POST data
        document = SalesDocument(
            company=company,
            document_type=document_type,
            status='DRAFT',
        )
        
        # Set fields from form
        document.subject = request.POST.get('subject', '')
        document.reference_number = request.POST.get('reference_number', '')
        document.header_text = sanitize_html(request.POST.get('header_text', ''))
        document.footer_text = sanitize_html(request.POST.get('footer_text', ''))
        document.notes_internal = request.POST.get('notes_internal', '')
        document.notes_public = request.POST.get('notes_public', '')
        
        # Set customer if provided
        customer_id = request.POST.get('customer_id')
        if customer_id:
            document.customer = get_object_or_404(Adresse, pk=customer_id)
        
        # Set issue_date (default to today if not provided)
        issue_date_str = request.POST.get('issue_date')
        if issue_date_str:
            document.issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
        else:
            document.issue_date = date.today()

        # Set performance_date_from if provided
        performance_date_from_str = request.POST.get('performance_date_from')
        if performance_date_from_str:
            document.performance_date_from = datetime.strptime(performance_date_from_str, '%Y-%m-%d').date()

        # Set performance_date_to if provided
        performance_date_to_str = request.POST.get('performance_date_to')
        if performance_date_to_str:
            document.performance_date_to = datetime.strptime(performance_date_to_str, '%Y-%m-%d').date()

        # Set payment_term if provided
        payment_term_id = request.POST.get('payment_term_id')
        if payment_term_id:
            document.payment_term = get_object_or_404(PaymentTerm, pk=payment_term_id)
            # Auto-calculate due_date and payment_term_text
            document.due_date = PaymentTermTextService.calculate_due_date(
                document.payment_term,
                document.issue_date
            )
            document.payment_term_text = PaymentTermTextService.generate_payment_term_text(
                document.payment_term,
                document.issue_date
            )
        
        # Generate document number
        document.number = get_next_number(company, document_type)
        
        # Save document
        document.save()
        
        # Log activity
        ActivityStreamService.add(
            company=company,
            domain='ORDER',
            activity_type='DOCUMENT_CREATED',
            title=f'{document_type.name} erstellt: {document.number}',
            description=f'Betreff: {document.subject}' if document.subject else None,
            target_url=f'/auftragsverwaltung/documents/{doc_key}/{document.pk}/',
            actor=request.user,
            severity='INFO'
        )
        
        # Redirect to detail view
        return redirect('auftragsverwaltung:document_detail', doc_key=doc_key, pk=document.pk)
    
    # GET: Show empty form
    customers = Adresse.objects.filter(adressen_type='KUNDE').order_by('name')
    payment_terms = PaymentTerm.objects.all().order_by('name')
    companies = Mandant.objects.all().order_by('name')
    tax_rates = TaxRate.objects.filter(is_active=True).order_by('code')
    kostenarten1 = Kostenart.objects.filter(parent__isnull=True).order_by('name')  # Main cost types only
    units = Unit.objects.all().order_by('name')  # All available units
    copy_document_types = DocumentType.objects.filter(
        key__in=['quote', 'order', 'delivery', 'invoice'],
        is_active=True
    ).order_by('name')
    
    # Get available text templates for this company
    header_templates = TextTemplate.objects.filter(
        company=company,
        is_active=True,
        type__in=['HEADER', 'BOTH']
    ).order_by('sort_order', 'title')
    
    footer_templates = TextTemplate.objects.filter(
        company=company,
        is_active=True,
        type__in=['FOOTER', 'BOTH']
    ).order_by('sort_order', 'title')
    
    context = {
        'document': None,  # Explicitly set to None for create mode
        'lines': [],  # No lines in create mode
        'document_type': document_type,
        'doc_key': doc_key,
        'company': company,
        'companies': companies,
        'customers': customers,
        'payment_terms': payment_terms,
        'tax_rates': tax_rates,
        'kostenarten1': kostenarten1,
        'units': units,
        'is_create': True,
        'header_templates': header_templates,
        'footer_templates': footer_templates,
        'status_choices': SalesDocument.STATUS_CHOICES,  # Add STATUS_CHOICES for create mode
        'copy_document_types': copy_document_types,
    }
    
    return render(request, 'auftragsverwaltung/documents/detail.html', context)


@login_required
@require_http_methods(["POST"])
def document_update(request, doc_key, pk):
    """
    Update an existing sales document
    
    POST: Update document fields and redirect to detail view
    
    Args:
        doc_key: Document type key
        pk: Primary key of the document
    """
    document = get_object_or_404(SalesDocument, pk=pk)
    document_type = get_object_or_404(DocumentType, key=doc_key, is_active=True)
    
    # Verify document belongs to the correct type
    if document.document_type != document_type:
        return redirect('auftragsverwaltung:document_list', doc_key=doc_key)
    
    # Update fields from form
    document.subject = request.POST.get('subject', '')
    document.reference_number = request.POST.get('reference_number', '')
    document.header_text = sanitize_html(request.POST.get('header_text', ''))
    document.footer_text = sanitize_html(request.POST.get('footer_text', ''))
    document.notes_internal = request.POST.get('notes_internal', '')
    document.notes_public = request.POST.get('notes_public', '')
    document.status = request.POST.get('status', 'DRAFT')
    
    # Update customer if provided
    customer_id = request.POST.get('customer_id')
    if customer_id:
        document.customer = get_object_or_404(Adresse, pk=customer_id)
    else:
        document.customer = None
    
    # Update issue_date
    issue_date_str = request.POST.get('issue_date')
    if issue_date_str:
        document.issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()

    # Update performance_date_from if provided
    performance_date_from_str = request.POST.get('performance_date_from')
    if performance_date_from_str:
        document.performance_date_from = datetime.strptime(performance_date_from_str, '%Y-%m-%d').date()
    else:
        document.performance_date_from = None

    # Update performance_date_to if provided
    performance_date_to_str = request.POST.get('performance_date_to')
    if performance_date_to_str:
        document.performance_date_to = datetime.strptime(performance_date_to_str, '%Y-%m-%d').date()
    else:
        document.performance_date_to = None

    # Update payment_term if provided
    payment_term_id = request.POST.get('payment_term_id')
    if payment_term_id:
        document.payment_term = get_object_or_404(PaymentTerm, pk=payment_term_id)
        # Auto-calculate due_date and payment_term_text
        document.due_date = PaymentTermTextService.calculate_due_date(
            document.payment_term,
            document.issue_date
        )
        document.payment_term_text = PaymentTermTextService.generate_payment_term_text(
            document.payment_term,
            document.issue_date
        )
    else:
        document.payment_term = None
        document.due_date = None
        document.payment_term_text = ''
    
    # Save document
    document.save()
    
    # Recalculate totals
    DocumentCalculationService.recalculate(document, persist=True)
    
    # Log activity
    ActivityStreamService.add(
        company=document.company,
        domain='ORDER',
        activity_type='DOCUMENT_UPDATED',
        title=f'{document.document_type.name} aktualisiert: {document.number}',
        description=f'Betreff: {document.subject}' if document.subject else None,
        target_url=f'/auftragsverwaltung/documents/{doc_key}/{document.pk}/',
        actor=request.user,
        severity='INFO'
    )
    
    # Redirect to detail view
    return redirect('auftragsverwaltung:document_detail', doc_key=doc_key, pk=document.pk)


@login_required
@require_POST
def document_copy(request, doc_key, pk):
    """
    Create a copy of an existing sales document in a (possibly) different document type.
    
    Expects POST parameter:
        - target_document_type: key of the target DocumentType
    
    Returns:
        JSON containing redirect_url to the new document detail page.
    """
    document = get_object_or_404(SalesDocument, pk=pk)
    document_type = get_object_or_404(DocumentType, key=doc_key, is_active=True)
    
    if document.document_type != document_type:
        return JsonResponse({'success': False, 'error': 'Dokumenttyp stimmt nicht überein.'}, status=400)
    
    target_key = request.POST.get('target_document_type')
    if not target_key:
        return JsonResponse({'success': False, 'error': 'Ziel-Dokumenttyp ist erforderlich.'}, status=400)
    
    try:
        target_document_type = DocumentType.objects.get(key=target_key, is_active=True)
    except DocumentType.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ungültiger Dokumenttyp.'}, status=400)
    
    try:
        new_document = document.clone_as(target_document_type)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.exception("Fehler beim Kopieren des Dokuments %s", document.pk)
        return JsonResponse({'success': False, 'error': 'Kopieren fehlgeschlagen.'}, status=500)
    
    ActivityStreamService.add(
        company=new_document.company,
        domain='ORDER',
        activity_type='DOCUMENT_COPIED',
        title=f'{document.document_type.name} kopiert: {new_document.number}',
        description=f'Quelle: {document.number}',
        target_url=f'/auftragsverwaltung/documents/{target_document_type.key}/{new_document.pk}/',
        actor=request.user,
        severity='INFO'
    )
    
    redirect_url = reverse('auftragsverwaltung:document_detail', kwargs={
        'doc_key': target_document_type.key,
        'pk': new_document.pk,
    })
    
    return JsonResponse({
        'success': True,
        'document_id': new_document.pk,
        'redirect_url': redirect_url,
    })


@login_required
@require_http_methods(["POST"])
def ajax_calculate_payment_term(request):
    """
    AJAX endpoint to calculate due_date and payment_term_text
    
    POST parameters:
        - payment_term_id: Payment term ID
        - issue_date: Issue date (YYYY-MM-DD)
    
    Returns:
        JSON: {due_date, payment_term_text}
    """
    try:
        payment_term_id = request.POST.get('payment_term_id')
        issue_date_str = request.POST.get('issue_date')
        
        if not payment_term_id or not issue_date_str:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        payment_term = get_object_or_404(PaymentTerm, pk=payment_term_id)
        issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
        
        due_date = PaymentTermTextService.calculate_due_date(payment_term, issue_date)
        payment_term_text = PaymentTermTextService.generate_payment_term_text(payment_term, issue_date)
        
        return JsonResponse({
            'due_date': due_date.strftime('%Y-%m-%d'),
            'due_date_formatted': due_date.strftime('%d.%m.%Y'),
            'payment_term_text': payment_term_text,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def ajax_search_articles(request):
    """
    AJAX endpoint for article search (full-text)
    
    GET parameters:
        - q: Search query
    
    Returns:
        JSON: List of matching articles with details
    """
    try:
        query = request.GET.get('q', '').strip()

        if not query or len(query) < 2:
            return JsonResponse({'articles': []})

        # Search across required fields:
        # - article_no: exact (case-insensitive)
        # - short_text_1/short_text_2/long_text: partial (case-insensitive)
        articles = (
            Item.objects.filter(
                Q(article_no__iexact=query) |
                Q(short_text_1__icontains=query) |
                Q(short_text_2__icontains=query) |
                Q(long_text__icontains=query),
                is_active=True
            )
            .select_related('tax_rate', 'cost_type_1', 'cost_type_2', 'item_group')
            .order_by('article_no')[:20]
        )

        # Format results
        results = []
        for article in articles:
            results.append({
                'id': article.pk,
                'article_no': article.article_no,
                'short_text_1': article.short_text_1,
                'short_text_2': article.short_text_2,
                'long_text': article.long_text,
                'net_price': str(article.net_price),
                'tax_rate_id': article.tax_rate.pk,
                'tax_rate_code': article.tax_rate.code,
                'tax_rate': str(article.tax_rate.rate),
                'is_discountable': article.is_discountable,
                'cost_type_1_id': article.cost_type_1.pk if article.cost_type_1 else None,
                'cost_type_2_id': article.cost_type_2.pk if article.cost_type_2 else None,
            })
        
        return JsonResponse({'articles': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def ajax_search_customers(request):
    """
    AJAX endpoint for customer search (partial string)

    GET parameters:
        - q: Search query

    Returns:
        JSON: List of matching customers with details
    """
    try:
        query = request.GET.get('q', '').strip()

        if not query or len(query) < 2:
            return JsonResponse({'customers': []})

        # Search across matchkey, name and firma using partial match (icontains)
        # OR-combination: match if query is found in any of them
        customers = (
            Adresse.objects.filter(
                Q(matchkey__icontains=query) | Q(name__icontains=query) | Q(firma__icontains=query),
                adressen_type='KUNDE'
            )
            .order_by('matchkey')[:20]
        )

        # Format results
        results = []
        for customer in customers:
            results.append({
                'id': customer.pk,
                'name': customer.name,
                'firma': customer.firma or '',
                'matchkey': customer.matchkey,
                # Rückwärtskompatibler Alias; identisch zum Matchkey.
                'full_name': customer.full_name(),
            })

        return JsonResponse({'customers': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ajax_add_line(request, doc_key, pk):
    """
    AJAX endpoint to add a new line to a document

    POST parameters (JSON):
        - item_id: Item/Article ID (optional for manual lines)
        - quantity: Quantity (German or English decimal format)
        - description: Description (required for manual lines)
        - unit_price_net: Unit price (required for manual lines; German or English decimal format)
        - tax_rate_id: Tax rate ID (required)
        - line_type: Line type (NORMAL, OPTIONAL, ALTERNATIVE)
        - kostenart1_id: Kostenart 1 ID (optional)
        - kostenart2_id: Kostenart 2 ID (optional)

    Returns:
        JSON: {success, line_id, line_data} on success.
        Validation errors (invalid decimal, unknown tax_rate_id/item_id, missing
        required fields, empty payload) return HTTP 400 with {'success': False, 'error': ...}.
    """
    document = get_object_or_404(SalesDocument, pk=pk)

    try:
        data = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Ungültiger JSON-Body.'}, status=400)

    if not data:
        return JsonResponse({'success': False, 'error': 'Keine Felder für die neue Position übermittelt.'}, status=400)

    item_id = data.get('item_id')
    line_type = data.get('line_type', 'NORMAL')
    description = data.get('description', '')
    short_text_1 = data.get('short_text_1', '')
    short_text_2 = data.get('short_text_2', '')
    long_text = data.get('long_text', '')
    unit_price_net = data.get('unit_price_net')
    tax_rate_id = data.get('tax_rate_id')
    kostenart1_id = data.get('kostenart1_id')
    kostenart2_id = data.get('kostenart2_id')

    try:
        quantity = normalize_decimal_input(data.get('quantity', '1.0'))
    except (ValueError, TypeError) as e:
        logger.warning("Ungültige Menge in add-document-line Request.", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Ungültige Menge.'}, status=400)

    try:
        # Determine line data based on whether item is provided
        if item_id:
            # Article-based line
            try:
                item = Item.objects.get(pk=item_id)
            except Item.DoesNotExist:
                return JsonResponse(
                    {'success': False, 'error': f'Ungültiger Artikel: Kein Artikel mit ID {item_id} gefunden.'},
                    status=400
                )

            # Determine tax rate (using TaxDeterminationService)
            tax_rate = TaxDeterminationService.determine_tax_rate(
                customer=document.customer,
                item_tax_rate=item.tax_rate
            )

            # Use item data
            if not short_text_1:
                short_text_1 = item.short_text_1
            if not short_text_2:
                short_text_2 = item.short_text_2
            if not long_text:
                long_text = item.long_text
            if not description:
                description = f"{short_text_1}\n{long_text}" if long_text else short_text_1
            if not unit_price_net:
                unit_price_net = item.net_price
            is_discountable = item.is_discountable

            # Use item's kostenart if not provided
            if not kostenart1_id and item.cost_type_1:
                kostenart1_id = item.cost_type_1.pk
            if not kostenart2_id and item.cost_type_2:
                kostenart2_id = item.cost_type_2.pk
        else:
            # Manual line without item
            item = None

            # Validate mandatory fields only if user has entered description content
            # Allow positions with just short_text_1 and zero price for initial creation
            if description and description.strip():
                # If user entered description, require short_text_1 too
                if not short_text_1 or not short_text_1.strip():
                    return JsonResponse(
                        {'success': False, 'error': 'Kurztext 1 ist erforderlich, wenn eine Beschreibung angegeben wird.'},
                        status=400
                    )

            if not tax_rate_id:
                return JsonResponse(
                    {'success': False, 'error': 'Steuersatz ist für manuelle Positionen erforderlich.'},
                    status=400
                )

            # Generate description from short texts if not provided
            if not description and short_text_1:
                parts = [short_text_1]
                if short_text_2:
                    parts.append(short_text_2)
                if long_text:
                    parts.append(long_text)
                description = '\n'.join(parts)

            # Set default empty description if still empty
            if not description:
                description = ''

            try:
                tax_rate = TaxRate.objects.get(pk=tax_rate_id)
            except TaxRate.DoesNotExist:
                return JsonResponse(
                    {'success': False, 'error': f'Ungültiger Steuersatz: Kein Steuersatz mit ID {tax_rate_id} gefunden.'},
                    status=400
                )
            is_discountable = data.get('is_discountable', True)

        try:
            if isinstance(unit_price_net, Decimal):
                unit_price_net_decimal = unit_price_net
            elif unit_price_net in (None, ''):
                unit_price_net_decimal = Decimal('0.00')
            else:
                unit_price_net_decimal = normalize_decimal_input(unit_price_net)
        except (ValueError, TypeError) as e:
            logger.warning("Ungültiger Netto-Stückpreis in add/update line request.", exc_info=True)
            return JsonResponse({'success': False, 'error': 'Ungültiger Netto-Stückpreis.'}, status=400)

        # Get unit and discount if provided
        unit_id = data.get('unit_id')
        discount = data.get('discount')

        try:
            discount_value = (
                normalize_decimal_input(discount) if discount not in (None, '') else Decimal('0.00')
            )
        except (ValueError, TypeError) as e:
            logger.warning("Ungültiger Rabatt in add/update line request.", exc_info=True)
            return JsonResponse({'success': False, 'error': 'Ungültiger Rabatt.'}, status=400)

        with transaction.atomic():
            # Get next position number
            max_position = document.lines.aggregate(max_pos=Max('position_no'))['max_pos'] or 0
            position_no = max_position + 1

            # Create line
            line = SalesDocumentLine.objects.create(
                document=document,
                item=item,
                tax_rate=tax_rate,
                position_no=position_no,
                line_type=line_type,
                is_selected=True if line_type == 'NORMAL' else data.get('is_selected', False),
                short_text_1=short_text_1,
                short_text_2=short_text_2,
                # long_text is rendered with the `|safe` filter in PDF templates, so it must be
                # bleach-sanitized. short_text_1/2 and description are always auto-escaped by
                # Django templates and are stored as plain text, so no sanitization is applied.
                long_text=sanitize_html(long_text) if long_text else '',
                description=description,
                quantity=quantity,
                unit_id=normalize_foreign_key_id(unit_id),
                unit_price_net=unit_price_net_decimal,
                discount=discount_value,
                is_discountable=is_discountable,
                kostenart1_id=normalize_foreign_key_id(kostenart1_id),
                kostenart2_id=normalize_foreign_key_id(kostenart2_id),
            )

            # Recalculate document totals
            DocumentCalculationService.recalculate(document, persist=True)
    except Http404:
        raise
    except Exception as e:
        logger.exception(f"Error adding line to document {pk}: {e}")
        return JsonResponse({'success': False, 'error': 'An internal error has occurred.'}, status=500)

    # Return line data
    return JsonResponse({
        'success': True,
        'line_id': line.pk,
        'line': {
            'id': line.pk,
            'position_no': line.position_no,
            'short_text_1': line.short_text_1,
            'short_text_2': line.short_text_2,
            'long_text': line.long_text,
            'description': line.description,
            'quantity': str(line.quantity),
            'unit_id': line.unit.pk if line.unit else None,
            'unit_price_net': str(line.unit_price_net),
            'discount': str(line.discount),
            'tax_rate': str(line.tax_rate.rate),
            'tax_rate_id': line.tax_rate.pk,
            'line_net': str(line.line_net),
            'line_tax': str(line.line_tax),
            'line_gross': str(line.line_gross),
            'kostenart1_id': line.kostenart1.pk if line.kostenart1 else None,
            'kostenart2_id': line.kostenart2.pk if line.kostenart2 else None,
        },
        'totals': {
            'total_net': str(document.total_net),
            'total_tax': str(document.total_tax),
            'total_gross': str(document.total_gross),
        }
    })


@login_required
@require_http_methods(["POST"])
def ajax_update_line(request, doc_key, pk, line_id):
    """
    AJAX endpoint to update an existing line
    
    POST parameters (JSON):
        - item_id: Item/Article ID (optional)
        - quantity: New quantity
        - unit_price_net: New unit price
        - short_text_1: Short text 1
        - short_text_2: Short text 2
        - long_text: Long text
        - description: New description
        - tax_rate_id: New tax rate ID
        - unit_id: New unit ID
        - discount: Discount percentage
        - kostenart1_id: New kostenart1 ID
        - kostenart2_id: New kostenart2 ID
    
    Returns:
        JSON: {success, line_data, totals} on success.
        Validation errors (invalid decimal, unknown tax_rate_id/item_id, empty or
        unrecognized payload) return HTTP 400 with {'success': False, 'error': ...}
        instead of a 500 and never discard the fields that were valid.
    """
    document = get_object_or_404(SalesDocument, pk=pk)

    # Parse request data - support both JSON and form-encoded data.
    # HTMX with hx-vals sends form-encoded data, while tests send JSON.
    # A JSON content-type with an unparsable/truncated body must fail loudly
    # instead of silently falling back to an empty payload (root cause of the
    # "success:True but nothing saved" no-op described in Issue #721).
    content_type = (request.content_type or '').lower()
    if 'application/json' in content_type:
        if not request.body:
            return JsonResponse({'success': False, 'error': 'Leerer Request-Body.'}, status=400)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Ungültiger JSON-Body.'}, status=400)
    else:
        try:
            data = json.loads(request.body) if request.body else {}
        except (json.JSONDecodeError, ValueError):
            # Fall back to form-encoded data (from HTMX hx-vals)
            data = request.POST.dict()

    if not data:
        return JsonResponse({'success': False, 'error': 'Keine Felder zum Aktualisieren übermittelt.'}, status=400)

    try:
        with transaction.atomic():
            # Lock the row for the duration of the read-modify-write so that
            # overlapping edits of the same line are serialized instead of
            # racing on a full-row save() (last-writer-wins over stale fields).
            line = get_object_or_404(
                SalesDocumentLine.objects.select_for_update(),
                pk=line_id, document=document
            )

            provided_short_text_1 = 'short_text_1' in data
            provided_short_text_2 = 'short_text_2' in data
            provided_long_text = 'long_text' in data
            provided_description = 'description' in data
            provided_tax_rate = 'tax_rate_id' in data
            provided_unit_price = 'unit_price_net' in data

            new_item = None
            item_changed = False

            # recognized_keys tracks which submitted keys this endpoint understood
            # (regardless of whether they changed anything); touched_fields tracks
            # which model fields actually need to be written, so save() only
            # overwrites the fields that were part of this request.
            recognized_keys = set()
            touched_fields = set()

            if 'item_id' in data:
                recognized_keys.add('item_id')
                item_id = normalize_foreign_key_id(data['item_id'])
                if item_id is not None:
                    try:
                        new_item = Item.objects.get(pk=item_id)
                    except Item.DoesNotExist:
                        raise ValueError(f'Ungültiger Artikel: Kein Artikel mit ID {item_id} gefunden.')
                    item_changed = line.item_id != new_item.pk
                    line.item = new_item
                else:
                    item_changed = line.item_id is not None
                    line.item = None
                touched_fields.add('item')
            if 'quantity' in data:
                recognized_keys.add('quantity')
                try:
                    line.quantity = normalize_decimal_input(data['quantity'])
                except (ValueError, TypeError) as e:
                    raise ValueError(f'Ungültige Menge: {e}')
                touched_fields.add('quantity')
            if 'unit_price_net' in data:
                recognized_keys.add('unit_price_net')
                try:
                    line.unit_price_net = normalize_decimal_input(data['unit_price_net'])
                except (ValueError, TypeError) as e:
                    raise ValueError(f'Ungültiger Netto-Stückpreis: {e}')
                touched_fields.add('unit_price_net')
            if 'short_text_1' in data:
                recognized_keys.add('short_text_1')
                line.short_text_1 = data['short_text_1']
                touched_fields.add('short_text_1')
            if 'short_text_2' in data:
                recognized_keys.add('short_text_2')
                line.short_text_2 = data['short_text_2']
                touched_fields.add('short_text_2')
            if 'long_text' in data:
                recognized_keys.add('long_text')
                # Log the update for debugging Issue #377
                logger.debug(f"Updating long_text for line {line_id}: old_value='{line.long_text}', new_value='{data['long_text']}'")
                # long_text is rendered with the `|safe` filter in PDF templates, so it must be
                # bleach-sanitized. short_text_1/2 and description are always auto-escaped by
                # Django templates and stored as plain text, so no sanitization is applied there.
                line.long_text = sanitize_html(data['long_text'])
                touched_fields.add('long_text')
            if 'description' in data:
                recognized_keys.add('description')
                line.description = data['description']
                touched_fields.add('description')
            if 'tax_rate_id' in data:
                recognized_keys.add('tax_rate_id')
                tax_rate_id = normalize_foreign_key_id(data['tax_rate_id'])
                if tax_rate_id is not None:
                    try:
                        line.tax_rate = TaxRate.objects.get(pk=tax_rate_id)
                    except TaxRate.DoesNotExist:
                        raise ValueError(f'Ungültiger Steuersatz: Kein Steuersatz mit ID {tax_rate_id} gefunden.')
                    touched_fields.add('tax_rate')
            if 'is_selected' in data:
                recognized_keys.add('is_selected')
                line.is_selected = data['is_selected']
                touched_fields.add('is_selected')
            if 'unit_id' in data or 'unit' in data:
                recognized_keys.update({'unit_id', 'unit'} & data.keys())
                unit_value = data.get('unit_id', data.get('unit'))
                line.unit_id = normalize_foreign_key_id(unit_value)
                touched_fields.add('unit')
            if 'discount' in data:
                recognized_keys.add('discount')
                discount_value = data['discount']
                try:
                    line.discount = (
                        normalize_decimal_input(discount_value)
                        if discount_value not in (None, '') else Decimal('0.00')
                    )
                except (ValueError, TypeError) as e:
                    raise ValueError(f'Ungültiger Rabatt: {e}')
                touched_fields.add('discount')
            if 'kostenart1_id' in data:
                recognized_keys.add('kostenart1_id')
                line.kostenart1_id = normalize_foreign_key_id(data['kostenart1_id'])
                touched_fields.add('kostenart1')
            if 'kostenart2_id' in data:
                recognized_keys.add('kostenart2_id')
                line.kostenart2_id = normalize_foreign_key_id(data['kostenart2_id'])
                touched_fields.add('kostenart2')

            if not recognized_keys:
                raise ValueError('Keine bekannten Felder in der Anfrage gefunden.')

            if item_changed and new_item:
                if not provided_short_text_1:
                    line.short_text_1 = new_item.short_text_1 or ''
                    touched_fields.add('short_text_1')
                if not provided_short_text_2:
                    line.short_text_2 = new_item.short_text_2 or ''
                    touched_fields.add('short_text_2')
                if not provided_long_text:
                    line.long_text = sanitize_html(new_item.long_text) if new_item.long_text else ''
                    touched_fields.add('long_text')
                if not provided_description:
                    description_parts = [
                        line.short_text_1,
                        line.short_text_2,
                        strip_tags(line.long_text) if line.long_text else '',
                    ]
                    line.description = '\n'.join([p for p in description_parts if p])
                    touched_fields.add('description')
                if not provided_unit_price:
                    line.unit_price_net = new_item.net_price
                    touched_fields.add('unit_price_net')
                if not provided_tax_rate:
                    line.tax_rate = TaxDeterminationService.determine_tax_rate(
                        customer=document.customer,
                        item_tax_rate=new_item.tax_rate
                    )
                    touched_fields.add('tax_rate')
                if 'is_discountable' not in data:
                    line.is_discountable = new_item.is_discountable
                    touched_fields.add('is_discountable')
                if 'kostenart1_id' not in data and new_item.cost_type_1:
                    line.kostenart1 = new_item.cost_type_1
                    touched_fields.add('kostenart1')
                if 'kostenart2_id' not in data:
                    line.kostenart2 = new_item.cost_type_2
                    touched_fields.add('kostenart2')

            # Recalculate line totals using the service before saving
            line_net, line_tax, line_gross = DocumentCalculationService.calculate_line_totals(line)
            line.line_net = line_net
            line.line_tax = line_tax
            line.line_gross = line_gross
            touched_fields.update({'line_net', 'line_tax', 'line_gross'})

            # Only write the fields this request actually touched, so an overlapping
            # save of a different field on the same line can never clobber it.
            line.save(update_fields=sorted(touched_fields))

            # Recalculate and persist document totals
            DocumentCalculationService.recalculate(document, persist=True)
    except Http404:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating line {line_id} in document {pk}: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid input.'}, status=400)
    except Exception as e:
        logger.exception(f"Error updating line {line_id} in document {pk}: {e}")
        return JsonResponse({'success': False, 'error': 'An internal error has occurred.'}, status=500)

    # Return updated line data
    return JsonResponse({
        'success': True,
        'line': {
            'id': line.pk,
            'item_id': line.item.pk if line.item else None,
            'short_text_1': line.short_text_1,
            'short_text_2': line.short_text_2,
            'long_text': line.long_text,
            'quantity': str(line.quantity),
            'unit_id': line.unit.pk if line.unit else None,
            'unit_symbol': line.unit.symbol if line.unit else '',
            'unit_price_net': str(line.unit_price_net),
            'discount': str(line.discount),
            'tax_rate_id': line.tax_rate.pk if line.tax_rate else None,
            'description': line.description,
            'line_net': str(line.line_net),
            'line_tax': str(line.line_tax),
            'line_gross': str(line.line_gross),
            'kostenart1_id': line.kostenart1.pk if line.kostenart1 else None,
            'kostenart2_id': line.kostenart2.pk if line.kostenart2 else None,
        },
        'totals': {
            'total_net': str(document.total_net),
            'total_tax': str(document.total_tax),
            'total_gross': str(document.total_gross),
        }
    })


@login_required
@require_http_methods(["POST"])
def ajax_delete_line(request, doc_key, pk, line_id):
    """
    AJAX endpoint to delete a line
    
    Returns:
        JSON: {success, totals}
    """
    try:
        document = get_object_or_404(SalesDocument, pk=pk)
        line = get_object_or_404(SalesDocumentLine, pk=line_id, document=document)
        
        line.delete()
        
        # Recalculate document totals
        DocumentCalculationService.recalculate(document, persist=True)
        
        return JsonResponse({
            'success': True,
            'totals': {
                'total_net': str(document.total_net),
                'total_tax': str(document.total_tax),
                'total_gross': str(document.total_gross),
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def ajax_get_kostenart2_options(request):
    """
    AJAX endpoint to get Kostenart2 options based on selected Kostenart1
    
    GET parameters:
        - kostenart1_id: Parent Kostenart ID (optional)
    
    Returns:
        JSON: List of child Kostenart options
        
    Note: If kostenart1_id is not provided or empty, returns an empty list
    (as Kostenart2 requires Kostenart1 to be selected first for cascading dropdown).
    """
    try:
        kostenart1_id = request.GET.get('kostenart1_id')
        
        if not kostenart1_id:
            # No parent specified - return empty list (Kostenart2 requires Kostenart1 to be selected first)
            results = []
        else:
            # Return children of the specified parent
            kostenarten = Kostenart.objects.filter(parent_id=kostenart1_id).order_by('name')
            results = [
                {
                    'id': k.pk,
                    'name': k.name,
                }
                for k in kostenarten
            ]
        
        return JsonResponse({'kostenarten': results})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def contract_list(request):
    """
    List view for contracts with filtering, sorting, and pagination.
    
    Displays a filterable, sortable, paginated list of recurring billing contracts.
    """
    # Base queryset with optimized select/prefetch
    # Show contracts from ALL companies (all users can work with all companies)
    queryset = Contract.objects.select_related(
        'customer', 'company'
    )
    
    # Apply filters
    filter_set = ContractFilter(request.GET, queryset=queryset)
    
    # Create table with filtered data
    table = ContractTable(filter_set.qs)
    
    # Set default ordering to next_run_date (ascending - operationally sensible)
    table.order_by = request.GET.get('sort', 'next_run_date')
    
    # Configure pagination (25 per page)
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    # Prepare context
    context = {
        'table': table,
        'filter': filter_set,
    }
    
    return render(request, 'auftragsverwaltung/contracts/list.html', context)


@login_required
def contract_detail(request, pk):
    """
    Detail view for a contract
    
    Shows contract header, lines, totals preview, and run history.
    Provides edit capabilities for all contract fields.
    
    Args:
        pk: Primary key of the contract
    """
    contract = get_object_or_404(Contract, pk=pk)
    
    # Get company (for now, first available)
    company = Mandant.objects.first()
    
    # Get all available customers, payment terms, tax rates, and document types
    customers = Adresse.objects.filter(adressen_type='KUNDE').order_by('name')
    payment_terms = PaymentTerm.objects.all().order_by('name')
    tax_rates = TaxRate.objects.filter(is_active=True).order_by('code')
    companies = Mandant.objects.all().order_by('name')
    document_types = DocumentType.objects.filter(is_active=True).order_by('key')
    kostenarten1 = Kostenart.objects.filter(parent__isnull=True).order_by('name')  # Main cost types only
    units = Unit.objects.all().order_by('name')  # All available units

    # Get contract lines (ordered by position_no)
    lines = contract.lines.select_related('item', 'tax_rate', 'unit', 'cost_type_1', 'cost_type_2').order_by('position_no')
    
    # Get contract runs (execution history)
    runs = contract.runs.select_related('document').order_by('-run_date')[:50]  # Last 50 runs
    
    # Get max position number for new lines
    max_position = lines.aggregate(max_pos=Max('position_no'))['max_pos'] or 0
    
    context = {
        'contract': contract,
        'lines': lines,
        'runs': runs,
        'customers': customers,
        'payment_terms': payment_terms,
        'tax_rates': tax_rates,
        'companies': companies,
        'document_types': document_types,
        'kostenarten1': kostenarten1,
        'units': units,
        'max_position': max_position,
        'is_create': False,
    }

    return render(request, 'auftragsverwaltung/contracts/detail.html', context)


@login_required
@require_POST
def contract_run_billing(request, pk):
    """
    Trigger billing run for a single contract via HTMX (POST-only).
    """
    contract = get_object_or_404(Contract, pk=pk)
    today = timezone.now().date()
    runs_created = []
    error_message = None
    
    try:
        runs_created = ContractBillingService().generate_due(today)
        status_message = "Rechnungslauf gestartet."
    except Exception as exc:
        status_message = "Fehler beim Starten des Rechnungslaufs."
        error_message = str(exc)
    
    contract.refresh_from_db()
    recent_runs = ContractRun.objects.filter(contract=contract).select_related('document').order_by('-id')[:20]
    runs_for_contract = [run for run in runs_created if getattr(run, 'contract_id', None) == contract.id]

    context = {
        'contract': contract,
        'recent_runs': recent_runs,
        'runs': recent_runs,  # Add runs for template compatibility
        'status_message': status_message,
        'error_message': error_message,
        'new_runs_count': len(runs_created),
        'contract_runs_count': len(runs_for_contract),
        'ran_at': today,
    }

    return render(request, 'auftragsverwaltung/contracts/partials/billing_result.html', context)


@login_required
@require_POST
def contracts_run_billing(request):
    """
    Trigger billing run for all due contracts via HTMX (POST-only).
    """
    today = timezone.now().date()
    runs_created = []
    error_message = None
    
    try:
        runs_created = ContractBillingService().generate_due(today)
        status_message = "Rechnungslauf gestartet."
    except Exception as exc:
        status_message = "Fehler beim Starten des Rechnungslaufs."
        error_message = str(exc)
    
    context = {
        'status_message': status_message,
        'error_message': error_message,
        'runs_created_count': len(runs_created),
        'ran_at': today,
    }
    
    return render(request, 'auftragsverwaltung/contracts/partials/billing_bulk_result.html', context)


@login_required
def contract_create(request):
    """
    Create a new contract
    
    GET: Show empty form for creating a new contract
    POST: Create the contract and redirect to detail view
    """
    company = Mandant.objects.first()
    
    if request.method == 'POST':
        # Get company from form
        company_id = request.POST.get('company_id')
        if company_id:
            company = get_object_or_404(Mandant, pk=company_id)
        else:
            company = Mandant.objects.first()
        
        # Create new contract from POST data
        contract = Contract(
            company=company,
            is_active=True,
        )
        
        # Set fields from form
        contract.name = request.POST.get('name', '')
        contract.reference = request.POST.get('reference', '')
        contract.currency = request.POST.get('currency', 'EUR')
        contract.interval = request.POST.get('interval', 'MONTHLY')
        
        # Set customer if provided
        customer_id = request.POST.get('customer_id')
        if customer_id:
            contract.customer = get_object_or_404(Adresse, pk=customer_id)
        
        # Set document type if provided
        document_type_id = request.POST.get('document_type_id')
        if document_type_id:
            contract.document_type = get_object_or_404(DocumentType, pk=document_type_id)
        
        # Set payment term if provided
        payment_term_id = request.POST.get('payment_term_id')
        if payment_term_id:
            contract.payment_term = get_object_or_404(PaymentTerm, pk=payment_term_id)
        
        # Set dates
        start_date_str = request.POST.get('start_date')
        if start_date_str:
            contract.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        end_date_str = request.POST.get('end_date')
        if end_date_str:
            contract.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        next_run_date_str = request.POST.get('next_run_date')
        if next_run_date_str:
            contract.next_run_date = datetime.strptime(next_run_date_str, '%Y-%m-%d').date()
        
        # Set is_active flag
        contract.is_active = request.POST.get('is_active') == 'on'
        
        # Save the contract
        contract.save()
        
        # Log activity
        ActivityStreamService.add(
            company=company,
            domain='ORDER',
            activity_type='CONTRACT_CREATED',
            title=f'Vertrag erstellt: {contract.name}',
            description=f'Kunde: {contract.customer.matchkey}' if contract.customer else None,
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
        
        # Redirect to detail view
        return redirect('auftragsverwaltung:contract_detail', pk=contract.pk)
    
    # GET: Show empty form
    customers = Adresse.objects.filter(adressen_type='KUNDE').order_by('name')
    payment_terms = PaymentTerm.objects.all().order_by('name')
    tax_rates = TaxRate.objects.filter(is_active=True).order_by('code')
    companies = Mandant.objects.all().order_by('name')
    document_types = DocumentType.objects.filter(is_active=True).order_by('key')
    kostenarten1 = Kostenart.objects.filter(parent__isnull=True).order_by('name')
    
    context = {
        'contract': None,
        'lines': [],
        'runs': [],
        'customers': customers,
        'payment_terms': payment_terms,
        'tax_rates': tax_rates,
        'companies': companies,
        'document_types': document_types,
        'kostenarten1': kostenarten1,
        'max_position': 0,
        'is_create': True,
    }
    
    return render(request, 'auftragsverwaltung/contracts/detail.html', context)


@login_required
@require_POST
def contract_update(request, pk):
    """
    Update an existing contract
    
    POST: Update contract fields and redirect to detail view
    
    Args:
        pk: Primary key of the contract
    """
    contract = get_object_or_404(Contract, pk=pk)
    
    # Track changes for activity logging
    old_is_active = contract.is_active
    old_customer = contract.customer
    old_customer_name = contract.customer.matchkey if contract.customer else None
    
    # Update fields from form
    contract.name = request.POST.get('name', '')
    contract.reference = request.POST.get('reference', '')
    contract.currency = request.POST.get('currency', 'EUR')
    contract.interval = request.POST.get('interval', 'MONTHLY')
    
    # Update customer if provided
    customer_id = request.POST.get('customer_id')
    if customer_id:
        contract.customer = get_object_or_404(Adresse, pk=customer_id)
    
    # Update document type if provided
    document_type_id = request.POST.get('document_type_id')
    if document_type_id:
        contract.document_type = get_object_or_404(DocumentType, pk=document_type_id)
    
    # Update payment term if provided
    payment_term_id = request.POST.get('payment_term_id')
    if payment_term_id:
        contract.payment_term = get_object_or_404(PaymentTerm, pk=payment_term_id)
    else:
        contract.payment_term = None
    
    # Update dates
    start_date_str = request.POST.get('start_date')
    if start_date_str:
        contract.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    
    end_date_str = request.POST.get('end_date')
    if end_date_str:
        contract.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        contract.end_date = None
    
    next_run_date_str = request.POST.get('next_run_date')
    if next_run_date_str:
        contract.next_run_date = datetime.strptime(next_run_date_str, '%Y-%m-%d').date()
    
    # Update is_active flag
    new_is_active = request.POST.get('is_active') == 'on'
    contract.is_active = new_is_active
    
    # Save the contract
    contract.save()
    
    # Log specific activities for business-relevant changes
    
    # 1. Log status change if it occurred
    if old_is_active != new_is_active:
        status_text = 'aktiviert' if new_is_active else 'deaktiviert'
        ActivityStreamService.add(
            company=contract.company,
            domain='ORDER',
            activity_type='CONTRACT_STATUS_CHANGED',
            title=f'Vertragsstatus geändert: {contract.name}',
            description=f'Status: {status_text} (vorher: {"aktiv" if old_is_active else "inaktiv"})',
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
    
    # 2. Log customer assignment change if it occurred
    if old_customer != contract.customer:
        new_customer_name = contract.customer.matchkey if contract.customer else None
        ActivityStreamService.add(
            company=contract.company,
            domain='ORDER',
            activity_type='CONTRACT_CUSTOMER_CHANGED',
            title=f'Kunde geändert: {contract.name}',
            description=f'Neuer Kunde: {new_customer_name}, Vorheriger Kunde: {old_customer_name}',
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
    
    # 3. Log general update (if no specific change was logged)
    if old_is_active == new_is_active and old_customer == contract.customer:
        ActivityStreamService.add(
            company=contract.company,
            domain='ORDER',
            activity_type='CONTRACT_UPDATED',
            title=f'Vertrag aktualisiert: {contract.name}',
            description=f'Kunde: {contract.customer.matchkey}' if contract.customer else None,
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
    
    # Redirect to detail view
    return redirect('auftragsverwaltung:contract_detail', pk=contract.pk)


# ============================================================================
# Contract AJAX Endpoints
# ============================================================================

@login_required
@require_http_methods(["POST"])
def ajax_contract_add_line(request, pk):
    """
    AJAX endpoint to add a new line to a contract
    
    POST parameters (JSON):
        - item_id: Item/Article ID (optional for manual lines)
        - quantity: Quantity
        - short_text_1: Primary short text (required for manual lines; leading field)
        - short_text_2: Optional second short text
        - long_text: Optional long text (sanitized)
        - description: Legacy fallback; otherwise generated from the short texts
        - unit_id: Unit of measure ID (optional)
        - unit_price_net: Unit price (required for manual lines)
        - tax_rate_id: Tax rate ID (required)
        - cost_type_1_id: Cost type 1 ID (optional)
        - cost_type_2_id: Cost type 2 ID (optional)
        - is_discountable: Whether the line is discountable (default: True)

    Returns:
        JSON: {success, line_id, line_data, preview_totals}
    """
    try:
        contract = get_object_or_404(Contract, pk=pk)

        # Parse JSON body
        data = json.loads(request.body)

        item_id = data.get('item_id')
        description = data.get('description', '')
        short_text_1 = data.get('short_text_1', '')
        short_text_2 = data.get('short_text_2', '')
        long_text = data.get('long_text', '')
        unit_id = data.get('unit_id')
        tax_rate_id = data.get('tax_rate_id')
        cost_type_1_id = data.get('cost_type_1_id')
        cost_type_2_id = data.get('cost_type_2_id')
        is_discountable = data.get('is_discountable', True)
        
        # Parse and normalize decimal fields with error handling
        try:
            quantity = normalize_decimal_input(data.get('quantity', '1.0'))
        except (ValueError, TypeError) as e:
            return JsonResponse({'error': f'Ungültige Menge: {str(e)}'}, status=400)
        
        unit_price_net = data.get('unit_price_net')
        
        # Determine line data based on whether item is provided
        if item_id:
            # Article-based line
            item = get_object_or_404(Item, pk=item_id)

            # Use item data as fallback for any text field the caller did not supply
            if not short_text_1:
                short_text_1 = item.short_text_1
            if not short_text_2:
                short_text_2 = item.short_text_2
            if not long_text:
                long_text = item.long_text
            if not unit_price_net:
                unit_price_net = item.net_price  # Already a Decimal from the model

            # Use item's tax rate if not provided
            if not tax_rate_id and item.tax_rate:
                tax_rate_id = item.tax_rate.pk

            # Use item's cost types if not provided
            if not cost_type_1_id and item.kostenart1:
                cost_type_1_id = item.kostenart1.pk
            if not cost_type_2_id and item.kostenart2:
                cost_type_2_id = item.kostenart2.pk

            is_discountable = item.is_discountable
        else:
            # Manual line - ensure required fields are present.
            # Backward compatibility: legacy callers may still send only `description`.
            # Seed the leading text fields from it so no text is lost.
            if not short_text_1 and description:
                first_line = description.split('\n', 1)[0].strip()
                short_text_1 = first_line[:200]
                if not long_text and ('\n' in description or len(first_line) > 200):
                    long_text = description
            if not short_text_1:
                return JsonResponse({'error': 'Kurztext 1 ist erforderlich'}, status=400)
            if not unit_price_net:
                return JsonResponse({'error': 'Netto-Stückpreis ist erforderlich'}, status=400)

        # Generate description consistently from the short texts. It is a secondary
        # display field and must never replace short_text_1.
        description = _build_contract_line_description(short_text_1, short_text_2, long_text)

        # Ensure tax rate is provided
        if not tax_rate_id:
            return JsonResponse({'error': 'Steuersatz ist erforderlich'}, status=400)
        
        # Normalize unit_price_net (might be from item or from input)
        try:
            if isinstance(unit_price_net, Decimal):
                unit_price_net_decimal = unit_price_net
            else:
                unit_price_net_decimal = normalize_decimal_input(unit_price_net)
        except (ValueError, TypeError) as e:
            return JsonResponse({'error': f'Ungültiger Netto-Stückpreis: {str(e)}'}, status=400)
        
        # Get tax rate
        tax_rate = get_object_or_404(TaxRate, pk=tax_rate_id)
        
        # Get next position number
        max_position = contract.lines.aggregate(max_pos=Max('position_no'))['max_pos'] or 0
        position_no = max_position + 1
        
        # Create new contract line
        line = ContractLine.objects.create(
            contract=contract,
            item_id=item_id if item_id else None,
            position_no=position_no,
            short_text_1=short_text_1,
            short_text_2=short_text_2,
            # long_text is rendered with the `|safe` filter in PDF templates, so it must be
            # bleach-sanitized. short_text_1/2 and description are always auto-escaped by
            # Django templates and stored as plain text, so no sanitization is applied there.
            long_text=sanitize_html(long_text) if long_text else '',
            description=description,
            unit_id=normalize_foreign_key_id(unit_id),
            quantity=quantity,
            unit_price_net=unit_price_net_decimal,
            tax_rate=tax_rate,
            cost_type_1_id=normalize_foreign_key_id(cost_type_1_id),
            cost_type_2_id=normalize_foreign_key_id(cost_type_2_id),
            is_discountable=is_discountable,
        )
        
        # Calculate preview totals
        preview_totals = _calculate_contract_preview_totals(contract)
        
        # Log activity
        description_preview = (line.description[:97] + '...' if len(line.description) > 100 else line.description) if line.description else None
        ActivityStreamService.add(
            company=contract.company,
            domain='ORDER',
            activity_type='CONTRACT_LINE_ADDED',
            title=f'Vertragsposition hinzugefügt: {contract.name}',
            description=f'Position: {description_preview}' if description_preview else None,
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
        
        # Return success with line data
        return JsonResponse({
            'success': True,
            'line': {
                'id': line.pk,
                'position_no': line.position_no,
                'short_text_1': line.short_text_1,
                'short_text_2': line.short_text_2,
                'long_text': line.long_text,
                'description': line.description,
                'unit_id': line.unit.pk if line.unit else None,
                'unit_code': line.unit.code if line.unit else '',
                'quantity': str(line.quantity),
                'unit_price_net': str(line.unit_price_net),
                'tax_rate_id': line.tax_rate.pk,
                'tax_rate_code': line.tax_rate.code,
                'tax_rate_rate': str(line.tax_rate.rate),
                'cost_type_1_id': line.cost_type_1.pk if line.cost_type_1 else None,
                'cost_type_2_id': line.cost_type_2.pk if line.cost_type_2 else None,
                'is_discountable': line.is_discountable,
                'item_id': line.item.pk if line.item else None,
            },
            'preview_totals': preview_totals,
        })
    except ValueError as e:
        # Validation errors should return 400
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        # Unexpected errors return 500
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ajax_contract_update_line(request, pk, line_id):
    """
    AJAX endpoint to update an existing contract line
    
    POST parameters (JSON):
        - quantity: New quantity
        - unit_price_net: New unit price
        - short_text_1: New primary short text (leading field)
        - short_text_2: New second short text
        - long_text: New long text (sanitized)
        - description: Legacy field; regenerated from the short texts when those change
        - unit_id: New unit of measure ID
        - tax_rate_id: New tax rate ID
        - cost_type_1_id: New cost type 1 ID
        - cost_type_2_id: New cost type 2 ID
        - is_discountable: Whether the line is discountable
    
    Returns:
        JSON: {success, line_data, preview_totals}
    """
    try:
        contract = get_object_or_404(Contract, pk=pk)
        line = get_object_or_404(ContractLine, pk=line_id, contract=contract)
        
        # Parse JSON body
        data = json.loads(request.body)
        
        # Update fields with proper decimal normalization
        if 'quantity' in data:
            try:
                line.quantity = normalize_decimal_input(data['quantity'])
            except (ValueError, TypeError) as e:
                return JsonResponse({'error': f'Ungültige Menge: {str(e)}'}, status=400)
        
        if 'unit_price_net' in data:
            try:
                line.unit_price_net = normalize_decimal_input(data['unit_price_net'])
            except (ValueError, TypeError) as e:
                return JsonResponse({'error': f'Ungültiger Netto-Stückpreis: {str(e)}'}, status=400)
        
        if 'short_text_1' in data:
            line.short_text_1 = data['short_text_1']
        if 'short_text_2' in data:
            line.short_text_2 = data['short_text_2']
        if 'long_text' in data:
            # long_text is rendered with the `|safe` filter in PDF templates, so it must be
            # bleach-sanitized. short_text_1/2 and description are always auto-escaped by
            # Django templates and stored as plain text, so no sanitization is applied there.
            line.long_text = sanitize_html(data['long_text'])
        # Regenerate the (secondary) description from the short texts whenever any of
        # them changed. description never replaces short_text_1.
        if 'short_text_1' in data or 'short_text_2' in data or 'long_text' in data:
            line.description = _build_contract_line_description(
                line.short_text_1, line.short_text_2, line.long_text
            )
        elif 'description' in data:
            line.description = data['description']
        if 'unit_id' in data:
            line.unit_id = normalize_foreign_key_id(data['unit_id'])
        if 'tax_rate_id' in data:
            line.tax_rate = get_object_or_404(TaxRate, pk=data['tax_rate_id'])
        if 'is_discountable' in data:
            line.is_discountable = data['is_discountable']
        if 'cost_type_1_id' in data:
            line.cost_type_1_id = normalize_foreign_key_id(data['cost_type_1_id'])
        if 'cost_type_2_id' in data:
            line.cost_type_2_id = normalize_foreign_key_id(data['cost_type_2_id'])
        
        line.save()
        
        # Calculate preview totals
        preview_totals = _calculate_contract_preview_totals(contract)
        
        # Log activity
        description_preview = (line.description[:97] + '...' if len(line.description) > 100 else line.description) if line.description else None
        ActivityStreamService.add(
            company=contract.company,
            domain='ORDER',
            activity_type='CONTRACT_LINE_UPDATED',
            title=f'Vertragsposition aktualisiert: {contract.name}',
            description=f'Position: {description_preview}' if description_preview else None,
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
        
        # Return updated line data
        return JsonResponse({
            'success': True,
            'line': {
                'id': line.pk,
                'quantity': str(line.quantity),
                'unit_price_net': str(line.unit_price_net),
                'short_text_1': line.short_text_1,
                'short_text_2': line.short_text_2,
                'long_text': line.long_text,
                'description': line.description,
                'unit_id': line.unit.pk if line.unit else None,
                'unit_code': line.unit.code if line.unit else '',
                'tax_rate_id': line.tax_rate.pk,
                'tax_rate_code': line.tax_rate.code,
                'tax_rate_rate': str(line.tax_rate.rate),
                'cost_type_1_id': line.cost_type_1.pk if line.cost_type_1 else None,
                'cost_type_2_id': line.cost_type_2.pk if line.cost_type_2 else None,
                'is_discountable': line.is_discountable,
            },
            'preview_totals': preview_totals,
        })
    except ValueError as e:
        # Validation errors should return 400
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        # Unexpected errors return 500
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ajax_contract_delete_line(request, pk, line_id):
    """
    AJAX endpoint to delete a contract line
    
    Returns:
        JSON: {success, preview_totals}
    """
    try:
        contract = get_object_or_404(Contract, pk=pk)
        line = get_object_or_404(ContractLine, pk=line_id, contract=contract)
        
        line_desc = line.description[:50]
        line.delete()
        
        # Calculate preview totals
        preview_totals = _calculate_contract_preview_totals(contract)
        
        # Log activity
        ActivityStreamService.add(
            company=contract.company,
            domain='ORDER',
            activity_type='CONTRACT_LINE_DELETED',
            title=f'Vertragsposition gelöscht: {contract.name}',
            description=f'Position: {line_desc}' if line_desc else None,
            target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
            actor=request.user,
            severity='INFO'
        )
        
        return JsonResponse({
            'success': True,
            'preview_totals': preview_totals,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def ajax_contract_calculate_next_run_date(request, pk):
    """
    AJAX endpoint to calculate the next run date based on interval and start date
    
    GET parameters:
        - interval: Interval (MONTHLY, QUARTERLY, SEMI_ANNUAL, ANNUAL)
        - start_date: Start date (YYYY-MM-DD)
        - current_next_run_date: Current next run date (YYYY-MM-DD, optional)
    
    Returns:
        JSON: {success, next_run_date}
    """
    try:
        contract = get_object_or_404(Contract, pk=pk)
        
        interval = request.GET.get('interval', contract.interval)
        start_date_str = request.GET.get('start_date')
        current_next_run_date_str = request.GET.get('current_next_run_date')
        
        # Parse start date
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = contract.start_date
        
        # Determine base date for calculation
        if current_next_run_date_str:
            base_date = datetime.strptime(current_next_run_date_str, '%Y-%m-%d').date()
        else:
            base_date = start_date
        
        # Calculate next run date based on interval
        if interval == 'MONTHLY':
            next_run_date = base_date + relativedelta(months=1)
        elif interval == 'QUARTERLY':
            next_run_date = base_date + relativedelta(months=3)
        elif interval == 'SEMI_ANNUAL':
            next_run_date = base_date + relativedelta(months=6)
        elif interval == 'ANNUAL':
            next_run_date = base_date + relativedelta(years=1)
        else:
            return JsonResponse({'error': 'Ungültiges Intervall'}, status=400)
        
        return JsonResponse({
            'success': True,
            'next_run_date': next_run_date.strftime('%Y-%m-%d'),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _calculate_contract_preview_totals(contract):
    """
    Calculate preview totals for a contract based on its lines
    
    Args:
        contract: Contract instance
    
    Returns:
        dict: Preview totals (total_net, total_tax, total_gross)
    """
    lines = contract.lines.select_related('tax_rate').all()
    
    total_net = Decimal('0.00')
    total_tax = Decimal('0.00')
    
    for line in lines:
        # Calculate line total (net)
        line_total_net = (line.quantity * line.unit_price_net).quantize(Decimal('0.01'))
        
        # Calculate line tax (rate is already decimal, e.g. 0.19 for 19%)
        line_tax = (line_total_net * line.tax_rate.rate).quantize(Decimal('0.01'))
        
        total_net += line_total_net
        total_tax += line_tax
    
    total_gross = total_net + total_tax
    
    return {
        'total_net': str(total_net),
        'total_tax': str(total_tax),
        'total_gross': str(total_gross),
    }


# ============================================================================
# TextTemplate Views
# ============================================================================

@login_required
def texttemplate_list(request):
    """
    List view for text templates (Textbausteine).
    
    Displays a filterable, sortable, paginated list of text templates.
    Shows templates for all companies (all users can work with all companies).
    """
    # Base queryset - show text templates from ALL companies
    queryset = TextTemplate.objects.select_related('company')
    
    # Apply filters
    filter_set = TextTemplateFilter(request.GET, queryset=queryset)
    
    # Create table with filtered data
    table = TextTemplateTable(filter_set.qs)
    
    # Set default ordering
    table.order_by = request.GET.get('sort', 'type,sort_order,title')
    
    # Configure pagination (25 per page)
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    # Prepare context
    context = {
        'table': table,
        'filter': filter_set,
    }
    
    return render(request, 'auftragsverwaltung/texttemplates/list.html', context)


@login_required
def texttemplate_create(request):
    """
    Create view for text template.
    """
    # Get the default company
    try:
        company = Mandant.objects.first()
    except Mandant.DoesNotExist:
        return redirect('auftragsverwaltung:texttemplate_list')
    
    if request.method == 'POST':
        # Extract form data
        key = request.POST.get('key', '').strip()
        title = request.POST.get('title', '').strip()
        type = request.POST.get('type', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        try:
            sort_order = int(request.POST.get('sort_order', '0'))
        except (ValueError, TypeError):
            sort_order = 0
        
        # Create text template with sanitized HTML content
        template = TextTemplate.objects.create(
            company=company,
            key=key,
            title=title,
            type=type,
            content=sanitize_html(request.POST.get('content', '').strip()),
            is_active=is_active,
            sort_order=sort_order
        )
        
        return redirect('auftragsverwaltung:texttemplate_list')
    
    # GET request - show form
    context = {
        'type_choices': TextTemplate.TYPE_CHOICES,
    }
    
    return render(request, 'auftragsverwaltung/texttemplates/form.html', context)


@login_required
def texttemplate_update(request, pk):
    """
    Update view for text template.
    """
    template = get_object_or_404(TextTemplate, pk=pk)
    
    if request.method == 'POST':
        # Extract form data
        template.key = request.POST.get('key', '').strip()
        template.title = request.POST.get('title', '').strip()
        template.type = request.POST.get('type', '').strip()
        template.is_active = request.POST.get('is_active') == 'on'
        
        try:
            template.sort_order = int(request.POST.get('sort_order', '0'))
        except (ValueError, TypeError):
            template.sort_order = 0
        
        # Sanitize HTML content
        template.content = sanitize_html(request.POST.get('content', '').strip())
        
        template.save()
        
        return redirect('auftragsverwaltung:texttemplate_list')
    
    # GET request - show form
    context = {
        'template': template,
        'type_choices': TextTemplate.TYPE_CHOICES,
    }
    
    return render(request, 'auftragsverwaltung/texttemplates/form.html', context)


@login_required
def texttemplate_delete(request, pk):
    """
    Delete view for text template.
    """
    template = get_object_or_404(TextTemplate, pk=pk)
    
    if request.method == 'POST':
        template.delete()
        
        return redirect('auftragsverwaltung:texttemplate_list')
    
    # GET request - show confirmation
    context = {
        'template': template,
    }
    
    return render(request, 'auftragsverwaltung/texttemplates/delete_confirm.html', context)


# ===============================================================================
# Outgoing Invoice Journal Views (Read-Only)
# ===============================================================================

@login_required
def journal_list(request):
    """
    List view for Outgoing Invoice Journal Entries (read-only).
    
    Displays a filterable, sortable, paginated list of journal entries.
    This is a read-only view - no create/update/delete operations.
    Shows journal entries from all companies (all users can work with all companies).
    """
    # Base queryset with optimized select/prefetch - from ALL companies
    queryset = OutgoingInvoiceJournalEntry.objects.select_related(
        'company', 'document'
    )
    
    # Apply filters
    filter_set = OutgoingInvoiceJournalFilter(request.GET, queryset=queryset)
    
    # Create table with filtered data
    table = OutgoingInvoiceJournalTable(filter_set.qs)
    
    # Set default ordering to -document_number (descending)
    table.order_by = request.GET.get('sort', '-document_number')
    
    # Configure pagination (25 per page)
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    # Prepare context
    context = {
        'table': table,
        'filter': filter_set,
    }
    
    return render(request, 'auftragsverwaltung/journal/list.html', context)


@login_required
def journal_detail(request, pk):
    """
    Detail view for an Outgoing Invoice Journal Entry (read-only).
    
    Shows all journal entry fields in a read-only format.
    No edit capabilities - this is a pure display view.
    
    Args:
        pk: Primary key of the journal entry
    """
    entry = get_object_or_404(
        OutgoingInvoiceJournalEntry.objects.select_related('company', 'document'),
        pk=pk
    )
    
    # Calculate total net amount for display
    total_net = entry.net_0 + entry.net_7 + entry.net_19
    
    context = {
        'entry': entry,
        'total_net': total_net,
    }
    
    return render(request, 'auftragsverwaltung/journal/detail.html', context)


@login_required
@require_http_methods(["GET"])
def document_pdf(request, pk):
    """
    Generate and download PDF for a SalesDocument.
    
    Generates a PDF invoice using the Core Printing Framework and returns it
    as a downloadable file.
    
    Args:
        request: HTTP request
        pk: Primary key of the SalesDocument
        
    Returns:
        HttpResponse with PDF content
    """
    # Get document with related data
    document = get_object_or_404(
        SalesDocument.objects.select_related(
            'company',
            'customer',
            'document_type'
        ),
        pk=pk
    )
    
    # Note: Company-level permission checks should be added in a future enhancement
    # to ensure users can only access documents from their authorized companies.
    # For now, we rely on @login_required decorator which is consistent
    # with other views in this module.
    
    # Build context using context builder
    context_builder = SalesDocumentInvoiceContextBuilder()
    context = context_builder.build_context(document)
    template_name = context_builder.get_template_name(document)
    
    # Get base URL for static assets using the utility function
    # This handles both development (with app-specific static dirs) and production (with STATIC_ROOT)
    base_url = get_static_base_url()
    
    # Generate PDF
    pdf_service = PdfRenderService()
    
    # Sanitize document number for filename (remove/replace unsafe characters)
    safe_number = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in document.number)
    
    result = pdf_service.render(
        template_name=template_name,
        context=context,
        base_url=base_url,
        filename=f'Rechnung_{safe_number}.pdf'
    )
    
    # Return PDF as HTTP response
    response = HttpResponse(result.pdf_bytes, content_type=result.content_type)
    response['Content-Disposition'] = f'inline; filename="{result.filename}"'
    
    logger.info(f"Generated PDF for document {document.number} ({len(result.pdf_bytes)} bytes)")

    return response


@login_required
@require_POST
def documents_bulk_print(request, doc_key):
    """
    Generate a merged PDF for multiple selected documents.

    Args:
        request: HTTP request with POST data containing 'document_ids[]'
        doc_key: The document type key (e.g., 'quote', 'order', 'invoice')

    Returns:
        HttpResponse with merged PDF content or error message
    """
    from pypdf import PdfWriter, PdfReader
    from io import BytesIO

    # Get document IDs from POST data
    document_ids = request.POST.getlist('document_ids[]')

    if not document_ids:
        return JsonResponse({
            'success': False,
            'error': 'Keine Dokumente ausgewählt.'
        }, status=400)

    # Validate document_ids are integers
    try:
        document_ids = [int(doc_id) for doc_id in document_ids]
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Ungültige Dokument-IDs.'
        }, status=400)

    # Get the document type
    document_type = get_object_or_404(DocumentType, key=doc_key, is_active=True)

    # Get all selected documents with validation
    documents = SalesDocument.objects.select_related(
        'company', 'customer', 'document_type'
    ).filter(
        pk__in=document_ids,
        document_type=document_type
    ).order_by('issue_date', 'number')

    if not documents.exists():
        return JsonResponse({
            'success': False,
            'error': 'Keine gültigen Dokumente gefunden.'
        }, status=404)

    # Initialize context builder and PDF service
    context_builder = SalesDocumentInvoiceContextBuilder()
    pdf_service = PdfRenderService()
    base_url = get_static_base_url()

    # Create PDF merger
    pdf_writer = PdfWriter()

    # Generate and merge PDFs for each document
    for document in documents:
        try:
            # Build context and get template
            context = context_builder.build_context(document)
            template_name = context_builder.get_template_name(document)

            # Generate PDF for this document
            result = pdf_service.render(
                template_name=template_name,
                context=context,
                base_url=base_url,
                filename=f'{document.number}.pdf'
            )

            # Add to merger
            pdf_reader = PdfReader(BytesIO(result.pdf_bytes))
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

        except Exception as e:
            logger.error(f"Error generating PDF for document {document.number}: {e}")
            # Continue with other documents
            continue

    # Check if we have any pages
    if len(pdf_writer.pages) == 0:
        return JsonResponse({
            'success': False,
            'error': 'Fehler beim Erstellen der PDFs.'
        }, status=500)

    # Write merged PDF to bytes
    output_buffer = BytesIO()
    pdf_writer.write(output_buffer)
    merged_pdf_bytes = output_buffer.getvalue()

    # Generate filename
    filename = f'{document_type.name}_Sammeldruck_{len(documents)}_Dokumente.pdf'

    # Return merged PDF
    response = HttpResponse(merged_pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    logger.info(f"Generated merged PDF for {len(documents)} documents ({len(merged_pdf_bytes)} bytes)")

    return response


@login_required
@require_POST
def invoice_finalize(request, pk):
    """
    Finalize an invoice (Echtdruck): assign number, set status to SENT, and download PDF.

    This is an idempotent operation:
    - If invoice already has a number, it won't be changed
    - Status is set to SENT
    - PDF is generated and returned for download

    Args:
        request: HTTP request
        pk: Primary key of the SalesDocument (must be an invoice)

    Returns:
        HttpResponse with PDF content (triggers download)
    """
    from auftragsverwaltung.services.invoice_finalization import finalize_invoice

    # Get invoice with related data
    document = get_object_or_404(
        SalesDocument.objects.select_related(
            'company',
            'customer',
            'document_type'
        ),
        pk=pk
    )

    # Validate this is an invoice
    if not document.document_type.is_invoice:
        return JsonResponse({
            'success': False,
            'error': f'Dokument ist keine Rechnung (Typ: {document.document_type.name})'
        }, status=400)

    try:
        # Finalize invoice
        document, was_modified = finalize_invoice(document)

        # Log activity
        if was_modified:
            ActivityStreamService.add(
                company=document.company,
                domain='ORDER',
                activity_type='INVOICE_FINALIZED',
                title=f'Rechnung finalisiert: {document.number}',
                description=f'Echtdruck durchgeführt, Status: {document.get_status_display()}',
                target_url=reverse('auftragsverwaltung:document_detail', kwargs={'doc_key': document.document_type.key, 'pk': document.pk}),
                actor=request.user,
                severity='INFO'
            )
            logger.info(f"Invoice {document.number} finalized by {request.user.username}")

        # Generate PDF for download
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(document)
        template_name = context_builder.get_template_name(document)
        base_url = get_static_base_url()

        pdf_service = PdfRenderService()
        safe_number = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in (document.number or 'Entwurf'))

        result = pdf_service.render(
            template_name=template_name,
            context=context,
            base_url=base_url,
            filename=f'Rechnung_{safe_number}.pdf'
        )

        # Return PDF as downloadable file
        response = HttpResponse(result.pdf_bytes, content_type=result.content_type)
        response['Content-Disposition'] = f'inline; filename="{result.filename}"'

        logger.info(f"Invoice {document.number} finalized and PDF generated by {request.user.username}")

        return response

    except ValueError as e:
        logger.warning(f"Invoice finalization failed: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    except Exception as e:
        logger.error(f"Unexpected error during invoice finalization: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Finalisieren: {str(e)}'
        }, status=500)


@login_required
@require_POST
def invoice_send_email(request, pk):
    """
    Send invoice via email to customer with PDF attachment.

    Also sends a copy to internal accounting (template sender).
    Automatically finalizes the invoice if not already done.

    Args:
        request: HTTP request
        pk: Primary key of the SalesDocument (must be an invoice)

    Returns:
        JsonResponse with success status and recipient list
    """
    from auftragsverwaltung.services.invoice_email import send_invoice_email, InvoiceEmailError

    # Get invoice with related data
    document = get_object_or_404(
        SalesDocument.objects.select_related(
            'company',
            'customer',
            'document_type'
        ),
        pk=pk
    )

    # Validate this is an invoice
    if not document.document_type.is_invoice:
        return JsonResponse({
            'success': False,
            'error': f'Dokument ist keine Rechnung (Typ: {document.document_type.name})'
        }, status=400)

    try:
        # Send email (also finalizes invoice if needed)
        result = send_invoice_email(
            invoice=document,
            to_customer=True,
            to_internal=True,  # Send copy to accounting
            request=request
        )

        # Log activity
        ActivityStreamService.add(
            company=document.company,
            domain='ORDER',
            activity_type='INVOICE_SENT',
            title=f'Rechnung versendet: {document.number}',
            description=f'An: {", ".join(result["recipients"])}',
            target_url=reverse('auftragsverwaltung:document_detail', kwargs={'doc_key': document.document_type.key, 'pk': document.pk}),
            actor=request.user,
            severity='INFO'
        )

        logger.info(f"Invoice {document.number} sent to {result['recipients']} by {request.user.username}")

        return JsonResponse({
            'success': True,
            'invoice_number': document.number,
            'recipients': result['recipients'],
        })

    except InvoiceEmailError as e:
        logger.warning(f"Invoice email failed: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    except Exception as e:
        logger.error(f"Unexpected error during invoice email: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Versenden: {str(e)}'
        }, status=500)


@login_required
@require_POST
def invoice_print_internal(request, pk):
    """
    Print invoice (download PDF) and send internal copy to accounting.

    This downloads the PDF for the user and sends an email copy to
    internal accounting only (not to the customer).

    Args:
        request: HTTP request
        pk: Primary key of the SalesDocument (must be an invoice)

    Returns:
        HttpResponse with PDF content (triggers download)
    """
    from auftragsverwaltung.services.invoice_email import send_invoice_email, InvoiceEmailError

    # Get invoice with related data
    document = get_object_or_404(
        SalesDocument.objects.select_related(
            'company',
            'customer',
            'document_type'
        ),
        pk=pk
    )

    # Validate this is an invoice
    if not document.document_type.is_invoice:
        return JsonResponse({
            'success': False,
            'error': f'Dokument ist keine Rechnung (Typ: {document.document_type.name})'
        }, status=400)

    try:
        # Send internal email in background (don't fail if it errors)
        try:
            send_invoice_email(
                invoice=document,
                to_customer=False,
                to_internal=True,  # Only to accounting
                request=request
            )
            logger.info(f"Invoice {document.number} internal email sent by {request.user.username}")
        except InvoiceEmailError as e:
            # Log but don't fail the print operation
            logger.warning(f"Internal email failed for invoice {document.number}: {str(e)}")

        # Generate PDF for download
        context_builder = SalesDocumentInvoiceContextBuilder()
        context = context_builder.build_context(document)
        template_name = context_builder.get_template_name(document)
        base_url = get_static_base_url()

        pdf_service = PdfRenderService()
        safe_number = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in (document.number or 'Entwurf'))

        result = pdf_service.render(
            template_name=template_name,
            context=context,
            base_url=base_url,
            filename=f'Rechnung_{safe_number}.pdf'
        )

        # Log activity
        ActivityStreamService.add(
            company=document.company,
            domain='ORDER',
            activity_type='INVOICE_PRINTED',
            title=f'Rechnung gedruckt: {document.number or "Entwurf"}',
            description='PDF heruntergeladen und interne Kopie versendet',
            target_url=reverse('auftragsverwaltung:document_detail', kwargs={'doc_key': document.document_type.key, 'pk': document.pk}),
            actor=request.user,
            severity='INFO'
        )

        # Return PDF as downloadable file
        response = HttpResponse(result.pdf_bytes, content_type=result.content_type)
        response['Content-Disposition'] = f'attachment; filename="{result.filename}"'

        logger.info(f"Invoice {document.number or 'draft'} printed by {request.user.username}")

        return response

    except Exception as e:
        logger.error(f"Unexpected error during invoice print: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Fehler beim Drucken: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def document_preview(request, pk):
    """
    Generate and preview PDF for a SalesDocument (read-only, no side effects).
    
    Generates a PDF preview using the Core Printing Framework and returns it
    for inline display in a new browser tab. This is a read-only operation with
    no side effects:
    - No finalization (no status change)
    - No number assignment
    - No snapshot creation/storage
    - No database writes
    
    Args:
        request: HTTP request
        pk: Primary key of the SalesDocument
        
    Returns:
        HttpResponse with PDF content for inline preview
    """
    # Get document with related data (read-only)
    document = get_object_or_404(
        SalesDocument.objects.select_related(
            'company',
            'customer',
            'document_type'
        ),
        pk=pk
    )
    
    # Note: Company-level permission checks should be added in a future enhancement
    # to ensure users can only access documents from their authorized companies.
    # For now, we rely on @login_required decorator which is consistent
    # with other views in this module.
    
    # Build context using context builder (read-only)
    context_builder = SalesDocumentInvoiceContextBuilder()
    context = context_builder.build_context(document)
    template_name = context_builder.get_template_name(document)
    
    # Get base URL for static assets using the utility function
    # This handles both development (with app-specific static dirs) and production (with STATIC_ROOT)
    base_url = get_static_base_url()
    
    # Generate PDF (read-only, no persistence)
    pdf_service = PdfRenderService()
    
    # Build filename using document type name and ID (no number assignment)
    filename = f"{document.document_type.name}_{document.id}.pdf"
    
    result = pdf_service.render(
        template_name=template_name,
        context=context,
        base_url=base_url,
        filename=filename
    )
    
    # Return PDF as HTTP response with inline disposition for browser preview
    response = HttpResponse(result.pdf_bytes, content_type=result.content_type)
    response['Content-Disposition'] = f'inline; filename="{result.filename}"'
    
    logger.info(f"Generated preview PDF for document ID {document.id} ({len(result.pdf_bytes)} bytes)")
    
    return response


# TimeEntry (Zeiterfassung) Views

def get_timeentry_customers():
    """
    Kunden-Queryset für die Auswahlliste der Zeiterfassungs-Formulare.

    Sortiert nach `matchkey` - also nach genau der Zeichenkette, die im
    Dropdown steht (siehe #1171). Der Matchkey ist eine gespeicherte,
    DB-generierte Spalte, damit entfällt die frühere Coalesce-Sortierung über
    `firma`/`name`.
    """
    return Adresse.objects.filter(adressen_type='KUNDE').order_by('matchkey')


def get_timeentry_projekte(selected_projekt_id=None):
    """
    Projekt-Queryset für die Auswahlliste der Zeiterfassungs-Formulare.

    Abgeschlossene Projekte werden ausgeblendet, damit die Liste kurz bleibt.
    Ein bereits zugeordnetes Projekt bleibt aber immer wählbar - sonst würde
    eine Bearbeitung die Zuordnung stillschweigend verlieren.
    """
    selectable = ~Q(status='ABGESCHLOSSEN')
    if selected_projekt_id:
        selectable |= Q(pk=selected_projekt_id)
    return Projekt.objects.select_related('kunde').filter(selectable).order_by('titel')


def get_timeentry_form_choices(selected_projekt_id=None):
    """
    Auswahllisten für das Zeiterfassungs-Formular (Anlegen und Bearbeiten).

    Args:
        selected_projekt_id: PK des bereits zugeordneten Projekts, damit es auch
            dann in der Liste steht, wenn es abgeschlossen ist.
    """
    from django.contrib.auth.models import User

    return {
        'companies': Mandant.objects.all().order_by('name'),
        'customers': get_timeentry_customers(),
        'orders': SalesDocument.objects.filter(
            document_type__key__iexact='order'
        ).order_by('-issue_date'),
        'projekte': get_timeentry_projekte(selected_projekt_id),
        'users': User.objects.all().order_by('username'),
    }


@login_required
def timeentry_list(request):
    """
    List view for time entries with filtering, sorting, and pagination.
    
    Displays a filterable, sortable, paginated list of time entries for billable services.
    """
    # Base queryset with optimized select/prefetch
    queryset = TimeEntry.objects.select_related(
        'customer', 'order', 'order__document_type', 'projekt', 'performed_by', 'company'
    )

    # Apply filters
    filter_set = TimeEntryFilter(request.GET, queryset=queryset)
    
    # Create table with filtered data
    table = TimeEntryTable(filter_set.qs)
    
    # Calculate total duration across full filtered queryset (no pagination)
    aggregates = filter_set.qs.aggregate(total_minutes=Sum('duration_minutes'))
    total_minutes = aggregates['total_minutes'] or 0
    total_hours = (Decimal(total_minutes) / Decimal('60')) if total_minutes else Decimal('0')
    
    # Set default ordering to -service_date, -created_at
    table.order_by = request.GET.get('sort', '-service_date')
    table.total_minutes = total_minutes
    table.total_hours = total_hours
    
    # Configure pagination (25 per page)
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    # Prepare context
    context = {
        'table': table,
        'filter': filter_set,
        'total_minutes': total_minutes,
        'total_hours': total_hours,
    }
    
    return render(request, 'auftragsverwaltung/timeentries/list.html', context)


@login_required
def timeentry_detail(request, pk):
    """
    Detail view for a time entry
    
    Shows time entry details and provides edit capabilities.
    
    Args:
        pk: Primary key of the time entry
    """
    timeentry = get_object_or_404(TimeEntry.objects.select_related(
        'customer', 'order', 'order__document_type', 'projekt', 'performed_by', 'company'
    ), pk=pk)
    
    context = {
        'timeentry': timeentry,
    }
    
    return render(request, 'auftragsverwaltung/timeentries/detail.html', context)


@login_required
def timeentry_create(request):
    """
    Create a new time entry
    
    GET: Show empty form for creating a new time entry.
        Optionaler Query-Parameter ``?projekt=<pk>`` belegt Projekt sowie den am
        Projekt hinterlegten Kunden/Mandanten vor (Einstieg aus dem Projekt).
    POST: Create the time entry and redirect to detail view
    """
    company = Mandant.objects.first()

    if request.method == 'POST':
        # Get company from form
        company_id = request.POST.get('company_id')
        if company_id:
            company = get_object_or_404(Mandant, pk=company_id)
        else:
            company = Mandant.objects.first()
        
        # Create new time entry from POST data
        timeentry = TimeEntry(
            company=company,
            is_travel_cost=False,
            is_billed=False,
        )
        
        # Set customer if provided
        customer_id = normalize_foreign_key_id(request.POST.get('customer_id'))
        if customer_id:
            timeentry.customer = get_object_or_404(Adresse, pk=customer_id)
        
        # Set order if provided (optional)
        order_id = normalize_foreign_key_id(request.POST.get('order_id'))
        if order_id:
            timeentry.order = get_object_or_404(SalesDocument, pk=order_id)

        # Set projekt if provided (optional)
        projekt_id = normalize_foreign_key_id(request.POST.get('projekt_id'))
        if projekt_id:
            timeentry.projekt = get_object_or_404(Projekt, pk=projekt_id)

        # Set performed_by (user)
        performed_by_id = normalize_foreign_key_id(request.POST.get('performed_by_id'))
        if performed_by_id:
            from django.contrib.auth.models import User
            timeentry.performed_by = get_object_or_404(User, pk=performed_by_id)
        else:
            # Default to current user if not specified
            timeentry.performed_by = request.user
        
        # Set service_date
        service_date_str = request.POST.get('service_date')
        if service_date_str:
            timeentry.service_date = datetime.strptime(service_date_str, '%Y-%m-%d').date()
        else:
            timeentry.service_date = date.today()
        
        # Set duration_minutes
        duration_minutes_str = request.POST.get('duration_minutes', '0')
        try:
            timeentry.duration_minutes = int(duration_minutes_str)
        except ValueError:
            timeentry.duration_minutes = 0
        
        # Set description
        timeentry.description = request.POST.get('description', '')
        
        # Set flags
        timeentry.is_travel_cost = request.POST.get('is_travel_cost') == 'on'
        timeentry.is_billed = request.POST.get('is_billed') == 'on'
        
        # Validate and save
        try:
            timeentry.full_clean()
            timeentry.save()
            
            # Log activity
            ActivityStreamService.add(
                company=company,
                domain='ORDER',
                activity_type='TIMEENTRY_CREATED',
                title=f'Zeiterfassung erstellt: {timeentry.service_date} - {timeentry.customer.matchkey}',
                target_url=f'/auftragsverwaltung/timeentries/{timeentry.pk}/',
                actor=request.user
            )
            
            return redirect('auftragsverwaltung:timeentry_detail', pk=timeentry.pk)
        except Exception as e:
            logger.error(f"Error creating time entry: {str(e)}")
            # Re-render form with error
            context = {
                'error': str(e),
                'timeentry': timeentry,
                'is_create': True,
                **get_timeentry_form_choices(timeentry.projekt_id),
            }
            return render(request, 'auftragsverwaltung/timeentries/form.html', context)

    # GET: Show empty form - optionally prefilled from a project (?projekt=<pk>)
    default_projekt = None
    default_customer = None
    projekt_id = normalize_foreign_key_id(request.GET.get('projekt'))
    if projekt_id:
        default_projekt = get_object_or_404(
            Projekt.objects.select_related('kunde', 'company'), pk=projekt_id
        )
        default_customer = default_projekt.kunde
        if default_projekt.company:
            company = default_projekt.company

    context = {
        'is_create': True,
        'default_company': company,
        'default_customer': default_customer,
        'default_projekt': default_projekt,
        'default_user': request.user,
        'default_date': date.today().strftime('%Y-%m-%d'),
        **get_timeentry_form_choices(projekt_id),
    }

    return render(request, 'auftragsverwaltung/timeentries/form.html', context)


@login_required
def timeentry_update(request, pk):
    """
    Update an existing time entry
    
    GET: Show form with current time entry data
    POST: Update the time entry and redirect to detail view
    
    Args:
        pk: Primary key of the time entry
    """
    timeentry = get_object_or_404(TimeEntry, pk=pk)
    
    if request.method == 'POST':
        # Update company if changed
        company_id = request.POST.get('company_id')
        if company_id:
            timeentry.company = get_object_or_404(Mandant, pk=company_id)
        
        # Update customer if changed
        customer_id = normalize_foreign_key_id(request.POST.get('customer_id'))
        if customer_id:
            timeentry.customer = get_object_or_404(Adresse, pk=customer_id)
        
        # Update order - beide Felder sind optional, eine leere Auswahl muss die
        # bestehende Zuordnung daher auch entfernen können.
        order_id = normalize_foreign_key_id(request.POST.get('order_id'))
        timeentry.order = get_object_or_404(SalesDocument, pk=order_id) if order_id else None

        # Update projekt
        projekt_id = normalize_foreign_key_id(request.POST.get('projekt_id'))
        timeentry.projekt = get_object_or_404(Projekt, pk=projekt_id) if projekt_id else None

        # Update performed_by if changed
        performed_by_id = normalize_foreign_key_id(request.POST.get('performed_by_id'))
        if performed_by_id:
            from django.contrib.auth.models import User
            timeentry.performed_by = get_object_or_404(User, pk=performed_by_id)
        
        # Update service_date
        service_date_str = request.POST.get('service_date')
        if service_date_str:
            timeentry.service_date = datetime.strptime(service_date_str, '%Y-%m-%d').date()
        
        # Update duration_minutes
        duration_minutes_str = request.POST.get('duration_minutes', '0')
        try:
            timeentry.duration_minutes = int(duration_minutes_str)
        except ValueError:
            timeentry.duration_minutes = 0
        
        # Update description
        timeentry.description = request.POST.get('description', '')
        
        # Update flags
        timeentry.is_travel_cost = request.POST.get('is_travel_cost') == 'on'
        timeentry.is_billed = request.POST.get('is_billed') == 'on'
        
        # Validate and save
        try:
            timeentry.full_clean()
            timeentry.save()
            
            # Log activity
            ActivityStreamService.add(
                company=timeentry.company,
                domain='ORDER',
                activity_type='TIMEENTRY_UPDATED',
                title=f'Zeiterfassung aktualisiert: {timeentry.service_date} - {timeentry.customer.matchkey}',
                target_url=f'/auftragsverwaltung/timeentries/{timeentry.pk}/',
                actor=request.user
            )
            
            return redirect('auftragsverwaltung:timeentry_detail', pk=timeentry.pk)
        except Exception as e:
            logger.error(f"Error updating time entry: {str(e)}")
            # Re-render form with error
            context = {
                'error': str(e),
                'timeentry': timeentry,
                'is_create': False,
                **get_timeentry_form_choices(timeentry.projekt_id),
            }
            return render(request, 'auftragsverwaltung/timeentries/form.html', context)

    # GET: Show form with current data
    context = {
        'timeentry': timeentry,
        'is_create': False,
        **get_timeentry_form_choices(timeentry.projekt_id),
    }

    return render(request, 'auftragsverwaltung/timeentries/form.html', context)
