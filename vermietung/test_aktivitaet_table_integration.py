"""
Integration test for HTML table support in Aktivitaet form.

This test verifies the complete flow:
1. Creating an Aktivitaet with table HTML via form
2. Saving to database
3. Loading from database
4. Verifying table HTML is preserved
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from vermietung.models import Aktivitaet
from vermietung.forms import AktivitaetForm

User = get_user_model()


class AktivitaetTableIntegrationTest(TestCase):
    """Integration test for table HTML in Aktivitaet descriptions"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_create_aktivitaet_with_table_html_via_form(self):
        """Test creating an Aktivitaet with table HTML via form"""
        table_html = '''<p>Test table from email:</p>
<table>
<tbody>
<tr><th>Header A</th><th>Header B</th></tr>
<tr><td>Value 1</td><td>Value 2</td></tr>
<tr><td>Value 3</td><td>Value 4</td></tr>
</tbody>
</table>
<p>Additional text after table.</p>'''

        form = AktivitaetForm(data={
            'titel': 'Test Activity with Table',
            'beschreibung': table_html,
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }, current_user=self.user)

        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        aktivitaet = form.save()

        # Verify the Aktivitaet was created
        self.assertIsNotNone(aktivitaet)
        self.assertIsNotNone(aktivitaet.id)

        # Verify table HTML is preserved in database
        self.assertIn('<table>', aktivitaet.beschreibung)
        self.assertIn('<tbody>', aktivitaet.beschreibung)
        self.assertIn('<th>Header A</th>', aktivitaet.beschreibung)
        self.assertIn('<td>Value 1</td>', aktivitaet.beschreibung)

    def test_update_aktivitaet_with_table_html_via_form(self):
        """Test updating an existing Aktivitaet to add table HTML"""
        # Create initial Aktivitaet
        aktivitaet = Aktivitaet.objects.create(
            titel='Test Activity',
            beschreibung='<p>Original text</p>',
            status='OFFEN',
            prioritaet='NORMAL',
            ersteller=self.user
        )

        table_html = '''<p>Updated with table:</p>
<table>
<thead>
<tr><th>Column 1</th><th>Column 2</th></tr>
</thead>
<tbody>
<tr><td colspan="2">Merged cell</td></tr>
<tr><td>Cell A</td><td>Cell B</td></tr>
</tbody>
</table>'''

        form = AktivitaetForm(data={
            'titel': 'Test Activity',
            'beschreibung': table_html,
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }, instance=aktivitaet, current_user=self.user)

        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        aktivitaet = form.save()

        # Reload from database
        aktivitaet.refresh_from_db()

        # Verify table HTML is preserved
        self.assertIn('<table>', aktivitaet.beschreibung)
        self.assertIn('<thead>', aktivitaet.beschreibung)
        self.assertIn('<tbody>', aktivitaet.beschreibung)
        self.assertIn('colspan="2"', aktivitaet.beschreibung)
        self.assertIn('<th>Column 1</th>', aktivitaet.beschreibung)

    def test_table_html_preserved_after_reload(self):
        """Test that table HTML survives save/reload cycle via form"""
        table_html = '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>'

        # Create via form to trigger sanitization
        form = AktivitaetForm(data={
            'titel': 'Table Test',
            'beschreibung': table_html,
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }, current_user=self.user)

        self.assertTrue(form.is_valid())
        aktivitaet = form.save()
        original_id = aktivitaet.id

        # Clear the instance from memory
        del aktivitaet

        # Reload from database
        aktivitaet = Aktivitaet.objects.get(id=original_id)

        # Verify table HTML is exactly as saved
        self.assertIn('<table>', aktivitaet.beschreibung)
        self.assertIn('<th>A</th>', aktivitaet.beschreibung)
        self.assertIn('<td>1</td>', aktivitaet.beschreibung)

    def test_dangerous_html_removed_from_table(self):
        """Test that dangerous attributes are sanitized from table HTML via form"""
        dangerous_table = '''<table onclick="alert('xss')">
<tr><td onmouseover="alert('xss2')">Cell</td></tr>
</table>
<script>alert('xss3')</script>'''

        # Use form to sanitize (forms apply sanitization)
        form = AktivitaetForm(data={
            'titel': 'Dangerous Table Test',
            'beschreibung': dangerous_table,
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }, current_user=self.user)

        self.assertTrue(form.is_valid())
        aktivitaet = form.save()

        # Verify table structure is preserved
        self.assertIn('<table>', aktivitaet.beschreibung)
        self.assertIn('<td>Cell</td>', aktivitaet.beschreibung)

        # Verify dangerous attributes and tags are removed
        self.assertNotIn('onclick', aktivitaet.beschreibung)
        self.assertNotIn('onmouseover', aktivitaet.beschreibung)
        self.assertNotIn('<script>', aktivitaet.beschreibung)
        # Note: bleach strips tags but keeps text content, so "alert" text may remain

    def test_complex_table_from_email_example(self):
        """Test the exact scenario from the bug report"""
        # This is the example from the bug report
        email_table = '''<table>
  <tbody><tr><th>A</th><th>B</th></tr>
  <tr><td>1</td><td>2</td></tr>
</tbody></table>'''

        form = AktivitaetForm(data={
            'titel': 'Email Table Test',
            'beschreibung': email_table,
            'status': 'OFFEN',
            'prioritaet': 'NORMAL',
        }, current_user=self.user)

        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        aktivitaet = form.save()

        # Reload from database
        aktivitaet.refresh_from_db()

        # Verify the exact table structure is preserved
        self.assertIn('<table>', aktivitaet.beschreibung)
        self.assertIn('<tbody>', aktivitaet.beschreibung)
        self.assertIn('<tr>', aktivitaet.beschreibung)
        self.assertIn('<th>A</th>', aktivitaet.beschreibung)
        self.assertIn('<th>B</th>', aktivitaet.beschreibung)
        self.assertIn('<td>1</td>', aktivitaet.beschreibung)
        self.assertIn('<td>2</td>', aktivitaet.beschreibung)

