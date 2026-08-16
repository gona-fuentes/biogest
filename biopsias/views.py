import csv
import uuid
import hashlib
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

# IMPORTACIONES LIMPIAS (Solo lo de esta app)
from .models import Examen, Comentario, TipoExamen, Paciente, PlantillaPatologo
from .forms import ExamenForm, PlantillaPatologoForm

User = get_user_model()

# --- VALIDACIONES DE ROLES ---
def es_laboratorio(user):
    return user.groups.filter(name='Laboratorio').exists() or user.is_superuser

def es_patologo(user):
    return user.groups.filter(name='Patólogo').exists() or user.is_superuser

def es_personal_autorizado(user):
    return user.groups.filter(name__in=['Laboratorio', 'Patólogo']).exists() or user.is_superuser


# --- VISTAS DE LABORATORIO ---
@login_required
@user_passes_test(es_laboratorio, login_url='/usuarios/login/')
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

    return render(request, 'biopsias/dashboard.html', {'muestras': muestras, 'query': query})

@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def registrar_biopsia(request):
    """
    Registra una nueva biopsia buscando si el paciente ya existe por su RUT
    para evitar duplicidades y autocompletar, registrando el inicio en la cadena de custodia.
    """
    if request.method == 'POST':
        form = ExamenForm(request.POST)
        if form.is_valid():
            rut = form.cleaned_data.get('rut')
            nombre_completo = form.cleaned_data.get('nombre_completo')
            fecha_nacimiento = form.cleaned_data.get('fecha_nacimiento')
            sexo = form.cleaned_data.get('sexo')
            telefono = form.cleaned_data.get('telefono')
            email = form.cleaned_data.get('email')

            # 1. Buscar o crear el paciente de forma única por RUT (Evita duplicados)
            paciente, created = Paciente.objects.get_or_create(
                rut=rut,
                defaults={
                    'nombre_completo': nombre_completo,
                    'fecha_nacimiento': fecha_nacimiento,
                    'sexo': sexo,
                    'telefono': telefono,
                    'email': email
                }
            )
            
            # Si el paciente ya existía, actualizamos datos si el usuario modificó algo en el form
            if not created:
                paciente.nombre_completo = nombre_completo
                if fecha_nacimiento: paciente.fecha_nacimiento = fecha_nacimiento
                if sexo: paciente.sexo = sexo
                if telefono: paciente.telefono = telefono
                if email: paciente.email = email
                paciente.save()

            # 2. Generar correlativo único para la muestra
            correlativo = f"BIO-{uuid.uuid4().hex[:6].upper()}"
            while Examen.objects.filter(numero_correlativo=correlativo).exists():
                correlativo = f"BIO-{uuid.uuid4().hex[:6].upper()}"

            examen = form.save(commit=False)
            examen.paciente = paciente
            examen.numero_correlativo = correlativo
            examen.estado = 'Ingresada'
            examen.save()

            # 3. REGISTRAR EN CADENA DE CUSTODIA (Punto de partida obligatorio)
            Comentario.objects.create(
                examen=examen,
                user=request.user,
                comentario=f"Se ha ingresado la nueva muestra con código correlativo {correlativo}.",
                tipo='Creación / Ingreso'
            )

            messages.success(request, f"Biopsia {correlativo} registrada e ingresada al sistema con éxito.")
            return redirect('dashboard')
    else:
        form = ExamenForm()
    
    return render(request, 'biopsias/nueva_biopsia.html', {'form': form})


# --- VISTAS DE PATÓLOGO ---
@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
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

    return render(request, 'biopsias/dashboard_patologo.html', {
        'muestras_pendientes': muestras_pendientes,
        'historial_examenes': historial_examenes,
        'query_historial': query_historial,
    })

@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
def asignar_patologo(request, examen_id):
    if request.method == 'POST':
        muestra = get_object_or_404(Examen, id=examen_id)
        if not muestra.patologo:
            muestra.patologo = request.user
            muestra.save()
            Comentario.objects.create(
                examen=muestra, user=request.user,
                comentario="Tomó el caso y se asignó como patólogo responsable.",
                tipo='Asignación Médica'
            )
    return redirect('dashboard_patologo')


