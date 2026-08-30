"""
Bestehende Eingangsrechnungen einem Mandanten zuordnen.

Reihenfolge der Ableitung – von der konkretesten Quelle zur allgemeinsten:

1. ``order.company`` (Auftrag)
2. ``rental_object.mandant`` (Mietobjekt)
3. der einzige Mandant im System, falls es genau einen gibt

Gibt es mehrere Mandanten und keine Ableitungsquelle, bleibt das Feld leer.
Es wird bewusst **nicht** geraten: Ein falsch zugeordneter Aufwand ist ein
Buchungsfehler, den niemand bemerkt, eine leere Zuordnung fällt dagegen vor
dem Export in der Fehlerliste auf.

Die Migration ist idempotent – bereits gesetzte Mandanten werden nicht
angefasst.
"""
from django.db import migrations


def backfill_company(apps, schema_editor):
    InvoiceIn = apps.get_model('lieferantenwesen', 'InvoiceIn')
    Mandant = apps.get_model('core', 'Mandant')

    fallback = None
    if Mandant.objects.count() == 1:
        fallback = Mandant.objects.first()

    updates = []
    invoices = InvoiceIn.objects.filter(company__isnull=True).select_related(
        'order', 'rental_object',
    )
    for invoice in invoices.iterator():
        company_id = None
        if invoice.order_id and invoice.order.company_id:
            company_id = invoice.order.company_id
        elif invoice.rental_object_id and invoice.rental_object.mandant_id:
            company_id = invoice.rental_object.mandant_id
        elif fallback is not None:
            company_id = fallback.pk

        if company_id is not None:
            invoice.company_id = company_id
            updates.append(invoice)

    if updates:
        InvoiceIn.objects.bulk_update(updates, ['company'], batch_size=500)


def noop_reverse(apps, schema_editor):
    """Kein Rückbau: Die Zuordnung ist fachlich richtig und soll bleiben.

    Beim Zurückrollen entfernt die vorhergehende Migration ohnehin die Spalte.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('lieferantenwesen', '0006_invoicein_company_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_company, noop_reverse),
    ]
