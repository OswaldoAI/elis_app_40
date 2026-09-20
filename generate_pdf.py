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
    
    # Custom Palette Styles
    primary_color = colors.HexColor("#0369a1")
    dark_bg = colors.HexColor("#0f172a")
    text_color = colors.HexColor("#1e293b")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=primary_color,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=primary_color,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=text_color,
        spaceAfter=8
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderColor=colors.HexColor("#cbd5e1"),
        borderWidth=0.5,
        borderPadding=6,
        spaceAfter=8
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0369a1"),
        backColor=colors.HexColor("#e0f2fe"),
        borderColor=colors.HexColor("#bae6fd"),
        borderWidth=0.5,
        borderPadding=8,
        spaceAfter=10
    )

    story = []

    # Header with Logo
    logo_path = "app/static/images/elis_logo.png"
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=140, height=45)
        story.append(logo_img)
        story.append(Spacer(1, 10))

    story.append(Paragraph("ELIS NÁJERA 4.0 — Documentación Técnica y Funcional", title_style))
    story.append(Paragraph("Sistema de Supervisión e Indicadores Operativos de Planta Industrial", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=15))

    # Section 1: Resumen Ejecutivo
    story.append(Paragraph("1. Resumen Ejecutivo y Objetivos", h1_style))
    story.append(Paragraph(
        "El sistema <b>ELIS NÁJERA 4.0</b> ha sido diseñado para la supervisión y control centralizado de la planta de lavandería industrial ELIS Nájera. "
        "El objetivo principal es proporcionar visibilidad en tiempo real sobre la productividad, eficiencia global del equipamiento (OEE), telemetría de máquinas "
        "y consumo de recursos clave (electricidad, agua, gas y vapor).", body_style
    ))
    story.append(Paragraph(
        "El software combina una arquitectura moderna con un diseño visual industrial de alto contraste (fondo oscuro con encabezado superior blanco), "
        "control de acceso basado en roles (RBAC) y despliegue sobre contenedores Docker en el servidor <b>Jetson Server A</b> (NVIDIA Tegra ARM64).", body_style
    ))

    # Section 2: Arquitectura
    story.append(Paragraph("2. Arquitectura de Software e Infraestructura", h1_style))
    arch_data = [
        [Paragraph("<b>Componente</b>", body_style), Paragraph("<b>Tecnología</b>", body_style), Paragraph("<b>Descripción / Rol</b>", body_style)],
        [Paragraph("Backend Core", body_style), Paragraph("Python 3.10 / FastAPI", body_style), Paragraph("Servicios API REST, middleware de JWT y routers modulares.", body_style)],
        [Paragraph("Base de Datos", body_style), Paragraph("SQLite (elis_40.db)", body_style), Paragraph("Persistencia ligera y rápida con volumen Docker permanente.", body_style)],
        [Paragraph("Frontend UI", body_style), Paragraph("HTML5 / CSS3 / JS TS", body_style), Paragraph("Interfaz dinamicamente renderizada con tema oscuro y header blanco.", body_style)],
        [Paragraph("Servidor Edge", body_style), Paragraph("Jetson Server A", body_style), Paragraph("IP: 100.121.212.67, Linux Tegra aarch64.", body_style)],
        [Paragraph("Contenedor", body_style), Paragraph("Docker (elis_industry4_app)", body_style), Paragraph("Mapeado al puerto 8084:8000 con reinicio automático.", body_style)],
        [Paragraph("Repositorio", body_style), Paragraph("GitHub (OswaldoAI/elis_app_40)", body_style), Paragraph("Control de versiones remoto y repositorio oficial.", body_style)]
    ]
    t_arch = Table(arch_data, colWidths=[110, 130, 264])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 15))

    # Section 3: Capturas de Pantalla y Vistas
    story.append(Paragraph("3. Capturas de Pantalla y Explicación de Vistas", h1_style))
    
    # Vista 1: Inicio
    story.append(Paragraph("3.1 Vista de Inicio (/inicio)", h2_style))
    story.append(Paragraph(
        "La vista de inicio incluye la cabecera blanca con el logo oficial <code>elis_logo.png</code>, el banner de bienvenida con la imagen <code>industria_40.png</code> "
        "y la cuadrícula de estado operativo de planta (100% Operativa, Disponibilidad OEE 98.4% y Rendimiento 14.2 Tn/Día).", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_inicio.png"):
        img_inicio = RLImage("pdf_assets/screenshot_inicio.png", width=500, height=280)
        story.append(img_inicio)
        story.append(Spacer(1, 10))

    # Page Break for clean presentation
    story.append(PageBreak())

    # Vista 2: Produccion
    story.append(Paragraph("3.2 Módulo de Producción y Tarjetas Gráficas de Máquinas", h2_style))
    story.append(Paragraph(
        "El módulo de Producción cuenta con 4 tarjetas gráficas dedicadas a la telemetría y estado operativo de las máquinas principales: "
        "<b>TÚNEL DE LAVADO</b>, <b>TÚNEL VT</b>, <b>CALANDRA 2</b> y <b>CALANDRA 3</b> (con integración de sistema de inspección óptica por IA en el puerto 5000).", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_produccion.png"):
        img_prod = RLImage("pdf_assets/screenshot_produccion.png", width=500, height=310)
        story.append(img_prod)
        story.append(Spacer(1, 10))

    # Vista 3: Admin y Permisos
    story.append(Paragraph("3.3 Panel de Administración de Usuarios y Matriz de Permisos", h2_style))
    story.append(Paragraph(
        "Accesible únicamente para el usuario <b>Admin</b>. Permite la administración de cuentas de usuario, restablecimiento de contraseñas y la matriz dinámica de "
        "visibilidad de módulos. Los usuarios con acceso restringido visualizan los botones en el menú lateral en tono <b>degradado como bloqueado (🔒)</b>.", body_style
    ))
    if os.path.exists("pdf_assets/screenshot_admin.png"):
        img_admin = RLImage("pdf_assets/screenshot_admin.png", width=500, height=250)
        story.append(img_admin)
        story.append(Spacer(1, 12))

    # Section 4: Modelo de Usuarios y Seguridad
    story.append(Paragraph("4. Modelo de Usuarios, Autenticación y RBAC", h1_style))
    story.append(Paragraph(
        "El sistema incluye 4 tipos de usuario predeterminados inicializados automáticamente en la base de datos SQLite:", body_style
    ))
    
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
    story.append(Spacer(1, 12))

    # Section 5: Despliegue y Repositorio
    story.append(Paragraph("5. Guía de Despliegue y Repositorios", h1_style))
    story.append(Paragraph("<b>URL de Acceso en Producción:</b> http://100.121.212.67:8084/inicio", body_style))
    story.append(Paragraph("<b>Repositorio GitHub Oficial:</b> https://github.com/OswaldoAI/elis_app_40.git", body_style))
    
    story.append(Paragraph("Comandos de despliegue Docker en Jetson Server A:", body_style))
    story.append(Paragraph(
        "cd /home/elisnajera/elis_4.0_v1<br/>"
        "sudo DOCKER_BUILDKIT=0 docker build -t elis_industry4_img .<br/>"
        "sudo docker run -d --name elis_industry4_app -p 8084:8000 --restart always -v elis_data:/app/data elis_industry4_img",
        code_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generated successfully at: {pdf_path}")

if __name__ == "__main__":
    build_pdf()
