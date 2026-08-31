"""
Artikelumsatz-Auswertung: Rangliste der Artikel nach Nettoumsatz.

Die Auswertung beantwortet „womit verdiene ich eigentlich Geld" und liegt
bewusst hier und nicht in der View, damit sie ohne HTTP-Schicht testbar ist.

Fachliche Festlegungen:

- **Grundlage sind Belegpositionen, nicht das Journal.** Für Kunden,
  Lieferanten und das Finanzen-Dashboard gilt die Regel, dass Umsätze
  ausschließlich aus dem Rechnungsausgangsjournal stammen. Sie lässt sich hier
  nicht anwenden: :class:`finanzen.models.OutgoingInvoiceJournalEntry` speichert
  nur Nettobeträge je Steuersatz und kennt keine Positionen. Eine
  Artikelauswertung ist zwangsläufig eine Positionsfrage und muss über
  :class:`auftragsverwaltung.models.SalesDocumentLine` laufen.
- Daraus folgt: Artikelumsätze sind eine **Steuerungsgröße, keine
  Buchungsgröße**. ``auftragsverwaltung.views.document_update()`` sperrt Belege
  nicht nach Status; eine bereits finalisierte Rechnung kann in ihren Positionen
  nachträglich verändert worden sein. Die Summe der Artikelumsätze kann deshalb
  geringfügig von den Journalzahlen abweichen. Die Oberfläche benennt das.
- **Gutschriften mindern den Umsatz.** Die Positionen einer Gutschrift sind
  positiv gespeichert; das negative Vorzeichen setzt erst das Journal beim
  Anlegen des Eintrags (``finanzen.services.journal.create_journal_entry()``).
  Wer die Positionen ungeprüft aufsummiert, addiert Gutschriften zum Umsatz
  hinzu, statt sie abzuziehen. Das Vorzeichen wird deshalb hier beim Aggregieren
  gesetzt – in derselben Reihenfolge wie
  :func:`finanzen.services.journal.get_document_kind`: ein Belegtyp mit beiden
  Flags ist fachlich eine Gutschrift.
- **Positionen ohne Artikelbezug** (``SalesDocumentLine.item`` ist nullable)
  werden nicht weggelassen, sondern als eigene Zeile „Ohne Artikelbezug"
  ausgewiesen. Sonst stimmt die Summe der Auswertung nicht mit dem
  Gesamtumsatz überein, und niemand kann nachvollziehen, wo die Differenz
  herkommt.
- **Einheiten werden nicht stillschweigend zusammengeworfen.** Die Position
  trägt eine eigene Einheit als Snapshot. Tragen die Positionen eines Artikels
  unterschiedliche Einheiten, weist die Zeile die Menge als uneinheitlich aus –
  eine Summe aus Stunden und Stück ist keine Menge.
- Ausgewertet wird immer **genau ein Mandant** und **genau ein Kalenderjahr**.

Die Aggregation erfolgt vollständig in der Datenbank (Gruppierung über den
Artikel bzw. den Monat plus Aggregat), nicht durch Schleifen über einzelne
Positionen.
"""
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import (
    Case,
    Count,
    DateField,
    DecimalField,
    F,
    IntegerField,
    Max,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, TruncMonth

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine
from finanzen.services.dashboard import MONTH_LABELS, ZERO


# Aggregatsfelder mit ausreichend Stellen für Jahressummen. Die Menge behält
# die vier Nachkommastellen der Position.
NET_FIELD = DecimalField(max_digits=16, decimal_places=2)
QUANTITY_FIELD = DecimalField(max_digits=16, decimal_places=4)
ZERO_QUANTITY = Decimal('0.0000')
HUNDRED = Decimal('100')
PERCENT = Decimal('0.01')

# Journalrelevante Belegarten aus Sicht der Position – dieselbe Bedingung wie
# `finanzen.services.journal.get_document_kind()`: Rechnungen und
# Korrekturbelege (Gutschriften). Angebote, Aufträge und Lieferscheine sind
# kein Umsatz.
JOURNAL_RELEVANT_LINES = Q(document__document_type__is_invoice=True) | Q(
    document__document_type__is_correction=True
)

# Positionen, die in die Belegsummen eingehen – Nachbildung von
# `SalesDocumentLine.is_included_in_totals()` als Filterbedingung:
# NORMAL immer, OPTIONAL/ALTERNATIVE nur wenn ausgewählt.
INCLUDED_IN_TOTALS = Q(line_type='NORMAL') | Q(is_selected=True)

# Schlüssel und Beschriftung der Sammelzeile für Positionen ohne Artikelbezug.
NO_ITEM_KEY = 'ohne-artikel'
NO_ITEM_LABEL = 'Ohne Artikelbezug'

# Sortierbare Spalten -> Annotationsname. Die Zuordnung ist bewusst eine
# Whitelist: der Sortierschlüssel kommt aus der URL.
SORT_NET = 'net'
SORT_QUANTITY = 'quantity'
SORT_DOCUMENTS = 'documents'
SORT_FIELDS = {
    SORT_NET: 'net',
    SORT_QUANTITY: 'quantity',
    SORT_DOCUMENTS: 'document_count',
}
DEFAULT_SORT = SORT_NET


def resolve_sort(sort, direction):
    """
    Sortierwunsch aus der URL auf gültige Werte abbilden.

    Args:
        sort: Spaltenschlüssel aus der URL (oder None)
        direction: 'asc' oder 'desc' (oder None)

    Returns:
        tuple(str, bool): Spaltenschlüssel und ``descending``. Unbekannte Werte
        fallen auf „Umsatz absteigend" zurück – ein manipulierter Link darf
        keine Fehlerseite erzeugen.
    """
    if sort not in SORT_FIELDS:
        return DEFAULT_SORT, True
    return sort, direction != 'asc'


def _year_bounds(year):
    """(erster Tag, letzter Tag) des Kalenderjahres – beide Grenzen inklusive."""
    return date(year, 1, 1), date(year, 12, 31)


def _sign():
    """
    Vorzeichen der Position nach Belegart.

    Korrekturbelege zuerst prüfen – identisch zu
    :func:`finanzen.services.journal.get_document_kind`: Ein Dokumenttyp, der
    beide Flags trägt (z. B. „Rechnungskorrektur"), ist fachlich eine
    Gutschrift und geht negativ ein.
    """
    return Case(
        When(document__document_type__is_correction=True, then=Value(-1)),
        default=Value(1),
        output_field=IntegerField(),
    )


def _signed_net():
    """Nettoumsatz-Aggregat mit Vorzeichen nach Belegart."""
    return Coalesce(
        Sum(F('line_net') * _sign(), output_field=NET_FIELD),
        Value(ZERO),
        output_field=NET_FIELD,
    )


def _signed_quantity():
    """Mengen-Aggregat mit Vorzeichen nach Belegart."""
    return Coalesce(
        Sum(F('quantity') * _sign(), output_field=QUANTITY_FIELD),
        Value(ZERO_QUANTITY),
        output_field=QUANTITY_FIELD,
    )


def group_filter(group):
    """
    Filterbedingung einer Warengruppe – bei einer Hauptgruppe inklusive
    Untergruppen.

    Analog zur Filterlogik in ``core.views.item_management()``, dort allerdings
    auf dem Artikel selbst. Artikel, die direkt an der Hauptgruppe hängen,
    zählen mit: sie gehören fachlich zu dieser Gruppe und dürften in einer
    Umsatzauswertung nicht verschwinden.

    Args:
        group: :class:`core.models.ItemGroup`

    Returns:
        django.db.models.Q
    """
    if group.group_type == 'MAIN':
        return Q(item__item_group=group) | Q(item__item_group__parent=group)
    return Q(item__item_group=group)


def line_queryset(company, year, group=None):
    """
    Grundmenge der Auswertung: Positionen journalrelevanter, finalisierter
    Belege des Mandanten im gewählten Jahr.

    Ausgeschlossen sind Entwürfe und stornierte Belege
    (:data:`SalesDocument.NON_PAYABLE_STATUSES`) sowie nicht ausgewählte
    OPTIONAL-/ALTERNATIVE-Positionen.

    Args:
        company: :class:`core.models.Mandant`
        year: Kalenderjahr
        group: optionale :class:`core.models.ItemGroup`

    Returns:
        QuerySet[SalesDocumentLine]
    """
    first_day, last_day = _year_bounds(year)
    queryset = (
        SalesDocumentLine.objects
        .filter(
            JOURNAL_RELEVANT_LINES,
            INCLUDED_IN_TOTALS,
            document__company=company,
            document__issue_date__range=(first_day, last_day),
        )
        .exclude(document__status__in=SalesDocument.NON_PAYABLE_STATUSES)
    )
    if group is not None:
        queryset = queryset.filter(group_filter(group))
    return queryset


@dataclass(frozen=True)
class ItemRevenueRow:
    """
    Eine Zeile der Rangliste – ein Artikel oder die Sammelzeile ohne
    Artikelbezug.

    ``quantity`` ist ``None``, wenn die Positionen unterschiedliche Einheiten
    tragen. Die Unterscheidung ist fachlich wichtig: eine 0 oder eine addierte
    Zahl würde eine Menge behaupten, die es nicht gibt.
    """

    key: str
    item_id: int | None
    article_no: str
    label: str
    group_name: str
    net: Decimal
    quantity: Decimal | None
    unit_label: str
    document_count: int
    share_percent: Decimal | None

    @property
    def has_item(self):
        """True für echte Artikel – nur die haben einen Link in die Artikelverwaltung."""
        return self.item_id is not None

    @property
    def is_negative(self):
        """True bei negativem Jahresumsatz (überwiegende Gutschriften)."""
        return self.net < ZERO

    @property
    def quantity_is_mixed(self):
        """True, wenn die Menge wegen uneinheitlicher Einheiten nicht addiert wird."""
        return self.quantity is None


@dataclass(frozen=True)
class ItemRevenueReport:
    """Ergebnis der Auswertung: Rangliste plus Summenzeile."""

    company: object
    year: int
    group: object = None
    sort: str = DEFAULT_SORT
    descending: bool = True
    rows: list = field(default_factory=list)
    total_net: Decimal = ZERO
    total_document_count: int = 0

    @property
    def has_data(self):
        """True, wenn im Zeitraum überhaupt Positionen gefunden wurden."""
        return bool(self.rows)


def _unit_label(row):
    """
    Einheit einer Artikelzeile – oder None, wenn sie uneinheitlich ist.

    Positionen ohne Einheit zählen als eigene Ausprägung: „5 Stk" und „5 ohne
    Einheit" sind nicht dieselbe Menge.

    Returns:
        str | None: Symbol bzw. Code der Einheit, '' wenn gar keine Einheit
        gesetzt ist, None bei uneinheitlichen Einheiten.
    """
    variants = row['unit_count'] + (1 if row['lines_without_unit'] else 0)
    if variants > 1:
        return None
    if row['unit_count'] == 0:
        return ''
    return (row['unit_symbol'] or '').strip() or (row['unit_code'] or '')


def _share_percent(net, total):
    """
    Anteil am Gesamtumsatz in Prozent.

    ``None`` bei einem Gesamtumsatz von 0: ein Anteil an nichts ist keine
    Kennzahl, und die Division wäre undefiniert.
    """
    if not total:
        return None
    return (net / total * HUNDRED).quantize(PERCENT)


def build_report(company, year, group=None, sort=DEFAULT_SORT, descending=True):
    """
    Rangliste der Artikel nach Nettoumsatz aufbauen.

    Artikel ohne Umsatz im Zeitraum erscheinen nicht: Die Rangliste beantwortet,
    was verkauft wurde. Eine Liste unverkaufter Artikel ist eine andere Frage.

    Args:
        company: :class:`core.models.Mandant` (oder ``None`` – dann leer)
        year: Kalenderjahr
        group: optionale :class:`core.models.ItemGroup`
        sort: Sortierschlüssel aus :data:`SORT_FIELDS`
        descending: absteigend sortieren

    Returns:
        ItemRevenueReport
    """
    if company is None:
        return ItemRevenueReport(
            company=None, year=year, group=group, sort=sort, descending=descending
        )

    queryset = line_queryset(company, year, group)

    aggregated = (
        queryset
        .values(
            'item',
            'item__article_no',
            'item__short_text_1',
            'item__item_group__name',
        )
        .annotate(
            net=_signed_net(),
            quantity=_signed_quantity(),
            document_count=Count('document', distinct=True),
            # Einheitenprüfung: NULL-Einheiten zählt Count nicht mit, deshalb
            # separat erfassen.
            unit_count=Count('unit', distinct=True),
            lines_without_unit=Count('pk', filter=Q(unit__isnull=True)),
            unit_symbol=Max('unit__symbol'),
            unit_code=Max('unit__code'),
        )
        # Zweites Sortierkriterium für ein stabiles Bild bei Gleichstand.
        .order_by(
            ('-' if descending else '') + SORT_FIELDS.get(sort, SORT_FIELDS[DEFAULT_SORT]),
            'item__article_no',
        )
    )

    # Ein zweites Aggregat statt einer Summe über die Zeilen: die Belegzahl
    # muss über alle Zeilen hinweg entdoppelt werden – ein Beleg mit drei
    # Artikeln ist ein Beleg, nicht drei.
    totals = queryset.aggregate(
        net=_signed_net(),
        document_count=Count('document', distinct=True),
    )
    total_net = totals['net']

    rows = []
    for row in aggregated:
        item_id = row['item']
        unit_label = _unit_label(row)
        rows.append(ItemRevenueRow(
            key=str(item_id) if item_id is not None else NO_ITEM_KEY,
            item_id=item_id,
            article_no=row['item__article_no'] or '',
            label=row['item__short_text_1'] or NO_ITEM_LABEL,
            group_name=row['item__item_group__name'] or '',
            net=row['net'],
            quantity=row['quantity'] if unit_label is not None else None,
            unit_label=unit_label or '',
            document_count=row['document_count'],
            share_percent=_share_percent(row['net'], total_net),
        ))

    return ItemRevenueReport(
        company=company,
        year=year,
        group=group,
        sort=sort,
        descending=descending,
        rows=rows,
        total_net=total_net,
        total_document_count=totals['document_count'],
    )


@dataclass(frozen=True)
class ItemMonthlyRevenue:
    """
    Monatsverlauf eines Artikels im gewählten Jahr.

    Die zwölf Werte summieren sich exakt auf den Jahresumsatz der zugehörigen
    Ranglistenzeile: es sind dieselben Positionen, nur zusätzlich nach Monat
    gruppiert.
    """

    item: object
    year: int
    net_by_month: list = field(default_factory=list)

    @property
    def label(self):
        """Beschriftung des Artikels bzw. der Sammelzeile."""
        if self.item is None:
            return NO_ITEM_LABEL
        return self.item.short_text_1

    @property
    def total_net(self):
        """Jahresumsatz als Summe der Monatswerte."""
        return sum(self.net_by_month, ZERO)

    @property
    def monthly_rows(self):
        """Monatswerte als Zeilen für die Tabellensicht neben dem Diagramm."""
        return [
            {'label': label, 'net': amount}
            for label, amount in zip(MONTH_LABELS, self.net_by_month)
        ]

    @property
    def chart_data(self):
        """
        Diagrammdaten.

        Die Beträge werden als ``float`` übergeben: als ``Decimal`` würden sie
        als Zeichenkette serialisiert, die Chart.js nicht als Zahlenwert
        zeichnen kann.
        """
        return {
            'labels': list(MONTH_LABELS),
            'values': [float(amount) for amount in self.net_by_month],
            'series': f'Nettoumsatz {self.year}',
        }

    @property
    def chart_data_json(self):
        """
        Diagrammdaten als JSON-Zeichenkette für ein ``data``-Attribut.

        Bewusst ein Attribut und kein ``json_script``-Block: Der Monatsverlauf
        wird per HTMX nachgeladen, und ein eingebettetes ``<script>``-Element
        hinge davon ab, wie HTMX Skripte beim Einfügen behandelt. Das Attribut
        wird vom Template-Autoescaping abgesichert; im JavaScript steht kein
        interpolierter Serverwert.
        """
        return json.dumps(self.chart_data)


def monthly_revenue(company, year, item=None):
    """
    Monatsverlauf eines Artikels (oder der Positionen ohne Artikelbezug).

    Monate ohne Umsatz erscheinen als 0 und werden nicht ausgelassen, sonst
    verzerrt die Zeitachse im Diagramm.

    Die Warengruppe ist hier kein Parameter: der Artikel ist bereits eindeutig
    gewählt, ein zusätzlicher Gruppenfilter könnte die Zeile nur widersprüchlich
    leeren.

    Args:
        company: :class:`core.models.Mandant` (oder ``None`` – dann Nullreihe)
        year: Kalenderjahr
        item: :class:`core.models.Item` oder ``None`` für „Ohne Artikelbezug"

    Returns:
        ItemMonthlyRevenue
    """
    series = [ZERO] * 12

    if company is None:
        return ItemMonthlyRevenue(item=item, year=year, net_by_month=series)

    queryset = line_queryset(company, year)
    if item is None:
        queryset = queryset.filter(item__isnull=True)
    else:
        queryset = queryset.filter(item=item)

    rows = (
        queryset
        .annotate(month=TruncMonth('document__issue_date', output_field=DateField()))
        .values('month')
        .annotate(net=_signed_net())
        .order_by()
    )
    for row in rows:
        month = row['month']
        if month is None or month.year != year:
            continue
        series[month.month - 1] = row['net']

    return ItemMonthlyRevenue(item=item, year=year, net_by_month=series)
