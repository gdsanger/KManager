"""
Signal handlers for Aktivitaet model to send email notifications.
"""
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from core.mailing.service import send_mail, MailServiceError
from .models import Aktivitaet
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Aktivitaet)
def store_original_values(sender, instance, **kwargs):
    """
    Store original values before save to detect changes.
    This runs before the save operation.
    """
    if instance.pk:
        try:
            original = Aktivitaet.objects.get(pk=instance.pk)
            instance._original_assigned_user = original.assigned_user
            instance._original_status = original.status
            # Store original CC users as a set of IDs for comparison
            instance._original_cc_users = set(original.cc_users.values_list('id', flat=True))
        except Aktivitaet.DoesNotExist:
            instance._original_assigned_user = None
            instance._original_status = None
            instance._original_cc_users = set()
    else:
        # New instance
        instance._original_assigned_user = None
        instance._original_status = None
        instance._original_cc_users = set()


@receiver(post_save, sender=Aktivitaet)
def send_activity_notifications(sender, instance, created, **kwargs):
    """
    Send email notifications when:
    1. Activity is created with an assigned user
    2. Assigned user is changed
    3. Status is changed to ERLEDIGT (completed)
    
    Note: CC user notifications on creation and CC changes are handled by m2m_changed signal.
    
    Deduplication: Only send emails on actual transitions.
    """
    # Get original values (set by pre_save signal)
    original_assigned_user = getattr(instance, '_original_assigned_user', None)
    original_status = getattr(instance, '_original_status', None)
    
    # Case 1 & 2: Activity assigned or assignee changed
    if instance.assigned_user:
        # Check if this is a new assignment or a change
        if created or (original_assigned_user != instance.assigned_user):
            # Only send if the new assignee has an email
            if instance.assigned_user.email:
                try:
                    # Build activity URL
                    activity_url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': instance.pk})
                    # Make it absolute (assuming request is not available here)
                    # In production, you might want to configure BASE_URL in settings
                    from django.conf import settings
                    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
                    activity_url = f"{base_url}{activity_url}"
                    
                    # Get context display
                    context_display = None
                    if instance.vertrag:
                        context_display = f"Vertrag: {instance.vertrag}"
                    elif instance.mietobjekt:
                        context_display = f"Mietobjekt: {instance.mietobjekt}"
                    elif instance.kunde:
                        context_display = f"Kunde: {instance.kunde}"
                    
                    # Prepare email context
                    email_context = {
                        'assignee_name': instance.assigned_user.get_full_name() or instance.assigned_user.username,
                        'activity_title': instance.titel,
                        'activity_description': instance.beschreibung or '',
                        'activity_priority': instance.get_prioritaet_display(),
                        'activity_due_date': instance.faellig_am.strftime('%d.%m.%Y') if instance.faellig_am else '',
                        'activity_context': context_display or '',
                        'activity_url': activity_url,
                        'creator_name': '',
                        'creator_email': '',
                    }
                    
                    # Add creator info if available
                    if instance.ersteller:
                        email_context['creator_name'] = instance.ersteller.get_full_name() or instance.ersteller.username
                        email_context['creator_email'] = instance.ersteller.email or ''
                    
                    # Build recipient list with deduplication
                    recipients = {instance.assigned_user.email}
                    
                    # Prepare CC list (creator, if different from assignee)
                    cc_list = []
                    if instance.ersteller and instance.ersteller.email and instance.ersteller != instance.assigned_user:
                        cc_list.append(instance.ersteller.email)
                    
                    # Send email
                    send_mail(
                        template_key='activity-assigned',
                        to=[instance.assigned_user.email],
                        context=email_context,
                        cc=cc_list
                    )
                    
                    logger.info(f"Sent activity assigned notification to {instance.assigned_user.email} for activity #{instance.pk}")
                    
                except MailServiceError as e:
                    logger.warning(f"Failed to send activity assigned notification for activity #{instance.pk}: {str(e)}")
                except Exception as e:
                    logger.error(f"Unexpected error sending activity assigned notification for activity #{instance.pk}: {str(e)}")
    
    # Case 3: Activity marked as completed
    if not created and instance.status == 'ERLEDIGT' and original_status != 'ERLEDIGT':
        # Build activity URL
        activity_url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': instance.pk})
        from django.conf import settings
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        activity_url = f"{base_url}{activity_url}"
        
        # Get context display
        context_display = None
        if instance.vertrag:
            context_display = f"Vertrag: {instance.vertrag}"
        elif instance.mietobjekt:
            context_display = f"Mietobjekt: {instance.mietobjekt}"
        elif instance.kunde:
            context_display = f"Kunde: {instance.kunde}"
        
        # Determine who completed it
        completed_by_name = ''
        if instance.assigned_user:
            completed_by_name = instance.assigned_user.get_full_name() or instance.assigned_user.username
        
        # Prepare email context
        email_context = {
            'creator_name': '',
            'activity_title': instance.titel,
            'activity_context': context_display or '',
            'activity_url': activity_url,
            'completed_by_name': completed_by_name,
            'completed_at': instance.updated_at.strftime('%d.%m.%Y %H:%M') if instance.updated_at else '',
        }
        
        # Build deduplicated recipient list
        recipient_emails = set()
        
        # Add creator
        if instance.ersteller and instance.ersteller.email:
            recipient_emails.add(instance.ersteller.email)
            # Update context with creator info
            email_context['creator_name'] = instance.ersteller.get_full_name() or instance.ersteller.username
        
        # Add assigned user
        if instance.assigned_user and instance.assigned_user.email:
            recipient_emails.add(instance.assigned_user.email)
        
        # Add CC users
        for cc_user in instance.cc_users.all():
            if cc_user.email:
                recipient_emails.add(cc_user.email)
        
        # Send emails to all recipients
        if recipient_emails:
            try:
                send_mail(
                    template_key='activity-completed',
                    to=list(recipient_emails),
                    context=email_context
                )
                
                logger.info(f"Sent activity completed notification to {len(recipient_emails)} recipients for activity #{instance.pk}")
                
            except MailServiceError as e:
                logger.warning(f"Failed to send activity completed notification for activity #{instance.pk}: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error sending activity completed notification for activity #{instance.pk}: {str(e)}")


