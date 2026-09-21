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
    img = Image.new('RGB', (1200, 850), color='#0f172a')
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
    draw.text((880, 95), "⚡ WEBSOCKET EN TIEMPO REAL CONECTADO", fill='#34d399')

    # Main KPI Cards (4 Cards)
    # Card 1: ikProd
    draw.rectangle([30, 145, 305, 310], fill='#1e293b', outline='#10b981')
    draw.rectangle([30, 145, 305, 175], fill='#0f172a')
    draw.text((45, 153), "ikProd (EFICIENCIA TURNO)", fill='#38bdf8')
    draw.text((50, 185), "68.5%", fill='#34d399')
    draw.text((50, 230), "Valor Neto: 20.5 | Tprom: 2.5 min", fill='#f8fafc')
    draw.text((50, 275), "Fórmula: (Kg_prom / Tprom) / 30", fill='#94a3b8')

    # Card 2: hProd
    draw.rectangle([320, 145, 595, 310], fill='#1e293b', outline='#38bdf8')
    draw.rectangle([320, 145, 595, 175], fill='#075985')
    draw.text((335, 153), "hProd (PRODUCTIVIDAD HORARIA)", fill='#7dd3fc')
    draw.text((340, 185), "1.790 kg/h", fill='#38bdf8')
    draw.text((340, 230), "Kilos procesados por hora", fill='#f8fafc')
    draw.text((340, 275), "Calculado dinámicamente en turno", fill='#94a3b8')

    # Card 3: Kg Totales Turno
    draw.rectangle([610, 145, 885, 310], fill='#1e293b', outline='#fbbf24')
    draw.rectangle([610, 145, 885, 175], fill='#78350f')
    draw.text((625, 153), "KG TOTALES TURNO", fill='#fde047')
    draw.text((630, 185), "8.950 kg", fill='#fbbf24')
    draw.text((630, 230), "Meta Objetivo: 14.400 kg", fill='#f8fafc')
    draw.text((630, 275), "Progreso Turno: 62.1%", fill='#94a3b8')

    # Card 4: Cargas Totales Turno
    draw.rectangle([900, 145, 1170, 310], fill='#1e293b', outline='#c084fc')
    draw.rectangle([900, 145, 1170, 175], fill='#581c87')
    draw.text((915, 153), "CARGAS TOTALES TURNO", fill='#e9d5ff')
    draw.text((920, 185), "172 cargas", fill='#c084fc')
    draw.text((920, 230), "Peso Promedio: 52.0 kg", fill='#f8fafc')
    draw.text((920, 275), "Tiempo Promedio: 2.5 min", fill='#94a3b8')

    # Secondary Compact Cards (Clientes & Programas)
    draw.rectangle([30, 330, 580, 410], fill='#1e293b', outline='#0284c7')
    draw.text((50, 345), "👥 CLIENTES ATENDIDOS", fill='#94a3b8')
    draw.text((50, 368), "4 Clientes", fill='#38bdf8')
    draw.text((50, 392), "Códigos de cliente únicos atendidos en el turno", fill='#cbd5e1')

    draw.rectangle([610, 330, 1170, 410], fill='#1e293b', outline='#0284c7')
    draw.text((630, 345), "🗂️ PROGRAMAS EJECUTADOS", fill='#94a3b8')
    draw.text((630, 368), "3 Programas", fill='#34d399')
    draw.text((630, 392), "Categorías y programas de lavado procesados", fill='#cbd5e1')

    # Shift Progress Dual-Axis Chart Mockup
    draw.rectangle([30, 435, 1170, 810], fill='#1e293b', outline='#334155')
    draw.text((50, 455), "📈 AVANCE PRODUCTIVO DEL TURNO (Kg/Hora vs Tiempo Acumulado entre Cargas)", fill='#38bdf8')
    draw.text((800, 455), "Eje Izq: Kg (Línea Azul) | Eje Der: Min Acum (Barras Ámbar)", fill='#94a3b8')

    # Chart Canvas Drawing
    draw.rectangle([80, 490, 1120, 760], fill='#0f172a', outline='#334155')
    
    # Grid lines
    for i in range(5):
        gy = 510 + i * 50
        draw.line([80, gy, 1120, gy], fill='#1e293b')

    # X-Axis Labels (Shift Hours)
    hours = ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"]
    for i, h in enumerate(hours):
        hx = 110 + i * 135
        draw.text((hx - 15, 770), h, fill='#94a3b8')
        # Bars (Tiempo Acumulado)
        t_height = [32, 28, 35, 30, 26, 31, 29, 0][i] * 4
        if t_height > 0:
            draw.rectangle([hx - 20, 750 - t_height, hx + 20, 750], fill='#d97706', outline='#fbbf24')

    # Line (Kg producidos / hora)
    kg_points = [(110, 620), (245, 570), (380, 540), (515, 560), (650, 530), (785, 520), (920, 540), (1055, 750)]
    draw.line(kg_points, fill='#38bdf8', width=4)
    for px, py in kg_points:
        draw.ellipse([px-5, py-5, px+5, py+5], fill='#0284c7', outline='#38bdf8')

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
