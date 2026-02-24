import os
import json

from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.http import JsonResponse, FileResponse, Http404
from django.urls import reverse
from django_tables2 import RequestConfig
from core.models import SmtpSettings, MailTemplate, Mandant, Item, ItemGroup, Unit, Projekt, ProjektFile
from core.forms import SmtpSettingsForm, MailTemplateForm, UserProfileForm, CustomPasswordChangeForm, MandantForm, ItemForm, ItemGroupForm, UnitForm, ProjektForm, ProjektOrdnerForm, ProjektFileUploadForm
from core.tables import ItemTable
from core.filters import ItemFilter
from core.services.activity_stream import ActivityStreamService
from werkzeug.utils import secure_filename

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
    """List all mail templates with search and filter"""
    templates = MailTemplate.objects.all()
    
    # Search by key
    search_key = request.GET.get('search_key', '').strip()
    if search_key:
        templates = templates.filter(key__icontains=search_key)
    
    # Search by subject
    search_subject = request.GET.get('search_subject', '').strip()
    if search_subject:
        templates = templates.filter(subject__icontains=search_subject)
    
    # Filter by is_active
    filter_active = request.GET.get('filter_active', '')
    if filter_active == '1':
        templates = templates.filter(is_active=True)
    elif filter_active == '0':
        templates = templates.filter(is_active=False)
    
    return render(request, 'core/mailtemplate_list.html', {'templates': templates})


@login_required
def mailtemplate_create(request):
    """Create a new mail template"""
    if request.method == 'POST':
        form = MailTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'E-Mail Template erfolgreich erstellt.')
            # Check if "Save & Close" was clicked
            if request.POST.get('action') == 'save_and_close':
                return redirect('mailtemplate_list')
            # Otherwise stay on the form (redirect to edit the newly created template)
            return redirect('mailtemplate_edit', pk=form.instance.pk)
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
            # Check if "Save & Close" was clicked
            if request.POST.get('action') == 'save_and_close':
                return redirect('mailtemplate_list')
            # Otherwise stay on the edit form
            return redirect('mailtemplate_edit', pk=pk)
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
        form = MandantForm(request.POST, request.FILES)
        if form.is_valid():
            # Save mandant first to get a valid pk
            mandant = form.save()
            
            # Handle logo upload after save
            logo_file = form.cleaned_data.get('logo')
            if logo_file:
                # Create mandants directory if it doesn't exist
                mandants_dir = os.path.join(settings.MEDIA_ROOT, 'mandants')
                os.makedirs(mandants_dir, exist_ok=True)
                
                # Generate unique filename using the saved mandant pk
                ext = os.path.splitext(logo_file.name)[1]
                filename = f"mandant_{mandant.pk}_{logo_file.name}"
                relative_path = os.path.join('mandants', filename)
                full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                
                # Save file
                with open(full_path, 'wb+') as destination:
                    for chunk in logo_file.chunks():
                        destination.write(chunk)
                
                # Update mandant with logo path
                mandant.logo_path = relative_path
                mandant.save()
            
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
        form = MandantForm(request.POST, request.FILES, instance=mandant)
        if form.is_valid():
            # Handle logo upload
            logo_file = form.cleaned_data.get('logo')
            if logo_file:
                # Delete old logo if exists
                if mandant.logo_path:
                    old_logo_path = os.path.join(settings.MEDIA_ROOT, mandant.logo_path)
                    if os.path.exists(old_logo_path):
                        os.remove(old_logo_path)
                
                # Create mandants directory if it doesn't exist
                mandants_dir = os.path.join(settings.MEDIA_ROOT, 'mandants')
                os.makedirs(mandants_dir, exist_ok=True)
                
                # Generate unique filename
                ext = os.path.splitext(logo_file.name)[1]
                filename = f"mandant_{mandant.pk}_{logo_file.name}"
                relative_path = os.path.join('mandants', filename)
                full_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                
                # Save file
                with open(full_path, 'wb+') as destination:
                    for chunk in logo_file.chunks():
                        destination.write(chunk)
                
                # Store relative path
                mandant.logo_path = relative_path
            
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
    
    # Handle logo upload from detail view
    if request.method == 'POST' and 'logo' in request.FILES:
        logo_file = request.FILES['logo']
        
        # Validate file size (max 5MB)
        if logo_file.size > 5 * 1024 * 1024:
            messages.error(request, 'Die Datei ist zu groß. Maximale Größe: 5MB.')
            return redirect('mandant_detail', pk=pk)
        
        # Validate file extension
        ext = os.path.splitext(logo_file.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        
        if ext not in allowed_extensions:
            messages.error(request, f'Ungültige Dateiendung "{ext}". Nur .jpg, .png und .gif sind erlaubt.')
            return redirect('mandant_detail', pk=pk)
        
        # Delete old logo if exists
        if mandant.logo_path:
            old_logo_path = os.path.join(settings.MEDIA_ROOT, mandant.logo_path)
            if os.path.exists(old_logo_path):
                os.remove(old_logo_path)
        
        # Create mandants directory if it doesn't exist
        mandants_dir = os.path.join(settings.MEDIA_ROOT, 'mandants')
        os.makedirs(mandants_dir, exist_ok=True)
        
        # Generate unique, safe filename
        safe_logo_name = secure_filename(logo_file.name)
        filename = f"mandant_{mandant.pk}_{safe_logo_name}"
        relative_path = os.path.join('mandants', filename)
        full_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, relative_path))
        safe_base_dir = os.path.normpath(mandants_dir)
        if os.path.commonpath([safe_base_dir, full_path]) != safe_base_dir:
            messages.error(request, 'Ungültiger Dateipfad.')
            return redirect('mandant_detail', pk=pk)
        
        # Save file
        with open(full_path, 'wb+') as destination:
            for chunk in logo_file.chunks():
                destination.write(chunk)
        
        # Store relative path
        mandant.logo_path = relative_path
        mandant.save()
        
        messages.success(request, 'Logo erfolgreich hochgeladen.')
        return redirect('mandant_detail', pk=pk)
    
    # Handle logo deletion
    if request.method == 'POST' and 'delete_logo' in request.POST:
        if mandant.logo_path:
            logo_path = os.path.join(settings.MEDIA_ROOT, mandant.logo_path)
            if os.path.exists(logo_path):
                os.remove(logo_path)
            
            mandant.logo_path = ''
            mandant.save()
            messages.success(request, 'Logo erfolgreich gelöscht.')
        
        return redirect('mandant_detail', pk=pk)
    
    return render(request, 'core/mandant_detail.html', {'mandant': mandant})


