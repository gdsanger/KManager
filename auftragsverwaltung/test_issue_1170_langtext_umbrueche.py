"""
Tests für Issue #1170: Zeilenumbrüche im Positions-Langtext.

Der Langtext einer Belegposition wird im Quill-Editor erfasst und als HTML
(pro Zeile ein <p>) gespeichert. Im Rechnungs-PDF muss er zeilengetreu
gedruckt werden — ein Zeilenumbruch darf keinen Absatzabstand erzeugen.

Die Tests messen die tatsächliche Layout-Position der Textzeilen im
WeasyPrint-Box-Baum, prüfen also das gerenderte Ergebnis und nicht nur das
HTML-Markup.
"""

from decimal import Decimal
from datetime import date, timedelta

from django.template.loader import render_to_string
from django.test import TestCase

from auftragsverwaltung.models import SalesDocument, SalesDocumentLine, DocumentType
from auftragsverwaltung.printing import SalesDocumentInvoiceContextBuilder
from core.models import Mandant, Adresse, TaxRate, Unit
from core.printing import get_static_base_url


def _iter_text_boxes(box):
    """Rekursiv alle TextBox-Knoten eines WeasyPrint-Box-Baums liefern."""
    if hasattr(box, 'text'):
        yield box
    for child in getattr(box, 'children', ()):
        yield from _iter_text_boxes(child)


class PositionsLangtextRenderingTest(TestCase):
    """Prüft das PDF-Layout des Positions-Langtextes."""

    LINE_1 = 'Projekt: GDS Hosting Neu / Hetzner'
    LINE_2 = 'Tätigkeit: Backupkontrolle täglich (23 Tage a` ca. 5 min)'

    # Langtext wird mit 8pt bei line-height 1.4 gesetzt -> ca. 14.9px pro Zeile.
    # Der globale p-Abstand aus print.css beträgt 8pt (~10.7px). Ein Wert
    # oberhalb dieser Schwelle bedeutet also: Absatzabstand oder Leerzeile.
    SINGLE_LINE_MAX_DELTA = 18.0

    def setUp(self):
        self.company = Mandant.objects.create(
            name='Test GmbH',
            adresse='Teststraße 1',
            plz='12345',
            ort='Berlin',
            land='Deutschland',
        )
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH',
            name='Max Mustermann',
            strasse='Kundenstraße 10',
            plz='54321',
            ort='Hamburg',
            land='Deutschland',
            country_code='DE',
        )
        self.doc_type = DocumentType.objects.create(
            key='rechnung',
            name='Rechnung',
            prefix='R',
            is_invoice=True,
            requires_due_date=True,
        )
        self.tax_19 = TaxRate.objects.create(
            code='normal', name='Normal 19%', rate=Decimal('0.19')
        )
        self.unit = Unit.objects.create(code='STK', name='Stück', symbol='Stk')

        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-01170',
            status='OPEN',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            subject='Test Rechnung',
            total_net=Decimal('100.00'),
            total_tax=Decimal('19.00'),
            total_gross=Decimal('119.00'),
        )

    def _create_line(self, long_text='', short_text_2=''):
        return SalesDocumentLine.objects.create(
            document=self.document,
            position_no=1,
            line_type='NORMAL',
            is_selected=True,
            short_text_1='Dienstleistung',
            short_text_2=short_text_2,
            long_text=long_text,
            description='Dienstleistung',
            unit=self.unit,
            quantity=Decimal('1.00'),
            unit_price_net=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_net=Decimal('100.00'),
            line_tax=Decimal('19.00'),
            line_gross=Decimal('119.00'),
            tax_rate=self.tax_19,
        )

    def _render_html(self):
        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        return render_to_string(builder.get_template_name(self.document), context)

    def _text_positions(self):
        """Rendert das Dokument und liefert {Textzeile: position_y}."""
        from weasyprint import HTML

        document = HTML(
            string=self._render_html(), base_url=get_static_base_url()
        ).render()

        positions = {}
        for page in document.pages:
            for text_box in _iter_text_boxes(page._page_box):
                text = text_box.text.strip()
                if text:
                    positions.setdefault(text, text_box.position_y)
        return positions

    def _find_position(self, positions, needle):
        for text, position_y in positions.items():
            if needle in text:
                return position_y
        self.fail(f'Textzeile nicht im PDF gefunden: {needle!r}\n'
                  f'Gefunden: {sorted(positions)}')

    def test_zwei_zeilen_ohne_leerzeile(self):
        """Zwei aufeinanderfolgende Quill-Zeilen stehen direkt untereinander."""
        self._create_line(
            long_text=f'<p>{self.LINE_1}</p><p>{self.LINE_2}</p>'
        )

        positions = self._text_positions()
        delta = (self._find_position(positions, 'Tätigkeit:')
                 - self._find_position(positions, 'Projekt:'))

        self.assertGreater(delta, 0, 'Zeilenreihenfolge im PDF ist vertauscht')
        self.assertLess(
            delta, self.SINGLE_LINE_MAX_DELTA,
            f'Zwischen den Langtext-Zeilen liegt ein Absatzabstand '
            f'({delta:.1f}px statt max. {self.SINGLE_LINE_MAX_DELTA}px)'
        )

    def test_zeilenumbrueche_im_quelltext_erzeugen_keinen_zusatzabstand(self):
        """Newlines zwischen den Tags dürfen keinen Leerraum erzeugen."""
        self._create_line(
            long_text=f'<p>{self.LINE_1}</p>\n<p>{self.LINE_2}</p>\n'
        )

        positions = self._text_positions()
        delta = (self._find_position(positions, 'Tätigkeit:')
                 - self._find_position(positions, 'Projekt:'))

        self.assertLess(
            delta, self.SINGLE_LINE_MAX_DELTA,
            f'Quelltext-Newlines erzeugen zusätzlichen Leerraum ({delta:.1f}px)'
        )

    def test_bewusste_leerzeile_bleibt_erhalten(self):
        """Ein bewusst leerer Absatz bleibt im PDF als Leerzeile sichtbar."""
        self._create_line(
            long_text=f'<p>{self.LINE_1}</p><p><br></p><p>{self.LINE_2}</p>'
        )

        positions = self._text_positions()
        delta = (self._find_position(positions, 'Tätigkeit:')
                 - self._find_position(positions, 'Projekt:'))

        self.assertGreater(
            delta, self.SINGLE_LINE_MAX_DELTA,
            f'Die bewusst eingefügte Leerzeile fehlt im PDF ({delta:.1f}px)'
        )

    def test_mehrzeiliger_short_text_2_bricht_weiterhin_um(self):
        """short_text_2 ist Klartext — Newlines müssen erhalten bleiben."""
        self._create_line(short_text_2='Erste Zusatzzeile\nZweite Zusatzzeile')

        positions = self._text_positions()
        delta = (self._find_position(positions, 'Zweite Zusatzzeile')
                 - self._find_position(positions, 'Erste Zusatzzeile'))

        self.assertGreater(
            delta, 0,
            'Mehrzeiliger short_text_2 wird nicht mehr umgebrochen'
        )

    def test_formatierungen_und_listen_bleiben_erhalten(self):
        """Fett/Kursiv/Unterstrichen und Listen werden weiterhin gerendert."""
        self._create_line(
            long_text=(
                '<p><strong>Fett</strong> <em>Kursiv</em> <u>Unterstrichen</u></p>'
                '<ul><li>Punkt eins</li><li>Punkt zwei</li></ul>'
            )
        )

        html = self._render_html()
        self.assertIn('<strong>Fett</strong>', html)
        self.assertIn('<em>Kursiv</em>', html)
        self.assertIn('<u>Unterstrichen</u>', html)
        self.assertIn('<li>Punkt eins</li>', html)

        positions = self._text_positions()
        self._find_position(positions, 'Punkt eins')
        self._find_position(positions, 'Punkt zwei')

    def test_langtext_nutzt_eigene_css_klasse(self):
        """Langtext (HTML) und short_text_2 (Klartext) sind getrennt gescopt."""
        self._create_line(
            long_text=f'<p>{self.LINE_1}</p>',
            short_text_2='Zusatzzeile',
        )

        html = self._render_html()
        self.assertIn(f'<div class="long-text-html"><p>{self.LINE_1}</p></div>', html)
        self.assertIn('<div class="long-text">Zusatzzeile</div>', html)
        self.assertIn('.long-text-html p {', html)


