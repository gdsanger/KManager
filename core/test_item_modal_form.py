"""
Tests for the item edit modal: cost type preselection/filtering and long text.

Covers the modal partial (item_edit_ajax / item_new_ajax), the HTMX endpoint
for the Kostenart 2 options and the round trip of the Quill long text through
item_save_ajax.
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.forms import ItemForm
from core.models import Item, ItemGroup, Kostenart, TaxRate


class ItemModalFormTestCase(TestCase):
    """Tests for the AJAX loaded item form in the modal"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        self.tax_rate = TaxRate.objects.create(code="VAT19", name="19%", rate=Decimal("0.19"))
        self.main_group = ItemGroup.objects.create(code="MG", name="Hauptgruppe", group_type="MAIN")
        self.item_group = ItemGroup.objects.create(
            code="SG", name="Untergruppe", group_type="SUB", parent=self.main_group
        )

        self.personal = Kostenart.objects.create(name="Personal")
        self.material = Kostenart.objects.create(name="Material")
        # Hauptkostenart without any children
        self.sonstiges = Kostenart.objects.create(name="Sonstiges")

        self.gehaelter = Kostenart.objects.create(name="Gehälter", parent=self.personal)
        self.sozialversicherung = Kostenart.objects.create(
            name="Sozialversicherung", parent=self.personal
        )
        self.rohstoffe = Kostenart.objects.create(name="Rohstoffe", parent=self.material)

        self.item = Item.objects.create(
            article_no="A-1000",
            short_text_1="Testartikel",
            net_price=Decimal("100.00"),
            purchase_price=Decimal("50.00"),
            tax_rate=self.tax_rate,
            cost_type_1=self.personal,
            cost_type_2=self.gehaelter,
            item_group=self.item_group,
            item_type='MATERIAL',
            long_text='<p><strong>Fett</strong> und <em>kursiv</em></p>',
        )

    # ------------------------------------------------------------------
    # Preselection of the saved cost types
    # ------------------------------------------------------------------
    def test_edit_form_preselects_both_cost_types(self):
        """Saved cost_type_1 and cost_type_2 are marked as selected"""
        response = self.client.get(reverse('item_edit_ajax', args=[self.item.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<option value="{self.personal.pk}" selected>', html=False)
        self.assertContains(response, f'<option value="{self.gehaelter.pk}" selected>', html=False)

    def test_edit_form_has_no_hand_built_cost_type_1_select(self):
        """cost_type_1 is rendered by Django, including its HTMX attributes"""
        response = self.client.get(reverse('item_edit_ajax', args=[self.item.pk]))
        content = response.content.decode('utf-8')

        self.assertIn('hx-get="%s"' % reverse('cost_type_2_options'), content)
        self.assertIn('hx-target="#cost-type-2-wrapper"', content)
        self.assertIn('hx-swap="outerHTML"', content)

    def test_partial_does_not_load_libraries_or_scripts(self):
        """HTMX and Quill are loaded globally, the partial must not re-include them"""
        response = self.client.get(reverse('item_edit_ajax', args=[self.item.pk]))
        content = response.content.decode('utf-8')

        self.assertNotIn('<script', content)
        self.assertNotIn('quill.js', content)
        self.assertNotIn('htmx.org', content)

    def test_new_form_has_empty_and_disabled_cost_type_2(self):
        """Without cost_type_1 the cost_type_2 field is empty and not selectable"""
        response = self.client.get(reverse('item_new_ajax'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].fields['cost_type_2'].queryset.count(), 0)
        self.assertIn('disabled', content)

    # ------------------------------------------------------------------
    # HTMX endpoint for the cost_type_2 options
    # ------------------------------------------------------------------
    def test_options_endpoint_returns_children_of_selected_hauptkostenart(self):
        response = self.client.get(
            reverse('cost_type_2_options'), {'cost_type_1': self.personal.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gehälter')
        self.assertContains(response, 'Sozialversicherung')
        self.assertNotContains(response, 'Rohstoffe')
        self.assertNotContains(response, 'disabled')

    def test_options_endpoint_for_hauptkostenart_without_children(self):
        """A Hauptkostenart without Unterkostenarten yields an empty but usable select"""
        response = self.client.get(
            reverse('cost_type_2_options'), {'cost_type_1': self.sonstiges.pk}
        )
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="cost-type-2-wrapper"', content)
        self.assertNotIn('Gehälter', content)
        self.assertNotIn('Rohstoffe', content)
        self.assertNotIn('disabled', content)

    def test_options_endpoint_without_selection_is_disabled(self):
        response = self.client.get(reverse('cost_type_2_options'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="cost-type-2-wrapper"', content)
        self.assertIn('disabled', content)

    def test_options_endpoint_drops_previous_selection(self):
        """Switching Kostenart 1 must not keep a now invalid Kostenart 2 selected"""
        response = self.client.get(
            reverse('cost_type_2_options'), {'cost_type_1': self.material.pk}
        )
        content = response.content.decode('utf-8')

        # Only the empty option is preselected, none of the Unterkostenarten
        self.assertIn('<option value="" selected>', content)
        self.assertNotIn(f'<option value="{self.rohstoffe.pk}" selected>', content)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------
    def _post_data(self, **overrides):
        data = {
            'item_id': self.item.pk,
            'article_no': self.item.article_no,
            'short_text_1': self.item.short_text_1,
            'net_price': '100.00',
            'purchase_price': '50.00',
            'tax_rate': self.tax_rate.pk,
            'cost_type_1': self.personal.pk,
            'cost_type_2': self.gehaelter.pk,
            'item_group': self.item_group.pk,
            'item_type': 'MATERIAL',
            'long_text': self.item.long_text,
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_save_with_matching_cost_types(self):
        response = self.client.post(
            reverse('item_save'), self._post_data(cost_type_2=self.sozialversicherung.pk)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.item.refresh_from_db()
        self.assertEqual(self.item.cost_type_1, self.personal)
        self.assertEqual(self.item.cost_type_2, self.sozialversicherung)

    def test_save_rejects_mismatching_cost_types(self):
        response = self.client.post(
            reverse('item_save'),
            self._post_data(cost_type_1=self.material.pk, cost_type_2=self.gehaelter.pk),
        )

        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('cost_type_2', data['errors'])

        self.item.refresh_from_db()
        self.assertEqual(self.item.cost_type_1, self.personal)

    def test_save_new_item_with_cost_types_and_long_text_in_one_go(self):
        """A new item can be created with both cost types and a long text at once"""
        data = self._post_data(
            item_id='',
            article_no='A-2000',
            cost_type_1=self.material.pk,
            cost_type_2=self.rohstoffe.pk,
            long_text='<p>Neuer <u>Langtext</u></p>',
        )

        response = self.client.post(reverse('item_save'), data)

        self.assertTrue(response.json()['success'], response.json())
        new_item = Item.objects.get(article_no='A-2000')
        self.assertEqual(new_item.cost_type_1, self.material)
        self.assertEqual(new_item.cost_type_2, self.rohstoffe)
        self.assertIn('<u>Langtext</u>', new_item.long_text)

    # ------------------------------------------------------------------
    # Long text round trip
    # ------------------------------------------------------------------
    def test_long_text_survives_save_and_reopen(self):
        html = '<p><strong>Fett</strong></p><ul><li>Punkt</li></ul>'

        response = self.client.post(reverse('item_save'), self._post_data(long_text=html))
        self.assertTrue(response.json()['success'])

        self.item.refresh_from_db()
        self.assertEqual(self.item.long_text, html)

        # Reopening the modal delivers the stored HTML back into the hidden field
        response = self.client.get(reverse('item_edit_ajax', args=[self.item.pk]))
        self.assertEqual(response.context['form'].initial['long_text'], html)
        self.assertContains(response, '&lt;strong&gt;Fett&lt;/strong&gt;')

    def test_long_text_is_sanitized(self):
        """Script tags from pasted content never reach the database"""
        response = self.client.post(
            reverse('item_save'),
            self._post_data(long_text='<p>ok</p><script>alert(1)</script>'),
        )
        self.assertTrue(response.json()['success'])

        self.item.refresh_from_db()
        self.assertNotIn('<script>', self.item.long_text)
        self.assertIn('<p>ok</p>', self.item.long_text)


class ItemFormCostTypeChoicesTestCase(TestCase):
    """Unit tests for ItemForm.set_cost_type_2_choices"""

    def setUp(self):
        self.personal = Kostenart.objects.create(name="Personal")
        self.gehaelter = Kostenart.objects.create(name="Gehälter", parent=self.personal)

    def test_valid_id_enables_field_and_filters_queryset(self):
        form = ItemForm()
        form.set_cost_type_2_choices(self.personal.pk)

        self.assertEqual(list(form.fields['cost_type_2'].queryset), [self.gehaelter])
        self.assertNotIn('disabled', form.fields['cost_type_2'].widget.attrs)

    def test_invalid_id_disables_field(self):
        form = ItemForm()
        form.set_cost_type_2_choices('keine-zahl')

        self.assertEqual(form.fields['cost_type_2'].queryset.count(), 0)
        self.assertEqual(form.fields['cost_type_2'].widget.attrs.get('disabled'), 'disabled')

    def test_empty_id_disables_field(self):
        form = ItemForm()
        form.set_cost_type_2_choices('')

        self.assertEqual(form.fields['cost_type_2'].queryset.count(), 0)
        self.assertEqual(form.fields['cost_type_2'].widget.attrs.get('disabled'), 'disabled')
