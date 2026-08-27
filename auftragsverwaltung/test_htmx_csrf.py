"""
Tests für den globalen HTMX-CSRF-Hook aus static/js/app.js.

Der Hook hängt `X-CSRFToken` (gelesen aus dem csrftoken-Cookie) an jeden
HTMX-Request. Damit entfallen die früheren per-Element
`hx-headers='{"X-CSRFToken": "..."}'`-Workarounds in den Contract-Templates.
Diese Tests sichern beide Seiten ab: Der Header-Weg wird akzeptiert, ohne
Token bleibt der CSRF-Schutz wirksam.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


class HtmxCsrfCookieTests(TestCase):
    """Der Cookie-basierte CSRF-Weg funktioniert für die Contract-Endpunkte."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="csrf-tester",
            password="pw12345!",
            is_staff=True,
            is_superuser=True,
        )

    def test_login_page_sets_csrf_cookie(self):
        """Grundannahme des Hooks: das csrftoken-Cookie ist gesetzt."""
        client = Client()
        client.get(reverse("login"))
        self.assertIn("csrftoken", client.cookies)

    def test_post_with_header_token_passes_csrf_check(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get(reverse("login"))  # setzt das csrftoken-Cookie
        token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("auftragsverwaltung:contracts_run_billing"),
            HTTP_X_CSRFTOKEN=token,
            HTTP_HX_REQUEST="true",
        )

        self.assertNotEqual(response.status_code, 403)

    def test_post_without_token_is_still_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(
            reverse("auftragsverwaltung:contracts_run_billing")
        )

        self.assertEqual(response.status_code, 403)


class ContractTemplateHxHeadersTests(TestCase):
    """Die Contract-Templates kommen ohne per-Element hx-headers aus."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="template-tester",
            password="pw12345!",
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_contract_list_has_no_hx_headers(self):
        response = self.client.get(reverse("auftragsverwaltung:contract_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "hx-headers")
        self.assertContains(response, "js/app.js")
