"""
Management command to recalculate the totals of sales documents

Usage:
    python manage.py recalculate_document_totals
    python manage.py recalculate_document_totals --company 1
    python manage.py recalculate_document_totals --dry-run

Recomputes line sums (line_net/line_tax/line_gross) and document totals
(total_net/total_tax/total_gross/total_discount) via DocumentCalculationService.
Needed after the line discount became part of the calculation: documents that
were saved before still carry sums in which no discount is deducted.
"""
from django.core.management.base import BaseCommand

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
            '--dry-run',
            action='store_true',
            help='Only report which documents would change; write nothing',
        )

    def handle(self, *args, **options):
        documents = SalesDocument.objects.all().select_related('company').order_by('pk')
        if options['company']:
            documents = documents.filter(company_id=options['company'])

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
