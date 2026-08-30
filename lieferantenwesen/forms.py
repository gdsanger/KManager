"""Forms for the Lieferantenwesen module."""
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from core.models import Adresse, Kostenart, Mandant
from .models import InvoiceIn, InvoiceInLine


def kostenart_sub_queryset(main_id):
    """Return the sub cost types of ``main_id`` (empty without a selection).

    ``main_id`` may come straight from POST data, so anything that is not a
    usable primary key yields an empty queryset instead of a database error.
    """
    if not main_id:
        return Kostenart.objects.none()
    try:
        main_pk = int(main_id)
    except (TypeError, ValueError):
        return Kostenart.objects.none()
    return Kostenart.objects.filter(parent_id=main_pk).order_by("name")


class CostTypeDependencyMixin:
    """Couple a sub cost type field to its main cost type field.

    ``core.Kostenart`` is hierarchical: a sub cost type always belongs to
    exactly one main cost type. Both the rendered choices and the server-side
    validation are therefore narrowed down to the children of the selected
    main cost type. On a bound form the selection is taken from ``self.data``
    so that a combination changed within the same request is accepted.
    """

    #: Shown when the submitted sub cost type is not a child of the main one.
    cost_type_mismatch_message = (
        "Die Unterkostenart muss zur gewählten Hauptkostenart gehören."
    )

    def _bind_cost_type_fields(self, main_name, sub_name):
        if self.is_bound:
            main_id = self.data.get(self.add_prefix(main_name))
        else:
            main_id = self.initial.get(main_name) or getattr(
                self.instance, f"{main_name}_id", None
            )

        sub_field = self.fields[sub_name]
        sub_field.queryset = kostenart_sub_queryset(main_id)
        # The narrowed queryset turns a mismatch into "invalid choice"; say why.
        sub_field.error_messages["invalid_choice"] = self.cost_type_mismatch_message

        # Hooks for the cascading dropdown in the browser.
        self.fields[main_name].widget.attrs["data-cost-type-target"] = self[
            sub_name
        ].auto_id
        if not main_id:
            # Without a main cost type there is nothing to choose from.
            sub_field.widget.attrs["disabled"] = "disabled"


class ModelErrorFallbackMixin:
    """Show model errors for fields without a form counterpart.

    ``Model.full_clean()`` does not filter errors raised by ``clean()`` by the
    form's field list, so an error on a field that is not rendered would make
    ``add_error()`` raise ``ValueError`` (HTTP 500) instead of showing the
    problem. Such errors are remapped to non-field errors and stay visible.
    """

    def _update_errors(self, errors):
        if hasattr(errors, "error_dict"):
            remapped = {}
            for field, messages in errors.error_dict.items():
                target = field if field in self.fields else NON_FIELD_ERRORS
                remapped.setdefault(target, []).extend(messages)
            errors = ValidationError(remapped)
        super()._update_errors(errors)


class InvoiceInForm(ModelErrorFallbackMixin, CostTypeDependencyMixin, forms.ModelForm):
    class Meta:
        model = InvoiceIn
        fields = [
            "company",
            "invoice_no",
            "invoice_date",
            "supplier",
            "currency",
            "net_amount",
            "tax_amount",
            "gross_amount",
            "payment_terms_text",
            "due_date",
            "payment_reference",
            "iban_from_invoice",
            "cost_type_main",
            "cost_type_sub",
            "order",
            "status",
            "approval_comment",
            "payment_date",
        ]
        widgets = {
            "company": forms.Select(attrs={"class": "form-select"}),
            "invoice_no": forms.TextInput(attrs={"class": "form-control"}),
            "invoice_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "net_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "tax_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "gross_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "payment_terms_text": forms.TextInput(attrs={"class": "form-control"}),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
            "payment_reference": forms.TextInput(attrs={"class": "form-control"}),
            "iban_from_invoice": forms.TextInput(attrs={"class": "form-control"}),
            "cost_type_main": forms.Select(attrs={"class": "form-select"}),
            "cost_type_sub": forms.Select(attrs={"class": "form-select"}),
            "order": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "approval_comment": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "payment_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # date fields need format set for initial rendering
        self.fields["invoice_date"].input_formats = ["%Y-%m-%d"]
        self.fields["due_date"].input_formats = ["%Y-%m-%d"]
        self.fields["payment_date"].input_formats = ["%Y-%m-%d"]
        # Limit supplier choices to LIEFERANT type
        self.fields["supplier"].queryset = Adresse.objects.filter(adressen_type="LIEFERANT")
        self._bind_cost_type_fields("cost_type_main", "cost_type_sub")
        # Der Mandant entscheidet, in welchem Buchungsstapel der Aufwand
        # landet – deshalb Pflichtfeld, obwohl das Modell (noch) NULL zulässt.
        company_field = self.fields["company"]
        company_field.required = True
        company_field.queryset = Mandant.objects.order_by("name")
        company_field.empty_label = "– bitte wählen –"
        if not self.is_bound and not self.initial.get("company") and not self.instance.company_id:
            # Bei genau einem Mandanten gibt es nichts zu entscheiden.
            only = company_field.queryset.first()
            if only and company_field.queryset.count() == 1:
                company_field.initial = only.pk


class InvoiceInLineForm(ModelErrorFallbackMixin, CostTypeDependencyMixin, forms.ModelForm):
    cost_type_mismatch_message = (
        "Kostenart 2 muss zur gewählten Kostenart 1 der Position gehören."
    )

    class Meta:
        model = InvoiceInLine
        fields = [
            "position_no",
            "description",
            "quantity",
            "unit",
            "unit_price",
            "net_amount",
            "tax_rate",
            "tax_amount",
            "gross_amount",
            "cost_type_main_line",
            "cost_type_sub_line",
        ]
        widgets = {
            "position_no": forms.NumberInput(attrs={"class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.001"}
            ),
            "unit": forms.TextInput(attrs={"class": "form-control"}),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.0001"}
            ),
            "net_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "tax_rate": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "tax_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "gross_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "cost_type_main_line": forms.Select(attrs={"class": "form-select"}),
            "cost_type_sub_line": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bind_cost_type_fields("cost_type_main_line", "cost_type_sub_line")


InvoiceInLineFormSet = forms.inlineformset_factory(
    InvoiceIn,
    InvoiceInLine,
    form=InvoiceInLineForm,
    extra=1,
    can_delete=True,
)


class ApprovalForm(forms.Form):
    """Form for the approval/rejection action."""

    approval_comment = forms.CharField(
        label="Kommentar",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    action = forms.ChoiceField(
        label="Entscheidung",
        choices=[("APPROVED", "Freigeben"), ("REJECTED", "Ablehnen")],
        widget=forms.RadioSelect,
    )
