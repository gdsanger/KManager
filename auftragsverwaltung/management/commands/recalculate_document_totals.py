"""
Management command to recalculate the totals of sales documents

Usage:
    python manage.py recalculate_document_totals
    python manage.py recalculate_document_totals --company 1
    python manage.py recalculate_document_totals --date-from 2025-01-01 --date-to 2025-12-31
    python manage.py recalculate_document_totals --dry-run

Recomputes line sums (line_net/line_tax/line_gross) and document totals
(total_net/total_tax/total_gross/total_discount) via DocumentCalculationService.

Needed twice so far:
- after the line discount became part of the calculation (documents saved
  before still carry sums in which no discount is deducted), and
- after the tax moved from per-line rounding to per-tax-rate rounding on the
  summed net (issue #1195): documents saved before can show a tax that is a few
  cents off the rate applied to the net.

Journal entries are deliberately NOT touched: an OutgoingInvoiceJournalEntry is
an immutable snapshot of the finalized document. If the totals of an already
finalized document change here, remove its journal entry in the admin and
recreate it with `python manage.py backfill_journal_entries`.
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from auftragsverwaltung.models import SalesDocument
from auftragsverwaltung.services import DocumentCalculationService


class Command(BaseCommand):
    help = 'Recalculate line and document totals for sales documents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            help='Restrict to a single Mandant (company ID)',
        )
        parser.add_argument(
            '--date-from',
            help='Only documents with issue_date >= YYYY-MM-DD',
        )
        parser.add_argument(
            '--date-to',
            help='Only documents with issue_date <= YYYY-MM-DD',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report which documents would change; write nothing',
        )

    def handle(self, *args, **options):
        documents = SalesDocument.objects.all().select_related('company').order_by('pk')
        if options['company']:
            documents = documents.filter(company_id=options['company'])

        date_from = self._parse_date(options.get('date_from'), '--date-from')
        date_to = self._parse_date(options.get('date_to'), '--date-to')
        if date_from and date_to and date_from > date_to:
            raise CommandError('--date-from liegt nach --date-to')
        if date_from:
            documents = documents.filter(issue_date__gte=date_from)
        if date_to:
            documents = documents.filter(issue_date__lte=date_to)

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN: es wird nichts gespeichert'))

        total_count = 0
        changed_count = 0

        for document in documents.iterator():
            total_count += 1
            old = (
                document.total_net,
                document.total_tax,
                document.total_gross,
                document.total_discount,
            )

            result = DocumentCalculationService.recalculate(document, persist=not dry_run)
            new = (
                result.total_net,
                result.total_tax,
                result.total_gross,
                result.total_discount,
            )

            if old != new:
                changed_count += 1
                self.stdout.write(
                    f"{document.number or f'#{document.pk}'}: "
                    f"netto {old[0]} -> {new[0]}, "
                    f"steuer {old[1]} -> {new[1]}, "
                    f"brutto {old[2]} -> {new[2]}, "
                    f"rabatt {old[3]} -> {new[3]}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{total_count} Beleg(e) geprüft, {changed_count} mit geänderten Summen"
                + (' (nicht gespeichert)' if dry_run else ' aktualisiert')
            )
        )

        if changed_count and not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Journaleinträge wurden nicht angefasst (unveränderliche Snapshots). '
                    'Für bereits finalisierte Belege mit geänderten Summen den '
                    'Journaleintrag im Admin löschen und mit '
                    '"python manage.py backfill_journal_entries" neu erzeugen.'
                )
            )

    def _parse_date(self, value, option):
        """Parse a YYYY-MM-DD command line date or fail with a clear message."""
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f'{option} erwartet ein Datum im Format YYYY-MM-DD, nicht "{value}"')
