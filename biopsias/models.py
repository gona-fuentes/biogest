from django.db import models
from django.conf import settings
from usuarios.models import Laboratorio

class Medico(models.Model):
    nombre = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

class TipoExamen(models.Model):
    nombre = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

class Examen(models.Model):
    numero_correlativo = models.CharField(max_length=100, unique=True)
    fecha_toma = models.DateField()
    fecha_recepcion = models.DateField()
    fecha_entrega = models.DateField(null=True, blank=True)
    
    paciente_nombre = models.CharField(max_length=255)
    paciente_rut = models.CharField(max_length=20)
    
    medico_solicitante = models.ForeignKey(Medico, on_delete=models.SET_NULL, null=True)
    cantidad_muestras = models.IntegerField()
    numero_fragmentos = models.IntegerField()
    
    tincion_rutina = models.CharField(max_length=255, blank=True, null=True)
    tecnicas_especiales = models.TextField(blank=True, null=True)
    
    # Relaciones principales (Llaves Foráneas)
    tipo_examen = models.ForeignKey(TipoExamen, on_delete=models.PROTECT)
    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.PROTECT)
    patologo = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='examenes_asignados'
    )
    
    estado = models.CharField(max_length=50) # Ej: 'En proceso', 'Finalizado'
    archivo_informe = models.FileField(upload_to='informes/', null=True, blank=True)
    galeria_imagenes = models.JSONField(null=True, blank=True) # Guardará rutas de imágenes múltiples
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.numero_correlativo} - {self.paciente_nombre}"

class Comentario(models.Model):
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE, related_name='comentarios')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comentario = models.TextField()
    tipo = models.CharField(max_length=100) # Ej: 'Nota interna', 'Cambio de estado'
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comentario de {self.user} en {self.examen}"