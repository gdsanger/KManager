"""
Signal handlers for Aktivitaet model to send email notifications.
"""
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
        except Aktivitaet.DoesNotExist:
            instance._original_assigned_user = None
            instance._original_status = None
    else:
        # New instance
        instance._original_assigned_user = None
        instance._original_status = None


@receiver(post_save, sender=Aktivitaet)
def send_activity_notifications(sender, instance, created, **kwargs):
    """
    Send email notifications when:
    1. Activity is created with an assigned user
    2. Assigned user is changed
    3. Status is changed to ERLEDIGT (completed)
    
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
        # Send email to creator
        if instance.ersteller and instance.ersteller.email:
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
                
                # Determine who completed it
                completed_by_name = ''
                if instance.assigned_user:
                    completed_by_name = instance.assigned_user.get_full_name() or instance.assigned_user.username
                
                # Prepare email context
                email_context = {
                    'creator_name': instance.ersteller.get_full_name() or instance.ersteller.username,
                    'activity_title': instance.titel,
                    'activity_context': context_display or '',
                    'activity_url': activity_url,
                    'completed_by_name': completed_by_name,
                    'completed_at': instance.updated_at.strftime('%d.%m.%Y %H:%M') if instance.updated_at else '',
                }
                
                # Prepare CC list (assigned user, if different from creator)
                cc_list = []
                if instance.assigned_user and instance.assigned_user.email and instance.assigned_user != instance.ersteller:
                    cc_list.append(instance.assigned_user.email)
                
                # Send email
                send_mail(
                    template_key='activity-completed',
                    to=[instance.ersteller.email],
                    context=email_context,
                    cc=cc_list
                )
                
                logger.info(f"Sent activity completed notification to {instance.ersteller.email} for activity #{instance.pk}")
                
            except MailServiceError as e:
                logger.warning(f"Failed to send activity completed notification for activity #{instance.pk}: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error sending activity completed notification for activity #{instance.pk}: {str(e)}")
