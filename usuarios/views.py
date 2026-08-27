from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from .models import Laboratorio
from .forms import PerfilPatologoForm, CrearUsuarioAdminForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


@login_required
def redireccion_post_login(request):
    """
    Controlador post-login: Revisa el rol del usuario y lo redirige a su panel.
    """
    if request.user.groups.filter(name='Patólogo').exists():
        return redirect('dashboard_patologo')
    return redirect('dashboard')


@login_required
def mi_perfil(request):
    """
    Permite al patólogo o usuario actualizar sus datos personales,
    registro médico, PIN y firma digital.
    """
    if request.method == 'POST':
        form = PerfilPatologoForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil y firma digital actualizados correctamente.")
            return redirect('mi_perfil')
        else:
            messages.error(request, "Error al guardar el perfil. Revise los datos.")
    else:
        form = PerfilPatologoForm(instance=request.user)
    
    return render(request, 'usuarios/mi_perfil.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/inicio/')
def admin_gestion_rapida(request):
    """
    Panel de administración centralizada para gestionar usuarios y laboratorios.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # --- 1. CREAR USUARIO ---
        if action == 'crear_usuario':
            form_user = CrearUsuarioAdminForm(request.POST)
            if form_user.is_valid():
                user = form_user.save(commit=False)
                user.set_password(form_user.cleaned_data['password'])
                user.save()
                
                grupo_nombre = form_user.cleaned_data['rol']
                grupo, _ = Group.objects.get_or_create(name=grupo_nombre)
                user.groups.add(grupo)
                
                messages.success(request, f"Usuario '{user.username}' registrado con éxito en el rol '{grupo_nombre}'.")
                return redirect('admin_gestion_rapida')
            else:
                messages.error(request, "Fallo al registrar la cuenta. Revisa los datos ingresados.")

        # --- 2. EDITAR USUARIO ---
        elif action == 'editar_usuario':
            user_id = request.POST.get('user_id')
            usuario_edit = get_object_or_404(User, id=user_id)
            
            usuario_edit.username = request.POST.get('username', usuario_edit.username).strip()
            usuario_edit.first_name = request.POST.get('first_name', '').strip()
            usuario_edit.last_name = request.POST.get('last_name', '').strip()
            usuario_edit.email = request.POST.get('email', '').strip()
            
            lab_id = request.POST.get('laboratorio')
            if lab_id:
                usuario_edit.laboratorio_id = lab_id
            else:
                usuario_edit.laboratorio = None
                
            rol = request.POST.get('rol')
            if rol:
                usuario_edit.groups.clear()
                grupo, _ = Group.objects.get_or_create(name=rol)
                usuario_edit.groups.add(grupo)
                
            new_password = request.POST.get('password')
            if new_password and new_password.strip():
                try:
                    validate_password(new_password, user=usuario_edit)
                    usuario_edit.set_password(new_password)
                except ValidationError:
                    mensaje_amigable = (
                        "Para proteger la cuenta, la nueva contraseña debe ser más segura. "
                        "Asegúrate de que tenga al menos 8 caracteres, incluya letras y números, "
                        "y no sea demasiado común."
                    )
                    
                    form_user = CrearUsuarioAdminForm()
                    laboratorios = Laboratorio.objects.all().order_by('nombre')
                    usuarios = User.objects.all().order_by('-date_joined')
                    
                    return render(request, 'usuarios/admin_gestion_rapida.html', {
                        'form_user': form_user,
                        'laboratorios': laboratorios,
                        'usuarios': usuarios,
                        'error_edicion': mensaje_amigable, 
                        'usuario_editado': usuario_edit    
                    })
                
            usuario_edit.save()
            messages.success(request, f"Usuario '{usuario_edit.username}' actualizado correctamente.")
            return redirect('admin_gestion_rapida')

        # --- 3. CREAR LABORATORIO ---
        elif action == 'crear_laboratorio':
            nombre = request.POST.get('nombre_lab', '').strip()
            rut = request.POST.get('rut_lab', '').strip()
            if nombre and rut:
                Laboratorio.objects.create(nombre=nombre, rut=rut)
                messages.success(request, f"Laboratorio '{nombre}' registrado exitosamente.")
                return redirect('admin_gestion_rapida')
            else:
                messages.error(request, "Nombre y RUT del laboratorio son obligatorios.")

        # --- 4. EDITAR LABORATORIO ---
        elif action == 'editar_laboratorio':
            lab_id = request.POST.get('lab_id')
            lab = get_object_or_404(Laboratorio, id=lab_id)
            nuevo_nombre = request.POST.get('nombre_lab', '').strip()
            nuevo_rut = request.POST.get('rut_lab', '').strip()
            
            if nuevo_nombre and nuevo_rut:
                lab.nombre = nuevo_nombre
                lab.rut = nuevo_rut
                lab.save()
                messages.success(request, f"Datos del laboratorio '{nuevo_nombre}' actualizados correctamente.")
            else:
                messages.error(request, "Los campos Nombre y RUT no pueden quedar vacíos.")
            return redirect('admin_gestion_rapida')

        # --- 5. ELIMINAR LABORATORIO ---
        elif action == 'eliminar_laboratorio':
            lab_id = request.POST.get('lab_id')
            lab = get_object_or_404(Laboratorio, id=lab_id)
            nombre_borrado = lab.nombre
            
            lab.delete()
            messages.success(request, f"Laboratorio '{nombre_borrado}' eliminado definitivamente del sistema.")
            return redirect('admin_gestion_rapida')

# --- 6. HABILITAR / DESHABILITAR USUARIO ---
        elif action == 'toggle_estado_usuario':
            user_id = request.POST.get('user_id')
            usuario_toggle = get_object_or_404(User, id=user_id)
            
            # Medida de seguridad: Evitar que el administrador principal se bloquee a sí mismo
            if usuario_toggle == request.user:
                messages.error(request, "Por seguridad, no puedes deshabilitar tu propia cuenta activa.")
            else:
                # Invertimos el estado actual (Si es True pasa a False y viceversa)
                usuario_toggle.is_active = not usuario_toggle.is_active
                usuario_toggle.save()
                
                texto_estado = "habilitada" if usuario_toggle.is_active else "deshabilitada"
                messages.success(request, f"La cuenta del usuario '{usuario_toggle.username}' ha sido {texto_estado} exitosamente.")
                
            return redirect('admin_gestion_rapida')



    # Contexto base
    form_user = CrearUsuarioAdminForm()
    laboratorios = Laboratorio.objects.all().order_by('nombre')
    usuarios = User.objects.all().order_by('-date_joined')

    return render(request, 'usuarios/admin_gestion_rapida.html', {
        'form_user': form_user,
        'laboratorios': laboratorios,
        'usuarios': usuarios,
    })