from fastapi import APIRouter, HTTPException, Depends, status
from app.auth import get_current_user
from app.database import get_db_connection
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import urllib.request
import csv
import io
import time
import logging

logger = logging.getLogger("consumos_router")

router = APIRouter(prefix="/api/consumos", tags=["Consumos"])

INFLUX_URL = "http://192.168.0.116:8086/api/v2/query?org=elis_laundry"
INFLUX_TOKEN = "2ivBvpVNfzgfivqZzg_5K2cLIAMzXDeT4pfXOMMOj63-bbVLRyICcPfqBTUotGpyZeqJXv31Mj5c87Ec2aNUlA=="

GAS_MACHINES_MAP = {
    "sensor_gas_general": {"machine_id": "gas_general", "title": "Gas General", "multiplier": 1.0, "eui": "24E1241360560098"},
    "gas_general": {"machine_id": "gas_general", "title": "Gas General", "multiplier": 1.0, "eui": "24E1241360560098"},
    "calandra1_IoT": {"machine_id": "calandra1", "title": "Gas Calandra 1", "multiplier": 0.1, "eui": "24E124136056524B"},
    "calandra1": {"machine_id": "calandra1", "title": "Gas Calandra 1", "multiplier": 0.1, "eui": "24E124136056524B"},
    "Calandra 2": {"machine_id": "calandra_2", "title": "Gas Calandra 2", "multiplier": 0.1, "eui": "24E12413605698EF"},
    "calandra_2": {"machine_id": "calandra_2", "title": "Gas Calandra 2", "multiplier": 0.1, "eui": "24E12413605698EF"},
    "Calandra 3": {"machine_id": "calandra_3", "title": "Gas Calandra 3", "multiplier": 0.1, "eui": "24E124136056E73C"},
    "calandra_3": {"machine_id": "calandra_3", "title": "Gas Calandra 3", "multiplier": 0.1, "eui": "24E124136056E73C"},
    "caldera1": {"machine_id": "caldera1", "title": "Gas Caldera 1", "multiplier": 0.1, "eui": "24E1241360563A6E"},
    "caldera2": {"machine_id": "caldera2", "title": "Gas Caldera 2", "multiplier": 0.1, "eui": "24E124136056DBB0"},
    "Túnel de Secado VT": {"machine_id": "secado_vt", "title": "Gas Túnel VT", "multiplier": 0.1, "eui": "24E124136056BCB7"},
    "secado_vt": {"machine_id": "secado_vt", "title": "Gas Túnel VT", "multiplier": 0.1, "eui": "24E124136056BCB7"},
    "secadoras_man": {"machine_id": "secadoras_man", "title": "Gas Secadoras Manuales", "multiplier": 0.1, "eui": "24E124136056026D"},
    "gas_secadoras_man": {"machine_id": "secadoras_man", "title": "Gas Secadoras Manuales", "multiplier": 0.1, "eui": "24E124136056026D"},
    "secadoras_aut": {"machine_id": "secadoras_aut", "title": "Gas Secadoras Automáticas", "multiplier": 0.1, "eui": "24E124136056AUTO"},
    "gas_secadoras_aut": {"machine_id": "secadoras_aut", "title": "Gas Secadoras Automáticas", "multiplier": 0.1, "eui": "24E124136056AUTO"}
}

def parse_influx_time(time_str: str) -> datetime:
    """Parsea de forma ultra-robusta timestamps de InfluxDB con cualquier cantidad de decimales en segundos."""
    if not time_str:
        return datetime.utcnow()
    try:
        ts = str(time_str).strip().rstrip("Z")
        if "." in ts:
            base, frac = ts.split(".", 1)
            frac = (frac + "000000")[:6]
            return datetime.strptime(f"{base}.{frac}", "%Y-%m-%dT%H:%M:%S.%f")
        else:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return datetime.utcnow()


def query_flux(flux: str) -> List[Dict[str, str]]:
    req = urllib.request.Request(INFLUX_URL, data=flux.encode('utf-8'))
    req.add_header('Authorization', f'Token {INFLUX_TOKEN}')
    req.add_header('Content-Type', 'application/vnd.flux')
    req.add_header('Accept', 'application/csv')
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            lines = [line for line in content.splitlines() if line and not line.startswith('#')]
            return list(csv.DictReader(lines))
    except Exception as e:
        logger.error(f"Error querying InfluxDB: {e}")
        return []

_gas_summary_cache = {
    "timestamp": 0.0,
    "data": None
}

