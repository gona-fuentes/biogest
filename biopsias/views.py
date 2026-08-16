import csv
import uuid
import hashlib
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

from .models import Examen, Comentario, TipoExamen, Paciente, Medico, PlantillaPatologo
from .forms import ExamenForm, PerfilPatologoForm, PlantillaPatologoForm, CrearUsuarioAdminForm
from usuarios.models import Laboratorio

User = get_user_model()


# --- VALIDACIONES DE ROLES ---

def es_laboratorio(user):
    return user.groups.filter(name='Laboratorio').exists() or user.is_superuser

def es_patologo(user):
    return user.groups.filter(name='Patólogo').exists() or user.is_superuser

def es_personal_autorizado(user):
    return user.groups.filter(name__in=['Laboratorio', 'Patólogo']).exists() or user.is_superuser


@login_required
def redireccion_post_login(request):
    """ Redirige al panel correspondiente según el rol del usuario """
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
                Comentario.objects.create(
                    examen=muestra, user=request.user, 
                    comentario=mensaje, tipo='Mensaje / Consulta'
                )
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
            
            if not created:
                paciente.nombre_completo = form.cleaned_data['nombre_completo']
                if form.cleaned_data.get('telefono'): paciente.telefono = form.cleaned_data['telefono']
                if form.cleaned_data.get('email'): paciente.email = form.cleaned_data['email']
                if form.cleaned_data.get('sexo'): paciente.sexo = form.cleaned_data['sexo']
                if form.cleaned_data.get('fecha_nacimiento'): paciente.fecha_nacimiento = form.cleaned_data['fecha_nacimiento']
                paciente.save()

            nueva_muestra = form.save(commit=False)
            nueva_muestra.paciente = paciente
            
            codigo_unico = uuid.uuid4().hex[:6].upper()
            nueva_muestra.numero_correlativo = f"BIO-{codigo_unico}"
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
            
        return redirect('dashboard_patologo')

    muestras_pendientes = Examen.objects.exclude(estado='Finalizado').filter(
        Q(patologo__isnull=True) | Q(patologo=request.user)
    ).order_by('-fecha_recepcion')

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


# --- DETALLE Y EVALUACIÓN MUESTRA ---

@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def detalle_muestra(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    es_patologo_user = es_patologo(request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'enviar_chat':
            mensaje = request.POST.get('mensaje', '').strip()
            if mensaje:
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=mensaje, tipo='Mensaje / Consulta'
                )
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        elif es_patologo_user and action == 'actualizar_diagnostico':
            if muestra.informe_cerrado and not request.user.is_superuser:
                messages.error(request, "El informe está cerrado y bloqueado.")
                return redirect('detalle_muestra', examen_id=muestra.id)

            nuevo_estado = request.POST.get('estado')
            nota_medica = request.POST.get('nota')
            es_critico = request.POST.get('resultado_critico') == 'True'
            
            if nuevo_estado and nuevo_estado != muestra.estado:
                estado_anterior = muestra.estado
                muestra.estado = nuevo_estado
                
                if nuevo_estado == 'Finalizado':
                    muestra.informe_cerrado = True
                    muestra.fecha_entrega = datetime.now().date()
                    
                muestra.save()
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=f"Cambió el estado de '{estado_anterior}' a '{nuevo_estado}'",
                    tipo='Cambio de estado'
                )

            if es_critico != muestra.resultado_critico:
                muestra.resultado_critico = es_critico
                muestra.save()
                msg_critico = "Marcó el hallazgo como CRÍTICO / URGENTE." if es_critico else "Quitó la marca de resultado crítico."
                Comentario.objects.create(examen=muestra, user=request.user, comentario=msg_critico, tipo='Alerta Médica')

            if nota_medica:
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=nota_medica, tipo='Diagnóstico / Nota'
                )
                
            messages.success(request, "Informe y diagnóstico guardados con éxito.")
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        elif request.user.is_superuser and action == 'reabrir_informe':
            motivo = request.POST.get('motivo_apertura')
            if motivo:
                muestra.informe_cerrado = False
                muestra.estado = 'En Evaluación'
                muestra.save()
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=f"Reapertura de informe cerrado. Motivo: {motivo}",
                    tipo='Apertura Admin'
                )
                messages.success(request, "El informe ha sido desbloqueado.")
            return redirect('detalle_muestra', examen_id=muestra.id)

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
    
    # Hash de Verificación de Autenticidad SHA-256
    cadena_verificacion = f"{muestra.numero_correlativo}|{muestra.paciente.rut}|{muestra.updated_at}|{muestra.patologo.username if muestra.patologo else 'S/N'}"
    hash_verificacion = hashlib.sha256(cadena_verificacion.encode('utf-8')).hexdigest().upper()

    return render(request, 'informe_pdf.html', {
        'muestra': muestra,
        'diagnostico': diagnostico_final,
        'hash_verificacion': hash_verificacion
    })


# --- FICHA CLÍNICA DE PACIENTES ---

