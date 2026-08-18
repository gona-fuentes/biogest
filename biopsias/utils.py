# biopsias/utils.py
import hashlib
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML

def generar_pdf_en_memoria(examen, request):
    """Convierte el HTML moderno a PDF usando WeasyPrint"""
    diagnosticos = examen.comentarios.filter(tipo='Diagnóstico / Nota').order_by('created_at')
    
    cadena_verificacion = f"{examen.numero_correlativo}|{examen.paciente.rut}|{examen.updated_at}|{examen.patologo.username if examen.patologo else 'S/N'}"
    hash_verificacion = hashlib.sha256(cadena_verificacion.encode('utf-8')).hexdigest().upper()
    
    context = {
        'muestra': examen,
        'diagnosticos': diagnosticos,
        'hash_verificacion': hash_verificacion
    }
    
    # Renderizamos tu HTML intacto (el que tiene Tailwind, FontAwesome y Flexbox)
    html_string = render_to_string('biopsias/informe_pdf.html', context)
    
    # Construimos la URL base (http://127.0.0.1:8000) para que WeasyPrint pueda descargar la firma local
    base_url = request.build_absolute_uri('/') if request else 'http://127.0.0.1:8000'
    
    # Magia: Generamos el PDF
    pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf()
    
    return pdf_bytes


def enviar_informe_por_correo(examen, email_destino, request):
    asunto = f"Informe Histopatológico Finalizado - {examen.numero_correlativo}"
    
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

    print(f"----> Generando PDF moderno para {examen.numero_correlativo}...")
    
    # IMPORTANTE: Pasamos el 'request' aquí
    pdf_bytes = generar_pdf_en_memoria(examen, request)
    
    if pdf_bytes:
        email.attach(f"Informe_{examen.numero_correlativo}.pdf", pdf_bytes, 'application/pdf')
        print("----> PDF adjuntado correctamente.")
    else:
        print("----> ✕ Error generando el PDF en memoria.")

    email.send(fail_silently=False)
    print("----> ¡Correo enviado con PDF adjunto!")