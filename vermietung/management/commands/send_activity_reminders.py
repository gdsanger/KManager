"""
Management command to send reminder emails for activities due in 2 days.

This command should be run periodically (e.g., daily via cron or scheduler).
It sends reminder emails to assigned users for activities that:
- Are due in exactly 2 days
- Are not yet completed (status is OFFEN or IN_BEARBEITUNG)
- Have not had a reminder sent yet
- Have an assigned user with an email address
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from datetime import timedelta, date
from vermietung.models import Aktivitaet
from core.mailing.service import send_mail, MailServiceError
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send reminder emails for activities due in 2 days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which activities would get reminders without actually sending emails',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        # Calculate target due date (2 days from today)
        today = date.today()
        target_due_date = today + timedelta(days=2)
        
        self.stdout.write(f"Looking for activities due on {target_due_date.strftime('%d.%m.%Y')}...")
        
        # Find activities that need reminders
        activities = Aktivitaet.objects.filter(
            faellig_am=target_due_date,  # Due in exactly 2 days
            status__in=['OFFEN', 'IN_BEARBEITUNG'],  # Not completed or cancelled
            reminder_sent_at__isnull=True,  # No reminder sent yet
            assigned_user__isnull=False,  # Has assigned user
            assigned_user__email__isnull=False,  # Assigned user has email
        ).exclude(
            assigned_user__email=''  # Exclude empty email strings
        ).select_related('assigned_user', 'ersteller', 'mietobjekt', 'vertrag', 'kunde')
        
        total_count = activities.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No activities found that need reminders.'))
            return
        
        self.stdout.write(f"Found {total_count} activity/activities that need reminders.")
        
        sent_count = 0
        error_count = 0
        
        for activity in activities:
            try:
                # Build activity URL
                activity_url = reverse('vermietung:aktivitaet_edit', kwargs={'pk': activity.pk})
                base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
                activity_url = f"{base_url}{activity_url}"
                
                # Get context display
                context_display = None
                if activity.vertrag:
                    context_display = f"Vertrag: {activity.vertrag}"
                elif activity.mietobjekt:
                    context_display = f"Mietobjekt: {activity.mietobjekt}"
                elif activity.kunde:
                    context_display = f"Kunde: {activity.kunde}"
                
                # Prepare email context
                email_context = {
                    'assignee_name': activity.assigned_user.get_full_name() or activity.assigned_user.username,
                    'activity_title': activity.titel,
                    'activity_description': activity.beschreibung or '',
                    'activity_priority': activity.get_prioritaet_display(),
                    'activity_due_date': activity.faellig_am.strftime('%d.%m.%Y') if activity.faellig_am else '',
                    'activity_context': context_display or '',
                    'activity_url': activity_url,
                    'creator_name': '',
                    'creator_email': '',
                }
                
                # Add creator info if available
                if activity.ersteller:
                    email_context['creator_name'] = activity.ersteller.get_full_name() or activity.ersteller.username
                    email_context['creator_email'] = activity.ersteller.email or ''
                
                # Prepare CC list (creator, if different from assignee)
                cc_list = []
                if activity.ersteller and activity.ersteller.email and activity.ersteller != activity.assigned_user:
                    cc_list.append(activity.ersteller.email)
                
                if dry_run:
                    self.stdout.write(
                        f"[DRY RUN] Would send reminder to {activity.assigned_user.email} "
                        f"for activity #{activity.pk}: {activity.titel}"
                    )
                    sent_count += 1
                else:
                    # Send email
                    send_mail(
                        template_key='activity-reminder',
                        to=[activity.assigned_user.email],
                        context=email_context,
                        cc=cc_list
                    )
                    
                    # Mark reminder as sent
                    activity.reminder_sent_at = timezone.now()
                    activity.save(update_fields=['reminder_sent_at'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Sent reminder to {activity.assigned_user.email} "
                            f"for activity #{activity.pk}: {activity.titel}"
                        )
                    )
                    logger.info(
                        f"Sent activity reminder to {activity.assigned_user.email} "
                        f"for activity #{activity.pk}"
                    )
                    sent_count += 1
                    
            except MailServiceError as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"✗ Failed to send reminder for activity #{activity.pk}: {str(e)}"
                    )
                )
                logger.warning(
                    f"Failed to send activity reminder for activity #{activity.pk}: {str(e)}"
                )
                error_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Unexpected error for activity #{activity.pk}: {str(e)}"
                    )
                )
                logger.error(
                    f"Unexpected error sending activity reminder for activity #{activity.pk}: {str(e)}"
                )
                error_count += 1
        
        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Summary:"))
        if dry_run:
            self.stdout.write(f"  Would send: {sent_count}")
        else:
            self.stdout.write(f"  Successfully sent: {sent_count}")
        if error_count > 0:
            self.stdout.write(self.style.WARNING(f"  Errors: {error_count}"))
        self.stdout.write(f"  Total: {total_count}")
