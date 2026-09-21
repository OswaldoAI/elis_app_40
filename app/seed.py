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

    conn.commit()
    conn.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed_database()
