"""
Tests für die ausgelagerten Base-Template-Assets (static/js/app.js,
static/js/sidebar.js).

Sichert ab, dass die Base-Templates die JS-Dateien einbinden und dass die
früher dreifach gepflegten Inline-Skripte nicht wieder zurückwandern.
"""

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

#: Alle Base-Templates. lieferantenwesen/base.html erbt von base.html und
#: bekommt app.js dadurch mit.
ALL_BASES = [
    "base.html",
    "core/core_base.html",
    "vermietung/vermietung_base.html",
    "auftragsverwaltung/auftragsverwaltung_base.html",
    "lieferantenwesen/base.html",
]

#: Bases mit Modul-Sidebar (#sidebarMenu) - nur diese brauchen sidebar.js.
SIDEBAR_BASES = [
    "core/core_base.html",
    "vermietung/vermietung_base.html",
    "auftragsverwaltung/auftragsverwaltung_base.html",
]

#: Marker aus den früheren Inline-Skripten. Tauchen sie im gerenderten HTML
#: auf, wurde JS wieder ins Template kopiert.
#: Einzige erlaubte Ausnahme ist das Anti-Flicker-Snippet in
#: includes/_sidebar_boot.html (muss vor dem ersten Paint laufen) - es wird in
#: test_base_template_layout.py geprüft.
INLINE_JS_MARKERS = [
    "htmx:configRequest",
    "nav.expandedMenuGroupIds",
    "toggleMobileSidebar",
    "new bootstrap.Tooltip",
    "form[enctype=",
]


class BaseTemplateAssetTests(TestCase):
    """Prüft Einbindung der ausgelagerten Skripte in allen Base-Templates."""

    def _render(self, template_name):
        request = RequestFactory().get("/")
        request.user = get_user_model()(username="tester")
        return render_to_string(template_name, request=request)

    def test_all_bases_include_app_js(self):
        for template_name in ALL_BASES:
            with self.subTest(template=template_name):
                self.assertIn("js/app.js", self._render(template_name))

    def test_sidebar_bases_include_sidebar_js(self):
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                self.assertIn("js/sidebar.js", self._render(template_name))

    def test_scripts_are_deferred(self):
        """defer, damit die Skripte das Parsen der Seite nicht blockieren."""
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                for script in ("app.js", "sidebar.js"):
                    self.assertRegex(html, rf'src="[^"]*js/{script}"\s+defer')

    def test_no_inline_js_left_in_bases(self):
        for template_name in ALL_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                for marker in INLINE_JS_MARKERS:
                    self.assertNotIn(marker, html)