def get_live_gas_summary() -> Dict[str, Dict[str, Any]]:
    global _gas_summary_cache
    now_ts = time.time()
    if _gas_summary_cache["data"] and (now_ts - _gas_summary_cache["timestamp"] < 2.0):
        return _gas_summary_cache["data"]

    now_dt = datetime.now()
    today_start_iso = now_dt.strftime("%Y-%m-%dT00:00:00Z")

    flux1 = f"""
    today_spread = from(bucket: "gas_telemetry")
      |> range(start: {today_start_iso})
      |> filter(fn: (r) => r._measurement == "gas_consumption" and r._field == "volume_m3")
      |> spread()
      |> set(key: "_stat", value: "today_spread")

    hour_spread = from(bucket: "gas_telemetry")
      |> range(start: -1h)
      |> filter(fn: (r) => r._measurement == "gas_consumption" and r._field == "volume_m3")
      |> spread()
      |> set(key: "_stat", value: "hour_spread")

    union(tables: [today_spread, hour_spread])
    """

    flux2 = """
    from(bucket: "gas_telemetry")
      |> range(start: -2h)
      |> filter(fn: (r) => r._measurement == "gas_consumption" and r._field == "temperature")
      |> last()
    """

    data: Dict[str, Dict[str, Any]] = {}
    for m_id in ["gas_general", "calandra1", "calandra_2", "calandra_3", "caldera1", "caldera2", "secado_vt", "secadoras_man", "secadoras_aut"]:
        data[m_id] = {
            "consumo_hoy_m3": 0.0,
            "caudal_1h_m3h": 0.0,
            "temperatura": None
        }

    try:
        rows1 = query_flux(flux1)
        for r in rows1:
            m_id = r.get("machine_id")
            stat = r.get("_stat")
            val_str = r.get("_value", "0")
            try:
                val = float(val_str)
            except ValueError:
                val = 0.0

            if m_id in data:
                if stat == "today_spread":
                    data[m_id]["consumo_hoy_m3"] = round(val, 2)
                elif stat == "hour_spread":
                    data[m_id]["caudal_1h_m3h"] = round(val, 2)

        rows2 = query_flux(flux2)
        for r in rows2:
            m_id = r.get("machine_id")
            val_str = r.get("_value", "0")
            try:
                val = float(val_str)
            except ValueError:
                val = 0.0

            if m_id in data:
                data[m_id]["temperatura"] = round(val, 1)

        # Calcular balance para Secadoras Automáticas: Gas General - Suma de todas las demás máquinas
        gg_hoy = data.get("gas_general", {}).get("consumo_hoy_m3", 0.0)
        gg_caudal = data.get("gas_general", {}).get("caudal_1h_m3h", 0.0)

        maq_keys = ["calandra1", "calandra_2", "calandra_3", "caldera1", "caldera2", "secado_vt", "secadoras_man"]
        sum_hoy = sum(data.get(k, {}).get("consumo_hoy_m3", 0.0) for k in maq_keys)
        sum_caudal = sum(data.get(k, {}).get("caudal_1h_m3h", 0.0) for k in maq_keys)

        data["secadoras_aut"]["consumo_hoy_m3"] = round(max(0.0, gg_hoy - sum_hoy), 2)
        data["secadoras_aut"]["caudal_1h_m3h"] = round(max(0.0, gg_caudal - sum_caudal), 2)
        data["secadoras_aut"]["temperatura"] = 28.5

        _gas_summary_cache["timestamp"] = now_ts
        _gas_summary_cache["data"] = data
    except Exception as e:
        logger.error(f"Error updating gas summary cache: {e}")

    return _gas_summary_cache["data"] or data


