from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('pdf_assets', exist_ok=True)

def create_mockup_inicio():
    img = Image.new('RGB', (1200, 675), color='#0f172a')
    draw = ImageDraw.Draw(img)
    
    # White Header
    draw.rectangle([0, 0, 1200, 70], fill='#ffffff')
    
    if os.path.exists('app/static/images/elis_logo.png'):
        logo = Image.open('app/static/images/elis_logo.png').convert('RGBA')
        logo.thumbnail((160, 50))
        img.paste(logo, (20, 10), logo)
    
    draw.text((200, 20), "ELIS NÁJERA 4.0 - SUPERVISIÓN PLANTA", fill='#0369a1')
    draw.text((200, 42), "Sistema de Control Industrial", fill='#64748b')
    draw.rectangle([960, 18, 1180, 52], fill='#f1f5f9', outline='#cbd5e1')
    draw.text((980, 28), "👤 Admin (Acceso Total)", fill='#0369a1')

    # Sidebar
    draw.rectangle([0, 70, 240, 675], fill='#0b1120', outline='#334155')
    draw.text((20, 90), "NAVEGACIÓN", fill='#64748b')
    draw.rectangle([10, 115, 230, 155], fill='#0284c7')
    draw.text((30, 127), "🏠 Inicio (/inicio)", fill='#ffffff')
    draw.rectangle([10, 165, 230, 205], fill='#1e293b')
    draw.text((30, 177), "🏭 Producción", fill='#94a3b8')
    draw.rectangle([10, 215, 230, 255], fill='#1e293b')
    draw.text((30, 227), "⚡ Consumos", fill='#94a3b8')
    draw.text((20, 280), "ADMINISTRACIÓN", fill='#64748b')
    draw.rectangle([10, 305, 230, 345], fill='#1e293b')
    draw.text((30, 317), "👥 Gestión Usuarios", fill='#94a3b8')

    # Content Area
    draw.rectangle([270, 95, 1170, 360], fill='#1e293b', outline='#334155')
    draw.text((290, 115), "Sistema de Supervisión Industria 4.0 - Planta Nájera", fill='#38bdf8')
    draw.text((290, 140), "Monitoreo en tiempo real de producción, eficiencia operativa OEE y consumos energéticos.", fill='#94a3b8')
    
    if os.path.exists('app/static/images/industria_40.png'):
        cover = Image.open('app/static/images/industria_40.png').convert('RGB')
        cover.thumbnail((860, 180))
        img.paste(cover, (290, 165))

    # Metric Cards
    metrics = [
        ("ESTADO PLANTA", "100% OPERATIVA", "#10b981"),
        ("DISPONIBILIDAD OEE", "98.4%", "#38bdf8"),
        ("RENDIMIENTO", "14.2 Tn/Día", "#fbbf24")
    ]
    for i, (title, val, color) in enumerate(metrics):
        x = 270 + i * 305
        draw.rectangle([x, 385, x + 285, 475], fill='#1e293b', outline='#334155')
        draw.text((x + 20, 400), title, fill='#94a3b8')
        draw.text((x + 20, 425), val, fill=color)

    img.save('pdf_assets/screenshot_inicio.png')
    print("Created screenshot_inicio.png")