@receiver(models.signals.m2m_changed, sender=Aktivitaet.cc_users.through)
def handle_cc_users_changed(sender, instance, action, pk_set, **kwargs):
    """
    Handle changes to the cc_users M2M relationship.
    
    Send notifications:
    1. When activity is created with CC users (post_add after creation)
    2. When CC users are added to existing activity (post_add, delta calculation)
    
    Note: We don't send notifications when CC users are removed.
    """
    if action == 'post_add' and pk_set:
        # Get original CC user IDs
        original_cc_ids = getattr(instance, '_original_cc_users', set())
        
        # Calculate newly added CC users
        added_cc_ids = pk_set - original_cc_ids
        
        if not added_cc_ids:
            return
        
        # Get the newly added users
        from django.contrib.auth import get_user_model
        User = get_user_model()
        added_cc_users = User.objects.filter(id__in=added_cc_ids, email__isnull=False).exclude(email='')
        
        if not added_cc_users.exists():
            return
        
        # Check if this is a new activity or an update
        # For new activities, _original_cc_users will be empty
        is_new_activity = len(original_cc_ids) == 0
        
        try:
            # Build activity URL
            activity_url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': instance.pk})
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            activity_url = f"{base_url}{activity_url}"
            
            # Get context display
            context_display = None
            if instance.vertrag:
                context_display = f"Vertrag: {instance.vertrag}"
            elif instance.mietobjekt:
                context_display = f"Mietobjekt: {instance.mietobjekt}"
            elif instance.kunde:
                context_display = f"Kunde: {instance.kunde}"
            
            # Prepare email context
            email_context = {
                'assignee_name': '',
                'activity_title': instance.titel,
                'activity_description': instance.beschreibung or '',
                'activity_priority': instance.get_prioritaet_display(),
                'activity_due_date': instance.faellig_am.strftime('%d.%m.%Y') if instance.faellig_am else '',
                'activity_context': context_display or '',
                'activity_url': activity_url,
                'creator_name': '',
                'creator_email': '',
            }
            
            # Add assignee info if available
            if instance.assigned_user:
                email_context['assignee_name'] = instance.assigned_user.get_full_name() or instance.assigned_user.username
            
            # Add creator info if available
            if instance.ersteller:
                email_context['creator_name'] = instance.ersteller.get_full_name() or instance.ersteller.username
                email_context['creator_email'] = instance.ersteller.email or ''
            
            # Build deduplicated recipient list (only newly added CC users)
            recipient_emails = set()
            for cc_user in added_cc_users:
                if cc_user.email:
                    recipient_emails.add(cc_user.email)
            
            # Remove assigned user and creator from CC recipients to avoid duplicates
            # (they get their own notifications)
            if instance.assigned_user and instance.assigned_user.email:
                recipient_emails.discard(instance.assigned_user.email)
            if instance.ersteller and instance.ersteller.email:
                recipient_emails.discard(instance.ersteller.email)
            
            if recipient_emails:
                # Use activity-assigned template for CC notifications
                send_mail(
                    template_key='activity-assigned',
                    to=list(recipient_emails),
                    context=email_context
                )
                
                action_type = "created" if is_new_activity else "added to CC list"
                logger.info(f"Sent CC notification to {len(recipient_emails)} recipients for activity #{instance.pk} ({action_type})")
                
        except MailServiceError as e:
            logger.warning(f"Failed to send CC notification for activity #{instance.pk}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending CC notification for activity #{instance.pk}: {str(e)}")