@login_required
def mandant_delete(request, pk):
    """Delete a Mandant"""
    mandant = get_object_or_404(Mandant, pk=pk)
    
    if request.method == 'POST':
        mandant_name = mandant.name
        
        # Delete logo file if exists
        if mandant.logo_path:
            logo_path = os.path.join(settings.MEDIA_ROOT, mandant.logo_path)
            if os.path.exists(logo_path):
                os.remove(logo_path)
        
        mandant.delete()
        messages.success(request, f'Mandant "{mandant_name}" wurde gelöscht.')
        return redirect('mandant_list')
    
    return render(request, 'core/mandant_confirm_delete.html', {'mandant': mandant})


@login_required
def support_portal(request):
    """Customer Support Portal - Agira iframe integration"""
    agira_token = settings.AGIRA_TOKEN.strip()
    
    context = {
        'agira_token': agira_token,
        'token_missing': not agira_token
    }
    
    return render(request, 'core/support_portal.html', context)


# Item Management Views
@login_required
def item_management(request):
    """
    Combined view for item management with tree, list, and detail view.
    
    This is a single-page view that shows:
    - Left: Item group tree (Hauptgruppe/Untergruppe)
    - Right top: Filtered item list (django-tables2 + django-filter)
    - Right bottom: Detail form for selected item
    """
    try:
        # Get all item groups for tree
        main_groups = ItemGroup.objects.filter(
            group_type='MAIN', is_active=True
        ).prefetch_related('children').order_by('code')
        
        # Base queryset for items
        queryset = Item.objects.select_related(
            'item_group', 'cost_type_1', 'cost_type_2'
        )
        
        # Get group filter from URL
        group_id = request.GET.get('group', '')
        if group_id:
            try:
                group = ItemGroup.objects.get(pk=group_id)
                # Filter by selected group - if it's a main group, show all items in subgroups
                if group.group_type == 'MAIN':
                    queryset = queryset.filter(item_group__parent=group)
                else:
                    queryset = queryset.filter(item_group=group)
            except (ItemGroup.DoesNotExist, ValueError):
                pass
        
        # Apply filters
        filter_set = ItemFilter(request.GET, queryset=queryset)
        
        # Create table with filtered data
        table = ItemTable(filter_set.qs)
        table.request = request  # Pass request to table for URL generation
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 20}).configure(table)
        
        # Get selected item for detail view
        selected_item = None
        selected_id = request.GET.get('selected', '')
        if selected_id:
            try:
                selected_item = Item.objects.select_related(
                    'item_group', 'cost_type_1', 'cost_type_2'
                ).get(pk=selected_id)
            except (Item.DoesNotExist, ValueError):
                pass
            except Exception as e:
                # Handle database errors (e.g., corrupted decimal fields in test data)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error loading item {selected_id}: {e}")
                messages.warning(request, f'Fehler beim Laden des Artikels. Bitte überprüfen Sie die Stammdaten.')
        
        # Create form for selected item or new item
        form = None
        if selected_item:
            try:
                form = ItemForm(instance=selected_item)
            except Exception as e:
                # Handle form creation errors
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error creating form for item {selected_item.pk}: {e}")
                messages.warning(request, f'Formular kann nicht geladen werden. Bitte kontaktieren Sie den Administrator.')
                selected_item = None  # Don't show broken form
        
        context = {
            'main_groups': main_groups,
            'table': table,
            'filter': filter_set,
            'form': form,
            'selected_item': selected_item,
            'selected_group_id': group_id,
        }
        
        return render(request, 'core/item_management.html', context)
    
    except Exception as e:
        # Catch-all for database issues with legacy test data
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in item_management view: {e}", exc_info=True)
        messages.error(request, 'Fehler beim Laden der Artikelverwaltung. Dies kann an beschädigten Test-Daten liegen. Bitte verwenden Sie das Django Admin-Interface oder kontaktieren Sie den Administrator.')
        return redirect('home')


