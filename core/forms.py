"""
Forms for core mailing functionality and user profile management
"""
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from core.models import SmtpSettings, MailTemplate, Mandant


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
        fields = ['key', 'subject', 'message_html', 'from_address', 'from_name', 'cc_copy_to']
        widgets = {
            'key': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'message_html': forms.Textarea(attrs={
                'class': 'form-control tinymce-editor',
                'rows': 15,
            }),
            'from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'cc_copy_to': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'key': 'Template Key *',
            'subject': 'Betreff *',
            'message_html': 'HTML Nachricht *',
            'from_address': 'Von E-Mail *',
            'from_name': 'Von Name *',
            'cc_copy_to': 'CC Kopie an',
        }
        help_texts = {
            'key': 'Eindeutiger technischer Name (z.B. "vertrag_erstellt")',
            'subject': 'Sie können Django Template-Variablen verwenden: {{ variable }}',
            'message_html': 'Sie können Django Template-Variablen verwenden: {{ variable }}',
            'cc_copy_to': 'Optional: Diese Adresse erhält automatisch eine Kopie jeder E-Mail',
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
