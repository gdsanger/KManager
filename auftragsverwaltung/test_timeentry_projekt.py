"""
Tests für die Projektzuordnung der Zeiterfassung (#1174)

Abgedeckt werden:
- Auftrag ist optional, Kunde bleibt Pflicht
- optionale Projektzuordnung inklusive Kunden-/Mandantenkonsistenz
- Formular, Liste, Filter und Vorbelegung aus dem Projekt heraus
"""
from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from auftragsverwaltung.filters import TimeEntryFilter
from auftragsverwaltung.models import DocumentType, SalesDocument, TimeEntry
from core.models import Adresse, Mandant, Projekt


class TimeEntryProjektTestDataMixin:
    """Gemeinsame Testdaten für Zeiterfassung mit Projektbezug."""

    def create_base_data(self):
        self.company = Mandant.objects.create(
            name="Test Company", adresse="Test Street 1", plz="12345", ort="Test City"
        )
        self.other_company = Mandant.objects.create(
            name="Other Company", adresse="Other Street 1", plz="54321", ort="Other City"
        )
        self.customer = Adresse.objects.create(
            name="Test Customer", strasse="Customer Street 1", plz="54321",
            ort="Customer City", land="Germany", adressen_type="KUNDE"
        )
        self.other_customer = Adresse.objects.create(
            name="Other Customer", strasse="Other Street 1", plz="12345",
            ort="Other City", land="Germany", adressen_type="KUNDE"
        )
        self.order_doc_type, _ = DocumentType.objects.get_or_create(
            key="order",
            defaults={"name": "Auftrag", "prefix": "AB", "is_active": True},
        )
        self.order = SalesDocument.objects.create(
            company=self.company,
            document_type=self.order_doc_type,
            customer=self.customer,
            number="AB26-00001",
            status="DRAFT",
            issue_date=date.today(),
            subject="Test Order",
        )
        self.user = User.objects.create_user(username="testuser", password="testpass")


class TimeEntryOptionalOrderTestCase(TimeEntryProjektTestDataMixin, TestCase):
    """Der Auftrag ist optional, der Kunde bleibt Pflicht."""

    def setUp(self):
        self.create_base_data()

    def test_timeentry_without_order_is_valid(self):
        """Eine Zeiterfassung ohne Auftrag lässt sich speichern."""
        timeentry = TimeEntry(
            company=self.company,
            customer=self.customer,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Leistung ohne Auftrag",
        )

        timeentry.full_clean()
        timeentry.save()

        self.assertIsNone(timeentry.order)
        self.assertIsNone(timeentry.projekt)

    def test_timeentry_without_customer_is_rejected(self):
        """Der Kunde bleibt Pflichtfeld."""
        timeentry = TimeEntry(
            company=self.company,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Leistung ohne Kunde",
        )

        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()

        self.assertIn('customer', cm.exception.error_dict)

    def test_order_validations_still_apply(self):
        """Die bisherigen Auftragsprüfungen greifen unverändert."""
        quote_doc_type, _ = DocumentType.objects.get_or_create(
            key="quote",
            defaults={"name": "Angebot", "prefix": "AN", "is_active": True},
        )
        quote = SalesDocument.objects.create(
            company=self.company,
            document_type=quote_doc_type,
            customer=self.customer,
            number="AN26-00001",
            status="DRAFT",
            issue_date=date.today(),
            subject="Test Quote",
        )

        timeentry = TimeEntry(
            company=self.company,
            customer=self.customer,
            order=quote,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Leistung mit falschem Belegtyp",
        )

        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()

        self.assertIn('order', cm.exception.error_dict)


