from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from core.models import SmtpSettings, MailTemplate
from core.forms import SmtpSettingsForm, MailTemplateForm


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

