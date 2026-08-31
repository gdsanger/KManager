"""
Umsatz- und Einkaufsauswertung je Geschäftspartner.

Die Auswertung beantwortet auf der Kunden- bzw. Lieferantenseite die Fragen
„wie viel Volumen macht dieser Partner, wie entwickelt es sich, wie viel ist
offen und wie zuverlässig wird gezahlt". Sie liegt bewusst hier und nicht in
der View: so ist sie ohne HTTP-Schicht testbar, und beide Seiten teilen sich
dieselbe Struktur.

Fachliche Festlegungen:

- **Kundenseite:** Grundlage ist das Rechnungsausgangsjournal
  (:class:`finanzen.models.OutgoingInvoiceJournalEntry`), nicht
  ``SalesDocument``. Damit fließen Entwürfe nicht ein, und die Zahlen stimmen
  mit dem DATEV-Buchungsstapel überein. Die Zuordnung läuft über den
  ``document``-Fremdschlüssel (``document__customer``) und **nicht** über die
  Snapshot-Felder ``customer_name``/``debtor_number`` – eine spätere
  Namensänderung am Kunden darf die Auswertung nicht zerreißen. Gutschriften
  stehen im Journal mit negativem Vorzeichen und mindern das Volumen deshalb
  ohne Sonderbehandlung.
- **Lieferantenseite:** Eingangsrechnungen
  (:class:`lieferantenwesen.models.InvoiceIn`) über den direkten
  Fremdschlüssel ``supplier``, eingeschränkt auf
  :data:`lieferantenwesen.models.EXPORTABLE_STATUSES` (freigegeben und
  bezahlt) – dieselbe Menge, die auch der DATEV-Export berücksichtigt.
- **Volumen netto, offene Posten brutto.** Netto ist die Ertragsgröße und
  zwischen Partnern vergleichbar; offen ist dagegen genau der Bruttobetrag, den
  der Kunde schuldet bzw. den man dem Lieferanten schuldet. Die Anzeige
  beschriftet beide Blöcke entsprechend.
- **Über alle Mandanten.** Das ist eine Partnersicht, keine Ergebnisrechnung –
  die Frage „wie viel macht dieser Kunde bei uns" endet nicht an der
  Mandantengrenze. (Anders als
  :mod:`finanzen.services.dashboard`, das je Mandant auswertet.)

Die Monats- und Summenbildung erfolgt in der Datenbank (Gruppierung über den
Monat plus Aggregat), nicht durch Schleifen über einzelne Datensätze – die
Detailseite darf durch den Tab nicht spürbar langsamer werden.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import (
    Avg,
    Count,
    DateField,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone

from auftragsverwaltung.models import SalesDocument
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services.dashboard import (
    AMOUNT_FIELD,
    JOURNAL_RELEVANT_DOCUMENTS,
    MONTH_LABELS,
    ZERO,
    days_overdue,
)
from lieferantenwesen.models import EXPORTABLE_STATUSES, InvoiceIn


# Länge der rollierenden Zeitreihe: zwölf Monate ab dem aktuellen Monat
# rückwärts – bewusst nicht das Kalenderjahr, sonst zeigt die Seite im Januar
# fast nichts.
MONTH_WINDOW = 12

# Zeitraum, aus dem die durchschnittliche Zahlungsdauer gebildet wird. Zwei
# Jahre glätten Ausreißer, ohne längst überholtes Zahlverhalten fortzuschreiben.
PAYMENT_HISTORY_MONTHS = 24

# Höchstzahl der gezeigten offenen Posten. Anzahl und Summe im Kartenkopf
# gelten trotzdem für alle offenen Posten, nicht nur für den Auszug.
OPEN_ITEM_LIMIT = 10

# Partnerarten der Auswertung – steuern nur die Beschriftung, nicht die Logik.
KIND_CUSTOMER = 'CUSTOMER'
KIND_SUPPLIER = 'SUPPLIER'

# Beschriftungen je Partnerart. Sie gehören zur Auswertung und nicht ins
# Template: das Markup des Tabs existiert nur einmal und wird von Kunden- und
# Lieferantenseite gemeinsam benutzt.
LABELS = {
    KIND_CUSTOMER: {
        'total': 'Gesamtumsatz (netto)',
        'last_12_months': 'Umsatz letzte 12 Monate (netto)',
        'open': 'Offener Betrag (brutto)',
        'payment_days': 'Zahlt durchschnittlich in',
        'chart_title': 'Umsatz der letzten 12 Monate',
        'chart_series': 'Umsatz (netto)',
        'open_items': 'Offene Posten dieses Kunden',
        'empty_open_items': 'Keine offenen Posten für diesen Kunden.',
        'source': 'Rechnungsausgangsjournal, alle Mandanten',
    },
    KIND_SUPPLIER: {
        'total': 'Einkaufsvolumen gesamt (netto)',
        'last_12_months': 'Einkaufsvolumen letzte 12 Monate (netto)',
        'open': 'Offene Verbindlichkeiten (brutto)',
        'payment_days': 'Wir zahlen durchschnittlich in',
        'chart_title': 'Einkaufsvolumen der letzten 12 Monate',
        'chart_series': 'Einkauf (netto)',
        'open_items': 'Offene Posten bei diesem Lieferanten',
        'empty_open_items': 'Keine offenen Posten bei diesem Lieferanten.',
        'source': 'Freigegebene und bezahlte Eingangsrechnungen, alle Mandanten',
    },
}


def month_window(today, months=MONTH_WINDOW):
    """
    Monatsanfänge der rollierenden Zeitreihe, ältester Monat zuerst.

    Args:
        today: Stichtag; sein Monat ist der letzte Punkt der Reihe.
        months: Länge der Reihe in Monaten.

    Returns:
        list[datetime.date]: je Monat der erste Tag
    """
    # Über einen fortlaufenden Monatsindex rechnen, damit der Jahreswechsel
    # ohne Sonderfall funktioniert.
    current = today.year * 12 + (today.month - 1)
    window = []
    for offset in range(months - 1, -1, -1):
        index = current - offset
        window.append(date(index // 12, index % 12 + 1, 1))
    return window


def month_label(month):
    """Monatskürzel mit zweistelligem Jahr, z. B. „Sep 26"."""
    return f'{MONTH_LABELS[month.month - 1]} {month.year % 100:02d}'


