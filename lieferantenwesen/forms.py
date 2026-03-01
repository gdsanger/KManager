"""Forms for the Lieferantenwesen module."""
from django import forms

from core.models import Adresse
from .models import InvoiceIn, InvoiceInLine


class InvoiceInForm(forms.ModelForm):
    class Meta:
        model = InvoiceIn
        fields = [
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
        ]
        widgets = {
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # date fields need format set for initial rendering
        self.fields["invoice_date"].input_formats = ["%Y-%m-%d"]
        self.fields["due_date"].input_formats = ["%Y-%m-%d"]
        # Limit supplier choices to LIEFERANT type
        self.fields["supplier"].queryset = Adresse.objects.filter(adressen_type="LIEFERANT")


class InvoiceInLineForm(forms.ModelForm):
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
        }


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
