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
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=secondary_color,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=text_color,
        spaceAfter=6
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderColor=colors.HexColor("#cbd5e1"),
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=6
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0369a1"),
        backColor=colors.HexColor("#f0f9ff"),
        borderColor=colors.HexColor("#bae6fd"),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )

    story = []

    # Header with Logo
    logo_path = "app/static/images/elis_logo.png"
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=130, height=42)
        story.append(logo_img)
        story.append(Spacer(1, 8))

    story.append(Paragraph("ELIS NÁJERA 4.0 — Documentación Técnica y Funcional", title_style))
    story.append(Paragraph("Sistema de Supervisión e Indicadores Operativos de Planta Industrial en Tiempo Real", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=10))

    # Section 1: Resumen Ejecutivo
    story.append(Paragraph("1. Resumen Ejecutivo y Objetivos del Sistema", h1_style))
    story.append(Paragraph(
        "El sistema <b>ELIS NÁJERA 4.0</b> constituye la plataforma centralizada de supervisión e inteligencia operativa de la planta "
        "de lavandería industrial ELIS Nájera. Permite la integración continua de telemetría de maquinaria, cálculo de indicadores de eficiencia de turno (OEE, hProd, ikProd), "
        "y monitoreo de consumos energéticos (electricidad, agua, gas y vapor).", body_style
    ))
    story.append(Paragraph(
        "Las características sobresalientes de esta versión incluyen la conexión en tiempo real al <b>Broker MQTT Mosquitto</b> para la captura automatizada de cargas "
        "del Túnel de Lavado, la sincronización dinámica con el sistema de <b>Programación de Turnos</b> (para acotar los promedios e indicadores únicamente al turno activo), "
        "la adición de la fecha de turno en tarjetas e interfaz, la meta objetivo de <b>14.400 kg por turno</b> y un Dashboard Ampliado sin menú lateral enfocado en la operabilidad.", body_style
    ))

    # Section 2: Arquitectura
    story.append(Paragraph("2. Arquitectura de Software, Infraestructura e Integraciones", h1_style))
    arch_data = [
        [Paragraph("<b>Componente</b>", body_style), Paragraph("<b>Tecnología</b>", body_style), Paragraph("<b>Descripción / Rol</b>", body_style)],
        [Paragraph("Backend Core", body_style), Paragraph("Python 3.10 / FastAPI", body_style), Paragraph("API REST modular, middleware de autenticación JWT y WebSocket/polling.", body_style)],
        [Paragraph("Broker MQTT", body_style), Paragraph("Mosquitto (192.168.0.116:1883)", body_style), Paragraph("Recepción en tiempo real de eventos de carga en tópico <code>elis/lavanderia/tunel/carga</code>.", body_style)],
        [Paragraph("Base de Datos", body_style), Paragraph("SQLite (elis_40.db)", body_style), Paragraph("Tabla <code>tunel_cargas</code> con <code>load_id UNIQUE</code> e indexación por <code>timestamp_iso</code>.", body_style)],
        [Paragraph("Sincronización Turnos", body_style), Paragraph("API Turnos (192.168.0.137:5001)", body_style), Paragraph("Sincronización automatizada con la app de turnos de planta para filtrado temporal.", body_style)],
        [Paragraph("Frontend UI", body_style), Paragraph("HTML5 / CSS3 / JavaScript", body_style), Paragraph("Tema oscuro industrial, tarjetas dinámicas, indicador ikProd multicolor y cache busting (v=4.0.4).", body_style)],
        [Paragraph("Servidor Edge", body_style), Paragraph("Jetson Server A (100.121.212.67)", body_style), Paragraph("Despliegue sobre Docker (puerto 8084) en plataforma ARM64 NVIDIA Tegra.", body_style)],
        [Paragraph("Repositorio Git", body_style), Paragraph("GitHub (OswaldoAI/elis_app_40)", body_style), Paragraph("Sincronización continua de código y versión de producción en rama <code>main</code>.", body_style)]
    ]
    t_arch = Table(arch_data, colWidths=[105, 135, 264])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 8))

    # Sub-section 2.1 MQTT
    story.append(Paragraph("2.1 Integración MQTT Mosquitto (Túnel de Lavado)", h2_style))
    story.append(Paragraph(
        "El backend mantiene una conexión permanente con el Broker MQTT Mosquitto mediante la librería <code>paho-mqtt</code> en un hilo secundario asíncrono. "
        "Cada vez que el autómata PLC FX3U del Túnel de Lavado procesa una carga, publica un paquete JSON en el tópico <code>elis/lavanderia/tunel/carga</code>:", body_style
    ))
    json_example = (
        '{\n'
        '  "site": "Elis Lavanderia Industrial",\n'
        '  "device": "Lenovo ThinkCentre PLC FX3U (HELMS Protocol)",\n'
        '  "load_id": 703,\n'
        '  "timestamp": "20/09/2026 22:00:50",\n'
        '  "cliente": 150,\n'
        '  "categoria": 4,\n'
        '  "peso_kg": 59,\n'
        '  "tiempo_entre_cargas_seg": 185,\n'
        '  "raw_hex": "1A40 10DC"\n'
        '}'
    )
    story.append(Paragraph(json_example.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))

    story.append(Paragraph(
        "El subscriptor almacena la carga de forma atómica en SQLite, convirtiendo el timestamp al formato ISO (<code>YYYY-MM-DD HH:MM:SS</code>) "
        "para garantizar consultas ordenadas por fecha y hora exactas en el turno actual.", body_style
    ))

    # Page Break for clean presentation
    story.append(PageBreak())

    # Section 3: KPIs e Indicadores Clave
    story.append(Paragraph("3. Indicadores Clave de Rendimiento (KPIs) de Turno", h1_style))
    story.append(Paragraph(
        "Con el objetivo de maximizar la eficiencia en la lavandería industrial, el sistema calcula de manera dinámica los siguientes indicadores acotados al turno activo:", body_style
    ))

    kpi_table_data = [
        [Paragraph("<b>Indicador</b>", body_style), Paragraph("<b>Fórmula / Definición</b>", body_style), Paragraph("<b>Valor Referencia / Criterio</b>", body_style)],
        [
            Paragraph("<b>Kg Totales Turno</b>", body_style),
            Paragraph("Sumatoria acumulada de <code>peso_kg</code> de cargas recibidas en el turno activo.", body_style),
            Paragraph("<b>Meta Objetivo: 14.400 kg</b> por turno.", body_style)
        ],
        [
            Paragraph("<b>Cargas Totales Turno</b>", body_style),
            Paragraph("Conteo total de eventos de carga registrados durante el turno en curso.", body_style),
            Paragraph("Medición de volumen de producción acumulado.", body_style)
        ],
        [
            Paragraph("<b>hProd (Productividad/Hora)</b>", body_style),
            Paragraph("<code>hProd = (Suma Kg Turno) / (Horas Transcurridas de Turno)</code>", body_style),
            Paragraph("Expresado en <b>kg/h</b>. Evalúa el ritmo horario del turno.", body_style)
        ],
        [
            Paragraph("<b>ikProd (Indicador Clave)</b>", body_style),
            Paragraph("<code>ikProd = (Peso Promedio Kg) * [1 / (Tiempo Promedio Cargas Min)]</code><br/><code>ikProd% = (ikProd_Neto / 30) * 100%</code>", body_style),
            Paragraph("<b>Ideal: 30 = 100%</b>.<br/>🔴 Rojo: &lt;30%<br/>🟠 Naranja: 30% - 60%<br/>🟢 Verde: &gt;60%", body_style)
        ],
        [
            Paragraph("<b>Tprom (Tiempo Promedio)</b>", body_style),
            Paragraph("<code>Tprom = (Sumatoria tiempo_entre_cargas_seg / # cargas) / 60</code>", body_style),
            Paragraph("Expresado en minutos. Mostrado en texto mediano junto al ikProd.", body_style)
        ]
    ]
    t_kpis = Table(kpi_table_data, colWidths=[120, 220, 164])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<b>Explicación del Indicador ikProd:</b> Multiplica el peso medio de las cargas por el inverso del tiempo medio entre cargas. "
        "Un ikProd igual o superior a 30 representa el 100% de la eficiencia teórica deseada de la línea. "
        "El porcentaje se destaca en fuente de mayor tamaño y cambia dinámicamente de color según el rendimiento operativo del turno.", callout_style
    ))

    # Section 4: Capturas de Pantalla y Vistas
    story.append(Paragraph("4. Capturas de Pantalla y Explicación de Vistas", h1_style))

    # 4.1 Vista Inicio
    story.append(Paragraph("4.1 Vista de Inicio (/inicio)", h2_style))
    story.append(Paragraph(
        "Panel principal con encabezado blanco institucional, logo oficial ELIS, banner 4.0 y tarjetas globales de estado de planta "
        "(100% Operativa, Disponibilidad OEE 98.4% y Rendimiento 14.2 Tn/Día).", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_inicio.png"):
        img_inicio = RLImage("pdf_assets/screenshot_inicio.png", width=500, height=270)
        story.append(img_inicio)
        story.append(Spacer(1, 8))

    # 4.2 Módulo Producción
    story.append(Paragraph("4.2 Módulo de Producción (/produccion)", h2_style))
    story.append(Paragraph(
        "Muestra la tarjeta integrada de <b>Túnel de Lavado</b> con telemetría MQTT en vivo, delimitación de datos al turno activo, "
        "fecha actual del turno, tarjeta ikProd con distintivo Tprom, indicador hProd y meta de 14.400 kg.", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_produccion.png"):
        img_prod = RLImage("pdf_assets/screenshot_produccion.png", width=500, height=310)
        story.append(img_prod)
        story.append(Spacer(1, 8))

    # Page Break for clean presentation
    story.append(PageBreak())

    # 4.3 Dashboard Ampliado
    story.append(Paragraph("4.3 Dashboard Ampliado del Túnel de Lavado", h2_style))
    story.append(Paragraph(
        "Vista simplificada y de alta visibilidad para monitores de planta. Se ha <b>eliminado el menú lateral de la izquierda</b> "
        "y las <b>tarjetas secundarias de telemetría y parámetros operativos</b>, enfocando el espacio exclusivamente en los 4 KPIs principales de turno "
        "(ikProd %, hProd kg/h, Kg Totales con Meta 14.400 kg, y Cargas Totales) más la tabla en tiempo real de cargas MQTT recibidas.", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_expanded.png"):
        img_exp = RLImage("pdf_assets/screenshot_expanded.png", width=500, height=310)
        story.append(img_exp)
        story.append(Spacer(1, 8))

    # 4.4 Admin y Permisos
    story.append(Paragraph("4.4 Panel de Administración y Matriz de Permisos (RBAC)", h2_style))
    story.append(Paragraph(
        "Permite al usuario <b>Admin</b> crear cuentas de usuario y definir la matriz de visibilidad de módulos. "
        "Los usuarios sin permiso visualizan los elementos restringidos en el menú lateral con estilo <b>degradado y candado (🔒)</b>.", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_admin.png"):
        img_admin = RLImage("pdf_assets/screenshot_admin.png", width=500, height=250)
        story.append(img_admin)
        story.append(Spacer(1, 8))

    # Section 5: Modelo de Seguridad y Usuarios
    story.append(Paragraph("5. Modelo de Seguridad, Usuarios y RBAC", h1_style))
    user_data = [
        [Paragraph("<b>Usuario</b>", body_style), Paragraph("<b>Rol</b>", body_style), Paragraph("<b>Contraseña Defecto</b>", body_style), Paragraph("<b>Permisos de Módulos</b>", body_style)],
        [Paragraph("<b>Admin</b>", body_style), Paragraph("Admin", body_style), Paragraph("<code>admin1</code>", body_style), Paragraph("Acceso Total + Panel Admin Usuarios y Permisos", body_style)],
        [Paragraph("<b>Dirección</b>", body_style), Paragraph("Dirección", body_style), Paragraph("<code>admin</code>", body_style), Paragraph("Acceso Total a Módulos Producción y Consumos", body_style)],
        [Paragraph("<b>producción</b>", body_style), Paragraph("producción", body_style), Paragraph("<code>admin</code>", body_style), Paragraph("Acceso a Producción. Consumos BLOQUEADO (🔒)", body_style)],
        [Paragraph("<b>mtto</b>", body_style), Paragraph("mtto", body_style), Paragraph("<code>admin</code>", body_style), Paragraph("Acceso a Consumos. Producción BLOQUEADO (🔒)", body_style)]
    ]
    t_users = Table(user_data, colWidths=[80, 80, 110, 234])
    t_users.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_users)
    story.append(Spacer(1, 10))

    # Section 6: Despliegue y Repositorio
    story.append(Paragraph("6. Guía de Despliegue, Servidores y Repositorio Git", h1_style))
    story.append(Paragraph("<b>URL de Producción (Planta Nájera):</b> http://100.121.212.67:8084/inicio", body_style))
    story.append(Paragraph("<b>Repositorio GitHub Oficial:</b> https://github.com/OswaldoAI/elis_app_40.git", body_style))
    
    story.append(Paragraph("Comandos para construcción y despliegue del contenedor Docker en Jetson Server A:", body_style))
    story.append(Paragraph(
        "cd /home/elisnajera/elis_4.0_v1<br/>"
        "git pull origin main<br/>"
        "sudo DOCKER_BUILDKIT=0 docker build -t elis_industry4_img .<br/>"
        "sudo docker stop elis_industry4_app && sudo docker rm elis_industry4_app<br/>"
        "sudo docker run -d --name elis_industry4_app -p 8084:8000 --restart always -v elis_data:/app/data elis_industry4_img",
        code_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {pdf_path}")

if __name__ == "__main__":
    build_pdf()
