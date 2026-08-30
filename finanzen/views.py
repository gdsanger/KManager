"""
Views des Finanzen-Moduls.

Das Modul wird zum Finanzplanungs- und Auswertungscockpit ausgebaut. Die
Buchhaltungsfunktionen – Rechnungsausgangsjournal und DATEV-Buchungsstapel-
Export – liegen in der Auftragsverwaltung unter „Buchhaltung". Die fachliche
Exportlogik (`finanzen.forms`, `finanzen.services.datev_export`) bleibt hier
als Domänenschicht und wird von der dortigen View sowie vom Management-Command
genutzt.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

logger = logging.getLogger(__name__)


@login_required
def home(request):
    """Einstiegsseite Finanzen – Platzhalter für das künftige Cockpit."""
    return render(request, 'finanzen/home.html')
