from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Examen, Comentario
from .forms import ExamenForm
import uuid




def es_laboratorio(user):
    return user.groups.filter(name='Laboratorio').exists() or user.is_superuser

def es_patologo(user):
    return user.groups.filter(name='Patólogo').exists() or user.is_superuser




@login_required
def redireccion_post_login(request):
    """
    Controlador de tráfico: Revisa a qué grupo pertenece el usuario
    y lo redirige a su panel correspondiente.
    """
    if request.user.groups.filter(name='Patólogo').exists():
        return redirect('dashboard_patologo')
    
  
    return redirect('dashboard')







@login_required
@user_passes_test(es_laboratorio, login_url='/inicio/')
def dashboard_laboratorio(request):
    # Traemos todas las muestras ordenadas de la más nueva a la más antigua
    muestras = Examen.objects.all().order_by('-created_at')
    return render(request, 'dashboard.html', {'muestras': muestras})

@login_required
@user_passes_test(es_laboratorio, login_url='/inicio/')
def registrar_biopsia(request):
    if request.method == 'POST':
        form = ExamenForm(request.POST)
        if form.is_valid():
            # Guardamos el formulario en memoria sin enviarlo a la BD aún
            nueva_muestra = form.save(commit=False)
            
            # Generamos el código correlativo automático (Ej: BIO-A1B2C3)
            codigo_unico = uuid.uuid4().hex[:6].upper()
            nueva_muestra.numero_correlativo = f"BIO-{codigo_unico}"
            
            # Asignamos el estado inicial
            nueva_muestra.estado = 'Ingresada'
            
            # Ahora sí, guardamos en la base de datos
            nueva_muestra.save()
            return redirect('dashboard')
    else:
        form = ExamenForm()
        
    return render(request, 'nueva_biopsia.html', {'form': form})


@login_required
@user_passes_test(es_patologo, login_url='/inicio/')
def dashboard_patologo(request):
    # Traemos las muestras que no están finalizadas para la bandeja de entrada
    muestras_pendientes = Examen.objects.exclude(estado='Finalizado').order_by('-fecha_recepcion')
    return render(request, 'dashboard_patologo.html', {'muestras': muestras_pendientes})

@login_required
@user_passes_test(es_patologo, login_url='/inicio/')
def detalle_muestra(request, examen_id):
    # Buscamos la muestra específica
    muestra = get_object_or_404(Examen, id=examen_id)
    # Traemos todo el historial de trazabilidad de esta muestra
    historial = muestra.comentarios.all().order_by('-created_at')

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        nota_medica = request.POST.get('nota')
        
        # 1. Actualizamos el estado de la muestra si cambió
        if nuevo_estado and nuevo_estado != muestra.estado:
            estado_anterior = muestra.estado
            muestra.estado = nuevo_estado
            muestra.save()
            
            # MAGIA DE TRAZABILIDAD: Registramos el cambio de estado automáticamente
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario=f"Cambió el estado de '{estado_anterior}' a '{nuevo_estado}'",
                tipo='Cambio de estado'
            )

        # 2. Guardamos la nota diagnóstica si el patólogo escribió una
        if nota_medica:
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario=nota_medica,
                tipo='Diagnóstico / Nota'
            )
            
        return redirect('detalle_muestra', examen_id=muestra.id)

    return render(request, 'detalle_muestra.html', {
        'muestra': muestra,
        'historial': historial
    })


