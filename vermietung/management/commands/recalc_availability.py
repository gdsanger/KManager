"""
Management command to recalculate availability for all MietObjekt.

This command updates the `verfuegbar` field for all MietObjekt based on
their currently active contracts.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from vermietung.models import MietObjekt, Vertrag


class Command(BaseCommand):
    help = 'Recalculate availability for all MietObjekt based on active contracts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mietobjekt-id',
            type=int,
            help='Recalculate availability for a specific MietObjekt ID',
        )

    def handle(self, *args, **options):
        mietobjekt_id = options.get('mietobjekt_id')
        
        if mietobjekt_id:
            # Recalculate for a specific MietObjekt
            try:
                mietobjekt = MietObjekt.objects.get(pk=mietobjekt_id)
                self._recalculate_single(mietobjekt)
            except MietObjekt.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'MietObjekt with ID {mietobjekt_id} does not exist')
                )
                return
        else:
            # Recalculate for all MietObjekt
            self._recalculate_all()

    def _recalculate_single(self, mietobjekt):
        """Recalculate availability for a single MietObjekt."""
        old_status = 'verfügbar' if mietobjekt.verfuegbar else 'nicht verfügbar'
        mietobjekt.update_availability()
        new_status = 'verfügbar' if mietobjekt.verfuegbar else 'nicht verfügbar'
        
        if old_status != new_status:
            self.stdout.write(
                self.style.SUCCESS(
                    f'{mietobjekt.name}: {old_status} → {new_status}'
                )
            )
        else:
            self.stdout.write(
                f'{mietobjekt.name}: {new_status} (unverändert)'
            )

    def _recalculate_all(self):
        """Recalculate availability for all MietObjekt."""
        mietobjekte = MietObjekt.objects.all()
        total = mietobjekte.count()
        updated = 0
        
        self.stdout.write(f'Recalculating availability for {total} MietObjekt...')
        
        for mietobjekt in mietobjekte:
            old_verfuegbar = mietobjekt.verfuegbar
            mietobjekt.update_availability()
            
            if old_verfuegbar != mietobjekt.verfuegbar:
                updated += 1
                status = 'verfügbar' if mietobjekt.verfuegbar else 'nicht verfügbar'
                self.stdout.write(
                    self.style.SUCCESS(f'  {mietobjekt.name}: → {status}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone! {updated} of {total} MietObjekt updated.'
            )
        )
