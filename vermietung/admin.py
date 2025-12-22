from django.contrib import admin
from .models import MietObjekt, OBJEKT_TYPE


@admin.register(MietObjekt)
class MietObjektAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'beschreibung', 'fläche', 'höhe', 'breite', 'tiefe', 'standort', 'mietpreis', 'verfuegbar')
    search_fields = ('name', 'standort__strasse', 'standort__ort', 'standort')
    list_filter = ('type', 'verfuegbar', 'standort')