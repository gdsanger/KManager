from django.contrib import admin
from django.contrib import messages
from auftragsverwaltung.models import (
    DocumentType,
    NumberRange,
    SalesDocument,
    SalesDocumentLine,
    SalesDocumentSource,
    Contract,
    ContractLine,
    ContractRun,
    TextTemplate,
)
from auftragsverwaltung.services import DocumentCalculationService


class SalesDocumentLineInline(admin.TabularInline):
    """Inline admin for SalesDocumentLine"""
    model = SalesDocumentLine
    extra = 1
    fields = (
        'position_no',
        'line_type',
        'is_selected',
        'item',
        'description',
        'quantity',
        'unit_price_net',
        'tax_rate',
        'is_discountable',
        'line_net',
        'line_tax',
        'line_gross'
    )
    readonly_fields = ('line_net', 'line_tax', 'line_gross')
    ordering = ('position_no',)


@admin.register(NumberRange)
class NumberRangeAdmin(admin.ModelAdmin):
    """Admin interface for NumberRange"""
    list_display = ('company', 'target', 'document_type', 'reset_policy', 'current_year', 'current_seq', 'format')
    list_filter = ('company', 'target', 'document_type', 'reset_policy')
    search_fields = ('company__name', 'document_type__name', 'document_type__key')
    ordering = ('company', 'target', 'document_type')
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('company', 'target', 'document_type')
        }),
        ('Konfiguration', {
            'fields': ('format', 'reset_policy')
        }),
        ('Status', {
            'fields': ('current_year', 'current_seq'),
            'description': 'Diese Felder werden automatisch verwaltet, können aber bei Bedarf manuell angepasst werden.'
        }),
    )


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    """Admin interface for DocumentType"""
    list_display = ('key', 'name', 'prefix', 'is_invoice', 'is_correction', 'requires_due_date', 'is_active')
    list_filter = ('is_active', 'is_invoice', 'is_correction', 'requires_due_date')
    search_fields = ('key', 'name', 'prefix')
    ordering = ('key',)
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('key', 'name', 'prefix', 'is_active')
        }),
        ('Flags', {
            'fields': ('is_invoice', 'is_correction', 'requires_due_date')
        }),
    )


