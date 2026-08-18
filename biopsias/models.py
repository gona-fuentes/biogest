from django.db import models
from django.conf import settings
from usuarios.models import *
from simple_history.models import HistoricalRecords

class Paciente(models.Model):
    rut = models.CharField(max_length=20, unique=True)
    nombre_completo = models.CharField(max_length=255)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=20, choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.nombre_completo} - {self.rut}"

class Medico(models.Model):
    nombre = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class TipoExamen(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    plantilla_preinforme = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Plantilla de Pre-Informe",
        help_text="Escriba la estructura predeterminada que verá el patólogo al redactar este examen."
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Examen(models.Model):
    numero_correlativo = models.CharField(max_length=100, unique=True)
    fecha_toma = models.DateField()
    fecha_recepcion = models.DateField()
    fecha_entrega = models.DateField(null=True, blank=True)
    
    # Vinculación a Ficha Clínica
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name='examenes')
    
    medico_solicitante = models.ForeignKey(Medico, on_delete=models.SET_NULL, null=True)
    cantidad_muestras = models.IntegerField()
    numero_fragmentos = models.IntegerField()
    
    tincion_rutina = models.CharField(max_length=255, blank=True, null=True)
    tecnicas_especiales = models.TextField(blank=True, null=True)
    
    alerta_chat_patologo = models.BooleanField(default=False)
    alerta_chat_laboratorio = models.BooleanField(default=False)

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
    galeria_imagenes = models.JSONField(null=True, blank=True) 
    
    # Nuevos controles de seguridad médica
    resultado_critico = models.BooleanField(default=False)
    informe_cerrado = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.numero_correlativo} - {self.paciente.nombre_completo}"

class Comentario(models.Model):
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE, related_name='comentarios')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comentario = models.TextField()
    tipo = models.CharField(max_length=100) # Ej: 'Nota interna', 'Cambio de estado', 'Apertura Admin'
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comentario de {self.user} en {self.examen}"


class PlantillaPatologo(models.Model):
    patologo = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='plantillas_personales'
    )
    tipo_examen = models.ForeignKey(TipoExamen, on_delete=models.CASCADE, related_name='plantillas_patologo')
    titulo = models.CharField(max_length=150, help_text="Ej: Gastritis Crónica Antral Leve")
    texto_predefinido = models.TextField(help_text="Texto diagnóstico que se inyectará en el informe")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plantilla Personal de Patólogo"
        verbose_name_plural = "Plantillas Personales de Patólogos"

    def __str__(self):
        return f"{self.patologo.username} - {self.tipo_examen.nombre}: {self.titulo}"