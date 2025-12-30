from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from core.models import SmtpSettings, MailTemplate, Mandant
from core.forms import SmtpSettingsForm, MailTemplateForm, UserProfileForm, CustomPasswordChangeForm, MandantForm


def home(request):
    """Home page view"""
    return render(request, 'home.html')


def htmx_demo(request):
    """HTMX demo view"""
    return render(request, 'htmx_demo.html')


# SMTP Settings Views
@login_required
def smtp_settings(request):
    """View and edit SMTP settings (singleton)"""
    settings = SmtpSettings.get_settings()
    
    if request.method == 'POST':
        form = SmtpSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'SMTP-Einstellungen erfolgreich gespeichert.')
            return redirect('smtp_settings')
    else:
        form = SmtpSettingsForm(instance=settings)
    
    return render(request, 'core/smtp_settings.html', {'form': form})


# MailTemplate CRUD Views
@login_required
def mailtemplate_list(request):
    """List all mail templates"""
    templates = MailTemplate.objects.all()
    return render(request, 'core/mailtemplate_list.html', {'templates': templates})


@login_required
def mailtemplate_create(request):
    """Create a new mail template"""
    if request.method == 'POST':
        form = MailTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'E-Mail Template erfolgreich erstellt.')
            return redirect('mailtemplate_list')
    else:
        form = MailTemplateForm()
    
    return render(request, 'core/mailtemplate_form.html', {
        'form': form,
        'title': 'Neues E-Mail Template',
        'action': 'Erstellen'
    })


@login_required
def mailtemplate_edit(request, pk):
    """Edit an existing mail template"""
    template = get_object_or_404(MailTemplate, pk=pk)
    
    if request.method == 'POST':
        form = MailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, 'E-Mail Template erfolgreich aktualisiert.')
            return redirect('mailtemplate_list')
    else:
        form = MailTemplateForm(instance=template)
    
    return render(request, 'core/mailtemplate_form.html', {
        'form': form,
        'template': template,
        'title': f'Template bearbeiten: {template.key}',
        'action': 'Speichern'
    })


@login_required
def mailtemplate_detail(request, pk):
    """View details of a mail template"""
    template = get_object_or_404(MailTemplate, pk=pk)
    return render(request, 'core/mailtemplate_detail.html', {'template': template})


@login_required
def mailtemplate_delete(request, pk):
    """Delete a mail template"""
    template = get_object_or_404(MailTemplate, pk=pk)
    
    if request.method == 'POST':
        template.delete()
        messages.success(request, f'E-Mail Template "{template.key}" wurde gelöscht.')
        return redirect('mailtemplate_list')
    
    return render(request, 'core/mailtemplate_confirm_delete.html', {'template': template})


# User Profile Views
@login_required
def profile(request):
    """User profile view with name and password change"""
    profile_updated = False
    password_updated = False
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = UserProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profil erfolgreich aktualisiert.')
                profile_updated = True
        elif 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Passwort erfolgreich geändert.')
                password_updated = True
    
    if not profile_updated:
        profile_form = UserProfileForm(instance=request.user)
    if not password_updated:
        password_form = CustomPasswordChangeForm(user=request.user)
    
    return render(request, 'core/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })


# Mandant CRUD Views
@login_required
def mandant_list(request):
    """List all Mandanten"""
    mandanten = Mandant.objects.all()
    return render(request, 'core/mandant_list.html', {'mandanten': mandanten})


@login_required
def mandant_create(request):
    """Create a new Mandant"""
    if request.method == 'POST':
        form = MandantForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mandant erfolgreich erstellt.')
            return redirect('mandant_list')
    else:
        form = MandantForm()
    
    return render(request, 'core/mandant_form.html', {
        'form': form,
        'title': 'Neuer Mandant',
        'action': 'Erstellen'
    })


@login_required
def mandant_edit(request, pk):
    """Edit an existing Mandant"""
    mandant = get_object_or_404(Mandant, pk=pk)
    
    if request.method == 'POST':
        form = MandantForm(request.POST, instance=mandant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Mandant erfolgreich aktualisiert.')
            return redirect('mandant_list')
    else:
        form = MandantForm(instance=mandant)
    
    return render(request, 'core/mandant_form.html', {
        'form': form,
        'mandant': mandant,
        'title': f'Mandant bearbeiten: {mandant.name}',
        'action': 'Speichern'
    })


@login_required
def mandant_detail(request, pk):
    """View details of a Mandant"""
    mandant = get_object_or_404(Mandant, pk=pk)
    return render(request, 'core/mandant_detail.html', {'mandant': mandant})


@login_required
def mandant_delete(request, pk):
    """Delete a Mandant"""
    mandant = get_object_or_404(Mandant, pk=pk)
    
    if request.method == 'POST':
        mandant_name = mandant.name
        mandant.delete()
        messages.success(request, f'Mandant "{mandant_name}" wurde gelöscht.')
        return redirect('mandant_list')
    
    return render(request, 'core/mandant_confirm_delete.html', {'mandant': mandant})

