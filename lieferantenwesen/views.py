"""Views for the Lieferantenwesen module."""
import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ApprovalForm, InvoiceInForm, InvoiceInLineFormSet
from .models import InvoiceIn
from .permissions import geschaeftsleitung_required, lieferantenwesen_required

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Home / Dashboard
# ---------------------------------------------------------------------------

@login_required
@lieferantenwesen_required
def home(request):
    recent_invoices = InvoiceIn.objects.select_related("supplier").order_by(
        "-created_at"
    )[:10]
    in_review_count = InvoiceIn.objects.filter(status="IN_REVIEW").count()
    overdue_count = InvoiceIn.objects.filter(
        due_date__lt=timezone.now().date(),
        status__in=["DRAFT", "EXTRACTED", "IN_REVIEW"],
    ).count()
    return render(
        request,
        "lieferantenwesen/home.html",
        {
            "recent_invoices": recent_invoices,
            "in_review_count": in_review_count,
            "overdue_count": overdue_count,
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
    overdue_only = request.GET.get("overdue", "") == "1"
    today = timezone.now().date()

    qs = InvoiceIn.objects.select_related("supplier", "order").order_by(
        "-invoice_date", "-created_at"
    )
    if q:
        qs = qs.filter(
            Q(invoice_no__icontains=q)
            | Q(supplier__name__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if overdue_only:
        qs = qs.filter(
            due_date__lt=today,
            status__in=["DRAFT", "EXTRACTED", "IN_REVIEW"],
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    from .models import INVOICE_IN_STATUS

    return render(
        request,
        "lieferantenwesen/invoices/list.html",
        {
            "page_obj": page_obj,
            "q": q,
            "status_filter": status_filter,
            "overdue_only": overdue_only,
            "today": today,
            "status_choices": INVOICE_IN_STATUS,
        },
    )


@login_required
@lieferantenwesen_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        InvoiceIn.objects.select_related(
            "supplier", "cost_type_main", "cost_type_sub", "order",
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
        },
    )


@login_required
@lieferantenwesen_required
def invoice_create(request):
    if request.method == "POST":
        form = InvoiceInForm(request.POST)
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
        form = InvoiceInForm(request.POST, instance=invoice)
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
            messages.success(
                request,
                "PDF wurde hochgeladen und analysiert. Bitte prüfen und ergänzen Sie die Daten.",
            )
            return redirect("lieferantenwesen:invoice_edit", pk=invoice.pk)
        except Exception as exc:
            logger.exception("PDF upload failed: %s", exc)
            messages.error(
                request,
                "Fehler beim Verarbeiten der PDF-Datei. Bitte versuchen Sie es erneut.",
            )
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
