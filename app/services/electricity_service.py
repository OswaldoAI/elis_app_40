import os
import time
import json
import math
import sqlite3
import threading
import logging
import urllib.request
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt

logger = logging.getLogger("electricity_service")

# Constantes de configuración eléctrica
VOLTAGE_LL = 400.0          # Tensión de línea trifásica (V)
POWER_FACTOR = 0.90         # Factor de potencia típico industrial (cos phi)
SQRT_3 = math.sqrt(3.0)     # 1.7320508

# Configuración InfluxDB
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://192.168.0.116:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "2ivBvpVNfzgfivqZzg_5K2cLIAMzXDeT4pfXOMMOj63-bbVLRyICcPfqBTUotGpyZeqJXv31Mj5c87Ec2aNUlA==")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "elis_laundry")
INFLUXDB_BUCKETS = ["electricidad_telemetria", "gas_telemetry"]

def send_to_influx(var_code: str, dev_eui: str, metrics: dict, delta_kwh: float, ts_epoch: int):
    """Escribe la lectura en InfluxDB v2 usando Line Protocol en ambos buckets."""
    try:
        line = (
            f"electricidad_telemetria,dev_eui={dev_eui},variable={var_code} "
            f"corriente_a={metrics['corriente_a']},"
            f"corriente_max_a={metrics['corriente_max_a']},"
            f"corriente_acumulada_ah={metrics['corriente_acumulada_ah']},"
            f"potencia_activa_kw={metrics['potencia_activa_kw']},"
            f"potencia_aparente_kva={metrics['potencia_aparente_kva']},"
            f"potencia_acumulada_kwh={metrics['potencia_acumulada_kwh']},"
            f"delta_potencia_kwh={delta_kwh} "
            f"{ts_epoch}"
        )
        data = line.encode("utf-8")
        headers = {
            "Authorization": f"Token {INFLUXDB_TOKEN}",
            "Content-Type": "text/plain; charset=utf-8"
        }
        for b in INFLUXDB_BUCKETS:
            url = f"{INFLUXDB_URL}/api/v2/write?org={INFLUXDB_ORG}&bucket={b}&precision=s"
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                pass
    except Exception as e:
        logger.warning(f"Error escribiendo en InfluxDB: {e}")

ELECTRIC_SENSORS_MAP = {
    "24e124751058d4ee": {
        "variable": "I_general",
        "alias_keys": ["energia_electrica", "I_gneral", "i_general", "I_general"],
        "dev_eui": "24E124751058D4EE",
        "model": "CT310",
        "is_ct310": True,
        "conductors_parallel": 3,
        "title": "Energía Eléctrica General",
        "device_name": "Milesight CT310 General (Acometida 3x)"
    },
    "24e124751067ecff": {
        "variable": "I_motor_tunel",
        "alias_keys": ["elec_tunel", "i_motor_tunel", "I_motor_tunel"],
        "dev_eui": "24E124751067ECFF",
        "model": "CT101",
        "is_ct310": False,
        "conductors_parallel": 1,
        "title": "Motor Principal Túnel",
        "device_name": "CT101 Motor Principal Túnel"
    },
    "24e124751067b747": {
        "variable": "I_bomba_calandra1",
        "alias_keys": ["elec_calandra_1", "i_bomba_calandra1", "I_bomba_calandra1"],
        "dev_eui": "24E124751067B747",
        "model": "CT101",
        "is_ct310": False,
        "conductors_parallel": 1,
        "title": "Electricidad Calandra 1",
        "device_name": "CT101 Bomba Calandra 1"
    },
    "24e12475106726fd": {
        "variable": "Bomba_calandra2",
        "alias_keys": ["elec_calandra_2", "corriente_bomba_calandra3", "Bomba_calandra2"],
        "dev_eui": "24E12475106726FD",
        "model": "CT101",
        "is_ct310": False,
        "conductors_parallel": 1,
        "title": "Electricidad Calandra 2",
        "device_name": "CT101 Bomba Calandra 2"
    },
    "24e124751067c296": {
        "variable": "I_bomba_calandra3",
        "alias_keys": ["elec_calandra_3", "i_bomba_calandra3", "I_bomba_calandra3"],
        "dev_eui": "24E124751067C296",
        "model": "CT101",
        "is_ct310": False,
        "conductors_parallel": 1,
        "title": "Electricidad Calandra 3",
        "device_name": "CT101 Bomba Calandra 3"
    },
    "24e1247510646dcf": {
        "variable": "I_prensa_tunel",
        "alias_keys": ["elec_prensa_tunel", "i_prensa_tunel", "I_prensa_tunel"],
        "dev_eui": "24E1247510646DCF",
        "model": "CT101",
        "is_ct310": False,
        "conductors_parallel": 1,
        "title": "Electricidad Prensa Túnel",
        "device_name": "CT101 Prensa Túnel de Lavado"
    }
}

