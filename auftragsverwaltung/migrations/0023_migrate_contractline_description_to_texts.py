"""
Verlustfreie Überführung bestehender ContractLine-Texte.

Historisch pflegte die Vertrags-UI Positionstexte ausschließlich in
``description``; ``short_text_1``/``long_text`` blieben leer. Das Rechnungs-Grid
rendert aber ``short_text_1``/``long_text``, sodass die Texte in erzeugten
Rechnungen optisch leer wirkten (siehe Issue #1044/#1053).

Diese Datenmigration befüllt die führenden Felder aus ``description``:

* Für jede ``ContractLine`` mit **leerem** ``short_text_1`` und **nicht-leerem**
  ``description``: ``short_text_1`` wird aus der ersten Zeile von ``description``
  gesetzt (an Wortgrenze auf 200 Zeichen gekürzt).
* Passt der Text nicht in 200 Zeichen **oder** ist er mehrzeilig **und**
  ``long_text`` ist leer, wird der **vollständige** ``description``-Text nach
  ``long_text`` übernommen – so geht kein Zeichen verloren.
* ``description`` wird **nie** gelöscht oder überschrieben.

Die Migration ist idempotent (Zeilen mit bereits gesetztem ``short_text_1``
werden übersprungen) und reversibel als No-op (das Befüllen leerer Zielfelder
ist ohnehin nicht destruktiv).
"""

from django.db import migrations

SHORT_TEXT_MAX_LENGTH = 200


def _shorten_to_short_text(text, limit=SHORT_TEXT_MAX_LENGTH):
    """Kürze ``text`` auf höchstens ``limit`` Zeichen an einer Wortgrenze."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # An letzter Leerstelle brechen, um kein Wort mittendrin abzuschneiden.
    # Nur, wenn der Bruch nicht zu früh liegt (mind. Hälfte des Limits).
    space_idx = cut.rfind(' ')
    if space_idx >= limit // 2:
        cut = cut[:space_idx]
    return cut.rstrip()


def forwards(apps, schema_editor):
    ContractLine = apps.get_model('auftragsverwaltung', 'ContractLine')

    for line in ContractLine.objects.all().iterator():
        description = (line.description or '').strip()
        if not description:
            continue
        # Idempotenz: Zeilen mit bereits gepflegtem Kurztext bleiben unverändert.
        if (line.short_text_1 or '').strip():
            continue

        first_line = description.split('\n', 1)[0].strip()
        is_multiline = '\n' in description
        needs_long_text = is_multiline or len(first_line) > SHORT_TEXT_MAX_LENGTH

        update_fields = []
        line.short_text_1 = _shorten_to_short_text(first_line)
        update_fields.append('short_text_1')

        # Vollständigen Text nur nach long_text übernehmen, wenn dort noch nichts
        # steht – sonst würde vorhandener Langtext überschrieben.
        if needs_long_text and not (line.long_text or '').strip():
            line.long_text = description
            update_fields.append('long_text')

        line.save(update_fields=update_fields)


def backwards(apps, schema_editor):
    """No-op: Das Befüllen leerer Felder ist nicht destruktiv, da ``description``
    unangetastet bleibt und weiterhin die vollständige Quelle darstellt."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('auftragsverwaltung', '0022_contractline_unit'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
