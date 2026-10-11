import urllib.request
import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional
from app.database import get_db_connection
from app.utils import get_local_now_str, get_local_now

logger = logging.getLogger("turnos_sync")

JETSON_SERVER_1_URLS = [
    "http://192.168.0.137:5001",
    "http://100.127.85.111:5001"
]
SYNC_INTERVAL_SECONDS = 30  # Sincronización continua cada 30 segundos según requerimiento


def resolve_current_shift(data: dict) -> dict:
    """
    Verifica el turno actual según los datos obtenidos del módulo de turnos (http://192.168.0.137:5001).
    Criterio único de validez de turnos:
    Si el módulo de turnos indicó explícitamente FUERA DE TURNO o is_active: false,
    se respeta estrictamente sin forzar turnos artificiales.
    """
    t_act = data.get("turno_actual") or {}

    # Si el módulo de turnos declaró explícitamente fuera de turno, respetarlo sin alteraciones
    if t_act.get("is_active") is False:
        return t_act
    nombre_upper = str(t_act.get("nombre") or "").upper()
    if any(x in nombre_upper for x in ["FUERA DE TURNO", "SIN TURNO", "INACTIVO"]):
        return t_act

    shifts = data.get("shifts") or []
    if not shifts:
        return t_act

    now_dt = get_local_now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    fecha_hoy = now_dt.strftime("%Y-%m-%d")

    # Si turno_actual existe y sigue en su ventana de tiempo, conservarlo
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

    # Si ya expiró el turno actual, verificar si entramos en alguno de los turnos programados en 'shifts'
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


def sync_turnos_from_server_1() -> bool:
    """
    Consulta la API de turnos de Jetson Server 1 (http://192.168.0.137:5001) cada 30 segundos.
    Actualiza la persistencia y cache en shift_cache:
    - jornada_actual (/api/turnos/jornada)
    - turno_actual (/api/turnos/actual)
    - schedule_semanal (/api/shifts/schedule o /api/turnos/semana)
    - shifts_{fecha} para cada fecha programada
    - config_turnos (/api/turnos/config)
    """
    jornada_data = None
    turno_actual_data = None
    schedule_data = None
    config_data = None
    successful_url = None

    for base_url in JETSON_SERVER_1_URLS:
        try:
            # 1. Turno actual disponible en tiempo real
            try:
                req_act = urllib.request.urlopen(f"{base_url}/api/turnos/actual", timeout=3)
                turno_actual_data = json.loads(req_act.read().decode('utf-8'))
            except Exception as ex_act:
                logger.debug(f"Error consultando /api/turnos/actual en {base_url}: {ex_act}")

            # 2. Jornada actual y lista de turnos del día
            try:
                req_jor = urllib.request.urlopen(f"{base_url}/api/turnos/jornada", timeout=3)
                jornada_data = json.loads(req_jor.read().decode('utf-8'))
            except Exception as ex_jor:
                logger.debug(f"Error consultando /api/turnos/jornada en {base_url}: {ex_jor}")

            # 3. Calendario semanal de programación por fecha
            try:
                req_sched = urllib.request.urlopen(f"{base_url}/api/shifts/schedule", timeout=3)
                schedule_data = json.loads(req_sched.read().decode('utf-8'))
            except Exception:
                try:
                    req_sem = urllib.request.urlopen(f"{base_url}/api/turnos/semana", timeout=3)
                    schedule_data = json.loads(req_sem.read().decode('utf-8'))
                except Exception as ex_sem:
                    logger.debug(f"Error consultando calendario de turnos en {base_url}: {ex_sem}")

            # 4. Configuración general de turnos
            try:
                req_cfg = urllib.request.urlopen(f"{base_url}/api/turnos/config", timeout=3)
                config_data = json.loads(req_cfg.read().decode('utf-8'))
            except Exception:
                config_data = None

            if jornada_data or turno_actual_data:
                successful_url = base_url
                break
        except Exception as e:
            logger.debug(f"Error general conectando a {base_url}: {e}")

    if not jornada_data and not turno_actual_data:
        now_err = get_local_now_str()
        print(f"[{now_err}] ⚠️ No se pudo conectar a la aplicación de turnos en {JETSON_SERVER_1_URLS}. Usando datos en cache local.")
        return False

    now_local = get_local_now_str()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Guardar turno_actual en shift_cache
    if turno_actual_data:
        turno_actual_data["synced_from_url"] = successful_url
        cursor.execute("""
            INSERT INTO shift_cache (key_name, data_json, updated_at)
            VALUES ('turno_actual', ?, ?)
            ON CONFLICT(key_name) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (json.dumps(turno_actual_data), now_local))

    # Guardar jornada_actual en shift_cache
    if jornada_data:
        jornada_data["synced_from_url"] = successful_url
        if turno_actual_data:
            jornada_data["turno_actual"] = turno_actual_data
        cursor.execute("""
            INSERT INTO shift_cache (key_name, data_json, updated_at)
            VALUES ('jornada_actual', ?, ?)
            ON CONFLICT(key_name) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (json.dumps(jornada_data), now_local))

    # Guardar schedule semanal y programación específica por cada fecha
    if schedule_data:
        cursor.execute("""
            INSERT INTO shift_cache (key_name, data_json, updated_at)
            VALUES ('schedule_semanal', ?, ?)
            ON CONFLICT(key_name) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (json.dumps(schedule_data), now_local))

        days_list = schedule_data.get("schedule") or schedule_data.get("days") or []
        for d in days_list:
            d_date = d.get("date")
            d_shifts = d.get("shifts") or []
            if d_date:
                cursor.execute("""
                    INSERT INTO shift_cache (key_name, data_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key_name) DO UPDATE SET
                        data_json = excluded.data_json,
                        updated_at = excluded.updated_at
                """, (f"shifts_{d_date}", json.dumps(d_shifts), now_local))

    # Guardar configuración general de turnos
    if config_data:
        cursor.execute("""
            INSERT INTO shift_cache (key_name, data_json, updated_at)
            VALUES ('config_turnos', ?, ?)
            ON CONFLICT(key_name) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (json.dumps(config_data), now_local))

    conn.commit()
    conn.close()

    # Invalidar caché en memoria para que la siguiente lectura refleje los datos frescos
    _turnos_mem_cache["data"] = None
    _turnos_mem_cache["last_read_ts"] = 0.0

    return True


