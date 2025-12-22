
from django.db import models

OBJEKT_TYPE = [
       ('GEBAEUDE','Gebäude'),
        ('RAUM','Raum'),
        ('CONTAINER','Container'),
        ('STELLPLATZ','Stellplatz'),
        ('KFZ','KFZ'),
        ('SONSTIGES','Sonstiges'),
    ]


class Stanorte(models.Model):
    name = models.CharField(max_length=100)
    adresse = models.CharField(max_length=255)
    plz = models.CharField(max_length=10)
    ort = models.CharField(max_length=100)  
    land = models.CharField(max_length=100)
    beschreibung = models.TextField()

    def __str__(self):
        return self.name

class MietObjekt(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=OBJEKT_TYPE)
    beschreibung = models.TextField()
    fläche = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    höhe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    breite = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tiefe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    standort = models.ForeignKey(Stanorte, on_delete=models.CASCADE)
    mietpreis = models.DecimalField(max_digits=10, decimal_places=2)
    verfuegbar = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
