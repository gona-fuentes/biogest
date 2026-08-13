from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Examen, Comentario
from django.db.models import Q
from .forms import ExamenForm
import uuid
from django.core.paginator import Paginator






def es_laboratorio(user):
    return user.groups.filter(name='Laboratorio').exists() or user.is_superuser

def es_patologo(user):
    return user.groups.filter(name='Patólogo').exists() or user.is_superuser

def es_personal_autorizado(user):
    return user.groups.filter(name__in=['Laboratorio', 'Patólogo']).exists() or user.is_superuser


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
    query = request.GET.get('q', '')
    
    if query:
        # Si buscamos algo, filtramos
        muestras = Examen.objects.filter(
            Q(numero_correlativo__icontains=query) |
            Q(paciente_rut__icontains=query) |
            Q(paciente_nombre__icontains=query)
        ).order_by('-created_at')
    else:

        muestras = Examen.objects.all().order_by('-created_at')
        
    return render(request, 'dashboard.html', {'muestras': muestras, 'query': query})

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
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def detalle_muestra(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    es_patologo_user = es_patologo(request.user)
    
    if request.method == 'POST':
        # Si un usuario de laboratorio intenta enviar el formulario, se bloquea la edición
        if not es_patologo_user:
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        nuevo_estado = request.POST.get('estado')
        nota_medica = request.POST.get('nota')
        
        if nuevo_estado and nuevo_estado != muestra.estado:
            estado_anterior = muestra.estado
            muestra.estado = nuevo_estado
            muestra.save()
            
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario=f"Cambió el estado de '{estado_anterior}' a '{nuevo_estado}'",
                tipo='Cambio de estado'
            )

        if nota_medica:
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario=nota_medica,
                tipo='Diagnóstico / Nota'
            )
            
        return redirect('detalle_muestra', examen_id=muestra.id)

    historial_list = muestra.comentarios.all().order_by('-created_at')
    paginator = Paginator(historial_list, 5)
    
    page_number = request.GET.get('page')
    historial = paginator.get_page(page_number)

    return render(request, 'detalle_muestra.html', {
        'muestra': muestra,
        'historial': historial,
        'es_patologo': es_patologo_user # Enviamos la bandera a la plantilla
    })





@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def generar_informe_pdf(request, examen_id):
    # Buscamos la muestra y su diagnóstico final
    muestra = get_object_or_404(Examen, id=examen_id)
    diagnostico_final = muestra.comentarios.filter(tipo='Diagnóstico / Nota').order_by('-created_at').first()
    
    # Renderizamos la plantilla HTML normal (El navegador hará el resto)
    return render(request, 'informe_pdf.html', {
        'muestra': muestra,
        'diagnostico': diagnostico_final
    })