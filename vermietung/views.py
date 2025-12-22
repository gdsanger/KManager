from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

def vermietung_home(request):
    return render(request, 'vermietung/vermietung_dashboard.html')