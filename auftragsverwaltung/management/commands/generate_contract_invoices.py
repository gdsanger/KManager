"""
Management command to generate invoices for due contracts

Usage:
    python manage.py generate_contract_invoices

This command finds all active contracts with next_run_date <= today
and generates draft invoices for them.
"""
from django.core.management.base import BaseCommand
from datetime import date

from auftragsverwaltung.services.contract_billing import ContractBillingService


class Command(BaseCommand):
    help = 'Generate invoices for due contracts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Reference date in YYYY-MM-DD format (default: today)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually generating invoices',
        )
    
    def handle(self, *args, **options):
        # Parse date argument
        if options['date']:
            try:
                reference_date = date.fromisoformat(options['date'])
                self.stdout.write(f"Using reference date: {reference_date}")
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {options['date']}. Use YYYY-MM-DD."))
                return
        else:
            reference_date = date.today()
            self.stdout.write(f"Using today's date: {reference_date}")
        
        # Dry-run mode
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY-RUN MODE: No invoices will be generated"))
            from auftragsverwaltung.models import Contract
            due_contracts = Contract.objects.filter(
                is_active=True,
                next_run_date__lte=reference_date
            ).select_related('company', 'customer')
            
            # Filter by is_contract_active()
            due_contracts = [c for c in due_contracts if c.is_contract_active()]
            
            if not due_contracts:
                self.stdout.write(self.style.SUCCESS("No contracts due for billing"))
                return
            
            self.stdout.write(f"Found {len(due_contracts)} contract(s) due for billing:")
            for contract in due_contracts:
                self.stdout.write(f"  - {contract.name} ({contract.company.name}): next_run_date={contract.next_run_date}")
            return
        
        # Generate invoices
        self.stdout.write("Generating invoices for due contracts...")
        runs = ContractBillingService.generate_due(today=reference_date)
        
        if not runs:
            self.stdout.write(self.style.SUCCESS("No contracts due for billing"))
            return
        
        # Report results
        success_count = sum(1 for run in runs if run.status == 'SUCCESS')
        failed_count = sum(1 for run in runs if run.status == 'FAILED')
        skipped_count = sum(1 for run in runs if run.status == 'SKIPPED')
        
        self.stdout.write(f"\nProcessed {len(runs)} contract(s):")
        self.stdout.write(self.style.SUCCESS(f"  - Success: {success_count}"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"  - Failed: {failed_count}"))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f"  - Skipped: {skipped_count}"))
        
        # Show details
        self.stdout.write("\nDetails:")
        for run in runs:
            status_style = {
                'SUCCESS': self.style.SUCCESS,
                'FAILED': self.style.ERROR,
                'SKIPPED': self.style.WARNING,
            }.get(run.status, self.style.NOTICE)
            
            doc_info = f"-> {run.document.number}" if run.document else ""
            message_info = f": {run.message}" if run.message else ""
            
            self.stdout.write(
                f"  {status_style(run.status)}: {run.contract.name} ({run.run_date}) {doc_info}{message_info}"
            )
