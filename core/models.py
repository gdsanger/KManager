from django.db import models

ANREDEN = [
    ('HERR', 'Herr'),
    ('FRAU', 'Frau'),
    ('DIVERS', 'Divers'),
]
ADRESSEN_TYPES = [
    ('Adresse', 'Adresse'),
    ('KUNDE', 'Kunde'),
    ('LIEFERANT', 'Lieferant'),
    ('STANDORT', 'Standort'),
    ('SONSTIGES', 'Sonstiges'),
]

# Create your models here.
class Adresse(models.Model):
    adressen_type = models.CharField(max_length=20, choices=ADRESSEN_TYPES, default='Adresse')
    firma = models.CharField(max_length=100, blank=True, null=True)
    anrede = models.CharField(max_length=10, choices=ANREDEN, blank=True, null=True)
    name = models.CharField(max_length=100)
    strasse = models.CharField(max_length=200)
    plz = models.CharField(max_length=10)
    ort = models.CharField(max_length=100)
    land = models.CharField(max_length=100)
    telefon = models.CharField(max_length=50, blank=True, null=True)
    mobil = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    bemerkung = models.TextField(blank=True, null=True)
    def full_name(self):
        if self.firma:
            return f"{self.firma} - ({self.name})"
        return self.name

    def __str__(self):
        return f"{self.full_name()}, {self.strasse}, {self.plz} {self.ort}, {self.land}"