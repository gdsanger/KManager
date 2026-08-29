"""
Views des Finanzen-Moduls.

Schwerpunkt ist der DATEV-Buchungsstapel-Export: Zeitraum wählen, Vorschau
mit Anzahl und Summen prüfen, Fehlerliste abarbeiten, Datei herunterladen.
Der Download ist bewusst ein eigener POST-Schritt – erst dabei werden die
Belege als exportiert gekennzeichnet.
"""
import logging
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from finanzen.forms import DatevExportForm
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services.datev_export import (
    DatevExportError,
    build_filename,
    build_preview,
    mark_exported,
    render_extf,
)

logger = logging.getLogger(__name__)


@login_required
def home(request):
    """Einstiegsseite Finanzen mit Kennzahlen zum Exportstand."""
    open_entries = OutgoingInvoiceJournalEntry.objects.filter(export_status='OPEN')
    context = {
        'open_journal_count': open_entries.count(),
        'recent_entries': OutgoingInvoiceJournalEntry.objects.select_related(
            'company'
        ).order_by('-document_date', '-created_at')[:10],
    }
    return render(request, 'finanzen/home.html', context)


def _build(request):
    """
    Formular auswerten und Vorschau erzeugen.

    Returns:
        tuple(form, preview, error): preview/error sind None, solange das
        Formular nicht abgeschickt bzw. nicht gültig ist.
    """
    if not request.GET and request.method != 'POST':
        return DatevExportForm(), None, None

    data = request.POST if request.method == 'POST' else request.GET
    form = DatevExportForm(data)
    if not form.is_valid():
        return form, None, None

    date_from, date_to = form.period()
    try:
        preview = build_preview(
            form.cleaned_data['company'],
            date_from,
            date_to,
            include_exported=form.cleaned_data['include_exported'],
        )
    except DatevExportError as exc:
        return form, None, str(exc)

    return form, preview, None


@login_required
def datev_export(request):
    """
    Vorschau des Buchungsstapels.

    Zeigt Anzahl und Summen der Buchungssätze sowie – vor jedem Download –
    die Fehlerliste der Belege ohne auflösbares Konto.
    """
    form, preview, error = _build(request)
    if error:
        messages.error(request, error)

    return render(request, 'finanzen/datev_export.html', {
        'form': form,
        'preview': preview,
        'period_label': form.period_label() if preview else '',
    })


@login_required
def datev_export_download(request):
    """
    Buchungsstapel erzeugen, herunterladen und die Belege als exportiert
    kennzeichnen.

    Bewusst nur per POST: Der Download verändert den Export-Status und darf
    daher nicht über einen Link auslösbar sein.
    """
    if request.method != 'POST':
        return redirect('finanzen:datev_export')

    form, preview, error = _build(request)
    if error or preview is None:
        messages.error(
            request,
            error or 'Bitte den Zeitraum korrekt auswählen.',
        )
        return render(request, 'finanzen/datev_export.html', {
            'form': form, 'preview': None, 'period_label': '',
        })

    try:
        content = render_extf(preview)
    except DatevExportError as exc:
        messages.error(request, str(exc))
        return render(request, 'finanzen/datev_export.html', {
            'form': form,
            'preview': preview,
            'period_label': form.period_label(),
        })

    if not preview.bookings:
        messages.warning(
            request,
            'Für den gewählten Zeitraum gibt es keine Buchungssätze.',
        )
        return render(request, 'finanzen/datev_export.html', {
            'form': form,
            'preview': preview,
            'period_label': form.period_label(),
        })

    batch_id = f'{timezone.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}'
    mark_exported(preview, batch_id)
    logger.info(
        'DATEV-Buchungsstapel %s erzeugt: %s Buchungssätze, Zeitraum %s bis %s',
        batch_id, len(preview.bookings), preview.date_from, preview.date_to,
    )

    response = HttpResponse(content, content_type='text/csv; charset=windows-1252')
    response['Content-Disposition'] = f'attachment; filename="{build_filename(preview)}"'
    return response