_turnos_mem_cache = {
    "data": None,
    "last_read_ts": 0.0
}


def get_cached_turnos() -> dict:
    """Obtiene los datos de turnos guardados en la base de datos local SQLite con cache en memoria (TTL 5s)."""
    now_ts = time.time()
    if _turnos_mem_cache["data"] and (now_ts - _turnos_mem_cache["last_read_ts"] < 5.0):
        return _turnos_mem_cache["data"]

    try:
        conn = get_db_connection()
        row_jor = conn.execute("SELECT data_json, updated_at FROM shift_cache WHERE key_name = 'jornada_actual'").fetchone()
        row_act = conn.execute("SELECT data_json, updated_at FROM shift_cache WHERE key_name = 'turno_actual'").fetchone()
        conn.close()

        if row_jor and row_jor["data_json"]:
            data = json.loads(row_jor["data_json"])
            data["cache_updated_at"] = row_jor["updated_at"] or get_local_now_str()

            # Si tenemos turno_actual específico sincronizado directamente de /api/turnos/actual
            if row_act and row_act["data_json"]:
                try:
                    data["turno_actual"] = json.loads(row_act["data_json"])
                except Exception:
                    pass

            # Validar y resolver si el turno actual sigue vigente o avanzó
            resolve_current_shift(data)
            _turnos_mem_cache["data"] = data
            _turnos_mem_cache["last_read_ts"] = now_ts
            return data
    except Exception as e:
        logger.error(f"Error leyendo shift_cache: {e}")

    # Fallback predeterminado estándar de la planta si aun no hay cache cargado
    return {
        "jornada": get_local_now_str("%Y-%m-%d"),
        "jornada_activa": True,
        "turno_actual": {
            "nombre": "Turno 1",
            "hora_inicio": "06:00",
            "hora_fin": "14:00",
            "nombre_completo": "Turno 1 (06:00 - 14:00)"
        },
        "shifts": [
            {"name": "Turno 1", "start": "06:00", "end": "14:00", "color": "#10b981"},
            {"name": "Turno 2", "start": "14:00", "end": "21:00", "color": "#3b82f6"},
            {"name": "Turno 3", "start": "21:00", "end": "02:00", "color": "#831843"}
        ],
        "cache_updated_at": "Local default"
    }