@login_required
def item_save(request):
    """
    Handle item save (create or update).
    Supports 'next' parameter for redirect after save.
    """
    if request.method != 'POST':
        return redirect('item_management')
    
    # Get item ID if updating
    item_id = request.POST.get('item_id', '')
    item = None
    if item_id:
        try:
            item = Item.objects.get(pk=item_id)
        except (Item.DoesNotExist, ValueError):
            pass
    
    # Create or update form
    if item:
        form = ItemForm(request.POST, instance=item)
    else:
        form = ItemForm(request.POST)
    
    if form.is_valid():
        saved_item = form.save()
        messages.success(request, f'Artikel "{saved_item.article_no}" erfolgreich gespeichert.')
        
        # Check for next parameter (for save & switch)
        next_url = request.POST.get('next', '')
        if next_url:
            return redirect(next_url)
        
        # Otherwise redirect back to management view with saved item selected
        return redirect(f'/items/?selected={saved_item.pk}')
    else:
        # Form has errors - redirect back with errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
        
        # Redirect back to the item or new form
        if item:
            return redirect(f'/items/?selected={item.pk}')
        else:
            return redirect('item_management')


@login_required
def item_create_new(request):
    """Show empty form to create a new item"""
    main_groups = ItemGroup.objects.filter(
        group_type='MAIN', is_active=True
    ).prefetch_related('children').order_by('code')
    
    queryset = Item.objects.select_related(
        'item_group', 'cost_type_1', 'cost_type_2'
    )
    
    # Apply filters from URL
    filter_set = ItemFilter(request.GET, queryset=queryset)
    
    # Create table
    table = ItemTable(filter_set.qs)
    table.request = request
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    # Empty form for new item
    form = ItemForm()
    
    context = {
        'main_groups': main_groups,
        'table': table,
        'filter': filter_set,
        'form': form,
        'selected_item': None,
        'is_new': True,
    }
    
    return render(request, 'core/item_management.html', context)


@login_required
def item_edit_ajax(request, pk):
    """
    Load item edit form for AJAX modal.
    Returns HTML partial for the modal body.
    """
    item = get_object_or_404(Item, pk=pk)
    form = ItemForm(instance=item)
    
    return render(request, 'core/item_edit_form.html', {
        'form': form,
        'item': item,
    })


