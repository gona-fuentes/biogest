from django.contrib import admin
from .models import Paciente, Medico, TipoExamen, Examen, Comentario, PlantillaPatologo


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('rut', 'nombre_completo', 'sexo', 'fecha_nacimiento', 'created_at')
    search_fields = ('rut', 'nombre_completo', 'email')


@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'created_at')
    search_fields = ('nombre',)


@admin.register(TipoExamen)
class TipoExamenAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    list_display = ('numero_correlativo', 'paciente', 'tipo_examen', 'estado', 'patologo', 'resultado_critico', 'informe_cerrado', 'fecha_recepcion')
    list_filter = ('estado', 'resultado_critico', 'informe_cerrado', 'tipo_examen')
    search_fields = ('numero_correlativo', 'paciente__rut', 'paciente__nombre_completo')
    raw_id_fields = ('paciente',)


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ('examen', 'user', 'tipo', 'created_at')
    list_filter = ('tipo',)
    search_fields = ('examen__numero_correlativo', 'comentario', 'user__username')


@admin.register(PlantillaPatologo)
class PlantillaPatologoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'patologo', 'tipo_examen', 'created_at')
    list_filter = ('tipo_examen', 'patologo')
    search_fields = ('titulo', 'texto_predefinido', 'patologo__username')