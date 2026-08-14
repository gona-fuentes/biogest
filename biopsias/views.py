from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Examen, Comentario, TipoExamen
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
    
    if request.method == 'POST':
        action = request.POST.get('action')
        examen_id = request.POST.get('examen_id')
        muestra = get_object_or_404(Examen, id=examen_id)

        if action == 'enviar_chat' and muestra.estado != 'Finalizado':
            mensaje = request.POST.get('mensaje', '').strip()
            if mensaje:
                Comentario.objects.create(examen=muestra, user=request.user, comentario=mensaje, tipo='Mensaje / Consulta')
                muestra.alerta_chat_patologo = True
                muestra.alerta_chat_laboratorio = False
                muestra.save()
        
        elif action == 'marcar_leido':
            muestra.alerta_chat_laboratorio = False
            muestra.save()
            
        return redirect('dashboard')

    muestras = Examen.objects.all().order_by('-fecha_recepcion')
    if query:
        muestras = muestras.filter(
            Q(paciente_rut__icontains=query) |
            Q(paciente_nombre__icontains=query) |
            Q(numero_correlativo__icontains=query)
        )

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
    query_historial = request.GET.get('q_historial', '')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        examen_id = request.POST.get('examen_id')
        muestra = get_object_or_404(Examen, id=examen_id)

        if action == 'enviar_chat':
            mensaje = request.POST.get('mensaje', '').strip()
            if mensaje:
                Comentario.objects.create(examen=muestra, user=request.user, comentario=mensaje, tipo='Mensaje / Consulta')
                muestra.alerta_chat_laboratorio = True
                muestra.alerta_chat_patologo = False
                muestra.save()
        
        elif action == 'marcar_leido':
            muestra.alerta_chat_patologo = False
            muestra.save()
            
        return redirect('dashboard_patologo')

    # Muestras pendientes para las CARDS
    muestras_pendientes = Examen.objects.exclude(estado='Finalizado').order_by('-fecha_recepcion')

    # Histórico general / Buscador de Exámenes
    historial_examenes = Examen.objects.all().order_by('-fecha_recepcion')
    if query_historial:
        historial_examenes = historial_examenes.filter(
            Q(paciente_rut__icontains=query_historial) |
            Q(paciente_nombre__icontains=query_historial) |
            Q(numero_correlativo__icontains=query_historial)
        )

    return render(request, 'dashboard_patologo.html', {
        'muestras_pendientes': muestras_pendientes,
        'historial_examenes': historial_examenes,
        'query_historial': query_historial,
    })
# 3. Detalle Muestra (Responde mensaje y quita la alerta pendiente)



@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def detalle_muestra(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    es_patologo_user = es_patologo(request.user)
    
    if request.method == 'POST' and es_patologo_user:
        # Aquí solo queda la lógica del cambio de estado y diagnóstico médico
        nuevo_estado = request.POST.get('estado')
        nota_medica = request.POST.get('nota')
        
        if nuevo_estado and nuevo_estado != muestra.estado:
            estado_anterior = muestra.estado
            muestra.estado = nuevo_estado
            muestra.save()
            Comentario.objects.create(examen=muestra, user=request.user, comentario=f"Cambió el estado a '{nuevo_estado}'", tipo='Cambio de estado')

        if nota_medica:
            Comentario.objects.create(examen=muestra, user=request.user, comentario=nota_medica, tipo='Diagnóstico / Nota')
            
        return redirect('detalle_muestra', examen_id=muestra.id)

    # Solo enviamos al historial los eventos legales, excluyendo los chats informales
    historial_list = muestra.comentarios.exclude(tipo='Mensaje / Consulta').order_by('-created_at')
    paginator = Paginator(historial_list, 5)
    historial = paginator.get_page(request.GET.get('page'))

    return render(request, 'detalle_muestra.html', {
        'muestra': muestra,
        'historial': historial,
        'es_patologo': es_patologo_user
    })





from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def detalle_muestra(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    es_patologo_user = es_patologo(request.user)
    
    # Procesamiento del método POST (Acciones: enviar_chat, actualizar_diagnostico)
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 💬 ACCIÓN 1: Enviar mensaje por el Chat Interno
        if action == 'enviar_chat':
            mensaje = request.POST.get('mensaje', '').strip()
            if mensaje:
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=mensaje,
                    tipo='Mensaje / Consulta'
                )
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        # 📝 ACCIÓN 2: Diagnóstico y Cambio de Estado (Exclusivo Patólogo)
        elif es_patologo_user and action == 'actualizar_diagnostico':
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

    # Paginación del historial/comentarios para solicitudes GET
    historial_list = muestra.comentarios.all().order_by('-created_at')
    paginator = Paginator(historial_list, 5)
    page_number = request.GET.get('page')
    historial = paginator.get_page(page_number)

    # Cargar todos los tipos de examen activos desde la base de datos
    tipos_examen_disponibles = TipoExamen.objects.filter(activo=True)

    return render(request, 'detalle_muestra.html', {
        'muestra': muestra,
        'historial': historial,
        'es_patologo': es_patologo_user,
        'tipos_examen_disponibles': tipos_examen_disponibles,
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