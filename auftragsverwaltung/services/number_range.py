"""
Number Range Service

Provides race-safe number generation for documents and contracts with yearly reset policy.
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
            target='DOCUMENT',
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
            # Year has changed with YEARLY policy, reset sequence
            number_range.current_year = yy
            number_range.current_seq = 0
        elif number_range.reset_policy == 'NEVER' and number_range.current_year != yy:
            # Year has changed with NEVER policy, update year but don't reset sequence
            number_range.current_year = yy
        
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


def get_next_contract_number(company, date_obj=None):
    """
    Get next number for a contract and company.
    
    This function is atomic and race-safe using database transactions and row-level locking.
    Raises ValueError if no contract NumberRange is configured for the company.
    
    Args:
        company: Mandant instance
        date_obj: datetime.date or datetime.datetime (defaults to today)
        
    Returns:
        str: Formatted number string (e.g., "V26-00001")
        
    Raises:
        ValueError: If no contract NumberRange exists for the company
        
    Example:
        >>> from core.models import Mandant
        >>> from datetime import date
        >>> company = Mandant.objects.first()
        >>> number = get_next_contract_number(company, date(2026, 1, 15))
        >>> print(number)  # "V26-00001"
    """
    if date_obj is None:
        date_obj = date.today()
    
    # Extract datetime.date from datetime.datetime if needed
    if hasattr(date_obj, 'date'):
        date_obj = date_obj.date()
    
    # Get two-digit year
    yy = date_obj.year % 100
    
    with transaction.atomic():
        # Try to get existing contract number range with row-level lock
        try:
            number_range = NumberRange.objects.select_for_update().get(
                company=company,
                target='CONTRACT'
            )
        except NumberRange.DoesNotExist:
            raise ValueError(
                f'Kein Nummernkreis für Verträge konfiguriert für Mandant "{company.name}". '
                'Bitte legen Sie einen Nummernkreis mit Ziel "CONTRACT" an.'
            )
        
        # Check if we need to reset the sequence based on policy
        if number_range.reset_policy == 'YEARLY' and number_range.current_year != yy:
            # Year has changed with YEARLY policy, reset sequence
            number_range.current_year = yy
            number_range.current_seq = 0
        elif number_range.reset_policy == 'NEVER' and number_range.current_year != yy:
            # Year has changed with NEVER policy, update year but don't reset sequence
            number_range.current_year = yy
        
        # Increment sequence
        number_range.current_seq += 1
        
        # Save the updated number range
        number_range.save()
        
        # Generate the formatted number with 'V' prefix for contracts
        # Use format from NumberRange, with 'V' as default prefix
        formatted_number = number_range.format.format(
            prefix='V',  # Default prefix for contracts
            yy=f"{yy:02d}",
            seq=number_range.current_seq
        )
        
        return formatted_number