def get_shifts_for_date(fecha: str) -> list[dict]:
    """
    Retorna los turnos programados específicamente para una fecha según el módulo de turnos
    (http://192.168.0.137:5001).
    Criterio único de ocurrencia de turnos:
    - Si el módulo de turnos programó turnos para esa fecha (ej. Sábado 10 oct: 1 turno), retorna esa lista exacta.
    - Si el módulo programó 0 turnos (ej. Domingo: 0 turnos), retorna lista vacía [].
    - Si la fecha no está explícitamente en el calendario semanal sincronizado:
      se consulta la configuración general de turnos por día de la semana (0=Lunes... 5=Sábado, 6=Domingo).
    """
    conn = get_db_connection()

    # 1. Buscar en caché específica por fecha (sincronizada desde /api/shifts/schedule o /api/turnos/semana)
    row = conn.execute("SELECT data_json FROM shift_cache WHERE key_name = ?", (f"shifts_{fecha}",)).fetchone()
    if row and row["data_json"]:
        try:
            cached_shifts = json.loads(row["data_json"])
            conn.close()
            result = []
            for idx, s in enumerate(cached_shifts):
                nombre = s.get("name") or s.get("nombre") or f"Turno {idx + 1}"
                h_start = s.get("start") or s.get("hora_inicio") or "06:00"
                h_end = s.get("end") or s.get("hora_fin") or "14:00"
                result.append({
                    "nombre": nombre,
                    "hora_inicio": str(h_start)[:5],
                    "hora_fin": str(h_end)[:5]
                })
            return result
        except Exception:
            pass

    # 2. Si no estaba en shifts_{fecha}, buscar en schedule_semanal
    row_sched = conn.execute("SELECT data_json FROM shift_cache WHERE key_name = 'schedule_semanal'").fetchone()
    if row_sched and row_sched["data_json"]:
        try:
            sched_data = json.loads(row_sched["data_json"])
            days_list = sched_data.get("schedule") or sched_data.get("days") or []
            for d in days_list:
                if d.get("date") == fecha:
                    d_shifts = d.get("shifts") or []
                    conn.close()
                    result = []
                    for idx, s in enumerate(d_shifts):
                        nombre = s.get("name") or s.get("nombre") or f"Turno {idx + 1}"
                        h_start = s.get("start") or s.get("hora_inicio") or "06:00"
                        h_end = s.get("end") or s.get("hora_fin") or "14:00"
                        result.append({
                            "nombre": nombre,
                            "hora_inicio": str(h_start)[:5],
                            "hora_fin": str(h_end)[:5]
                        })
                    return result
        except Exception:
            pass

    # 3. Si la fecha consultada es la jornada actual de hoy, verificar jornada_actual
    now_dt = get_local_now()
    fecha_hoy = now_dt.strftime("%Y-%m-%d")
    if fecha == fecha_hoy:
        row_jor = conn.execute("SELECT data_json FROM shift_cache WHERE key_name = 'jornada_actual'").fetchone()
        if row_jor and row_jor["data_json"]:
            try:
                j_data = json.loads(row_jor["data_json"])
                j_shifts = j_data.get("shifts", [])
                conn.close()
                result = []
                for idx, s in enumerate(j_shifts):
                    nombre = s.get("name") or s.get("nombre") or f"Turno {idx + 1}"
                    h_start = s.get("start") or s.get("hora_inicio") or "06:00"
                    h_end = s.get("end") or s.get("hora_fin") or "14:00"
                    result.append({
                        "nombre": nombre,
                        "hora_inicio": str(h_start)[:5],
                        "hora_fin": str(h_end)[:5]
                    })
                return result
            except Exception:
                pass

    # 4. Si la fecha es de otra semana o no está en el schedule semanal:
    # Determinar el día de la semana de la fecha consultada (0=Lunes... 5=Sábado, 6=Domingo)
    try:
        dt = datetime.strptime(fecha, "%Y-%m-%d")
        day_num = dt.weekday()
    except Exception:
        day_num = 0

    # Revisar config_turnos
    row_cfg = conn.execute("SELECT data_json FROM shift_cache WHERE key_name = 'config_turnos'").fetchone()
    conn.close()

    if row_cfg and row_cfg["data_json"]:
        try:
            cfg = json.loads(row_cfg["data_json"])
            turnos_cfg = cfg.get("turnos") or []
            valid_shifts = []
            for t in turnos_cfg:
                if not t.get("activo", True):
                    continue
                dias_str = str(t.get("dias_semana") or "")
                dias_list = [int(x.strip()) for x in dias_str.split(",") if x.strip().isdigit()]
                if day_num in dias_list:
                    valid_shifts.append({
                        "nombre": t.get("nombre") or f"Turno {len(valid_shifts)+1}",
                        "hora_inicio": str(t.get("hora_inicio", "06:00"))[:5],
                        "hora_fin": str(t.get("hora_fin", "14:00"))[:5]
                    })
            if valid_shifts:
                valid_shifts.sort(key=lambda x: x["hora_inicio"])
                return valid_shifts
            elif day_num == 6:  # Domingo sin turnos en config
                return []
        except Exception:
            pass

    # Fallback predeterminado según patrón estándar de la planta si la BD estuviese vacía:
    # Domingo: 0 turnos
    if day_num == 6:
        return []
    # Sábado: 1 turno
    if day_num == 5:
        return [{"nombre": "Turno 1", "hora_inicio": "06:00", "hora_fin": "14:15"}]
    # Lunes a Viernes: 3 turnos
    return [
        {"nombre": "Turno 1", "hora_inicio": "06:00", "hora_fin": "14:00"},
        {"nombre": "Turno 2", "hora_inicio": "14:00", "hora_fin": "21:00"},
        {"nombre": "Turno 3", "hora_inicio": "21:00", "hora_fin": "02:00"}
    ]