@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def lista_pacientes(request):
    query = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.all().order_by('-created_at')

    if query:
        pacientes = pacientes.filter(
            Q(rut__icontains=query) |
            Q(nombre_completo__icontains=query) |
            Q(email__icontains=query)
        )

    pacientes = pacientes.annotate(total_biopsias=Count('examenes'))

    return render(request, 'lista_pacientes.html', {'pacientes': pacientes, 'query': query})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/inicio/')
def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    examenes = paciente.examenes.all().order_by('-fecha_recepcion')
    
    return render(request, 'detalle_paciente.html', {'paciente': paciente, 'examenes': examenes})


# --- HISTORIAL FILTRADO AVANZADO ---

@login_required
def historial_filtrado(request):
    examenes = Examen.objects.all().order_by('-fecha_recepcion')
    
    q = request.GET.get('q', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    estado = request.GET.get('estado', '')
    tipo_examen_id = request.GET.get('tipo_examen', '')

    if q:
        examenes = examenes.filter(
            Q(paciente__rut__icontains=q) |
            Q(paciente__nombre_completo__icontains=q) |
            Q(numero_correlativo__icontains=q)
        )
    if fecha_inicio: examenes = examenes.filter(fecha_recepcion__gte=fecha_inicio)
    if fecha_fin: examenes = examenes.filter(fecha_recepcion__lte=fecha_fin)
    if estado: examenes = examenes.filter(estado=estado)
    if tipo_examen_id: examenes = examenes.filter(tipo_examen_id=tipo_examen_id)

    tipos_examen = TipoExamen.objects.filter(activo=True)

    return render(request, 'historial_filtrado.html', {
        'examenes': examenes, 'tipos_examen': tipos_examen,
        'q': q, 'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin,
        'estado_sel': estado, 'tipo_sel': tipo_examen_id,
    })


# --- ESTADÍSTICAS Y EXCEL ---

@login_required
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

    examenes_por_tipo = TipoExamen.objects.annotate(
        total=Count('examen')
    ).values('nombre', 'total')

    biopsias_mensuales = Examen.objects.annotate(
        mes=TruncMonth('fecha_recepcion')
    ).values('mes').annotate(total=Count('id')).order_by('mes')
    
    labels_meses = [b['mes'].strftime('%B %Y') for b in biopsias_mensuales if b['mes']]
    data_meses = [b['total'] for b in biopsias_mensuales if b['mes']]

    finalizados = Examen.objects.filter(estado='Finalizado', fecha_entrega__isnull=False)
    dias_tat = [(ex.fecha_entrega - ex.fecha_recepcion).days for ex in finalizados if (ex.fecha_entrega - ex.fecha_recepcion).days >= 0]
    tat_promedio_dias = round(sum(dias_tat) / len(dias_tat), 1) if dias_tat else "N/A"

    return render(request, 'estadisticas.html', {
        'total_biopsias': total_biopsias, 'total_finalizadas': total_finalizadas,
        'total_criticos': total_criticos, 'total_pendientes': total_pendientes,
        'tat_promedio_dias': tat_promedio_dias,
        'labels_patologos': [p['username'] for p in patologos_stats],
        'data_patologos': [p['total_asignadas'] for p in patologos_stats],
        'labels_tipos': [e['nombre'] for e in examenes_por_tipo],
        'data_tipos': [e['total'] for e in examenes_por_tipo],
        'porcentaje_criticos': porcentaje_criticos,
        'porcentaje_normales': porcentaje_normales,
        'labels_meses': labels_meses, 'data_meses': data_meses,
    })


@login_required
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"Reporte_Biopsias_Biogest_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Correlativo', 'RUT Paciente', 'Nombre Paciente', 'Fecha Nacimiento',
        'Sexo', 'Médico Solicitante', 'Tipo Examen', 'Muestras', 'Fragmentos',
        'Fecha Recepción', 'Fecha Entrega', 'Estado', 'Patólogo Asignado', 'Resultado Crítico'
    ])

    examenes = Examen.objects.all().order_by('-fecha_recepcion')
    for ex in examenes:
        writer.writerow([
            ex.numero_correlativo, ex.paciente.rut, ex.paciente.nombre_completo,
            ex.paciente.fecha_nacimiento.strftime('%d/%m/%Y') if ex.paciente.fecha_nacimiento else '',
            ex.paciente.sexo, ex.medico_solicitante.nombre if ex.medico_solicitante else '',
            ex.tipo_examen.nombre, ex.cantidad_muestras, ex.numero_fragmentos,
            ex.fecha_recepcion.strftime('%d/%m/%Y'),
            ex.fecha_entrega.strftime('%d/%m/%Y') if ex.fecha_entrega else 'Pendiente',
            ex.estado, ex.patologo.username if ex.patologo else 'No asignado',
            'SÍ' if ex.resultado_critico else 'NO'
        ])
    return response


# --- PERFIL, FIRMA DIGITAL Y PLANTILLAS ---