@admin.register(SalesDocument)
class SalesDocumentAdmin(admin.ModelAdmin):
    """Admin interface for SalesDocument"""
    list_display = (
        'number',
        'company',
        'document_type',
        'status',
        'subject',
        'reference_number',
        'header_text',
        'footer_text',
        'payment_term_text',
        'issue_date',
        'due_date',
        'total_net',
        'total_tax',
        'total_gross',
        'source_document'
    )
    list_filter = (
        'company',
        'document_type',
        'status',
        'issue_date'
    )
    search_fields = (
        'number',
        'company__name',
        'document_type__name',
        'document_type__key',
        'notes_internal',
        'subject',
        'reference_number',
        'notes_public'
    )
    ordering = ('-issue_date', '-id')
    date_hierarchy = 'issue_date'
    inlines = [SalesDocumentLineInline]
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('company', 'document_type', 'number', 'status', 'subject', 'reference_number')
        }),
        ('Datumsangaben', {
            'fields': ('issue_date', 'due_date', 'paid_at')
        }),
        ('Beziehungen', {
            'fields': ('payment_term', 'source_document')
        }),
        ('Beträge', {
            'fields': ('total_net', 'total_tax', 'total_gross'),
            'description': 'Diese Felder sind denormalisiert. Berechnungslogik wird in einem separaten Issue implementiert.'
        }),
        ('Snapshots', {
            'fields': ('payment_term_snapshot',),
            'classes': ('collapse',),
            'description': 'JSON-Snapshots zum Zeitpunkt der Belegausstellung.'
        }),
        ('Notizen', {
            'fields': ('notes_internal', 'notes_public'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ()
    actions = ['recalculate_totals']
    
    def recalculate_totals(self, request, queryset):
        """
        Admin action to recalculate totals for selected documents
        
        This action calls DocumentCalculationService.recalculate() with persist=True
        for each selected document and provides feedback on success/failure.
        """
        success_count = 0
        error_count = 0
        
        for document in queryset:
            try:
                DocumentCalculationService.recalculate(document, persist=True)
                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Fehler beim Berechnen von {document.number}: {str(e)}",
                    level=messages.ERROR
                )
        
        # Success message
        if success_count > 0:
            self.message_user(
                request,
                f"Summen für {success_count} Dokument(e) erfolgreich neu berechnet.",
                level=messages.SUCCESS
            )
        
        # Summary if there were errors
        if error_count > 0:
            self.message_user(
                request,
                f"{error_count} Dokument(e) konnten nicht berechnet werden.",
                level=messages.WARNING
            )
    
    recalculate_totals.short_description = "Summen neu berechnen"
    
    def get_readonly_fields(self, request, obj=None):
        """Make payment_term_snapshot readonly by default"""
        readonly = list(self.readonly_fields)
        # Optionally make payment_term_snapshot readonly in the future
        return readonly


@admin.register(SalesDocumentLine)
class SalesDocumentLineAdmin(admin.ModelAdmin):
    """Admin interface for SalesDocumentLine"""
    list_display = (
        'document',
        'position_no',
        'line_type',
        'is_selected',
        'description_short',
        'quantity',
        'unit_price_net',
        'line_net',
        'line_tax',
        'line_gross'
    )
    list_filter = (
        'document__company',
        'document__document_type',
        'line_type',
        'is_selected'
    )
    search_fields = (
        'document__number',
        'description',
        'item__name'
    )
    ordering = ('document', 'position_no')
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('document', 'position_no')
        }),
        ('Positionstyp', {
            'fields': ('line_type', 'is_selected')
        }),
        ('Inhalt', {
            'fields': ('item', 'description', 'quantity', 'unit_price_net', 'tax_rate', 'is_discountable')
        }),
        ('Beträge (berechnet)', {
            'fields': ('line_net', 'line_tax', 'line_gross'),
            'description': 'Diese Felder werden durch den DocumentCalculationService berechnet.'
        }),
    )
    
    readonly_fields = ('line_net', 'line_tax', 'line_gross')
    
    def description_short(self, obj):
        """Show shortened description"""
        if len(obj.description) > 50:
            return f"{obj.description[:50]}..."
        return obj.description
    description_short.short_description = "Beschreibung"


@admin.register(SalesDocumentSource)
class SalesDocumentSourceAdmin(admin.ModelAdmin):
    """Admin interface for SalesDocumentSource"""
    list_display = (
        'target_document',
        'source_document',
        'role',
        'created_at',
        'target_company'
    )
    list_filter = (
        'role',
        'target_document__company',
    )
    search_fields = (
        'target_document__number',
        'source_document__number',
        'target_document__company__name',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Dokumentbeziehung', {
            'fields': ('target_document', 'source_document', 'role')
        }),
        ('Metadaten', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)
    
    def target_company(self, obj):
        """Show company of target document"""
        return obj.target_document.company.name
    target_company.short_description = "Mandant"


