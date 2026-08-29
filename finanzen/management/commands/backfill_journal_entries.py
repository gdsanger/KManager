"""
Management command: Journaleinträge für bereits finalisierte Belege nacherzeugen.

Das Rechnungsausgangsjournal wurde erst nachträglich an die Finalisierung
angebunden. Für Belege, die vorher finalisiert wurden, fehlen die Einträge.
Dieses Command trägt sie nach – idempotent und mit Trockenlauf.

Bewusst kein automatischer Lauf in einer Migration: Der Vorgang soll
kontrolliert und prüfbar bleiben.

Beispiele:
    python manage.py backfill_journal_entries --dry-run
    python manage.py backfill_journal_entries
    python manage.py backfill_journal_entries --company 1 --include-cancelled
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from auftragsverwaltung.models import SalesDocument
from finanzen.models import OutgoingInvoiceJournalEntry
from finanzen.services.journal import JournalEntryError, create_journal_entry, get_document_kind


# Belege in diesen Status gelten nicht als finalisiert
UNFINALIZED_STATUSES = ('DRAFT',)


class Command(BaseCommand):
    help = (
        'Erzeugt fehlende Rechnungsausgangsjournal-Einträge für bereits '
        'finalisierte Rechnungen und Gutschriften (idempotent).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Nur anzeigen, was passieren würde – es wird nichts geschrieben.',
        )
        parser.add_argument(
            '--company',
            type=int,
            default=None,
            help='Nur Belege eines Mandanten (ID) verarbeiten.',
        )
        parser.add_argument(
            '--include-cancelled',
            action='store_true',
            help='Auch stornierte Belege (Status CANCELLED) nachtragen.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        company_id = options['company']
        include_cancelled = options['include_cancelled']

        documents = self._get_documents(company_id, include_cancelled)

        created = 0
        skipped_existing = 0
        failed = 0

        if dry_run:
            self.stdout.write(self.style.WARNING('Trockenlauf: Es werden keine Daten geschrieben.'))

        for document in documents:
            if get_document_kind(document) is None:
                # Sollte durch den Queryset-Filter nicht vorkommen
                continue

            if self._has_entry(document):
                skipped_existing += 1
                continue

            if dry_run:
                try:
                    self._validate(document)
                except JournalEntryError as exc:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f'FEHLER  {document.number}: {exc}'))
                    continue
                created += 1
                self.stdout.write(f'WÜRDE ANLEGEN  {document.number} ({document.company.name})')
                continue

            try:
                with transaction.atomic():
                    entry, was_created = create_journal_entry(document)
            except JournalEntryError as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f'FEHLER  {document.number}: {exc}'))
                continue

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'ANGELEGT  {entry.document_number} ({entry.gross_amount} brutto)'))
            else:
                skipped_existing += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Zusammenfassung: {created} Einträge '
            f'{"würden angelegt" if dry_run else "angelegt"}, '
            f'{skipped_existing} übersprungen (bereits vorhanden), '
            f'{failed} fehlerhaft.'
        ))

        if failed and not dry_run:
            self.stdout.write(self.style.WARNING(
                'Fehlerhafte Belege wurden übersprungen und müssen fachlich geprüft werden.'
            ))

    def _get_documents(self, company_id, include_cancelled):
        """Finalisierte, journalrelevante Belege einsammeln."""
        queryset = SalesDocument.objects.select_related(
            'company', 'customer', 'document_type'
        ).filter(
            Q(document_type__is_invoice=True) | Q(document_type__is_correction=True)
        ).exclude(number='').exclude(status__in=UNFINALIZED_STATUSES)

        if not include_cancelled:
            queryset = queryset.exclude(status='CANCELLED')

        if company_id is not None:
            from core.models import Mandant
            if not Mandant.objects.filter(pk=company_id).exists():
                raise CommandError(f'Mandant mit ID {company_id} existiert nicht.')
            queryset = queryset.filter(company_id=company_id)

        return queryset.order_by('company_id', 'issue_date', 'id')

    def _has_entry(self, document):
        return OutgoingInvoiceJournalEntry.objects.filter(
            company=document.company,
            document=document,
        ).exists()

    def _validate(self, document):
        """
        Trockenlauf-Prüfung: legt den Eintrag testweise an und verwirft ihn
        wieder, damit dieselben fachlichen Regeln greifen wie im Echtlauf.
        """
        try:
            with transaction.atomic():
                create_journal_entry(document)
                raise _Rollback()
        except _Rollback:
            return


class _Rollback(Exception):
    """Interne Ausnahme, um den Trockenlauf-Savepoint zurückzurollen."""