VARIABLE_TO_SENSOR = {}
for eui_lower, s_info in ELECTRIC_SENSORS_MAP.items():
    for k in [s_info["variable"]] + s_info["alias_keys"]:
        VARIABLE_TO_SENSOR[k] = s_info

DB_PATH = os.getenv("DB_PATH", "/app/data/elis_40.db")

def get_sqlite_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_electricity_table():
    try:
        conn = get_sqlite_conn()
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS electricidad_telemetria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variable TEXT NOT NULL,
                dev_eui TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                timestamp_iso TEXT NOT NULL,
                corriente_a REAL NOT NULL,
                corriente_max_a REAL NOT NULL,
                corriente_acumulada_ah REAL DEFAULT 0.0,
                potencia_activa_kw REAL NOT NULL,
                potencia_aparente_kva REAL NOT NULL,
                potencia_acumulada_kwh REAL NOT NULL,
                delta_potencia_kwh REAL NOT NULL,
                dispositivo TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_elec_var_time ON electricidad_telemetria(variable, timestamp_iso);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_elec_time ON electricidad_telemetria(timestamp_iso);")
        conn.close()
        logger.info("Tabla electricidad_telemetria inicializada con éxito.")
    except Exception as e:
        logger.error(f"Error al inicializar tabla electricidad_telemetria: {e}")

_electricity_live_state = {}

def calculate_electric_metrics(sensor_info: dict, payload: dict) -> dict:
    """Calcula las métricas eléctricas según sea CT310 trifásico o CT101 equilibrado con protección ante paquetes de eventos."""
    is_ct310 = sensor_info.get("is_ct310", False)
    conductors = sensor_info.get("conductors_parallel", 1)
    var_code = sensor_info.get("variable", "")

    if is_ct310:
        # CT310 entrega canales 1, 2 y 3
        chn1 = float(payload.get("current_chn1", 0.0) or 0.0)
        chn2 = float(payload.get("current_chn2", 0.0) or 0.0)
        chn3 = float(payload.get("current_chn3", 0.0) or 0.0)

        # Multiplicar por los conductores en paralelo por fase (3)
        i_l1 = chn1 * conductors
        i_l2 = chn2 * conductors
        i_l3 = chn3 * conductors

        i_avg = round((i_l1 + i_l2 + i_l3) / 3.0, 2)
        i_max = round(max(i_l1, i_l2, i_l3), 2)

        tot1 = float(payload.get("current_chn1_total", 0.0) or 0.0)
        tot2 = float(payload.get("current_chn2_total", 0.0) or 0.0)
        tot3 = float(payload.get("current_chn3_total", 0.0) or 0.0)
        ah_total_avg = ((tot1 + tot2 + tot3) / 3.0) * conductors
    else:
        # CT101 monofásico: se asumen 3 fases equilibradas con la misma corriente
        i_raw = float(payload.get("current", 0.0) or 0.0)
        i_avg = round(i_raw, 2)
        i_max = round(i_raw, 2)
        ah_total_avg = float(payload.get("total_current", 0.0) or 0.0)

    # Protección: si es un paquete de evento/alarma que no trae el totalizador de corriente (ah_total_avg == 0),
    # rescatar el último valor acumulado válido de la base de datos para no resetear a 0.
    if ah_total_avg <= 0.0:
        try:
            conn = get_sqlite_conn()
            last_ah_row = conn.execute("""
                SELECT corriente_acumulada_ah FROM electricidad_telemetria
                WHERE variable = ? AND corriente_acumulada_ah > 0.0
                ORDER BY id DESC LIMIT 1
            """, (var_code,)).fetchone()
            conn.close()
            if last_ah_row and last_ah_row[0]:
                ah_total_avg = float(last_ah_row[0])
        except Exception:
            pass

    # Potencia aparente: S (kVA) = (sqrt(3) * V_L * I_avg) / 1000
    potencia_aparente_kva = round((SQRT_3 * VOLTAGE_LL * i_avg) / 1000.0, 2)
    # Potencia activa: P (kW) = S * cos(phi)
    potencia_activa_kw = round(potencia_aparente_kva * POWER_FACTOR, 2)

    # Potencia acumulada en kWh: E (kWh) = (sqrt(3) * V_L * Ah_total * cos(phi)) / 1000
    potencia_acumulada_kwh = round((SQRT_3 * VOLTAGE_LL * ah_total_avg * POWER_FACTOR) / 1000.0, 2)

    return {
        "corriente_a": i_avg,
        "corriente_max_a": i_max,
        "corriente_acumulada_ah": round(ah_total_avg, 2),
        "potencia_activa_kw": potencia_activa_kw,
        "potencia_aparente_kva": potencia_aparente_kva,
        "potencia_acumulada_kwh": potencia_acumulada_kwh
    }

