"""
Tests for Projekt and ProjektFile models and views.
"""
import os
import tempfile
import shutil
from pathlib import Path

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from core.models import Projekt, ProjektFile, PROJEKT_STATUS_CHOICES, PROJEKT_MAX_FILE_SIZE


TEMP_PROJECT_DIR = None


def setUpModule():
    global TEMP_PROJECT_DIR
    TEMP_PROJECT_DIR = tempfile.mkdtemp()


def tearDownModule():
    if TEMP_PROJECT_DIR and os.path.exists(TEMP_PROJECT_DIR):
        shutil.rmtree(TEMP_PROJECT_DIR)


class ProjektModelTestCase(TestCase):
    """Tests for the Projekt model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    def test_create_projekt(self):
        """Test basic project creation."""
        projekt = Projekt.objects.create(
            titel='Testprojekt',
            beschreibung='Eine Beschreibung',
            status='NEU',
            erstellt_von=self.user,
        )
        self.assertIsNotNone(projekt.pk)
        self.assertEqual(projekt.titel, 'Testprojekt')
        self.assertEqual(projekt.status, 'NEU')
        self.assertEqual(str(projekt), 'Testprojekt')

    def test_all_status_choices(self):
        """Test that all status choices are valid."""
        for status_code, _ in PROJEKT_STATUS_CHOICES:
            projekt = Projekt.objects.create(titel=f'Projekt {status_code}', status=status_code)
            self.assertEqual(projekt.status, status_code)

    def test_default_status_is_neu(self):
        """Test that default status is NEU."""
        projekt = Projekt.objects.create(titel='Status Test')
        self.assertEqual(projekt.status, 'NEU')

    def test_ordering_newest_first(self):
        """Test that projects are ordered by newest first."""
        p1 = Projekt.objects.create(titel='Projekt 1')
        p2 = Projekt.objects.create(titel='Projekt 2')
        projekte = list(Projekt.objects.all())
        self.assertEqual(projekte[0], p2)
        self.assertEqual(projekte[1], p1)


class ProjektFileModelTestCase(TestCase):
    """Tests for the ProjektFile model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser2', password='password')
        self.projekt = Projekt.objects.create(titel='File Test Projekt', erstellt_von=self.user)

    def test_create_folder(self):
        """Test creating a folder entry."""
        folder = ProjektFile.objects.create(
            projekt=self.projekt,
            filename='Dokumente',
            ordner='',
            is_folder=True,
            benutzer=self.user,
        )
        self.assertTrue(folder.is_folder)
        self.assertEqual(str(folder), 'Dokumente')

    def test_create_file_entry(self):
        """Test creating a file metadata entry."""
        pfile = ProjektFile.objects.create(
            projekt=self.projekt,
            filename='test.pdf',
            ordner='Dokumente',
            is_folder=False,
            storage_path='1/Dokumente/test.pdf',
            file_size=1024,
            mime_type='application/pdf',
            benutzer=self.user,
        )
        self.assertFalse(pfile.is_folder)
        self.assertEqual(str(pfile), 'Dokumente/test.pdf')

    def test_file_in_root(self):
        """Test file at project root (no ordner)."""
        pfile = ProjektFile.objects.create(
            projekt=self.projekt,
            filename='readme.txt',
            ordner='',
            is_folder=False,
            storage_path='1/readme.txt',
            file_size=512,
            benutzer=self.user,
        )
        self.assertEqual(str(pfile), 'readme.txt')