class KopfUndFusstextAbstandTest(TestCase):
    """Kopf-/Fußtext behalten ihren Absatzabstand (keine Regression)."""

    def setUp(self):
        self.company = Mandant.objects.create(
            name='Test GmbH', adresse='Teststraße 1', plz='12345',
            ort='Berlin', land='Deutschland',
        )
        self.customer = Adresse.objects.create(
            firma='Kunde GmbH', name='Max Mustermann', strasse='Kundenstraße 10',
            plz='54321', ort='Hamburg', land='Deutschland', country_code='DE',
        )
        self.doc_type = DocumentType.objects.create(
            key='rechnung', name='Rechnung', prefix='R',
            is_invoice=True, requires_due_date=True,
        )
        self.document = SalesDocument.objects.create(
            company=self.company,
            document_type=self.doc_type,
            customer=self.customer,
            number='R26-01171',
            status='OPEN',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            subject='Test Rechnung',
            header_text='<p>Kopf Absatz eins</p><p>Kopf Absatz zwei</p>',
            footer_text='<p>Fuß Absatz eins</p><p>Fuß Absatz zwei</p>',
            total_net=Decimal('0.00'),
            total_tax=Decimal('0.00'),
            total_gross=Decimal('0.00'),
        )

    def test_kopftext_behaelt_absatzabstand(self):
        from weasyprint import HTML

        builder = SalesDocumentInvoiceContextBuilder()
        context = builder.build_context(self.document)
        html = render_to_string(builder.get_template_name(self.document), context)

        document = HTML(string=html, base_url=get_static_base_url()).render()
        positions = {}
        for page in document.pages:
            for text_box in _iter_text_boxes(page._page_box):
                text = text_box.text.strip()
                if text:
                    positions.setdefault(text, text_box.position_y)

        def find(needle):
            for text, position_y in positions.items():
                if needle in text:
                    return position_y
            self.fail(f'Textzeile nicht im PDF gefunden: {needle!r}')

        # Kopftext: 10pt Schrift (~18.7px Zeilenhöhe) + 8pt Absatzabstand.
        kopf_delta = find('Kopf Absatz zwei') - find('Kopf Absatz eins')
        self.assertGreater(
            kopf_delta, 20.0,
            f'Kopftext hat seinen Absatzabstand verloren ({kopf_delta:.1f}px)'
        )
