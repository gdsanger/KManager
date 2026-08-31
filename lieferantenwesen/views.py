"""Views for the Lieferantenwesen module."""
import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from core.models import Adresse
from core.services.ai.invoice_extraction import InvoiceExtractionError
from core.services.base import ServiceNotConfigured
from .forms import ApprovalForm, InvoiceInForm, InvoiceInLineFormSet
from .models import InvoiceIn
from .permissions import geschaeftsleitung_required, lieferantenwesen_required

logger = logging.getLogger(__name__)

#: Maximale Länge des technischen Details in einer Meldung an den Anwender.
#: Die vollständige Meldung steht im AIJobsHistory-Eintrag.
AI_ERROR_DETAIL_MAX_LENGTH = 300


# ---------------------------------------------------------------------------
# Home / Dashboard
# ---------------------------------------------------------------------------

@login_required
@lieferantenwesen_required
def home(request):
    today = timezone.now().date()
    recent_invoices = InvoiceIn.objects.select_related("supplier", "order").order_by(
        "-invoice_date",
        "-created_at",
    )[:10]
    overdue_qs = InvoiceIn.objects.filter(
        due_date__lt=today,
        status__in=["DRAFT", "EXTRACTED", "IN_REVIEW"],
    )
    paid_qs = InvoiceIn.objects.filter(status="PAID")
    in_review_count = InvoiceIn.objects.filter(status="IN_REVIEW").count()
    overdue_count = overdue_qs.count()
    overdue_total_amount = overdue_qs.aggregate(total=Sum("gross_amount"))[
        "total"
    ]
    paid_count = paid_qs.count()
    paid_total_amount = paid_qs.aggregate(total=Sum("gross_amount"))["total"]
    return render(
        request,
        "lieferantenwesen/home.html",
        {
            "recent_invoices": recent_invoices,
            "in_review_count": in_review_count,
            "overdue_count": overdue_count,
            "overdue_total_amount": overdue_total_amount,
            "paid_count": paid_count,
            "paid_total_amount": paid_total_amount,
            "today": today,
        },
    )


# ---------------------------------------------------------------------------
# InvoiceIn (Eingangsrechnung) views
# ---------------------------------------------------------------------------