@login_required
def mi_perfil(request):
    if request.method == 'POST':
        form = PerfilPatologoForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil y firma digital actualizados correctamente.")
            return redirect('mi_perfil')
    else:
        form = PerfilPatologoForm(instance=request.user)
    return render(request, 'mi_perfil.html', {'form': form})


@login_required
@user_passes_test(es_patologo, login_url='/inicio/')
def mis_plantillas(request):
    plantillas = PlantillaPatologo.objects.filter(patologo=request.user)
    if request.method == 'POST':
        form = PlantillaPatologoForm(request.POST)
        if form.is_valid():
            nueva = form.save(commit=False)
            nueva.patologo = request.user
            nueva.save()
            messages.success(request, "Plantilla personal agregada con éxito.")
            return redirect('mis_plantillas')
    else:
        form = PlantillaPatologoForm()
    return render(request, 'mis_plantillas.html', {'plantillas': plantillas, 'form': form})


@login_required
def api_obtener_plantillas(request, tipo_examen_id):
    plantillas = PlantillaPatologo.objects.filter(
        patologo=request.user, tipo_examen_id=tipo_examen_id
    ).values('id', 'titulo', 'texto_predefinido')
    return JsonResponse({'plantillas': list(plantillas)})


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='/inicio/')
def admin_gestion_rapida(request):
    from django.contrib.auth.models import Group
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'crear_usuario':
            form_user = CrearUsuarioAdminForm(request.POST)
            if form_user.is_valid():
                user = form_user.save(commit=False)
                user.set_password(form_user.cleaned_data['password'])
                user.save()
                grupo_nombre = form_user.cleaned_data['rol']
                grupo, _ = Group.objects.get_or_create(name=grupo_nombre)
                user.groups.add(grupo)
                messages.success(request, f"Usuario '{user.username}' registrado correctamente.")
                return redirect('admin_gestion_rapida')
        elif action == 'crear_laboratorio':
            nombre = request.POST.get('nombre_lab')
            rut = request.POST.get('rut_lab')
            if nombre and rut:
                Laboratorio.objects.create(nombre=nombre, rut=rut)
                messages.success(request, f"Laboratorio '{nombre}' creado.")
                return redirect('admin_gestion_rapida')

    form_user = CrearUsuarioAdminForm()
    return render(request, 'admin_gestion_rapida.html', {'form_user': form_user})


# --- ENDPOINTS AJAX EN TIEMPO REAL ---

def buscar_paciente_por_rut(request, rut):
    try:
        paciente = Paciente.objects.get(rut=rut)
        return JsonResponse({
            'encontrado': True,
            'nombre_completo': paciente.nombre_completo,
            'email': paciente.email,
            'telefono': paciente.telefono,
            'sexo': paciente.sexo,
            'fecha_nacimiento': paciente.fecha_nacimiento.strftime('%Y-%m-%d') if paciente.fecha_nacimiento else ''
        })
    except Paciente.DoesNotExist:
        return JsonResponse({'encontrado': False})


@login_required
def api_check_pendientes(request):
    if es_patologo(request.user):
        muestras = Examen.objects.exclude(estado='Finalizado').filter(
            Q(patologo__isnull=True) | Q(patologo=request.user)
        )
        data = [{'id': m.id, 'alerta_chat': m.alerta_chat_patologo} for m in muestras]
        return JsonResponse({'muestras': data})
    elif es_laboratorio(request.user):
        muestras = Examen.objects.all()
        data = [{'id': m.id, 'alerta_chat': m.alerta_chat_laboratorio} for m in muestras]
        return JsonResponse({'muestras': data})
    return JsonResponse({'muestras': []})


@login_required
def api_chat_examen(request, examen_id):
    muestra = get_object_or_404(Examen, id=examen_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'marcar_leido':
            if es_patologo(request.user): muestra.alerta_chat_patologo = False
            else: muestra.alerta_chat_laboratorio = False
            muestra.save()
            return JsonResponse({'status': 'ok'})

        mensaje = request.POST.get('mensaje', '').strip()
        if mensaje:
            Comentario.objects.create(
                examen=muestra, user=request.user,
                comentario=mensaje, tipo='Mensaje / Consulta'
            )
            if es_patologo(request.user):
                muestra.alerta_chat_laboratorio = True
                muestra.alerta_chat_patologo = False
            else:
                muestra.alerta_chat_patologo = True
                muestra.alerta_chat_laboratorio = False
            muestra.save()
        return JsonResponse({'status': 'ok'})

    mensajes = muestra.comentarios.filter(tipo='Mensaje / Consulta').order_by('created_at')
    data = [{
        'usuario': msg.user.username,
        'es_mio': msg.user == request.user,
        'texto': msg.comentario,
        'fecha': msg.created_at.strftime("%d/%m %H:%M")
    } for msg in mensajes]
    
    alerta_actual = muestra.alerta_chat_patologo if es_patologo(request.user) else muestra.alerta_chat_laboratorio
    return JsonResponse({'mensajes': data, 'alerta_chat': alerta_actual})