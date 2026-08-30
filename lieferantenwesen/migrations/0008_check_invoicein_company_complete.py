"""
Prüfen, ob nach der Nachzuordnung noch Eingangsrechnungen ohne Mandant offen sind.

Das Feld ``InvoiceIn.company`` bleibt bewusst ``null=True``:

- Der Weg über den PDF-Upload legt einen Entwurf an, **bevor** ein Mandant
  ableitbar ist. Ein NOT-NULL-Feld würde diesen Weg entweder brechen oder zum
  Raten eines Mandanten zwingen – genau das soll die Datenmigration vermeiden.
- Bestandsbelege, für die sich der Mandant nicht ableiten ließ, sollen offen
  sichtbar bleiben, statt eine Migration auf Produktivdaten scheitern zu lassen.

Die fachliche Pflicht wird stattdessen dort durchgesetzt, wo sie wirkt:
``InvoiceInForm`` verlangt den Mandanten, und der DATEV-Export meldet Belege
ohne Mandant in der Fehlerliste und blockiert damit den Download.

Diese Migration ändert nichts an der Datenbank; sie schreibt lediglich eine
Warnung ins Migrationslog, wenn noch Belege offen sind. Sobald der Bestand
vollständig zugeordnet ist **und** der PDF-Upload-Weg immer einen Mandanten
liefert, kann das Feld in einer Folgemigration auf ``null=False`` gezogen
werden.
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def report_open_invoices(apps, schema_editor):
    InvoiceIn = apps.get_model('lieferantenwesen', 'InvoiceIn')
    open_count = InvoiceIn.objects.filter(company__isnull=True).count()
    if open_count:
        logger.warning(
            "%s Eingangsrechnung(en) haben keinen Mandanten. Sie werden nicht "
            "exportiert, sondern erscheinen im DATEV-Export in der Fehlerliste. "
            "Bitte den Mandanten am Beleg nachpflegen.",
            open_count,
        )


def noop_reverse(apps, schema_editor):
    """Reine Prüfung – es gibt nichts zurückzurollen."""


class Migration(migrations.Migration):

    dependencies = [
        ('lieferantenwesen', '0007_backfill_invoicein_company'),
    ]

    operations = [
        migrations.RunPython(report_open_invoices, noop_reverse),
    ]
