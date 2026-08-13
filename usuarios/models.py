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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username