# --- DETALLE Y EVALUACIÓN ---
@login_required
def detalle_muestra(request, examen_id):
    """
    Gestiona el detalle, la cadena de custodia completa y la acción de
    reapertura por parte del administrador informando el motivo.
    """
    muestra = get_object_or_404(Examen, id=examen_id)
    comentarios = muestra.comentarios.all().order_by('-created_at')
    
    es_patologo_user = request.user.groups.filter(name='Patólogo').exists() or request.user.is_superuser
    
    if request.method == 'POST':
        action = request.POST.get('action')

        # ACCIÓN 1: Reabrir informe bloqueado (Exclusivo Administrador con motivo)
        if action == 'reabrir_informe' and request.user.is_superuser:
            motivo = request.POST.get('motivo_apertura', '').strip()
            if motivo:
                muestra.informe_cerrado = False
                muestra.estado = 'En Evaluación'
                muestra.save()
                
                # Registrar obligatoriamente en la cadena de custodia
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

        # ACCIÓN 2: Agregar comentarios / mensajes internos
        elif action == 'agregar_comentario':
            texto = request.POST.get('comentario')
            if texto:
                Comentario.objects.create(
                    examen=muestra,
                    user=request.user,
                    comentario=texto,
                    tipo='Nota interna'
                )
                messages.success(request, "Comentario agregado a la cronología.")
            return redirect('detalle_muestra', examen_id=muestra.id)
            
        # ACCIÓN 3: Actualizar diagnóstico y estados (Patólogo)
        elif es_patologo_user and action == 'actualizar_diagnostico':
            if muestra.informe_cerrado and not request.user.is_superuser:
                messages.error(request, "El informe está cerrado y bloqueado por seguridad.")
                return redirect('detalle_muestra', examen_id=muestra.id)

            nuevo_estado = request.POST.get('estado')
            nota_medica = request.POST.get('nota')
            es_critico = request.POST.get('resultado_critico') == 'True'
            pin_ingresado = request.POST.get('pin_firma', '')

            # Validación de PIN si se intenta finalizar
            if nuevo_estado == 'Finalizado' and muestra.estado != 'Finalizado':
                if not request.user.pin_firma:
                    messages.error(request, "❌ Debe configurar su PIN de Firma Digital en 'Mi Perfil' antes de emitir un informe.")
                    return redirect('detalle_muestra', examen_id=muestra.id)
                elif pin_ingresado != request.user.pin_firma:
                    messages.error(request, "❌ PIN de Firma Digital Incorrecto.")
                    return redirect('detalle_muestra', examen_id=muestra.id)

            # Registrar cambio de estado en la cronología
            if nuevo_estado and nuevo_estado != muestra.estado:
                estado_anterior = muestra.estado
                muestra.estado = nuevo_estado
                
                if nuevo_estado == 'Finalizado':
                    muestra.informe_cerrado = True
                    muestra.fecha_entrega = datetime.now().date()
                    
                muestra.save()
                Comentario.objects.create(
                    examen=muestra, user=request.user,
                    comentario=f"Cambio de estado en cadena de custodia: de '{estado_anterior}' a '{nuevo_estado}'",
                    tipo='Cambio de estado'
                )

            # Registrar marca de resultado crítico en la cronología
            if es_critico != muestra.resultado_critico:
                muestra.resultado_critico = es_critico
                muestra.save()
                msg_critico = "ALERTA: Se marcó la muestra como RESULTADO CRÍTICO / URGENTE." if es_critico else "Se retiró la marca de resultado crítico."
                Comentario.objects.create(examen=muestra, user=request.user, comentario=msg_critico, tipo='Alerta Médica')

            # Registrar nota diagnóstica en la cronología
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
    diagnostico_final = muestra.comentarios.filter(tipo='Diagnóstico / Nota').order_by('-created_at').first()
    
    cadena_verificacion = f"{muestra.numero_correlativo}|{muestra.paciente.rut}|{muestra.updated_at}|{muestra.patologo.username if muestra.patologo else 'S/N'}"
    hash_verificacion = hashlib.sha256(cadena_verificacion.encode('utf-8')).hexdigest().upper()

    return render(request, 'biopsias/informe_pdf.html', {
        'muestra': muestra, 'diagnostico': diagnostico_final,
        'hash_verificacion': hash_verificacion
    })


# --- FICHAS CLÍNICAS ---
@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def lista_pacientes(request):
    query = request.GET.get('q', '').strip()
    pacientes = Paciente.objects.all().order_by('-created_at')
    if query:
        pacientes = pacientes.filter(Q(rut__icontains=query) | Q(nombre_completo__icontains=query))
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
def historial_filtrado(request):
    examenes = Examen.objects.all().order_by('-fecha_recepcion')
    q = request.GET.get('q', '').strip()
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    estado = request.GET.get('estado', '')
    tipo_examen_id = request.GET.get('tipo_examen', '')

    if q: examenes = examenes.filter(Q(paciente__rut__icontains=q) | Q(paciente__nombre_completo__icontains=q) | Q(numero_correlativo__icontains=q))
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
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"Reporte_Biopsias_Biogest_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
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
def mis_plantillas(request):
    plantillas = PlantillaPatologo.objects.filter(patologo=request.user)
    if request.method == 'POST':
        form = PlantillaPatologoForm(request.POST)
        if form.is_valid():
            nueva = form.save(commit=False)
            nueva.patologo = request.user
            nueva.save()
            messages.success(request, "Plantilla guardada con éxito.")
            return redirect('mis_plantillas')
    else:
        form = PlantillaPatologoForm()
    return render(request, 'biopsias/mis_plantillas.html', {'plantillas': plantillas, 'form': form})