class ContractLineInline(admin.TabularInline):
    """Inline admin for ContractLine"""
    model = ContractLine
    extra = 1
    fields = (
        'position_no',
        'item',
        'description',
        'quantity',
        'unit_price_net',
        'tax_rate',
        'cost_type_1',
        'cost_type_2',
        'is_discountable',
    )
    ordering = ('position_no',)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """Admin interface for Contract"""
    list_display = (
        'number',
        'name',
        'company',
        'customer',
        'interval',
        'start_date',
        'end_date',
        'next_run_date',
        'is_active',
        'is_contract_active',
    )
    list_filter = (
        'company',
        'interval',
        'is_active',
        'start_date',
        'next_run_date',
    )
    search_fields = (
        'number',
        'name',
        'reference',
        'company__name',
        'customer__name',
        'customer__firma',
    )
    ordering = ('company', 'name')
    date_hierarchy = 'start_date'
    inlines = [ContractLineInline]
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('company', 'number', 'name', 'customer', 'reference')
        }),
        ('Abrechnungskonfiguration', {
            'fields': ('document_type', 'payment_term', 'currency', 'interval')
        }),
        ('Zeitraum', {
            'fields': ('start_date', 'end_date', 'next_run_date', 'last_run_date')
        }),
        ('Status & Automatisierung', {
            'fields': ('is_active', 'auto_finalize', 'auto_send')
        }),
    )
    
    readonly_fields = ('last_run_date',)
    
    def is_contract_active(self, obj):
        """Show if contract is currently active (considering end_date)"""
        return obj.is_contract_active()
    is_contract_active.boolean = True
    is_contract_active.short_description = "Effektiv aktiv"


@admin.register(ContractLine)
class ContractLineAdmin(admin.ModelAdmin):
    """Admin interface for ContractLine"""
    list_display = (
        'contract',
        'position_no',
        'description_short',
        'quantity',
        'unit_price_net',
        'tax_rate',
        'is_discountable',
    )
    list_filter = (
        'contract__company',
        'is_discountable',
    )
    search_fields = (
        'contract__name',
        'description',
        'item__article_no',
        'item__short_text_1',
    )
    ordering = ('contract', 'position_no')
    
    fieldsets = (
        ('Zuordnung', {
            'fields': ('contract', 'position_no')
        }),
        ('Inhalt', {
            'fields': ('item', 'description', 'quantity', 'unit_price_net')
        }),
        ('Steuer & Kostenarten', {
            'fields': ('tax_rate', 'cost_type_1', 'cost_type_2')
        }),
        ('Flags', {
            'fields': ('is_discountable',)
        }),
    )
    
    def description_short(self, obj):
        """Show shortened description"""
        if len(obj.description) > 50:
            return f"{obj.description[:50]}..."
        return obj.description
    description_short.short_description = "Beschreibung"


@admin.register(ContractRun)
class ContractRunAdmin(admin.ModelAdmin):
    """Admin interface for ContractRun"""
    list_display = (
        'contract',
        'run_date',
        'status',
        'document',
        'created_at',
        'message_short',
    )
    list_filter = (
        'status',
        'contract__company',
        'run_date',
        'created_at',
    )
    search_fields = (
        'contract__name',
        'document__number',
        'message',
    )
    ordering = ('-run_date', '-created_at')
    date_hierarchy = 'run_date'
    
    fieldsets = (
        ('Vertragsausführung', {
            'fields': ('contract', 'run_date', 'status')
        }),
        ('Ergebnis', {
            'fields': ('document', 'message')
        }),
        ('Metadaten', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)
    
    def message_short(self, obj):
        """Show shortened message"""
        if obj.message and len(obj.message) > 50:
            return f"{obj.message[:50]}..."
        return obj.message or ""
    message_short.short_description = "Nachricht"


@admin.register(TextTemplate)
class TextTemplateAdmin(admin.ModelAdmin):
    """Admin interface for TextTemplate"""
    list_display = (
        'title',
        'company',
        'type',
        'key',
        'is_active',
        'sort_order',
        'updated_at',
    )
    list_filter = (
        'company',
        'type',
        'is_active',
    )
    search_fields = (
        'title',
        'key',
        'content',
        'company__name',
    )
    ordering = ('company', 'type', 'sort_order', 'title')
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('company', 'key', 'title', 'type')
        }),
        ('Inhalt', {
            'fields': ('content',)
        }),
        ('Optionen', {
            'fields': ('is_active', 'sort_order')
        }),
        ('Metadaten', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
