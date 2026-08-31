"""
Tests für den Stammdatenexport der Personenkonten.

Deckt Service (Auswahl je Kontoart, Feldabbildung, Fehlerliste, Zeichensatz,
Dateiname) und Oberfläche (Vorschau, Download, Leerzustand) ab.
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Adresse
from finanzen.forms import PartnerExportForm
from finanzen.services import partner_export as service


def _address(**overrides):
    """Adresse mit Pflichtfeldern anlegen; Personenkonto explizit steuerbar."""
    data = {
        'adressen_type': 'KUNDE',
        'name': 'Müller',
        'strasse': 'Hauptstraße 1',
        'plz': '12345',
        'ort': 'Stadt',
        'land': 'Deutschland',
    }
    data.update(overrides)
    return Adresse.objects.create(**data)


def _address_without_account(**overrides):
    """
    Adresse ohne Personenkonto anlegen.

    `Adresse.save()` vergibt bei der Neuanlage automatisch ein Personenkonto;
    für den Fehlerfall wird es deshalb per UPDATE wieder entfernt – so
    entstehen dieselben Datenstände wie bei importierten Altadressen.
    """
    address = _address(**overrides)
    Adresse.objects.filter(pk=address.pk).update(debitor_number=None)
    address.refresh_from_db()
    return address


class PartnerPreviewSelectionTests(TestCase):
    """Grundmenge und Sortierung je Auswahl."""

    def setUp(self):
        self.customer = _address(name='Kunde A', debitor_number='10500')
        self.customer_2 = _address(name='Kunde B', debitor_number='10100')
        self.supplier = _address(
            adressen_type='LIEFERANT', name='Lieferant', debitor_number='70100',
        )
        # Übrige Adresstypen führen kein Personenkonto.
        _address(adressen_type='Adresse', name='Nur Adresse')
        _address(adressen_type='STANDORT', name='Standort')
        _address(adressen_type='SONSTIGES', name='Sonstiges')

    def test_debtors_only(self):
        preview = service.build_partner_preview(service.DEBTOR)
        self.assertEqual([p.account for p in preview.partners], ['10100', '10500'])
        self.assertEqual(preview.debtor_count, 2)
        self.assertEqual(preview.creditor_count, 0)
        self.assertFalse(preview.problems)

    def test_creditors_only(self):
        preview = service.build_partner_preview(service.CREDITOR)
        self.assertEqual([p.account for p in preview.partners], ['70100'])
        self.assertEqual(preview.creditor_count, 1)
        self.assertEqual(preview.debtor_count, 0)

    def test_both_sorted_by_account(self):
        preview = service.build_partner_preview(service.BOTH)
        self.assertEqual(
            [p.account for p in preview.partners], ['10100', '10500', '70100'],
        )
        self.assertEqual(preview.partner_count, 3)

    def test_other_address_types_are_never_included(self):
        names = set()
        for kind in (service.DEBTOR, service.CREDITOR, service.BOTH):
            preview = service.build_partner_preview(kind)
            names.update(p.address.name for p in preview.partners)
            names.update(p.name for p in preview.problems)
        self.assertNotIn('Nur Adresse', names)
        self.assertNotIn('Standort', names)
        self.assertNotIn('Sonstiges', names)

    def test_default_is_both(self):
        self.assertEqual(service.build_partner_preview().kind, service.BOTH)


class PartnerProblemTests(TestCase):
    """Adressen, die nicht exportiert werden können."""

    def test_address_without_account_is_reported_and_not_exported(self):
        _address_without_account(name='Ohne Konto')

        preview = service.build_partner_preview(service.DEBTOR)

        self.assertEqual(preview.partners, [])
        self.assertTrue(preview.has_problems)
        problem = preview.problems[0]
        self.assertEqual(problem.account, '')
        self.assertEqual(problem.name, 'Ohne Konto')
        self.assertIn('ohne Personenkonto', problem.message)

        content = service.render_partner_csv(preview).decode(service.ENCODING)
        self.assertNotIn('Ohne Konto', content)

    def test_customer_with_creditor_account_is_reported(self):
        _address(name='Falscher Bereich', debitor_number='70001')

        preview = service.build_partner_preview(service.DEBTOR)

        self.assertEqual(preview.partners, [])
        self.assertIn('außerhalb', preview.problems[0].message)
        self.assertEqual(preview.problems[0].account_kind, 'Debitor')

    def test_supplier_with_debtor_account_is_reported(self):
        _address(
            adressen_type='LIEFERANT', name='Falscher Bereich',
            debitor_number='10001',
        )

        preview = service.build_partner_preview(service.CREDITOR)

        self.assertEqual(preview.partners, [])
        self.assertIn('außerhalb', preview.problems[0].message)
        self.assertEqual(preview.problems[0].account_kind, 'Kreditor')

    def test_non_numeric_legacy_account_is_reported(self):
        _address(name='Altdaten', debitor_number='DEB26-00001')

        preview = service.build_partner_preview(service.DEBTOR)

        self.assertEqual(preview.partners, [])
        self.assertIn('numerisch', preview.problems[0].message)

    def test_rendering_does_not_abort_on_problems(self):
        _address_without_account(name='Ohne Konto')
        _address(name='Mit Konto', debitor_number='10001')

        preview = service.build_partner_preview(service.DEBTOR)
        content = service.render_partner_csv(preview).decode(service.ENCODING)

        self.assertTrue(preview.has_problems)
        self.assertIn('Mit Konto', content)
        self.assertNotIn('Ohne Konto', content)


class PartnerCsvTests(TestCase):
    """Aufbau und Inhalt der Datei."""

    def _rows(self, preview):
        content = service.render_partner_csv(preview).decode(service.ENCODING)
        return [
            line.split(service.DELIMITER)
            for line in content.split(service.LINE_ENDING)
            if line
        ]

    def test_header_row_matches_columns(self):
        preview = service.build_partner_preview(service.BOTH)
        rows = self._rows(preview)
        self.assertEqual(rows[0], [f'"{c}"' for c in service.PARTNER_COLUMNS])

    def test_field_mapping(self):
        _address(
            firma='Müller GmbH', name='Anna Müller', anrede='FRAU',
            debitor_number='10042', strasse='Bäckergasse 3', plz='80331',
            ort='München', land='Deutschland', country_code='DE',
            vat_id='DE123456789', is_eu=True, is_business=True,
            email='info@example.com', invoice_email='rechnung@example.com',
            telefon='089 123', mobil='0170 456',
        )

        rows = self._rows(service.build_partner_preview(service.DEBTOR))
        row = dict(zip(service.PARTNER_COLUMNS, [v.strip('"') for v in rows[1]]))

        self.assertEqual(row['Konto'], '10042')
        self.assertEqual(row['Kontoart'], 'Debitor')
        self.assertEqual(row['Adressattyp'], 'Unternehmen')
        self.assertEqual(row['Firma'], 'Müller GmbH')
        self.assertEqual(row['Name'], 'Anna Müller')
        self.assertEqual(row['Anrede'], 'Frau')
        self.assertEqual(row['Straße'], 'Bäckergasse 3')
        self.assertEqual(row['PLZ'], '80331')
        self.assertEqual(row['Ort'], 'München')
        self.assertEqual(row['Land'], 'Deutschland')
        self.assertEqual(row['Ländercode'], 'DE')
        self.assertEqual(row['USt-IdNr.'], 'DE123456789')
        self.assertEqual(row['EU'], 'ja')
        self.assertEqual(row['E-Mail'], 'info@example.com')
        self.assertEqual(row['E-Mail Rechnung'], 'rechnung@example.com')
        self.assertEqual(row['Telefon'], '089 123')
        self.assertEqual(row['Mobil'], '0170 456')

    def test_private_person_and_non_eu_are_readable_text(self):
        _address(name='Privat', debitor_number='10001', is_business=False, is_eu=False)

        rows = self._rows(service.build_partner_preview(service.DEBTOR))
        row = dict(zip(service.PARTNER_COLUMNS, [v.strip('"') for v in rows[1]]))

        self.assertEqual(row['Adressattyp'], 'natürliche Person')
        self.assertEqual(row['EU'], 'nein')
        self.assertNotIn('True', rows[1])
        self.assertNotIn('False', rows[1])

    def test_matchkey_is_not_exported(self):
        _address(firma='Beispiel AG', name='Chef', debitor_number='10001')

        content = service.render_partner_csv(
            service.build_partner_preview(service.DEBTOR),
        ).decode(service.ENCODING)

        self.assertNotIn('Beispiel AG (Chef)', content)
        self.assertIn('"Beispiel AG";"Chef"', content)

    def test_empty_fields_stay_empty(self):
        _address(
            name='Minimal', debitor_number='10001', firma=None, anrede=None,
            vat_id=None, email=None, invoice_email=None, telefon=None, mobil=None,
        )

        rows = self._rows(service.build_partner_preview(service.DEBTOR))
        row = dict(zip(service.PARTNER_COLUMNS, [v.strip('"') for v in rows[1]]))

        for column in ('Firma', 'Anrede', 'USt-IdNr.', 'E-Mail',
                       'E-Mail Rechnung', 'Telefon', 'Mobil'):
            self.assertEqual(row[column], '', column)
        self.assertNotIn('None', rows[1])

    def test_umlauts_survive_the_encoding(self):
        _address(firma='Grün & Söhne GmbH', name='Jäger', debitor_number='10001',
                 ort='Osnabrück')

        raw = service.render_partner_csv(service.build_partner_preview(service.DEBTOR))

        self.assertIsInstance(raw, bytes)
        decoded = raw.decode('cp1252')
        self.assertIn('Grün & Söhne GmbH', decoded)
        self.assertIn('Osnabrück', decoded)
        # Nicht als UTF-8 kodiert: der Umlaut belegt in cp1252 genau ein Byte.
        self.assertIn('ü'.encode('cp1252'), raw)

    def test_leading_zeros_are_preserved(self):
        _address(name='Führende Null', debitor_number='010001')

        rows = self._rows(service.build_partner_preview(service.DEBTOR))

        self.assertEqual(rows[1][0], '"010001"')

    def test_line_ending_is_crlf(self):
        _address(name='Kunde', debitor_number='10001')

        raw = service.render_partner_csv(service.build_partner_preview(service.DEBTOR))

        self.assertTrue(raw.endswith(b'\r\n'))
        self.assertEqual(raw.count(b'\r\n'), 2)  # Kopfzeile + eine Datenzeile

    def test_delimiter_in_text_does_not_break_the_row(self):
        _address(firma='Meier; Schulze GbR', name='Kunde', debitor_number='10001')

        rows = self._rows(service.build_partner_preview(service.DEBTOR))

        self.assertEqual(len(rows[1]), len(service.PARTNER_COLUMNS))
        self.assertIn('"Meier Schulze GbR"', rows[1])

    def test_empty_stock_renders_only_the_header(self):
        preview = service.build_partner_preview(service.BOTH)

        rows = self._rows(preview)

        self.assertEqual(preview.partner_count, 0)
        self.assertEqual(len(rows), 1)


class PartnerFilenameTests(TestCase):

    def _name(self, kind):
        preview = service.PartnerExportPreview(kind=kind)
        return service.build_partner_filename(preview, created_at=date(2026, 8, 31))

    def test_filename_per_selection(self):
        self.assertEqual(self._name(service.DEBTOR), 'Personenkonten_Debitoren_20260831.csv')
        self.assertEqual(self._name(service.CREDITOR), 'Personenkonten_Kreditoren_20260831.csv')
        self.assertEqual(self._name(service.BOTH), 'Personenkonten_20260831.csv')


class PartnerExportViewTests(TestCase):
    """Oberfläche: Vorschau per GET, Download per POST."""

    def setUp(self):
        self.user = User.objects.create_user('tester', password='pw12345678')
        self.client.login(username='tester', password='pw12345678')
        self.customer = _address(name='Kunde', debitor_number='10001')
        self.supplier = _address(
            adressen_type='LIEFERANT', name='Lieferant', debitor_number='70001',
        )

    def test_preview_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('auftragsverwaltung:partner_export'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_preview_without_parameters_shows_both(self):
        response = self.client.get(reverse('auftragsverwaltung:partner_export'))

        self.assertEqual(response.status_code, 200)
        preview = response.context['preview']
        self.assertEqual(preview.kind, service.BOTH)
        self.assertEqual(preview.debtor_count, 1)
        self.assertEqual(preview.creditor_count, 1)

    def test_preview_selection_via_get(self):
        response = self.client.get(
            reverse('auftragsverwaltung:partner_export'), {'kind': service.CREDITOR},
        )

        preview = response.context['preview']
        self.assertEqual(preview.creditor_count, 1)
        self.assertEqual(preview.debtor_count, 0)

    def test_preview_lists_problems(self):
        _address_without_account(name='Ohne Konto')

        response = self.client.get(reverse('auftragsverwaltung:partner_export'))

        self.assertEqual(len(response.context['preview'].problems), 1)
        self.assertContains(response, 'Ohne Konto')

    def test_download_delivers_csv(self):
        response = self.client.post(
            reverse('auftragsverwaltung:partner_export_download'),
            {'kind': service.DEBTOR},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('windows-1252', response['Content-Type'])
        self.assertIn('Personenkonten_Debitoren_', response['Content-Disposition'])
        content = response.content.decode(service.ENCODING)
        self.assertIn('"Konto";"Kontoart"', content)
        self.assertIn('"10001"', content)
        self.assertNotIn('"70001"', content)

    def test_download_changes_no_data_and_is_repeatable(self):
        url = reverse('auftragsverwaltung:partner_export_download')

        first = self.client.post(url, {'kind': service.BOTH})
        before = list(
            Adresse.objects.order_by('pk').values_list('pk', 'debitor_number'),
        )
        second = self.client.post(url, {'kind': service.BOTH})

        self.assertEqual(first.content, second.content)
        self.assertEqual(
            before,
            list(Adresse.objects.order_by('pk').values_list('pk', 'debitor_number')),
        )

    def test_download_without_partners_shows_empty_state(self):
        Adresse.objects.all().delete()

        response = self.client.post(
            reverse('auftragsverwaltung:partner_export_download'),
            {'kind': service.BOTH},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Content-Disposition', response)
        self.assertContains(response, 'Keine Adressen mit Personenkonto')

    def test_download_rejects_get(self):
        response = self.client.get(
            reverse('auftragsverwaltung:partner_export_download'),
        )

        self.assertRedirects(
            response, reverse('auftragsverwaltung:partner_export'),
        )

    def test_form_defaults_to_both(self):
        self.assertEqual(PartnerExportForm().fields['kind'].initial, service.BOTH)
