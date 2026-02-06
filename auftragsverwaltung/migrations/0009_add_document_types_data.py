"""
Migration to add sample DocumentType data for testing the list views.
Adds the 5 document types referenced in the navigation:
- quote (Angebot)
- order (Auftragsbestätigung)
- invoice (Rechnung)
- delivery (Lieferschein)
- credit (Gutschrift)
"""

from django.db import migrations


def create_document_types(apps, schema_editor):
    """Create the 5 document types for auftragsverwaltung"""
    DocumentType = apps.get_model('auftragsverwaltung', 'DocumentType')
    
    # Create document types if they don't exist
    document_types = [
        {
            'key': 'quote',
            'name': 'Angebot',
            'prefix': 'AN',
            'is_invoice': False,
            'is_correction': False,
            'requires_due_date': False,
            'is_active': True,
        },
        {
            'key': 'order',
            'name': 'Auftragsbestätigung',
            'prefix': 'AB',
            'is_invoice': False,
            'is_correction': False,
            'requires_due_date': False,
            'is_active': True,
        },
        {
            'key': 'invoice',
            'name': 'Rechnung',
            'prefix': 'R',
            'is_invoice': True,
            'is_correction': False,
            'requires_due_date': True,
            'is_active': True,
        },
        {
            'key': 'delivery',
            'name': 'Lieferschein',
            'prefix': 'LS',
            'is_invoice': False,
            'is_correction': False,
            'requires_due_date': False,
            'is_active': True,
        },
        {
            'key': 'credit',
            'name': 'Gutschrift',
            'prefix': 'GS',
            'is_invoice': False,
            'is_correction': True,
            'requires_due_date': False,
            'is_active': True,
        },
    ]
    
    for doc_type_data in document_types:
        DocumentType.objects.get_or_create(
            key=doc_type_data['key'],
            defaults=doc_type_data
        )


def reverse_create_document_types(apps, schema_editor):
    """Remove the document types (optional - for rollback)"""
    DocumentType = apps.get_model('auftragsverwaltung', 'DocumentType')
    
    # Only delete if no SalesDocuments are using them
    keys = ['quote', 'order', 'invoice', 'delivery', 'credit']
    for key in keys:
        try:
            doc_type = DocumentType.objects.get(key=key)
            # Only delete if no documents are using this type
            if doc_type.sales_documents.count() == 0:
                doc_type.delete()
        except DocumentType.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('auftragsverwaltung', '0008_salesdocument_footer_text_salesdocument_header_text_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_document_types,
            reverse_create_document_types
        ),
    ]
