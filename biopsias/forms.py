from django import forms
from .models import Examen, PlantillaPatologo

class ExamenForm(forms.ModelForm):
    # --- Campos para la Ficha Clínica del Paciente ---
    rut = forms.CharField(max_length=20, label='RUT del Paciente', widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    nombre_completo = forms.CharField(max_length=255, label='Nombre Completo', widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    fecha_nacimiento = forms.DateField(required=False, label='Fecha de Nacimiento', widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    sexo = forms.ChoiceField(choices=[('', 'Seleccione...'), ('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], required=False, widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    telefono = forms.CharField(max_length=20, required=False, label='Teléfono', widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))
    email = forms.EmailField(required=False, label='Correo Electrónico', widget=forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded focus:ring-clinica'}))

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
        
        # 1. Quitamos todo lo que no sea número o letra 'K', y lo pasamos a mayúscula
        rut_limpio = ''.join(c for c in rut if c.isalnum()).upper()
        
        # 2. Si tiene longitud válida, lo formateamos matemáticamente a XX.XXX.XXX-X
        if len(rut_limpio) > 1:
            cuerpo = rut_limpio[:-1]
            dv = rut_limpio[-1]
            
            try:
                # El truco del formato {:,} pone comas cada 3 números, luego las cambiamos por puntos
                cuerpo_formateado = "{:,}".format(int(cuerpo)).replace(',', '.')
                return f"{cuerpo_formateado}-{dv}"
            except ValueError:
                pass # Si el cuerpo no es un número válido, lo deja pasar para que el modelo lo rechace
                
        return rut


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