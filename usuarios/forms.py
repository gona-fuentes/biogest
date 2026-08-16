from django import forms
from django.contrib.auth import get_user_model
from .models import Laboratorio

User = get_user_model()


class PerfilPatologoForm(forms.ModelForm):
    """ Formulario para que el patólogo actualice sus datos y firma digital """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'registro_medico', 'firma', 'pin_firma']
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'registro_medico': 'N° Registro Médico (RNS)',
            'firma': 'Firma Digitalizada (Imagen PNG)',
            'pin_firma': 'PIN de Seguridad'
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'registro_medico': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm', 'placeholder': 'Ej: 123456-MINSAL'}),
            'pin_firma': forms.PasswordInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm', 'placeholder': '****', 'maxlength': '6'}),
        }


class CrearUsuarioAdminForm(forms.ModelForm):
    """ Formulario administrativo para la creación rápida de usuarios con roles """
    rol = forms.ChoiceField(
        choices=[('Laboratorio', 'Clínico / Laboratorio'), ('Patólogo', 'Patólogo')],
        label="Rol del Usuario",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'})
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'laboratorio', 'password']
        labels = {
            'username': 'Nombre de Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'laboratorio': 'Laboratorio Asignado',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
            'laboratorio': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica focus:outline-none text-sm'}),
        }