class TimeEntryProjektValidationTestCase(TimeEntryProjektTestDataMixin, TestCase):
    """Validierung der Projektzuordnung."""

    def setUp(self):
        self.create_base_data()
        self.projekt = Projekt.objects.create(
            titel='Hosting Neu', kunde=self.customer, company=self.company
        )
        self.internes_projekt = Projekt.objects.create(titel='Internes Projekt')

    def _timeentry(self, **overrides):
        defaults = dict(
            company=self.company,
            customer=self.customer,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Test",
        )
        defaults.update(overrides)
        return TimeEntry(**defaults)

    def test_projekt_assignment_is_valid(self):
        """Zeiterfassung mit passendem Projekt ist gültig."""
        timeentry = self._timeentry(projekt=self.projekt)
        timeentry.full_clean()
        timeentry.save()

        self.assertEqual(timeentry.projekt, self.projekt)
        self.assertEqual(list(self.projekt.time_entries.all()), [timeentry])

    def test_projekt_without_kunde_accepts_any_customer(self):
        """Interne Projekte ohne Kunde passen zu jedem Kunden."""
        timeentry = self._timeentry(
            projekt=self.internes_projekt, customer=self.other_customer
        )
        timeentry.full_clean()

    def test_projekt_customer_mismatch_is_rejected(self):
        """Abweichender Kunde am Projekt führt zu einer Validierungsmeldung."""
        timeentry = self._timeentry(projekt=self.projekt, customer=self.other_customer)

        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()

        self.assertIn('projekt', cm.exception.error_dict)
        self.assertIn('Hosting Neu', str(cm.exception.error_dict['projekt']))

    def test_projekt_company_mismatch_is_rejected(self):
        """Abweichender Mandant am Projekt führt zu einer Validierungsmeldung."""
        timeentry = self._timeentry(projekt=self.projekt, company=self.other_company)

        with self.assertRaises(ValidationError) as cm:
            timeentry.full_clean()

        self.assertIn('projekt', cm.exception.error_dict)

    def test_order_and_projekt_can_be_combined(self):
        """Auftrag und Projekt lassen sich ohne künstliche Kopplung kombinieren."""
        projekt_ohne_auftragsbezug = Projekt.objects.create(titel='Sammelprojekt')

        timeentry = self._timeentry(
            order=self.order, projekt=projekt_ohne_auftragsbezug
        )
        timeentry.full_clean()
        timeentry.save()

        self.assertEqual(timeentry.order, self.order)
        self.assertEqual(timeentry.projekt, projekt_ohne_auftragsbezug)

    def test_get_duration_display(self):
        """Dauer-Formatierung ist zentral am Modell verfügbar."""
        self.assertEqual(self._timeentry(duration_minutes=90).get_duration_display(), '1h 30min')
        self.assertEqual(self._timeentry(duration_minutes=120).get_duration_display(), '2h')
        self.assertEqual(self._timeentry(duration_minutes=45).get_duration_display(), '45min')


