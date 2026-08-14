from django.contrib import admin
from .models import TipoExamen, Examen, Comentario

admin.site.register(Examen)
admin.site.register(Comentario)


@admin.register(TipoExamen)
class TipoExamenAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    search_fields = ('nombre',)
    list_filter = ('activo',)