def create_mockup_produccion():
    img = Image.new('RGB', (1200, 780), color='#0f172a')
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([0, 0, 1200, 65], fill='#ffffff')
    draw.text((30, 20), "ELIS NÁJERA 4.0 - MÓDULO DE PRODUCCIÓN (TÚNEL DE LAVADO ENRIQUECIDO)", fill='#0369a1')

    # Title
    draw.text((30, 80), "🏭 Monitoreo en Tiempo Real: Túnel de Lavado con Indicadores de Turno", fill='#38bdf8')

    # Tunel de Lavado Detailed Card
    x, y = 30, 120
    draw.rectangle([x, y, x + 1140, y + 620], fill='#1e293b', outline='#38bdf8')
    draw.rectangle([x, y, x + 1140, y + 6], fill='#0284c7')

    draw.text((x + 20, y + 20), "TÚNEL DE LAVADO", fill='#ffffff')
    draw.text((x + 20, y + 42), "Lavado Continuo Industrial | Planta Nájera", fill='#94a3b8')
    draw.rectangle([x + 980, y + 20, x + 1110, y + 50], fill='#064e3b', outline='#10b981')
    draw.text((x + 995, y + 28), "🟢 OPERATIVA", fill='#34d399')

    # Shift Banner
    draw.rectangle([x + 20, y + 75, x + 1110, y + 115], fill='#0f172a', outline='#0284c7')
    draw.text((x + 40, y + 88), "🕒 TURNO ACTIVO: Turno Mañana", fill='#38bdf8')
    draw.text((x + 900, y + 88), "⏰ HORARIO: 06:00 - 14:00", fill='#94a3b8')

    # Subtitle Resumen Turno Actual
    draw.text((x + 20, y + 135), "RESUMEN TURNO ACTUAL", fill='#fbbf24')
    draw.line([x + 230, y + 143, x + 1110, y + 143], fill='#334155')

    # 3 Shift Indicators
    shift_items = [
        ("PROMEDIO CARGA", "52.4 kg", "#34d399"),
        ("PROMEDIO TIEMPO DE CARGA", "2.1 min", "#38bdf8"),
        ("CANTIDAD DE CARGAS", "38 cargas", "#c084fc")
    ]
    for idx, (label, val, color) in enumerate(shift_items):
        ix = x + 20 + idx * 370
        iy = y + 160
        draw.rectangle([ix, iy, ix + 345, iy + 65], fill='#0f172a', outline='#334155')
        draw.text((ix + 15, iy + 12), label, fill='#64748b')
        draw.text((ix + 15, iy + 34), val, fill=color)

    # Key Telemetry
    draw.text((x + 20, y + 245), "PARÁMETROS OPERATIVOS Y TELEMETRÍA", fill='#ffffff')
    telemetry = [
        ("Rendimiento", "1.250 kg/h"),
        ("Temp. Agua", "74,5 °C"),
        ("Presión Prensa", "44 bar"),
        ("Dosis Detergente", "4.2 L/min")
    ]
    for i_idx, (lbl, val) in enumerate(telemetry):
        ix = x + 20 + (i_idx % 2) * 555
        iy = y + 270 + (i_idx // 2) * 65
        draw.rectangle([ix, iy, ix + 535, iy + 55], fill='#0f172a', outline='#334155')
        draw.text((ix + 15, iy + 10), lbl.upper(), fill='#64748b')
        draw.text((ix + 15, iy + 30), val, fill='#f8fafc')

    # OEE Bar
    draw.text((x + 20, y + 420), "Rendimiento OEE / Disponibilidad: 91.2% OEE", fill='#38bdf8')
    draw.rectangle([x + 20, y + 445, x + 1110, y + 462], fill='#0b1120', outline='#334155')
    draw.rectangle([x + 20, y + 445, x + 20 + 990, y + 462], fill='#10b981')

    # Program footer
    draw.rectangle([x + 20, y + 490, x + 1110, y + 530], fill='#0c4a6e', outline='#0284c7')
    draw.text((x + 30, y + 502), "▶ Programa Actual: Prog 04 - Sábanas y Mantelería Hostelería", fill='#f8fafc')

    img.save('pdf_assets/screenshot_produccion.png')
    print("Created updated screenshot_produccion.png")

def create_mockup_admin():
    img = Image.new('RGB', (1200, 600), color='#0f172a')
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 1200, 65], fill='#ffffff')
    draw.text((30, 20), "ELIS NÁJERA 4.0 - PANEL DE ADMINISTRACIÓN Y PERMISOS", fill='#0369a1')

    draw.rectangle([30, 95, 580, 560], fill='#1e293b', outline='#334155')
    draw.text((50, 115), "👥 Gestión de Usuarios y Credenciales", fill='#c084fc')
    
    users = [
        ("Admin", "Administrador Sistema", "Admin", "🟢 Activo"),
        ("Dirección", "Director de Planta", "Dirección", "🟢 Activo"),
        ("producción", "Supervisor Producción", "producción", "🟢 Activo"),
        ("mtto", "Técnico Mantenimiento", "mtto", "🟢 Activo")
    ]

    draw.rectangle([50, 150, 560, 180], fill='#0b1120')
    draw.text((60, 160), "USUARIO | NOMBRE | ROL | ESTADO", fill='#64748b')

    for i, (u, n, r, s) in enumerate(users):
        y = 190 + i * 50
        draw.rectangle([50, y, 560, y + 42], fill='#0f172a', outline='#334155')
        draw.text((60, y + 12), f"{u}  |  {n}  |  {r}  |  {s}", fill='#f8fafc')

    draw.rectangle([610, 95, 1170, 560], fill='#1e293b', outline='#334155')
    draw.text((630, 115), "⚙️ Matriz de Visibilidad y Permisos", fill='#38bdf8')

    draw.rectangle([630, 150, 1150, 180], fill='#0b1120')
    draw.text((640, 160), "ROL | MÓDULO PRODUCCIÓN | MÓDULO CONSUMOS", fill='#64748b')

    matrix = [
        ("Admin", "Permitido", "Permitido"),
        ("Dirección", "Permitido", "Permitido"),
        ("producción", "Permitido", "Bloqueado (Degradado 🔒)"),
        ("mtto", "Bloqueado (Degradado 🔒)", "Permitido")
    ]

    for i, (r, p1, p2) in enumerate(matrix):
        y = 190 + i * 50
        draw.rectangle([630, y, 1150, y + 42], fill='#0f172a', outline='#334155')
        draw.text((640, y + 12), f"{r}  ->  {p1}  |  {p2}", fill='#f8fafc')

    img.save('pdf_assets/screenshot_admin.png')
    print("Created screenshot_admin.png")

if __name__ == "__main__":
    create_mockup_inicio()
    create_mockup_produccion()
    create_mockup_admin()