def _monthly_series(queryset, date_field, amount_expression, months):
    """
    Monatssummen eines Querysets auf das Zeitfenster abbilden.

    Monate ohne Bewegung erscheinen als 0 und werden nicht ausgelassen; sonst
    verzerrt die Zeitachse im Diagramm.

    Args:
        queryset: bereits auf Partner und Zeitfenster eingeschränkte Grundmenge
        date_field: Feldpfad, über den gruppiert wird
        amount_expression: Aggregat (``Sum(...)``) für den Monatswert
        months: Monatsanfänge aus :func:`month_window`

    Returns:
        list[Decimal]: eine Summe je Monat des Fensters
    """
    rows = (
        queryset
        .annotate(month=TruncMonth(date_field, output_field=DateField()))
        .values('month')
        .annotate(total=amount_expression)
        .order_by()
    )

    totals = {}
    for row in rows:
        month = row['month']
        if month is not None:
            totals[(month.year, month.month)] = row['total'] or ZERO

    return [totals.get((month.year, month.month), ZERO) for month in months]


def _sum(queryset, expression):
    """Summe eines Aggregats, 0 statt None bei leerer Grundmenge."""
    return queryset.aggregate(
        total=Coalesce(expression, Value(ZERO), output_field=AMOUNT_FIELD)
    )['total']


def _average_days(queryset, later_field, earlier_field):
    """
    Mittlere Anzahl Tage zwischen zwei Datumsfeldern, in der Datenbank gebildet.

    Returns:
        int | None: gerundete Tage, ``None`` wenn die Grundmenge leer ist. Die
        Unterscheidung ist fachlich wichtig: eine 0 würde eine sofortige
        Zahlung behaupten, wo schlicht nichts bekannt ist.
    """
    average = queryset.aggregate(
        average=Avg(
            ExpressionWrapper(
                later_field - earlier_field, output_field=DurationField()
            )
        )
    )['average']
    if average is None:
        return None
    return round(average.total_seconds() / 86400)


def _payment_history_start(today):
    """Erster Tag des Zeitraums, aus dem die Zahlungsdauer gebildet wird."""
    return month_window(today, PAYMENT_HISTORY_MONTHS)[0]


