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

    conn.commit()
    conn.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database()