@login_required
def item_new_ajax(request):
    """
    Load item creation form for AJAX modal.
    Supports preselecting item_group via ?group=<id> parameter.
    Returns HTML partial for the modal body.
    """
    # Get group parameter for preselection
    group_id = request.GET.get('group', '')
    initial_data = {}
    
    if group_id:
        try:
            group = ItemGroup.objects.get(pk=group_id)
            initial_data['item_group'] = group
        except (ItemGroup.DoesNotExist, ValueError):
            pass
    
    form = ItemForm(initial=initial_data)
    
    return render(request, 'core/item_edit_form.html', {
        'form': form,
        'item': None,
    })



@login_required
def item_save_ajax(request):
    """
    Handle item save via AJAX.
    Returns JSON response with success/error status.
    
    Activity Stream Integration:
    - Logs ITEM_CREATED for new items
    - Logs ITEM_STATUS_CHANGED when is_active changes
    - Logs ITEM_UPDATED for other changes
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'errors': {'non_field_errors': ['Invalid request method']}})
    
    # Get item ID if updating
    item_id = request.POST.get('item_id', '')
    item = None
    is_new = True
    old_is_active = None
    
    if item_id:
        try:
            item = Item.objects.get(pk=item_id)
            is_new = False
            # Track old values for change detection
            old_is_active = item.is_active
        except (Item.DoesNotExist, ValueError):
            return JsonResponse({'success': False, 'errors': {'non_field_errors': ['Item not found']}})
    
    # Create or update form
    if item:
        form = ItemForm(request.POST, instance=item)
    else:
        form = ItemForm(request.POST)
    
    if form.is_valid():
        saved_item = form.save()
        
        # Get company for activity logging (items are global, use first company)
        # TODO: In a multi-tenant setup, consider making company association more explicit
        company = Mandant.objects.first()
        
        # Log activity based on operation type
        if company:  # Only log if company exists
            if is_new:
                # Log item creation
                ActivityStreamService.add(
                    company=company,
                    domain='ORDER',
                    activity_type='ITEM_CREATED',
                    title=f'Artikel erstellt: {saved_item.article_no}',
                    description=f'{saved_item.short_text_1}',
                    target_url=f'/items/?selected={saved_item.pk}',
                    actor=request.user,
                    severity='INFO'
                )
            else:
                # For updates, check if status changed
                new_is_active = saved_item.is_active
                
                if old_is_active is not None and old_is_active != new_is_active:
                    # Status changed
                    old_status = 'aktiv' if old_is_active else 'inaktiv'
                    status_action = 'aktiviert' if new_is_active else 'deaktiviert'
                    
                    ActivityStreamService.add(
                        company=company,
                        domain='ORDER',
                        activity_type='ITEM_STATUS_CHANGED',
                        title=f'Artikel-Status geändert: {saved_item.article_no}',
                        description=f'Status: {status_action} (vorher: {old_status})',
                        target_url=f'/items/?selected={saved_item.pk}',
                        actor=request.user,
                        severity='INFO'
                    )
                else:
                    # Generic update (only if there were actual changes)
                    # Check if form actually changed anything
                    if form.changed_data:
                        ActivityStreamService.add(
                            company=company,
                            domain='ORDER',
                            activity_type='ITEM_UPDATED',
                            title=f'Artikel aktualisiert: {saved_item.article_no}',
                            description=f'{saved_item.short_text_1}',
                            target_url=f'/items/?selected={saved_item.pk}',
                            actor=request.user,
                            severity='INFO'
                        )
        
        return JsonResponse({
            'success': True,
            'item_id': saved_item.pk,
            'message': f'Artikel "{saved_item.article_no}" erfolgreich gespeichert.'
        })
    else:
        # Return errors as JSON
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(e) for e in error_list]
        return JsonResponse({'success': False, 'errors': errors})


@login_required
def item_group_get(request, pk):
    """
    Get item group data for editing.
    Returns JSON with group details.
    """
    group = get_object_or_404(ItemGroup, pk=pk)
    
    return JsonResponse({
        'id': group.pk,
        'code': group.code,
        'name': group.name,
        'group_type': group.group_type,
        'parent_id': group.parent.pk if group.parent else None,
        'description': group.description or '',
    })


@login_required
def item_group_save(request):
    """
    Handle item group save (create or update) via AJAX.
    Returns JSON response with success/error status.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'errors': 'Invalid request method'})
    
    try:
        # Get form data
        group_id = request.POST.get('group_id', '').strip()
        code = request.POST.get('code', '').strip()
        name = request.POST.get('name', '').strip()
        group_type = request.POST.get('group_type', '').strip()
        parent_id = request.POST.get('parent_id', '').strip()
        description = request.POST.get('description', '').strip()
        
        # Validate required fields
        if not code or not name or not group_type:
            return JsonResponse({'success': False, 'errors': 'Code, Name und Typ sind erforderlich'})
        
        # Get or create group
        if group_id:
            group = get_object_or_404(ItemGroup, pk=group_id)
        else:
            group = ItemGroup()
        
        # Set values
        group.code = code
        group.name = name
        group.group_type = group_type
        group.description = description if description else None
        
        # Set parent for SUB groups
        if group_type == 'SUB' and parent_id:
            try:
                parent = ItemGroup.objects.get(pk=parent_id)
                group.parent = parent
            except ItemGroup.DoesNotExist:
                return JsonResponse({'success': False, 'errors': 'Übergeordnete Gruppe nicht gefunden'})
        else:
            group.parent = None
        
        # Validate and save
        try:
            group.full_clean()  # Run model validation
            group.save()
            
            return JsonResponse({
                'success': True,
                'group_id': group.pk,
                'message': f'Warengruppe "{group.name}" erfolgreich gespeichert.'
            })
        except Exception as e:
            # Return validation errors
            if hasattr(e, 'message_dict'):
                errors = {}
                for field, messages in e.message_dict.items():
                    errors[field] = messages
                return JsonResponse({'success': False, 'errors': errors})
            else:
                return JsonResponse({'success': False, 'errors': str(e)})
    
    except Exception as e:
        return JsonResponse({'success': False, 'errors': f'Fehler beim Speichern: {str(e)}'})


