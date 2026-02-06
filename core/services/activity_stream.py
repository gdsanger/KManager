"""
Activity Stream Service

Provides centralized activity logging for all modules (Rental, Order Management, Finance).
Activities are explicitly created in business logic (no automatic signals/events).
"""
from typing import Optional, List
from datetime import datetime

from django.db.models import QuerySet
from django.contrib.auth.models import User

from core.models import Activity, Mandant


class ActivityStreamService:
    """
    Core service for managing activity stream entries.
    
    Provides synchronous methods to:
    - Add activity entries to the stream
    - Retrieve filtered and sorted activity entries
    
    Design principles:
    - No async/queue processing - direct database writes
    - No signals/events - explicit calls only
    - No GenericFK - only target_url for linking
    """
    
    @staticmethod
    def add(
        company: Mandant,
        domain: str,
        activity_type: str,
        title: str,
        target_url: str,
        description: Optional[str] = None,
        actor: Optional[User] = None,
        severity: str = 'INFO',
    ) -> Activity:
        """
        Add a new activity entry to the stream.
        
        Args:
            company: Mandant instance (required)
            domain: Activity domain - one of: RENTAL, ORDER, FINANCE
            activity_type: Machine-readable activity code (e.g., INVOICE_CREATED, CONTRACT_RUN_FAILED)
            title: Short description of the activity (max 255 chars)
            target_url: Clickable link to affected object (relative URL, e.g., /auftragsverwaltung/documents/123)
            description: Optional detailed description
            actor: User who performed the action (optional)
            severity: Severity level - one of: INFO, WARNING, ERROR (default: INFO)
        
        Returns:
            Created Activity instance
        
        Raises:
            ValueError: If invalid domain or severity is provided
        """
        # Validate domain
        valid_domains = [choice[0] for choice in Activity._meta.get_field('domain').choices]
        if domain not in valid_domains:
            raise ValueError(f"Invalid domain '{domain}'. Must be one of: {', '.join(valid_domains)}")
        
        # Validate severity
        valid_severities = [choice[0] for choice in Activity._meta.get_field('severity').choices]
        if severity not in valid_severities:
            raise ValueError(f"Invalid severity '{severity}'. Must be one of: {', '.join(valid_severities)}")
        
        # Create and save activity
        activity = Activity(
            company=company,
            domain=domain,
            activity_type=activity_type,
            title=title,
            target_url=target_url,
            description=description,
            actor=actor,
            severity=severity,
        )
        activity.save()
        
        return activity
    
    @staticmethod
    def latest(
        n: int = 20,
        company: Optional[Mandant] = None,
        domain: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> QuerySet[Activity]:
        """
        Retrieve the latest activity entries with optional filtering.
        
        Args:
            n: Maximum number of entries to return (default: 20)
            company: Optional filter by company/Mandant
            domain: Optional filter by domain (RENTAL, ORDER, FINANCE)
            since: Optional filter to only include entries created at or after this datetime
        
        Returns:
            QuerySet of Activity instances, sorted by created_at DESC, limited to n entries
        
        Example:
            # Get latest 50 activities for a specific company
            activities = ActivityStreamService.latest(n=50, company=my_company)
            
            # Get latest 20 rental activities from the last week
            from datetime import datetime, timedelta
            week_ago = datetime.now() - timedelta(days=7)
            activities = ActivityStreamService.latest(domain='RENTAL', since=week_ago)
        """
        # Start with all activities
        queryset = Activity.objects.all()
        
        # Apply filters
        if company is not None:
            queryset = queryset.filter(company=company)
        
        if domain is not None:
            queryset = queryset.filter(domain=domain)
        
        if since is not None:
            queryset = queryset.filter(created_at__gte=since)
        
        # Order by created_at DESC (most recent first) and limit to n
        # Note: ordering is already defined in model Meta, but we make it explicit here
        queryset = queryset.order_by('-created_at')[:n]
        
        return queryset
