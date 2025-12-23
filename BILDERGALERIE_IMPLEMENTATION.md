# MietObjekt Bildergalerie - Implementierung

## Überblick
Die Bildergalerie für MietObjekte ermöglicht das Hochladen, Anzeigen und Löschen von Bildern für jedes Mietobjekt. Die Implementierung folgt den gleichen Mustern wie das bestehende Dokumenten-Management-System.

## Features

### Multi-Upload
- **Mehrere Bilder gleichzeitig hochladen**: Benutzer können mehrere Bilddateien in einem Vorgang hochladen
- **Unterstützte Formate**: PNG, JPG/JPEG, GIF
- **Maximale Dateigröße**: 10 MB pro Bild
- **Serverseitige Validierung**:
  - MIME-Type Detection (nicht nur Dateiendung)
  - Größenlimit-Prüfung

### Thumbnail-Erzeugung
- **Automatisch**: Beim Upload wird automatisch ein Thumbnail erzeugt
- **Größe**: Maximal 300x300 Pixel, Seitenverhältnis wird beibehalten
- **Format**: Thumbnails werden als JPEG gespeichert (Optimierung)
- **Speicherort**: Gleicher Ordner wie Original mit `thumb_` Präfix

### Galerie-Ansicht
- **Tab "Bilder"** auf der Mietobjekt-Detailseite
- **Grid-Layout**: 3x4 Grid mit Thumbnails (12 Bilder pro Seite)
- **Bildvorschau**: Klick auf Thumbnail öffnet Modal mit Original-Bild
- **Metadaten angezeigt**:
  - Dateiname
  - Dateigröße
  - Upload-Datum
- **Pagination**: Automatisch bei mehr als 12 Bildern

### Löschen
- **Bestätigung erforderlich**: JavaScript-Confirm-Dialog vor dem Löschen
- **POST-only**: Löschen nur über POST-Request
- **Cleanup**: Dateien (Original + Thumbnail) werden aus dem Filesystem entfernt
- **Leere Ordner**: Werden automatisch aufgeräumt

### Zugriffschutz
- **Auth-geschützt**: Alle Views sind mit `@vermietung_required` geschützt
- **Django-Serving**: Bilder werden über Django ausgeliefert, nicht direkt über Nginx
- **Separate Endpoints**: `/thumbnail/` und `/original/` für unterschiedliche Auflösungen

## Technische Details

### Datenmodell

```python
class MietObjektBild(models.Model):
    mietobjekt = ForeignKey(MietObjekt, related_name='bilder')
    original_filename = CharField(max_length=255)
    storage_path = CharField(max_length=500)  # Original
    thumbnail_path = CharField(max_length=500)  # Thumbnail
    file_size = IntegerField()
    mime_type = CharField(max_length=100)
    uploaded_at = DateTimeField(auto_now_add=True)
    uploaded_by = ForeignKey(User, null=True)
```

### Storage-Struktur

```
/data/vermietung/
  └── mietobjekt/
      └── <id>/
          └── images/
              ├── <uuid>_<filename>.jpg        # Original
              └── thumb_<uuid>_<filename>.jpg  # Thumbnail
```

- **UUID-Präfix**: Verhindert Dateinamen-Kollisionen
- **Pfadformat**: `mietobjekt/<id>/images/<uuid>_<filename>`
- **Eindeutigkeit**: Durch Typ + ID + UUID garantiert

### Views

#### Upload: `mietobjekt_bild_upload(request, pk)`
- **Methode**: POST
- **Parameter**: `pk` (MietObjekt ID)
- **Files**: `bilder[]` (multiple)
- **Rückgabe**: Redirect zur Detailseite mit Success-/Error-Message

#### Serve Thumbnail: `serve_mietobjekt_bild(request, bild_id, mode='thumbnail')`
- **Methode**: GET
- **Parameter**: `bild_id`, `mode='thumbnail'`
- **Rückgabe**: FileResponse (image/jpeg)
- **Permissions**: @vermietung_required

#### Serve Original: `serve_mietobjekt_bild(request, bild_id, mode='original')`
- **Methode**: GET
- **Parameter**: `bild_id`, `mode='original'`
- **Rückgabe**: FileResponse (original MIME-Type)
- **Permissions**: @vermietung_required

#### Delete: `mietobjekt_bild_delete(request, bild_id)`
- **Methode**: POST only
- **Parameter**: `bild_id`
- **Rückgabe**: Redirect zur Detailseite mit Success-/Error-Message
- **Permissions**: @vermietung_required

### Forms

#### MietObjektBildUploadForm
- **Feld**: `bilder` (FileField mit multiple)
- **Validierung**: Durch Model-Methoden in `save()`
- **Multi-Upload**: Via `request.FILES.getlist('bilder')`

### URLs

```python
# Upload
path('mietobjekte/<int:pk>/bilder/hochladen/', views.mietobjekt_bild_upload, name='mietobjekt_bild_upload')

# Serve
path('mietobjekte/bilder/<int:bild_id>/thumbnail/', views.serve_mietobjekt_bild, {'mode': 'thumbnail'}, name='mietobjekt_bild_thumbnail')
path('mietobjekte/bilder/<int:bild_id>/original/', views.serve_mietobjekt_bild, {'mode': 'original'}, name='mietobjekt_bild_original')

# Delete
path('mietobjekte/bilder/<int:bild_id>/loeschen/', views.mietobjekt_bild_delete, name='mietobjekt_bild_delete')
```