DECODER_API_URLS = [
    "http://100.105.75.39:8080/api/data",
    "http://192.168.0.139:8080/api/data",
    "http://192.168.0.137:8080/api/data"
]


def sync_cargas_from_decoder_api():
    """Consulta la API HTTP del Decodificador HELMS (100.105.75.39:8080) e ingiere cargas reales continuamente."""
    from app.mqtt_subscriber import parse_timestamp_to_iso

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
    """Bucle asíncrono para ejecutar la sincronización de turnos cada 30 segundos y cargas del decodificador."""
    last_shift_sync = 0

    # Sincronización inmediata al arrancar
    try:
        await asyncio.to_thread(sync_turnos_from_server_1)
        last_shift_sync = time.time()
    except Exception as e:
        logger.error(f"Error en sincronización inicial de turnos: {e}")

    while True:
        try:
            # 1. Ingesta continua de cargas reales desde Decodificador HELMS (cada 10 seg)
            await asyncio.to_thread(sync_cargas_from_decoder_api)

            # 2. Sincronizar cache de turnos desde Server 1 cada 30 segundos
            now_ts = time.time()
            if now_ts - last_shift_sync >= SYNC_INTERVAL_SECONDS:
                await asyncio.to_thread(sync_turnos_from_server_1)
                last_shift_sync = now_ts
        except Exception as e:
            logger.error(f"Error en bucle de sincronización de turnos: {e}")

        await asyncio.sleep(5)


def start_turnos_background_sync(app):
    """Inicializa la sincronización asíncrona de turnos al arrancar FastAPI."""
    @app.on_event("startup")
    async def schedule_sync():
        asyncio.create_task(turnos_sync_loop())
