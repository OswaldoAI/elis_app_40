from app.database import get_db_connection, init_db
from app.auth import hash_password

def seed_database():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Crear Módulos Base
    modules = [
        ('produccion', 'Producción', 'fa-industry', 'Gestión, control y monitoreo de la producción de lavandería'),
        ('consumos', 'Consumos', 'fa-bolt', 'Monitoreo de consumos energéticos, agua, gas y vapor')
    ]
    
    for code, name, icon, desc in modules:
        cursor.execute("""
            INSERT INTO modules (code, name, icon, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET name=excluded.name, icon=excluded.icon, description=excluded.description
        """, (code, name, icon, desc))

    # 2. Crear Usuarios Iniciales
    # Admin password: admin1, others: admin
    initial_users = [
        ('Admin', 'Administrador del Sistema', 'Admin', hash_password('admin1')),
        ('mtto', 'Técnico de Mantenimiento', 'mtto', hash_password('admin')),
        ('producción', 'Supervisor de Producción', 'producción', hash_password('admin')),
        ('Dirección', 'Director de Planta', 'Dirección', hash_password('admin'))
    ]

    for username, full_name, role, pwd_hash in initial_users:
        cursor.execute("""
            INSERT INTO users (username, full_name, role, password_hash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET full_name=excluded.full_name, role=excluded.role
        """, (username, full_name, role, pwd_hash))

    # 3. Asignar Permisos Iniciales por Rol
    # Admin y Dirección -> produccion & consumos
    # producción -> produccion
    # mtto -> consumos
    default_permissions = [
        # Rol, module_code, can_view, can_edit
        ('Admin', 'produccion', 1, 1),
        ('Admin', 'consumos', 1, 1),
        ('Dirección', 'produccion', 1, 1),
        ('Dirección', 'consumos', 1, 1),
        ('producción', 'produccion', 1, 1),
        ('producción', 'consumos', 0, 0),
        ('mtto', 'produccion', 0, 0),
        ('mtto', 'consumos', 1, 1)
    ]

    for role, module_code, can_view, can_edit in default_permissions:
        cursor.execute("""
            INSERT INTO role_permissions (role, module_code, can_view, can_edit)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(role, module_code) DO UPDATE SET can_view=excluded.can_view, can_edit=excluded.can_edit
        """, (role, module_code, can_view, can_edit))

    # 4. Sembrar datos iniciales de telemetría de agua (1 pulso = 0,1 m3)
    cursor.execute("SELECT COUNT(*) FROM agua_tunel_telemetria")
    if cursor.fetchone()[0] == 0:
        from datetime import datetime, timedelta
        now = datetime.now()
        seed_records = [
            (now - timedelta(hours=6), 25, 2.5, 12.5),
            (now - timedelta(hours=5), 30, 3.0, 15.0),
            (now - timedelta(hours=4), 35, 3.5, 17.5),
            (now - timedelta(hours=3), 28, 2.8, 14.0),
            (now - timedelta(hours=2), 32, 3.2, 16.0),
            (now - timedelta(hours=1), 40, 4.0, 20.0),
            (now, 18, 1.8, 14.2)
        ]
        for ts_dt, pulsos, vol, caudal in seed_records:
            ts_str = ts_dt.strftime("%d/%m/%Y %H:%M:%S")
            ts_iso = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO agua_tunel_telemetria (variable, timestamp, timestamp_iso, pulsos, volumen_m3, caudal_m3h)
                VALUES ('AGUA_TUNEL_LAVADORAS', ?, ?, ?, ?, ?)
            """, (ts_str, ts_iso, pulsos, vol, caudal))

    # 5. Sembrar datos iniciales para todas las 14 variables de telemetría de procesos
    cursor.execute("SELECT COUNT(*) FROM procesos_telemetria")
    if cursor.fetchone()[0] == 0:
        from datetime import datetime, timedelta
        now = datetime.now()
        
        variables_config = [
            ('AGUA_GENERAL', 'm³', 0.1, 18.5),
            ('sensor_gas_general', 'm³', 1.0, 154.0),
            ('I_gneral', 'kWh', 1.0, 345.2),
            ('AGUA_TUNEL_LAVADORAS', 'm³', 0.1, 14.2),
            ('Túnel de Secado VT', 'm³', 0.1, 32.5),
            ('calandra1_IoT', 'm³', 0.1, 45.0),
            ('Calandra 2', 'm³', 0.1, 42.8),
            ('Calandra 3', 'm³', 0.1, 48.2),
            ('caldera1', 'm³', 0.1, 52.4),
            ('caldera2', 'm³', 0.1, 48.6),
            ('I_motor_tunel', 'kWh', 1.0, 85.4),
            ('I_bomba_calandra1', 'kWh', 1.0, 42.1),
            ('Bomba_calandra2', 'kWh', 1.0, 39.8),
            ('I_bomba_calandra3', 'kWh', 1.0, 46.5)
        ]
        
        for var_code, unidad, mult, caudal in variables_config:
            for i in range(6, -1, -1):
                ts_dt = now - timedelta(hours=i)
                ts_str = ts_dt.strftime("%d/%m/%Y %H:%M:%S")
                ts_iso = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
                pulsos = 15 + (i * 3)
                valor = round(pulsos * mult, 2)
                cursor.execute("""
                    INSERT INTO procesos_telemetria (variable, timestamp, timestamp_iso, pulsos, valor, unidad, caudal_m3h, dispositivo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (var_code, ts_str, ts_iso, pulsos, valor, unidad, caudal, f"Monitor Telemetría 192.168.0.116:3000 ({var_code})"))

    # 6. Sembrar cargas históricas iniciales del Turno 3 (21:00 - 23:59 del 22/09) si no existen
    cursor.execute("SELECT COUNT(*) FROM tunel_cargas WHERE timestamp_iso >= '2026-09-22 21:00:00' AND timestamp_iso < '2026-09-23 00:00:00'")
    if cursor.fetchone()[0] == 0:
        cargas_iniciales_turno3 = [
            (1590, "22/09/2026 21:15:20", "2026-09-22 21:15:20", 851, 1, 58.0, 120, "32B0 4010"),
            (1591, "22/09/2026 21:38:40", "2026-09-22 21:38:40", 851, 1, 60.0, 140, "32B0 4020"),
            (1592, "22/09/2026 22:05:10", "2026-09-22 22:05:10", 851, 1, 57.0, 115, "32B0 4030"),
            (1593, "22/09/2026 22:32:30", "2026-09-22 22:32:30", 851, 1, 59.0, 125, "32B0 4040"),
            (1594, "22/09/2026 23:02:15", "2026-09-22 23:02:15", 851, 1, 58.0, 110, "32B0 4050"),
            (1595, "22/09/2026 23:28:45", "2026-09-22 23:28:45", 851, 1, 61.0, 130, "32B0 4060"),
            (1596, "22/09/2026 23:55:10", "2026-09-22 23:55:10", 851, 1, 57.5, 120, "32B0 4070")
        ]
        for lid, ts, ts_iso, cli, cat, peso, tseg, raw in cargas_iniciales_turno3:
            cursor.execute("""
                INSERT OR IGNORE INTO tunel_cargas (load_id, site, device, timestamp, timestamp_iso, cliente, categoria, peso_kg, tiempo_entre_cargas_seg, raw_hex)
                VALUES (?, 'Elis Lavanderia Industrial', 'Lenovo ThinkCentre PLC FX3U (HELMS Protocol)', ?, ?, ?, ?, ?, ?, ?)
            """, (lid, ts, ts_iso, cli, cat, peso, tseg, raw))

    # 7. Sembrar cargas para el Turno 1 de hoy (23/09/2026 06:00 - 14:00) si no existen
    cursor.execute("SELECT COUNT(*) FROM tunel_cargas WHERE timestamp_iso >= '2026-09-23 06:00:00' AND timestamp_iso <= '2026-09-23 14:00:00'")
    if cursor.fetchone()[0] == 0:
        from datetime import datetime, timedelta
        dt_start = datetime.strptime("2026-09-23 06:00:00", "%Y-%m-%d %H:%M:%S")
        now_dt = datetime.now()
        limit_dt = min(now_dt, datetime.strptime("2026-09-23 14:00:00", "%Y-%m-%d %H:%M:%S"))
        
        last_id_row = cursor.execute("SELECT COALESCE(MAX(load_id), 1600) FROM tunel_cargas").fetchone()
        next_load_id = (last_id_row[0] if last_id_row and last_id_row[0] else 1600) + 1

        curr_dt = dt_start + timedelta(minutes=10)
        clientes_pool = [120, 150, 210, 305, 412, 518, 851]
        categorias_pool = [1, 2, 4, 7, 12, 18, 21, 33, 36]

        cargas_inserted = 0
        while curr_dt <= limit_dt:
            ts_str = curr_dt.strftime("%d/%m/%Y %H:%M:%S")
            ts_iso = curr_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            peso = round(56.0 + (cargas_inserted % 7) * 1.1, 1)
            t_seg = 115 + (cargas_inserted % 5) * 6
            cliente = clientes_pool[cargas_inserted % len(clientes_pool)]
            categoria = categorias_pool[cargas_inserted % len(categorias_pool)]

            cursor.execute("""
                INSERT OR IGNORE INTO tunel_cargas 
                (load_id, site, device, timestamp, timestamp_iso, cliente, categoria, peso_kg, tiempo_entre_cargas_seg, raw_hex)
                VALUES (?, 'Elis Lavanderia Industrial', 'Lenovo ThinkCentre PLC FX3U (HELMS Protocol)', ?, ?, ?, ?, ?, ?, '32B0 4010')
            """, (next_load_id, ts_str, ts_iso, cliente, categoria, peso, t_seg))

            next_load_id += 1
            cargas_inserted += 1
            curr_dt += timedelta(minutes=2, seconds=15)

    conn.commit()
    conn.close()

    # 8. Sincronizar automáticamente todos los turnos históricos desde la tabla de cargas
    try:
        from app.routers.produccion_router import sync_all_historical_shifts
        sync_all_historical_shifts()
    except Exception as e:
        print(f"Error sincronizando turnos históricos en seed: {e}")

    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database()
