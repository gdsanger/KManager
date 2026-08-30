"""
Project Billing Service

Überführt die offenen Stunden eines Projekts in einen Rechnungsentwurf.

Fachlicher Ablauf (typischerweise am Monatsende):
- Auswahl aller unabgerechneten Zeiterfassungen des Projekts im gewählten Zeitraum
- Eine Rechnung je Projekt mit Leistungszeitraum und einer Position je Zeiterfassung
- Die Tätigkeitsbeschreibungen werden vor dem Erzeugen der Positionen per KI in
  eine für die Rechnung übliche Form gebracht (siehe
  ``core.services.ai.time_entry_normalization``); die Zeiterfassung selbst
  bleibt unverändert
- Leistungs- und Anfahrtszeit werden getrennt abgerechnet (eigener Artikel,
  eigener Stundensatz aus dem Projekt)
- Jede Zeiterfassung wird einzeln auf 15 Minuten aufgerundet, nicht die Summe
- Der Beleg entsteht immer als Entwurf (``DRAFT``); Finalisierung, Journaleintrag
  und Versand laufen anschließend über den bestehenden Weg
- Kein Journaleintrag hier - den bekommt der Beleg erst bei der Finalisierung

Der Ablauf ist an ``ContractBillingService._generate_invoice()`` angelehnt
(Beleg anlegen, Positionen erzeugen, Summen berechnen, Nummer vergeben,
Activity-Stream-Eintrag).
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from math import ceil
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from auftragsverwaltung.models import (
    DocumentType,
    SalesDocument,
    SalesDocumentLine,
    TimeEntry,
)
from auftragsverwaltung.services.document_calculation import DocumentCalculationService
from auftragsverwaltung.services.item_snapshot import apply_item_snapshot
from auftragsverwaltung.services.number_range import get_next_number
from core.models import PaymentTerm
from core.services.activity_stream import ActivityStreamService
from core.services.ai.time_entry_normalization import TimeEntryNormalizationService

#: Abrechnungstakt: jede Zeiterfassung wird einzeln auf volle 15 Minuten
#: aufgerundet (0,25 / 0,50 / 0,75 / 1,00 h ...).
BILLING_INTERVAL_MINUTES = 15

#: Nachkommastellen des Mengenfeldes von ``SalesDocumentLine.quantity``.
QUANTITY_QUANTIZE = Decimal('0.0001')

#: Hinweis für die Oberfläche, wenn die KI-Normalisierung nicht durchlief.
#: Der Lauf selbst ist dann trotzdem erfolgreich - die Positionen tragen den
#: Originaltext der Zeiterfassung.
NORMALIZATION_WARNING = (
    'Die Tätigkeitsbeschreibungen konnten nicht automatisch für die Rechnung '
    'aufbereitet werden. Die Positionen enthalten den Originaltext der '
    'Zeiterfassung - bitte die Langtexte im Entwurf prüfen.'
)


class ProjectBillingError(Exception):
    """
    Der Abrechnungslauf ist nicht möglich.

    ``errors`` enthält alle Gründe im Klartext, damit die Oberfläche sie als
    Liste anzeigen kann statt nur den ersten Fehler.
    """

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__(' '.join(self.errors))


@dataclass
class ProjectBillingPreviewLine:
    """Eine Zeile der Abrechnungsvorschau (noch nichts gespeichert)."""

    time_entry: TimeEntry
    item: Optional[object]
    quantity: Decimal
    unit_price_net: Decimal
    discount: Decimal

    @property
    def line_net(self) -> Decimal:
        """Nettobetrag der Zeile inklusive Rabatt (nur zur Anzeige)."""
        gross = self.quantity * self.unit_price_net
        net = gross * (Decimal('1.00') - (self.discount / Decimal('100')))
        return net.quantize(Decimal('0.01'))


@dataclass
class ProjectBillingPreview:
    """
    Vorschau auf den Abrechnungslauf.

    ``errors`` ist leer, wenn der Lauf durchgeführt werden kann.
    """

    projekt: object
    date_from: date
    date_to: date
    lines: List[ProjectBillingPreviewLine] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def can_bill(self) -> bool:
        return not self.errors and bool(self.lines)

    @property
    def total_net(self) -> Decimal:
        return sum((line.line_net for line in self.lines), Decimal('0.00'))

    @property
    def total_minutes(self) -> int:
        return sum(line.time_entry.duration_minutes for line in self.lines)

    @property
    def total_quantity(self) -> Decimal:
        return sum((line.quantity for line in self.lines), Decimal('0'))


class ProjectBillingService:
    """
    Erzeugt aus den offenen Stunden eines Projekts einen Rechnungsentwurf.

    Beispiel:
        >>> from auftragsverwaltung.services.project_billing import ProjectBillingService
        >>> preview = ProjectBillingService.build_preview(projekt, date(2026, 8, 1), date(2026, 8, 31))
        >>> if preview.can_bill:
        ...     document = ProjectBillingService.create_invoice(
        ...         projekt, date(2026, 8, 1), date(2026, 8, 31), actor=request.user
        ...     )
    """

    # ------------------------------------------------------------------
    # Auswahl und Rundung
    # ------------------------------------------------------------------

    @staticmethod
    def get_open_entries(projekt, date_from: date, date_to: date):
        """
        Offene (noch nicht abgerechnete) Zeiterfassungen des Projekts im Zeitraum.

        Sortierung nach Leistungsdatum und PK - genau in dieser Reihenfolge
        werden später die Positionsnummern vergeben.
        """
        return (
            TimeEntry.objects.filter(
                projekt=projekt,
                is_billed=False,
                service_date__gte=date_from,
                service_date__lte=date_to,
            )
            .select_related('company', 'customer', 'performed_by')
            .order_by('service_date', 'pk')
        )

    @staticmethod
    def round_quantity(duration_minutes: int) -> Decimal:
        """
        Dauer in Stunden, je Eintrag auf volle 15 Minuten aufgerundet.

        1 Minute -> 0,25 h; 16 Minuten -> 0,50 h; 60 Minuten -> 1,00 h;
        61 Minuten -> 1,25 h.
        """
        minutes = max(int(duration_minutes or 0), 0)
        rounded = ceil(minutes / BILLING_INTERVAL_MINUTES) * BILLING_INTERVAL_MINUTES
        return (Decimal(rounded) / Decimal('60')).quantize(QUANTITY_QUANTIZE)

    @staticmethod
    def get_invoice_document_type() -> Optional[DocumentType]:
        """Rechnungs-Dokumenttyp (Key ``invoice``) bzw. ersatzweise ein Typ mit ``is_invoice``."""
        return (
            DocumentType.objects.filter(key__iexact='invoice').first()
            or DocumentType.objects.filter(is_invoice=True).order_by('key').first()
        )

    # ------------------------------------------------------------------
    # Vorschau und Prüfungen
    # ------------------------------------------------------------------

    @classmethod
    def build_preview(cls, projekt, date_from: date, date_to: date) -> ProjectBillingPreview:
        """
        Vorschau auf den Lauf: die einbezogenen Zeiterfassungen plus alle
        Gründe, die den Lauf verhindern.

        Es wird nichts gespeichert.
        """
        preview = ProjectBillingPreview(projekt=projekt, date_from=date_from, date_to=date_to)

        if date_from > date_to:
            preview.errors.append(
                'Das Von-Datum liegt nach dem Bis-Datum - bitte den Zeitraum korrigieren.'
            )
            return preview

        entries = list(cls.get_open_entries(projekt, date_from, date_to))
        preview.errors.extend(cls._collect_errors(projekt, entries, date_from, date_to))

        for entry in entries:
            item, rate = cls._conditions_for(projekt, entry)
            discount = projekt.discount_percent or Decimal('0.00')
            if item is not None and not item.is_discountable:
                discount = Decimal('0.00')
            preview.lines.append(
                ProjectBillingPreviewLine(
                    time_entry=entry,
                    item=item,
                    quantity=cls.round_quantity(entry.duration_minutes),
                    unit_price_net=rate if rate is not None else Decimal('0.00'),
                    discount=discount,
                )
            )

        return preview

    @staticmethod
    def _conditions_for(projekt, entry: TimeEntry):
        """Artikel und Stundensatz für eine Zeiterfassung (Leistung oder Anfahrt)."""
        if entry.is_travel_cost:
            return projekt.travel_item, projekt.travel_hourly_rate
        return projekt.billing_item, projekt.hourly_rate

    @classmethod
    def _collect_errors(cls, projekt, entries, date_from: date, date_to: date) -> List[str]:
        """
        Alle Gründe, die den Lauf verhindern - jeder benennt den fehlenden Wert.

        Es werden bewusst alle Fehler gesammelt (nicht beim ersten abgebrochen),
        damit die Oberfläche sie in einem Rutsch anzeigen kann.
        """
        errors: List[str] = []

        if projekt.kunde_id is None:
            errors.append(
                f'Das Projekt „{projekt.titel}" hat keinen Kunden. '
                'Ohne Kunde kann keine Rechnung erstellt werden.'
            )
        if projekt.company_id is None:
            errors.append(
                f'Das Projekt „{projekt.titel}" hat keinen Mandanten. '
                'Ohne Mandant kann keine Rechnung erstellt werden.'
            )

        has_service = any(not entry.is_travel_cost for entry in entries)
        has_travel = any(entry.is_travel_cost for entry in entries)

        if has_service:
            if projekt.billing_item_id is None:
                errors.append(
                    'Für die Leistungszeit fehlt der Abrechnungsartikel '
                    '(Feld „Abrechnungsartikel (Leistung)" am Projekt).'
                )
            if projekt.hourly_rate is None:
                errors.append(
                    'Für die Leistungszeit fehlt der Stundensatz '
                    '(Feld „Stundensatz (netto)" am Projekt).'
                )
        if has_travel:
            if projekt.travel_item_id is None:
                errors.append(
                    'Für die Anfahrtszeit fehlt der Abrechnungsartikel '
                    '(Feld „Abrechnungsartikel (Anfahrt)" am Projekt).'
                )
            if projekt.travel_hourly_rate is None:
                errors.append(
                    'Für die Anfahrtszeit fehlt der Stundensatz '
                    '(Feld „Stundensatz Anfahrt (netto)" am Projekt).'
                )

        if not entries:
            errors.append(
                'Im Zeitraum {} - {} gibt es keine offenen Zeiterfassungen. '
                'Es wird keine leere Rechnung erzeugt.'.format(
                    date_from.strftime('%d.%m.%Y'), date_to.strftime('%d.%m.%Y')
                )
            )

        # Mandantenbruch wird gemeldet statt stillschweigend übernommen.
        if projekt.company_id is not None:
            abweichend = [e for e in entries if e.company_id != projekt.company_id]
            if abweichend:
                nummern = ', '.join(e.service_date.strftime('%d.%m.%Y') for e in abweichend[:5])
                errors.append(
                    f'{len(abweichend)} Zeiterfassung(en) gehören zu einem anderen Mandanten '
                    f'als das Projekt (z. B. vom {nummern}). Bitte zuerst korrigieren.'
                )

        if cls.get_invoice_document_type() is None:
            errors.append(
                'Es ist kein Dokumenttyp „Rechnung" (Key „invoice") konfiguriert.'
            )

        return errors

    # ------------------------------------------------------------------
    # Abrechnungslauf
    # ------------------------------------------------------------------

    @classmethod
    def create_invoice(cls, projekt, date_from: date, date_to: date, actor=None) -> SalesDocument:
        """
        Erzeugt den Rechnungsentwurf über die offenen Stunden des Projekts.

        Args:
            projekt: core.Projekt Instanz
            date_from: Beginn des Leistungszeitraums (einschließlich)
            date_to: Ende des Leistungszeitraums (einschließlich), zugleich Belegdatum
            actor: auslösender Benutzer (für den Activity Stream), optional

        Returns:
            SalesDocument: der erzeugte Rechnungsentwurf (Status ``DRAFT``).
                Am Objekt hängt ``normalization_warning``: ``None``, wenn die
                Langtexte aufbereitet werden konnten, sonst der anzuzeigende
                Warntext (:data:`NORMALIZATION_WARNING`).

        Raises:
            ProjectBillingError: wenn Konditionen fehlen oder keine offenen
                Stunden vorliegen. Es wird dann nichts angelegt.

        Alles läuft in einer Transaktion: schlägt ein Schritt fehl, bleibt weder
        eine halbe Rechnung noch eine fälschlich als abgerechnet markierte Stunde
        zurück.
        """
        with transaction.atomic():
            # Innerhalb der Transaktion neu einlesen: bereits abgerechnete
            # Stunden fallen durch den Filter ``is_billed=False`` heraus, ein
            # zweiter Lauf über denselben Zeitraum erzeugt daher keine Dubletten.
            entries = list(cls.get_open_entries(projekt, date_from, date_to))
            errors = cls._collect_errors(projekt, entries, date_from, date_to)
            if date_from > date_to:
                errors.insert(
                    0, 'Das Von-Datum liegt nach dem Bis-Datum - bitte den Zeitraum korrigieren.'
                )
            if errors:
                raise ProjectBillingError(errors)

            # Alle Beschreibungen in einem Zug aufbereiten - ein Aufruf je Block
            # statt einer je Position. Fällt die KI aus, kommen hier die
            # Originaltexte zurück und der Lauf geht normal weiter.
            normalization = TimeEntryNormalizationService().normalize(
                [entry.description for entry in entries], user=actor
            )
            long_texts = normalization.texts

            document = cls._create_document(projekt, date_from, date_to)
            billed_at = timezone.now()

            for position_no, entry in enumerate(entries, start=1):
                line = cls._create_line(
                    document, projekt, entry, position_no, long_texts[position_no - 1]
                )
                entry.is_billed = True
                entry.billed_at = billed_at
                entry.invoice_line = line
                entry.save(update_fields=['is_billed', 'billed_at', 'invoice_line', 'updated_at'])

            DocumentCalculationService.recalculate(document, persist=True)

            ActivityStreamService.add(
                company=document.company,
                domain='ORDER',
                activity_type='PROJECT_INVOICE_GENERATED',
                title=f'Rechnung aus Projekt erstellt: {projekt.titel}',
                description=(
                    f'Rechnung {document.number} (Entwurf) über {len(entries)} Zeiterfassung(en) '
                    f'für den Leistungszeitraum {date_from.strftime("%d.%m.%Y")} - '
                    f'{date_to.strftime("%d.%m.%Y")} erstellt'
                ),
                target_url=f'/auftragsverwaltung/documents/{document.document_type.key}/{document.pk}/',
                actor=actor,
                severity='INFO',
            )

        document.refresh_from_db()
        # Transientes Feld: die Oberfläche zeigt den Hinweis nach dem Lauf an,
        # gespeichert wird er nicht.
        document.normalization_warning = NORMALIZATION_WARNING if normalization.failed else None
        return document

    @classmethod
    def _create_document(cls, projekt, date_from: date, date_to: date) -> SalesDocument:
        """Rechnungsentwurf mit Projektbezug, Leistungszeitraum und Belegnummer."""
        document_type = cls.get_invoice_document_type()
        payment_term = PaymentTerm.get_default()

        subject = (
            f'Projekt „{projekt.titel}" — Leistungszeitraum '
            f'{date_from.strftime("%d.%m.%Y")} – {date_to.strftime("%d.%m.%Y")}'
        )

        document = SalesDocument(
            company=projekt.company,
            document_type=document_type,
            customer=projekt.kunde,
            number='',
            status='DRAFT',
            # Belegdatum ist das gewählte Bis-Datum (i. d. R. der Monatsletzte),
            # nicht das Erfassungsdatum.
            issue_date=date_to,
            performance_date_from=date_from,
            performance_date_to=date_to,
            payment_term=payment_term,
            subject=subject[:200],
        )

        if payment_term:
            document.payment_term_snapshot = {
                'name': payment_term.name,
                'discount_days': payment_term.discount_days,
                'discount_rate': str(payment_term.discount_rate) if payment_term.discount_rate else None,
                'net_days': payment_term.net_days,
            }
            document.due_date = payment_term.calculate_due_date(document.issue_date)

        # Die Nummer wird sofort vergeben - wie beim Vertragslauf, um
        # Verletzungen der Unique-Constraint zu vermeiden.
        document.number = get_next_number(
            projekt.company, document_type, document.issue_date
        )
        document.save()
        return document

    @classmethod
    def _create_line(
        cls,
        document,
        projekt,
        entry: TimeEntry,
        position_no: int,
        long_text: Optional[str] = None,
    ) -> SalesDocumentLine:
        """
        Eine Rechnungsposition je Zeiterfassung.

        ``long_text`` ist die aufbereitete Tätigkeitsbeschreibung; ohne Angabe
        gilt der Originaltext der Zeiterfassung.
        """
        item, rate = cls._conditions_for(projekt, entry)
        billing_text = long_text if long_text is not None else entry.description

        line = SalesDocumentLine(
            document=document,
            position_no=position_no,
            line_type='NORMAL',
            is_selected=True,
            item=item,
            quantity=cls.round_quantity(entry.duration_minutes),
            unit_price_net=Decimal('0.00'),
        )

        # Übernimmt Steuersatz, Rabattfähigkeit und (vorläufig) den Artikelpreis.
        apply_item_snapshot(line, item)

        # Der Projektsatz gewinnt bewusst gegen den Artikelpreis - deshalb erst
        # nach dem Snapshot setzen.
        line.unit_price_net = rate

        # Kurztexte kopiert apply_item_snapshot() laut eigenem Docstring nicht.
        line.short_text_1 = item.short_text_1
        line.short_text_2 = item.short_text_2
        line.description = ' '.join(
            part for part in (item.short_text_1, item.short_text_2) if part
        ) or billing_text
        # Nur die Position bekommt den aufbereiteten Text - ``entry.description``
        # bleibt als Arbeitsnachweis unverändert.
        line.long_text = billing_text
        line.unit = item.unit

        line.discount = (
            (projekt.discount_percent or Decimal('0.00'))
            if line.is_discountable
            else Decimal('0.00')
        )

        # Kostenarten steuern später das Erlöskonto im DATEV-Export.
        line.kostenart1 = item.cost_type_1
        line.kostenart2 = item.cost_type_2

        line.save()
        return line
