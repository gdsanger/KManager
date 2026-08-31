"""
DATEV-Buchungsstapel-Export im EXTF-Format

Erzeugt für einen Zeitraum einen Buchungsstapel, den ein beliebiges
Fibu-System oder ein Steuerberater importieren kann. GIS bleibt damit
Belegerfassung; UStVA, EÜR, AfA und Kontenblätter macht das Zielsystem.

Quellen:
- **Einnahmenseite ausschließlich** ``finanzen.OutgoingInvoiceJournalEntry``.
  ``SalesDocument`` wird bewusst **nicht** gelesen: Nur die Snapshots des
  Rechnungsausgangsjournals ändern sich nicht nachträglich mit dem Beleg mit.
- **Ausgabenseite** ``lieferantenwesen.InvoiceIn`` (nur freigegebene bzw.
  bezahlte Rechnungen).

Beide Seiten werden auf den Mandanten des Stapels gefiltert: Der Kopfsatz trägt
dessen Berater- und Mandantennummer, ein mandantenfremder Beleg wäre dort eine
Falschbuchung.

Buchungslogik:
- Ausgangsrechnung: Debitor (Konto) an Erlöskonto (Gegenkonto), Umsatz brutto,
  Soll/Haben-Kennzeichen ``S``.
- Gutschrift: dieselben Konten, aber ``H`` – das Vorzeichen kommt aus den
  negativen Journalbeträgen und wird nicht gesondert modelliert.
- Eingangsrechnung: Aufwandskonto (Konto) an Kreditor (Gegenkonto), Umsatz
  brutto, ``S``.

Steuer:
Es wird **kein BU-Schlüssel** gesetzt. Die Steuer leitet das Zielsystem aus dem
Automatikkonto ab (z. B. SKR03/04 „Erlöse 19 % USt"). Ein selbst gesetzter
BU-Schlüssel wäre kontenrahmenabhängig und würde bei falscher Wahl still
falsch buchen; das Automatikkonto ist der dokumentierte Standardweg. Die
rechnerische Steuer je Steuersatz wird vor dem Export gegen die im Beleg
ausgewiesene Steuer geprüft (siehe :func:`_split_tax`).

Format:
EXTF, Formatversion 700, Formatname „Buchungsstapel" (Formatkategorie 21).
Die Feldliste steht als einzelne Konstante in diesem Modul
(:data:`BOOKING_COLUMNS`) und ist damit an einer Stelle nachziehbar, wenn
DATEV das Format weiterentwickelt. Siehe docs/DATEV_EXPORT.md.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from finanzen.models import (
    DEFAULT_ACCOUNT_LENGTH,
    DEFAULT_CLIENT_NUMBER,
    DEFAULT_CONSULTANT_NUMBER,
    CompanyAccountingSettings,
    OutgoingInvoiceJournalEntry,
)
from finanzen.services.accounts import (
    EXPENSE,
    AccountResolutionError,
    require_account,
)
# Zeichensatz, Trennzeichen, Zeilenende und Feldaufbereitung sind mit dem
# Stammdatenexport der Personenkonten geteilt und stehen deshalb in
# finanzen/services/datev_common.py. Hier bewusst re-exportiert, damit der
# Buchungsstapel weiterhin über dieses Modul ansprechbar bleibt.
from finanzen.services.datev_common import (  # noqa: F401
    DELIMITER,
    ENCODING,
    LINE_ENDING,
    _clean,
    _quote,
)
from lieferantenwesen.models import EXPORTABLE_STATUSES, InvoiceIn

ZERO = Decimal('0.00')
CENT = Decimal('0.01')

# Zulässige Abweichung zwischen rechnerischer und ausgewiesener Steuer.
# Deckt Rundungsdifferenzen ab, die beim Aufteilen der Belegsteuer auf die
# Steuersatz-Töpfe entstehen können; alles darüber ist ein struktureller Fehler
# und blockiert den Export.
TAX_TOLERANCE = Decimal('1.00')

# --- Formatkonstanten -------------------------------------------------------

FORMAT_KENNZEICHEN = 'EXTF'
FORMAT_VERSION = 700          # DATEV-Versionsnummer
FORMAT_CATEGORY = 21          # 21 = Buchungsstapel
FORMAT_NAME = 'Buchungsstapel'
FORMAT_NAME_VERSION = 13      # Formatversion innerhalb der Kategorie
BOOKING_TYPE = 1              # 1 = Finanzbuchführung
CURRENCY = 'EUR'
# 0 = nicht festgeschrieben. Bewusst nicht festgeschrieben exportiert, damit
# ein Fehlimport im Zielsystem korrigierbar bleibt.
FESTSCHREIBUNG = 0
ORIGIN = 'RE'                 # Herkunftskennzeichen (2 Zeichen)

# Feldlängen laut Formatbeschreibung
MAX_BELEGFELD1 = 36
MAX_BUCHUNGSTEXT = 60

# Spalten des Buchungssatzes (Überschriftenzeile, 2. Zeile der Datei).
# Reihenfolge und Anzahl sind Teil des Formats – hier bewusst vollständig
# ausgeschrieben statt generiert, damit Abweichungen sofort sichtbar sind.
BOOKING_COLUMNS = (
    [
        'Umsatz (ohne Soll/Haben-Kz)', 'Soll/Haben-Kennzeichen', 'WKZ Umsatz',
        'Kurs', 'Basis-Umsatz', 'WKZ Basis-Umsatz', 'Konto',
        'Gegenkonto (ohne BU-Schlüssel)', 'BU-Schlüssel', 'Belegdatum',
        'Belegfeld 1', 'Belegfeld 2', 'Skonto', 'Buchungstext',
        'Postensperre', 'Diverse Adressnummer', 'Geschäftspartnerbank',
        'Sachverhalt', 'Zinssperre', 'Beleglink',
    ]
    + [f'Beleginfo - {kind} {i}' for i in range(1, 9) for kind in ('Art', 'Inhalt')]
    + [
        'KOST1 - Kostenstelle', 'KOST2 - Kostenstelle', 'KOST-Menge',
        'EU-Land u. UStID (Bestimmung)', 'EU-Steuersatz (Bestimmung)',
        'Abw. Versteuerungsart', 'Sachverhalt L+L', 'Funktionsergänzung L+L',
        'BU 49 Hauptfunktionstyp', 'BU 49 Hauptfunktionsnummer',
        'BU 49 Funktionsergänzung',
    ]
    + [f'Zusatzinformation - {kind} {i}' for i in range(1, 21) for kind in ('Art', 'Inhalt')]
    + [
        'Stück', 'Gewicht', 'Zahlweise', 'Forderungsart', 'Veranlagungsjahr',
        'Zugeordnete Fälligkeit', 'Skontotyp', 'Auftragsnummer', 'Buchungstyp',
        'USt-Schlüssel (Anzahlungen)', 'EU-Land (Anzahlungen)',
        'Sachverhalt L+L (Anzahlungen)', 'EU-Steuersatz (Anzahlungen)',
        'Erlöskonto (Anzahlungen)', 'Herkunft-Kz', 'Buchungs GUID',
        'KOST-Datum', 'SEPA-Mandatsreferenz', 'Skontosperre',
        'Gesellschaftername', 'Beteiligtennummer', 'Identifikationsnummer',
        'Zeichnernummer', 'Postensperre bis', 'Bezeichnung SoBil-Sachverhalt',
        'Kennzeichen SoBil-Buchung', 'Festschreibung', 'Leistungsdatum',
        'Datum Zuord. Steuerperiode',
    ]
    + [
        # Ab Formatversion 700 ergänzte Felder
        'Fälligkeit', 'Generalumkehr (GU)', 'Steuersatz', 'Land',
        'Abrechnungsreferenz', 'BVV-Position', 'EU-Land u. UStID (Ursprung)',
        'EU-Steuersatz (Ursprung)', 'Abw. Skontokonto',
    ]
)

# Spaltenindizes (0-basiert) der tatsächlich befüllten Felder
COL_UMSATZ = 0
COL_SOLL_HABEN = 1
COL_WKZ = 2
COL_KONTO = 6
COL_GEGENKONTO = 7
COL_BELEGDATUM = 9
COL_BELEGFELD1 = 10
COL_BUCHUNGSTEXT = 13
COL_FESTSCHREIBUNG = BOOKING_COLUMNS.index('Festschreibung')
COL_LEISTUNGSDATUM = BOOKING_COLUMNS.index('Leistungsdatum')

# Steuersätze der Einnahmenseite: Journalfeld -> (Schlüssel, Satz)
JOURNAL_TAX_BUCKETS = [
    ('net_0', '0', Decimal('0.00'), 'revenue_account_0'),
    ('net_7', '7', Decimal('0.07'), 'revenue_account_7'),
    ('net_19', '19', Decimal('0.19'), 'revenue_account_19'),
]


class DatevExportError(ValueError):
    """Der Buchungsstapel kann für den gewählten Zeitraum nicht erzeugt werden."""


# --- Datenstrukturen --------------------------------------------------------

@dataclass
class Booking:
    """Ein einzelner Buchungssatz des Stapels."""

    amount: Decimal          # Bruttobetrag, vorzeichenbehaftet
    account: str             # Konto
    contra_account: str      # Gegenkonto
    document_date: date
    document_field_1: str    # Belegfeld 1 (Belegnummer)
    text: str                # Buchungstext
    service_date: date = None  # Leistungsdatum (optional)

    @property
    def debit_credit(self):
        """Soll/Haben-Kennzeichen aus dem Vorzeichen ableiten."""
        return 'S' if self.amount >= ZERO else 'H'


@dataclass
class ExportProblem:
    """Ein Beleg, der nicht exportiert werden kann."""

    source: str      # 'AUSGANG' oder 'EINGANG'
    reference: str   # Belegnummer
    document_date: date
    message: str


@dataclass
class ExportPreview:
    """Ergebnis der Vorschau: was exportiert würde und was blockiert."""

    company: object
    date_from: date
    date_to: date
    bookings: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    journal_entries: list = field(default_factory=list)
    incoming_invoices: list = field(default_factory=list)
    skipped_exported: int = 0

    @property
    def has_problems(self):
        return bool(self.problems)

    @property
    def booking_count(self):
        return len(self.bookings)

    @property
    def total_debit(self):
        """Summe aller Sollbuchungen (positive Beträge)."""
        return sum((b.amount for b in self.bookings if b.amount >= ZERO), ZERO)

    @property
    def total_credit(self):
        """Summe aller Habenbuchungen (als positiver Betrag)."""
        return -sum((b.amount for b in self.bookings if b.amount < ZERO), ZERO)

    @property
    def outgoing_total(self):
        return sum((e.gross_amount for e in self.journal_entries), ZERO)

    @property
    def incoming_total(self):
        return sum((i.gross_amount or ZERO for i in self.incoming_invoices), ZERO)


# --- Hilfsfunktionen --------------------------------------------------------

def _german_amount(value):
    """Betrag im deutschen Zahlenformat, immer positiv, zwei Nachkommastellen."""
    return f'{abs(Decimal(value)).quantize(CENT):.2f}'.replace('.', ',')


def _get_settings(company):
    """Buchhaltungseinstellungen des Mandanten laden (oder Fehler)."""
    settings = CompanyAccountingSettings.objects.filter(company=company).first()
    if settings is None:
        raise DatevExportError(
            f'Für den Mandanten "{company}" sind keine Buchhaltungseinstellungen '
            'hinterlegt. Bitte zuerst Beraternummer, Mandantennummer und '
            'Erlöskonten pflegen.'
        )
    return settings


def _split_tax(entry):
    """
    Nettobeträge des Journaleintrags je Steuersatz um die Steuer ergänzen.

    Die Steuer wird je Steuersatz gerechnet; die Rundungsdifferenz zur im
    Beleg ausgewiesenen Gesamtsteuer landet im betragsstärksten steuerpflichtigen
    Topf. Dadurch bleibt die Belegsumme cent-genau, auch wenn ein Beleg mehrere
    Steuersätze enthält.

    Returns:
        list[tuple(str, str, Decimal, Decimal)]:
            (Journalfeld, Steuersatz-Schlüssel, Netto, Steuer)

    Raises:
        DatevExportError: wenn rechnerische und ausgewiesene Steuer um mehr als
            :data:`TAX_TOLERANCE` auseinanderliegen.
    """
    buckets = []
    for net_field, tax_key, rate, _account_field in JOURNAL_TAX_BUCKETS:
        net = getattr(entry, net_field) or ZERO
        if net == ZERO:
            continue
        buckets.append([net_field, tax_key, net, (net * rate).quantize(CENT), rate])

    if not buckets:
        return []

    computed = sum(b[3] for b in buckets)
    difference = (entry.tax_amount or ZERO) - computed

    if difference != ZERO:
        if abs(difference) > TAX_TOLERANCE:
            raise DatevExportError(
                f'Beleg {entry.document_number}: Die ausgewiesene Umsatzsteuer '
                f'({entry.tax_amount}) weicht um {difference} von der rechnerischen '
                f'Steuer ({computed}) ab. Der Beleg kann nicht sauber auf Steuersätze '
                'aufgeteilt werden.'
            )
        taxed = [b for b in buckets if b[4] > 0]
        if not taxed:
            raise DatevExportError(
                f'Beleg {entry.document_number}: Es ist Umsatzsteuer ausgewiesen '
                f'({entry.tax_amount}), aber kein steuerpflichtiger Nettobetrag '
                'vorhanden.'
            )
        largest = max(taxed, key=lambda b: abs(b[2]))
        largest[3] += difference

    return [(b[0], b[1], b[2], b[3]) for b in buckets]


# --- Einnahmenseite ---------------------------------------------------------

def _collect_outgoing(preview, company, date_from, date_to, include_exported):
    """
    Buchungssätze der Ausgangsseite ausschließlich aus dem
    Rechnungsausgangsjournal aufbauen.
    """
    entries = OutgoingInvoiceJournalEntry.objects.filter(
        company=company,
        document_date__gte=date_from,
        document_date__lte=date_to,
    ).order_by('document_date', 'document_number')

    if not include_exported:
        already = entries.filter(export_status='EXPORTED').count()
        preview.skipped_exported += already
        entries = entries.exclude(export_status='EXPORTED')

    for entry in entries:
        debtor = (entry.debtor_number or '').strip()
        if not debtor:
            preview.problems.append(ExportProblem(
                'AUSGANG', entry.document_number, entry.document_date,
                'Kein Debitorenkonto im Journaleintrag hinterlegt. Der Kunde hatte '
                'zum Zeitpunkt der Finalisierung kein Personenkonto.',
            ))
            continue

        try:
            buckets = _split_tax(entry)
        except DatevExportError as exc:
            preview.problems.append(ExportProblem(
                'AUSGANG', entry.document_number, entry.document_date, str(exc),
            ))
            continue

        if not buckets:
            # Nullbeleg: nichts zu buchen, aber auch kein Fehler.
            preview.journal_entries.append(entry)
            continue

        entry_bookings = []
        failed = False
        for net_field, tax_key, net, tax in buckets:
            account_field = next(
                b[3] for b in JOURNAL_TAX_BUCKETS if b[0] == net_field
            )
            revenue_account = (getattr(entry, account_field, '') or '').strip()
            if not revenue_account:
                preview.problems.append(ExportProblem(
                    'AUSGANG', entry.document_number, entry.document_date,
                    f'Kein Erlöskonto für den Steuersatz {tax_key} % im '
                    'Journaleintrag hinterlegt. Bitte das Erlöskonto in den '
                    'Buchhaltungseinstellungen bzw. an der Kostenart pflegen; '
                    'der Beleg muss anschließend neu finalisiert werden.',
                ))
                failed = True
                break

            kind = 'Gutschrift' if entry.document_kind == 'CREDIT_NOTE' else 'Rechnung'
            entry_bookings.append(Booking(
                amount=net + tax,
                account=debtor,
                contra_account=revenue_account,
                document_date=entry.document_date,
                document_field_1=entry.document_number,
                text=f'{kind} {entry.customer_name}',
            ))

        if failed:
            continue

        preview.bookings.extend(entry_bookings)
        preview.journal_entries.append(entry)


# --- Ausgabenseite ----------------------------------------------------------

def _invoice_cost_types(invoice, line=None):
    """
    Maßgebliche Kostenarten für eine Eingangsrechnung(sposition) bestimmen.

    Position vor Kopf: Trägt die Position eine eigene Kostenart, gilt diese
    vollständig; sonst die Kostenart des Rechnungskopfs. Eine Mischung aus
    Positions-Unterkostenart und Kopf-Hauptkostenart wäre nicht nachvollziehbar.
    """
    if line is not None and (line.cost_type_sub_line_id or line.cost_type_main_line_id):
        return line.cost_type_sub_line, line.cost_type_main_line
    return invoice.cost_type_sub, invoice.cost_type_main


def _incoming_bookings(invoice):
    """
    Buchungssätze einer Eingangsrechnung erzeugen.

    Hat die Rechnung Positionen, wird je Kombination aus Aufwandskonto und
    Steuersatz ein Buchungssatz gebildet – so werden Belege mit mehreren
    Steuersätzen korrekt aufgeteilt. Ohne Positionen entsteht ein Buchungssatz
    aus den Kopfbeträgen.

    Raises:
        AccountResolutionError: wenn ein Aufwandskonto fehlt.
        DatevExportError: wenn die Positionssummen nicht zur Kopfsumme passen.
    """
    context = f'Eingangsrechnung {invoice.invoice_no}'
    supplier = invoice.supplier
    creditor = (supplier.debitor_number or '').strip() if supplier else ''
    if not creditor:
        raise DatevExportError(
            f'{context}: Der Lieferant "{supplier}" hat kein Kreditorenkonto.'
        )

    text = _clean(invoice.subject or str(supplier), MAX_BUCHUNGSTEXT)
    lines = list(invoice.lines.select_related(
        'cost_type_main_line', 'cost_type_sub_line', 'cost_type_sub_line__parent',
    ).all())

    if not lines:
        gross = invoice.gross_amount
        if gross is None or gross == ZERO:
            return []
        cost_sub, cost_main = _invoice_cost_types(invoice)
        account = require_account(
            EXPENSE, cost_type_sub=cost_sub, cost_type_main=cost_main, context=context,
        )
        return [Booking(
            amount=gross,
            account=account,
            contra_account=creditor,
            document_date=invoice.invoice_date,
            document_field_1=invoice.invoice_no,
            text=text,
            service_date=invoice.service_period_to or invoice.service_period_from,
        )]

    # Je (Aufwandskonto, Steuersatz) zusammenfassen
    grouped = {}
    for line in lines:
        cost_sub, cost_main = _invoice_cost_types(invoice, line)
        account = require_account(
            EXPENSE, cost_type_sub=cost_sub, cost_type_main=cost_main, context=context,
        )
        rate = line.tax_rate if line.tax_rate is not None else ZERO
        net = line.net_amount or ZERO
        tax = line.tax_amount
        if tax is None:
            tax = (net * rate / Decimal('100')).quantize(CENT)
        key = (account, rate)
        grouped.setdefault(key, ZERO)
        grouped[key] += net + tax

    total = sum(grouped.values(), ZERO)
    header_gross = invoice.gross_amount
    if header_gross is not None and total != header_gross:
        raise DatevExportError(
            f'{context}: Die Positionssummen ({total}) weichen vom Bruttobetrag '
            f'der Rechnung ({header_gross}) ab. Bitte die Rechnung korrigieren.'
        )

    return [
        Booking(
            amount=amount,
            account=account,
            contra_account=creditor,
            document_date=invoice.invoice_date,
            document_field_1=invoice.invoice_no,
            text=text,
            service_date=invoice.service_period_to or invoice.service_period_from,
        )
        for (account, _rate), amount in grouped.items()
        if amount != ZERO
    ]


def _report_incoming_without_company(preview, date_from, date_to):
    """
    Buchungsreife Eingangsrechnungen ohne Mandant in die Fehlerliste stellen.

    Ohne Mandant gehört der Beleg in keinen Buchungsstapel – er würde sonst je
    nach Filterung in gar keinem oder im falschen landen. Gemeldet werden nur
    Belege im gewählten Zeitraum mit exportfähigem Status, damit die
    Fehlerliste nicht durch Entwürfe oder fremde Perioden zuwächst.

    Der Export-Status spielt hier bewusst keine Rolle: Ein Beleg ohne Mandant
    ist auch dann noch offen, wenn er versehentlich schon einmal mitexportiert
    wurde.
    """
    orphans = InvoiceIn.objects.filter(
        company__isnull=True,
        invoice_date__gte=date_from,
        invoice_date__lte=date_to,
        status__in=EXPORTABLE_STATUSES,
    ).order_by('invoice_date', 'invoice_no')

    for invoice in orphans:
        preview.problems.append(ExportProblem(
            'EINGANG', invoice.invoice_no, invoice.invoice_date,
            'Der Rechnung ist kein Mandant zugeordnet. Bitte den Mandanten am '
            'Beleg pflegen; sonst lässt sich nicht entscheiden, in welchen '
            'Buchungsstapel der Aufwand gehört.',
        ))


def _collect_incoming(preview, company, date_from, date_to, include_exported):
    """
    Buchungssätze der Eingangsseite aus freigegebenen Eingangsrechnungen.

    Es werden ausschließlich Rechnungen **dieses** Mandanten gebucht. Belege
    ohne Mandant lassen sich keinem Buchungsstapel zuordnen und werden nicht
    still übergangen, sondern gemeldet (siehe :func:`_report_incoming_without_company`).
    """
    _report_incoming_without_company(preview, date_from, date_to)

    invoices = InvoiceIn.objects.filter(
        company=company,
        invoice_date__gte=date_from,
        invoice_date__lte=date_to,
        status__in=EXPORTABLE_STATUSES,
    ).select_related(
        'supplier', 'cost_type_main', 'cost_type_sub', 'cost_type_sub__parent',
    ).order_by('invoice_date', 'invoice_no')

    if not include_exported:
        already = invoices.filter(export_status='EXPORTED').count()
        preview.skipped_exported += already
        invoices = invoices.exclude(export_status='EXPORTED')

    for invoice in invoices:
        try:
            bookings = _incoming_bookings(invoice)
        except (AccountResolutionError, DatevExportError) as exc:
            preview.problems.append(ExportProblem(
                'EINGANG', invoice.invoice_no, invoice.invoice_date, str(exc),
            ))
            continue

        preview.bookings.extend(bookings)
        preview.incoming_invoices.append(invoice)


# --- Öffentliche API --------------------------------------------------------

def build_preview(company, date_from, date_to, include_exported=False):
    """
    Buchungsstapel für einen Zeitraum zusammenstellen, ohne ihn zu schreiben.

    Args:
        company: core.Mandant
        date_from, date_to: Zeitraumgrenzen (inklusive)
        include_exported: True, um bereits exportierte Belege bewusst erneut
            aufzunehmen (Wiederholungsexport nach Fehlimport)

    Returns:
        ExportPreview – enthält Buchungssätze **und** die Fehlerliste. Belege
        ohne auflösbares Konto sowie Eingangsrechnungen ohne Mandant stehen in
        ``problems`` und werden nicht still übergangen.

    Raises:
        DatevExportError: bei unbrauchbarem Zeitraum oder fehlenden
            Buchhaltungseinstellungen.
    """
    if date_from > date_to:
        raise DatevExportError('Das Von-Datum muss vor dem Bis-Datum liegen.')
    if date_from.year != date_to.year:
        # Das Belegdatum eines Buchungssatzes trägt nur Tag und Monat; der
        # Jahresbezug kommt aus dem Kopfsatz. Ein jahresübergreifender Stapel
        # wäre dadurch mehrdeutig.
        raise DatevExportError(
            'Ein Buchungsstapel darf nicht über einen Jahreswechsel gehen. '
            'Bitte je Jahr einen eigenen Export erzeugen.'
        )

    _get_settings(company)

    preview = ExportPreview(company=company, date_from=date_from, date_to=date_to)
    _collect_outgoing(preview, company, date_from, date_to, include_exported)
    _collect_incoming(preview, company, date_from, date_to, include_exported)
    return preview


def _header_row(company, settings, date_from, date_to, created_at):
    """Kopfsatz (1. Zeile) des EXTF-Buchungsstapels."""
    consultant = (settings.datev_consultant_number or '').strip() or DEFAULT_CONSULTANT_NUMBER
    client = (settings.datev_client_number or '').strip() or DEFAULT_CLIENT_NUMBER
    account_length = settings.account_length or DEFAULT_ACCOUNT_LENGTH
    fiscal_start = settings.effective_fiscal_year_start(date_from.year)

    label = (
        f'{company.name} {date_from.strftime("%d.%m.%Y")}-{date_to.strftime("%d.%m.%Y")}'
    )

    return [
        _quote(FORMAT_KENNZEICHEN),
        str(FORMAT_VERSION),
        str(FORMAT_CATEGORY),
        _quote(FORMAT_NAME),
        str(FORMAT_NAME_VERSION),
        created_at.strftime('%Y%m%d%H%M%S') + '000',
        '',                                    # Importiert (leer beim Export)
        _quote(ORIGIN),
        _quote(_clean(company.name, 25)),      # Exportiert von
        '',                                    # Importiert von
        consultant,
        client,
        fiscal_start.strftime('%Y%m%d'),
        str(account_length),
        date_from.strftime('%Y%m%d'),
        date_to.strftime('%Y%m%d'),
        _quote(_clean(label, 30)),
        _quote(''),                            # Diktatkürzel
        str(BOOKING_TYPE),
        '',                                    # Rechnungslegungszweck
        str(FESTSCHREIBUNG),
        _quote(CURRENCY),
        '',                                    # reserviert
        _quote(''),                            # Derivatskennzeichen
        '',                                    # reserviert
        '',                                    # reserviert
        _quote(''),                            # SKR
        '',                                    # Branchenlösungs-Id
        '',                                    # reserviert
        '',                                    # reserviert
        _quote(''),                            # Anwendungsinformation
    ]


def _booking_row(booking):
    """Einen Buchungssatz auf die Spalten des Formats abbilden."""
    row = [''] * len(BOOKING_COLUMNS)
    row[COL_UMSATZ] = _german_amount(booking.amount)
    row[COL_SOLL_HABEN] = _quote(booking.debit_credit)
    row[COL_WKZ] = _quote(CURRENCY)
    row[COL_KONTO] = booking.account
    row[COL_GEGENKONTO] = booking.contra_account
    row[COL_BELEGDATUM] = booking.document_date.strftime('%d%m')
    row[COL_BELEGFELD1] = _quote(_clean(booking.document_field_1, MAX_BELEGFELD1))
    row[COL_BUCHUNGSTEXT] = _quote(_clean(booking.text, MAX_BUCHUNGSTEXT))
    row[COL_FESTSCHREIBUNG] = str(FESTSCHREIBUNG)
    if booking.service_date:
        row[COL_LEISTUNGSDATUM] = _quote(booking.service_date.strftime('%d%m%Y'))
    return row


def render_extf(preview, created_at=None):
    """
    Den Buchungsstapel als EXTF-Datei rendern.

    Args:
        preview: ExportPreview aus :func:`build_preview`
        created_at: Erzeugungszeitpunkt (Default: jetzt)

    Returns:
        bytes: die Datei im DATEV-Zeichensatz (Windows-1252)

    Raises:
        DatevExportError: wenn noch Belege in der Fehlerliste stehen. Ein
            stillschweigend kleinerer Stapel wäre der teurere Fehler.
    """
    if preview.has_problems:
        raise DatevExportError(
            f'{len(preview.problems)} Beleg(e) können nicht exportiert werden. '
            'Bitte zuerst die Fehlerliste abarbeiten.'
        )

    settings = _get_settings(preview.company)
    created_at = created_at or timezone.localtime()
    if isinstance(created_at, datetime) and timezone.is_aware(created_at):
        created_at = timezone.localtime(created_at)

    rows = [
        _header_row(
            preview.company, settings, preview.date_from, preview.date_to, created_at,
        ),
        [_quote(name) for name in BOOKING_COLUMNS],
    ]
    rows.extend(_booking_row(b) for b in preview.bookings)

    content = LINE_ENDING.join(DELIMITER.join(row) for row in rows) + LINE_ENDING
    return content.encode(ENCODING, errors='replace')


def build_filename(preview):
    """Sprechender Dateiname für den Download."""
    return (
        f'EXTF_Buchungsstapel_{preview.date_from:%Y%m%d}_{preview.date_to:%Y%m%d}.csv'
    )


@transaction.atomic
def mark_exported(preview, batch_id):
    """
    Exportierte Belege als exportiert kennzeichnen.

    Setzt Export-Status, Zeitpunkt und Batch-ID auf beiden Seiten. Die Batch-ID
    macht einen bewussten Wiederholungsexport im Nachhinein erkennbar: Der
    Beleg trägt dann die ID des letzten Exports.

    Args:
        preview: ExportPreview, aus dem die Datei erzeugt wurde
        batch_id: Kennung dieser Export-Charge
    """
    now = timezone.now()

    journal_ids = [e.pk for e in preview.journal_entries]
    if journal_ids:
        OutgoingInvoiceJournalEntry.objects.filter(pk__in=journal_ids).update(
            export_status='EXPORTED', exported_at=now, export_batch_id=batch_id,
        )

    invoice_ids = [i.pk for i in preview.incoming_invoices]
    if invoice_ids:
        InvoiceIn.objects.filter(pk__in=invoice_ids).update(
            export_status='EXPORTED', exported_at=now, export_batch_id=batch_id,
        )
