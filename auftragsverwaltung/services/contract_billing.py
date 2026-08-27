"""
Contract Billing Service

Provides automated invoice generation for recurring contracts.
Finds active contracts due for billing and creates invoices with unique numbers.

Business Rules:
- Finds contracts with next_run_date <= today
- Creates SalesDocument (invoice) with unique number (via NumberRange service)
- Status set to DRAFT (default) or SENT (if auto_finalize=True)
- Copies ContractLine to SalesDocumentLine (snapshot)
- Creates ContractRun for audit trail
- Advances next_run_date based on interval
- No duplicate runs per contract/day
- Numbers are always assigned immediately to avoid unique constraint violations
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple, Optional
from django.db import transaction
from django.core.exceptions import ValidationError

from auftragsverwaltung.models import (
    Contract,
    ContractLine,
    ContractRun,
    SalesDocument,
    SalesDocumentLine,
)
from auftragsverwaltung.services.document_calculation import DocumentCalculationService
from auftragsverwaltung.services.number_range import get_next_number
from core.services.activity_stream import ActivityStreamService


class ContractBillingService:
    """
    Service for generating invoices from recurring contracts
    
    This service finds active contracts that are due for billing
    and creates draft invoices with proper snapshots and audit trails.
    """
    
    @classmethod
    def generate_due(cls, today: Optional[date] = None) -> List[ContractRun]:
        """
        Generate invoices for all contracts due for billing
        
        Args:
            today: Reference date (defaults to today)
            
        Returns:
            List of ContractRun instances created
            
        Example:
            >>> from auftragsverwaltung.services.contract_billing import ContractBillingService
            >>> runs = ContractBillingService.generate_due()
            >>> for run in runs:
            ...     print(f"Contract: {run.contract.name}, Status: {run.status}")
        """
        if today is None:
            today = date.today()
        
        # Find all active contracts with next_run_date <= today
        due_contracts = Contract.objects.filter(
            is_active=True,
            next_run_date__lte=today
        ).select_related('company', 'customer', 'document_type', 'payment_term')
        
        # Filter by is_contract_active() (checks end_date)
        due_contracts = [c for c in due_contracts if c.is_contract_active()]
        
        # Process each contract
        runs = []
        for contract in due_contracts:
            run = cls._process_contract(contract, today)
            runs.append(run)
        
        return runs
    
    @classmethod
    def _process_contract(cls, contract: Contract, today: date) -> ContractRun:
        """
        Process a single contract for billing
        
        Args:
            contract: Contract instance to process
            today: Reference date
            
        Returns:
            ContractRun instance
        """
        try:
            # Check for duplicate run
            existing_run = ContractRun.objects.filter(
                contract=contract,
                run_date=contract.next_run_date
            ).first()
            
            if existing_run:
                # Skip if already processed
                return existing_run
            
            # Generate invoice within transaction
            with transaction.atomic():
                document, run = cls._generate_invoice(contract)
                
                # Update contract dates
                contract.last_run_date = contract.next_run_date
                contract.next_run_date = contract.advance_next_run_date()
                contract.save(update_fields=['last_run_date', 'next_run_date'])

                # Log successful invoice generation
                if contract.auto_finalize:
                    description = f'Rechnung {document.number} für {contract.customer.matchkey if contract.customer else "N/A"} finalisiert'
                else:
                    description = f'Rechnung {document.number} (Entwurf) für {contract.customer.matchkey if contract.customer else "N/A"} erstellt'

                ActivityStreamService.add(
                    company=contract.company,
                    domain='ORDER',
                    activity_type='CONTRACT_INVOICE_GENERATED',
                    title=f'Rechnung aus Vertrag erstellt: {contract.name}',
                    description=description,
                    target_url=f'/auftragsverwaltung/documents/{document.pk}/',
                    actor=None,  # Automated process
                    severity='INFO'
                )
            
            return run
        
        except Exception as e:
            # Create failed run on error with user-friendly message
            # Avoid exposing raw database constraint errors
            error_msg = str(e)

            # Sanitize database constraint errors for user display
            if 'unique_salesdocument_number_per_company_doctype' in error_msg.lower():
                user_friendly_msg = 'Fehler bei der Nummernvergabe: Dokumentnummer konnte nicht eindeutig zugewiesen werden. Bitte prüfen Sie die Nummernkreiskonfiguration.'
            elif 'integrity' in error_msg.lower() or 'constraint' in error_msg.lower():
                user_friendly_msg = f'Datenbankfehler bei Rechnungserstellung. Details: {error_msg[:200]}'
            else:
                user_friendly_msg = error_msg[:200]  # Limit message length

            run = ContractRun.objects.create(
                contract=contract,
                run_date=contract.next_run_date,
                status='FAILED',
                message=user_friendly_msg
            )
            
            # Log failed invoice generation
            ActivityStreamService.add(
                company=contract.company,
                domain='ORDER',
                activity_type='CONTRACT_INVOICE_FAILED',
                title=f'Rechnungserstellung fehlgeschlagen: {contract.name}',
                description=f'Fehler: {str(e)[:200]}',
                target_url=f'/auftragsverwaltung/contracts/{contract.pk}/',
                actor=None,  # Automated process
                severity='ERROR'
            )
            
            return run
    
    @classmethod
    def _generate_invoice(cls, contract: Contract) -> Tuple[SalesDocument, ContractRun]:
        """
        Generate invoice from contract
        
        Args:
            contract: Contract instance
            
        Returns:
            Tuple of (SalesDocument, ContractRun)
        """
        billing_period = cls._build_billing_period(contract)

        # Determine status based on auto_finalize flag
        if contract.auto_finalize and contract.document_type.is_invoice:
            status = 'SENT'  # Finalized invoices are marked as SENT
        else:
            status = 'DRAFT'  # Default to DRAFT

        # Create SalesDocument
        document = SalesDocument.objects.create(
            company=contract.company,
            document_type=contract.document_type,
            customer=contract.customer,
            number='',  # Will be assigned immediately below
            status=status,
            issue_date=contract.next_run_date,
            payment_term=contract.payment_term,
            subject=f"{contract.name} {billing_period}",
        )
        
        # Set payment_term snapshot
        if contract.payment_term:
            document.payment_term_snapshot = {
                'name': contract.payment_term.name,
                'discount_days': contract.payment_term.discount_days,
                'discount_rate': str(contract.payment_term.discount_rate) if contract.payment_term.discount_rate else None,
                'net_days': contract.payment_term.net_days,
            }
            
            # Calculate due_date
            document.due_date = contract.payment_term.calculate_due_date(document.issue_date)
        
        document.save(update_fields=['payment_term_snapshot', 'due_date'])
        
        # Copy ContractLine -> SalesDocumentLine
        contract_lines = contract.lines.select_related('item', 'tax_rate', 'unit', 'cost_type_1', 'cost_type_2').order_by('position_no')

        for contract_line in contract_lines:
            SalesDocumentLine.objects.create(
                document=document,
                position_no=contract_line.position_no,
                line_type='NORMAL',
                is_selected=True,
                item=contract_line.item,
                short_text_1=contract_line.short_text_1,
                short_text_2=contract_line.short_text_2,
                long_text=contract_line.long_text,
                description=contract_line.description,
                unit=contract_line.unit,
                quantity=contract_line.quantity,
                unit_price_net=contract_line.unit_price_net,
                tax_rate=contract_line.tax_rate,
                is_discountable=contract_line.is_discountable,
                kostenart1=contract_line.cost_type_1,
                kostenart2=contract_line.cost_type_2,
            )
        
        # Calculate totals
        DocumentCalculationService.recalculate(document, persist=True)

        # Assign unique document number using race-safe number range service
        # This is done for ALL invoices (both DRAFT and SENT) to avoid duplicate key violations
        # on the unique constraint (company_id, document_type_id, number)
        try:
            document.number = get_next_number(
                document.company,
                document.document_type,
                document.issue_date
            )
            document.save(update_fields=['number'])
        except Exception as e:
            # If number assignment fails, raise exception to trigger FAILED ContractRun
            raise ValueError(f'Fehler bei Nummernvergabe: {str(e)}')

        # Create ContractRun with appropriate message
        if contract.auto_finalize:
            message = f'Rechnung {document.number} erfolgreich finalisiert'
        else:
            message = f'Rechnung {document.number} (Entwurf) erfolgreich erstellt'

        run = ContractRun.objects.create(
            contract=contract,
            run_date=contract.next_run_date,
            document=document,
            status='SUCCESS',
            message=message
        )

        return document, run

    @staticmethod
    def _build_billing_period(contract: Contract) -> str:
        """
        Build billing period string for the current run based on contract dates.
        """
        period_start = contract.next_run_date
        period_end = contract.advance_next_run_date() - timedelta(days=1)
        return f"{period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}"