class ProjektViewsTestCase(TestCase):
    """Tests for the Projekt views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='viewuser', password='password')
        self.client.login(username='viewuser', password='password')

    def test_projekt_list_requires_login(self):
        """Test that projekt_list requires authentication."""
        self.client.logout()
        response = self.client.get(reverse('projekt_list'))
        self.assertRedirects(response, f'/login/?next=/projekte/')

    def test_projekt_list_empty(self):
        """Test project list page with no projects."""
        response = self.client.get(reverse('projekt_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Projekte')

    def test_projekt_list_with_data(self):
        """Test project list page shows existing projects."""
        Projekt.objects.create(titel='Sichtbares Projekt', erstellt_von=self.user)
        response = self.client.get(reverse('projekt_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sichtbares Projekt')

    def test_projekt_create_get(self):
        """Test GET request to projekt_create returns form."""
        response = self.client.get(reverse('projekt_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neues Projekt')

    def test_projekt_create_post(self):
        """Test POST creates a project and redirects to detail."""
        response = self.client.post(reverse('projekt_create'), {
            'titel': 'Neues Testprojekt',
            'beschreibung': 'Beschreibung',
            'status': 'NEU',
        })
        self.assertEqual(Projekt.objects.filter(titel='Neues Testprojekt').count(), 1)
        projekt = Projekt.objects.get(titel='Neues Testprojekt')
        self.assertRedirects(response, reverse('projekt_detail', args=[projekt.pk]))
        self.assertEqual(projekt.erstellt_von, self.user)

    def test_projekt_detail_view(self):
        """Test projekt_detail page renders."""
        projekt = Projekt.objects.create(titel='Detail Projekt', erstellt_von=self.user)
        response = self.client.get(reverse('projekt_detail', args=[projekt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Projekt')

    def test_projekt_edit_get(self):
        """Test GET on projekt_edit returns pre-filled form."""
        projekt = Projekt.objects.create(titel='Edit Projekt', status='NEU', erstellt_von=self.user)
        response = self.client.get(reverse('projekt_edit', args=[projekt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Projekt')

    def test_projekt_edit_post(self):
        """Test POST on projekt_edit updates and redirects."""
        projekt = Projekt.objects.create(titel='Alt', status='NEU', erstellt_von=self.user)
        response = self.client.post(reverse('projekt_edit', args=[projekt.pk]), {
            'titel': 'Neu',
            'beschreibung': '',
            'status': 'IN_BEARBEITUNG',
        })
        self.assertRedirects(response, reverse('projekt_detail', args=[projekt.pk]))
        projekt.refresh_from_db()
        self.assertEqual(projekt.titel, 'Neu')
        self.assertEqual(projekt.status, 'IN_BEARBEITUNG')

    def test_projekt_delete_get(self):
        """Test GET on projekt_delete shows confirmation page."""
        projekt = Projekt.objects.create(titel='Zu löschen', erstellt_von=self.user)
        response = self.client.get(reverse('projekt_delete', args=[projekt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zu löschen')

    def test_projekt_delete_post(self):
        """Test POST on projekt_delete removes the project."""
        projekt = Projekt.objects.create(titel='Zu löschen', erstellt_von=self.user)
        pk = projekt.pk
        response = self.client.post(reverse('projekt_delete', args=[pk]))
        self.assertRedirects(response, reverse('projekt_list'))
        self.assertFalse(Projekt.objects.filter(pk=pk).exists())

    def test_projekt_list_search(self):
        """Test project list search by title."""
        Projekt.objects.create(titel='Alpha Projekt', erstellt_von=self.user)
        Projekt.objects.create(titel='Beta Projekt', erstellt_von=self.user)
        response = self.client.get(reverse('projekt_list'), {'search': 'Alpha'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Projekt')
        self.assertNotContains(response, 'Beta Projekt')

    def test_projekt_list_status_filter(self):
        """Test project list filter by status."""
        Projekt.objects.create(titel='Neues P', status='NEU', erstellt_von=self.user)
        Projekt.objects.create(titel='Abgeschlossenes P', status='ABGESCHLOSSEN', erstellt_von=self.user)
        response = self.client.get(reverse('projekt_list'), {'status': 'NEU'})
        self.assertContains(response, 'Neues P')
        self.assertNotContains(response, 'Abgeschlossenes P')


class ProjektOrdnerCreateTestCase(TestCase):
    """Tests for folder creation inside a project."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='ordneruser', password='password')
        self.client.login(username='ordneruser', password='password')
        self.projekt = Projekt.objects.create(titel='Ordner Test', erstellt_von=self.user)

    @override_settings(PROJECT_DOCUMENTS_ROOT=TEMP_PROJECT_DIR or '/tmp/test_projects')
    def test_create_ordner(self):
        """Test creating a folder creates a DB entry and physical directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(PROJECT_DOCUMENTS_ROOT=tmpdir):
                response = self.client.post(
                    reverse('projekt_ordner_create', args=[self.projekt.pk]),
                    {'ordner_name': 'Unterlagen', 'parent_ordner': ''},
                )
                self.assertEqual(
                    ProjektFile.objects.filter(
                        projekt=self.projekt, filename='Unterlagen', is_folder=True
                    ).count(),
                    1,
                )
                expected_dir = Path(tmpdir) / str(self.projekt.pk) / 'Unterlagen'
                self.assertTrue(expected_dir.is_dir())

    def test_create_ordner_invalid_name(self):
        """Test that folder names with path separators are rejected."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(PROJECT_DOCUMENTS_ROOT=tmpdir):
                response = self.client.post(
                    reverse('projekt_ordner_create', args=[self.projekt.pk]),
                    {'ordner_name': '../evil', 'parent_ordner': ''},
                )
                # Should NOT create the folder
                self.assertEqual(
                    ProjektFile.objects.filter(
                        projekt=self.projekt, is_folder=True
                    ).count(),
                    0,
                )


class ProjektFileFileSizeTestCase(TestCase):
    """Tests for file size validation."""

    def test_file_size_limit_constant(self):
        """Verify max file size is 25 MB."""
        self.assertEqual(PROJEKT_MAX_FILE_SIZE, 25 * 1024 * 1024)
