"""
Contract Billing Service

Provides automated invoice generation for recurring contracts.
Finds active contracts due for billing and creates draft invoices.

Business Rules:
- Finds contracts with next_run_date <= today
- Creates SalesDocument (invoice) in DRAFT status
- Copies ContractLine to SalesDocumentLine (snapshot)
- Creates ContractRun for audit trail
- Advances next_run_date based on interval
- No duplicate runs per contract/day
"""
from datetime import date
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
            
            return run
        
        except Exception as e:
            # Create failed run on error
            run = ContractRun.objects.create(
                contract=contract,
                run_date=contract.next_run_date,
                status='FAILED',
                message=str(e)
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
        # Create SalesDocument
        document = SalesDocument.objects.create(
            company=contract.company,
            document_type=contract.document_type,
            number='',  # Will be assigned by number range service
            status='DRAFT',
            issue_date=contract.next_run_date,
            payment_term=contract.payment_term,
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
        contract_lines = contract.lines.select_related('item', 'tax_rate', 'cost_type_1', 'cost_type_2').order_by('position_no')
        
        for contract_line in contract_lines:
            SalesDocumentLine.objects.create(
                document=document,
                position_no=contract_line.position_no,
                line_type='NORMAL',
                is_selected=True,
                item=contract_line.item,
                description=contract_line.description,
                quantity=contract_line.quantity,
                unit_price_net=contract_line.unit_price_net,
                tax_rate=contract_line.tax_rate,
                is_discountable=contract_line.is_discountable,
            )
        
        # Calculate totals
        DocumentCalculationService.recalculate(document, persist=True)
        
        # Create ContractRun
        run = ContractRun.objects.create(
            contract=contract,
            run_date=contract.next_run_date,
            document=document,
            status='SUCCESS',
            message=f'Invoice {document.number} generated successfully'
        )
        
        return document, run
