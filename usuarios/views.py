from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from .models import Laboratorio
from .forms import PerfilPatologoForm, CrearUsuarioAdminForm

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
    Panel de administración centralizada para registrar usuarios y laboratorios.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'crear_usuario':
            form_user = CrearUsuarioAdminForm(request.POST)
            if form_user.is_valid():
                user = form_user.save(commit=False)
                user.set_password(form_user.cleaned_data['password'])
                user.save()
                
                # Asignación de Grupo / Rol
                grupo_nombre = form_user.cleaned_data['rol']
                grupo, _ = Group.objects.get_or_create(name=grupo_nombre)
                user.groups.add(grupo)
                
                messages.success(request, f"Usuario '{user.username}' registrado con éxito en el rol '{grupo_nombre}'.")
                return redirect('admin_gestion_rapida')
            else:
                messages.error(request, "No se pudo registrar el usuario. Verifique la información.")

        elif action == 'crear_laboratorio':
            nombre = request.POST.get('nombre_lab', '').strip()
            rut = request.POST.get('rut_lab', '').strip()
            if nombre and rut:
                Laboratorio.objects.create(nombre=nombre, rut=rut)
                messages.success(request, f"Laboratorio '{nombre}' registrado exitosamente.")
                return redirect('admin_gestion_rapida')
            else:
                messages.error(request, "Nombre y RUT del laboratorio son obligatorios.")

    form_user = CrearUsuarioAdminForm()
    laboratorios = Laboratorio.objects.all().order_by('nombre')
    usuarios = User.objects.all().order_by('-date_joined')

    return render(request, 'usuarios/admin_gestion_rapida.html', {
        'form_user': form_user,
        'laboratorios': laboratorios,
        'usuarios': usuarios,
    })