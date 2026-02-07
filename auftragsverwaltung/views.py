from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Max
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta, date
from decimal import Decimal
from django_tables2 import RequestConfig
import json

from .models import SalesDocument, DocumentType, SalesDocumentLine, Contract, ContractLine, TextTemplate
from .tables import SalesDocumentTable, ContractTable, TextTemplateTable, OutgoingInvoiceJournalTable
from .filters import SalesDocumentFilter, ContractFilter, TextTemplateFilter, OutgoingInvoiceJournalFilter
from .services import (
    DocumentCalculationService,
    TaxDeterminationService,
    PaymentTermTextService,
    get_next_number
)
from .utils import sanitize_html
from core.models import Mandant, Adresse, Item, PaymentTerm, TaxRate, Kostenart, Unit
from core.services.activity_stream import ActivityStreamService
from finanzen.models import OutgoingInvoiceJournalEntry


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


@login_required
def auftragsverwaltung_home(request):
    """
    Dashboard for Auftragsverwaltung (Order Management)
    
    Shows:
    - KPIs (open documents, unpaid invoices, new documents, open amount)
    - Open sales documents table
    - Latest 10 documents
    - Activity stream (last 25 entries)
    """
    # Get the default company (for now, we'll use the first available)
    # In a multi-tenant setup, this would be based on the user's company
    company = Mandant.objects.first()
    
    # Initialize KPIs
    kpi_open_documents = 0
    kpi_unpaid_invoices = 0
    kpi_new_documents_30d = 0
    kpi_open_amount = Decimal('0.00')
    
    open_sales_documents = []
    latest_documents = []
    
    if company:
        # KPI 1: Count of open documents (DRAFT, SENT, APPROVED)
        kpi_open_documents = SalesDocument.objects.filter(
            company=company,
            status__in=['DRAFT', 'SENT', 'APPROVED']
        ).count()
        
        # KPI 2: Count of unpaid invoices (documents marked as invoice, not paid, not cancelled)
        kpi_unpaid_invoices = SalesDocument.objects.filter(
            company=company,
            document_type__is_invoice=True,
            paid_at__isnull=True,
            status__in=['SENT', 'APPROVED', 'OVERDUE']
        ).exclude(status='CANCELLED').count()
        
        # KPI 3: New documents in the last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        kpi_new_documents_30d = SalesDocument.objects.filter(
            company=company,
            issue_date__gte=thirty_days_ago.date()
        ).count()
        
        # KPI 4: Total open amount (sum of unpaid invoices)
        open_amount_aggregate = SalesDocument.objects.filter(
            company=company,
            document_type__is_invoice=True,
            paid_at__isnull=True,
            status__in=['SENT', 'APPROVED', 'OVERDUE']
        ).exclude(status='CANCELLED').aggregate(total=Sum('total_gross'))
        
        kpi_open_amount = open_amount_aggregate['total'] or Decimal('0.00')
        
        # Get open sales documents (DRAFT, SENT, APPROVED)
        open_sales_documents = SalesDocument.objects.filter(
            company=company,
            status__in=['DRAFT', 'SENT', 'APPROVED']
        ).select_related('document_type').order_by('-issue_date')[:20]
        
        # Get latest 10 documents
        latest_documents = SalesDocument.objects.filter(
            company=company
        ).select_related('document_type').order_by('-issue_date', '-id')[:10]
    
    # Get activity stream (last 25 activities)
    # Filter by ORDER domain if we want only order management activities
    if company:
        activities = ActivityStreamService.latest(n=25, company=company, domain='ORDER')
    else:
        activities = []
    
    context = {
        'kpi_open_documents': kpi_open_documents,
        'kpi_unpaid_invoices': kpi_unpaid_invoices,
        'kpi_new_documents_30d': kpi_new_documents_30d,
        'kpi_open_amount': kpi_open_amount,
        'open_sales_documents': open_sales_documents,
        'latest_documents': latest_documents,
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
    
    # Get the default company (for now, we'll use the first available)
    try:
        company = Mandant.objects.first()
    except Mandant.DoesNotExist:
        company = None
    
    # Base queryset with optimized select/prefetch
    queryset = SalesDocument.objects.select_related(
        'document_type', 'company', 'customer'
    ).filter(
        document_type=document_type
    )
    
    # Filter by company if available
    if company:
        queryset = queryset.filter(company=company)
    
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
    
    # Get document lines (ordered by position_no)
    lines = document.lines.select_related('item', 'tax_rate', 'kostenart1', 'kostenart2').order_by('position_no')
    
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
        
        # Full-text search across article fields
        articles = Item.objects.filter(
            Q(article_no__icontains=query) |
            Q(short_text_1__icontains=query) |
            Q(short_text_2__icontains=query) |
            Q(long_text__icontains=query),
            is_active=True
        ).select_related('tax_rate', 'cost_type_1', 'cost_type_2', 'item_group')[:20]
        
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
@require_http_methods(["POST"])
def ajax_add_line(request, doc_key, pk):
    """
    AJAX endpoint to add a new line to a document
    
    POST parameters (JSON):
        - item_id: Item/Article ID (optional for manual lines)
        - quantity: Quantity
        - description: Description (required for manual lines)
        - unit_price_net: Unit price (required for manual lines)
        - tax_rate_id: Tax rate ID (required)
        - line_type: Line type (NORMAL, OPTIONAL, ALTERNATIVE)
        - kostenart1_id: Kostenart 1 ID (optional)
        - kostenart2_id: Kostenart 2 ID (optional)
    
    Returns:
        JSON: {success, line_id, line_data}
    """
    try:
        document = get_object_or_404(SalesDocument, pk=pk)
        
        # Parse JSON body
        data = json.loads(request.body)
        
        item_id = data.get('item_id')
        quantity = Decimal(data.get('quantity', '1.0'))
        line_type = data.get('line_type', 'NORMAL')
        description = data.get('description', '')
        short_text_1 = data.get('short_text_1', '')
        short_text_2 = data.get('short_text_2', '')
        long_text = data.get('long_text', '')
        unit_price_net = data.get('unit_price_net')
        tax_rate_id = data.get('tax_rate_id')
        kostenart1_id = data.get('kostenart1_id')
        kostenart2_id = data.get('kostenart2_id')
        
        # Determine line data based on whether item is provided
        if item_id:
            # Article-based line
            item = get_object_or_404(Item, pk=item_id)
            
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
            
            # Allow empty positions for initial creation (user will fill them in)
            # Only validate if we have some non-empty content
            try:
                price_value = float(unit_price_net) if unit_price_net else 0.0
            except (ValueError, TypeError):
                price_value = 0.0
            
            # Validate mandatory fields only if user has entered description content
            # Allow positions with just short_text_1 and zero price for initial creation
            if description and description.strip():
                # If user entered description, require short_text_1 too
                if not short_text_1 or not short_text_1.strip():
                    return JsonResponse({'error': 'Short text 1 is required when description is provided'}, status=400)
            
            if not tax_rate_id:
                return JsonResponse({'error': 'Tax rate is required for manual lines'}, status=400)
            
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
            
            tax_rate = get_object_or_404(TaxRate, pk=tax_rate_id)
            unit_price_net = Decimal(unit_price_net) if unit_price_net else Decimal('0.00')
            is_discountable = data.get('is_discountable', True)
        
        # Get next position number
        max_position = document.lines.aggregate(max_pos=Max('position_no'))['max_pos'] or 0
        position_no = max_position + 1
        
        # Get unit and discount if provided
        unit_id = data.get('unit_id')
        discount = data.get('discount')
        
        # Safely convert discount to Decimal
        if discount not in (None, ''):
            try:
                discount_value = Decimal(str(discount))
            except (ValueError, TypeError):
                discount_value = Decimal('0.00')
        else:
            discount_value = Decimal('0.00')
        
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
            long_text=long_text,
            description=description,
            quantity=quantity,
            unit_id=normalize_foreign_key_id(unit_id),
            unit_price_net=unit_price_net,
            discount=discount_value,
            is_discountable=is_discountable,
            kostenart1_id=normalize_foreign_key_id(kostenart1_id),
            kostenart2_id=normalize_foreign_key_id(kostenart2_id),
        )
        
        # Recalculate document totals
        DocumentCalculationService.recalculate(document, persist=True)
        
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ajax_update_line(request, doc_key, pk, line_id):
    """
    AJAX endpoint to update an existing line
    
    POST parameters (JSON):
        - quantity: New quantity
        - unit_price_net: New unit price
        - description: New description
        - tax_rate_id: New tax rate ID
        - kostenart1_id: New kostenart1 ID
        - kostenart2_id: New kostenart2 ID
    
    Returns:
        JSON: {success, line_data, totals}
    """
    try:
        document = get_object_or_404(SalesDocument, pk=pk)
        line = get_object_or_404(SalesDocumentLine, pk=line_id, document=document)
        
        # Parse JSON body
        data = json.loads(request.body)
        
        # Update fields
        if 'quantity' in data:
            line.quantity = Decimal(data['quantity'])
        if 'unit_price_net' in data:
            line.unit_price_net = Decimal(data['unit_price_net'])
        if 'short_text_1' in data:
            line.short_text_1 = data['short_text_1']
        if 'short_text_2' in data:
            line.short_text_2 = data['short_text_2']
        if 'long_text' in data:
            line.long_text = data['long_text']
        if 'description' in data:
            line.description = data['description']
        if 'tax_rate_id' in data:
            line.tax_rate = get_object_or_404(TaxRate, pk=data['tax_rate_id'])
        if 'is_selected' in data:
            line.is_selected = data['is_selected']
        if 'unit_id' in data:
            line.unit_id = normalize_foreign_key_id(data['unit_id'])
        if 'discount' in data:
            discount_value = data['discount']
            if discount_value not in (None, ''):
                try:
                    line.discount = Decimal(str(discount_value))
                except (ValueError, TypeError):
                    line.discount = Decimal('0.00')
            else:
                line.discount = Decimal('0.00')
        if 'kostenart1_id' in data:
            line.kostenart1_id = normalize_foreign_key_id(data['kostenart1_id'])
        if 'kostenart2_id' in data:
            line.kostenart2_id = normalize_foreign_key_id(data['kostenart2_id'])
        
        line.save()
        
        # Recalculate document totals
        DocumentCalculationService.recalculate(document, persist=True)
        
        # Return updated line data
        return JsonResponse({
            'success': True,
            'line': {
                'id': line.pk,
                'short_text_1': line.short_text_1,
                'short_text_2': line.short_text_2,
                'long_text': line.long_text,
                'quantity': str(line.quantity),
                'unit_id': line.unit.pk if line.unit else None,
                'unit_price_net': str(line.unit_price_net),
                'discount': str(line.discount),
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    # Get the default company (for now, we'll use the first available)
    try:
        company = Mandant.objects.first()
    except Mandant.DoesNotExist:
        company = None
    
    # Base queryset with optimized select/prefetch
    queryset = Contract.objects.select_related(
        'customer', 'company'
    )
    
    # Filter by company if available
    if company:
        queryset = queryset.filter(company=company)
    
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
    
    # Get contract lines (ordered by position_no)
    lines = contract.lines.select_related('item', 'tax_rate', 'cost_type_1', 'cost_type_2').order_by('position_no')
    
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
        'max_position': max_position,
        'is_create': False,
    }
    
    return render(request, 'auftragsverwaltung/contracts/detail.html', context)


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
            description=f'Kunde: {contract.customer.name}' if contract.customer else None,
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
    old_customer_name = contract.customer.name if contract.customer else None
    
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
        new_customer_name = contract.customer.name if contract.customer else None
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
            description=f'Kunde: {contract.customer.name}' if contract.customer else None,
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
        - description: Description (required for manual lines)
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
        quantity = Decimal(data.get('quantity', '1.0'))
        description = data.get('description', '')
        unit_price_net = data.get('unit_price_net')
        tax_rate_id = data.get('tax_rate_id')
        cost_type_1_id = data.get('cost_type_1_id')
        cost_type_2_id = data.get('cost_type_2_id')
        is_discountable = data.get('is_discountable', True)
        
        # Determine line data based on whether item is provided
        if item_id:
            # Article-based line
            item = get_object_or_404(Item, pk=item_id)
            
            # Use item data
            if not description:
                description = f"{item.short_text_1}\n{item.long_text}" if item.long_text else item.short_text_1
            if not unit_price_net:
                unit_price_net = item.net_price
            
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
            # Manual line - ensure required fields are present
            if not description:
                return JsonResponse({'error': 'Beschreibung ist erforderlich'}, status=400)
            if not unit_price_net:
                return JsonResponse({'error': 'Netto-Stückpreis ist erforderlich'}, status=400)
        
        # Ensure tax rate is provided
        if not tax_rate_id:
            return JsonResponse({'error': 'Steuersatz ist erforderlich'}, status=400)
        
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
            description=description,
            quantity=quantity,
            unit_price_net=Decimal(unit_price_net),
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
                'description': line.description,
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
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ajax_contract_update_line(request, pk, line_id):
    """
    AJAX endpoint to update an existing contract line
    
    POST parameters (JSON):
        - quantity: New quantity
        - unit_price_net: New unit price
        - description: New description
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
        
        # Update fields
        if 'quantity' in data:
            line.quantity = Decimal(data['quantity'])
        if 'unit_price_net' in data:
            line.unit_price_net = Decimal(data['unit_price_net'])
        if 'description' in data:
            line.description = data['description']
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
                'description': line.description,
                'tax_rate_id': line.tax_rate.pk,
                'tax_rate_code': line.tax_rate.code,
                'tax_rate_rate': str(line.tax_rate.rate),
                'cost_type_1_id': line.cost_type_1.pk if line.cost_type_1 else None,
                'cost_type_2_id': line.cost_type_2.pk if line.cost_type_2 else None,
                'is_discountable': line.is_discountable,
            },
            'preview_totals': preview_totals,
        })
    except Exception as e:
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
    Only shows templates for the user's company.
    """
    # Get the default company
    try:
        company = Mandant.objects.first()
    except Mandant.DoesNotExist:
        company = None
    
    # Base queryset
    queryset = TextTemplate.objects.select_related('company')
    
    # Filter by company if available
    if company:
        queryset = queryset.filter(company=company)
    
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
    """
    # Get the default company (for now, we'll use the first available)
    try:
        company = Mandant.objects.first()
    except Mandant.DoesNotExist:
        company = None
    
    # Base queryset with optimized select/prefetch
    queryset = OutgoingInvoiceJournalEntry.objects.select_related(
        'company', 'document'
    )
    
    # Filter by company if available
    if company:
        queryset = queryset.filter(company=company)
    
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

