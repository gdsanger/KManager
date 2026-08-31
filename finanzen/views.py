"""
Views des Finanzen-Moduls.

Das Modul ist das Finanzplanungs- und Auswertungscockpit. Die
Buchhaltungsfunktionen – Rechnungsausgangsjournal und DATEV-Buchungsstapel-
Export – liegen in der Auftragsverwaltung unter „Buchhaltung". Die fachliche
Exportlogik (`finanzen.forms`, `finanzen.services.datev_export`) bleibt hier
als Domänenschicht und wird von der dortigen View sowie vom Management-Command
genutzt.
"""
import logging
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core.models import Item

from .forms import DashboardFilterForm, ItemRevenueFilterForm
from .services.dashboard import build_dashboard
from .services.item_revenue import (
    NO_ITEM_KEY,
    SORT_FIELDS,
    build_report,
    monthly_revenue,
    resolve_sort,
)

logger = logging.getLogger(__name__)


@login_required
def home(request):
    """
    Finanzen-Dashboard: Kennzahlen, Jahresverlauf und offene Posten.

    Die Filter stehen als GET-Parameter in der URL, damit ein Stand teilbar und
    über einen Link wiederherstellbar ist. Die Auswertung selbst liegt in
    `finanzen.services.dashboard` und ist dort ohne HTTP-Schicht testbar.
    """
    form = DashboardFilterForm(request.GET or None)
    selection = form.selection()
    dashboard = build_dashboard(
        company=selection['company'],
        year=selection['year'],
        value_basis=selection['value_basis'],
        date_basis=selection['date_basis'],
    )

    # Chart.js braucht Zahlen: der DjangoJSONEncoder hinter `json_script` würde
    # Decimal als Zeichenkette ausgeben, und die Wertachse bliebe leer.
    chart_data = {
        'labels': dashboard.month_labels,
        'income': [float(value) for value in dashboard.income_by_month],
        'expenses': [float(value) for value in dashboard.expense_by_month],
    }

    return render(request, 'finanzen/home.html', {
        'form': form,
        'dashboard': dashboard,
        'chart_data': chart_data,
    })


def _filter_params(selection):
    """
    Filterstand als URL-Parameter – Grundlage für Sortierlinks und Nachladen.

    Args:
        selection: Ergebnis von :meth:`ItemRevenueFilterForm.selection`

    Returns:
        dict: nur gesetzte Parameter, damit die URL nicht mit Leerwerten zuwächst
    """
    params = {'year': selection['year']}
    if selection['company']:
        params['company'] = selection['company'].pk
    if selection['group']:
        params['group'] = selection['group'].pk
    return params


def _sort_links(params, sort, descending):
    """
    Sortierlinks der Tabellenköpfe aufbauen.

    Ein Klick auf die aktive Spalte dreht die Richtung um; jede andere Spalte
    beginnt absteigend – bei Umsatz, Menge und Belegzahl interessiert zuerst
    der größte Wert.

    Returns:
        dict: je Spaltenschlüssel `url`, `is_active` und `descending`
    """
    links = {}
    for key in SORT_FIELDS:
        is_active = key == sort
        next_descending = (not descending) if is_active else True
        query = dict(params, sort=key, dir='desc' if next_descending else 'asc')
        links[key] = {
            'url': f'?{urlencode(query)}',
            'is_active': is_active,
            'descending': descending if is_active else None,
        }
    return links


@login_required
def item_revenue(request):
    """
    Auswertung „Artikelumsatz": Rangliste aller Artikel nach Nettoumsatz.

    Die Filter stehen als GET-Parameter in der URL, damit ein Stand teilbar ist.
    Die Auswertung selbst liegt in `finanzen.services.item_revenue` und ist dort
    ohne HTTP-Schicht testbar. Der Monatsverlauf wird bewusst nicht hier
    berechnet, sondern erst beim Aufklappen einer Zeile nachgeladen
    (:func:`item_revenue_months`).
    """
    form = ItemRevenueFilterForm(request.GET or None)
    selection = form.selection()
    sort, descending = resolve_sort(request.GET.get('sort'), request.GET.get('dir'))

    report = build_report(
        company=selection['company'],
        year=selection['year'],
        group=selection['group'],
        sort=sort,
        descending=descending,
    )

    params = _filter_params(selection)
    return render(request, 'finanzen/artikelumsatz.html', {
        'form': form,
        'report': report,
        'sort_links': _sort_links(params, sort, descending),
        # Nur Mandant und Jahr: der Monatsverlauf gilt einem einzelnen Artikel,
        # die Warengruppe kann ihn nicht weiter einschränken.
        'detail_query': urlencode(
            {k: v for k, v in params.items() if k != 'group'}
        ),
        'no_item_key': NO_ITEM_KEY,
    })


@login_required
def item_revenue_months(request, item_key):
    """
    Monatsverlauf eines Artikels – wird beim Aufklappen einer Ranglistenzeile
    per HTMX nachgeladen.

    Eigener Endpunkt, damit die Rangliste nicht für jeden Artikel im Voraus
    zwölf Werte berechnet.

    Args:
        item_key: Artikel-PK oder :data:`NO_ITEM_KEY` für die Sammelzeile
            „Ohne Artikelbezug"
    """
    form = ItemRevenueFilterForm(request.GET or None)
    selection = form.selection()

    if item_key == NO_ITEM_KEY:
        item = None
    elif item_key.isdigit():
        item = get_object_or_404(Item, pk=item_key)
    else:
        raise Http404('Unbekannter Artikelschlüssel.')

    series = monthly_revenue(
        company=selection['company'], year=selection['year'], item=item
    )

    return render(request, 'finanzen/partials/artikelumsatz_monate.html', {
        'series': series,
        'item_key': item_key,
    })
