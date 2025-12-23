# Authentication & Authorization für Vermietung

## Übersicht

Der Vermietungsbereich von K-Manager ist durch Authentifizierung und Autorisierung geschützt. Nur autorisierte Benutzer können auf diesen Bereich zugreifen.

## Zugriffsberechtigung

Der Zugriff auf den Vermietungsbereich wird wie folgt gewährt:

### 1. Administrator (is_staff=True)
Benutzer mit `is_staff=True` haben **immer** Zugriff auf alle Bereiche, einschließlich Vermietung.

### 2. Gruppe "Vermietung"
Benutzer, die Mitglied der Gruppe **"Vermietung"** sind, haben Zugriff auf den Vermietungsbereich.

**Wichtig:** Der Gruppenname muss exakt `Vermietung` lauten (mit korrekter Groß-/Kleinschreibung).

## Benutzergruppe erstellen

### Via Django Admin

1. Melden Sie sich im Django Admin an: `/admin/`
2. Navigieren Sie zu "Authentifizierung und Autorisierung" → "Gruppen"
3. Klicken Sie auf "Gruppe hinzufügen"
4. Geben Sie den Namen `Vermietung` ein (exakt wie geschrieben)
5. Optional: Wählen Sie spezifische Berechtigungen aus
6. Klicken Sie auf "Sichern"

### Via Django Shell

```python
from django.contrib.auth.models import Group

# Gruppe erstellen
vermietung_group, created = Group.objects.get_or_create(name='Vermietung')

if created:
    print("Gruppe 'Vermietung' wurde erfolgreich erstellt")
else:
    print("Gruppe 'Vermietung' existiert bereits")
```

## Benutzer zur Gruppe hinzufügen

### Via Django Admin

1. Melden Sie sich im Django Admin an
2. Navigieren Sie zu "Benutzer"
3. Wählen Sie den Benutzer aus
4. Scrollen Sie zu "Berechtigungen"
5. Wählen Sie `Vermietung` aus "Verfügbare Gruppen"
6. Klicken Sie auf den Pfeil nach rechts, um die Gruppe hinzuzufügen
7. Klicken Sie auf "Sichern"

### Via Django Shell

```python
from django.contrib.auth.models import User, Group

# Benutzer und Gruppe abrufen
user = User.objects.get(username='max.mustermann')
vermietung_group = Group.objects.get(name='Vermietung')

# Benutzer zur Gruppe hinzufügen
user.groups.add(vermietung_group)
user.save()

print(f"Benutzer {user.username} wurde zur Gruppe 'Vermietung' hinzugefügt")
```

## Login & Logout

### Login-Seite
- URL: `/login/`
- Benutzer können sich mit Benutzername und Passwort anmelden
- Nach erfolgreicher Anmeldung werden Benutzer zur Startseite weitergeleitet
- Bei Zugriff auf geschützte Seiten erfolgt eine Umleitung zum Login mit anschließender Weiterleitung zur ursprünglich angeforderten Seite

### Logout
- URL: `/logout/`
- Benutzer werden abgemeldet und zur Startseite weitergeleitet

## Verhalten bei fehlenden Berechtigungen

### Nicht authentifizierte Benutzer
- Werden automatisch zur Login-Seite umgeleitet
- Nach erfolgreicher Anmeldung werden sie zur ursprünglich angeforderten Seite weitergeleitet

### Authentifizierte Benutzer ohne Berechtigung
- Erhalten einen HTTP 403 Forbidden Fehler
- Sehen eine Fehlermeldung: "Sie haben keine Berechtigung für den Vermietung-Bereich."

## Technische Implementierung

### Für Entwickler: View-Schutz

#### Function-Based Views
```python
from vermietung.permissions import vermietung_required

@vermietung_required
def my_view(request):
    # Nur für autorisierte Benutzer
    return render(request, 'my_template.html')
```

#### Class-Based Views
```python
from vermietung.permissions import VermietungAccessMixin
from django.views.generic import TemplateView

class MyView(VermietungAccessMixin, TemplateView):
    template_name = 'my_template.html'
    # Nur für autorisierte Benutzer
```

### Berechtigung programmatisch prüfen
```python
from vermietung.permissions import user_has_vermietung_access

if user_has_vermietung_access(request.user):
    # Benutzer hat Zugriff
    pass
else:
    # Benutzer hat keinen Zugriff
    pass
```

## Testing

Für Tests können Sie Benutzer mit den entsprechenden Berechtigungen wie folgt erstellen:

```python
from django.contrib.auth.models import User, Group

# Admin-Benutzer erstellen
admin_user = User.objects.create_user(
    username='admin',
    password='password',
    is_staff=True
)

# Vermietungs-Benutzer erstellen
vermietung_group = Group.objects.create(name='Vermietung')
vermietung_user = User.objects.create_user(
    username='vermietung',
    password='password'
)
vermietung_user.groups.add(vermietung_group)
```

## Sicherheitshinweise

1. **Passwörter**: Verwenden Sie starke Passwörter für alle Benutzerkonten
2. **is_staff**: Geben Sie `is_staff=True` nur an vertrauenswürdige Administratoren
3. **Gruppenname**: Der Gruppenname `Vermietung` ist case-sensitive und muss exakt übereinstimmen
4. **Produktionsumgebung**: Stellen Sie sicher, dass `DEBUG=False` in der Produktion gesetzt ist
5. **HTTPS**: Verwenden Sie HTTPS in der Produktion, um Anmeldedaten zu schützen
