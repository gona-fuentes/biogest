from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Laboratorio


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'first_name', 'last_name', 'laboratorio', 'registro_medico', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Información Profesional & Firma Digital', {
            'fields': ('laboratorio', 'registro_medico', 'firma', 'pin_firma')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Profesional & Firma Digital', {
            'fields': ('laboratorio', 'registro_medico', 'firma', 'pin_firma')
        }),
    )


@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rut', 'email', 'created_at')
    search_fields = ('nombre', 'rut')