"""URL-Konfiguration des Finanzen-Moduls."""
from django.urls import path

from . import views

app_name = 'finanzen'

urlpatterns = [
    path('', views.home, name='home'),
    path('artikelumsatz/', views.item_revenue, name='item_revenue'),
    path(
        'artikelumsatz/<str:item_key>/monatsverlauf/',
        views.item_revenue_months,
        name='item_revenue_months',
    ),
]
