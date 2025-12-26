"""
Forms for core mailing functionality
"""
from django import forms
from core.models import SmtpSettings, MailTemplate


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
