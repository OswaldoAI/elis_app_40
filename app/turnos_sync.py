
def resolve_current_shift(data: dict) -> dict:
    """Verifica si el turno_actual en caché sigue vigente en el reloj local.
    Si ya expiró, busca en la lista de turnos programados el que corresponda a la hora actual."""
    shifts = data.get("shifts") or []
    if not shifts:
        return data.get("turno_actual", {})

    now_dt = get_local_now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    fecha_hoy = now_dt.strftime("%Y-%m-%d")

    # Si turno_actual existe y sigue en su ventana de tiempo, conservarlo
    t_act = data.get("turno_actual") or {}
    h_ini = t_act.get("hora_inicio")
    h_fin = t_act.get("hora_fin")
    f_shift = t_act.get("fecha") or fecha_hoy
    if h_ini and h_fin and t_act.get("is_active"):
        try:
            from app.routers.produccion_router import get_shift_start_end_iso
            s_iso, e_iso = get_shift_start_end_iso(f_shift, h_ini, h_fin)
            if s_iso <= now_str <= e_iso:
                return t_act
        except Exception:
            pass

    # Si ya expiró, evaluar cada turno de la lista 'shifts'
    for idx, s in enumerate(shifts):
        s_ini = s.get("start") or s.get("hora_inicio") or "06:00"
        s_fin = s.get("end") or s.get("hora_fin") or "14:00"
        s_name = s.get("name") or s.get("nombre") or f"Turno {idx + 1}"
        s_color = s.get("color") or "#10b981"
        try:
            from app.routers.produccion_router import get_shift_start_end_iso
            s_iso, e_iso = get_shift_start_end_iso(fecha_hoy, s_ini[:5], s_fin[:5])
            if s_iso <= now_str <= e_iso:
                dt_start = datetime.strptime(s_iso, "%Y-%m-%d %H:%M:%S")
                dt_end = datetime.strptime(e_iso, "%Y-%m-%d %H:%M:%S")
                dur_min = max(1, int((dt_end - dt_start).total_seconds() / 60))
                elapsed_min = max(0, int((now_dt.replace(tzinfo=None) - dt_start).total_seconds() / 60))
                remaining_min = max(0, dur_min - elapsed_min)
                pct = round(min(100.0, max(0.0, (elapsed_min / dur_min) * 100)), 1)
                
                resolved = {
                    "nombre": s_name,
                    "hora_inicio": s_ini[:5],
                    "hora_fin": s_fin[:5],
                    "nombre_completo": f"{s_name} ({s_ini[:5]} - {s_fin[:5]}) - {now_dt.strftime('%d/%m/%Y')}",
                    "fecha": fecha_hoy,
                    "fecha_formateada": now_dt.strftime("%d/%m/%Y"),
                    "duracion_total_minutos": dur_min,
                    "minutos_transcurridos": elapsed_min,
                    "minutos_restantes": remaining_min,
                    "progreso_porcentaje": pct,
                    "color": s_color,
                    "turno_index": idx + 1,
                    "is_active": True
                }
                data["turno_actual"] = resolved
                return resolved
        except Exception as e:
            logger.debug(f"Error comprobando turno {s_name}: {e}")

    return t_act

import urllib.request
import json
import asyncio
import logging
import time
from datetime import datetime
from app.database import get_db_connection
from app.utils import get_local_now_str, get_local_now

JETSON_SERVER_1_URLS = [
    "http://192.168.0.137:5001",
    "http://100.127.85.111:5001"
]
SYNC_INTERVAL_SECONDS = 30  # Sincronización continua cada 30 segundos

logger = logging.getLogger("turnos_sync")

def sync_turnos_from_server_1():
    """Consulta la API de turnos de Jetson Server 1 (http://192.168.0.137:5001) y actualiza la cache en SQLite cada 30 min."""
    jornada_data = None
    successful_url = None
    for base_url in JETSON_SERVER_1_URLS:
        try:
            url_jornada = f"{base_url}/api/turnos/jornada"
            req = urllib.request.urlopen(url_jornada, timeout=3)
            jornada_data = json.loads(req.read().decode('utf-8'))
            if jornada_data:
                successful_url = base_url
                break
        except Exception:
            pass

    if not jornada_data:
        now_err = get_local_now_str()
        print(f"[{now_err}] ⚠️ No se pudo conectar a la aplicación de turnos en {JETSON_SERVER_1_URLS}. Usando datos en cache local.")
        return False

    now_local = get_local_now_str()
    jornada_data["synced_from_url"] = successful_url
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
    print(f"[{now_local}] ✅ Turnos sincronizados exitosamente desde {successful_url} (Frecuencia: cada 30 min)")
    return True

