from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from datetime import datetime, timedelta
from decimal import Decimal
from django_tables2 import RequestConfig

from .models import SalesDocument, DocumentType
from .tables import SalesDocumentTable
from .filters import SalesDocumentFilter
from core.models import Mandant
from core.services.activity_stream import ActivityStreamService


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
        'document_type', 'company'
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
