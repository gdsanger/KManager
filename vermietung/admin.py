from django.contrib import admin
from .models import Stanorte, MietObjekt, OBJEKT_TYPE


@admin.register(Stanorte)
class StanorteAdmin(admin.ModelAdmin):
    list_display = ('name', 'adresse', 'plz', 'ort', 'land')
    search_fields = ('name', 'adresse', 'ort', 'land')