def check_consumos_permission(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") == "Invitado":
        return current_user

    conn = get_db_connection()
    perm = conn.execute("""
        SELECT can_view FROM role_permissions WHERE role = ? AND module_code = 'consumos'
    """, (current_user["role"],)).fetchone()
    conn.close()

    if not perm or not perm["can_view"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder al módulo de Consumos"
        )
    return current_user


@router.get("/summary")
def get_consumos_summary(user: dict = Depends(check_consumos_permission)):
    gas_data = get_live_gas_summary()
    try:
        from app.services.electricity_service import get_live_electricity_summary
        elec_summary = get_live_electricity_summary()
    except Exception as e_elec:
        logger.error(f"Error obteniendo live electricity summary: {e_elec}")
        elec_summary = {}

    gen_elec = elec_summary.get("I_general", {})

    gg = gas_data.get("gas_general", {})
    c1 = gas_data.get("calandra1", {})
    c2 = gas_data.get("calandra_2", {})
    c3 = gas_data.get("calandra_3", {})
    cald1 = gas_data.get("caldera1", {})
    cald2 = gas_data.get("caldera2", {})
    vt = gas_data.get("secado_vt", {})
    sec_man = gas_data.get("secadoras_man", {})
    sec_aut = gas_data.get("secadoras_aut", {})

    res = {
        "status": "online",
        "planta": "ELIS NÁJERA 4.0",
        "generales": {
            "agua_general": {
                "titulo": "Agua (General)",
                "variable_telemetria": "AGUA_GENERAL",
                "caudal_m3h": 18.5,
                "consumo_hoy_m3": 210.4,
                "reciclaje_pct": 42.0,
                "icono": "fa-water",
                "color": "blue"
            },
            "gas_general": {
                "titulo": "Gas General Hoy",
                "variable_telemetria": "sensor_gas_general",
                "consumo_hoy_m3": gg.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(gg.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_m3h": gg.get("caudal_1h_m3h", 0.0),
                "caudal_kwh": round(gg.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "presion_vapor_bar": 9.2,
                "eficiencia_caldera_pct": 92.4,
                "temperatura_c": gg.get("temperatura", 25.7),
                "icono": "fa-fire",
                "color": "orange"
            },
            "energia_electrica": {
                "titulo": "Energía Eléctrica General",
                "variable_telemetria": "I_general",
                "potencia_activa_kw": gen_elec.get("potencia_activa_kw", 0.0),
                "potencia_kw": gen_elec.get("potencia_activa_kw", 0.0),
                "potencia_aparente_kva": gen_elec.get("potencia_aparente_kva", 0.0),
                "consumo_hoy_kwh": gen_elec.get("consumo_hoy_kwh", 0.0),
                "corriente_max_a": gen_elec.get("corriente_max_a", 0.0),
                "corriente_actual_a": gen_elec.get("corriente_actual_a", 0.0),
                "factor_potencia": 0.90,
                "icono": "fa-bolt",
                "color": "amber"
            }
        },
        "desglose_agua": {
            "agua_tunel_lavadoras": {
                "titulo": "Agua Túnel y Lavadoras",
                "variable_telemetria": "AGUA_TUNEL_LAVADORAS",
                "caudal_m3h": 14.2,
                "consumo_especifico_l_kg": 4.8,
                "consumo_hoy_m3": 168.5,
                "icono": "fa-shower",
                "color": "blue"
            }
        },
        "desglose_gas": {
            "gas_tunel_vt": {
                "titulo": "Gas Túnel VT Hoy",
                "variable_telemetria": "Túnel de Secado VT",
                "consumo_m3h": vt.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": vt.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(vt.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(vt.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_secado_c": vt.get("temperatura", 29.9),
                "icono": "fa-wind",
                "color": "orange"
            },
            "gas_calandra_1": {
                "titulo": "Gas Calandra 1 Hoy",
                "variable_telemetria": "calandra1_IoT",
                "consumo_m3h": c1.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": c1.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(c1.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(c1.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": c1.get("temperatura", 24.3),
                "icono": "fa-scroll",
                "color": "orange"
            },
            "gas_calandra_2": {
                "titulo": "Gas Calandra 2 Hoy",
                "variable_telemetria": "Calandra 2",
                "consumo_m3h": c2.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": c2.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(c2.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(c2.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": c2.get("temperatura", 24.4),
                "icono": "fa-scroll",
                "color": "orange"
            },
            "gas_calandra_3": {
                "titulo": "Gas Calandra 3 Hoy",
                "variable_telemetria": "Calandra 3",
                "consumo_m3h": c3.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": c3.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(c3.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(c3.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": c3.get("temperatura", 24.5),
                "icono": "fa-eye",
                "color": "orange"
            },
            "gas_caldera_1": {
                "titulo": "Gas Caldera 1 Hoy",
                "variable_telemetria": "caldera1",
                "consumo_m3h": cald1.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": cald1.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(cald1.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(cald1.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": cald1.get("temperatura", 33.6),
                "icono": "fa-fire-burner",
                "color": "orange"
            },
            "gas_caldera_2": {
                "titulo": "Gas Caldera 2 Hoy",
                "variable_telemetria": "caldera2",
                "consumo_m3h": cald2.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": cald2.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(cald2.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(cald2.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": cald2.get("temperatura", 31.3),
                "icono": "fa-fire-burner",
                "color": "orange"
            },
            "gas_secadoras_man": {
                "titulo": "Gas Secadoras Manuales Hoy",
                "variable_telemetria": "secadoras_man",
                "consumo_m3h": sec_man.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": sec_man.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(sec_man.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(sec_man.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": sec_man.get("temperatura", 22.0),
                "icono": "fa-hands",
                "color": "orange"
            },
            "gas_secadoras_aut": {
                "titulo": "Gas Secadoras Automáticas Hoy",
                "variable_telemetria": "secadoras_aut",
                "consumo_m3h": sec_aut.get("caudal_1h_m3h", 0.0),
                "consumo_hoy_m3": sec_aut.get("consumo_hoy_m3", 0.0),
                "consumo_hoy_kwh": round(sec_aut.get("consumo_hoy_m3", 0.0) * 11.68, 1),
                "caudal_kwh": round(sec_aut.get("caudal_1h_m3h", 0.0) * 11.68, 1),
                "temp_trabajo_c": sec_aut.get("temperatura", 28.5),
                "icono": "fa-robot",
                "color": "orange"
            }
        },
        "desglose_electricidad": {
            "elec_tunel": {
                "titulo": "Electricidad Túnel",
                "variable_telemetria": "I_motor_tunel",
                "potencia_kw": elec_summary.get("I_motor_tunel", {}).get("potencia_kw", 0.0),
                "potencia_activa_kw": elec_summary.get("I_motor_tunel", {}).get("potencia_kw", 0.0),
                "potencia_aparente_kva": elec_summary.get("I_motor_tunel", {}).get("potencia_aparente_kva", 0.0),
                "consumo_hoy_kwh": elec_summary.get("I_motor_tunel", {}).get("consumo_hoy_kwh", 0.0),
                "corriente_max_a": elec_summary.get("I_motor_tunel", {}).get("corriente_max_a", 0.0),
                "corriente_actual_a": elec_summary.get("I_motor_tunel", {}).get("corriente_actual_a", 0.0),
                "icono": "fa-circle-notch",
                "color": "amber"
            },
            "elec_calandra_1": {
                "titulo": "Electricidad Calandra 1",
                "variable_telemetria": "I_bomba_calandra1",
                "potencia_kw": elec_summary.get("I_bomba_calandra1", {}).get("potencia_kw", 0.0),
                "potencia_activa_kw": elec_summary.get("I_bomba_calandra1", {}).get("potencia_kw", 0.0),
                "potencia_aparente_kva": elec_summary.get("I_bomba_calandra1", {}).get("potencia_aparente_kva", 0.0),
                "consumo_hoy_kwh": elec_summary.get("I_bomba_calandra1", {}).get("consumo_hoy_kwh", 0.0),
                "corriente_max_a": elec_summary.get("I_bomba_calandra1", {}).get("corriente_max_a", 0.0),
                "corriente_actual_a": elec_summary.get("I_bomba_calandra1", {}).get("corriente_actual_a", 0.0),
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_calandra_2": {
                "titulo": "Electricidad Calandra 2",
                "variable_telemetria": "Bomba_calandra2",
                "potencia_kw": elec_summary.get("Bomba_calandra2", {}).get("potencia_kw", 0.0),
                "potencia_activa_kw": elec_summary.get("Bomba_calandra2", {}).get("potencia_kw", 0.0),
                "potencia_aparente_kva": elec_summary.get("Bomba_calandra2", {}).get("potencia_aparente_kva", 0.0),
                "consumo_hoy_kwh": elec_summary.get("Bomba_calandra2", {}).get("consumo_hoy_kwh", 0.0),
                "corriente_max_a": elec_summary.get("Bomba_calandra2", {}).get("corriente_max_a", 0.0),
                "corriente_actual_a": elec_summary.get("Bomba_calandra2", {}).get("corriente_actual_a", 0.0),
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_calandra_3": {
                "titulo": "Electricidad Calandra 3",
                "variable_telemetria": "I_bomba_calandra3",
                "potencia_kw": elec_summary.get("I_bomba_calandra3", {}).get("potencia_kw", 0.0),
                "potencia_activa_kw": elec_summary.get("I_bomba_calandra3", {}).get("potencia_kw", 0.0),
                "potencia_aparente_kva": elec_summary.get("I_bomba_calandra3", {}).get("potencia_aparente_kva", 0.0),
                "consumo_hoy_kwh": elec_summary.get("I_bomba_calandra3", {}).get("consumo_hoy_kwh", 0.0),
                "corriente_max_a": elec_summary.get("I_bomba_calandra3", {}).get("corriente_max_a", 0.0),
                "corriente_actual_a": elec_summary.get("I_bomba_calandra3", {}).get("corriente_actual_a", 0.0),
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_prensa_tunel": {
                "titulo": "Electricidad Prensa Túnel",
                "variable_telemetria": "I_prensa_tunel",
                "potencia_kw": elec_summary.get("I_prensa_tunel", {}).get("potencia_kw", 0.0),
                "potencia_activa_kw": elec_summary.get("I_prensa_tunel", {}).get("potencia_kw", 0.0),
                "potencia_aparente_kva": elec_summary.get("I_prensa_tunel", {}).get("potencia_aparente_kva", 0.0),
                "consumo_hoy_kwh": elec_summary.get("I_prensa_tunel", {}).get("consumo_hoy_kwh", 0.0),
                "corriente_max_a": elec_summary.get("I_prensa_tunel", {}).get("corriente_max_a", 0.0),
                "corriente_actual_a": elec_summary.get("I_prensa_tunel", {}).get("corriente_actual_a", 0.0),
                "icono": "fa-compress-arrows-alt",
                "color": "amber"
            }
        }
    }

    # Integracion dinamica de telemetria de agua desde SQLite
    try:
        conn_proc = get_db_connection()
        today_iso = datetime.now().strftime("%Y-%m-%d 00:00:00")
        row_ag = conn_proc.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM procesos_telemetria
            WHERE variable = 'AGUA_GENERAL' AND timestamp_iso >= ?
        """, (today_iso,)).fetchone()
        agua_hoy_m3 = round(float(row_ag[0]), 1) if row_ag and row_ag[0] is not None else 0.0

        row_last_agua = conn_proc.execute("""
            SELECT COALESCE(caudal_m3h, 0)
            FROM procesos_telemetria
            WHERE variable = 'AGUA_GENERAL'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        agua_caudal = round(float(row_last_agua[0]), 1) if row_last_agua and row_last_agua[0] is not None else 0.0

        if agua_hoy_m3 > 0:
            res["generales"]["agua_general"]["consumo_hoy_m3"] = agua_hoy_m3
        if agua_caudal > 0:
            res["generales"]["agua_general"]["caudal_m3h"] = agua_caudal

        row_at = conn_proc.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM procesos_telemetria
            WHERE variable = 'AGUA_TUNEL_LAVADORAS' AND timestamp_iso >= ?
        """, (today_iso,)).fetchone()
        at_hoy_m3 = round(float(row_at[0]), 1) if row_at and row_at[0] is not None else 0.0

        row_last_at = conn_proc.execute("""
            SELECT COALESCE(caudal_m3h, 0)
            FROM procesos_telemetria
            WHERE variable = 'AGUA_TUNEL_LAVADORAS'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        at_caudal = round(float(row_last_at[0]), 1) if row_last_at and row_last_at[0] is not None else 0.0

        if at_hoy_m3 > 0 and "agua_tunel_lavadoras" in res.get("desglose_agua", {}):
            res["desglose_agua"]["agua_tunel_lavadoras"]["consumo_hoy_m3"] = at_hoy_m3
        if at_caudal > 0 and "agua_tunel_lavadoras" in res.get("desglose_agua", {}):
            res["desglose_agua"]["agua_tunel_lavadoras"]["caudal_m3h"] = at_caudal

        conn_proc.close()
    except Exception as e_proc:
        logger.warning(f"Error integrando telemetria de agua: {e_proc}")

    return res


class ProcesoIngestaPayload(BaseModel):
    variable: str
    pulsos: Optional[int] = 1
    valor: float
    unidad: Optional[str] = "m³"
    caudal_m3h: Optional[float] = 0.0
    dispositivo: Optional[str] = "Monitor Telemetria 192.168.0.116:3000"
    timestamp: Optional[str] = None


@router.get("/telemetria")
def get_proceso_telemetria(
    variable: str,
    fecha_inicio: Optional[str] = None,
    hora_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    hora_fin: Optional[str] = None,
    user: dict = Depends(check_consumos_permission)
):
    """Consulta dinámica de telemetría para cualquier variable de proceso."""
    now = datetime.now()
    if not fecha_inicio:
        fecha_inicio = now.strftime("%Y-%m-%d")
    if not hora_inicio:
        hora_inicio = "00:00:00"
    if not fecha_fin:
        fecha_fin = now.strftime("%Y-%m-%d")
    if not hora_fin:
        hora_fin = "23:59:59"

    start_iso = f"{fecha_inicio} {hora_inicio}"
    end_iso = f"{fecha_fin} {hora_fin}"

    # CASO 0: Consulta de Electricidad en tiempo real
    try:
        from app.services.electricity_service import VARIABLE_TO_SENSOR, get_electricity_telemetria
        if variable in VARIABLE_TO_SENSOR:
            res = get_electricity_telemetria(variable, start_iso, end_iso)
            res["filtro"] = {
                "fecha_inicio": fecha_inicio,
                "hora_inicio": hora_inicio,
                "fecha_fin": fecha_fin,
                "hora_fin": hora_fin,
                "start_iso": start_iso,
                "end_iso": end_iso
            }
            return res
    except Exception as e_elec_query:
        logger.error(f"Error consultando telemetria electrica: {e_elec_query}")

    # CASO 1: Consulta de Gas directo a InfluxDB
    if variable in GAS_MACHINES_MAP:
        gas_info = GAS_MACHINES_MAP[variable]
        machine_id = gas_info["machine_id"]
        multiplier = gas_info["multiplier"]
        eui = gas_info["eui"]
        title = gas_info["title"]

        try:
            # Parsear rango a RFC3339 UTC (-2 horas por timezone España CEST)
            dt_start = datetime.strptime(f"{fecha_inicio} {hora_inicio}", "%Y-%m-%d %H:%M:%S") - timedelta(hours=2)
            dt_end = datetime.strptime(f"{fecha_fin} {hora_fin}", "%Y-%m-%d %H:%M:%S") - timedelta(hours=2)
            start_rfc = dt_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_rfc = dt_end.strftime("%Y-%m-%dT%H:%M:%SZ")

            if machine_id == "secadoras_aut":
                # Calcular telemetría sintética de balance a partir de gas_general y las demás máquinas
                flux_gg = f"""
                from(bucket: "gas_telemetry")
                  |> range(start: {start_rfc}, stop: {end_rfc})
                  |> filter(fn: (r) => r._measurement == "gas_consumption" and r.machine_id == "gas_general" and r._field == "volume_m3")
                  |> sort(columns: ["_time"], desc: true)
                  |> limit(n: 200)
                """
                gg_rows = query_flux(flux_gg)

                # Spread total de todas las máquinas en el rango
                flux_spread_all = f"""
                from(bucket: "gas_telemetry")
                  |> range(start: {start_rfc}, stop: {end_rfc})
                  |> filter(fn: (r) => r._measurement == "gas_consumption" and r._field == "volume_m3")
                  |> spread()
                """
                spread_all_rows = query_flux(flux_spread_all)
                spread_map = {sr.get("machine_id"): float(sr.get("_value", 0)) for sr in spread_all_rows if sr.get("machine_id")}

                gg_tot = spread_map.get("gas_general", 0.0)
                maq_tot = sum(spread_map.get(m, 0.0) for m in ["calandra1", "calandra_2", "calandra_3", "caldera1", "caldera2", "secado_vt", "secadoras_man"])
                acumulado_aut = round(max(0.0, gg_tot - maq_tot), 2)

                ratio = (acumulado_aut / gg_tot) if gg_tot > 0 else 0.28
                registros = []

                for idx, r in enumerate(gg_rows):
                    time_str = r.get("_time", "")
                    dt_utc = parse_influx_time(time_str)
                    dt_local = dt_utc + timedelta(hours=2)
                    ts_iso = dt_local.strftime("%Y-%m-%d %H:%M:%S")
                    ts_str = dt_local.strftime("%d/%m/%Y %H:%M:%S")

                    try:
                        gg_vol = float(r.get("_value", 0))
                    except (ValueError, TypeError):
                        gg_vol = 0.0

                    vol_aut = round(gg_vol * ratio, 2)
                    pulses_val = int(vol_aut * 10)

                    caudal = 0.0
                    delta_m3 = 0.0
                    if idx < len(gg_rows) - 1:
                        next_r = gg_rows[idx + 1]
                        try:
                            next_vol = round(float(next_r.get("_value", 0)) * ratio, 2)
                            delta_m3 = round(max(0.0, vol_aut - next_vol), 2)
                            next_dt_utc = parse_influx_time(next_r.get("_time", ""))
                            delta_h = (dt_utc - next_dt_utc).total_seconds() / 3600.0
                            if 0 < delta_h < 2.0 and delta_m3 > 0:
                                caudal = round(delta_m3 / delta_h, 1)
                        except Exception:
                            pass

                    registros.append({
                        "id": idx + 1,
                        "variable": variable,
                        "timestamp": ts_str,
                        "timestamp_iso": ts_iso,
                        "pulsos": pulses_val,
                        "valor": vol_aut,
                        "kwh": round(vol_aut * 11.68, 1),
                        "delta_m3": delta_m3,
                        "unidad": "m³",
                        "caudal_m3h": max(0.0, caudal),
                        "caudal_kwh": round(max(0.0, caudal) * 11.68, 1),
                        "dispositivo": f"Gas Secadoras Automáticas (Balance / EUI: {eui})"
                    })

                return {
                    "variable": variable,
                    "acumulado": acumulado_aut,
                    "acumulado_kwh": round(acumulado_aut * 11.68, 1),
                    "unidad": "m³",
                    "total_pulsos": int(acumulado_aut * 10),
                    "filtro": {
                        "fecha_inicio": fecha_inicio,
                        "hora_inicio": hora_inicio,
                        "fecha_fin": fecha_fin,
                        "hora_fin": hora_fin,
                        "start_iso": start_iso,
                        "end_iso": end_iso
                    },
                    "total_registros": len(registros),
                    "registros": registros
                }

            flux_detail = f"""
            from(bucket: "gas_telemetry")
              |> range(start: {start_rfc}, stop: {end_rfc})
              |> filter(fn: (r) => r._measurement == "gas_consumption" and r.machine_id == "{machine_id}")
              |> filter(fn: (r) => r._field == "pulses" or r._field == "volume_m3")
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> sort(columns: ["_time"], desc: true)
              |> limit(n: 200)
            """

            rows = query_flux(flux_detail)
            registros = []

            for idx, r in enumerate(rows):
                time_str = r.get("_time", "")
                dt_utc = parse_influx_time(time_str)
                dt_local = dt_utc + timedelta(hours=2)
                ts_iso = dt_local.strftime("%Y-%m-%d %H:%M:%S")
                ts_str = dt_local.strftime("%d/%m/%Y %H:%M:%S")

                try:
                    pulses_val = int(float(r.get("pulses", 0) or 0))
                except (ValueError, TypeError):
                    pulses_val = 0

                try:
                    raw_vol = r.get("volume_m3")
                    if raw_vol is not None and str(raw_vol).strip() != "":
                        vol_val = float(raw_vol)
                    else:
                        vol_val = round(pulses_val * multiplier, 2)
                except (ValueError, TypeError):
                    vol_val = round(pulses_val * multiplier, 2)

                caudal = 0.0
                delta_m3 = 0.0
                if idx < len(rows) - 1:
                    next_r = rows[idx + 1]
                    try:
                        next_pulses = int(float(next_r.get("pulses", 0) or 0))
                    except Exception:
                        next_pulses = 0

                    try:
                        raw_next_vol = next_r.get("volume_m3")
                        if raw_next_vol is not None and str(raw_next_vol).strip() != "":
                            next_vol = float(raw_next_vol)
                        else:
                            next_vol = round(next_pulses * multiplier, 2)
                    except Exception:
                        next_vol = round(next_pulses * multiplier, 2)

                    # Cálculo directo e independiente de delta_m3
                    delta_m3 = round(max(0.0, vol_val - next_vol), 2)

                    try:
                        next_dt_utc = parse_influx_time(next_r.get("_time", ""))
                        delta_h = (dt_utc - next_dt_utc).total_seconds() / 3600.0
                        if 0 < delta_h < 2.0 and delta_m3 > 0:
                            caudal = round(delta_m3 / delta_h, 1)
                    except Exception:
                        pass

                registros.append({
                    "id": idx + 1,
                    "variable": variable,
                    "timestamp": ts_str,
                    "timestamp_iso": ts_iso,
                    "pulsos": pulses_val,
                    "valor": round(vol_val, 2),
                    "kwh": round(vol_val * 11.68, 1),
                    "delta_m3": delta_m3,
                    "unidad": "m³",
                    "caudal_m3h": max(0.0, caudal),
                    "caudal_kwh": round(max(0.0, caudal) * 11.68, 1),
                    "dispositivo": f"{title} (EUI: {eui})"
                })

            # Calcular acumulado exacto de todo el rango solicitado mediante spread() en Flux
            flux_range_spread = f"""
            from(bucket: "gas_telemetry")
              |> range(start: {start_rfc}, stop: {end_rfc})
              |> filter(fn: (r) => r._measurement == "gas_consumption" and r.machine_id == "{machine_id}")
              |> filter(fn: (r) => r._field == "volume_m3" or r._field == "pulses")
              |> spread()
            """
            spread_rows = query_flux(flux_range_spread)
            acumulado = 0.0
            total_pulsos = 0
            for sr in spread_rows:
                field = sr.get("_field")
                try:
                    val = float(sr.get("_value", 0))
                except ValueError:
                    val = 0.0
                if field == "volume_m3":
                    acumulado = round(max(0.0, val), 2)
                elif field == "pulses":
                    total_pulsos = int(max(0, val))

            if acumulado == 0.0 and len(registros) >= 2:
                acumulado = round(max(0.0, registros[0]["valor"] - registros[-1]["valor"]), 2)
                total_pulsos = max(0, registros[0]["pulsos"] - registros[-1]["pulsos"])

            return {
                "variable": variable,
                "acumulado": acumulado,
                "acumulado_kwh": round(acumulado * 11.68, 1),
                "unidad": "m³",
                "total_pulsos": total_pulsos,
                "filtro": {
                    "fecha_inicio": fecha_inicio,
                    "hora_inicio": hora_inicio,
                    "fecha_fin": fecha_fin,
                    "hora_fin": hora_fin,
                    "start_iso": start_iso,
                    "end_iso": end_iso
                },
                "total_registros": len(registros),
                "registros": registros
            }

        except Exception as ex:
            logger.error(f"Error querying gas telemetria from InfluxDB: {ex}")

    # CASO 2: Fallback a SQLite para Agua y Electricidad
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, variable, timestamp, timestamp_iso, pulsos, valor, unidad, caudal_m3h, dispositivo, created_at
        FROM procesos_telemetria
        WHERE variable = ? AND timestamp_iso >= ? AND timestamp_iso <= ?
        ORDER BY timestamp_iso DESC
    """, (variable, start_iso, end_iso)).fetchall()

    if not rows and variable == "AGUA_TUNEL_LAVADORAS":
        agua_rows = conn.execute("""
            SELECT id, variable, timestamp, timestamp_iso, pulsos, volumen_m3 as valor, 'm³' as unidad, caudal_m3h, dispositivo, created_at
            FROM agua_tunel_telemetria
            WHERE timestamp_iso >= ? AND timestamp_iso <= ?
            ORDER BY timestamp_iso DESC
        """, (start_iso, end_iso)).fetchall()
        rows = agua_rows

    total_agg = conn.execute("""
        SELECT 
            COALESCE(SUM(pulsos), 0) as total_pulsos,
            COALESCE(SUM(valor), 0) as total_valor
        FROM procesos_telemetria
        WHERE variable = ? AND timestamp_iso >= ? AND timestamp_iso <= ?
    """, (variable, start_iso, end_iso)).fetchone()

    total_pulsos = total_agg["total_pulsos"] if total_agg else 0
    acumulado = round(total_agg["total_valor"], 2) if total_agg else 0.0

    if acumulado == 0.0 and variable == "AGUA_TUNEL_LAVADORAS":
        total_agua = conn.execute("""
            SELECT COALESCE(SUM(pulsos), 0) as total_pulsos, COALESCE(SUM(volumen_m3), 0) as total_valor
            FROM agua_tunel_telemetria WHERE timestamp_iso >= ? AND timestamp_iso <= ?
        """, (start_iso, end_iso)).fetchone()
        if total_agua:
            total_pulsos = total_agua["total_pulsos"]
            acumulado = round(total_agua["total_valor"], 2)

    conn.close()

    registros = []
    unidad = "m³"
    for r in rows:
        r_dict = dict(r)
        unidad = r_dict.get("unidad", "m³") or "m³"
        registros.append({
            "id": r_dict["id"],
            "variable": r_dict["variable"],
            "timestamp": r_dict["timestamp"],
            "timestamp_iso": r_dict["timestamp_iso"],
            "pulsos": r_dict["pulsos"],
            "valor": round(r_dict["valor"], 2),
            "unidad": unidad,
            "caudal_m3h": round(r_dict["caudal_m3h"], 1),
            "dispositivo": r_dict["dispositivo"]
        })

    return {
        "variable": variable,
        "acumulado": acumulado,
        "unidad": unidad,
        "total_pulsos": total_pulsos,
        "filtro": {
            "fecha_inicio": fecha_inicio,
            "hora_inicio": hora_inicio,
            "fecha_fin": fecha_fin,
            "hora_fin": hora_fin,
            "start_iso": start_iso,
            "end_iso": end_iso
        },
        "total_registros": len(registros),
        "registros": registros
    }


# Endpoints de Retrocompatibilidad
@router.get("/agua-tunel/telemetria")
def get_agua_tunel_telemetria(
    fecha_inicio: Optional[str] = None,
    hora_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    hora_fin: Optional[str] = None,
    user: dict = Depends(check_consumos_permission)
):
    res = get_proceso_telemetria(
        variable="AGUA_TUNEL_LAVADORAS",
        fecha_inicio=fecha_inicio,
        hora_inicio=hora_inicio,
        fecha_fin=fecha_fin,
        hora_fin=hora_fin,
        user=user
    )
    res["factor_conversion"] = "1 pulso = 0.1 m3 (100 Litros)"
    res["acumulado_m3"] = res["acumulado"]
    return res


@router.post("/ingesta")
def registrar_ingesta_proceso(
    payload: ProcesoIngestaPayload,
    user: dict = Depends(check_consumos_permission)
):
    now_dt = datetime.now()
    timestamp_str = payload.timestamp or now_dt.strftime("%d/%m/%Y %H:%M:%S")
    timestamp_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    valor = round(payload.valor, 2)
    unidad = payload.unidad or "m³"
    caudal_m3h = float(payload.caudal_m3h or 0.0)
    dispositivo = payload.dispositivo or f"Monitor Telemetria 192.168.0.116:3000 ({payload.variable})"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO procesos_telemetria (variable, timestamp, timestamp_iso, pulsos, valor, unidad, caudal_m3h, dispositivo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (payload.variable, timestamp_str, timestamp_iso, payload.pulsos or 1, valor, unidad, caudal_m3h, dispositivo))
    
    if payload.variable == "AGUA_TUNEL_LAVADORAS":
        cursor.execute("""
            INSERT INTO agua_tunel_telemetria (variable, timestamp, timestamp_iso, pulsos, volumen_m3, caudal_m3h, dispositivo)
            VALUES ('AGUA_TUNEL_LAVADORAS', ?, ?, ?, ?, ?, ?)
        """, (timestamp_str, timestamp_iso, payload.pulsos or 1, valor, caudal_m3h, dispositivo))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "variable": payload.variable,
        "valor": valor,
        "unidad": unidad,
        "timestamp_iso": timestamp_iso
    }


class AguaIngestaPayload(BaseModel):
    pulsos: int
    caudal_m3h: Optional[float] = 0.0
    dispositivo: Optional[str] = "Contador Pulsos Agua 192.168.0.116:3000"
    timestamp: Optional[str] = None


@router.post("/agua-tunel/ingesta")
def registrar_ingesta_agua(
    payload: AguaIngestaPayload,
    user: dict = Depends(check_consumos_permission)
):
    volumen_m3 = round(payload.pulsos * 0.1, 2)
    return registrar_ingesta_proceso(
        payload=ProcesoIngestaPayload(
            variable="AGUA_TUNEL_LAVADORAS",
            pulsos=payload.pulsos,
            valor=volumen_m3,
            unidad="m³",
            caudal_m3h=payload.caudal_m3h,
            dispositivo=payload.dispositivo,
            timestamp=payload.timestamp
        ),
        user=user
    )
