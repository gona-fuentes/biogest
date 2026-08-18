import os
import django
import random
import uuid
from datetime import timedelta
from django.utils import timezone

# Configurar el entorno de Django para poder usar los modelos desde este script suelto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biogest.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from biopsias.models import Paciente, Laboratorio, Medico, TipoExamen, Examen, Comentario

User = get_user_model()

def poblar_base_de_datos():
    print("🚀 Iniciando población de la base de datos...")

    # 1. CREAR GRUPOS
    grupo_patologo, _ = Group.objects.get_or_create(name='Patólogo')
    grupo_lab, _ = Group.objects.get_or_create(name='Laboratorio')

    # 2. CREAR USUARIOS DE PRUEBA
    print("👤 Creando usuarios...")
    admin, _ = User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'is_staff': True})
    if _: admin.set_password('admin123'); admin.save()

    patologo1, _ = User.objects.get_or_create(username='dr_house', defaults={'first_name': 'Gregory', 'last_name': 'House'})
    if _: patologo1.set_password('patologo123'); patologo1.groups.add(grupo_patologo); patologo1.save()

    patologo2, _ = User.objects.get_or_create(username='dra_grey', defaults={'first_name': 'Meredith', 'last_name': 'Grey'})
    if _: patologo2.set_password('patologo123'); patologo2.groups.add(grupo_patologo); patologo2.save()

    lab1, _ = User.objects.get_or_create(username='lab_central', defaults={'first_name': 'Laboratorio', 'last_name': 'Central'})
    if _: lab1.set_password('lab123'); lab1.groups.add(grupo_lab); lab1.save()

    # 3. CREAR ENTIDADES BASE
    print("🏥 Creando laboratorios, médicos y tipos de examen...")
    lab_obj, _ = Laboratorio.objects.get_or_create(nombre='Biogest Red de Salud', email='laboratorio@biogest.cl')
    
    medicos = [
        Medico.objects.get_or_create(nombre='Dr. Juan Pérez', email='juan.perez@clinica.cl')[0],
        Medico.objects.get_or_create(nombre='Dra. Ana Silva', email='ana.silva@clinica.cl')[0],
    ]

    tipos = [
        TipoExamen.objects.get_or_create(nombre='Biopsia Gástrica')[0],
        TipoExamen.objects.get_or_create(nombre='Biopsia de Piel')[0],
        TipoExamen.objects.get_or_create(nombre='Papanicolau (PAP)')[0],
        TipoExamen.objects.get_or_create(nombre='Biopsia Prostática')[0]
    ]

    print("🧑‍🤝‍🧑 Creando pacientes...")
    pacientes = []
    nombres = ['Carlos Gómez', 'María López', 'Pedro Sánchez', 'Camila Ruiz', 'Roberto Díaz']
    ruts = ['11111111-1', '22222222-2', '33333333-3', '44444444-4', '55555555-5']
    
    for i in range(5):
        p, _ = Paciente.objects.get_or_create(
            rut=ruts[i],
            defaults={'nombre_completo': nombres[i], 'email': f'paciente{i}@mail.com'}
        )
        pacientes.append(p)

    # 4. GENERAR BIOPSIAS DE PRUEBA
    print("🔬 Generando 20 biopsias históricas...")
    estados = ['Ingresada', 'En Evaluación', 'Finalizado']
    
    for i in range(20):
        correlativo = f"BIO-{uuid.uuid4().hex[:6].upper()}"
        estado_actual = random.choice(estados)
        fecha_rec = timezone.now() - timedelta(days=random.randint(1, 90)) # Fechas aleatorias últimos 3 meses
        fecha_tom = fecha_rec - timedelta(days=random.randint(1, 3)) # La toma fue 1 a 3 días antes de recibirla
        
        patologo_asignado = None
        fecha_ent = None
        es_critico = False

        if estado_actual == 'En Evaluación':
            patologo_asignado = random.choice([patologo1, patologo2])
        elif estado_actual == 'Finalizado':
            patologo_asignado = random.choice([patologo1, patologo2])
            fecha_ent = fecha_rec + timedelta(days=random.randint(2, 7)) # TAT entre 2 a 7 días
            es_critico = random.choice([True, False, False, False]) # 25% de probabilidad de ser crítico

        examen = Examen.objects.create(
            numero_correlativo=correlativo,
            paciente=random.choice(pacientes),
            laboratorio=lab_obj,
            medico_solicitante=random.choice(medicos),
            tipo_examen=random.choice(tipos),
            estado=estado_actual,
            patologo=patologo_asignado,
            resultado_critico=es_critico,
            informe_cerrado=(estado_actual == 'Finalizado'),
            fecha_toma=fecha_tom.date(),
            fecha_recepcion=fecha_rec.date(),  # <-- AHORA SÍ PASAMOS LA FECHA DE INMEDIATO
            fecha_entrega=fecha_ent.date() if fecha_ent else None, # <-- TAMBIÉN LA DE ENTREGA
            cantidad_muestras=random.randint(1, 3),
            numero_fragmentos=random.randint(1, 6)
        )
        
        # Truco para forzar la fecha de creación en el pasado para los gráficos
        # Esto ignora el auto_now_add si estuviese activo
        Examen.objects.filter(id=examen.id).update(fecha_recepcion=fecha_rec, fecha_entrega=fecha_ent)

        # Generar trazabilidad (Comentarios)
        Comentario.objects.create(examen=examen, user=lab1, tipo='Creación / Ingreso', comentario="Muestra recepcionada en laboratorio.")
        
        if patologo_asignado:
            Comentario.objects.create(examen=examen, user=patologo_asignado, tipo='Asignación Médica', comentario="Caso tomado por el patólogo.")
            
        if estado_actual == 'Finalizado':
            Comentario.objects.create(
                examen=examen, 
                user=patologo_asignado, 
                tipo='Diagnóstico / Nota', 
                comentario=f"Se analizaron los fragmentos. {'Malignidad detectada.' if es_critico else 'Tejido benigno sin alteraciones mayores.'}"
            )
            Comentario.objects.create(examen=examen, user=patologo_asignado, tipo='Cambio de estado', comentario="Cambio de estado en cadena de custodia: de 'En Evaluación' a 'Finalizado'")

    print("✅ ¡Población completada con éxito! Revisa tu Dashboard.")

if __name__ == '__main__':
    poblar_base_de_datos()