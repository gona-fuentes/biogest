from django.contrib.auth.models import AbstractUser
from django.db import models

class Laboratorio(models.Model):
    nombre = models.CharField(max_length=255)
    rut = models.CharField(max_length=20, unique=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Laboratorio"
        verbose_name_plural = "Laboratorios"

    def __str__(self):
        return self.nombre


class User(AbstractUser):
    laboratorio = models.ForeignKey(
        Laboratorio, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='usuarios'
    )
    
    # Campos de Firma Digital y Validez Legal de Patólogos
    firma = models.ImageField(
        upload_to='firmas/', 
        null=True, 
        blank=True, 
        help_text="Imagen de la firma hológrafa transparente (PNG recomendado)"
    )
    registro_medico = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="N° de Registro Nacional de Prestadores de Salud (RNS)"
    )
    pin_firma = models.CharField(
        max_length=6, 
        blank=True, 
        null=True, 
        help_text="PIN de 4-6 dígitos para autorizar la firma del informe"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        nombre_completo = self.get_full_name()
        return f"{self.username} ({nombre_completo if nombre_completo else 'Sin nombre'})"