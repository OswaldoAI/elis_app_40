import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "elis_40.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Tabla de Módulos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        icon TEXT NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)
    
    # Tabla de Permisos por Rol y Módulo
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        module_code TEXT NOT NULL,
        can_view INTEGER DEFAULT 1,
        can_edit INTEGER DEFAULT 0,
        UNIQUE(role, module_code)
    )
    """)
    
    # Tabla de Cache de Turnos (Sincronizado cada 30 min desde Jetson Server 1: 192.168.0.137:5001)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shift_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_name TEXT UNIQUE NOT NULL,
        data_json TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de Telemetría de Cargas del Túnel de Lavado (MQTT Broker 192.168.0.116:1883)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tunel_cargas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        load_id INTEGER UNIQUE,
        site TEXT,
        device TEXT,
        timestamp TEXT,
        timestamp_iso TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cliente INTEGER,
        categoria INTEGER,
        peso_kg REAL,
        tiempo_entre_cargas_seg INTEGER,
        raw_hex TEXT
    )
    """)
    
    # Migración de columna timestamp_iso si no existe
    try:
        cursor.execute("ALTER TABLE tunel_cargas ADD COLUMN timestamp_iso TEXT")
    except Exception:
        pass

    # Rellenar timestamp_iso para registros existentes que tengan formato DD/MM/YYYY HH:MM:SS
    cursor.execute("""
        UPDATE tunel_cargas 
        SET timestamp_iso = 
            substr(timestamp, 7, 4) || '-' || 
            substr(timestamp, 4, 2) || '-' || 
            substr(timestamp, 1, 2) || ' ' || 
            substr(timestamp, 12)
        WHERE (timestamp_iso IS NULL OR timestamp_iso = '') AND timestamp LIKE '%/%/% %'
    """)
    
    # Tabla de Persistencia de Paquetes JSON de Turnos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS turnos_persistencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shift_key TEXT UNIQUE NOT NULL,
        fecha TEXT NOT NULL,
        nombre_turno TEXT NOT NULL,
        hora_inicio TEXT NOT NULL,
        hora_fin TEXT NOT NULL,
        total_kg REAL DEFAULT 0,
        total_cargas INTEGER DEFAULT 0,
        ikprod_pct REAL DEFAULT 0,
        data_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de Telemetría de Agua Túnel y Lavadoras (0,1 m3 por pulso)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agua_tunel_telemetria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variable TEXT DEFAULT 'AGUA_TUNEL_LAVADORAS',
        timestamp TEXT NOT NULL,
        timestamp_iso TEXT NOT NULL,
        pulsos INTEGER NOT NULL,
        volumen_m3 REAL NOT NULL,
        caudal_m3h REAL DEFAULT 0.0,
        dispositivo TEXT DEFAULT 'Contador Pulsos Agua 192.168.0.116:3000',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de Telemetría General de Procesos (Agua, Gas, Electricidad)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS procesos_telemetria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variable TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        timestamp_iso TEXT NOT NULL,
        pulsos INTEGER DEFAULT 1,
        valor REAL NOT NULL,
        unidad TEXT DEFAULT 'm³',
        caudal_m3h REAL DEFAULT 0.0,
        dispositivo TEXT DEFAULT 'Monitor Telemetria 192.168.0.116:3000',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


