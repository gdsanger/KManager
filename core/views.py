from django.shortcuts import render


def home(request):
    """Home page view"""
    return render(request, 'home.html')


def htmx_demo(request):
    """HTMX demo view"""
    return render(request, 'htmx_demo.html')