@login_required
def cost_type_2_options(request):
    """
    HTMX endpoint to get filtered cost_type_2 options based on selected cost_type_1.
    Returns HTML partial with updated select options.
    """
    from core.models import Kostenart
    
    cost_type_1_id = request.GET.get('cost_type_1', '')
    
    # Create a temporary form to render the cost_type_2 field
    form = ItemForm()
    
    # Flag to track if we should disable the field
    should_disable = False
    
    # Filter cost_type_2 options based on cost_type_1
    if cost_type_1_id:
        try:
            # Try to convert to int and filter
            cost_type_1_id_int = int(cost_type_1_id)
            form.fields['cost_type_2'].queryset = Kostenart.objects.filter(
                parent_id=cost_type_1_id_int
            )
        except (ValueError, TypeError):
            # Invalid ID - disable and set empty queryset
            form.fields['cost_type_2'].queryset = Kostenart.objects.none()
            should_disable = True
    else:
        # No cost_type_1 selected - disable
        form.fields['cost_type_2'].queryset = Kostenart.objects.none()
        should_disable = True
    
    # Disable the field if needed
    if should_disable:
        form.fields['cost_type_2'].widget.attrs['disabled'] = 'disabled'
    
    return render(request, 'core/partials/cost_type_2_select.html', {'form': form})


# Unit CRUD Views
@login_required
def unit_list(request):
    """List all units with search and filter"""
    units = Unit.objects.all()
    
    # Search by code or name
    search_q = request.GET.get('q', '').strip()
    if search_q:
        units = units.filter(
            models.Q(code__icontains=search_q) | 
            models.Q(name__icontains=search_q)
        )
    
    # Filter by is_active
    filter_active = request.GET.get('is_active', '')
    if filter_active == '1':
        units = units.filter(is_active=True)
    elif filter_active == '0':
        units = units.filter(is_active=False)
    
    return render(request, 'core/unit_list.html', {'units': units})


@login_required
def unit_create(request):
    """Create a new unit"""
    if request.method == 'POST':
        form = UnitForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Einheit erfolgreich erstellt.')
            return redirect('unit_list')
    else:
        form = UnitForm()
    
    return render(request, 'core/unit_form.html', {
        'form': form,
        'title': 'Neue Einheit',
        'action': 'Erstellen'
    })


@login_required
def unit_detail(request, pk):
    """Display unit details"""
    unit = get_object_or_404(Unit, pk=pk)
    return render(request, 'core/unit_detail.html', {'unit': unit})


