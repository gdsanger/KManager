from django.contrib import admin
from django import forms
from core.models import Adresse, SmtpSettings, MailTemplate, Mandant


# Register your models here.
@admin.register(Adresse)
class AdressenAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'strasse', 'plz', 'ort', 'land', 'telefon', 'email')
    search_fields = ('firma', 'name', 'strasse', 'plz', 'ort', 'land', 'telefon', 'email')
    list_filter = ('adressen_type', 'land')


class MailTemplateAdminForm(forms.ModelForm):
    """Custom form for MailTemplate with TinyMCE integration"""
    
    class Meta:
        model = MailTemplate
        fields = '__all__'
        widgets = {
            'message_html': forms.Textarea(attrs={
                'class': 'tinymce',
                'rows': 20,
            }),
        }


@admin.register(MailTemplate)
class MailTemplateAdmin(admin.ModelAdmin):
    form = MailTemplateAdminForm
    list_display = ('key', 'subject', 'from_name', 'from_address')
    search_fields = ('key', 'subject', 'from_name', 'from_address')
    
    class Media:
        js = ('https://cdn.tiny.cloud/1/no-api-key/tinymce/6/tinymce.min.js',)
        css = {
            'all': ()
        }
    
    def render_change_form(self, request, context, *args, **kwargs):
        """Add TinyMCE initialization script"""
        context['tinymce_config'] = '''
        <script>
        tinymce.init({
            selector: 'textarea.tinymce',
            plugins: 'link image code table lists',
            toolbar: 'undo redo | formatselect | bold italic | alignleft aligncenter alignright | bullist numlist | link image | code',
            menubar: false,
            height: 400
        });
        </script>
        '''
        return super().render_change_form(request, context, *args, **kwargs)


@admin.register(SmtpSettings)
class SmtpSettingsAdmin(admin.ModelAdmin):
    list_display = ('host', 'port', 'use_tls', 'username')
    
    def has_add_permission(self, request):
        """Only allow adding if no instance exists (singleton)"""
        return not SmtpSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of SMTP settings"""
        return False


@admin.register(Mandant)
class MandantAdmin(admin.ModelAdmin):
    list_display = ('name', 'plz', 'ort', 'land', 'telefon', 'email')
    search_fields = ('name', 'adresse', 'plz', 'ort', 'email', 'telefon')
    list_filter = ('land',)
    fieldsets = (
        ('Basisdaten', {
            'fields': ('name', 'adresse', 'plz', 'ort', 'land')
        }),
        ('Kontakt', {
            'fields': ('telefon', 'fax', 'email', 'internet')
        }),
        ('Rechtliches', {
            'fields': ('steuernummer', 'ust_id_nr', 'geschaeftsfuehrer', 'kreditinstitut', 'iban', 'bic', 'kontoinhaber')
        }),
    )