## UI/UX

### Upload-Modal
- **Button**: "Bilder hochladen" im Tab "Bilder"
- **Modal**: Bootstrap 5.3 Modal mit Formular
- **File Input**: Mit `multiple` Attribut für Multi-Select
- **Preview**: JavaScript zeigt ausgewählte Bilder vor Upload an

### Galerie-Display
- **Responsive Grid**: `col-md-3 col-sm-4 col-6` (anpassbar)
- **Card Layout**: Bootstrap Cards mit Bild + Metadaten
- **Hover-Effekte**: CSS-Hover für bessere UX
- **Lazy Loading**: Durch Pagination (12 Bilder/Seite)

### Bildvorschau
- **Modal**: Bootstrap Modal mit `modal-lg` Größe
- **Image**: `max-height: 70vh` für optimale Darstellung
- **Centered**: Modal zentriert auf dem Bildschirm

### Delete-Bestätigung
- **JavaScript Confirm**: Native Browser-Dialog
- **Form Submit**: POST über verstecktes Formular
- **Feedback**: Django Messages nach dem Löschen

## Tests

### Model Tests (11 Tests)
- Storage path generation
- Save uploaded image (JPEG, PNG)
- Delete removes files
- File size validation (valid, too large)
- File type validation (JPEG, PNG, invalid)
- Thumbnail creation

### View Tests (10 Tests)
- MietObjekt detail includes bilder
- Upload single image
- Upload multiple images
- Upload requires authentication
- Upload requires vermietung access
- Serve thumbnail
- Serve original
- Serve requires authentication
- Delete image
- Delete requires POST
- Non-staff with Vermietung group can upload

**Alle 21 Tests bestehen** ✅

## Dependencies

### Neue Abhängigkeit
- **Pillow 10.2.0**: Für Bildverarbeitung und Thumbnail-Erzeugung

```python
# requirements.txt
Pillow==10.2.0
```

## Migration

```bash
python manage.py makemigrations vermietung
python manage.py migrate
```

### Migration 0008_mietobjektbild.py
- Erstellt `MietObjektBild` Tabelle
- Alle Felder mit entsprechenden Constraints
- ForeignKey zu `MietObjekt` mit CASCADE
- ForeignKey zu `User` mit SET_NULL

## Sicherheit

### Validierung
- **MIME-Type Detection**: Via python-magic (nicht nur Extension)
- **File Size Check**: Server-seitig (10 MB Limit)
- **Allowed Types**: Whitelist (PNG, JPEG, GIF)

### Zugriffskontrolle
- **Auth Required**: Alle Endpoints
- **Vermietung Permission**: Via `@vermietung_required`
- **Staff oder Gruppe**: is_staff=True ODER in Gruppe "Vermietung"

### Filesystem
- **Private Storage**: `/data/vermietung/` (außerhalb von static/media)
- **Django Serving**: Keine direkten File-URLs
- **Path Traversal**: Verhindert durch absolute Pfade und Validierung

## Performance

### Thumbnail-Strategie
- **Eager Generation**: Beim Upload (nicht on-demand)
- **JPEG Format**: Komprimierung mit quality=85
- **Optimized**: PIL optimize=True

### Pagination
- **12 Bilder/Seite**: Balance zwischen UX und Performance
- **Queryset**: `select_related('uploaded_by')` zur Optimierung

### File Serving
- **FileResponse**: Django's optimierte File-Serving-Klasse
- **Content-Type**: Korrekt gesetzt (JPEG für Thumbnails, original für Originals)

## Erweiterungsmöglichkeiten

### Zukünftige Features (nicht im MVP)
- [ ] Bildtitel/Beschreibung
- [ ] Sortier-Reihenfolge
- [ ] Hauptbild markieren
- [ ] Bildrotation/Bearbeitung
- [ ] Bulk-Delete
- [ ] Zip-Download aller Bilder
- [ ] Exif-Daten anzeigen

### Code-Verbesserungen
- [ ] Async Thumbnail-Generierung (Celery)
- [ ] Image Caching (CDN)
- [ ] Responsive Images (srcset)
- [ ] WebP Format-Unterstützung

## Checkliste für Deployment

- [x] Migration erstellt und getestet
- [x] Tests geschrieben (21/21 passing)
- [x] UI Integration abgeschlossen
- [x] Permissions korrekt gesetzt
- [x] File Validation implementiert
- [x] Dokumentation erstellt
- [ ] `/data/vermietung/` Ordner auf Server erstellen
- [ ] Permissions auf `/data/vermietung/` setzen (Webserver-Benutzer)
- [ ] Pillow in Production installieren
- [ ] Migration auf Production ausführen

## Bekannte Einschränkungen

1. **Keine Bildbearbeitung**: Rotation/Crop muss vor Upload erfolgen
2. **Keine EXIF-Bereinigung**: Metadata bleibt im Original erhalten
3. **Fixed Thumbnail Size**: 300x300 nicht konfigurierbar
4. **Keine Batch-Operations**: Löschen nur einzeln möglich
5. **Keine Versioning**: Überschreiben nicht möglich, nur löschen + neu hochladen

## Support

Bei Fragen oder Problemen:
1. Tests ausführen: `python manage.py test vermietung.test_mietobjekt_bild --settings=test_settings`
2. Logs prüfen: Django error logs
3. Filesystem prüfen: `/data/vermietung/mietobjekt/<id>/images/`
4. Permissions prüfen: Webserver-Benutzer muss Schreibrechte haben
