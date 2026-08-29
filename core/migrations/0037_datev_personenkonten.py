"""
Personenkonten DATEV-konform umstellen.

Bisher vergab `Adresse.save()` für Kunden Nummern der Form `DEB26-00001`:
mit Präfix, Jahresbestandteil und Bindestrich. DATEV erwartet rein numerische
Personenkonten; der Jahresbestandteil war zusätzlich fachlich falsch, weil ein
Debitorenkonto dauerhaft zu einem Kunden gehört.

Diese Migration
- richtet die Nummernkreise CUSTOMER (ab 10000) und SUPPLIER (ab 70000) auf
  rein numerisches Format ohne Jahresreset ein,
- ersetzt bestehende nicht-numerische bzw. bereichsfremde Konten durch
  fortlaufende numerische Konten und
- zieht `current_seq` so nach, dass Neuanlagen nicht mit dem Bestand
  kollidieren.

Idempotent: Bereits numerische Konten im passenden Bereich bleiben unangetastet;
ein zweiter Lauf ändert nichts.
"""
from django.db import migrations


# Bewusst als Migrations-Konstanten und nicht aus den Settings gelesen:
# Eine Datenmigration muss auch dann reproduzierbar dasselbe Ergebnis liefern,
# wenn die Settings später verschoben werden.
CUSTOMER_START = 10000
CUSTOMER_END = 69999
SUPPLIER_START = 70000
SUPPLIER_END = 99999

RANGES = [
    ('KUNDE', 'CUSTOMER', CUSTOMER_START, CUSTOMER_END),
    ('LIEFERANT', 'SUPPLIER', SUPPLIER_START, SUPPLIER_END),
]


def _is_in_range(value, low, high):
    """True, wenn `value` ein rein numerisches Konto im Bereich [low, high] ist."""
    if not value or not value.isdigit():
        return False
    return low <= int(value) <= high


def _sort_key(adresse):
    """
    Stabile Reihenfolge für die Neuvergabe.

    Adressen mit bisheriger Nummer behalten deren Reihenfolge (Gruppe 0),
    danach folgen Adressen ohne Nummer nach pk (Gruppe 1). So bleibt die
    Zuordnung nachvollziehbar und über wiederholte Läufe identisch.
    """
    number = (adresse.debitor_number or '').strip()
    if number:
        return (0, number, adresse.pk)
    return (1, '', adresse.pk)


def migrate_personal_accounts(apps, schema_editor):
    Adresse = apps.get_model('core', 'Adresse')
    NumberRange = apps.get_model('auftragsverwaltung', 'NumberRange')

    for adressen_type, target, low, high in RANGES:
        number_range, _ = NumberRange.objects.get_or_create(
            target=target,
            defaults={
                'company': None,
                'document_type': None,
                'format': '{seq}',
                'reset_policy': 'NEVER',
                'start_seq': low,
                'current_year': 0,
                'current_seq': 0,
            },
        )
        # Bestehende Nummernkreise (z. B. der alte CUSTOMER-Kreis mit
        # Jahresreset) auf das neue Format umstellen.
        number_range.company = None
        number_range.document_type = None
        number_range.format = '{seq}'
        number_range.reset_policy = 'NEVER'
        number_range.start_seq = low

        addresses = list(Adresse.objects.filter(adressen_type=adressen_type))

        # Konten, die bereits passen, bleiben – und blockieren ihre Nummer.
        taken = {
            int(a.debitor_number.strip())
            for a in addresses
            if _is_in_range((a.debitor_number or '').strip(), low, high)
        }

        next_seq = max(low, number_range.current_seq + 1)
        updated = []
        for adresse in sorted(addresses, key=_sort_key):
            current = (adresse.debitor_number or '').strip()
            if _is_in_range(current, low, high):
                if current != adresse.debitor_number:
                    adresse.debitor_number = current
                    updated.append(adresse)
                continue

            while next_seq in taken:
                next_seq += 1
            if next_seq > high:
                raise RuntimeError(
                    f'Der Kontenbereich {low}-{high} für {adressen_type} ist erschöpft. '
                    'Bitte den Bereich erweitern, bevor die Migration erneut läuft.'
                )
            adresse.debitor_number = str(next_seq)
            taken.add(next_seq)
            updated.append(adresse)
            next_seq += 1

        if updated:
            Adresse.objects.bulk_update(updated, ['debitor_number'])

        # current_seq auf das höchste vergebene Konto ziehen, damit
        # Neuanlagen nicht mit dem Bestand kollidieren.
        highest = max(taken) if taken else low - 1
        number_range.current_seq = max(number_range.current_seq, highest)
        number_range.save()


def reverse_noop(apps, schema_editor):
    """
    Kein Rückbau.

    Die alten `DEB26-…`-Nummern sind nicht rekonstruierbar, und ein Rückbau
    wäre fachlich auch nicht gewünscht: Personenkonten sind ab hier Teil der
    Buchhaltung.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_kostenart_aufwandskonto_kostenart_erloeskonto_and_more'),
        ('auftragsverwaltung', '0026_remove_numberrange_numberrange_document_requires_doctype_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_personal_accounts, reverse_noop),
    ]
