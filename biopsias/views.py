from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
import uuid

from .models import Examen, Comentario, TipoExamen, Paciente
from .forms import ExamenForm


# --- VALIDACIONES DE ROLES ---

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


# --- VISTAS DE LABORATORIO ---

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
        # Búsqueda usando las relaciones de la llave foránea (paciente__campo)
        muestras = muestras.filter(
            Q(paciente__rut__icontains=query) |
            Q(paciente__nombre_completo__icontains=query) |
            Q(numero_correlativo__icontains=query)
        )

    return render(request, 'dashboard.html', {'muestras': muestras, 'query': query})


@login_required
@user_passes_test(es_laboratorio, login_url='/inicio/')
def registrar_biopsia(request):
    if request.method == 'POST':
        form = ExamenForm(request.POST)
        if form.is_valid():
            # 1. Obtener o crear al paciente en la base de datos
            rut = form.cleaned_data['rut']
            paciente, created = Paciente.objects.get_or_create(
                rut=rut,
                defaults={
                    'nombre_completo': form.cleaned_data['nombre_completo'],
                    'fecha_nacimiento': form.cleaned_data.get('fecha_nacimiento'),
                    'sexo': form.cleaned_data.get('sexo'),
                    'telefono': form.cleaned_data.get('telefono'),
                    'email': form.cleaned_data.get('email'),
                }
            )
            
            # Si el paciente ya existía, actualizamos sus datos por si cambiaron
            if not created:
                paciente.nombre_completo = form.cleaned_data['nombre_completo']
                if form.cleaned_data.get('telefono'): paciente.telefono = form.cleaned_data['telefono']
                if form.cleaned_data.get('email'): paciente.email = form.cleaned_data['email']
                if form.cleaned_data.get('sexo'): paciente.sexo = form.cleaned_data['sexo']
                paciente.save()

            # 2. Guardar el Examen (Biopsia) vinculándolo al paciente
            nueva_muestra = form.save(commit=False)
            nueva_muestra.paciente = paciente
            
            # Generamos el código correlativo automático (Ej: BIO-A1B2C3)
            codigo_unico = uuid.uuid4().hex[:6].upper()
            nueva_muestra.numero_correlativo = f"BIO-{codigo_unico}"
            
            # Asignamos el estado inicial
            nueva_muestra.estado = 'Ingresada'
            
            nueva_muestra.save()
            return redirect('dashboard')
    else:
        form = ExamenForm()
        
    return render(request, 'nueva_biopsia.html', {'form': form})


# --- VISTAS DE PATÓLOGO ---

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
            Q(paciente__rut__icontains=query_historial) |
            Q(paciente__nombre_completo__icontains=query_historial) |
            Q(numero_correlativo__icontains=query_historial)
        )

    return render(request, 'dashboard_patologo.html', {
        'muestras_pendientes': muestras_pendientes,
        'historial_examenes': historial_examenes,
        'query_historial': query_historial,
    })


@login_required
@user_passes_test(es_patologo, login_url='/inicio/')
def asignar_patologo(request, examen_id):
    """ Permite a un patólogo asignarse una muestra desde el dashboard """
    if request.method == 'POST':
        muestra = get_object_or_404(Examen, id=examen_id)
        if not muestra.patologo:
            muestra.patologo = request.user
            muestra.save()
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario="Tomó el caso y se asignó como patólogo responsable.",
                tipo='Asignación Médica'
            )
    return redirect('dashboard_patologo')


# --- VISTAS COMPARTIDAS / DETALLE ---

@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def detalle_muestra(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    es_patologo_user = es_patologo(request.user)
    
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
            # Si el informe está cerrado, no se puede modificar (a menos que seas admin y uses reabrir_informe)
            if muestra.informe_cerrado and not request.user.is_superuser:
                return redirect('detalle_muestra', examen_id=muestra.id)

            nuevo_estado = request.POST.get('estado')
            nota_medica = request.POST.get('nota')
            es_critico = request.POST.get('resultado_critico') == 'True'
            
            if nuevo_estado and nuevo_estado != muestra.estado:
                estado_anterior = muestra.estado
                muestra.estado = nuevo_estado
                
                # Bloquear informe si se finaliza
                if nuevo_estado == 'Finalizado':
                    muestra.informe_cerrado = True
                    
                muestra.save()
                
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=f"Cambió el estado de '{estado_anterior}' a '{nuevo_estado}'",
                    tipo='Cambio de estado'
                )

            # Control de resultado crítico
            if es_critico != muestra.resultado_critico:
                muestra.resultado_critico = es_critico
                muestra.save()
                msg_critico = "Marcó el hallazgo como CRÍTICO / URGENTE." if es_critico else "Quitó la marca de resultado crítico."
                Comentario.objects.create(examen=muestra, user=request.user, comentario=msg_critico, tipo='Alerta Médica')

            if nota_medica:
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=nota_medica,
                    tipo='Diagnóstico / Nota'
                )
                
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        # 🔓 ACCIÓN 3: Reabrir informe cerrado (Exclusivo Admin)
        elif request.user.is_superuser and action == 'reabrir_informe':
            motivo = request.POST.get('motivo_apertura')
            if motivo:
                muestra.informe_cerrado = False
                muestra.estado = 'En Evaluación'
                muestra.save()
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=f"Reapertura de informe cerrado. Motivo: {motivo}",
                    tipo='Apertura Admin'
                )
            return redirect('detalle_muestra', examen_id=muestra.id)


    # Paginación del historial/comentarios para solicitudes GET
    historial_list = muestra.comentarios.all().order_by('-created_at')
    paginator = Paginator(historial_list, 5)
    page_number = request.GET.get('page')
    historial = paginator.get_page(page_number)

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
    muestra = get_object_or_404(Examen, id=examen_id)
    diagnostico_final = muestra.comentarios.filter(tipo='Diagnóstico / Nota').order_by('-created_at').first()
    
    return render(request, 'informe_pdf.html', {
        'muestra': muestra,
        'diagnostico': diagnostico_final
    })


# --- API / AJAX ---

def buscar_paciente_por_rut(request, rut):
    """ Devuelve los datos del paciente para autocompletar formularios """
    try:
        paciente = Paciente.objects.get(rut=rut)
        return JsonResponse({
            'encontrado': True,
            'nombre_completo': paciente.nombre_completo,
            'email': paciente.email,
            'telefono': paciente.telefono,
            'sexo': paciente.sexo
        })
    except Paciente.DoesNotExist:
        return JsonResponse({'encontrado': False})