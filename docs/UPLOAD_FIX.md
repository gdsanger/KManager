# Fix für Bild- und Dokument-Upload

## Problem
Upload von Bildern und Dokumenten funktionierte nicht. Die Dateien wurden nicht in `/data` gespeichert und nichts wurde angezeigt, obwohl die HTTP-Anfrage mit einem 302-Redirect erfolgreich war.

## Ursache
Das `/data/vermietung` Verzeichnis wurde nicht automatisch beim Start der Anwendung erstellt. Während der Code `mkdir(parents=True, exist_ok=True)` verwendet, um Verzeichnisse zu erstellen, konnte es in bestimmten Deployment-Szenarien zu Problemen kommen, wenn die grundlegende Verzeichnisstruktur nicht vorhanden war.

## Lösung

### 1. Automatische Verzeichniserstellung beim App-Start
In `vermietung/apps.py` wurde eine `VermietungConfig` Klasse mit einer `ready()` Methode hinzugefügt, die sicherstellt, dass das `VERMIETUNG_DOCUMENTS_ROOT` Verzeichnis beim Start der Anwendung erstellt wird.

```python
class VermietungConfig(AppConfig):
    def ready(self):
        """Ensures that required media directories exist."""
        from django.conf import settings
        from pathlib import Path
        
        vermietung_docs_root = Path(settings.VERMIETUNG_DOCUMENTS_ROOT)
        if not vermietung_docs_root.exists():
            try:
                vermietung_docs_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create directory: {e}")
```

### 2. Verbesserte Fehlerbehandlung und Logging
In `vermietung/models.py` wurden die Methoden `save_uploaded_image()` und `save_uploaded_file()` mit besserer Fehlerbehandlung und Logging erweitert:

- Explizite try-except Blöcke für Verzeichniserstellung
- Explizite try-except Blöcke für Dateispeicherung
- Logging von Debug-, Info- und Error-Meldungen
- Aufräumen von Dateien bei Fehlern
- Aussagekräftige Fehlermeldungen für Benutzer

## Deployment-Hinweise

### Entwicklung
Beim Start der Anwendung mit `manage.py runserver` wird das Verzeichnis automatisch erstellt.

### Produktion
- Das `data/` Verzeichnis ist in `.gitignore` und wird nicht ins Repository committed
- Stellen Sie sicher, dass der Webserver (z.B. Nginx, Apache) Schreibrechte für das `data/` Verzeichnis hat
- Bei Docker: Mounten Sie das `data/` Verzeichnis als Volume

### Berechtigungen
```bash
# Sicherstellen, dass der Webserver-Benutzer Schreibrechte hat
sudo chown -R www-data:www-data /path/to/KManager/data
sudo chmod -R 755 /path/to/KManager/data
```

## Tests
Alle bestehenden Tests laufen weiterhin erfolgreich:
- `vermietung.test_mietobjekt_bild` - 21 Tests
- `vermietung.test_dokument` - 15 Tests
