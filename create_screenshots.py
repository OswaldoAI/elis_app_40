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
    img = Image.new('RGB', (1200, 750), color='#0f172a')
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([0, 0, 1200, 65], fill='#ffffff')
    if os.path.exists('app/static/images/elis_logo.png'):
        logo = Image.open('app/static/images/elis_logo.png').convert('RGBA')
        logo.thumbnail((140, 45))
        img.paste(logo, (20, 10), logo)
    draw.text((180, 20), "ELIS NÁJERA 4.0 - MÓDULO DE PRODUCCIÓN (DATOS TIEMPO REAL MQTT)", fill='#0369a1')
    draw.text((180, 40), "Túnel de Lavado | Sincronizado con Turno Activo", fill='#64748b')

    # Title
    draw.text((30, 80), "🏭 Monitoreo de Túnel de Lavado (Integrado Mosquitto MQTT: elis/lavanderia/tunel/carga)", fill='#38bdf8')

    # Card Túnel de Lavado
    x, y = 30, 115
    draw.rectangle([x, y, x + 1140, y + 610], fill='#1e293b', outline='#0284c7')
    draw.rectangle([x, y, x + 1140, y + 6], fill='#0284c7')

    draw.text((x + 20, y + 20), "TÚNEL DE LAVADO - LAVANDERÍA INDUSTRIAL", fill='#ffffff')
    draw.text((x + 20, y + 42), "Lenovo ThinkCentre PLC FX3U (HELMS Protocol) | Broker: 192.168.0.116:1883", fill='#94a3b8')
    draw.rectangle([x + 970, y + 20, x + 1110, y + 50], fill='#064e3b', outline='#10b981')
    draw.text((x + 985, y + 28), "🟢 EN LÍNEA MQTT", fill='#34d399')

    # Shift Banner with current date
    draw.rectangle([x + 20, y + 70, x + 1110, y + 110], fill='#0f172a', outline='#0284c7')
    draw.text((x + 30, y + 83), "🕒 TURNO ACTIVO: Turno 2 (14:00 - 21:00) — 21/09/2026", fill='#38bdf8')
    draw.text((x + 850, y + 83), "📡 Tópico: elis/lavanderia/tunel/carga", fill='#a7f3d0')

    # Grid 2x2 for KPIs
    kpis = [
        ("KG TOTALES TURNO", "8.950 kg", "Meta Objetivo: 14.400 kg", "#38bdf8"),
        ("CARGAS TOTALES TURNO", "172 cargas", "Registradas en Turno Actual", "#34d399"),
        ("hProd (PRODUCTIVIDAD/HORA)", "1.790 kg/h", "Rendimiento Horario del Turno", "#fbbf24"),
        ("ikProd (INDICADOR CLAVE)", "68.5%", "🟢 Semáforo Verde (>60%) | Texto en Verde (#34d399)", "#34d399")
    ]

    for idx, (title, main_val, sub_val, color) in enumerate(kpis):
        col = idx % 2
        row = idx // 2
        kx = x + 20 + col * 555
        ky = y + 125 + row * 125
        draw.rectangle([kx, ky, kx + 535, ky + 110], fill='#0f172a', outline='#334155')
        draw.text((kx + 20, ky + 15), title, fill='#94a3b8')
        draw.text((kx + 20, ky + 40), main_val, fill=color)
        draw.text((kx + 20, ky + 80), sub_val, fill='#cbd5e1')

    # Formula Callout Box inside card
    draw.rectangle([x + 20, y + 390, x + 1110, y + 450], fill='#0c4a6e', outline='#0284c7')
    draw.text((x + 30, y + 402), "💡 Fórmula Aplicada ikProd con Semáforo de Texto Numérico:", fill='#38bdf8')
    draw.text((x + 30, y + 423), "ikProd = (Prom. Peso Cargas / Prom. Tiempo entre Cargas) | Texto Numérico: Rojo <30% | Naranja 30-60% | Verde >60%", fill='#f8fafc')

    # Latest Load Telemetry
    draw.text((x + 20, y + 470), "ÚLTIMA CARGA RECIBIDA VÍA MQTT (Tópico: elis/lavanderia/tunel/carga):", fill='#fbbf24')
    draw.rectangle([x + 20, y + 495, x + 1110, y + 580], fill='#0f172a', outline='#334155')
    draw.text((x + 30, y + 510), "Load ID: #703  |  Timestamp: 21/09/2026 20:42:15  |  Cliente: #150  |  Categoría: 4", fill='#f8fafc')
    draw.text((x + 30, y + 535), "Peso Carga: 59.0 kg  |  Tiempo entre cargas: 185 seg (3.08 min)  |  HEX: 1A40 10DC", fill='#38bdf8')
    draw.text((x + 30, y + 558), "Dispositivo: Lenovo ThinkCentre PLC FX3U  |  Sitio: Elis Lavanderia Industrial", fill='#94a3b8')

    img.save('pdf_assets/screenshot_produccion.png')
    print("Created screenshot_produccion.png")

