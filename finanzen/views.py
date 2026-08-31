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

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .forms import DashboardFilterForm
from .services.dashboard import build_dashboard

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
