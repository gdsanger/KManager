"""
Auswertungen für das Finanzen-Dashboard.

Die Logik liegt bewusst hier und nicht in der View, damit sie ohne HTTP-Schicht
testbar bleibt und später von weiteren Auswertungen mitbenutzt werden kann.

Fachliche Festlegungen:

- **Einnahmen** kommen ausschließlich aus dem Rechnungsausgangsjournal
  (:class:`finanzen.models.OutgoingInvoiceJournalEntry`), nicht aus
  ``SalesDocument``. Nur so zeigt das Dashboard dieselben Zahlen wie der
  DATEV-Buchungsstapel; Entwürfe fließen nicht in eine Ertragsrechnung ein.
  Gutschriften stehen im Journal mit negativem Vorzeichen und mindern die
  Einnahmen deshalb ohne Sonderbehandlung.
- **Ausgaben** sind Eingangsrechnungen in den Status
  :data:`lieferantenwesen.models.EXPORTABLE_STATUSES` (freigegeben und
  bezahlt) – dieselbe Menge, die auch der DATEV-Export berücksichtigt.
- Ausgewertet wird immer **genau ein Mandant**. Eine Summe über mehrere
  Mandanten wäre kaufmännisch keine Ergebnisrechnung.

Die Monatssummen werden in der Datenbank gebildet (Gruppierung über den Monat
plus Aggregat), nicht durch Schleifen über einzelne Datensätze.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Count, DateField, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from auftragsverwaltung.models import SalesDocument
from finanzen.models import OutgoingInvoiceJournalEntry
from lieferantenwesen.models import EXPORTABLE_STATUSES, InvoiceIn


ZERO = Decimal('0.00')

# Wertebasis der Auswertung
VALUE_BASIS_NET = 'NET'
VALUE_BASIS_GROSS = 'GROSS'
VALUE_BASIS_CHOICES = [
    (VALUE_BASIS_NET, 'Netto'),
    (VALUE_BASIS_GROSS, 'Brutto'),
]

# Datumsbezug der Auswertung
DATE_BASIS_DOCUMENT = 'DOCUMENT'
DATE_BASIS_PAYMENT = 'PAYMENT'
DATE_BASIS_CHOICES = [
    (DATE_BASIS_DOCUMENT, 'Belegdatum'),
    (DATE_BASIS_PAYMENT, 'Zahldatum'),
]

MONTH_LABELS = [
    'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
    'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez',
]

# Höchstzahl der in den Karten „Offene Posten" gezeigten Zeilen. Die Summen im
# Kartenkopf gelten trotzdem für alle offenen Posten, nicht nur für die Auszüge.
OPEN_ITEM_LIMIT = 15

# Journalrelevante Belegarten – dieselbe Bedingung wie
# `finanzen.services.journal.get_document_kind()`, nur als Queryset-Filter:
# Rechnungen und Korrekturbelege (Gutschriften).
JOURNAL_RELEVANT_DOCUMENTS = Q(document_type__is_invoice=True) | Q(
    document_type__is_correction=True
)

# Aggregatsfelder mit ausreichend Stellen für Jahressummen.
AMOUNT_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _year_bounds(year):
    """(erster Tag, letzter Tag) des Kalenderjahres – beide Grenzen inklusive."""
    return date(year, 1, 1), date(year, 12, 31)


def _monthly_series(queryset, date_field, amount_expression, year):
    """
    Monatssummen eines Querysets als Liste mit zwölf Werten (Januar–Dezember).

    Monate ohne Bewegung erscheinen als 0, damit die Zeitachse im Diagramm
    nicht verzerrt.

    Args:
        queryset: bereits auf Mandant und Jahr eingeschränkte Grundmenge
        date_field: Feldpfad, über den gruppiert wird
        amount_expression: Aggregat (``Sum(...)``) für den Monatswert
        year: Kalenderjahr der Auswertung

    Returns:
        list[Decimal]: zwölf Monatssummen
    """
    rows = (
        queryset
        # `output_field=DateField()` rechnet ein DateTimeField (Zahldatum) vor
        # dem Abschneiden in die aktive Zeitzone um und liefert einen Tag –
        # identisch zum `__date`-Lookup beim Filtern.
        .annotate(month=TruncMonth(date_field, output_field=DateField()))
        .values('month')
        .annotate(total=amount_expression)
        .order_by()
    )

    series = [ZERO] * 12
    for row in rows:
        month = row['month']
        if month is None or month.year != year:
            continue
        series[month.month - 1] = row['total'] or ZERO
    return series


def _income_amount_expression(value_basis):
    """Aggregat für die Einnahmenseite je Wertebasis."""
    if value_basis == VALUE_BASIS_GROSS:
        return Sum('gross_amount', output_field=AMOUNT_FIELD)
    # Netto ist im Journal auf die Steuersätze aufgeteilt gespeichert.
    return Sum(
        F('net_0') + F('net_7') + F('net_19'),
        output_field=AMOUNT_FIELD,
    )


def _expense_amount_expression(value_basis):
    """
    Aggregat für die Ausgabenseite je Wertebasis.

    Netto- und Bruttobetrag der Eingangsrechnung sind nullable – fehlende Werte
    zählen als 0 statt die Summe zu verwerfen.
    """
    field_name = 'gross_amount' if value_basis == VALUE_BASIS_GROSS else 'net_amount'
    return Sum(
        Coalesce(F(field_name), Value(ZERO), output_field=AMOUNT_FIELD),
        output_field=AMOUNT_FIELD,
    )


def monthly_income(company, year, value_basis=VALUE_BASIS_NET,
                   date_basis=DATE_BASIS_DOCUMENT):
    """
    Einnahmen des Jahres je Monat aus dem Rechnungsausgangsjournal.

    Bei Datumsbezug „Zahldatum" erscheinen nur Belege mit erfasstem
    Zahlungseingang – ein unbezahlter Beleg ist kein Zahlungseingang.
    """
    if company is None:
        return [ZERO] * 12

    start, end = _year_bounds(year)
    queryset = OutgoingInvoiceJournalEntry.objects.filter(company=company)

    if date_basis == DATE_BASIS_PAYMENT:
        # `paid_at` ist ein DateTimeField; `__date` reduziert auf den Tag in der
        # aktiven Zeitzone. Einträge ohne Zahldatum fallen durch den Filter.
        queryset = queryset.filter(document__paid_at__date__range=(start, end))
        date_field = 'document__paid_at'
    else:
        queryset = queryset.filter(document_date__range=(start, end))
        date_field = 'document_date'

    return _monthly_series(
        queryset, date_field, _income_amount_expression(value_basis), year
    )


def monthly_expenses(company, year, value_basis=VALUE_BASIS_NET,
                     date_basis=DATE_BASIS_DOCUMENT):
    """
    Ausgaben des Jahres je Monat aus den Eingangsrechnungen.

    Berücksichtigt werden nur freigegebene und bezahlte Rechnungen; Entwürfe
    und Rechnungen in Prüfung sind buchhalterisch kein Aufwand.
    """
    if company is None:
        return [ZERO] * 12

    start, end = _year_bounds(year)
    queryset = InvoiceIn.objects.filter(
        company=company, status__in=EXPORTABLE_STATUSES
    )

    date_field = (
        'payment_date' if date_basis == DATE_BASIS_PAYMENT else 'invoice_date'
    )
    # Rechnungen ohne das jeweilige Datum fallen durch den Bereichsfilter.
    queryset = queryset.filter(**{f'{date_field}__range': (start, end)})

    return _monthly_series(
        queryset, date_field, _expense_amount_expression(value_basis), year
    )


def days_overdue(due_date, today):
    """Tage seit Fälligkeit (0, wenn nicht überfällig oder ohne Fälligkeit)."""
    if due_date is None or due_date >= today:
        return 0
    return (today - due_date).days


@dataclass(frozen=True)
class OpenItems:
    """Offene Posten einer Seite: Auszug plus Summen über die Gesamtmenge."""

    entries: list = field(default_factory=list)
    count: int = 0
    total: Decimal = ZERO
    overdue_count: int = 0
    truncated: bool = False


def open_receivables(company, today=None, limit=OPEN_ITEM_LIMIT):
    """
    Offene Posten Rechnungsausgang – Stichtagsbild, unabhängig vom Jahresfilter.

    Grundmenge: journalrelevante Belege des Mandanten ohne erfassten
    Zahlungseingang. Die Bedingung „offen" kommt aus
    :meth:`SalesDocument.unpaid_filter`, damit Belegliste, Belegseite und
    Dashboard dieselbe Definition verwenden.
    """
    today = today or timezone.localdate()
    if company is None:
        return OpenItems()

    queryset = SalesDocument.objects.filter(
        SalesDocument.unpaid_filter(),
        JOURNAL_RELEVANT_DOCUMENTS,
        company=company,
    )

    totals = queryset.aggregate(
        count=Count('pk'),
        total=Coalesce(
            Sum('total_gross', output_field=AMOUNT_FIELD),
            Value(ZERO),
            output_field=AMOUNT_FIELD,
        ),
        overdue_count=Count('pk', filter=Q(due_date__lt=today)),
    )

    entries = list(
        queryset
        .select_related('customer', 'document_type')
        # Ältestes zuerst; Belege ohne Fälligkeit hängen hinten an, weil sie
        # kein Alter haben, das man mahnen könnte.
        .order_by(F('due_date').asc(nulls_last=True), 'issue_date', 'number')[:limit]
    )
    for entry in entries:
        entry.days_overdue = days_overdue(entry.due_date, today)

    return OpenItems(
        entries=entries,
        count=totals['count'],
        total=totals['total'],
        overdue_count=totals['overdue_count'],
        truncated=totals['count'] > len(entries),
    )


def open_payables(company, today=None, limit=OPEN_ITEM_LIMIT):
    """
    Offene Posten Rechnungseingang – Stichtagsbild, unabhängig vom Jahresfilter.

    Grundmenge: freigegebene Eingangsrechnungen ohne Zahlungsdatum. Rechnungen
    in Prüfung sind noch nicht zur Zahlung freigegeben und damit kein offener
    Posten.
    """
    today = today or timezone.localdate()
    if company is None:
        return OpenItems()

    queryset = InvoiceIn.objects.filter(
        company=company, status='APPROVED', payment_date__isnull=True
    )

    totals = queryset.aggregate(
        count=Count('pk'),
        total=Coalesce(
            Sum('gross_amount', output_field=AMOUNT_FIELD),
            Value(ZERO),
            output_field=AMOUNT_FIELD,
        ),
        overdue_count=Count('pk', filter=Q(due_date__lt=today)),
    )

    entries = list(
        queryset
        .select_related('supplier', 'company')
        .order_by(F('due_date').asc(nulls_last=True), 'invoice_date', 'invoice_no')[:limit]
    )
    for entry in entries:
        entry.days_overdue = days_overdue(entry.due_date, today)

    return OpenItems(
        entries=entries,
        count=totals['count'],
        total=totals['total'],
        overdue_count=totals['overdue_count'],
        truncated=totals['count'] > len(entries),
    )


def basis_label(value_basis, date_basis):
    """Grundlage der Auswertung als Text, z. B. „Netto, nach Belegdatum"."""
    values = dict(VALUE_BASIS_CHOICES)
    dates = dict(DATE_BASIS_CHOICES)
    return (
        f'{values.get(value_basis, values[VALUE_BASIS_NET])}, nach '
        f'{dates.get(date_basis, dates[DATE_BASIS_DOCUMENT])}'
    )


