from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Autenticación y Semáforo Post-Login
    path('login/', auth_views.LoginView.as_view(template_name='usuarios/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.redireccion_post_login, name='inicio'),

    # Perfil y Firma Digital del Patólogo
    path('perfil/', views.mi_perfil, name='mi_perfil'),

    # Panel Administrativo de Usuarios y Laboratorios
    path('admin-panel/', views.admin_gestion_rapida, name='admin_gestion_rapida'),
]