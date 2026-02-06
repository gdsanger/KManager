"""
Number Range Service

Provides race-safe number generation for documents with yearly reset policy.
"""
from django.db import transaction
from datetime import date
from auftragsverwaltung.models import NumberRange


def get_next_number(company, document_type, date_obj=None):
    """
    Get next number for a document type and company.
    
    This function is atomic and race-safe using database transactions and row-level locking.
    
    Args:
        company: Mandant instance
        document_type: DocumentType instance
        date_obj: datetime.date or datetime.datetime (defaults to today)
        
    Returns:
        str: Formatted number string (e.g., "R26-00001")
        
    Example:
        >>> from core.models import Mandant
        >>> from auftragsverwaltung.models import DocumentType
        >>> from datetime import date
        >>> company = Mandant.objects.first()
        >>> doc_type = DocumentType.objects.get(key='invoice')
        >>> number = get_next_number(company, doc_type, date(2026, 1, 15))
        >>> print(number)  # "R26-00001"
    """
    if date_obj is None:
        date_obj = date.today()
    
    # Extract datetime.date from datetime.datetime if needed
    if hasattr(date_obj, 'date'):
        date_obj = date_obj.date()
    
    # Get two-digit year
    yy = date_obj.year % 100
    
    with transaction.atomic():
        # Get or create the number range with row-level lock
        number_range, created = NumberRange.objects.select_for_update().get_or_create(
            company=company,
            document_type=document_type,
            defaults={
                'current_year': yy,
                'current_seq': 0,
                'format': '{prefix}{yy}-{seq:05d}',
                'reset_policy': 'YEARLY'
            }
        )
        
        # Check if we need to reset the sequence based on policy
        if number_range.reset_policy == 'YEARLY' and number_range.current_year != yy:
            # Year has changed, reset sequence
            number_range.current_year = yy
            number_range.current_seq = 0
        
        # Increment sequence
        number_range.current_seq += 1
        
        # Save the updated number range
        number_range.save()
        
        # Generate the formatted number
        formatted_number = number_range.format.format(
            prefix=document_type.prefix,
            yy=f"{yy:02d}",
            seq=number_range.current_seq
        )
        
        return formatted_number
