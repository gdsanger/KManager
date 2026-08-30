"""
Tests für das gemeinsame Layout der Base-Templates.

Sichert ab, dass Navbar und Head-Assets nur noch als Include existieren, dass
die Sidebar-Bases die Layout-Klasse `has-sidebar` setzen und dass Sidebar,
Main und Footer ihre Breite aus derselben CSS-Variablen beziehen.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

#: Alle Base-Templates. lieferantenwesen/base.html erbt von
#: auftragsverwaltung/auftragsverwaltung_base.html (gemeinsame Sidebar).
ALL_BASES = [
    "base.html",
    "core/core_base.html",
    "vermietung/vermietung_base.html",
    "auftragsverwaltung/auftragsverwaltung_base.html",
    "lieferantenwesen/base.html",
]

#: Bases mit Modul-Sidebar (#sidebarMenu).
SIDEBAR_BASES = [
    "core/core_base.html",
    "vermietung/vermietung_base.html",
    "auftragsverwaltung/auftragsverwaltung_base.html",
    "lieferantenwesen/base.html",
]

SITE_CSS = Path(settings.BASE_DIR) / "static" / "css" / "site.css"


class BaseTemplateRenderMixin:
    """Rendert ein Template mit angemeldetem Nutzer im Request-Kontext."""

    def _render(self, template_name):
        request = RequestFactory().get("/")
        request.user = get_user_model()(username="tester")
        return render_to_string(template_name, request=request)


class NavbarIncludeTests(BaseTemplateRenderMixin, TestCase):
    """Die Navbar existiert nur noch einmal als Include."""

    def test_navbar_rendered_exactly_once(self):
        for template_name in ALL_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                self.assertEqual(html.count("navbar-brand"), 1)

    def test_all_bases_show_lieferantenwesen(self):
        """Früher fehlte der Eintrag in allen Bases außer base.html."""
        for template_name in ALL_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                self.assertIn("/lieferantenwesen/", html)
                self.assertIn("Lieferantenwesen", html)

    def test_all_bases_show_same_nav_entries(self):
        expected = [
            "Home",
            "Gebäude",
            "Auftragsverwaltung",
            "Lieferantenwesen",
            "Finanzen",
            "Verwaltung",
            "Support Portal",
        ]
        for template_name in ALL_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                for entry in expected:
                    self.assertIn(entry, html)

    def test_navbar_include_is_used_in_sources(self):
        """Kein Base-Template pflegt die Navbar noch selbst."""
        for template_name in ALL_BASES[:-1]:  # lieferantenwesen erbt die Navbar
            with self.subTest(template=template_name):
                source = (Path(settings.BASE_DIR) / "templates" / template_name).read_text(
                    encoding="utf-8"
                )
                self.assertIn('include "includes/_navbar.html"', source)
                self.assertNotIn("navbar-brand", source)


class HeadIncludeTests(BaseTemplateRenderMixin, TestCase):
    """Head-Assets kommen aus einem gemeinsamen Include."""

    def test_head_assets_present(self):
        for template_name in ALL_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                self.assertIn("css/site.css", html)
                self.assertIn("bootstrap@5.3.2", html)
                self.assertIn("bootstrap-icons", html)
                self.assertIn("quill", html)

    def test_title_block_still_overridable(self):
        """Der <title> bleibt im Base, damit {% block title %} greift."""
        self.assertIn("Gebäude - Domus", self._render("vermietung/vermietung_base.html"))
        self.assertIn("Verwaltung - Domus", self._render("core/core_base.html"))


class SidebarLayoutTests(BaseTemplateRenderMixin, TestCase):
    """Layout-Klassen und Anti-Flicker-Snippet der Sidebar-Bases."""

    def test_sidebar_bases_set_has_sidebar_class(self):
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                self.assertIn('<body class="has-sidebar">', self._render(template_name))

    def test_base_without_sidebar_has_no_offset_class(self):
        """base.html hat keine Sidebar und darf keinen Offset bekommen."""
        self.assertNotIn("has-sidebar", self._render("base.html"))

    def test_main_offset_comes_from_css_not_grid(self):
        """Main nutzt .main-panel statt eigener Grid-Breite."""
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                self.assertIn('<main class="main-panel', html)
                self.assertNotIn("ms-sm-auto", html)

    def test_sidebar_boot_snippet_present(self):
        """Anti-Flicker-Snippet: Klasse muss vor dem ersten Paint stehen."""
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                self.assertIn("nav.sidebarCollapsed", html)
                # direkt nach <body>, noch vor der Navbar
                self.assertLess(
                    html.index("nav.sidebarCollapsed"), html.index("navbar-brand")
                )

    def test_toggle_button_is_accessible(self):
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                html = self._render(template_name)
                self.assertIn('id="sidebarToggle"', html)
                self.assertIn('aria-controls="sidebarMenu"', html)
                self.assertIn('aria-label="Seitenleiste einklappen"', html)

    def test_no_inline_styles_in_sidebar_bases(self):
        """Positionierung gehört nach site.css (siehe CLAUDE.md)."""
        for template_name in SIDEBAR_BASES:
            with self.subTest(template=template_name):
                source = (Path(settings.BASE_DIR) / "templates" / template_name).read_text(
                    encoding="utf-8"
                )
                self.assertNotIn("style=", source)


class SiteCssLayoutTests(TestCase):
    """Eine gemeinsame Quelle für Navbar-Höhe und Sidebar-Breite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = SITE_CSS.read_text(encoding="utf-8")

    def test_layout_variables_defined(self):
        for variable in (
            "--navbar-height",
            "--sidebar-width-md",
            "--sidebar-width-lg",
            "--sidebar-width-collapsed",
        ):
            with self.subTest(variable=variable):
                self.assertIn(variable + ":", self.css)

    def test_sidebar_top_follows_navbar_height(self):
        self.assertIn("top: var(--navbar-height)", self.css)
        self.assertNotIn("top: 56px", self.css)

    def test_navbar_is_above_sidebar(self):
        navbar_block = self.css[self.css.index("/* Navigation Styles */"):]
        navbar_block = navbar_block[: navbar_block.index("}")]
        self.assertIn("position: sticky", navbar_block)
        self.assertIn("z-index: 1045", navbar_block)

    def test_sidebar_main_and_footer_share_one_width(self):
        # Sidebar (Desktop-Media-Query) …
        self.assertIn("width: var(--sidebar-width);", self.css)
        # … Main und Footer lesen dieselbe Variable
        for selector in (".has-sidebar .main-panel", ".has-sidebar .footer"):
            with self.subTest(selector=selector):
                block_start = self.css.index(selector + " {")
                block = self.css[block_start : self.css.index("}", block_start)]
                self.assertIn("var(--sidebar-width)", block)

    def test_sticky_footer_layout(self):
        body_block = self.css[self.css.index("/* Global Styles */"):]
        body_block = body_block[: body_block.index("}")]
        self.assertIn("min-height: 100vh", body_block)
        self.assertIn("flex-direction: column", body_block)
        self.assertIn(".page-content", self.css)