_turnos_mem_cache = {
    "data": None,
    "last_read_ts": 0.0
}

def get_cached_turnos():
    """Obtiene los datos de turnos guardados en la base de datos local SQLite con cache en memoria (TTL 5s)."""
    now_ts = time.time()
    if _turnos_mem_cache["data"] and (now_ts - _turnos_mem_cache["last_read_ts"] < 5.0):
        return _turnos_mem_cache["data"]

    try:
        conn = get_db_connection()
        row = conn.execute("SELECT data_json, updated_at FROM shift_cache WHERE key_name = 'jornada_actual'").fetchone()
        conn.close()

        if row and row["data_json"]:
            data = json.loads(row["data_json"])
            data["cache_updated_at"] = row["updated_at"] or get_local_now_str()
            # Validar y resolver dinámicamente si el turno actual sigue vigente o avanzó
            resolve_current_shift(data)
            _turnos_mem_cache["data"] = data
            _turnos_mem_cache["last_read_ts"] = now_ts
            return data
    except Exception as e:
        logger.error(f"Error leyendo shift_cache: {e}")

    # Fallback predeterminado si aun no hay cache cargado
    return {
        "jornada": get_local_now_str("%Y-%m-%d"),
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

DECODER_API_URLS = [
    "http://100.105.75.39:8080/api/data",
    "http://192.168.0.139:8080/api/data",
    "http://192.168.0.137:8080/api/data"
]

def sync_cargas_from_decoder_api():
    """Consulta la API HTTP del Decodificador HELMS (100.105.75.39:8080) e ingiere cargas reales continuamente."""
    from app.mqtt_subscriber import parse_timestamp_to_iso
    from app.routers.produccion_router import sync_all_historical_shifts

    loads = []
    for url in DECODER_API_URLS:
        try:
            req = urllib.request.urlopen(url, timeout=3)
            data = json.loads(req.read().decode('utf-8'))
            loads = data.get("load_history", [])
            if loads:
                break
        except Exception:
            pass

    if not loads:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        inserted_count = 0
        for l in loads:
            load_id = l.get("load_id")
            ts_local = l.get("time") or l.get("created_at") or get_local_now_str("%d/%m/%Y %H:%M:%S")
            ts_iso = parse_timestamp_to_iso(ts_local)
            cliente = l.get("cliente", 0)
            categoria = l.get("categoria", 0)
            peso_kg = float(l.get("peso_kg", 0.0))
            t_seg = int(l.get("tiempo_entre_cargas_seg", 0))
            raw_hex = l.get("raw_hex", "")

            cursor.execute("""
                INSERT INTO tunel_cargas (load_id, site, device, timestamp, timestamp_iso, cliente, categoria, peso_kg, tiempo_entre_cargas_seg, raw_hex)
                VALUES (?, 'Elis Lavanderia Industrial', 'Lenovo ThinkCentre PLC FX3U (HELMS Protocol)', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(load_id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    timestamp_iso = excluded.timestamp_iso,
                    cliente = excluded.cliente,
                    categoria = excluded.categoria,
                    peso_kg = excluded.peso_kg,
                    tiempo_entre_cargas_seg = excluded.tiempo_entre_cargas_seg,
                    raw_hex = excluded.raw_hex
            """, (load_id, ts_local, ts_iso, cliente, categoria, peso_kg, t_seg, raw_hex))
            
            if cursor.rowcount > 0:
                inserted_count += 1

        conn.commit()
        conn.close()

        if inserted_count > 0:
            logger.info(f"✅ Ingeridas {inserted_count} cargas reales desde API Decodificador HELMS")
    except Exception as e:
        logger.error(f"Error ingiriendo cargas desde API Decodificador HELMS: {e}")


async def turnos_sync_loop():
    """Bucle asíncrono para ejecutar la sincronización de turnos y telemetría real del decodificador."""
    last_shift_sync = 0
    while True:
        try:
            # 1. Ingesta continua de cargas reales desde Decodificador HELMS (cada 10 seg)
            await asyncio.to_thread(sync_cargas_from_decoder_api)

            # 2. Sincronizar cache de jornada desde Server 1 cada 30 min
            now_ts = time.time()
            if now_ts - last_shift_sync >= SYNC_INTERVAL_SECONDS:
                await asyncio.to_thread(sync_turnos_from_server_1)
                last_shift_sync = now_ts
        except Exception as e:
            logger.error(f"Error en bucle de sincronización: {e}")
        await asyncio.sleep(10)

def start_turnos_background_sync(app):
    """Inicializa la sincronización asíncrona de turnos al arrancar FastAPI."""
    @app.on_event("startup")
    async def schedule_sync():
        asyncio.create_task(turnos_sync_loop())