def create_mockup_expanded():
    img = Image.new('RGB', (1200, 750), color='#0f172a')
    draw = ImageDraw.Draw(img)

    # Clean Top Header (No sidebar)
    draw.rectangle([0, 0, 1200, 65], fill='#ffffff')
    if os.path.exists('app/static/images/elis_logo.png'):
        logo = Image.open('app/static/images/elis_logo.png').convert('RGBA')
        logo.thumbnail((140, 45))
        img.paste(logo, (20, 10), logo)
    draw.text((180, 20), "ELIS NÁJERA 4.0 - DASHBOARD AMPLIADO TÚNEL DE LAVADO", fill='#0369a1')
    draw.text((180, 40), "Vista de Producción Simplificada sin Menú Lateral ni Tarjetas Secundarias", fill='#64748b')

    # Banner Turno Activo
    draw.rectangle([30, 80, 1170, 125], fill='#0c4a6e', outline='#0284c7')
    draw.text((50, 95), "🕒 TURNO ACTIVO: Turno 2 (14:00 - 21:00) — 21/09/2026", fill='#ffffff')
    draw.text((880, 95), "🟢 MQTT BROKER CONECTADO", fill='#34d399')

    # Main KPI Cards (4 Cards)
    # Card 1: ikProd High Impact with Dynamic Semáforo Text Color
    draw.rectangle([30, 145, 305, 340], fill='#1e293b', outline='#10b981')
    draw.rectangle([30, 145, 305, 175], fill='#0f172a')
    draw.text((45, 153), "ikProd (EFICIENCIA TURNO)", fill='#38bdf8')
    draw.text((50, 190), "68.5%", fill='#34d399') # Dynamic Semáforo Color (Green)
    draw.text((50, 240), "Valor Neto: 20.5", fill='#f8fafc')
    draw.rectangle([50, 265, 280, 290], fill='#0f172a', outline='#334155')
    draw.text((60, 271), "Tprom: 2.5 min", fill='#38bdf8')
    draw.text((50, 305), "Fórmula: (Kg_prom / Tprom) / 30", fill='#94a3b8')

    # Card 2: hProd
    draw.rectangle([320, 145, 595, 340], fill='#1e293b', outline='#38bdf8')
    draw.rectangle([320, 145, 595, 175], fill='#075985')
    draw.text((335, 153), "hProd (PRODUCTIVIDAD HORARIA)", fill='#7dd3fc')
    draw.text((340, 190), "1.790 kg/h", fill='#38bdf8')
    draw.text((340, 240), "Kilos procesados por hora", fill='#f8fafc')
    draw.text((340, 270), "Calculado dinámicamente", fill='#94a3b8')
    draw.text((340, 295), "durante el turno activo", fill='#94a3b8')

    # Card 3: Kg Totales Turno
    draw.rectangle([610, 145, 885, 340], fill='#1e293b', outline='#fbbf24')
    draw.rectangle([610, 145, 885, 175], fill='#78350f')
    draw.text((625, 153), "KG TOTALES TURNO", fill='#fde047')
    draw.text((630, 190), "8.950 kg", fill='#fbbf24')
    draw.rectangle([630, 245, 865, 275], fill='#0f172a', outline='#d97706')
    draw.text((640, 253), "Meta Objetivo: 14.400 kg", fill='#fbbf24')
    draw.text((630, 295), "Progreso Turno: 62.1%", fill='#94a3b8')

    # Card 4: Cargas Totales Turno
    draw.rectangle([900, 145, 1170, 340], fill='#1e293b', outline='#c084fc')
    draw.rectangle([900, 145, 1170, 175], fill='#581c87')
    draw.text((915, 153), "CARGAS TOTALES TURNO", fill='#e9d5ff')
    draw.text((920, 190), "172 cargas", fill='#c084fc')
    draw.text((920, 240), "Peso Promedio: 52.0 kg", fill='#f8fafc')
    draw.text((920, 270), "Tiempo Promedio: 2.5 min", fill='#94a3b8')

    # Recent Loads Table (MQTT Feed)
    draw.text((30, 360), "📋 HISTORIAL DE CARGAS RECIBIDAS EN EL TURNO ACTIVO (MQTT: elis/lavanderia/tunel/carga)", fill='#38bdf8')
    
    headers = ["Load ID", "Hora / Fecha", "Cliente", "Categoría", "Peso (kg)", "Tiempo s/Carga (s)"]
    draw.rectangle([30, 385, 1170, 415], fill='#0f172a', outline='#334155')
    for i, h in enumerate(headers):
        draw.text((40 + i * 190, 395), h, fill='#38bdf8')

    loads_sample = [
        ("703", "21/09/2026 20:42:15", "150 - Hotel Nájera", "Cat 4 - Mantelería", "59.0 kg", "185 seg (3.08 min)"),
        ("702", "21/09/2026 20:39:10", "150 - Hotel Nájera", "Cat 4 - Mantelería", "54.5 kg", "175 seg (2.91 min)"),
        ("701", "21/09/2026 20:36:15", "112 - Residencia Rioja", "Cat 2 - Sábanas", "51.0 kg", "160 seg (2.66 min)"),
        ("700", "21/09/2026 20:33:35", "112 - Residencia Rioja", "Cat 2 - Sábanas", "53.2 kg", "168 seg (2.80 min)"),
        ("699", "21/09/2026 20:30:47", "089 - Clínica Nájera", "Cat 1 - Hospitalario", "48.0 kg", "152 seg (2.53 min)")
    ]

    for idx, row in enumerate(loads_sample):
        ry = 420 + idx * 45
        bg = '#1e293b' if idx % 2 == 0 else '#0f172a'
        draw.rectangle([30, ry, 1170, ry + 40], fill=bg, outline='#334155')
        for c_idx, val in enumerate(row):
            draw.text((40 + c_idx * 190, ry + 12), val, fill='#f8fafc')

    img.save('pdf_assets/screenshot_expanded.png')
    print("Created screenshot_expanded.png")

def create_mockup_admin():
    img = Image.new('RGB', (1200, 600), color='#0f172a')
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, 1200, 65], fill='#ffffff')
    if os.path.exists('app/static/images/elis_logo.png'):
        logo = Image.open('app/static/images/elis_logo.png').convert('RGBA')
        logo.thumbnail((140, 45))
        img.paste(logo, (20, 10), logo)
    draw.text((180, 20), "ELIS NÁJERA 4.0 - PANEL DE ADMINISTRACIÓN Y PERMISOS", fill='#0369a1')

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
    create_mockup_expanded()
    create_mockup_admin()
