from django import forms
from django.forms import inlineformset_factory
from .models import Contract, ContractLine


class ContractForm(forms.ModelForm):
    """Form for creating and editing contracts"""
    
    class Meta:
        model = Contract
        fields = [
            'company',
            'name',
            'customer',
            'document_type',
            'payment_term',
            'currency',
            'interval',
            'start_date',
            'end_date',
            'next_run_date',
            'is_active',
            'reference',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'next_run_date': forms.DateInput(attrs={'type': 'date'}),
            'reference': forms.TextInput(attrs={'placeholder': 'Externe Referenz (optional)'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        next_run_date = cleaned_data.get('next_run_date')
        
        # Validate end_date >= start_date
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'Das Enddatum muss nach oder am Startdatum liegen.')
        
        # Validate next_run_date >= start_date
        if start_date and next_run_date and next_run_date < start_date:
            self.add_error('next_run_date', 'Das nächste Ausführungsdatum muss nach oder am Startdatum liegen.')
        
        return cleaned_data


class ContractLineForm(forms.ModelForm):
    """Form for creating and editing contract lines"""
    
    class Meta:
        model = ContractLine
        fields = [
            'item',
            'description',
            'quantity',
            'unit_price_net',
            'tax_rate',
            'cost_type_1',
            'cost_type_2',
            'is_discountable',
            'position_no',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'quantity': forms.NumberInput(attrs={'step': '0.0001'}),
            'unit_price_net': forms.NumberInput(attrs={'step': '0.01'}),
        }


# ContractLine FormSet for inline editing
ContractLineFormSet = inlineformset_factory(
    Contract,
    ContractLine,
    form=ContractLineForm,
    extra=0,
    can_delete=True,
)
