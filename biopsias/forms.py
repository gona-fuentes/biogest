from django import forms
from .models import Examen, Laboratorio, Medico, PlantillaPatologo
from django.core.exceptions import ValidationError
from itertools import cycle

class ExamenForm(forms.ModelForm):
    # --- Campos para la Ficha Clínica del Paciente (Todos Obligatorios) ---
    rut = forms.CharField(max_length=20, label='RUT del Paciente', widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    nombre_completo = forms.CharField(max_length=255, label='Nombre Completo', widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    fecha_nacimiento = forms.DateField(label='Fecha de Nacimiento', widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    sexo = forms.ChoiceField(choices=[('', 'Seleccione...'), ('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    telefono = forms.CharField(max_length=20, label='Teléfono', widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    email = forms.EmailField(label='Correo Electrónico', widget=forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))

    field_order = [
        'rut', 'nombre_completo', 'fecha_nacimiento', 'sexo', 'telefono', 'email',
        'tipo_examen', 'medico_solicitante', 'laboratorio', 
        'fecha_toma', 'fecha_recepcion', 'cantidad_muestras', 'numero_fragmentos'
    ]

    class Meta:
        model = Examen
        fields = [
            'tipo_examen', 'medico_solicitante', 'laboratorio', 
            'fecha_toma', 'fecha_recepcion', 'cantidad_muestras', 'numero_fragmentos'
        ]
        widgets = {
            'fecha_toma': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'fecha_recepcion': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'tipo_examen': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'medico_solicitante': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'laboratorio': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'cantidad_muestras': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'numero_fragmentos': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
        }

    # NUEVO: Lógica de purificación anti-espagueti para el RUT
    def clean_rut(self):
        rut = self.cleaned_data.get('rut', '')
        
        # 1. Limpiamos puntos y guiones para hacer el cálculo
        rut_limpio = rut.replace('.', '').replace('-', '').upper()

        if not rut_limpio or len(rut_limpio) < 2:
            raise ValidationError("Formato de RUT demasiado corto.")

        cuerpo = rut_limpio[:-1]
        dv_ingresado = rut_limpio[-1]

        if not cuerpo.isdigit():
            raise ValidationError("El cuerpo del RUT debe ser numérico.")

        # 2. Algoritmo Módulo 11
        reverso = map(int, reversed(cuerpo))
        factores = cycle(range(2, 8))
        suma = sum(d * f for d, f in zip(reverso, factores))
        modulo = 11 - (suma % 11)

        if modulo == 11:
            dv_calculado = '0'
        elif modulo == 10:
            dv_calculado = 'K'
        else:
            dv_calculado = str(modulo)

        # 3. Verificamos si coinciden
        if dv_ingresado != dv_calculado:
            raise ValidationError("El RUT ingresado no es válido (Dígito Verificador incorrecto).")

        return rut # Si la matemática cuadra, lo dejamos pasar

class PlantillaPatologoForm(forms.ModelForm):
    class Meta:
        model = PlantillaPatologo
        fields = ['tipo_examen', 'titulo', 'texto_predefinido']
        labels = {
            'tipo_examen': 'Tipo de Examen Asociado',
            'titulo': 'Título de la Plantilla',
            'texto_predefinido': 'Texto Diagnóstico'
        }
        widgets = {
            'tipo_examen': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}),
            'titulo': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica', 'placeholder': 'Ej: Biopsia Piel - Nevus Melanocítico'}),
            'texto_predefinido': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica font-mono', 'rows': 6}),
        }