def _customer_net_expression():
    """Nettoaggregat der Kundenseite – im Journal je Steuersatz gespeichert."""
    return Sum(F('net_0') + F('net_7') + F('net_19'), output_field=AMOUNT_FIELD)


def _supplier_net_expression():
    """
    Nettoaggregat der Lieferantenseite.

    Der Nettobetrag der Eingangsrechnung ist nullable – ein fehlender Wert
    zählt als 0, statt die Summe zu verwerfen.
    """
    return Sum(
        Coalesce(F('net_amount'), Value(ZERO), output_field=AMOUNT_FIELD),
        output_field=AMOUNT_FIELD,
    )


@dataclass(frozen=True)
class PartnerStats:
    """
    Auswertungsergebnis für einen Geschäftspartner.

    Die Kennzahl „letzte 12 Monate" wird aus der Monatsreihe summiert – so
    entspricht sie cent-genau der Summe der zwölf Diagrammbalken.
    """

    partner: object
    kind: str
    total_net: Decimal = ZERO
    net_by_month: list = field(default_factory=list)
    months: list = field(default_factory=list)
    open_total_gross: Decimal = ZERO
    open_count: int = 0
    open_overdue_count: int = 0
    # None (und nicht 0), solange kein einziger bezahlter Beleg vorliegt.
    average_payment_days: int | None = None
    open_items: list = field(default_factory=list)
    truncated: bool = False
    today: date | None = None

    @property
    def labels(self):
        """Beschriftungen der Partnerart (Kunde oder Lieferant)."""
        return LABELS[self.kind]

    @property
    def is_customer(self):
        """True auf der Kundenseite – steuert Links und Spaltentitel."""
        return self.kind == KIND_CUSTOMER

    @property
    def last_12_months_net(self):
        """Volumen der rollierenden zwölf Monate (Summe der Monatsreihe)."""
        return sum(self.net_by_month, ZERO)

    @property
    def month_labels(self):
        """Monatskürzel der Zeitreihe für die Achsenbeschriftung."""
        return [month_label(month) for month in self.months]

    @property
    def monthly_rows(self):
        """Monatswerte als Zeilen für die Tabellensicht neben dem Diagramm."""
        return [
            {'label': label, 'net': amount}
            for label, amount in zip(self.month_labels, self.net_by_month)
        ]

    @property
    def has_movement(self):
        """True, wenn überhaupt Beträge oder offene Posten vorliegen."""
        return bool(self.total_net or self.open_count)

    @property
    def chart_data(self):
        """
        Diagrammdaten für ``json_script``.

        Die Beträge werden als ``float`` übergeben: ``DjangoJSONEncoder``
        serialisiert ``Decimal`` als String, den Chart.js nicht als Zahlenwert
        zeichnen könnte.
        """
        return {
            'labels': self.month_labels,
            'values': [float(amount) for amount in self.net_by_month],
            'series': self.labels['chart_series'],
        }


def _empty_stats(partner, kind, today):
    """Leerzustand: Nullwerte über das volle Zeitfenster, keine offenen Posten."""
    months = month_window(today)
    return PartnerStats(
        partner=partner,
        kind=kind,
        net_by_month=[ZERO] * len(months),
        months=months,
        today=today,
    )


def customer_stats(adresse, today=None, limit=OPEN_ITEM_LIMIT):
    """
    Umsatzauswertung eines Kunden über alle Mandanten.

    Args:
        adresse: :class:`core.models.Adresse` des Kunden (oder ``None``)
        today: Stichtag; ohne Angabe der heutige Tag
        limit: Höchstzahl der aufgelisteten offenen Posten

    Returns:
        PartnerStats
    """
    today = today or timezone.localdate()
    months = month_window(today)

    if adresse is None or adresse.pk is None:
        return _empty_stats(adresse, KIND_CUSTOMER, today)

    # Zuordnung über den Belegbezug, nicht über die Namens-Snapshots.
    journal = OutgoingInvoiceJournalEntry.objects.filter(document__customer=adresse)

    total_net = _sum(journal, _customer_net_expression())
    net_by_month = _monthly_series(
        journal.filter(document_date__gte=months[0]),
        'document_date',
        _customer_net_expression(),
        months,
    )

    open_items, open_totals, truncated = _open_receivables(adresse, today, limit)

    # `paid_at` ist ein DateTimeField; `TruncDate` reduziert es in der aktiven
    # Zeitzone auf den Tag, damit die Differenz volle Tage ergibt.
    paid = SalesDocument.objects.filter(
        JOURNAL_RELEVANT_DOCUMENTS,
        customer=adresse,
        paid_at__isnull=False,
        issue_date__isnull=False,
        paid_at__date__gte=_payment_history_start(today),
    )
    average_payment_days = _average_days(
        paid, TruncDate('paid_at'), F('issue_date')
    )

    return PartnerStats(
        partner=adresse,
        kind=KIND_CUSTOMER,
        total_net=total_net,
        net_by_month=net_by_month,
        months=months,
        open_total_gross=open_totals['total'],
        open_count=open_totals['count'],
        open_overdue_count=open_totals['overdue_count'],
        average_payment_days=average_payment_days,
        open_items=open_items,
        truncated=truncated,
        today=today,
    )


