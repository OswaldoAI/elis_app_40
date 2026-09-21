import urllib.request
import json
import asyncio
import logging
from datetime import datetime
from app.database import get_db_connection

JETSON_SERVER_1_URL = "http://192.168.0.137:5001"
SYNC_INTERVAL_SECONDS = 1800  # 30 minutos

logger = logging.getLogger("turnos_sync")

def sync_turnos_from_server_1():
    """Consulta la API de turnos de Jetson Server 1 y actualiza la cache en SQLite."""
    logger.info("Sincronizando turnos desde Jetson Server 1 (192.168.0.137:5001)...")
    try:
        url_jornada = f"{JETSON_SERVER_1_URL}/api/turnos/jornada"
        req = urllib.request.urlopen(url_jornada, timeout=4)
        jornada_data = json.loads(req.read().decode('utf-8'))

        now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shift_cache (key_name, data_json, updated_at)
            VALUES ('jornada_actual', ?, ?)
            ON CONFLICT(key_name) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (json.dumps(jornada_data), now_local))
        conn.commit()
        conn.close()
        print(f"[{now_local}] ✅ Cache de Turnos actualizado exitosamente desde Jetson Server 1")
        return True
    except Exception as e:
        now_err = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now_err}] ⚠️ No se pudo conectar a Jetson Server 1 ({e}). Usando datos en cache local.")
        return False

def get_cached_turnos():
    """Obtiene los datos de turnos guardados en la base de datos local SQLite."""
    conn = get_db_connection()
    row = conn.execute("SELECT data_json, updated_at FROM shift_cache WHERE key_name = 'jornada_actual'").fetchone()
    conn.close()

    if row and row["data_json"]:
        try:
            data = json.loads(row["data_json"])
            data["cache_updated_at"] = row["updated_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return data
        except Exception:
            pass

    # Fallback predeterminado si aun no hay cache cargado
    return {
        "jornada": datetime.now().strftime("%Y-%m-%d"),
        "jornada_activa": True,
        "turno_actual": {
            "nombre": "Turno Mañana",
            "hora_inicio": "06:00",
            "hora_fin": "14:00",
            "nombre_completo": "Turno Mañana (06:00 - 14:00)"
        },
        "shifts": [
            {"name": "Turno 1", "start": "06:00", "end": "14:00", "color": "#10b981"},
            {"name": "Turno 2", "start": "14:00", "end": "21:00", "color": "#3b82f6"},
            {"name": "Turno 3", "start": "21:00", "end": "02:00", "color": "#831843"}
        ],
        "cache_updated_at": "Local default"
    }

async def turnos_sync_loop():
    """Bucle asíncrono para ejecutar la sincronización cada 30 minutos."""
    while True:
        try:
            await asyncio.to_thread(sync_turnos_from_server_1)
        except Exception as e:
            logger.error(f"Error en bucle de sincronización de turnos: {e}")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)

def start_turnos_background_sync(app):
    """Inicializa la sincronización asíncrona de turnos al arrancar FastAPI."""
    @app.on_event("startup")
    async def schedule_sync():
        asyncio.create_task(turnos_sync_loop())
