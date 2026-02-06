"""
Management command to populate sample TaxRate data
"""
from django.core.management.base import BaseCommand
from core.models import TaxRate
from decimal import Decimal


class Command(BaseCommand):
    help = 'Populate sample TaxRate data'

    def handle(self, *args, **options):
        """Create sample tax rates if they don't exist"""
        
        sample_rates = [
            {
                'code': 'VAT19',
                'name': 'Standard VAT 19%',
                'rate': Decimal('0.19'),
                'is_active': True
            },
            {
                'code': 'VAT7',
                'name': 'Reduced VAT 7%',
                'rate': Decimal('0.07'),
                'is_active': True
            },
            {
                'code': 'VAT0',
                'name': 'Tax Free',
                'rate': Decimal('0'),
                'is_active': True
            },
            {
                'code': 'EXPORT',
                'name': 'Export (0%)',
                'rate': Decimal('0'),
                'is_active': True
            },
        ]
        
        created_count = 0
        skipped_count = 0
        
        for rate_data in sample_rates:
            # Check if tax rate with this code already exists (case-insensitive)
            existing = TaxRate.objects.filter(code__iexact=rate_data['code']).first()
            
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped: {rate_data['code']} - already exists"
                    )
                )
                skipped_count += 1
            else:
                TaxRate.objects.create(**rate_data)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {rate_data['code']} - {rate_data['name']}"
                    )
                )
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary: Created {created_count}, Skipped {skipped_count}"
            )
        )