def _open_receivables(adresse, today, limit):
    """
    Offene Posten eines Kunden: journalrelevante Belege ohne Zahlungseingang.

    Die Bedingung „offen" kommt aus :meth:`SalesDocument.unpaid_filter`, damit
    Belegliste, Dashboard und Partnerauswertung dieselbe Definition verwenden –
    Entwürfe und stornierte Belege sind kein offener Posten.
    """
    queryset = SalesDocument.objects.filter(
        SalesDocument.unpaid_filter(),
        JOURNAL_RELEVANT_DOCUMENTS,
        customer=adresse,
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
        .select_related('document_type', 'company')
        # Älteste Fälligkeit zuerst; Belege ohne Fälligkeit hängen hinten an.
        .order_by(F('due_date').asc(nulls_last=True), 'issue_date', 'number')[:limit]
    )
    for entry in entries:
        entry.days_overdue = days_overdue(entry.due_date, today)

    return entries, totals, totals['count'] > len(entries)


def supplier_stats(adresse, today=None, limit=OPEN_ITEM_LIMIT):
    """
    Einkaufsauswertung eines Lieferanten über alle Mandanten.

    Args:
        adresse: :class:`core.models.Adresse` des Lieferanten (oder ``None``)
        today: Stichtag; ohne Angabe der heutige Tag
        limit: Höchstzahl der aufgelisteten offenen Posten

    Returns:
        PartnerStats
    """
    today = today or timezone.localdate()
    months = month_window(today)

    if adresse is None or adresse.pk is None:
        return _empty_stats(adresse, KIND_SUPPLIER, today)

    invoices = InvoiceIn.objects.filter(
        supplier=adresse, status__in=EXPORTABLE_STATUSES
    )

    total_net = _sum(invoices, _supplier_net_expression())
    net_by_month = _monthly_series(
        invoices.filter(invoice_date__gte=months[0]),
        'invoice_date',
        _supplier_net_expression(),
        months,
    )

    open_items, open_totals, truncated = _open_payables(adresse, today, limit)

    paid = invoices.filter(
        payment_date__isnull=False,
        payment_date__gte=_payment_history_start(today),
    )
    average_payment_days = _average_days(
        paid, F('payment_date'), F('invoice_date')
    )

    return PartnerStats(
        partner=adresse,
        kind=KIND_SUPPLIER,
        total_net=total_net,
        net_by_month=net_by_month,
        months=months,
        open_total_gross=open_totals['total'],
        open_count=open_totals['count'],
        open_overdue_count=open_totals['overdue_count'],
        average_payment_days=average_payment_days,
        open_items=open_items,
        truncated=truncated,
        today=today,
    )


def _open_payables(adresse, today, limit):
    """
    Offene Posten bei einem Lieferanten: freigegebene Rechnungen ohne Zahldatum.

    Rechnungen in Prüfung sind noch nicht zur Zahlung freigegeben und damit
    keine Verbindlichkeit, die man beziffern könnte.
    """
    queryset = InvoiceIn.objects.filter(
        supplier=adresse, status='APPROVED', payment_date__isnull=True
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
        .select_related('company')
        .order_by(F('due_date').asc(nulls_last=True), 'invoice_date', 'invoice_no')[:limit]
    )
    for entry in entries:
        entry.days_overdue = days_overdue(entry.due_date, today)

    return entries, totals, totals['count'] > len(entries)
