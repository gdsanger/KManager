"""
Rechnungsausgangsjournal-Service (Outgoing Invoice Journal)

Erzeugt die unveränderlichen Journaleinträge zu finalisierten Belegen
(Rechnungen und Gutschriften). Das Journal ist auf der Einnahmenseite die
alleinige Basis für den DATEV-Export; deshalb werden hier ausschließlich
Snapshot-Werte des Belegs geschrieben, die sich später nicht mehr mit dem
Beleg mitändern.

Fachliche Regeln:
- Genau ein Eintrag je (Mandant, Beleg) – die Erzeugung ist idempotent.
- Unterstützte Steuersätze: 0 %, 7 %, 19 %. Andere Steuersätze führen zu
  einem verständlichen Fehler statt zu einer stillen Falschbuchung.
- Gutschriften (Korrekturbelege) werden mit `document_kind='CREDIT_NOTE'`
  und negativen Beträgen gebucht, damit eine Summe über das Journal direkt
  den Umsatz der Periode ergibt.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction

from finanzen.models import CompanyAccountingSettings, OutgoingInvoiceJournalEntry


TWO_PLACES = Decimal('0.01')
FOUR_PLACES = Decimal('0.0001')
ZERO = Decimal('0.00')

# Unterstützte Steuersätze -> zugehöriges Snapshot-Feld im Journal
SUPPORTED_TAX_RATES = {
    Decimal('0.0000'): 'net_0',
    Decimal('0.0700'): 'net_7',
    Decimal('0.1900'): 'net_19',
}

# Zuordnung Journal-Nettofeld -> Erlöskonto-Feld (Mandanteneinstellung/Snapshot)
REVENUE_ACCOUNT_FIELDS = {
    'net_0': 'revenue_account_0',
    'net_7': 'revenue_account_7',
    'net_19': 'revenue_account_19',
}


class JournalEntryError(ValueError):
    """
    Fachlicher Fehler bei der Erzeugung eines Journaleintrags.

    Erbt bewusst von ``ValueError``: Die aufrufenden Views behandeln
    ``ValueError`` bereits als Anwenderfehler (HTTP 400 mit Meldung).
    """


class UnsupportedTaxRateError(JournalEntryError):
    """Der Beleg enthält einen Steuersatz, den das Journal nicht abbilden kann."""


def get_document_kind(document):
    """
    Belegart für das Journal bestimmen.

    Args:
        document: SalesDocument-Instanz

    Returns:
        str: 'INVOICE', 'CREDIT_NOTE' oder None, wenn der Beleg nicht
        journalrelevant ist (z. B. Angebot oder Lieferschein).
    """
    document_type = document.document_type

    # Korrekturbelege (Gutschriften) zuerst prüfen: Ein Dokumenttyp, der
    # beide Flags trägt (z. B. "Rechnungskorrektur"), ist fachlich eine
    # Gutschrift und muss mit negativem Vorzeichen ins Journal.
    if document_type.is_correction:
        return 'CREDIT_NOTE'
    if document_type.is_invoice:
        return 'INVOICE'
    return None


def require_document_kind(document):
    """
    Wie :func:`get_document_kind`, wirft aber bei nicht journalrelevanten
    Belegen einen :class:`JournalEntryError`.
    """
    kind = get_document_kind(document)
    if kind is None:
        raise JournalEntryError(
            f'Belegart "{document.document_type.name}" ist weder Rechnung noch Gutschrift '
            'und kann nicht im Rechnungsausgangsjournal gebucht werden.'
        )
    return kind


def _tax_field_for_rate(tax_rate):
    """Journal-Nettofeld für einen Steuersatz ermitteln (oder Fehler werfen)."""
    rate = (tax_rate.rate or ZERO).quantize(FOUR_PLACES)
    field = SUPPORTED_TAX_RATES.get(rate)
    if field is None:
        percent = (rate * Decimal('100')).quantize(TWO_PLACES)
        raise UnsupportedTaxRateError(
            f'Steuersatz "{tax_rate.code}" ({percent} %) wird im Rechnungsausgangsjournal '
            'nicht unterstützt. Zulässig sind nur 0 %, 7 % und 19 %.'
        )
    return field


def _amounts_from_lines(document):
    """
    Nettobeträge je Steuersatz aus den Belegpositionen aufteilen.

    Es zählen nur Positionen, die in die Belegsummen eingehen (NORMAL sowie
    ausgewählte OPTIONAL/ALTERNATIVE-Positionen).

    Returns:
        tuple(dict, Decimal) mit den Nettobeträgen je Feld und dem
        Steuerbetrag – oder None, wenn der Beleg gar keine Positionen hat.
    """
    nets = {'net_0': ZERO, 'net_7': ZERO, 'net_19': ZERO}
    tax_amount = ZERO
    has_lines = False

    for line in document.lines.select_related('tax_rate').all():
        has_lines = True
        if not line.is_included_in_totals():
            continue
        nets[_tax_field_for_rate(line.tax_rate)] += line.line_net
        tax_amount += line.line_tax

    if not has_lines:
        return None

    return nets, tax_amount


def _amounts_from_totals(document):
    """
    Fallback für Belege ohne Positionen (z. B. Altbestand): Aufteilung aus
    den Belegsummen ableiten.

    Der Steuersatz wird aus dem Verhältnis Steuer/Netto bestimmt und muss
    exakt einem unterstützten Satz entsprechen – sonst Fehler.
    """
    net_total = document.total_net or ZERO
    tax_amount = document.total_tax or ZERO

    if net_total == ZERO and tax_amount == ZERO:
        return {'net_0': ZERO, 'net_7': ZERO, 'net_19': ZERO}, ZERO

    if net_total == ZERO:
        raise JournalEntryError(
            f'Beleg {document.number} hat einen Steuerbetrag ohne Nettobetrag und kann '
            'nicht auf Steuersätze aufgeteilt werden.'
        )

    effective_rate = (tax_amount / net_total).quantize(FOUR_PLACES)
    field = SUPPORTED_TAX_RATES.get(effective_rate)
    if field is None:
        percent = (effective_rate * Decimal('100')).quantize(TWO_PLACES)
        raise UnsupportedTaxRateError(
            f'Beleg {document.number} hat keine Positionen und einen rechnerischen '
            f'Steuersatz von {percent} %. Für das Rechnungsausgangsjournal sind nur '
            '0 %, 7 % und 19 % zulässig.'
        )

    nets = {'net_0': ZERO, 'net_7': ZERO, 'net_19': ZERO}
    nets[field] = net_total
    return nets, tax_amount


def _derive_amounts(document):
    """
    Snapshot-Beträge des Belegs ermitteln und gegen die Belegsummen prüfen.

    Returns:
        tuple(dict, Decimal): Nettobeträge je Steuersatz und Steuerbetrag
        (jeweils ohne Vorzeichenlogik, also so wie am Beleg erfasst).
    """
    amounts = _amounts_from_lines(document)
    if amounts is None:
        return _amounts_from_totals(document)

    nets, tax_amount = amounts
    net_total = nets['net_0'] + nets['net_7'] + nets['net_19']

    # Cent-genauer Abgleich mit den denormalisierten Belegsummen: Weichen
    # Positionen und Kopfsummen ab, ist der Beleg nicht sauber gerechnet und
    # darf nicht gebucht werden.
    if (
        net_total != (document.total_net or ZERO)
        or tax_amount != (document.total_tax or ZERO)
        or (net_total + tax_amount) != (document.total_gross or ZERO)
    ):
        raise JournalEntryError(
            f'Beleg {document.number}: Positionssummen ({net_total} netto / {tax_amount} Steuer) '
            f'weichen von den Belegsummen ({document.total_net} netto / {document.total_tax} Steuer) ab. '
            'Bitte den Beleg neu berechnen (speichern) und erneut finalisieren.'
        )

    return nets, tax_amount


def _customer_snapshot(document):
    """Kundenname (Matchkey) und Debitorennummer als Snapshot ermitteln."""
    customer = document.customer
    if customer is None:
        raise JournalEntryError(
            f'Beleg {document.number} hat keinen Kunden und kann nicht im '
            'Rechnungsausgangsjournal gebucht werden.'
        )

    customer_name = (customer.matchkey or customer.name or '').strip()
    if not customer_name:
        raise JournalEntryError(
            f'Beleg {document.number}: Der Kunde hat keinen Namen und kann nicht '
            'ins Rechnungsausgangsjournal übernommen werden.'
        )

    return customer_name[:200], (customer.debitor_number or '')


def _revenue_account_snapshot(company):
    """Erlöskonten des Mandanten als Snapshot übernehmen (optional gepflegt)."""
    settings = CompanyAccountingSettings.objects.filter(company=company).first()
    if settings is None:
        return {field: '' for field in REVENUE_ACCOUNT_FIELDS.values()}
    return {
        field: getattr(settings, field, '') or ''
        for field in REVENUE_ACCOUNT_FIELDS.values()
    }


def create_journal_entry(document):
    """
    Journaleintrag zu einem finalisierten Beleg erzeugen (idempotent).

    Der Eintrag ist ein Snapshot: Alle Werte werden zum Zeitpunkt der
    Finalisierung kopiert und später nicht mehr nachgeführt.

    Args:
        document: finalisierte SalesDocument-Instanz (Rechnung oder Gutschrift)

    Returns:
        tuple: (entry, created) – Journaleintrag und ob er neu angelegt wurde

    Raises:
        JournalEntryError: Beleg ist nicht journalrelevant, unvollständig,
            in sich nicht schlüssig oder enthält einen nicht unterstützten
            Steuersatz.

    Example:
        >>> entry, created = create_journal_entry(invoice)
    """
    kind = require_document_kind(document)

    if not document.number:
        raise JournalEntryError(
            'Beleg ohne Belegnummer kann nicht im Rechnungsausgangsjournal gebucht werden.'
        )
    if not document.issue_date:
        raise JournalEntryError(
            f'Beleg {document.number} hat kein Belegdatum und kann nicht gebucht werden.'
        )

    # Idempotenz: Echtdruck und E-Mail-Versand finalisieren nacheinander
    # denselben Beleg – der zweite Aufruf darf keinen zweiten Eintrag anlegen.
    existing = OutgoingInvoiceJournalEntry.objects.filter(
        company=document.company,
        document=document,
    ).first()
    if existing is not None:
        return existing, False

    nets, tax_amount = _derive_amounts(document)
    customer_name, debtor_number = _customer_snapshot(document)

    # Gutschriften mindern den Umsatz: negatives Vorzeichen zusätzlich zum
    # Kennzeichen document_kind.
    sign = Decimal('-1') if kind == 'CREDIT_NOTE' else Decimal('1')
    signed_nets = {field: (value * sign) for field, value in nets.items()}
    signed_tax = tax_amount * sign
    gross_amount = (
        signed_nets['net_0'] + signed_nets['net_7'] + signed_nets['net_19'] + signed_tax
    )

    try:
        with transaction.atomic():
            entry = OutgoingInvoiceJournalEntry.objects.create(
                company=document.company,
                document=document,
                document_number=document.number,
                document_date=document.issue_date,
                document_kind=kind,
                customer_name=customer_name,
                debtor_number=debtor_number,
                tax_amount=signed_tax,
                gross_amount=gross_amount,
                export_status='OPEN',
                **signed_nets,
                **_revenue_account_snapshot(document.company),
            )
    except IntegrityError as exc:
        raise JournalEntryError(
            f'Journaleintrag für Beleg {document.number} konnte nicht angelegt werden: '
            'Belegnummer ist im Rechnungsausgangsjournal dieses Mandanten bereits vergeben.'
        ) from exc

    return entry, True
