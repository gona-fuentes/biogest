from django import forms
from .models import Examen

class ExamenForm(forms.ModelForm):
    class Meta:
        model = Examen
        # Excluimos campos que se generan automáticamente o que llena el patólogo después
        fields = [
            'paciente_nombre', 'paciente_rut', 'fecha_toma', 'fecha_recepcion',
            'medico_solicitante', 'laboratorio', 'tipo_examen', 
            'cantidad_muestras', 'numero_fragmentos'
        ]
        
        # Le damos un poco de estilo base de Tailwind a los inputs
        widgets = {
            'fecha_toma': forms.DateInput(attrs={'type': 'date'}),
            'fecha_recepcion': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicamos clases de Tailwind a todos los campos dinámicamente
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-clinica'
            })

            