# --- ENDPOINTS AJAX ---
@login_required
def buscar_paciente_por_rut(request, rut):

    try:
        paciente = Paciente.objects.get(rut=rut)
        
        if paciente:
            return JsonResponse({
                'encontrado': True,
                'nombre_completo': paciente.nombre_completo,
                'fecha_nacimiento': paciente.fecha_nacimiento.strftime('%Y-%m-%d') if paciente.fecha_nacimiento else '',
                'sexo': paciente.sexo,
                'telefono': paciente.telefono,
                'email': paciente.email
            })
    except Exception:
        pass
        
    return JsonResponse({'encontrado': False})

@login_required
def api_check_pendientes(request):
    if es_patologo(request.user):
        muestras = Examen.objects.exclude(estado='Finalizado').filter(Q(patologo__isnull=True) | Q(patologo=request.user))
        return JsonResponse({'muestras': [{'id': m.id, 'alerta_chat': m.alerta_chat_patologo} for m in muestras]})
    elif es_laboratorio(request.user):
        muestras = Examen.objects.all()
        return JsonResponse({'muestras': [{'id': m.id, 'alerta_chat': m.alerta_chat_laboratorio} for m in muestras]})
    return JsonResponse({'muestras': []})

@login_required
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
            # Si escribe el patólogo, alerta al lab (y viceversa)
            if request.user.groups.filter(name='Patólogo').exists():
                muestra.alerta_chat_laboratorio = True
            else:
                muestra.alerta_chat_patologo = True
            muestra.save()
            return JsonResponse({'status': 'ok'})

    # GET: Cargar mensajes (Muestra el nombre real del usuario)
    mensajes_db = muestra.comentarios.filter(tipo='Chat Interno').order_by('created_at')
    data = []
    for msg in mensajes_db:
        data.append({
            'id': msg.id,
            'texto': msg.comentario,
            'usuario': msg.user.get_full_name() or msg.user.username, # <--- Nombre real
            'fecha': msg.created_at.strftime('%d/%m %H:%M'),
            'es_mio': msg.user == request.user
        })
        
    return JsonResponse({'mensajes': data})

@login_required
def api_obtener_plantillas(request, tipo_examen_id):
    plantillas = PlantillaPatologo.objects.filter(patologo=request.user, tipo_examen_id=tipo_examen_id).values('id', 'titulo', 'texto_predefinido')
    return JsonResponse({'plantillas': list(plantillas)})


@login_required
@user_passes_test(es_personal_autorizado, login_url='/usuarios/login/')
def etiqueta_frasco(request, examen_id):
    """ Genera la vista HTML pura de la etiqueta para impresión térmica """
    muestra = get_object_or_404(Examen, id=examen_id)
    return render(request, 'biopsias/etiqueta_qr.html', {'muestra': muestra})



@login_required
@user_passes_test(es_patologo, login_url='/usuarios/login/')
def tomar_muestra(request):
    """ Muestra las biopsias recién ingresadas para que el patólogo se las asigne """
    # Buscar solo muestras en estado 'Ingresada'
    muestras_disponibles = Examen.objects.filter(estado='Ingresada').order_by('fecha_recepcion', 'id')
    
    if request.method == 'POST':
        muestra_id = request.POST.get('muestra_id')
        muestra = get_object_or_404(Examen, id=muestra_id)
        
        # Validación de seguridad: evitar doble asignación
        if muestra.estado == 'Ingresada':
            muestra.patologo = request.user
            muestra.estado = 'En Evaluación'
            muestra.save()
            
            Comentario.objects.create(
                examen=muestra,
                user=request.user,
                comentario="El patólogo ha tomado el caso para evaluación.",
                tipo='Asignación Médica'
            )
            messages.success(request, f"¡Muestra {muestra.numero_correlativo} asignada a su bandeja!")
            return redirect('dashboard_patologo')
        else:
            messages.error(request, "Esta muestra ya fue tomada por otro patólogo.")
            
    return render(request, 'biopsias/tomar_muestra.html', {'muestras': muestras_disponibles})