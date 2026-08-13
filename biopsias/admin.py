from django.contrib import admin
from .models import Medico, TipoExamen, Examen, Comentario

admin.site.register(Medico)
admin.site.register(TipoExamen)
admin.site.register(Examen)
admin.site.register(Comentario)