@dataclass(frozen=True)
class DashboardData:
    """Ergebnis der Dashboard-Auswertung für einen Mandanten und ein Jahr."""

    company: object
    year: int
    value_basis: str
    date_basis: str
    month_labels: list
    income_by_month: list
    expense_by_month: list
    total_income: Decimal
    total_expenses: Decimal
    result: Decimal
    receivables: OpenItems
    payables: OpenItems
    today: date

    @property
    def monthly_rows(self):
        """Monatswerte als Zeilen für die Tabellensicht neben dem Diagramm."""
        return [
            {'label': label, 'income': income, 'expenses': expenses}
            for label, income, expenses in zip(
                self.month_labels, self.income_by_month, self.expense_by_month
            )
        ]

    @property
    def basis_label(self):
        """Grundlage der Kennzahlen als Text für die Anzeige."""
        return basis_label(self.value_basis, self.date_basis)

    @property
    def is_gross(self):
        """True, wenn die Kennzahlen die Umsatzsteuer enthalten."""
        return self.value_basis == VALUE_BASIS_GROSS

    @property
    def has_movement(self):
        """True, wenn im gewählten Jahr überhaupt Beträge angefallen sind."""
        return bool(self.total_income or self.total_expenses)


def build_dashboard(company, year, value_basis=VALUE_BASIS_NET,
                    date_basis=DATE_BASIS_DOCUMENT, today=None):
    """
    Vollständige Datengrundlage des Finanzen-Dashboards zusammenstellen.

    Die Jahressummen werden aus den Monatswerten gebildet – so entspricht die
    Kennzahl cent-genau der Summe der zugehörigen Diagrammlinie, und das
    Ergebnis cent-genau der Differenz der beiden Kennzahlen.
    """
    today = today or timezone.localdate()

    income = monthly_income(company, year, value_basis, date_basis)
    expenses = monthly_expenses(company, year, value_basis, date_basis)
    total_income = sum(income, ZERO)
    total_expenses = sum(expenses, ZERO)

    return DashboardData(
        company=company,
        year=year,
        value_basis=value_basis,
        date_basis=date_basis,
        month_labels=list(MONTH_LABELS),
        income_by_month=income,
        expense_by_month=expenses,
        total_income=total_income,
        total_expenses=total_expenses,
        result=total_income - total_expenses,
        receivables=open_receivables(company, today=today),
        payables=open_payables(company, today=today),
        today=today,
    )
