"""
Forms for core mailing functionality and user profile management
"""
import os
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from core.models import SmtpSettings, MailTemplate, Mandant, Item, ItemGroup, TaxRate, Kostenart, Unit


class SmtpSettingsForm(forms.ModelForm):
    """Form for SMTP settings"""
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Lassen Sie dieses Feld leer, wenn Sie das Passwort nicht ändern möchten.'
    )
    
    class Meta:
        model = SmtpSettings
        fields = ['host', 'port', 'use_tls', 'username', 'password']
        widgets = {
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'host': 'SMTP Host *',
            'port': 'SMTP Port *',
            'use_tls': 'STARTTLS verwenden',
            'username': 'Benutzername',
            'password': 'Passwort',
        }
        help_texts = {
            'use_tls': 'Aktivieren Sie diese Option für STARTTLS (Port 587)',
            'username': 'Leer lassen für Versand ohne Authentifizierung',
        }


class MailTemplateForm(forms.ModelForm):
    """Form for mail templates with TinyMCE editor"""
    
    class Meta:
        model = MailTemplate
        fields = ['key', 'subject', 'message', 'from_address', 'from_name', 'cc_address', 'is_active']
        widgets = {
            'key': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={
                'class': 'form-control tinymce-editor',
                'rows': 15,
            }),
            'from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'cc_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'key': 'Template Key *',
            'subject': 'Betreff *',
            'message': 'Nachricht *',
            'from_address': 'Von E-Mail',
            'from_name': 'Von Name',
            'cc_address': 'CC-Adresse',
            'is_active': 'Aktiv',
        }
        help_texts = {
            'key': 'Eindeutiger technischer Name (z.B. "issue-created-confirmation")',
            'subject': 'Sie können Django Template-Variablen verwenden: {{ variable }}',
            'message': 'Sie können Django Template-Variablen verwenden: {{ variable }}',
            'cc_address': 'Optional: Diese Adresse erhält automatisch eine Kopie jeder E-Mail',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values for new templates (not when editing existing ones)
        if not self.instance.pk:
            self.fields['from_address'].initial = settings.DEFAULT_FROM_EMAIL
            self.fields['from_name'].initial = settings.DEFAULT_FROM_NAME


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information"""
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'Benutzername *',
            'first_name': 'Vorname',
            'last_name': 'Nachname',
            'email': 'E-Mail',
        }
        help_texts = {
            'username': 'Erforderlich. 150 Zeichen oder weniger. Buchstaben, Ziffern und @/./+/-/_ nur.',
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with Bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})
        
        self.fields['old_password'].label = 'Aktuelles Passwort'
        self.fields['new_password1'].label = 'Neues Passwort'
        self.fields['new_password2'].label = 'Neues Passwort bestätigen'


class MandantForm(forms.ModelForm):
    """Form for Mandant entity"""
    
    logo = forms.FileField(
        required=False,
        label='Logo',
        help_text='Nur .jpg, .png oder .gif Dateien (max. 5MB)',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.gif'})
    )
    
    class Meta:
        model = Mandant
        fields = [
            'name', 'adresse', 'plz', 'ort', 'land',
            'telefon', 'fax', 'email', 'internet',
            'steuernummer', 'ust_id_nr', 'geschaeftsfuehrer', 
            'kreditinstitut', 'iban', 'bic', 'kontoinhaber'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'plz': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'ort': forms.TextInput(attrs={'class': 'form-control'}),
            'land': forms.TextInput(attrs={'class': 'form-control'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control'}),
            'fax': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'internet': forms.URLInput(attrs={'class': 'form-control'}),
            'steuernummer': forms.TextInput(attrs={'class': 'form-control'}),
            'ust_id_nr': forms.TextInput(attrs={'class': 'form-control'}),
            'geschaeftsfuehrer': forms.TextInput(attrs={'class': 'form-control'}),
            'kreditinstitut': forms.TextInput(attrs={'class': 'form-control'}),
            'iban': forms.TextInput(attrs={'class': 'form-control'}),
            'bic': forms.TextInput(attrs={'class': 'form-control'}),
            'kontoinhaber': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Name *',
            'adresse': 'Adresse *',
            'plz': 'PLZ *',
            'ort': 'Ort *',
            'land': 'Land *',
            'telefon': 'Telefon',
            'fax': 'Fax',
            'email': 'E-Mail',
            'internet': 'Internet',
            'steuernummer': 'Steuernummer',
            'ust_id_nr': 'UStIdNr',
            'geschaeftsfuehrer': 'Geschäftsführer',
            'kreditinstitut': 'Kreditinstitut',
            'iban': 'IBAN',
            'bic': 'BIC',
            'kontoinhaber': 'Kontoinhaber',
        }
    
    def clean_logo(self):
        """Validate uploaded logo file"""
        logo = self.cleaned_data.get('logo')
        
        if logo:
            # Check file size (max 5MB)
            if logo.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Die Datei ist zu groß. Maximale Größe: 5MB.')
            
            # Check file extension
            ext = os.path.splitext(logo.name)[1].lower()
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f'Ungültige Dateiendung "{ext}". Nur .jpg, .png und .gif sind erlaubt.'
                )
        
        return logo


class ItemForm(forms.ModelForm):
    """Form for Item (Article/Service) entity"""
    
    class Meta:
        model = Item
        fields = [
            'article_no', 'short_text_1', 'short_text_2', 'long_text',
            'net_price', 'purchase_price', 'tax_rate', 'cost_type_1', 'cost_type_2',
            'item_group', 'item_type', 'is_discountable', 'is_active'
        ]
        widgets = {
            'article_no': forms.TextInput(attrs={'class': 'form-control'}),
            'short_text_1': forms.TextInput(attrs={'class': 'form-control'}),
            'short_text_2': forms.TextInput(attrs={'class': 'form-control'}),
            'long_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'net_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tax_rate': forms.Select(attrs={'class': 'form-select'}),
            'cost_type_1': forms.Select(attrs={'class': 'form-select'}),
            'cost_type_2': forms.Select(attrs={'class': 'form-select'}),
            'item_group': forms.Select(attrs={'class': 'form-select'}),
            'item_type': forms.Select(attrs={'class': 'form-select'}),
            'is_discountable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'article_no': 'Artikelnummer *',
            'short_text_1': 'Kurztext 1 *',
            'short_text_2': 'Kurztext 2',
            'long_text': 'Langtext',
            'net_price': 'Verkaufspreis netto *',
            'purchase_price': 'Einkaufspreis netto *',
            'tax_rate': 'Steuersatz *',
            'cost_type_1': 'Kostenart 1 (Hauptkostenart) *',
            'cost_type_2': 'Kostenart 2 (Unterkostenart)',
            'item_group': 'Warengruppe',
            'item_type': 'Artikeltyp *',
            'is_discountable': 'Rabattfähig',
            'is_active': 'Aktiv',
        }
        help_texts = {
            'article_no': 'Eindeutige Artikelnummer',
            'short_text_1': 'Primärer Kurztext',
            'short_text_2': 'Optionaler zweiter Kurztext',
            'long_text': 'Detaillierte Beschreibung',
            'item_group': 'Optional: Zuordnung zu einer Warengruppe',
            'cost_type_1': 'Wählen Sie eine Hauptkostenart',
            'cost_type_2': 'Optional: Unterkostenart der gewählten Hauptkostenart',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter cost_type_1 to only show Hauptkostenarten (parent=None)
        self.fields['cost_type_1'].queryset = Kostenart.objects.filter(parent__isnull=True)
        
        # Filter cost_type_2 based on selected cost_type_1
        if self.instance and self.instance.pk and self.instance.cost_type_1:
            # Edit mode: filter by the saved cost_type_1
            self.fields['cost_type_2'].queryset = Kostenart.objects.filter(
                parent=self.instance.cost_type_1
            )
        elif self.data.get('cost_type_1'):
            # Form submission with data: filter by submitted cost_type_1
            try:
                cost_type_1_id = self.data.get('cost_type_1')
                self.fields['cost_type_2'].queryset = Kostenart.objects.filter(
                    parent_id=cost_type_1_id
                )
            except (ValueError, TypeError):
                self.fields['cost_type_2'].queryset = Kostenart.objects.none()
        else:
            # New item or no cost_type_1 selected: empty queryset
            self.fields['cost_type_2'].queryset = Kostenart.objects.none()
        
        # Make cost_type_2 not required
        self.fields['cost_type_2'].required = False
    
    def clean(self):
        """Validate cost type selections"""
        cleaned_data = super().clean()
        cost_type_1 = cleaned_data.get('cost_type_1')
        cost_type_2 = cleaned_data.get('cost_type_2')
        
        # Validate that cost_type_1 is a Hauptkostenart (no parent)
        if cost_type_1 and cost_type_1.parent is not None:
            raise forms.ValidationError({
                'cost_type_1': 'Kostenart 1 muss eine Hauptkostenart sein (keine Unterkostenart).'
            })
        
        # Validate that cost_type_2 (if set) is a child of cost_type_1
        if cost_type_2:
            if not cost_type_1:
                raise forms.ValidationError({
                    'cost_type_2': 'Kostenart 2 kann nur gewählt werden, wenn Kostenart 1 gesetzt ist.'
                })
            if cost_type_2.parent != cost_type_1:
                raise forms.ValidationError({
                    'cost_type_2': f'Kostenart 2 muss eine Unterkostenart von "{cost_type_1.name}" sein.'
                })
        
        return cleaned_data


class ItemGroupForm(forms.ModelForm):
    """Form for ItemGroup (Warengruppe) entity"""
    
    class Meta:
        model = ItemGroup
        fields = ['code', 'name', 'group_type', 'parent', 'description']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'group_type': forms.HiddenInput(),
            'parent': forms.HiddenInput(),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'code': 'Code',
            'name': 'Name',
            'description': 'Beschreibung',
        }
        help_texts = {
            'code': 'Eindeutiger Code für die Warengruppe',
            'name': 'Bezeichnung der Warengruppe',
        }


class UnitForm(forms.ModelForm):
    """Form for Unit (Einheit) entity"""
    
    class Meta:
        model = Unit
        fields = ['code', 'name', 'symbol', 'is_active', 'description']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: uppercase;'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'code': 'Code *',
            'name': 'Name *',
            'symbol': 'Symbol',
            'is_active': 'Aktiv',
            'description': 'Beschreibung',
        }
        help_texts = {
            'code': 'Eindeutiger Code für die Einheit (z.B. STK, PAU, LFM) - wird automatisch in Großbuchstaben umgewandelt',
            'name': 'Bezeichnung der Einheit (z.B. Stück, Pauschal, Laufender Meter)',
            'symbol': 'Optionales Symbol für die Einheit (z.B. Stk, lfm)',
            'description': 'Optionale Beschreibung der Einheit',
        }
