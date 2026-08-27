from django.shortcuts import redirect
from django.urls import reverse

class RedirigirUsuariosAutenticadosMiddleware:
    """
    Middleware que intercepta a los usuarios que ya iniciaron sesión 
    y los aleja de la pantalla de Login.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificamos si el usuario está autenticado y si la ruta es la del login 2FA
        if request.user.is_authenticated and request.path == reverse('two_factor:login'):
            # Lo redirigimos a nuestro controlador de tráfico principal
            return redirect('inicio') 
            
        return self.get_response(request)