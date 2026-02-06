"""
Payment Term Text Service

Provides automatic generation of payment term text based on PaymentTerm and issue_date.
Generates German text for payment terms including discount (Skonto) and net payment terms.

Examples:
- Without discount: "Zahlbar innerhalb 14 Tagen (bis 14.09.2026) netto."
- With discount: "Zahlbar innerhalb 10 Tagen (bis 10.09.2026) mit 2% Skonto, 
                  spätestens innerhalb 14 Tagen (bis 14.09.2026) netto."
"""
from datetime import date, timedelta
from decimal import Decimal


class PaymentTermTextService:
    """
    Service for generating payment term text
    
    This service generates German payment term text based on PaymentTerm settings
    and the invoice/document issue date.
    """
    
    @classmethod
    def generate_payment_term_text(
        cls,
        payment_term,
        issue_date: date
    ) -> str:
        """
        Generate payment term text
        
        Args:
            payment_term: PaymentTerm instance
            issue_date: datetime.date - Invoice/document issue date
            
        Returns:
            str: Generated payment term text in German
            
        Examples:
            >>> from core.models import PaymentTerm
            >>> from datetime import date
            >>> pt = PaymentTerm(name="14 Tage netto", net_days=14)
            >>> text = PaymentTermTextService.generate_payment_term_text(pt, date(2026, 9, 1))
            >>> print(text)
            'Zahlbar innerhalb 14 Tagen (bis 15.09.2026) netto.'
        """
        if payment_term is None:
            return ""
        
        # Convert datetime to date if needed
        if hasattr(issue_date, 'date'):
            issue_date = issue_date.date()
        
        # Check if payment term has discount (Skonto)
        if payment_term.has_discount():
            return cls._generate_with_discount(payment_term, issue_date)
        else:
            return cls._generate_without_discount(payment_term, issue_date)
    
    @classmethod
    def _generate_without_discount(
        cls,
        payment_term,
        issue_date: date
    ) -> str:
        """
        Generate payment term text without discount
        
        Format: "Zahlbar innerhalb {net_days} Tagen (bis {due_date}) netto."
        
        Args:
            payment_term: PaymentTerm instance
            issue_date: datetime.date
            
        Returns:
            str: Payment term text
        """
        # Calculate due date
        due_date = issue_date + timedelta(days=payment_term.net_days)
        
        # Format due date as DD.MM.YYYY
        due_date_str = due_date.strftime('%d.%m.%Y')
        
        # Generate text
        text = f"Zahlbar innerhalb {payment_term.net_days} Tagen (bis {due_date_str}) netto."
        
        return text
    
    @classmethod
    def _generate_with_discount(
        cls,
        payment_term,
        issue_date: date
    ) -> str:
        """
        Generate payment term text with discount (Skonto)
        
        Format: "Zahlbar innerhalb {discount_days} Tagen (bis {discount_end_date}) 
                 mit {discount_rate}% Skonto, spätestens innerhalb {net_days} Tagen 
                 (bis {due_date}) netto."
        
        Args:
            payment_term: PaymentTerm instance
            issue_date: datetime.date
            
        Returns:
            str: Payment term text with discount
        """
        # Calculate dates
        discount_end_date = issue_date + timedelta(days=payment_term.discount_days)
        due_date = issue_date + timedelta(days=payment_term.net_days)
        
        # Format dates as DD.MM.YYYY
        discount_end_str = discount_end_date.strftime('%d.%m.%Y')
        due_date_str = due_date.strftime('%d.%m.%Y')
        
        # Format discount rate as percentage (e.g., 2% from 0.02)
        discount_pct = (payment_term.discount_rate * Decimal('100')).quantize(Decimal('0.01'))
        
        # Remove trailing zeros and decimal point if whole number
        discount_pct_str = str(discount_pct).rstrip('0').rstrip('.')
        
        # Generate text
        text = (
            f"Zahlbar innerhalb {payment_term.discount_days} Tagen "
            f"(bis {discount_end_str}) mit {discount_pct_str}% Skonto, "
            f"spätestens innerhalb {payment_term.net_days} Tagen "
            f"(bis {due_date_str}) netto."
        )
        
        return text
    
    @classmethod
    def calculate_due_date(
        cls,
        payment_term,
        issue_date: date
    ) -> date:
        """
        Calculate due date based on payment term and issue date
        
        Args:
            payment_term: PaymentTerm instance
            issue_date: datetime.date
            
        Returns:
            datetime.date: Due date
        """
        if payment_term is None:
            return issue_date
        
        # Convert datetime to date if needed
        if hasattr(issue_date, 'date'):
            issue_date = issue_date.date()
        
        return issue_date + timedelta(days=payment_term.net_days)
