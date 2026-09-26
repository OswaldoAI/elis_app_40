import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

PDF_FILENAME = "ELIS_40_Documentacion_Tecnica_y_Funcional.pdf"

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#0369a1"))

        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "ELIS NÁJERA 4.0 — Documentación Técnica y Funcional")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer (All pages)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(54, 36, "Planta Lavandería Industrial ELIS NÁJERA 4.0")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(558, 36, page_str)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        self.restoreState()

def build_pdf():
    pdf_path = Path(__file__).parent / PDF_FILENAME
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Palette Styles
    primary_color = colors.HexColor("#0369a1")
    secondary_color = colors.HexColor("#0f172a")
    text_color = colors.HexColor("#1e293b")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=secondary_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=text_color,
        spaceAfter=5
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderColor=colors.HexColor("#cbd5e1"),
        borderWidth=0.5,
        borderPadding=4,
        spaceAfter=5
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#0369a1"),
        backColor=colors.HexColor("#f0f9ff"),
        borderColor=colors.HexColor("#bae6fd"),
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=6
    )

    story = []

    # Header with Logo
    logo_path = "app/static/images/elis_logo.png"
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=120, height=38)
        story.append(logo_img)
        story.append(Spacer(1, 6))

    story.append(Paragraph("ELIS NÁJERA 4.0 — Documentación Técnica y Funcional", title_style))
    story.append(Paragraph("Manual de Arquitectura, Métricas de Producción y Módulos del Túnel de Lavado", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=8))

    # Section 1: Resumen Ejecutivo
    story.append(Paragraph("1. Resumen Ejecutivo y Objetivos del Sistema", h1_style))
    story.append(Paragraph(
        "El sistema <b>ELIS NÁJERA 4.0</b> constituye la plataforma integral de supervisión, analítica e inteligencia operativa de la planta "
        "de lavandería industrial ELIS Nájera. Su objetivo primordial es digitalizar en tiempo real el proceso productivo, centralizar "
        "la telemetría de pesaje y ciclos de lavado del <b>Túnel de Lavado</b>, controlar la eficiencia energética y dotar a la dirección "
        "y supervisión de herramientas de análisis histórico, ranking y filtrado de turnos.", body_style
    ))
    story.append(Paragraph(
        "Esta entrega incorpora la suite avanzada del Túnel de Lavado: captura de cargas en tiempo real por MQTT, persistencia estructurada "
        "de turnos con desglose horario, el indicador de cadencia y saturación <b>ikProd</b>, la productividad horaria <b>hProd</b>, "
        "el módulo de <b>Filtrado por Rango Horario</b> con preservación de cuadrícula convencional y la pantalla interactiva de "
        "<b>Comparación y Ranking Top 5 de Turnos</b> con reconstrucción completa de dashboards.", body_style
    ))

    # Section 2: Arquitectura
    story.append(Paragraph("2. Arquitectura de Software, Infraestructura y Flujo de Datos", h1_style))
    arch_data = [
        [Paragraph("<b>Componente</b>", body_style), Paragraph("<b>Tecnología</b>", body_style), Paragraph("<b>Descripción / Rol en Planta</b>", body_style)],
        [Paragraph("Autómata Túnel", body_style), Paragraph("PLC Mitsubishi FX3U", body_style), Paragraph("Control de pesaje de tolvas, tiempos de transferencia y descarga.", body_style)],
        [Paragraph("Decodificador IoT", body_style), Paragraph("HELMS Protocol (100.105.75.39:8080)", body_style), Paragraph("Lectura de tramas RS485 del PLC y conversión a HTTP / MQTT.", body_style)],
        [Paragraph("Broker MQTT", body_style), Paragraph("Mosquitto (192.168.0.116:1883)", body_style), Paragraph("Publicación de eventos de carga en <code>elis/lavanderia/tunel/carga</code>.", body_style)],
        [Paragraph("Backend Core", body_style), Paragraph("Python 3.10 / FastAPI / Uvicorn", body_style), Paragraph("API REST, cálculo de KPIs, motor de filtrado y subagente MQTT.", body_style)],
        [Paragraph("Base de Datos", body_style), Paragraph("SQLite (elis_40.db)", body_style), Paragraph("Tablas <code>tunel_cargas</code>, <code>turnos_persistencia</code> y <code>resultados_turnos</code>.", body_style)],
        [Paragraph("Sincronizador Turnos", body_style), Paragraph("Jetson Server 1 (192.168.0.137:5001)", body_style), Paragraph("Sincronización horaria periódica de jornada industrial y pausas.", body_style)],
        [Paragraph("Frontend UI", body_style), Paragraph("HTML5 / CSS3 / Vanilla JS / Chart.js", body_style), Paragraph("Interfaz industrial oscura, técnica Zero-Flicker y gráficos con doble eje Y.", body_style)],
        [Paragraph("Servidor Edge", body_style), Paragraph("Jetson Server A (100.121.212.67:8084)", body_style), Paragraph("Contenedor Docker <code>elis_industry4_app</code> sobre NVIDIA Jetson ARM64.", body_style)]
    ]
    t_arch = Table(arch_data, colWidths=[100, 140, 264])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 6))

    story.append(Paragraph("2.1 Estructura de Tablas en Base de Datos", h2_style))
    story.append(Paragraph(
        "• <b><code>tunel_cargas</code></b>: Registro atómico de cada descarga (<code>load_id</code>, <code>peso_kg</code>, <code>tiempo_entre_cargas_seg</code>, <code>cliente</code>, <code>categoria</code>, <code>timestamp_iso</code>).<br/>"
        "• <b><code>turnos_persistencia</code></b>: Guarda el paquete JSON exhaustivo de cada turno (<code>shift_key</code>, <code>data_json</code>, <code>total_kg</code>, <code>total_cargas</code>, <code>ikprod_pct</code>), incluyendo el desglose hora a hora para reconstrucción idéntica de dashboards.<br/>"
        "• <b><code>resultados_turnos</code></b>: Vista agregada y liviana optimizada para consultas de alto rendimiento y listados históricos.<br/>"
        "• <b><code>shift_cache</code></b>: Cache local de la jornada actual y turnos configurados procedentes de Jetson Server 1.", body_style
    ))

    # Page Break
    story.append(PageBreak())

    # Section 3: Lógica de Jornada Industrial y Turnos
    story.append(Paragraph("3. Lógica de Jornada Industrial y Turnos Operativos", h1_style))
    story.append(Paragraph(
        "La planta opera bajo el concepto de <b>Jornada Industrial Continua</b>, la cual comprende cronológicamente desde las "
        "<b>05:00 AM</b> de un día hasta las <b>05:00 AM del día siguiente</b>. Cualquier registro anterior a las 05:00 AM pertenece "
        "a la jornada operativa del día previo.", body_style
    ))
    story.append(Paragraph(
        "<b>Distribución de Turnos:</b><br/>"
        "• <b>Turno 1 (Mañana):</b> 06:00 a 14:00.<br/>"
        "• <b>Turno 2 (Tarde):</b> 14:00 a 21:00.<br/>"
        "• <b>Turno 3 (Noche):</b> 21:00 a 02:00 (o hasta 06:00 de la madrugada).", body_style
    ))
    story.append(Paragraph(
        "<b>Continuidad Matemática de Medianoche:</b> En los turnos nocturnos que cruzan las 00:00 (Turno 3), las horas ≥ 21:00 "
        "corresponden a la fecha de inicio del turno, mientras que las horas menores a las 05:00 AM toman la fecha del día siguiente. "
        "Esta lógica asegura que tanto las consultas SQL como los gráficos de avance horológico mantengan una secuencia continua sin cortes.", callout_style
    ))

    # Section 4: KPIs
    story.append(Paragraph("4. Fórmulas y Métricas de Rendimiento (KPIs)", h1_style))
    kpi_table_data = [
        [Paragraph("<b>Indicador</b>", body_style), Paragraph("<b>Fórmula / Definición</b>", body_style), Paragraph("<b>Criterio / Ponderación</b>", body_style)],
        [
            Paragraph("<b>Kg Totales Turno</b>", body_style),
            Paragraph("Sumatoria acumulada de <code>peso_kg</code> de cargas en el turno activo.", body_style),
            Paragraph("<b>Meta: 14.400 kg</b> por turno completo. Barra de progreso visual.", body_style)
        ],
        [
            Paragraph("<b>Cargas Totales</b>", body_style),
            Paragraph("Conteo total de cargas reales ingresadas al túnel.", body_style),
            Paragraph("Medición de volumen físico de carga procesado.", body_style)
        ],
        [
            Paragraph("<b>hProd (Kg/Hora)</b>", body_style),
            Paragraph("<code>hProd = (Kg Totales) / (Horas Transcurridas de Turno)</code>", body_style),
            Paragraph("Velocidad de producción horaria efectiva en <b>kg/h</b>.", body_style)
        ],
        [
            Paragraph("<b>ikProd (Eficiencia)</b>", body_style),
            Paragraph("<code>ikProd_Neto = (Peso Prom. kg) / (Tiempo Prom. min)</code><br/><code>ikProd% = (ikProd_Neto / 30.0) * 100%</code>", body_style),
            Paragraph("<b>Ideal: 30 = 100%</b>.<br/>🔴 Rojo: &lt;30%<br/>🟠 Naranja: 30% - 60%<br/>🟢 Verde: &gt;60%", body_style)
        ],
        [
            Paragraph("<b>Tprom (Tiempo Medio)</b>", body_style),
            Paragraph("<code>Tprom = (Sumatoria seg / # cargas) / 60</code>", body_style),
            Paragraph("Tiempo medio de cadencia de prensa/lavado expresado en min y seg.", body_style)
        ],
        [
            Paragraph("<b>Clientes / Programas</b>", body_style),
            Paragraph("<code>COUNT(DISTINCT cliente)</code> y <code>COUNT(DISTINCT categoria)</code>", body_style),
            Paragraph("Diversidad de clientes y programas procesados en el turno.", body_style)
        ]
    ]
    t_kpis = Table(kpi_table_data, colWidths=[110, 230, 164])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 6))

    # Page Break
    story.append(PageBreak())

    # Section 5: Pantallas y Funcionalidades
    story.append(Paragraph("5. Pantallas y Funcionalidades del Módulo Túnel de Lavado", h1_style))

    # 5.1 Dashboard Ampliado
    story.append(Paragraph("5.1 Dashboard Ampliado del Túnel de Lavado (#view-tunel_lavado)", h2_style))
    story.append(Paragraph(
        "Diseñado específicamente para pantallas operativas de planta. Elimina el menú lateral para maximizar el área útil y presenta "
        "una <b>cuadrícula 4x2 de alta visibilidad</b>. Integra en la parte inferior la <b>Gráfica de Avance Productivo con Doble Eje Y</b> "
        "(barras rosa de kg/h, línea cian de kg acumulados y barras amarillas de cargas por franja horaria convencional). "
        "El refresco en vivo emplea la técnica <i>Zero-Flicker</i>, actualizando canvas y DOM in-place sin parpadeos.", body_style
    ))
    img_tunel = "pdf_assets/screenshot_tunel_ampliado.png" if os.path.exists("pdf_assets/screenshot_tunel_ampliado.png") else "pdf_assets/screenshot_expanded.png"
    if os.path.exists(img_tunel):
        story.append(RLImage(img_tunel, width=500, height=230))
        story.append(Spacer(1, 6))

    # 5.2 Filtros
    story.append(Paragraph("5.2 Pantalla de Filtros por Rango Horario (#view-filtros_turno)", h2_style))
    story.append(Paragraph(
        "Accesible mediante el botón <b>'Filtros'</b> (icono ecualizadores). Permite a los supervisores auditar cualquier ventana temporal "
        "del turno actual ingresando los campos <b>Desde</b> (HH:MM) y <b>Hasta</b> (HH:MM). Soporta cruce de medianoche en el turno nocturno. "
        "El eje X de la gráfica mantiene las franjas horarias convencionales (ej: <code>06:00 - 07:00</code>), calculando las cargas y kilogramos "
        "proporcionales de los minutos correspondientes. Si no se han escogido datos, muestra un fondo oscuro con mensaje de guía.", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_filtros.png"):
        story.append(RLImage("pdf_assets/screenshot_filtros.png", width=500, height=230))
        story.append(Spacer(1, 6))

    # Page Break
    story.append(PageBreak())

    # 5.3 Comparar y Top 5
    story.append(Paragraph("5.3 Pantalla de Comparación y Ranking Top 5 (#view-comparar_turnos)", h2_style))
    story.append(Paragraph(
        "Accesible mediante el botón <b>'Comparar'</b> (icono balanza). Permite clasificar y ranquear los 5 mejores turnos dentro de un rango "
        "de fechas personalizado (<code>Fecha Inicio</code> y <code>Fecha Fin</code>) evaluando cualquiera de los 4 criterios fundamentales: "
        "<b>ikProd (%)</b>, <b>Kg Totales</b>, <b>Cargas Totales</b> o <b>Kg / Hora (Productividad)</b>.", body_style
    ))
    story.append(Paragraph(
        "<b>Características del Ranking:</b><br/>"
        "• <b>Insignias Numéricas:</b> Cada turno muestra su posición destacada (<b>#1</b> dorado, <b>#2</b> plateado, <b>#3</b> bronce, <b>#4</b> cian y <b>#5</b> índigo).<br/>"
        "• <b>Pastillas de Indicadores:</b> Resumen visual de kilos, cargas, % ikProd y tasa hProd.<br/>"
        "• <b>Zona Activa Interactiva:</b> Al hacer clic sobre cualquier turno de la lista, se abre de inmediato un dashboard completo con la misma apariencia 4x2 del dashboard ampliado, reconstruyendo las 8 tarjetas de KPIs y la gráfica hora a hora con los datos completos almacenados en <code>turnos_persistencia</code>.", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_comparar.png"):
        story.append(RLImage("pdf_assets/screenshot_comparar.png", width=500, height=220))
        story.append(Spacer(1, 6))

    # Section 6: Catálogo Endpoints
    story.append(Paragraph("6. Catálogo de Endpoints de la API Backend (FastAPI)", h1_style))
    api_data = [
        [Paragraph("<b>Método</b>", body_style), Paragraph("<b>Endpoint</b>", body_style), Paragraph("<b>Parámetros / Payload</b>", body_style), Paragraph("<b>Descripción / Respuesta</b>", body_style)],
        [Paragraph("<code>GET</code>", body_style), Paragraph("<code>/api/produccion/tunel-lavado/dashboard</code>", body_style), Paragraph("Ninguno", body_style), Paragraph("KPIs agregados, ikProd y desglose horario del turno activo en curso.", body_style)],
        [Paragraph("<code>GET</code>", body_style), Paragraph("<code>/api/produccion/tunel-lavado/dashboard-filtrado</code>", body_style), Paragraph("<code>hora_desde</code>, <code>hora_hasta</code>", body_style), Paragraph("Métricas y gráfica recalculadas para el intervalo horario especificado.", body_style)],
        [Paragraph("<code>GET</code>", body_style), Paragraph("<code>/api/produccion/turnos/ranking</code>", body_style), Paragraph("<code>fecha_inicio</code>, <code>fecha_fin</code>, <code>criterio</code>", body_style), Paragraph("Clasificación descendente de los mejores 5 turnos del periodo.", body_style)],
        [Paragraph("<code>GET</code>", body_style), Paragraph("<code>/api/produccion/turnos/historial-json/{key}</code>", body_style), Paragraph("<code>shift_key</code> (path)", body_style), Paragraph("Paquete JSON completo con desglose para reconstrucción de dashboard.", body_style)],
        [Paragraph("<code>GET</code>", body_style), Paragraph("<code>/api/produccion/turnos/fechas-disponibles</code>", body_style), Paragraph("Ninguno", body_style), Paragraph("Listado de fechas con registros de turnos históricos.", body_style)],
        [Paragraph("<code>GET</code>", body_style), Paragraph("<code>/api/produccion/turnos/resultados</code>", body_style), Paragraph("<code>fecha</code> (opcional)", body_style), Paragraph("Consulta a la tabla liviana de resultados para resúmenes tabulares.", body_style)],
        [Paragraph("<code>POST</code>", body_style), Paragraph("<code>/api/produccion/turnos/guardar-json</code>", body_style), Paragraph("JSON con turno completo", body_style), Paragraph("Persistencia atómica de paquete de turno en <code>turnos_persistencia</code>.", body_style)]
    ]
    t_api = Table(api_data, colWidths=[45, 175, 120, 164])
    t_api.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_api)
    story.append(Spacer(1, 6))

    # Page Break
    story.append(PageBreak())

    # Section 7: Seguridad y Roles
    story.append(Paragraph("7. Modelo de Seguridad, Autenticación y Permisos (RBAC)", h1_style))
    user_data = [
        [Paragraph("<b>Usuario</b>", body_style), Paragraph("<b>Rol</b>", body_style), Paragraph("<b>Contraseña</b>", body_style), Paragraph("<b>Permisos Asignados</b>", body_style)],
        [Paragraph("<b>Admin</b>", body_style), Paragraph("Admin", body_style), Paragraph("<code>admin1</code>", body_style), Paragraph("Control total del sistema, gestión de usuarios y matriz de permisos.", body_style)],
        [Paragraph("<b>Dirección</b>", body_style), Paragraph("Dirección", body_style), Paragraph("<code>admin</code>", body_style), Paragraph("Acceso completo a Producción (Túnel, Filtros, Comparar) y Consumos.", body_style)],
        [Paragraph("<b>producción</b>", body_style), Paragraph("producción", body_style), Paragraph("<code>admin</code>", body_style), Paragraph("Acceso exclusivo a Producción. Consumos bloqueado con candado (🔒).", body_style)],
        [Paragraph("<b>mtto</b>", body_style), Paragraph("mtto", body_style), Paragraph("<code>admin</code>", body_style), Paragraph("Acceso a telemetría de Consumos energéticos. Producción bloqueado (🔒).", body_style)]
    ]
    t_users = Table(user_data, colWidths=[75, 75, 75, 279])
    t_users.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_users)
    story.append(Spacer(1, 8))

    if os.path.exists("pdf_assets/screenshot_admin.png"):
        img_admin = RLImage("pdf_assets/screenshot_admin.png", width=500, height=210)
        story.append(img_admin)
        story.append(Spacer(1, 8))

    # Section 8: Despliegue y Repositorio Git
    story.append(Paragraph("8. Guía de Despliegue y Acceso a la Plataforma", h1_style))
    story.append(Paragraph("<b>URL en Red Local de Planta:</b> http://192.168.0.116:8084/inicio#tunel_lavado", body_style))
    story.append(Paragraph("<b>URL Remota Segura (Tailscale):</b> https://elisnajera-desktop.tail2f2130.ts.net/inicio#tunel_lavado", body_style))
    story.append(Paragraph("<b>Repositorio GitHub Oficial:</b> https://github.com/OswaldoAI/elis_app_40.git", body_style))
    
    story.append(Paragraph("<b>Comandos de Construcción y Despliegue en Jetson Server A:</b>", body_style))
    story.append(Paragraph(
        "cd /home/elisnajera/elis_4.0_v1<br/>"
        "git pull origin main<br/>"
        "sudo DOCKER_BUILDKIT=0 docker build -t elis_industry4_img .<br/>"
        "sudo docker stop elis_industry4_app &amp;&amp; sudo docker rm elis_industry4_app<br/>"
        "sudo docker run -d --name elis_industry4_app -p 8084:8000 --restart always -v elis_data:/app/data elis_industry4_img",
        code_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {pdf_path}")

if __name__ == "__main__":
    build_pdf()
