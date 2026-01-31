from django.contrib import admin
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.conf import settings
from core.models import (
    Adresse, SmtpSettings, MailTemplate, Mandant, Kostenart,
    AIProvider, AIModel, AIJobsHistory
)
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
        password_changed_count = 0  # Track passwords changed regardless of email status
        
        for user in queryset:
            # Validate: user must have an email address BEFORE changing password
            if not user.email:
                errors.append(f"{user.username}: Keine E-Mail-Adresse hinterlegt")
                error_count += 1
                continue
            
            try:
                # Generate secure random password
                # NOTE: Sending passwords via email is a security consideration.
                # This implementation sends temporary passwords that users should change immediately.
                # Consider using time-limited password reset tokens for higher security.
                # Use Django's recommended method: secrets module for cryptographically strong random
                # Build alphabet with mixed character types for security
                alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
                new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
                
                # Set password (this will hash it automatically via Django's user model)
                user.set_password(new_password)
                user.save()
                password_changed_count += 1
                
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
                # Unexpected error during password generation or save
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


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'is_active', 'created_at')
    list_filter = ('provider_type', 'is_active')
    search_fields = ('name', 'provider_type')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Provider Information', {
            'fields': ('name', 'provider_type', 'is_active')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'organization_id'),
            'description': 'API credentials (stored securely)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ('provider', 'name', 'model_id', 'is_active', 'input_price_per_1m_tokens', 'output_price_per_1m_tokens')
    list_filter = ('provider', 'is_active')
    search_fields = ('name', 'model_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Model Information', {
            'fields': ('provider', 'name', 'model_id', 'is_active')
        }),
        ('Pricing', {
            'fields': ('input_price_per_1m_tokens', 'output_price_per_1m_tokens'),
            'description': 'Pricing in USD per 1 million tokens'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AIJobsHistory)
class AIJobsHistoryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'agent', 'user', 'provider', 'model', 'status', 'costs', 'duration_ms')
    list_filter = ('status', 'provider', 'model', 'agent')
    search_fields = ('agent', 'user__username', 'error_message')
    readonly_fields = ('timestamp', 'duration_ms', 'costs', 'input_tokens', 'output_tokens')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Job Information', {
            'fields': ('agent', 'user', 'status', 'client_ip')
        }),
        ('AI Configuration', {
            'fields': ('provider', 'model')
        }),
        ('Usage & Costs', {
            'fields': ('input_tokens', 'output_tokens', 'costs', 'duration_ms')
        }),
        ('Timing', {
            'fields': ('timestamp',)
        }),
        ('Error Details', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of job history records"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make job history read-only"""
        return False


# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)