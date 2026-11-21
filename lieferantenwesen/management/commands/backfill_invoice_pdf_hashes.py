"""
Management command: PDF-Fingerabdruck (SHA-256) für Bestandsrechnungen nachtragen.

Ohne diesen Lauf greift die Dateiprüfung beim Import nur für neu importierte
Belege. Idempotent: bereits gefüllte Hashes bleiben unangetastet; im Storage
fehlende Dateien werden protokolliert und übersprungen.

Beispiele:
    python manage.py backfill_invoice_pdf_hashes --dry-run
    python manage.py backfill_invoice_pdf_hashes
"""
import hashlib
from collections import defaultdict

from django.core.management.base import BaseCommand

from lieferantenwesen.models import InvoiceIn


def _hash_stored_file(invoice) -> str:
    digest = hashlib.sha256()
    with invoice.pdf_file.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = (
        'Füllt pdf_sha256 für Eingangsrechnungen mit PDF und leerem Hash '
        '(idempotent) und listet Belege mit identischer Datei auf.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Nur zählen und Dubletten auflisten – es wird nichts geschrieben.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        candidates = (
            InvoiceIn.objects.exclude(pdf_file='')
            .exclude(pdf_file__isnull=True)
            .filter(pdf_sha256='')
            .order_by('created_at', 'pk')
        )

        # Bereits gefüllte Hashes zählen mit, damit Dubletten zum Bestand sichtbar sind.
        by_hash = defaultdict(list)
        for pk, no, sha in InvoiceIn.objects.exclude(pdf_sha256='').order_by(
            'created_at', 'pk'
        ).values_list('pk', 'invoice_no', 'pdf_sha256'):
            by_hash[sha].append((pk, no))

        filled = 0
        missing = 0
        for invoice in candidates:
            try:
                sha = _hash_stored_file(invoice)
            except (OSError, ValueError) as exc:
                missing += 1
                self.stderr.write(
                    f'Rechnung {invoice.pk}: Datei nicht lesbar ({exc}) – übersprungen.'
                )
                continue
            by_hash[sha].append((invoice.pk, invoice.invoice_no))
            if not dry_run:
                InvoiceIn.objects.filter(pk=invoice.pk).update(pdf_sha256=sha)
            filled += 1

        verb = 'würden gefüllt' if dry_run else 'gefüllt'
        self.stdout.write(
            f'{filled} Hash(es) {verb}, {missing} Datei(en) fehlend/übersprungen.'
        )

        duplicates = {h: v for h, v in by_hash.items() if len(v) > 1}
        if duplicates:
            self.stdout.write(f'{len(duplicates)} Datei-Dublette(n) gefunden:')
            for sha, entries in duplicates.items():
                listing = ', '.join(f'#{pk} ({no or "ohne Nr."})' for pk, no in entries)
                self.stdout.write(f'  {sha[:12]}…: {listing}')
        else:
            self.stdout.write('Keine Datei-Dubletten gefunden.')
        if dry_run:
            self.stdout.write('Trockenlauf – es wurde nichts geändert.')