@login_required
def unit_edit(request, pk):
    """Edit an existing unit"""
    unit = get_object_or_404(Unit, pk=pk)
    
    if request.method == 'POST':
        form = UnitForm(request.POST, instance=unit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Einheit erfolgreich aktualisiert.')
            return redirect('unit_list')
    else:
        form = UnitForm(instance=unit)
    
    return render(request, 'core/unit_form.html', {
        'form': form,
        'title': 'Einheit bearbeiten',
        'action': 'Speichern'
    })


@login_required
def unit_delete(request, pk):
    """Delete a unit"""
    unit = get_object_or_404(Unit, pk=pk)
    
    if request.method == 'POST':
        unit.delete()
        messages.success(request, 'Einheit erfolgreich gelöscht.')
        return redirect('unit_list')
    
    return render(request, 'core/unit_confirm_delete.html', {'unit': unit})




# ---------------------------------------------------------------------------
# Projektverwaltung
# ---------------------------------------------------------------------------

@login_required
def projekt_list(request):
    """List all projects with optional search/filter."""
    projekte = Projekt.objects.all()

    search = request.GET.get('search', '').strip()
    if search:
        projekte = projekte.filter(titel__icontains=search)

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        projekte = projekte.filter(status=status_filter)

    from core.models import PROJEKT_STATUS_CHOICES
    return render(request, 'core/projekt_list.html', {
        'projekte': projekte,
        'status_choices': PROJEKT_STATUS_CHOICES,
    })


@login_required
def projekt_detail(request, pk):
    """Detail view for a project including its files and folders."""
    projekt = get_object_or_404(Projekt, pk=pk)

    # Current folder from query string
    current_ordner = request.GET.get('ordner', '').strip()

    # Files and folders at the current level
    files_qs = projekt.files.filter(ordner=current_ordner)

    upload_form = ProjektFileUploadForm(initial={'ordner': current_ordner})
    ordner_form = ProjektOrdnerForm(initial={'parent_ordner': current_ordner})

    # Breadcrumb path for folder navigation
    breadcrumb = []
    if current_ordner:
        parts = current_ordner.split('/')
        accumulated = ''
        for part in parts:
            accumulated = f"{accumulated}/{part}" if accumulated else part
            breadcrumb.append({'name': part, 'path': accumulated})

    return render(request, 'core/projekt_detail.html', {
        'projekt': projekt,
        'files': files_qs,
        'current_ordner': current_ordner,
        'breadcrumb': breadcrumb,
        'upload_form': upload_form,
        'ordner_form': ordner_form,
    })


@login_required
def projekt_create(request):
    """Create a new project."""
    if request.method == 'POST':
        form = ProjektForm(request.POST)
        if form.is_valid():
            projekt = form.save(commit=False)
            projekt.erstellt_von = request.user
            projekt.save()
            messages.success(request, f'Projekt „{projekt.titel}" wurde erfolgreich erstellt.')
            return redirect('projekt_detail', pk=projekt.pk)
    else:
        form = ProjektForm()
    return render(request, 'core/projekt_form.html', {'form': form, 'title': 'Neues Projekt'})


@login_required
def projekt_edit(request, pk):
    """Edit an existing project."""
    projekt = get_object_or_404(Projekt, pk=pk)
    if request.method == 'POST':
        form = ProjektForm(request.POST, instance=projekt)
        if form.is_valid():
            form.save()
            messages.success(request, f'Projekt „{projekt.titel}" wurde gespeichert.')
            return redirect('projekt_detail', pk=projekt.pk)
    else:
        form = ProjektForm(instance=projekt)
    return render(request, 'core/projekt_form.html', {
        'form': form,
        'projekt': projekt,
        'title': f'Projekt bearbeiten: {projekt.titel}',
    })


@login_required
def projekt_delete(request, pk):
    """Delete a project and all associated files."""
    import shutil
    from pathlib import Path

    projekt = get_object_or_404(Projekt, pk=pk)
    if request.method == 'POST':
        titel = projekt.titel
        # Remove all physical files (cascade delete handles DB records)
        project_dir = Path(settings.PROJECT_DOCUMENTS_ROOT) / str(projekt.pk)
        if project_dir.exists():
            try:
                shutil.rmtree(project_dir)
            except OSError:
                pass
        projekt.delete()
        messages.success(request, f'Projekt „{titel}" wurde gelöscht.')
        return redirect('projekt_list')
    return render(request, 'core/projekt_confirm_delete.html', {'projekt': projekt})


@login_required
def projekt_file_upload(request, pk):
    """Upload one or more files to a project folder."""
    projekt = get_object_or_404(Projekt, pk=pk)

    if request.method == 'POST':
        ordner = request.POST.get('ordner', '').strip()
        uploaded_files = request.FILES.getlist('files')

        if not uploaded_files:
            messages.error(request, 'Bitte wählen Sie mindestens eine Datei aus.')
            return redirect(f"{reverse('projekt_detail', args=[pk])}?ordner={ordner}")

        errors = []
        success_count = 0
        for uploaded_file in uploaded_files:
            try:
                storage_path, mime_type, unique_name = ProjektFile.save_uploaded_file(
                    uploaded_file, projekt, ordner
                )
                ProjektFile.objects.create(
                    projekt=projekt,
                    filename=uploaded_file.name,
                    ordner=ordner,
                    is_folder=False,
                    storage_path=storage_path,
                    file_size=uploaded_file.size,
                    mime_type=mime_type,
                    benutzer=request.user,
                )
                success_count += 1
            except Exception as exc:
                errors.append(f'{uploaded_file.name}: {exc}')

        if success_count:
            messages.success(request, f'{success_count} Datei(en) erfolgreich hochgeladen.')
        for err in errors:
            messages.error(request, err)

        return redirect(f"{reverse('projekt_detail', args=[pk])}?ordner={ordner}")

    return redirect('projekt_detail', pk=pk)


@login_required
def projekt_ordner_create(request, pk):
    """Create a new folder inside a project."""
    from pathlib import Path

    projekt = get_object_or_404(Projekt, pk=pk)

    if request.method == 'POST':
        form = ProjektOrdnerForm(request.POST)
        if form.is_valid():
            ordner_name = form.cleaned_data['ordner_name']
            parent_ordner = form.cleaned_data.get('parent_ordner', '').strip()

            full_path = f"{parent_ordner}/{ordner_name}" if parent_ordner else ordner_name

            # Create physical directory
            abs_dir = Path(settings.PROJECT_DOCUMENTS_ROOT) / str(projekt.pk) / full_path
            try:
                abs_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                messages.error(request, f'Ordner konnte nicht erstellt werden: {exc}')
                return redirect(f"{reverse('projekt_detail', args=[pk])}?ordner={parent_ordner}")

            # Create DB record
            ProjektFile.objects.get_or_create(
                projekt=projekt,
                filename=ordner_name,
                ordner=parent_ordner,
                is_folder=True,
                defaults={'benutzer': request.user},
            )
            messages.success(request, f'Ordner „{ordner_name}" wurde erstellt.')
            return redirect(f"{reverse('projekt_detail', args=[pk])}?ordner={parent_ordner}")
        else:
            for error in form.errors.values():
                messages.error(request, error)

    return redirect('projekt_detail', pk=pk)


@login_required
def projekt_file_delete(request, pk, file_pk):
    """Delete a single project file or folder."""
    projekt = get_object_or_404(Projekt, pk=pk)
    pfile = get_object_or_404(ProjektFile, pk=file_pk, projekt=projekt)

    if request.method == 'POST':
        parent_ordner = pfile.ordner
        name = pfile.filename
        pfile.delete()
        messages.success(request, f'„{name}" wurde gelöscht.')
        return redirect(f"{reverse('projekt_detail', args=[pk])}?ordner={parent_ordner}")

    return render(request, 'core/projektfile_confirm_delete.html', {
        'projekt': projekt,
        'pfile': pfile,
    })


@login_required
def projekt_file_download(request, pk, file_pk):
    """Serve a project file for download."""
    from pathlib import Path

    projekt = get_object_or_404(Projekt, pk=pk)
    pfile = get_object_or_404(ProjektFile, pk=file_pk, projekt=projekt, is_folder=False)

    file_path = Path(settings.PROJECT_DOCUMENTS_ROOT) / pfile.storage_path
    if not file_path.exists():
        raise Http404('Datei nicht gefunden.')

    response = FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=pfile.filename,
    )
    return response
