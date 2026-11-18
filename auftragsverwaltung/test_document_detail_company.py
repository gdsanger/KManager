"""
Regression: Die Detailansicht muss den Mandanten des Belegs anzeigen
(nicht den ersten verfügbaren Mandanten).
"""
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from auftragsverwaltung.models import DocumentType, SalesDocument
from core.models import Adresse, Mandant


class DocumentDetailCompanyTest(TestCase):
    def setUp(self):
        self.first_company = Mandant.objects.create(
            name='A Erster Mandant', adresse='Str. 1', plz='12345', ort='Stadt'
        )
        self.doc_company = Mandant.objects.create(
            name='Z Beleg Mandant', adresse='Str. 2', plz='12345', ort='Stadt'
        )
        self.customer = Adresse.objects.create(
            name='Kunde', strasse='Weg 1', plz='54321', ort='Ort',
            adressen_type='KUNDE'
        )
        self.invoice_type = DocumentType.objects.get(key='invoice')
        self.document = SalesDocument.objects.create(
            company=self.doc_company,
            document_type=self.invoice_type,
            customer=self.customer,
            number='RC26/00022',
            status='DRAFT',
            issue_date=date(2026, 11, 18),
            due_date=date(2026, 12, 2),
        )
        User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')

    def test_detail_uses_document_company(self):
        url = reverse('auftragsverwaltung:document_detail',
                      kwargs={'doc_key': 'invoice', 'pk': self.document.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['company'], self.doc_company)