@login_required
@lieferantenwesen_required
def invoice_list(request):
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    company_filter = request.GET.get("company", "")
    overdue_only = request.GET.get("overdue", "") == "1"
    supplier_filter = request.GET.get("supplier", "")
    # Zahlstatus der Verbindlichkeit – Einstieg von der Lieferantenauswertung
    # aus. Bewusst getrennt vom Schalter „Nur Überfällige", der die noch nicht
    # freigegebenen Rechnungen im Blick behält.
    payment_filter = request.GET.get("payment", "")
    today = timezone.now().date()

    qs = InvoiceIn.objects.select_related("supplier", "order", "company").order_by(
        "-invoice_date", "-created_at"
    )
    if q:
        qs = qs.filter(
            Q(invoice_no__icontains=q)
            | Q(supplier__name__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if company_filter == "NONE":
        # Belege ohne Mandant blockieren den DATEV-Export – sie müssen
        # auffindbar sein, um sie nachpflegen zu können.
        qs = qs.filter(company__isnull=True)
    elif company_filter.isdigit():
        qs = qs.filter(company_id=int(company_filter))
    else:
        company_filter = ""
    if supplier_filter.isdigit():
        qs = qs.filter(supplier_id=int(supplier_filter))
    else:
        supplier_filter = ""
    if payment_filter in ("open", "overdue"):
        # Offene Verbindlichkeit: freigegeben und ohne erfasstes Zahldatum.
        # Rechnungen in Prüfung sind noch nicht zur Zahlung freigegeben.
        qs = qs.filter(status="APPROVED", payment_date__isnull=True)
        if payment_filter == "overdue":
            qs = qs.filter(due_date__lt=today)
    else:
        payment_filter = ""
    if overdue_only:
        qs = qs.filter(
            due_date__lt=today,
            status__in=["DRAFT", "EXTRACTED", "IN_REVIEW"],
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    from core.models import Mandant

    from .models import INVOICE_IN_STATUS

    return render(
        request,
        "lieferantenwesen/invoices/list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "status_filter": status_filter,
            "company_filter": company_filter,
            "overdue_only": overdue_only,
            "supplier_filter": supplier_filter,
            "payment_filter": payment_filter,
            "supplier": (
                Adresse.objects.filter(pk=supplier_filter).first()
                if supplier_filter else None
            ),
            "today": today,
            "status_choices": INVOICE_IN_STATUS,
            "companies": Mandant.objects.order_by("name"),
        },
    )


@login_required
@lieferantenwesen_required
def invoice_detail(request, pk):
    from django.utils import timezone

    invoice = get_object_or_404(
        InvoiceIn.objects.select_related(
            "company", "supplier", "cost_type_main", "cost_type_sub", "order",
            "created_by", "updated_by", "approved_by", "rejected_by",
        ),
        pk=pk,
    )
    lines = invoice.lines.all()
    from .permissions import user_can_approve_invoices

    can_approve = user_can_approve_invoices(request.user)
    approval_form = (
        ApprovalForm() if can_approve and invoice.status == "IN_REVIEW" else None
    )
    return render(
        request,
        "lieferantenwesen/invoices/detail.html",
        {
            "invoice": invoice,
            "lines": lines,
            "can_approve": can_approve,
            "approval_form": approval_form,
            "today": timezone.now().date(),
        },
    )


@login_required
@lieferantenwesen_required
@xframe_options_sameorigin
def invoice_pdf(request, pk):
    """Stream the PDF file of an invoice inline for preview in an iframe."""
    invoice = get_object_or_404(InvoiceIn, pk=pk)

    if not invoice.pdf_file:
        raise Http404("Kein PDF-Dokument für diese Rechnung hinterlegt.")

    if not os.path.exists(invoice.pdf_file.path):
        raise Http404("PDF-Datei wurde nicht gefunden im Filesystem.")

    response = FileResponse(
        invoice.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = (
        f'inline; filename="{os.path.basename(invoice.pdf_file.name)}"'
    )
    return response


@login_required
@lieferantenwesen_required
def invoice_create(request):
    if request.method == "POST":
        form = InvoiceInForm(request.POST, request.FILES)
        formset = InvoiceInLineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            invoice.updated_by = request.user
            invoice.save()
            formset.instance = invoice
            formset.save()
            messages.success(
                request,
                f'Eingangsrechnung "{invoice.invoice_no}" wurde erfolgreich angelegt.',
            )
            return redirect("lieferantenwesen:invoice_detail", pk=invoice.pk)
    else:
        form = InvoiceInForm()
        formset = InvoiceInLineFormSet()
    return render(
        request,
        "lieferantenwesen/invoices/form.html",
        {"form": form, "formset": formset, "title": "Eingangsrechnung anlegen"},
    )


@login_required
@lieferantenwesen_required
def invoice_edit(request, pk):
    invoice = get_object_or_404(InvoiceIn, pk=pk)
    if invoice.status in ("APPROVED", "REJECTED"):
        messages.error(
            request,
            "Freigegebene oder abgelehnte Rechnungen können nicht bearbeitet werden.",
        )
        return redirect("lieferantenwesen:invoice_detail", pk=pk)

    if request.method == "POST":
        form = InvoiceInForm(request.POST, request.FILES, instance=invoice)
        formset = InvoiceInLineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            formset.save()
            messages.success(
                request,
                f'Eingangsrechnung "{invoice.invoice_no}" wurde gespeichert.',
            )
            return redirect("lieferantenwesen:invoice_detail", pk=pk)
    else:
        form = InvoiceInForm(instance=invoice)
        formset = InvoiceInLineFormSet(instance=invoice)
    return render(
        request,
        "lieferantenwesen/invoices/form.html",
        {
            "form": form,
            "formset": formset,
            "invoice": invoice,
            "title": "Eingangsrechnung bearbeiten",
        },
    )


def _ai_job_admin_url(request, ai_job_id):
    """
    Admin-Link auf den KI-Job zum Fehlschlag – oder ``None``.

    Der Eintrag enthält die vollständige technische Fehlermeldung. Er ist nur
    für Staff erreichbar, deshalb bekommen alle anderen keinen toten Link
    angeboten.
    """
    if not ai_job_id or not request.user.is_staff:
        return None
    try:
        return reverse("admin:core_aijobshistory_change", args=[ai_job_id])
    except NoReverseMatch:
        return None


def _ai_failure_message(request, lead, exc, detail=None):
    """
    Meldung zu einem Fehlschlag der Belegerkennung zusammensetzen.

    Aufbau (durch Zeilenumbrüche getrennt, damit die Meldung lesbar bleibt):
    Sachverhalt samt Ursache, das gekürzte technische Detail und – nur für
    Staff – der Link auf den zugehörigen ``AIJobsHistory``-Eintrag.
    """
    parts = [lead]

    if detail is None:
        detail = getattr(exc, "detail", "")
    detail = (detail or "").strip()
    if detail:
        if len(detail) > AI_ERROR_DETAIL_MAX_LENGTH:
            detail = detail[:AI_ERROR_DETAIL_MAX_LENGTH].rstrip() + " …"
        parts.append(format_html("Technische Meldung: {}", detail))

    job_url = _ai_job_admin_url(request, getattr(exc, "ai_job_id", None))
    if job_url:
        parts.append(
            format_html(
                '<a href="{}" target="_blank" rel="noopener">Technische Details</a>',
                job_url,
            )
        )

    return format_html_join(mark_safe("<br>"), "{}", ((part,) for part in parts))


def _warn_about_missing_company(request, invoice):
    """
    Hinweis auf den fehlenden Mandanten – unabhängig davon, ob die
    Belegerkennung funktioniert hat. Ohne Mandant fehlt die Rechnung im
    DATEV-Buchungsstapel.
    """
    if invoice is not None and invoice.company_id is None:
        messages.warning(
            request,
            "Der Rechnung konnte kein Mandant zugeordnet werden. Bitte "
            "wählen Sie den Mandanten aus, bevor Sie die Rechnung "
            "freigeben – sonst fehlt sie im DATEV-Buchungsstapel.",
        )


def _redirect_to_failed_invoice(request, exc):
    """
    Nach einem Fehlschlag der Erkennung auf den trotzdem angelegten Beleg
    führen. Die hochgeladene Datei bleibt so erhalten – der Anwender kann die
    Daten direkt manuell nachtragen.

    Ohne angelegten Beleg (Fehler vor dem Speichern) bleibt es beim
    Upload-Formular.
    """
    invoice = getattr(exc, "invoice", None)
    if invoice is None or invoice.pk is None:
        return render(request, "lieferantenwesen/invoices/pdf_upload.html")
    _warn_about_missing_company(request, invoice)
    return redirect("lieferantenwesen:invoice_edit", pk=invoice.pk)


@login_required
@lieferantenwesen_required
def invoice_upload_pdf(request):
    """Upload a PDF and trigger AI extraction to pre-fill a new InvoiceIn."""
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf_file")
        if not pdf_file:
            messages.error(request, "Bitte wählen Sie eine PDF-Datei aus.")
            return redirect("lieferantenwesen:invoice_upload_pdf")

        from .services import InvoiceInService

        service = InvoiceInService()
        try:
            invoice = service.create_from_pdf(pdf_file, user=request.user)
        except ServiceNotConfigured as exc:
            # Kein technischer Fehler, sondern eine fehlende Einstellung –
            # entsprechend benannt, damit niemand vergeblich neu hochlädt.
            logger.exception("KI-Belegerkennung ist nicht konfiguriert: %s", exc)
            messages.warning(
                request,
                _ai_failure_message(
                    request,
                    "Das PDF wurde gespeichert, aber es ist kein aktives "
                    "KI-Modell konfiguriert – der Beleg konnte deshalb nicht "
                    "analysiert werden. Bitte hinterlegen Sie in der "
                    "Administration unter „KI-Konfiguration“ ein aktives "
                    "Modell. Bis dahin sind die Rechnungsdaten manuell zu "
                    "erfassen; eingetragen ist vorerst das heutige "
                    "Rechnungsdatum.",
                    exc,
                    detail=str(exc),
                ),
            )
            return _redirect_to_failed_invoice(request, exc)
        except InvoiceExtractionError as exc:
            logger.exception("KI-Analyse der Eingangsrechnung fehlgeschlagen: %s", exc)
            messages.warning(
                request,
                _ai_failure_message(
                    request,
                    format_html(
                        "Das PDF wurde gespeichert, die KI-Analyse ist "
                        "jedoch fehlgeschlagen: {} Bitte erfassen Sie die "
                        "Rechnungsdaten manuell; eingetragen ist vorerst "
                        "das heutige Rechnungsdatum.",
                        exc.reason,
                    ),
                    exc,
                ),
            )
            return _redirect_to_failed_invoice(request, exc)
        except Exception as exc:
            # Fehler vor dem Speichern (Datei unlesbar, Storage o. ä.): Der
            # Anwender erfährt die konkrete Ursache – ein Pauschaltext würde
            # ihn nur zu einem aussichtslosen zweiten Versuch einladen.
            logger.exception("PDF upload failed: %s", exc)
            messages.error(
                request,
                format_html(
                    "Die PDF-Datei konnte nicht verarbeitet werden: {}",
                    str(exc) or exc.__class__.__name__,
                ),
            )
        else:
            messages.success(
                request,
                "PDF wurde hochgeladen und analysiert. Bitte prüfen und ergänzen Sie die Daten.",
            )
            if getattr(invoice, "invoice_date_fallback", False):
                messages.warning(
                    request,
                    "Das Rechnungsdatum konnte nicht aus dem Beleg erkannt "
                    "werden. Eingetragen ist das heutige Datum – bitte prüfen "
                    "und korrigieren Sie es, denn das Rechnungsdatum "
                    "entscheidet über den DATEV-Buchungsstapel.",
                )
            skipped_lines = getattr(invoice, "skipped_line_count", 0) or 0
            if skipped_lines:
                messages.warning(
                    request,
                    f"{skipped_lines} Position(en) konnten nicht aus dem Beleg "
                    "übernommen werden, weil der Nettobetrag fehlte oder "
                    "unlesbar war. Bitte ergänzen Sie die fehlenden Positionen "
                    "im Bearbeitungsformular.",
                )
            lines_total = getattr(invoice, "lines_gross_mismatch", None)
            if lines_total is not None:
                messages.warning(
                    request,
                    f"Die Summe der Positionen ({lines_total} "
                    f"{invoice.currency}) weicht vom Bruttobetrag der Rechnung "
                    f"({invoice.gross_amount} {invoice.currency}) ab. Bitte "
                    "prüfen Sie die Positionen, bevor Sie die Rechnung "
                    "freigeben.",
                )
            _warn_about_missing_company(request, invoice)
            return redirect("lieferantenwesen:invoice_edit", pk=invoice.pk)
    return render(request, "lieferantenwesen/invoices/pdf_upload.html")


@login_required
@lieferantenwesen_required
@require_POST
def invoice_approve(request, pk):
    """Approve or reject an invoice (Geschäftsleitung only)."""
    from .permissions import user_can_approve_invoices

    if not user_can_approve_invoices(request.user):
        messages.error(
            request,
            "Sie haben keine Berechtigung, Rechnungen freizugeben oder abzulehnen.",
        )
        return redirect("lieferantenwesen:invoice_detail", pk=pk)

    invoice = get_object_or_404(InvoiceIn, pk=pk)
    if invoice.status != "IN_REVIEW":
        messages.error(
            request,
            "Nur Rechnungen im Status 'In Prüfung' können freigegeben werden.",
        )
        return redirect("lieferantenwesen:invoice_detail", pk=pk)

    form = ApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Ungültige Eingabe. Bitte versuchen Sie es erneut.")
        return redirect("lieferantenwesen:invoice_detail", pk=pk)

    action = form.cleaned_data["action"]
    comment = form.cleaned_data.get("approval_comment", "")
    now = timezone.now()

    invoice.approval_comment = comment
    invoice.updated_by = request.user

    if action == "APPROVED":
        invoice.status = "APPROVED"
        invoice.approved_at = now
        invoice.approved_by = request.user
        messages.success(request, f'Rechnung "{invoice.invoice_no}" wurde freigegeben.')
    else:
        invoice.status = "REJECTED"
        invoice.rejected_at = now
        invoice.rejected_by = request.user
        messages.warning(request, f'Rechnung "{invoice.invoice_no}" wurde abgelehnt.')

    invoice.save()
    return redirect("lieferantenwesen:invoice_detail", pk=pk)


@login_required
@lieferantenwesen_required
@require_POST
def invoice_mark_as_paid(request, pk):
    """Mark an invoice as paid (only for APPROVED invoices)."""
    from django.utils import timezone

    invoice = get_object_or_404(InvoiceIn, pk=pk)

    # Only approved invoices can be marked as paid
    if invoice.status != "APPROVED":
        messages.error(
            request,
            "Nur freigegebene Rechnungen können als bezahlt markiert werden.",
        )
        return redirect("lieferantenwesen:invoice_detail", pk=pk)

    # Get payment_date from POST or use today
    payment_date_str = request.POST.get("payment_date", "")
    if payment_date_str:
        from datetime import datetime
        try:
            payment_date = datetime.strptime(payment_date_str, "%Y-%m-%d").date()
        except ValueError:
            payment_date = timezone.now().date()
    else:
        payment_date = timezone.now().date()

    # Use the model method to mark as paid
    invoice.mark_as_paid(payment_date=payment_date)
    invoice.updated_by = request.user
    invoice.save()

    messages.success(
        request,
        f'Rechnung "{invoice.invoice_no}" wurde als bezahlt markiert.',
    )
    return redirect("lieferantenwesen:invoice_detail", pk=pk)


@login_required
@lieferantenwesen_required
@require_POST
def invoice_delete(request, pk):
    """Hard-delete an invoice including its PDF file and line items."""
    invoice = get_object_or_404(InvoiceIn, pk=pk)
    invoice_no = invoice.invoice_no

    # Delete PDF file if it exists
    if invoice.pdf_file:
        try:
            invoice.pdf_file.delete(save=False)
            logger.info(f"Deleted PDF file for invoice {invoice_no} (pk={pk})")
        except Exception as exc:
            logger.exception(f"Failed to delete PDF file for invoice {invoice_no} (pk={pk}): {exc}")
            messages.error(
                request,
                "Fehler beim Löschen der PDF-Datei. Die Rechnung wurde nicht gelöscht.",
            )
            return redirect("lieferantenwesen:invoice_detail", pk=pk)

    # Delete invoice (will cascade to lines)
    try:
        invoice.delete()
        logger.info(f"Deleted invoice {invoice_no} (pk={pk})")
        messages.success(request, f'Eingangsrechnung "{invoice_no}" wurde gelöscht.')
    except Exception as exc:
        logger.exception(f"Failed to delete invoice {invoice_no} (pk={pk}): {exc}")
        messages.error(request, "Fehler beim Löschen der Rechnung.")
        return redirect("lieferantenwesen:invoice_detail", pk=pk)

    return redirect("lieferantenwesen:invoice_list")
