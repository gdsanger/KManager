from decimal import Decimal
from datetime import date

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Adresse
from vermietung.models import MietObjekt, Vertrag, VertragsObjekt


class MonthlyRentIncomeViewTests(TestCase):
    """Tests for the monthly rent income overview."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rentuser',
            password='testpass123',
            is_staff=False
        )
        vermietung_group = Group.objects.create(name='Vermietung')
        self.user.groups.add(vermietung_group)

        self.client = Client()
        self.client.login(username='rentuser', password='testpass123')

        self.standort = Adresse.objects.create(
            adressen_type='STANDORT',
            name='Campus',
            strasse='Hauptstrasse 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland'
        )
        self.kunde_active = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Aktiver Kunde',
            strasse='Kundenweg 1',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland'
        )
        self.kunde_inactive = Adresse.objects.create(
            adressen_type='KUNDE',
            name='Inaktiver Kunde',
            strasse='Kundenweg 2',
            plz='12345',
            ort='Musterstadt',
            land='Deutschland'
        )
        self.objekt_a = MietObjekt.objects.create(
            name='Objekt A',
            type='RAUM',
            beschreibung='Büro',
            standort=self.standort,
            mietpreis=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            verfuegbar=True,
            verfuegbare_einheiten=3
        )
        self.objekt_b = MietObjekt.objects.create(
            name='Objekt B',
            type='RAUM',
            beschreibung='Lager',
            standort=self.standort,
            mietpreis=Decimal('200.00'),
            kaution=Decimal('600.00'),
            verfuegbar=True,
            verfuegbare_einheiten=3
        )

    def test_lists_only_active_contracts_for_selected_month(self):
        """Only contracts active in the chosen month are shown."""
        active_contract = Vertrag.objects.create(
            mietobjekt=None,
            mieter=self.kunde_active,
            start=date(2024, 1, 1),
            ende=None,
            miete=Decimal('500.00'),
            kaution=Decimal('1500.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=active_contract,
            mietobjekt=self.objekt_a,
            preis=Decimal('500.00'),
            anzahl=1
        )

        # Contract ended before the requested month
        ended_contract = Vertrag.objects.create(
            mietobjekt=None,
            mieter=self.kunde_inactive,
            start=date(2023, 5, 1),
            ende=date(2024, 2, 28),
            miete=Decimal('300.00'),
            kaution=Decimal('900.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=ended_contract,
            mietobjekt=self.objekt_b,
            preis=Decimal('300.00'),
            anzahl=1
        )

        response = self.client.get(
            reverse('vermietung:mieteinnahmen_monatlich'),
            {'monat': '2024-03'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aktiver Kunde')
        self.assertNotContains(response, 'Inaktiver Kunde')

    def test_month_filter_respects_contract_start(self):
        """Contracts starting after the month are excluded until active."""
        may_contract = Vertrag.objects.create(
            mietobjekt=None,
            mieter=self.kunde_active,
            start=date(2024, 5, 15),
            ende=date(2024, 12, 31),
            miete=Decimal('700.00'),
            kaution=Decimal('2100.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=may_contract,
            mietobjekt=self.objekt_a,
            preis=Decimal('700.00'),
            anzahl=1
        )

        april_response = self.client.get(
            reverse('vermietung:mieteinnahmen_monatlich'),
            {'monat': '2024-04'}
        )
        self.assertNotContains(april_response, 'Aktiver Kunde')

        may_response = self.client.get(
            reverse('vermietung:mieteinnahmen_monatlich'),
            {'monat': '2024-05'}
        )
        self.assertContains(may_response, 'Aktiver Kunde')

    def test_displays_amount_and_object_names(self):
        """Amounts are derived from contract pricing and objects are listed."""
        contract = Vertrag.objects.create(
            mietobjekt=None,
            mieter=self.kunde_active,
            start=date(2024, 5, 1),
            ende=None,
            miete=Decimal('0.00'),
            kaution=Decimal('0.00'),
            status='active'
        )
        VertragsObjekt.objects.create(
            vertrag=contract,
            mietobjekt=self.objekt_a,
            preis=Decimal('500.00'),
            anzahl=2
        )
        VertragsObjekt.objects.create(
            vertrag=contract,
            mietobjekt=self.objekt_b,
            preis=Decimal('200.00'),
            anzahl=1
        )

        response = self.client.get(
            reverse('vermietung:mieteinnahmen_monatlich'),
            {'monat': '2024-05'}
        )

        self.assertContains(response, 'Objekt A (+1 weitere)')
        # Sum from VertragsObjekte: 2*500 + 1*200 = 1200.00
        self.assertContains(response, '1200,00 €')
