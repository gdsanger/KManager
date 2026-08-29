"""
Management command: DATEV-Buchungsstapel auf der Kommandozeile erzeugen.

Zweck ist vor allem die **Formatprüfung vor dem Produktivbetrieb**: Mit
``--sample`` entsteht eine kleine, aus Beispieldaten gebaute Datei, die ohne
Zugriff auf Echtbelege gegen den Importer des Zielsystems (z. B. Kontolino,
DATEV-Import) eingelesen werden kann. Kopfsatz, Feldreihenfolge und
Zahlenformat lassen sich so verifizieren, bevor mit Echtdaten gearbeitet wird.

Ohne ``--sample`` verhält sich das Command wie die UI, schreibt aber in eine
Datei. Der Export-Status wird nur mit ``--mark-exported`` gesetzt, damit
Probeläufe folgenlos bleiben.

Beispiele:
    python manage.py datev_export --sample --output probe.csv
    python manage.py datev_export --company 1 --from 2026-01-01 --to 2026-01-31
    python manage.py datev_export --company 1 --from 2026-01-01 --to 2026-01-31 \\
        --output stapel.csv --mark-exported
"""
import uuid
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Mandant
from finanzen.services import datev_export as service


class Command(BaseCommand):
    help = 'Erzeugt einen DATEV-Buchungsstapel (EXTF) für einen Zeitraum.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int,
            help='ID des Mandanten (Default: erster Mandant).',
        )
        parser.add_argument(
            '--from', dest='date_from',
            help='Beginn des Zeitraums (YYYY-MM-DD).',
        )
        parser.add_argument(
            '--to', dest='date_to',
            help='Ende des Zeitraums (YYYY-MM-DD, inklusive).',
        )
        parser.add_argument(
            '--output',
            help=(
                'Zieldatei. Ohne diese Angabe wird nur die Zusammenfassung '
                'ausgegeben und keine Datei geschrieben.'
            ),
        )
        parser.add_argument(
            '--include-exported', action='store_true',
            help='Bereits exportierte Belege erneut aufnehmen (Wiederholungsexport).',
        )
        parser.add_argument(
            '--mark-exported', action='store_true',
            help='Belege als exportiert kennzeichnen (ohne dies bleibt der Lauf folgenlos).',
        )
        parser.add_argument(
            '--sample', action='store_true',
            help=(
                'Beispieldatei aus fest verdrahteten Buchungssätzen erzeugen, '
                'um das Format gegen den Importer des Zielsystems zu prüfen. '
                'Greift nicht auf Belegdaten zu.'
            ),
        )

    def handle(self, *args, **options):
        if options['sample']:
            content = self._sample(options)
            self._write(content, options.get('output'))
            return

        company = self._company(options)
        date_from = self._date(options, 'date_from')
        date_to = self._date(options, 'date_to')
        if date_from is None or date_to is None:
            raise CommandError('Bitte --from und --to angeben (YYYY-MM-DD).')

        # Ohne Zieldatei bliebe der Export folgenlos – dann darf er auch
        # keinen Status setzen.
        if options['mark_exported'] and not options.get('output'):
            raise CommandError('--mark-exported erfordert --output.')

        try:
            preview = service.build_preview(
                company, date_from, date_to,
                include_exported=options['include_exported'],
            )
        except service.DatevExportError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            f'Zeitraum {date_from} bis {date_to} – '
            f'{preview.booking_count} Buchungssätze, '
            f'{len(preview.journal_entries)} Ausgangs-, '
            f'{len(preview.incoming_invoices)} Eingangsbelege.'
        )
        if preview.skipped_exported:
            self.stdout.write(
                f'{preview.skipped_exported} bereits exportierte Beleg(e) übersprungen.'
            )

        if preview.has_problems:
            self.stderr.write(
                self.style.ERROR(f'{len(preview.problems)} Beleg(e) nicht exportierbar:')
            )
            for problem in preview.problems:
                self.stderr.write(f'  [{problem.source}] {problem.reference}: {problem.message}')
            raise CommandError('Bitte zuerst die Fehlerliste abarbeiten.')

        if not options.get('output'):
            self.stdout.write(
                'Vorschau abgeschlossen. Mit --output <datei> die EXTF-Datei schreiben.'
            )
            return

        self._write(service.render_extf(preview), options['output'])

        if options['mark_exported']:
            batch_id = f'{timezone.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}'
            service.mark_exported(preview, batch_id)
            self.stdout.write(self.style.SUCCESS(f'Als exportiert gekennzeichnet: {batch_id}'))
        else:
            self.stdout.write(
                'Hinweis: Ohne --mark-exported bleibt der Export-Status unverändert.'
            )

    # --- Hilfsfunktionen ---------------------------------------------------

    def _company(self, options):
        if options.get('company'):
            try:
                return Mandant.objects.get(pk=options['company'])
            except Mandant.DoesNotExist:
                raise CommandError(f'Mandant {options["company"]} existiert nicht.')
        company = Mandant.objects.order_by('pk').first()
        if company is None:
            raise CommandError('Es ist kein Mandant angelegt.')
        return company

    def _date(self, options, key):
        raw = options.get(key)
        if not raw:
            return None
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f'Ungültiges Datum für --{key}: {raw} (erwartet YYYY-MM-DD).')

    def _sample(self, options):
        """
        Kleine Beispieldatei bauen: eine Ausgangsrechnung, eine Gutschrift und
        eine Eingangsrechnung – genug, um Kopfsatz, Soll/Haben-Kennzeichen und
        Zahlenformat beim Zielsystem zu prüfen.
        """
        from decimal import Decimal

        company = Mandant.objects.order_by('pk').first()
        if company is None:
            raise CommandError(
                'Für die Beispieldatei wird ein Mandant mit '
                'Buchhaltungseinstellungen benötigt.'
            )

        year = date.today().year
        preview = service.ExportPreview(
            company=company,
            date_from=date(year, 1, 1),
            date_to=date(year, 1, 31),
        )
        preview.bookings = [
            service.Booking(
                amount=Decimal('1190.00'), account='10000', contra_account='8400',
                document_date=date(year, 1, 15), document_field_1='RE-0001',
                text='Rechnung Musterkunde GmbH',
            ),
            service.Booking(
                amount=Decimal('-119.00'), account='10000', contra_account='8400',
                document_date=date(year, 1, 20), document_field_1='GS-0001',
                text='Gutschrift Musterkunde GmbH',
            ),
            service.Booking(
                amount=Decimal('238.00'), account='4930', contra_account='70000',
                document_date=date(year, 1, 10), document_field_1='ER-2026-7',
                text='Bürobedarf',
            ),
        ]
        return service.render_extf(preview)

    def _write(self, content, output):
        if not output:
            self.stdout.write(content.decode(service.ENCODING, errors='replace'))
            return
        with open(output, 'wb') as handle:
            handle.write(content)
        self.stdout.write(self.style.SUCCESS(f'Datei geschrieben: {output}'))
