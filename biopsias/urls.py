from django.urls import path
from . import views

urlpatterns = [
    # ==========================================
    # 1. PANELES PRINCIPALES (DASHBOARDS)
    # ==========================================
    path('laboratorio/', views.dashboard, name='dashboard'),
    path('patologia/', views.dashboard_patologo, name='dashboard_patologo'),


    # ==========================================
    # 2. GESTIÓN DE BIOPSIAS Y EVALUACIÓN
    # ==========================================
    path('nueva-biopsia/', views.registrar_biopsia, name='registrar_biopsia'),
    path('muestra/<int:examen_id>/', views.detalle_muestra, name='detalle_muestra'),
    path('muestra/<int:examen_id>/pdf/', views.generar_informe_pdf, name='generar_pdf'),
    path('muestra/<int:examen_id>/etiqueta/', views.etiqueta_frasco, name='etiqueta_qr'),
    path('asignar/<int:examen_id>/', views.asignar_patologo, name='asignar_patologo'),

    # ==========================================
    # 3. FICHAS CLÍNICAS DE PACIENTES
    # ==========================================
    path('fichas/', views.lista_pacientes, name='lista_pacientes'),
    path('fichas/<int:paciente_id>/', views.detalle_paciente, name='detalle_paciente'),
    path('paciente/<int:paciente_id>/consentimiento/', views.imprimir_consentimiento, name='imprimir_consentimiento'),
    # ==========================================
    # 4. HISTORIAL, ESTADÍSTICAS Y REPORTES
    # ==========================================
    path('historial/', views.historial_filtrado, name='historial_filtrado'),
    path('estadisticas/', views.dashboard_estadisticas, name='dashboard_estadisticas'),
    path('exportar-excel/', views.exportar_excel, name='exportar_excel'),

    # ==========================================
    # 5. PLANTILLAS PERSONALES (PATÓLOGO)
    # ==========================================
    path('plantillas/', views.gestion_plantillas, name='gestion_plantillas'),
    # ==========================================
    # 6. ENDPOINTS AJAX / TIEMPO REAL (API)
    # ==========================================
    path('api/paciente/<str:rut>/', views.buscar_paciente_por_rut, name='api_buscar_paciente'),
    path('api/check-pendientes/', views.api_check_pendientes, name='api_check_pendientes'),
    path('api/chat/<int:examen_id>/', views.api_chat_examen, name='api_chat_examen'),
    path('api/plantillas/<int:tipo_examen_id>/', views.api_obtener_plantillas, name='api_obtener_plantillas'),
]