from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # EL LOGIN ANTIGUO SE BORRÓ (El 2FA toma el control)
    
    # Actualizamos el Logout para que te lleve al login del 2FA
    path('logout/', auth_views.LogoutView.as_view(next_page='two_factor:login'), name='logout'),
    
    path('', views.redireccion_post_login, name='inicio'),

    # Perfil y Firma Digital del Patólogo
    path('perfil/', views.mi_perfil, name='mi_perfil'),

    # Panel Administrativo de Usuarios y Laboratorios
    path('admin-panel/', views.admin_gestion_rapida, name='admin_gestion_rapida'),
]