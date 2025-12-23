# Dokumentenverwaltung (Vermietung)

## Übersicht

Das Dokumentenverwaltungssystem ermöglicht das Hochladen, Speichern und Verwalten von Dokumenten im Bereich Vermietung. Dokumente werden im Filesystem gespeichert, während die Metadaten in der PostgreSQL-Datenbank verwaltet werden.

## Konzept

### Speicherort

Dokumente werden im Filesystem unter folgendem Pfad gespeichert:

```
<APP_ROOT>/data/vermietung/
```

### Ordnerstruktur

Um Namenskollisionen zwischen unterschiedlichen Entitätstypen zu vermeiden, wird die folgende Struktur verwendet:

```
<APP_ROOT>/data/vermietung/<entity_type>/<entity_id>/<filename>
```

Beispiele:
- `data/vermietung/vertrag/123/mietvertrag.pdf`
- `data/vermietung/mietobjekt/456/foto.jpg`
- `data/vermietung/adresse/789/ausweis.pdf`
- `data/vermietung/uebergabeprotokoll/321/protokoll.pdf`

Diese Struktur stellt sicher, dass IDs verschiedener Entitätstypen nicht kollidieren (z.B. Vertrag #1 und Mietobjekt #1 werden in unterschiedlichen Ordnern gespeichert).

## Datenmodell

### Model: `Dokument`

Das `Dokument`-Model in der App `vermietung` speichert folgende Metadaten:

#### Metadatenfelder

- **original_filename**: Originaler Dateiname beim Upload
- **storage_path**: Relativer Pfad zur Datei (relativ zu `VERMIETUNG_DOCUMENTS_ROOT`)
- **file_size**: Dateigröße in Bytes
- **mime_type**: MIME-Type der Datei (serverseitig erkannt)
- **uploaded_at**: Upload-Zeitpunkt (automatisch gesetzt)
- **uploaded_by**: Benutzer, der die Datei hochgeladen hat (optional)
- **beschreibung**: Optionale Beschreibung/Kommentar zum Dokument

#### Verknüpfung

Jedes Dokument ist **genau einem** der folgenden Zielobjekte zugeordnet:

- **Vertrag** (Mietvertrag)
- **MietObjekt** (Vermietungsobjekt)
- **Adresse** (Kunde, Standort, etc.)
- **Uebergabeprotokoll** (Übergabeprotokoll)

Die Validierung stellt sicher, dass:
- Mindestens ein Zielobjekt gesetzt ist
- Maximal ein Zielobjekt gesetzt ist

## Upload-Regeln

### Erlaubte Dateitypen

Die folgenden Dateitypen sind erlaubt (serverseitig validiert):

- **PDF** (.pdf) - `application/pdf`
- **PNG** (.png) - `image/png`
- **JPG/JPEG** (.jpg, .jpeg) - `image/jpeg`
- **GIF** (.gif) - `image/gif`
- **DOCX** (.docx) - `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

### Maximale Dateigröße

- **10 MB** pro Datei

### Validierung

Die Validierung erfolgt serverseitig und umfasst:

1. **Dateigrößenprüfung**: Die Datei darf nicht größer als 10 MB sein
2. **MIME-Type-Prüfung**: Der MIME-Type wird anhand des Dateiinhalts erkannt (nicht nur über die Dateiendung)
3. **Dateiendung-Prüfung**: Die Dateiendung muss zum erkannten MIME-Type passen

## Zugriff und Security

### Auth-Schutz

- Dokumente sind **nicht** direkt über Nginx/Webserver abrufbar
- Der Zugriff erfolgt über Django-Views mit `@login_required`-Decorator
- Nur eingeloggte Benutzer können Dokumente herunterladen

### Download

Download-URL: `/vermietung/dokument/<id>/download/`

Der Download erfolgt über die View `download_dokument`, die:
1. Prüft, ob der Benutzer eingeloggt ist
2. Das Dokument aus der Datenbank lädt
3. Die Datei aus dem Filesystem liest
4. Die Datei mit korrektem MIME-Type und Download-Header ausliefert

## Django Admin Integration

### Upload

Im Django Admin kann ein Dokument wie folgt hochgeladen werden:

1. Navigieren zu **Vermietung > Dokumente > Dokument hinzufügen**
2. Datei auswählen über das "Datei hochladen"-Feld
3. Zielobjekt auswählen (Vertrag, Mietobjekt, Adresse oder Übergabeprotokoll)
4. Optional: Beschreibung hinzufügen
5. Speichern

Das System:
- Validiert die Datei (Größe, Typ)
- Generiert den Speicherpfad automatisch
- Speichert die Datei im Filesystem
- Speichert die Metadaten in der Datenbank

### Anzeige

Die Dokumentenliste zeigt:
- Dateiname
- Zielobjekt-Typ
- Zugeordnetes Objekt
- Dateigröße (human-readable)
- MIME-Type
- Upload-Zeitpunkt
- Hochgeladen von (Benutzer)

### Filterung

Dokumente können gefiltert werden nach:
- MIME-Type
- Upload-Datum

### Suche

Suche ist möglich nach:
- Dateiname
- Beschreibung
- Vertragsnummer
- Mietobjekt-Name
- Adressen-Name
- Übergabeprotokoll-Vertragsnummer

## Backup

### Datenbank-Backup

Metadaten werden in PostgreSQL gespeichert und sollten mit den regulären Datenbank-Backups gesichert werden:

```bash
pg_dump -U kmanager_user kmanager > backup_$(date +%Y%m%d).sql
```

### Filesystem-Backup

Die Dokumente im Filesystem sollten separat gesichert werden:

```bash
tar -czf dokumente_backup_$(date +%Y%m%d).tar.gz data/vermietung/
```

### Restore

Um ein vollständiges Backup wiederherzustellen:

1. Datenbank wiederherstellen:
   ```bash
   psql -U kmanager_user kmanager < backup_20241223.sql
   ```

2. Dateien wiederherstellen:
   ```bash
   tar -xzf dokumente_backup_20241223.tar.gz
   ```

## Technische Details

### File Storage Helper

Die statische Methode `Dokument.save_uploaded_file()` übernimmt:
- Validierung der Datei
- MIME-Type-Erkennung
- Speicherpfad-Generierung
- Erstellen der Verzeichnisstruktur
- Speichern der Datei im Filesystem

### Delete-Verhalten

Beim Löschen eines Dokuments:
- Wird die Datei aus dem Filesystem entfernt
- Werden leere übergeordnete Verzeichnisse entfernt
- Werden die Metadaten aus der Datenbank gelöscht

### Cascade-Verhalten

Wenn ein Zielobjekt (Vertrag, MietObjekt, etc.) gelöscht wird:
- Werden alle verknüpften Dokumente automatisch gelöscht (`on_delete=CASCADE`)
- Werden die entsprechenden Dateien aus dem Filesystem entfernt

## Entwicklung

### Tests

Tests befinden sich in `vermietung/test_dokument.py` und decken ab:
- Model-Validierung
- Dateigrößen-Validierung
- Dateityp-Validierung
- Speicherpfad-Generierung
- Download-View (Auth-Schutz)
- CRUD-Operationen

Tests ausführen:

```bash
python manage.py test vermietung.test_dokument
```

### Migration

Die Dokument-Tabelle wird mit folgender Migration erstellt:

```bash
python manage.py migrate vermietung
```

Migration: `vermietung/migrations/0005_dokument.py`

## Offene Punkte / Zukünftige Erweiterungen

### Geplante Features

- **Versionierung**: Dokumente könnten versioniert werden (später)
- **Thumbnails**: Vorschaubilder für Bilder generieren (später)
- **Feinere Rechte**: Tenant-/Role-basierte Zugriffskontrolle (später)
- **Volltext-Suche**: PDF-Inhalte durchsuchbar machen (später)

### Hinweise für Deployment

1. **Verzeichnis-Berechtigungen**: Der Webserver benötigt Schreibrechte auf `data/vermietung/`
2. **Nginx-Konfiguration**: Der Pfad `data/` sollte NICHT direkt von Nginx ausgeliefert werden
3. **Backup-Strategie**: Regelmäßige Backups von DB und Filesystem einrichten
4. **.gitignore**: Der Ordner `data/` ist in `.gitignore` aufgenommen und wird nicht versioniert
