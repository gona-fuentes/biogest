# biopsias/utils.py
import os
import hashlib
from io import BytesIO
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import get_template
from xhtml2pdf import pisa

def link_callback(uri, rel):
    """
    Traduce las URLs de las imágenes (ej: /media/firmas/firma.jpg) a rutas físicas
    reales del disco duro (ej: C:/Proyectos/.../media/firmas/firma.jpg) para que
    xhtml2pdf pueda incrustarlas en el documento.
    """
    # Si es una URL de internet, ignorarla
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri

    # Buscar la ruta de la carpeta MEDIA (donde guardas las firmas)
    media_root = getattr(settings, 'MEDIA_ROOT', '')
    media_url = getattr(settings, 'MEDIA_URL', '/media/')

    # Limpiamos la URI para unirla con la ruta física
    if uri.startswith(media_url):
        uri_clean = uri.replace(media_url, "", 1)
    else:
        uri_clean = uri.lstrip('/')
        
    path = os.path.join(media_root, uri_clean)

    # Si el archivo existe físicamente, retornamos la ruta absoluta
    if os.path.isfile(path):
        return path
    
    # Si no la encuentra, imprimimos una alerta en consola para avisarte
    print(f"⚠️ xhtml2pdf no encontró la imagen en: {path}")
    return uri


def generar_pdf_en_memoria(examen):
    """Convierte el HTML del informe a un archivo PDF en la memoria del servidor"""
    diagnosticos = examen.comentarios.filter(tipo='Diagnóstico / Nota').order_by('created_at')
    
    cadena_verificacion = f"{examen.numero_correlativo}|{examen.paciente.rut}|{examen.updated_at}|{examen.patologo.username if examen.patologo else 'S/N'}"
    hash_verificacion = hashlib.sha256(cadena_verificacion.encode('utf-8')).hexdigest().upper()
    
    context = {
        'muestra': examen,
        'diagnosticos': diagnosticos,
        'hash_verificacion': hash_verificacion
    }
    
    template = get_template('biopsias/informe_pdf.html')
    html = template.render(context)
    
    # SOLUCIÓN ERROR 1: Eliminar FontAwesome del string HTML porque xhtml2pdf no soporta CSS moderno.
    # (Al eliminarlo solo de esta variable 'html', no afectará tu vista web normal).
    html = html.replace('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">', '')
    
    result = BytesIO()
    
    # SOLUCIÓN ERROR 2: Pasamos la función 'link_callback' para que traduzca las rutas de las firmas.
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return result.getvalue()
    return None


def enviar_informe_por_correo(examen, email_destino):
    asunto = f"Informe de Biopsia Finalizado - {examen.numero_correlativo}"
    
    cuerpo_html = f"""
    <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
        <h2 style="color: #047857; border-bottom: 2px solid #047857; padding-bottom: 10px;">Informe Histopatológico Finalizado</h2>
        <p>Estimado(a) Colega,</p>
        <p>Se ha emitido y firmado digitalmente el informe correspondiente a la muestra <strong>{examen.numero_correlativo}</strong> del paciente <strong>{examen.paciente.nombre_completo}</strong>.</p>
        <p>Adjunto a este correo encontrará el documento oficial en formato PDF, listo para impresión o registro en ficha clínica.</p>
        <br>
        <p style="font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 10px;">
            Atentamente,<br><strong>Equipo Biogest</strong><br>contacto@gona.cl
        </p>
    </div>
    """

    email = EmailMessage(
        subject=asunto,
        body=cuerpo_html,
        from_email='contacto@gona.cl', 
        to=[email_destino],
    )
    email.content_subtype = "html"

    print(f"----> Generando PDF para {examen.numero_correlativo}...")
    pdf_bytes = generar_pdf_en_memoria(examen)
    
    if pdf_bytes:
        email.attach(f"Informe_{examen.numero_correlativo}.pdf", pdf_bytes, 'application/pdf')
        print("----> PDF adjuntado correctamente.")
    else:
        print("----> ✕ Error generando el PDF en memoria.")

    email.send(fail_silently=False)
    print("----> ¡Correo enviado con PDF adjunto!")