def record_electric_reading(topic: str, payload: dict):
    """Guarda una lectura eléctrica en SQLite, InfluxDB y actualiza el caché de métricas en vivo con control de anomalías."""
    parts = topic.strip().split('/')
    eui_lower = parts[-1].lower() if parts else ""
    if eui_lower not in ELECTRIC_SENSORS_MAP:
        return

    sensor_info = ELECTRIC_SENSORS_MAP[eui_lower]
    var_code = sensor_info["variable"]
    is_general = sensor_info.get("is_ct310", False)
    metrics = calculate_electric_metrics(sensor_info, payload)

    dt_now = datetime.now()
    ts_str = dt_now.strftime("%d/%m/%Y %H:%M:%S")
    ts_iso = dt_now.strftime("%Y-%m-%d %H:%M:%S")
    ts_epoch = int(dt_now.timestamp())

    conn = get_sqlite_conn()
    last_row = conn.execute("""
        SELECT potencia_acumulada_kwh, timestamp_iso FROM electricidad_telemetria
        WHERE variable = ? AND potencia_acumulada_kwh > 0.0
        ORDER BY id DESC LIMIT 1
    """, (var_code,)).fetchone()

    delta_kwh = 0.0
    if last_row and last_row[0] is not None:
        last_kwh = float(last_row[0])
        last_ts_iso = last_row[1] if len(last_row) > 1 and last_row[1] else None

        # Calcular tiempo transcurrido respecto a la última lectura (base 600s)
        elapsed_seconds = 600.0
        if last_ts_iso:
            try:
                dt_last = datetime.strptime(str(last_ts_iso), "%Y-%m-%d %H:%M:%S")
                diff_sec = (dt_now - dt_last).total_seconds()
                if diff_sec > 0:
                    elapsed_seconds = diff_sec
            except Exception:
                pass

        elapsed_hours = elapsed_seconds / 3600.0

        calc_delta = metrics["potencia_acumulada_kwh"] - last_kwh
        # Filtro de protección anti-saltos dinámico según ventana de tiempo:
        # En 10 min: General máx 150 kWh, máquina individual máx 30 kWh.
        # Si hubo corte o desconexión prolongada, la energía admisible escala con la duración del período
        # (Acometida General: 550 kW capacidad máx; Máquinas: 80 kW capacidad máx).
        if is_general:
            max_delta_allowed = max(150.0, round(550.0 * elapsed_hours, 2))
        else:
            max_delta_allowed = max(30.0, round(80.0 * elapsed_hours, 2))

        if 0.0 <= calc_delta <= max_delta_allowed:
            delta_kwh = round(calc_delta, 3)
        else:
            delta_kwh = 0.0

    dispositivo_label = f"{sensor_info['device_name']} (EUI: {sensor_info['dev_eui']})"

    with conn:
        conn.execute("""
            INSERT INTO electricidad_telemetria (
                variable, dev_eui, timestamp, timestamp_iso,
                corriente_a, corriente_max_a, corriente_acumulada_ah,
                potencia_activa_kw, potencia_aparente_kva,
                potencia_acumulada_kwh, delta_potencia_kwh, dispositivo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            var_code, sensor_info["dev_eui"], ts_str, ts_iso,
            metrics["corriente_a"], metrics["corriente_max_a"],
            metrics["corriente_acumulada_ah"],
            metrics["potencia_activa_kw"], metrics["potencia_aparente_kva"],
            metrics["potencia_acumulada_kwh"], delta_kwh, dispositivo_label
        ))
    conn.close()

    # Enviar a InfluxDB en tiempo real
    send_to_influx(var_code, sensor_info["dev_eui"], metrics, delta_kwh, ts_epoch)

    # Actualizar estado en vivo
    today_start_iso = dt_now.strftime("%Y-%m-%d 00:00:00")
    conn = get_sqlite_conn()
    day_stats = conn.execute("""
        SELECT 
            COALESCE(MAX(corriente_max_a), 0.0) as max_corriente,
            COALESCE(MAX(potencia_acumulada_kwh) - MIN(potencia_acumulada_kwh), 0.0) as kwh_hoy
        FROM electricidad_telemetria
        WHERE variable = ? AND timestamp_iso >= ? AND potencia_acumulada_kwh > 0.0
    """, (var_code, today_start_iso)).fetchone()
    conn.close()

    max_c = round(day_stats[0], 1) if day_stats else metrics["corriente_max_a"]
    kwh_h = round(day_stats[1], 1) if day_stats else 0.0

    _electricity_live_state[var_code] = {
        "potencia_activa_kw": metrics["potencia_activa_kw"],
        "potencia_aparente_kva": metrics["potencia_aparente_kva"],
        "corriente_actual_a": metrics["corriente_a"],
        "corriente_max_a": max(metrics["corriente_max_a"], max_c),
        "corriente_acumulada_ah": metrics["corriente_acumulada_ah"],
        "consumo_hoy_kwh": kwh_h,
        "last_seen": ts_iso
    }

def get_live_electricity_summary() -> dict:
    """Devuelve las métricas de hoy para todas las tarjetas de electricidad calculadas por delta de totalizador."""
    dt_now = datetime.now()
    today_start_iso = dt_now.strftime("%Y-%m-%d 00:00:00")

    conn = get_sqlite_conn()
    summary = {}

    for eui, s_info in ELECTRIC_SENSORS_MAP.items():
        var_code = s_info["variable"]
        last_row = conn.execute("""
            SELECT corriente_a, corriente_max_a, potencia_activa_kw, potencia_aparente_kva, timestamp_iso, corriente_acumulada_ah
            FROM electricidad_telemetria
            WHERE variable = ? ORDER BY id DESC LIMIT 1
        """, (var_code,)).fetchone()

        # Calcular consumo de hoy como MAX - MIN del acumulador del hardware (robusto frente a anomalías)
        day_stats = conn.execute("""
            SELECT 
                COALESCE(MAX(corriente_max_a), 0.0) as max_corriente,
                COALESCE(MAX(potencia_acumulada_kwh) - MIN(potencia_acumulada_kwh), 0.0) as kwh_hoy,
                COALESCE(SUM(delta_potencia_kwh), 0.0) as sum_deltas
            FROM electricidad_telemetria
            WHERE variable = ? AND timestamp_iso >= ? AND potencia_acumulada_kwh > 0.0
        """, (var_code, today_start_iso)).fetchone()

        p_kw = round(last_row[2], 1) if last_row else 0.0
        s_kva = round(last_row[3], 1) if last_row else 0.0
        i_curr = round(last_row[0], 1) if last_row else 0.0
        i_max = round(day_stats[0], 1) if day_stats else 0.0
        # Usar la diferencia de acumuladores
        kwh_hoy = round(day_stats[1], 1) if (day_stats and day_stats[1] > 0) else (round(day_stats[2], 1) if day_stats else 0.0)
        ah_acum = round(last_row[5], 1) if (last_row and len(last_row) > 5 and last_row[5]) else 0.0

        item_data = {
            "titulo": s_info["title"],
            "variable_telemetria": var_code,
            "potencia_kw": p_kw,
            "potencia_activa_kw": p_kw,
            "potencia_aparente_kva": s_kva,
            "consumo_hoy_kwh": kwh_hoy,
            "corriente_max_a": i_max,
            "corriente_actual_a": i_curr,
            "corriente_acumulada_ah": ah_acum
        }

        _electricity_live_state[var_code] = {
            "potencia_activa_kw": p_kw,
            "potencia_aparente_kva": s_kva,
            "corriente_actual_a": i_curr,
            "corriente_max_a": i_max,
            "corriente_acumulada_ah": ah_acum,
            "consumo_hoy_kwh": kwh_hoy,
            "last_seen": last_row[4] if last_row else ""
        }

        summary[var_code] = item_data

    conn.close()
    return summary

def get_electricity_telemetria(variable: str, start_iso: str, end_iso: str) -> dict:
    """Consulta el rango seleccionado para la tabla de telemetría y cabecera de electricidad."""
    s_info = VARIABLE_TO_SENSOR.get(variable)
    if not s_info:
        var_code = variable
        title = variable
        dev_eui = ""
    else:
        var_code = s_info["variable"]
        title = s_info["title"]
        dev_eui = s_info["dev_eui"]

    conn = get_sqlite_conn()
    rows = conn.execute("""
        SELECT id, variable, dev_eui, timestamp, timestamp_iso,
               corriente_a, corriente_max_a, corriente_acumulada_ah,
               potencia_activa_kw, potencia_aparente_kva,
               potencia_acumulada_kwh, delta_potencia_kwh, dispositivo
        FROM electricidad_telemetria
        WHERE variable = ? AND timestamp_iso >= ? AND timestamp_iso <= ?
        ORDER BY timestamp_iso DESC
    """, (var_code, start_iso, end_iso)).fetchall()

    registros = []
    total_delta_kwh = 0.0
    sum_kw = 0.0
    sum_kva = 0.0
    max_corriente_rango = 0.0

    for idx, r in enumerate(rows):
        delta_p = round(float(r["delta_potencia_kwh"] or 0.0), 3)
        total_delta_kwh += delta_p
        p_kw = round(float(r["potencia_activa_kw"] or 0.0), 2)
        p_kva = round(float(r["potencia_aparente_kva"] or 0.0), 2)
        c_a = round(float(r["corriente_a"] or 0.0), 2)
        c_max = round(float(r["corriente_max_a"] or 0.0), 2)
        c_ah = round(float(r["corriente_acumulada_ah"] or 0.0), 2)
        p_acum = round(float(r["potencia_acumulada_kwh"] or 0.0), 2)

        sum_kw += p_kw
        sum_kva += p_kva
        if c_max > max_corriente_rango:
            max_corriente_rango = c_max
        if c_a > max_corriente_rango:
            max_corriente_rango = c_a

        registros.append({
            "id": r["id"],
            "variable": var_code,
            "timestamp": r["timestamp"],
            "timestamp_iso": r["timestamp_iso"],
            "corriente_a": c_a,
            "corriente_max_a": c_max,
            "corriente_acumulada_ah": c_ah,
            "potencia_activa_kw": p_kw,
            "potencia_aparente_kva": p_kva,
            "potencia_acumulada_kwh": p_acum,
            "delta_potencia_kwh": delta_p,
            "dispositivo": r["dispositivo"]
        })

    conn.close()

    n = len(registros)
    potencia_activa_media = round(sum_kw / n, 2) if n > 0 else 0.0
    potencia_aparente_media = round(sum_kva / n, 2) if n > 0 else 0.0

    # Consumo del rango calculado directamente a partir del totalizador del sensor (final - inicial)
    valid_p_acums = [r["potencia_acumulada_kwh"] for r in registros if r["potencia_acumulada_kwh"] > 0]
    valid_ah_acums = [r["corriente_acumulada_ah"] for r in registros if r["corriente_acumulada_ah"] > 0]

    if len(valid_p_acums) >= 2:
        consumo_rango_kwh = round(max(0.0, max(valid_p_acums) - min(valid_p_acums)), 2)
        corriente_consumida_rango_ah = round(max(0.0, max(valid_ah_acums) - min(valid_ah_acums)), 2)
    elif len(valid_p_acums) == 1:
        consumo_rango_kwh = registros[0]["delta_potencia_kwh"]
        corriente_consumida_rango_ah = round(consumo_rango_kwh / 0.623538, 2)
    else:
        consumo_rango_kwh = 0.0
        corriente_consumida_rango_ah = 0.0

    potencia_aparente_rango_kvah = round(consumo_rango_kwh / POWER_FACTOR, 2) if POWER_FACTOR > 0 else 0.0

    return {
        "variable": var_code,
        "titulo": title,
        "dev_eui": dev_eui,
        "unidad": "kWh",
        "acumulado": consumo_rango_kwh,
        "potencia_activa_rango_kwh": consumo_rango_kwh,
        "potencia_aparente_rango_kvah": potencia_aparente_rango_kvah,
        "corriente_acumulada_rango_ah": corriente_consumida_rango_ah,
        "potencia_activa_media_kw": potencia_activa_media,
        "potencia_aparente_media_kva": potencia_aparente_media,
        "corriente_max_rango_a": round(max_corriente_rango, 1),
        "total_registros": n,
        "total_pulsos": n,
        "registros": registros
    }

def get_proceso_electric_telemetry(var_code: str, fecha_inicio: str = "", hora_inicio: str = "00:00:00", fecha_fin: str = "", hora_fin: str = "23:59:59"):
    """Wrapper para compatibilidad con consumos_router."""
    dt_now = datetime.now()
    if not fecha_inicio:
        fecha_inicio = dt_now.strftime("%Y-%m-%d")
    if not fecha_fin:
        fecha_fin = dt_now.strftime("%Y-%m-%d")

    start_iso = f"{fecha_inicio} {hora_inicio}"
    end_iso = f"{fecha_fin} {hora_fin}"

    res = get_electricity_telemetria(var_code, start_iso, end_iso)
    res["filtro"] = {
        "fecha_inicio": fecha_inicio,
        "hora_inicio": hora_inicio,
        "fecha_fin": fecha_fin,
        "hora_fin": hora_fin,
        "start_iso": start_iso,
        "end_iso": end_iso
    }
    return res
