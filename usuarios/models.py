from django.contrib.auth.models import AbstractUser
from django.db import models

class Laboratorio(models.Model):
    nombre = models.CharField(max_length=255)
    rut = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

class User(AbstractUser):
    laboratorio = models.ForeignKey(Laboratorio, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Campos para Firma Digital y Validez Legal
    firma = models.ImageField(upload_to='firmas/', null=True, blank=True, help_text="Imagen de la firma hológrafa transparente")
    registro_medico = models.CharField(max_length=100, blank=True, null=True, help_text="N° de Registro Nacional de Prestadores de Salud")
    pin_firma = models.CharField(max_length=6, blank=True, null=True, help_text="PIN de 4-6 dígitos para autorizar el cierre del informe")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_full_name() or 'Sin Nombre'})"