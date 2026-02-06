"""
Management command to populate DocumentType seed data

This command creates the initial document types with idempotent behavior (upsert).
Can be run multiple times without creating duplicates.
"""
from django.core.management.base import BaseCommand
from auftragsverwaltung.models import DocumentType


class Command(BaseCommand):
    help = 'Populate DocumentType seed data (idempotent - can be run multiple times)'

    def handle(self, *args, **options):
        """Create or update document types based on key"""
        
        # Seed data according to requirements
        # key, name, prefix, is_invoice, is_correction, requires_due_date
        seed_data = [
            {
                'key': 'angebot',
                'name': 'Angebot',
                'prefix': 'A',
                'is_invoice': False,
                'is_correction': False,
                'requires_due_date': False,
                'is_active': True,
            },
            {
                'key': 'rechnung',
                'name': 'Rechnung',
                'prefix': 'R',
                'is_invoice': True,
                'is_correction': False,
                'requires_due_date': True,
                'is_active': True,
            },
            {
                'key': 'auftrag',
                'name': 'Auftragsbestätigung',
                'prefix': 'AB',
                'is_invoice': False,
                'is_correction': False,
                'requires_due_date': False,
                'is_active': True,
            },
            {
                'key': 'lieferschein',
                'name': 'Lieferschein',
                'prefix': 'LS',
                'is_invoice': False,
                'is_correction': False,
                'requires_due_date': False,
                'is_active': True,
            },
            {
                'key': 'gutschrift',
                'name': 'Rechnungskorrektur',
                'prefix': 'RK',
                'is_invoice': True,
                'is_correction': True,
                'requires_due_date': True,
                'is_active': True,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for doc_data in seed_data:
            key = doc_data['key']
            
            # Use update_or_create for idempotent upsert behavior
            doc_type, created = DocumentType.objects.update_or_create(
                key=key,
                defaults={
                    'name': doc_data['name'],
                    'prefix': doc_data['prefix'],
                    'is_invoice': doc_data['is_invoice'],
                    'is_correction': doc_data['is_correction'],
                    'requires_due_date': doc_data['requires_due_date'],
                    'is_active': doc_data['is_active'],
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {key} - {doc_data['name']} ({doc_data['prefix']})"
                    )
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated: {key} - {doc_data['name']} ({doc_data['prefix']})"
                    )
                )
                updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary: Created {created_count}, Updated {updated_count}"
            )
        )
