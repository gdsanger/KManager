# KManager v1.0 - Setup Anleitung

## Voraussetzungen

- Python 3.12 oder höher
- PostgreSQL 14 oder höher
- pip (Python Package Manager)

## Installation

### 1. Repository klonen

```bash
git clone <repository-url>
cd KManager
```

### 2. Virtuelle Umgebung erstellen

```bash
python -m venv venv
source venv/bin/activate  # Unter Linux/Mac
# oder
venv\Scripts\activate  # Unter Windows
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 4. Umgebungsvariablen konfigurieren

Kopieren Sie `.env.example` zu `.env` und passen Sie die Werte an:

```bash
cp .env.example .env
```

Bearbeiten Sie die `.env` Datei mit Ihren Datenbank-Credentials:

```env
SECRET_KEY=ihr-geheimer-schluessel
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=kmanager
DB_USER=kmanager_user
DB_PASSWORD=ihr-db-passwort
DB_HOST=localhost
DB_PORT=5432
```

### 5. PostgreSQL Datenbank erstellen

```bash
# PostgreSQL Shell öffnen
psql -U postgres

# Datenbank und Benutzer erstellen
CREATE DATABASE kmanager;
CREATE USER kmanager_user WITH PASSWORD 'ihr-db-passwort';
ALTER ROLE kmanager_user SET client_encoding TO 'utf8';
ALTER ROLE kmanager_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE kmanager_user SET timezone TO 'Europe/Berlin';
GRANT ALL PRIVILEGES ON DATABASE kmanager TO kmanager_user;
\q
```

### 6. Datenbank-Migrationen ausführen

```bash
python manage.py migrate
```

### 7. Superuser erstellen (optional)

```bash
python manage.py createsuperuser
```

### 8. Statische Dateien sammeln (für Produktion)

```bash
python manage.py collectstatic
```

### 9. Entwicklungsserver starten

```bash
python manage.py runserver
```

Die Anwendung ist jetzt unter `http://localhost:8000` erreichbar.

## Entwicklung

### Server im Debug-Modus starten

```bash
python manage.py runserver
```

### Admin-Interface

Das Django Admin-Interface ist unter `http://localhost:8000/admin` verfügbar.

## Hinweise

- Stellen Sie sicher, dass PostgreSQL läuft, bevor Sie den Server starten
- Im Debug-Modus wird SQLite verwendet, wenn PostgreSQL nicht verfügbar ist (Standard-Fallback)
- Die `.env` Datei sollte niemals in Git committed werden (bereits in `.gitignore`)
