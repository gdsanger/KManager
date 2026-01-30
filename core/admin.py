from django.contrib import admin
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.conf import settings
from core.models import Adresse, SmtpSettings, MailTemplate, Mandant, Kostenart
from core.mailing.service import send_mail, MailServiceError
import secrets
import string


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
            'message': forms.Textarea(attrs={
                'class': 'tinymce',
                'rows': 20,
            }),
        }


@admin.register(MailTemplate)
class MailTemplateAdmin(admin.ModelAdmin):
    form = MailTemplateAdminForm
    list_display = ('key', 'subject', 'from_name', 'from_address', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('key', 'subject', 'from_name', 'from_address')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Grunddaten', {
            'fields': ('key', 'subject', 'message', 'is_active')
        }),
        ('Absender', {
            'fields': ('from_name', 'from_address', 'cc_address')
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
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


class UnterkostenartInline(admin.TabularInline):
    """Inline admin for child cost types (Unterkostenarten)"""
    model = Kostenart
    fk_name = 'parent'
    extra = 1
    verbose_name = "Unterkostenart"
    verbose_name_plural = "Unterkostenarten"


@admin.register(Kostenart)
class KostenartAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_hauptkostenart')
    list_filter = ('parent',)
    search_fields = ('name',)
    inlines = [UnterkostenartInline]
    
    def get_queryset(self, request):
        """Only show Hauptkostenarten (top-level) in main list"""
        qs = super().get_queryset(request)
        return qs.filter(parent__isnull=True)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of Hauptkostenart if it has children"""
        if obj and obj.children.exists():
            return False
        return super().has_delete_permission(request, obj)
    
    def is_hauptkostenart(self, obj):
        """Display whether this is a main cost type"""
        return obj.is_hauptkostenart()
    is_hauptkostenart.boolean = True
    is_hauptkostenart.short_description = "Hauptkostenart"


# Custom User Admin with password reset action
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin with password reset functionality"""
    
    actions = ['reset_user_password']
    
    def reset_user_password(self, request, queryset):
        """
        Admin action to reset password for selected users.
        Generates a new random password, saves it (hashed), and sends an email.
        """
        if queryset.count() > 10:
            self.message_user(
                request,
                "Bitte wählen Sie maximal 10 Benutzer gleichzeitig aus.",
                level=messages.WARNING
            )
            return
        
        success_count = 0
        error_count = 0
        errors = []
        
        for user in queryset:
            try:
                # Validate: user must have an email address
                if not user.email:
                    errors.append(f"{user.username}: Keine E-Mail-Adresse hinterlegt")
                    error_count += 1
                    continue
                
                # Generate secure random password
                # Use Django's recommended method: secrets module for cryptographically strong random
                alphabet = string.ascii_letters + string.digits + string.punctuation
                # Remove ambiguous characters
                alphabet = alphabet.replace('l', '').replace('1', '').replace('I', '').replace('O', '').replace('0', '')
                new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
                
                # Set password (this will hash it automatically via Django's user model)
                user.set_password(new_password)
                user.save()
                
                # Get base URL from settings
                base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
                
                # Send email via mail service
                try:
                    send_mail(
                        template_key='user-password-reset',
                        to=[user.email],
                        context={
                            'username': user.username,
                            'password': new_password,
                            'baseUrl': base_url,
                        }
                    )
                    success_count += 1
                    
                except MailServiceError as e:
                    # Password is already changed, but mail failed
                    errors.append(f"{user.username}: Kennwort geändert, aber Mailversand fehlgeschlagen - {str(e)}")
                    error_count += 1
                    
            except Exception as e:
                errors.append(f"{user.username}: {str(e)}")
                error_count += 1
        
        # Display results to admin
        if success_count > 0:
            self.message_user(
                request,
                f"{success_count} Kennwort(e) erfolgreich zurückgesetzt und per E-Mail versendet.",
                level=messages.SUCCESS
            )
        
        if error_count > 0:
            error_msg = f"{error_count} Fehler beim Zurücksetzen:\n" + "\n".join(errors)
            self.message_user(
                request,
                error_msg,
                level=messages.ERROR
            )
    
    reset_user_password.short_description = "Kennwort zurücksetzen (neues Kennwort per E-Mail)"


# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)