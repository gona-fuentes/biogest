import csv
import uuid
import hashlib
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Case, When, Value, IntegerField, Q, Count
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.utils import timezone

from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import timedelta
# IMPORTACIONES LIMPIAS DE LA APP
from .models import Examen, Comentario, TipoExamen, Paciente, PlantillaPatologo, Medico
from .forms import ExamenForm, PlantillaPatologoForm
from .utils import enviar_informe_por_correo
import uuid
from django.contrib import messages






User = get_user_model()


# --- FUNCIONES DE UTILIDAD Y VALIDACIÓN DE ROLES ---
def es_laboratorio(user):
    return user.groups.filter(name='Laboratorio').exists() or user.is_superuser

def es_patologo(user):
    return user.groups.filter(name='Patólogo').exists() or user.is_superuser

def es_personal_autorizado(user):
    return user.groups.filter(name__in=['Laboratorio', 'Patólogo']).exists() or user.is_superuser

def limpiar_rut(rut):
    """Limpia el RUT removiendo puntos, guiones y espacios para búsquedas estandarizadas."""
    if not rut:
        return ""
    return re.sub(r'[^0-9kK]', '', str(rut)).upper()


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def dashboard(request):
    query = request.GET.get('q', '').strip()
    
    queryset = Examen.objects.all()
    
    if query:
        queryset = queryset.filter(
            Q(paciente__rut__icontains=query) |
            Q(paciente__nombre_completo__icontains=query) |
            Q(numero_correlativo__icontains=query)
        )

    # 1. TABLA DE CRÍTICOS
    examenes_criticos = queryset.filter(resultado_critico=True).order_by('-fecha_recepcion')[:2]

    # 2. TABLA PRINCIPAL
    examenes_principales = queryset.annotate(
        orden_estado=Case(
            When(estado='Ingresada', then=Value(1)),
            When(estado='En Evaluación', then=Value(2)),
            When(estado='Finalizado', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('orden_estado', '-fecha_recepcion')

    paginator = Paginator(examenes_principales, 3) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 👇 NUEVA LÓGICA DE ALERTAS KPI 👇
    # Calculamos la fecha límite (hace 15 días exactamente)
    fecha_limite = timezone.now().date() - timedelta(days=15)
    
    # Buscamos biopsias que NO estén finalizadas y que hayan entrado antes de esa fecha límite
    muestras_atrasadas = queryset.exclude(estado='Finalizado').filter(fecha_recepcion__lt=fecha_limite)
    cantidad_atrasadas = muestras_atrasadas.count()

    context = {
        'page_obj': page_obj,
        'query': query,
        'examenes_criticos': examenes_criticos,
        'cantidad_atrasadas': cantidad_atrasadas,  # Mandamos el número de atrasadas al HTML
    }
    return render(request, 'biopsias/dashboard.html', context)



@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def registrar_biopsia(request):
    if request.method == 'POST':
        # 1. Copia de datos para inyectar al médico
        datos_post = request.POST.copy()

        # 2. RESOLVER EL MÉDICO SOLICITANTE
        tipo_medico = datos_post.get('tipo_medico')
        
        if tipo_medico == 'nuevo':
            nuevo_nombre = datos_post.get('nuevo_medico_nombre', '').strip()
            nuevo_email = datos_post.get('nuevo_medico_email', '').strip()
            
            if nuevo_nombre:
                medico_obj, created = Medico.objects.get_or_create(
                    nombre=nuevo_nombre,
                    defaults={'email': nuevo_email if nuevo_email else None}
                )
                datos_post['medico_solicitante'] = medico_obj.id
        else:
            datos_post['medico_solicitante'] = datos_post.get('medico_existente')

        # 3. Formulario con datos reparados
        form = ExamenForm(datos_post)
        
        if form.is_valid():
            
            # 👇 GUARDAR PACIENTE (INCLUYENDO NOMBRE SOCIAL)
            paciente, created = Paciente.objects.get_or_create(
                rut=form.cleaned_data.get('rut'),
                defaults={
                    'nombre_completo': form.cleaned_data.get('nombre_completo'),
                    'nombre_social': form.cleaned_data.get('paciente_nombre_social'),
                    'fecha_nacimiento': form.cleaned_data.get('fecha_nacimiento'),
                    'sexo': form.cleaned_data.get('sexo'),
                    'telefono': form.cleaned_data.get('telefono'),
                    'email': form.cleaned_data.get('email')
                }
            )
            if not created:
                paciente.nombre_completo = form.cleaned_data.get('nombre_completo')
                paciente.nombre_social = form.cleaned_data.get('paciente_nombre_social')
                paciente.fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')
                paciente.sexo = form.cleaned_data.get('sexo')
                paciente.telefono = form.cleaned_data.get('telefono')
                paciente.email = form.cleaned_data.get('email')
                paciente.save()

            # Guardar Biopsia
            correlativo = f"BIO-{uuid.uuid4().hex[:6].upper()}"
            while Examen.objects.filter(numero_correlativo=correlativo).exists():
                correlativo = f"BIO-{uuid.uuid4().hex[:6].upper()}"

            examen = form.save(commit=False)
            examen.paciente = paciente
            examen.numero_correlativo = correlativo
            
            # 👇 ALGORITMO DE ASIGNACIÓN AUTOMÁTICA (Minsal TAT)
            # Busca al patólogo con menos exámenes "En Evaluación"
            patologo_libre = User.objects.filter(groups__name='Patologo').annotate(
                carga_laboral=Count('examenes_asignados', filter=Q(examenes_asignados__estado='En Evaluación'))
            ).order_by('carga_laboral').first()

            if patologo_libre:
                examen.patologo = patologo_libre
                examen.estado = 'En Evaluación'
                msg_auditoria = f"Se ha ingresado la nueva muestra {correlativo}. Asignada automáticamente a Dr(a). {patologo_libre.last_name} (Balance de carga laboral)."
            else:
                examen.estado = 'Ingresada'
                msg_auditoria = f"Se ha ingresado la nueva muestra con código correlativo {correlativo}. (Pendiente de asignación médica)."

            examen.save()

            Comentario.objects.create(
                examen=examen,
                user=request.user,
                comentario=msg_auditoria,
                tipo='Creación / Ingreso'
            )

            messages.success(request, f"Biopsia {correlativo} registrada exitosamente.")
            return redirect('dashboard')
        else:
            messages.error(request, "✕ Faltan campos obligatorios. Revise el formulario y asegúrese de asignar al Médico Solicitante.")
            
    else:
        form = ExamenForm()
    
    medicos = Medico.objects.all().order_by('nombre')
    return render(request, 'biopsias/nueva_biopsia.html', {'form': form, 'medicos': medicos})


@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
def dashboard_patologo(request):
    query_historial = request.GET.get('q_historial', '').strip()
    
    # 1. MANEJO DE POST (Chat, Marcar Leído y Enviar Correo)
    if request.method == 'POST':
        action = request.POST.get('action')
        examen_id = request.POST.get('examen_id')
        
        if examen_id:
            muestra = get_object_or_404(Examen, id=examen_id)

            if action == 'enviar_chat':
                mensaje = request.POST.get('mensaje', '').strip()
                if mensaje:
                    Comentario.objects.create(
                        examen=muestra, user=request.user, 
                        comentario=mensaje, tipo='Mensaje / Consulta'
                    )
                    muestra.alerta_chat_laboratorio = True
                    muestra.alerta_chat_patologo = False
                    muestra.save()
            
            elif action == 'marcar_leido':
                muestra.alerta_chat_patologo = False
                muestra.save()
                
            elif action == 'enviar_correo':
                # Buscar correo EXCLUSIVAMENTE del Médico Solicitante
                email_destino = None
                if muestra.medico_solicitante and muestra.medico_solicitante.email:
                    email_destino = muestra.medico_solicitante.email
                
                if email_destino:
                    try:
                        # Pasamos request para que WeasyPrint pueda leer la firma local
                        enviar_informe_por_correo(muestra, email_destino, request)
                        messages.success(request, f'✓ Informe {muestra.numero_correlativo} enviado a Dr(a). {muestra.medico_solicitante.nombre} ({email_destino}).')
                    except Exception as e:
                        messages.error(request, f'✕ Error al enviar el correo: {e}')
                else:
                    messages.error(request, f'✕ El Médico Solicitante de la muestra {muestra.numero_correlativo} no tiene un correo registrado o no existe.')

        return redirect('dashboard_patologo')

    # 2. BANDEJA SUPERIOR: Muestras Pendientes
    muestras_pendientes = Examen.objects.exclude(estado='Finalizado').filter(
        Q(patologo__isnull=True) | Q(patologo=request.user)
    ).order_by('-fecha_recepcion')

    # 3. BANDEJA INFERIOR: Historial General
    historial_queryset = Examen.objects.all().order_by('-fecha_recepcion')
    
    if query_historial:
        query_limpio = limpiar_rut(query_historial)
        historial_queryset = historial_queryset.filter(
            Q(paciente__rut__icontains=query_historial) |
            Q(paciente__rut__icontains=query_limpio) |
            Q(paciente__nombre_completo__icontains=query_historial) |
            Q(numero_correlativo__icontains=query_historial)
        )

    # Configuración del paginador
    paginator = Paginator(historial_queryset, 5)
    page_number = request.GET.get('page') 
    historial_examenes = paginator.get_page(page_number)

    context = {
        'muestras_pendientes': muestras_pendientes,
        'historial_examenes': historial_examenes,
        'query_historial': query_historial,
    }
    
    return render(request, 'biopsias/dashboard_patologo.html', context)


@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
def asignar_patologo(request, examen_id):
    if request.method == 'POST':
        muestra = get_object_or_404(Examen, id=examen_id)
        if not muestra.patologo:
            muestra.patologo = request.user
            if muestra.estado == 'Ingresada':
                muestra.estado = 'En Evaluación'
            muestra.save()
            Comentario.objects.create(
                examen=muestra, user=request.user,
                comentario="Tomó el caso y se asignó como patólogo responsable.",
                tipo='Asignación Médica'
            )
    return redirect('dashboard_patologo')


# --- DETALLE Y EVALUACIÓN ---
@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def detalle_muestra(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    comentarios = muestra.comentarios.all().order_by('-created_at')
    
    es_patologo_user = request.user.groups.filter(name='Patólogo').exists() or request.user.is_superuser
    
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reabrir_informe' and request.user.is_superuser:
            motivo = request.POST.get('motivo_apertura', '').strip()
            if motivo:
                muestra.informe_cerrado = False
                muestra.estado = 'En Evaluación'
                muestra.save()
                
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=f"INFORME REABIERTO POR ADMINISTRACIÓN.\nMotivo registrado: {motivo}",
                    tipo='Apertura Admin'
                )
                messages.success(request, "Informe desbloqueado y reabierto exitosamente. Registrado en cronología.")
            else:
                messages.error(request, "Debe ingresar obligatoriamente un motivo para reabrir el informe.")
            return redirect('detalle_muestra', examen_id=muestra.id)

        elif action == 'agregar_comentario':
            texto = request.POST.get('comentario', '').strip()
            if texto:
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=texto,
                    tipo='Nota interna'
                )
                messages.success(request, "Comentario agregado a la cadena de custodia.")
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        elif es_patologo_user and action == 'actualizar_diagnostico':
            if muestra.informe_cerrado and not request.user.is_superuser:
                messages.error(request, "El informe está cerrado y bloqueado por seguridad.")
                return redirect('detalle_muestra', examen_id=muestra.id)

            nuevo_estado = request.POST.get('estado')
            nota_medica = request.POST.get('nota', '').strip()
            es_critico = request.POST.get('resultado_critico') == 'True'
            pin_ingresado = request.POST.get('pin_firma', '')

            if nuevo_estado == 'Finalizado' and muestra.estado != 'Finalizado':
                pin_usuario = getattr(request.user, 'pin_firma', None)
                if not pin_usuario:
                    messages.error(request, "❌ Debe configurar su PIN de Firma Digital en 'Mi Perfil' antes de emitir un informe.")
                    return redirect('detalle_muestra', examen_id=muestra.id)
                elif pin_ingresado != pin_usuario:
                    messages.error(request, "❌ PIN de Firma Digital Incorrecto.")
                    return redirect('detalle_muestra', examen_id=muestra.id)

            if nuevo_estado and nuevo_estado != muestra.estado:
                estado_anterior = muestra.estado
                muestra.estado = nuevo_estado
                
                if nuevo_estado == 'Finalizado':
                    muestra.informe_cerrado = True
                    muestra.fecha_entrega = timezone.now().date()
                    
                muestra.save()
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=f"Cambio de estado en cadena de custodia: de '{estado_anterior}' a '{nuevo_estado}'",
                    tipo='Cambio de estado'
                )

            if es_critico != muestra.resultado_critico:
                muestra.resultado_critico = es_critico
                muestra.save()
                msg_critico = "ALERTA: Se marcó la muestra como RESULTADO CRÍTICO / URGENTE." if es_critico else "Se retiró la marca de resultado crítico."
                Comentario.objects.create(examen=muestra, user=request.user, comentario=msg_critico, tipo='Alerta Médica')

            if nota_medica:
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=nota_medica, tipo='Diagnóstico / Nota'
                )
                
            messages.success(request, "Diagnóstico e información guardados correctamente en la trazabilidad.")
            return redirect('detalle_muestra', examen_id=muestra.id)

    return render(request, 'biopsias/detalle_muestra.html', {
        'muestra': muestra,
        'comentarios': comentarios,
        'es_patologo': es_patologo_user
    })


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def generar_informe_pdf(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    diagnosticos = muestra.comentarios.filter(tipo='Diagnóstico / Nota').order_by('created_at')
    
    cadena_verificacion = f"{muestra.numero_correlativo}|{muestra.paciente.rut}|{muestra.updated_at}|{muestra.patologo.username if muestra.patologo else 'S/N'}"
    hash_verificacion = hashlib.sha256(cadena_verificacion.encode('utf-8')).hexdigest().upper()

    return render(request, 'biopsias/informe_pdf.html', {
        'muestra': muestra,
        'diagnosticos': diagnosticos,
        'hash_verificacion': hash_verificacion
    })


# --- FICHAS CLÍNICAS ---
@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def lista_pacientes(request):
    query = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.all().order_by('-created_at')
    if query:
        query_limpio = limpiar_rut(query)
        pacientes = pacientes.filter(
            Q(rut__icontains=query) | Q(rut__icontains=query_limpio) | Q(nombre_completo__icontains=query)
        )
    pacientes = pacientes.annotate(total_biopsias=Count('examenes'))
    return render(request, 'biopsias/lista_pacientes.html', {'pacientes': pacientes, 'query': query})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    examenes = paciente.examenes.all().order_by('-fecha_recepcion')
    return render(request, 'biopsias/detalle_paciente.html', {'paciente': paciente, 'examenes': examenes})


# --- HISTORIAL Y ESTADÍSTICAS ---
@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def historial_filtrado(request):
    examenes = Examen.objects.all().order_by('-fecha_recepcion')
    q = request.GET.get('q', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    estado = request.GET.get('estado', '')
    tipo_examen_id = request.GET.get('tipo_examen', '')

    if q:
        q_limpio = limpiar_rut(q)
        examenes = examenes.filter(
            Q(paciente__rut__icontains=q) | Q(paciente__rut__icontains=q_limpio) |
            Q(paciente__nombre_completo__icontains=q) | Q(numero_correlativo__icontains=q)
        )
    if fecha_inicio: examenes = examenes.filter(fecha_recepcion__gte=fecha_inicio)
    if fecha_fin: examenes = examenes.filter(fecha_recepcion__lte=fecha_fin)
    if estado: examenes = examenes.filter(estado=estado)
    if tipo_examen_id: examenes = examenes.filter(tipo_examen_id=tipo_examen_id)

    tipos_examen = TipoExamen.objects.filter(activo=True)
    return render(request, 'biopsias/historial_filtrado.html', {
        'examenes': examenes, 'tipos_examen': tipos_examen, 'q': q, 
        'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin,
        'estado_sel': estado, 'tipo_sel': tipo_examen_id,
    })


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def dashboard_estadisticas(request):
    total_biopsias = Examen.objects.count()
    total_finalizadas = Examen.objects.filter(estado='Finalizado').count()
    total_criticos = Examen.objects.filter(resultado_critico=True).count()
    total_pendientes = Examen.objects.exclude(estado='Finalizado').count()

    porcentaje_criticos = round((total_criticos / total_biopsias * 100), 1) if total_biopsias > 0 else 0
    porcentaje_normales = 100 - porcentaje_criticos

    patologos_stats = User.objects.filter(groups__name='Patólogo').annotate(
        total_asignadas=Count('examenes_asignados')
    ).values('username', 'total_asignadas')

    examenes_por_tipo = TipoExamen.objects.annotate(total=Count('examen')).values('nombre', 'total')

    biopsias_mensuales = Examen.objects.annotate(mes=TruncMonth('fecha_recepcion')).values('mes').annotate(total=Count('id')).order_by('mes')
    labels_meses = [b['mes'].strftime('%B %Y') for b in biopsias_mensuales if b['mes']]
    data_meses = [b['total'] for b in biopsias_mensuales if b['mes']]

    finalizados = Examen.objects.filter(estado='Finalizado', fecha_entrega__isnull=False)
    dias_tat = [(ex.fecha_entrega - ex.fecha_recepcion).days for ex in finalizados if (ex.fecha_entrega - ex.fecha_recepcion).days >= 0]
    tat_promedio_dias = round(sum(dias_tat) / len(dias_tat), 1) if dias_tat else "N/A"

    return render(request, 'biopsias/estadisticas.html', {
        'total_biopsias': total_biopsias, 'total_finalizadas': total_finalizadas,
        'total_criticos': total_criticos, 'total_pendientes': total_pendientes,
        'tat_promedio_dias': tat_promedio_dias,
        'labels_patologos': [p['username'] for p in patologos_stats], 'data_patologos': [p['total_asignadas'] for p in patologos_stats],
        'labels_tipos': [e['nombre'] for e in examenes_por_tipo], 'data_tipos': [e['total'] for e in examenes_por_tipo],
        'porcentaje_criticos': porcentaje_criticos, 'porcentaje_normales': porcentaje_normales,
        'labels_meses': labels_meses, 'data_meses': data_meses,
    })


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"Reporte_Biopsias_Biogest_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Correlativo', 'RUT Paciente', 'Nombre Paciente', 'Fecha Recepción', 'Estado', 'Patólogo Asignado', 'Resultado Crítico'])

    examenes = Examen.objects.all().order_by('-fecha_recepcion')
    for ex in examenes:
        writer.writerow([
            ex.numero_correlativo, ex.paciente.rut, ex.paciente.nombre_completo,
            ex.fecha_recepcion.strftime('%d/%m/%Y'), ex.estado, 
            ex.patologo.username if ex.patologo else 'No asignado', 'SÍ' if ex.resultado_critico else 'NO'
        ])
    return response


# --- PLANTILLAS PATÓLOGO ---
@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
def gestion_plantillas(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. CREAR PLANTILLA
        if action == 'crear':
            titulo = request.POST.get('titulo', '').strip()
            tipo_examen_id = request.POST.get('tipo_examen')
            texto = request.POST.get('texto_predefinido', '').strip()
            
            if titulo and tipo_examen_id and texto:
                PlantillaPatologo.objects.create(
                    patologo=request.user,
                    tipo_examen_id=tipo_examen_id,
                    titulo=titulo,
                    texto_predefinido=texto
                )

        # 2. EDITAR PLANTILLA
        elif action == 'editar':
            plantilla_id = request.POST.get('plantilla_id')
            plantilla = get_object_or_404(PlantillaPatologo, id=plantilla_id, patologo=request.user)
            
            plantilla.titulo = request.POST.get('titulo', '').strip()
            plantilla.tipo_examen_id = request.POST.get('tipo_examen')
            plantilla.texto_predefinido = request.POST.get('texto_predefinido', '').strip()
            plantilla.save()

        # 3. ELIMINAR PLANTILLA
        elif action == 'eliminar':
            plantilla_id = request.POST.get('plantilla_id')
            plantilla = get_object_or_404(PlantillaPatologo, id=plantilla_id, patologo=request.user)
            plantilla.delete()

        return redirect('gestion_plantillas')

    plantillas = PlantillaPatologo.objects.filter(patologo=request.user).select_related('tipo_examen').order_by('-id')
    tipos_examen = TipoExamen.objects.all()

    return render(request, 'biopsias/mis_plantillas.html', {
        'plantillas': plantillas,
        'tipos_examen': tipos_examen,
    })


# --- ENDPOINTS AJAX / API ---
@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def buscar_paciente_por_rut(request, rut):
    rut_limpio = limpiar_rut(rut)
    try:
        paciente = Paciente.objects.filter(Q(rut=rut) | Q(rut=rut_limpio)).first()
        if paciente:
            return JsonResponse({
                'encontrado': True,
                'nombre_completo': paciente.nombre_completo,
                'nombre_social': paciente.nombre_social,
                'fecha_nacimiento': paciente.fecha_nacimiento.strftime('%Y-%m-%d') if paciente.fecha_nacimiento else '',
                'sexo': paciente.sexo,
                'telefono': paciente.telefono,
                'email': paciente.email
            })
    except Exception:
        pass
        
    return JsonResponse({'encontrado': False})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def api_check_pendientes(request):
    if es_patologo(request.user):
        muestras = Examen.objects.exclude(estado='Finalizado').filter(Q(patologo__isnull=True) | Q(patologo=request.user))
        return JsonResponse({'muestras': [{'id': m.id, 'alerta_chat': m.alerta_chat_patologo} for m in muestras]})
    elif es_laboratorio(request.user):
        muestras = Examen.objects.all()
        return JsonResponse({'muestras': [{'id': m.id, 'alerta_chat': m.alerta_chat_laboratorio} for m in muestras]})
    return JsonResponse({'muestras': []})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def api_chat_examen(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'marcar_leido':
            if request.user.groups.filter(name='Laboratorio').exists():
                muestra.alerta_chat_laboratorio = False
            else:
                muestra.alerta_chat_patologo = False
            muestra.save()
            return JsonResponse({'status': 'ok'})
            
        mensaje_texto = request.POST.get('mensaje')
        if mensaje_texto:
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario=mensaje_texto,
                tipo='Chat Interno'
            )
            if request.user.groups.filter(name='Patólogo').exists():
                muestra.alerta_chat_laboratorio = True
            else:
                muestra.alerta_chat_patologo = True
            muestra.save()
            return JsonResponse({'status': 'ok'})

    mensajes_db = muestra.comentarios.filter(tipo='Chat Interno').order_by('created_at')
    data = []
    for msg in mensajes_db:
        data.append({
            'id': msg.id,
            'texto': msg.comentario,
            'usuario': msg.user.get_full_name() or msg.user.username,
            'fecha': msg.created_at.strftime('%d/%m %H:%M'),
            'es_mio': msg.user == request.user
        })
        
    return JsonResponse({'mensajes': data})


@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
def api_obtener_plantillas(request, tipo_examen_id):
    plantillas = PlantillaPatologo.objects.filter(patologo=request.user, tipo_examen_id=tipo_examen_id).values('id', 'titulo', 'texto_predefinido')
    return JsonResponse({'plantillas': list(plantillas)})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def etiqueta_frasco(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    return render(request, 'biopsias/etiqueta_qr.html', {'muestra': muestra})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def imprimir_consentimiento(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    
    # Renderizamos el HTML con los datos del paciente
    html_string = render_to_string('biopsias/pdf/consentimiento_pdf.html', {'paciente': paciente})
    
    # Generamos el PDF con WeasyPrint
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    # Usamos 'inline' para que se abra en el navegador e imprimirlo rápido
    response['Content-Disposition'] = f'inline; filename="Consentimiento_Ley21719_{paciente.rut}.pdf"'
    return response