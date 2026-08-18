from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Rutas de Autenticación y Usuarios
    path('', include('usuarios.urls')),
    
    # Rutas Médicas y de Biopsias
    path('biopsias/', include('biopsias.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)