class TimeEntryProjektViewTestCase(TimeEntryProjektTestDataMixin, TestCase):
    """Formular, Liste und Vorbelegung aus dem Projekt."""

    def setUp(self):
        self.create_base_data()
        self.projekt = Projekt.objects.create(
            titel='Hosting Neu', kunde=self.customer, company=self.other_company
        )
        self.client.login(username="testuser", password="testpass")

    def test_create_form_order_is_not_required(self):
        """Das Auftragsfeld ist im Formular nicht mehr als Pflichtfeld markiert."""
        response = self.client.get(reverse('auftragsverwaltung:timeentry_create'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="order_id"', content)
        self.assertNotIn('name="order_id" required', content)
        self.assertIn('-- Kein Auftrag --', content)
        self.assertIn('-- Kein Projekt --', content)

    def test_create_without_order_succeeds(self):
        """Eine Zeiterfassung ohne Auftrag lässt sich über das Formular anlegen."""
        response = self.client.post(
            reverse('auftragsverwaltung:timeentry_create'),
            {
                'company_id': self.company.id,
                'customer_id': self.customer.id,
                'order_id': '',
                'projekt_id': '',
                'performed_by_id': self.user.id,
                'service_date': date.today().strftime('%Y-%m-%d'),
                'duration_minutes': 45,
                'description': 'Leistung ohne Auftrag',
            },
        )

        timeentry = TimeEntry.objects.get()
        self.assertRedirects(
            response,
            reverse('auftragsverwaltung:timeentry_detail', kwargs={'pk': timeentry.pk}),
        )
        self.assertIsNone(timeentry.order)

    def test_create_with_projekt_succeeds(self):
        """Die Projektzuordnung wird aus dem Formular übernommen."""
        self.client.post(
            reverse('auftragsverwaltung:timeentry_create'),
            {
                'company_id': self.other_company.id,
                'customer_id': self.customer.id,
                'projekt_id': self.projekt.id,
                'performed_by_id': self.user.id,
                'service_date': date.today().strftime('%Y-%m-%d'),
                'duration_minutes': 30,
                'description': 'Projektarbeit',
            },
        )

        timeentry = TimeEntry.objects.get()
        self.assertEqual(timeentry.projekt, self.projekt)

        # Die Detailansicht zeigt das Projekt und verlinkt es
        detail = self.client.get(
            reverse('auftragsverwaltung:timeentry_detail', kwargs={'pk': timeentry.pk})
        )
        self.assertContains(detail, 'Hosting Neu')
        self.assertContains(detail, reverse('projekt_detail', kwargs={'pk': self.projekt.pk}))

    def test_create_form_prefilled_from_projekt(self):
        """?projekt=<pk> belegt Projekt, Kunde und Mandant vor."""
        response = self.client.get(
            f"{reverse('auftragsverwaltung:timeentry_create')}?projekt={self.projekt.pk}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['default_projekt'], self.projekt)
        self.assertEqual(response.context['default_customer'], self.customer)
        self.assertEqual(response.context['default_company'], self.other_company)

    def test_update_can_clear_order_and_projekt(self):
        """Eine leere Auswahl entfernt bestehende Auftrags-/Projektzuordnungen."""
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            order=self.order,
            projekt=Projekt.objects.create(titel='Altes Projekt'),
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Initial",
        )

        self.client.post(
            reverse('auftragsverwaltung:timeentry_update', kwargs={'pk': timeentry.pk}),
            {
                'company_id': self.company.id,
                'customer_id': self.customer.id,
                'order_id': '',
                'projekt_id': '',
                'performed_by_id': self.user.id,
                'service_date': date.today().strftime('%Y-%m-%d'),
                'duration_minutes': 60,
                'description': 'Ohne Zuordnung',
            },
        )

        timeentry.refresh_from_db()
        self.assertIsNone(timeentry.order)
        self.assertIsNone(timeentry.projekt)

    def test_completed_projekt_stays_selectable_when_assigned(self):
        """Ein abgeschlossenes Projekt bleibt im Bearbeiten-Formular wählbar."""
        abgeschlossen = Projekt.objects.create(
            titel='Abgeschlossenes Projekt', status='ABGESCHLOSSEN'
        )
        timeentry = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            projekt=abgeschlossen,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Initial",
        )

        response = self.client.get(
            reverse('auftragsverwaltung:timeentry_update', kwargs={'pk': timeentry.pk})
        )

        self.assertIn(abgeschlossen, list(response.context['projekte']))

        create_response = self.client.get(reverse('auftragsverwaltung:timeentry_create'))
        self.assertNotIn(abgeschlossen, list(create_response.context['projekte']))

    def test_list_shows_projekt_column(self):
        """Die Liste zeigt eine Projekt-Spalte, leerer Auftrag erscheint als Strich."""
        TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            projekt=self.projekt,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Projektarbeit",
        )

        response = self.client.get(reverse('auftragsverwaltung:timeentry_list'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Projekt', content)
        self.assertIn('Hosting Neu', content)
        self.assertIn('—', content)

    def test_list_does_not_add_queries_per_projekt(self):
        """Die Projekt-Spalte erzeugt keine zusätzliche Abfrage pro Zeile."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = reverse('auftragsverwaltung:timeentry_list')

        def add_entries(count, prefix):
            for index in range(count):
                TimeEntry.objects.create(
                    company=self.company,
                    customer=self.customer,
                    projekt=Projekt.objects.create(
                        titel=f'{prefix} {index}', kunde=self.customer
                    ),
                    performed_by=self.user,
                    service_date=date.today(),
                    duration_minutes=60,
                    description=f'{prefix} {index}',
                )

        add_entries(1, 'Einzeln')
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(url)

        add_entries(9, 'Weitere')
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)

        self.assertEqual(len(many.captured_queries), len(baseline.captured_queries))


class TimeEntryProjektFilterTestCase(TimeEntryProjektTestDataMixin, TestCase):
    """Filter und Volltextsuche über den Projekttitel."""

    def setUp(self):
        self.create_base_data()
        self.projekt = Projekt.objects.create(titel='GDS Hosting Neu', kunde=self.customer)
        self.entry_mit_projekt = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            projekt=self.projekt,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=60,
            description="Projektarbeit",
        )
        self.entry_ohne_projekt = TimeEntry.objects.create(
            company=self.company,
            customer=self.customer,
            performed_by=self.user,
            service_date=date.today(),
            duration_minutes=30,
            description="Sonstige Arbeit",
        )

    def test_filter_by_projekt(self):
        """Der Projektfilter grenzt auf Einträge des Projekts ein."""
        filter_set = TimeEntryFilter(
            {'projekt': str(self.projekt.pk)}, queryset=TimeEntry.objects.all()
        )

        self.assertEqual(list(filter_set.qs), [self.entry_mit_projekt])

    def test_search_finds_entries_by_projekt_title(self):
        """Die Volltextsuche findet Einträge über den Projekttitel."""
        filter_set = TimeEntryFilter({'q': 'Hosting'}, queryset=TimeEntry.objects.all())

        self.assertEqual(list(filter_set.qs), [self.entry_mit_projekt])
