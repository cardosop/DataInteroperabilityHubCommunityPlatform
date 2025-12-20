from django.urls import path
from . import views

urlpatterns = [
    path('', views.health_check, name='health'),
    path('circuit-breakers/', views.circuit_breaker_status, name='circuit_breaker_status'),
]

