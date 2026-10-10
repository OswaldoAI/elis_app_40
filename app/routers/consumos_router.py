import os
import time
import json
import urllib.request
import urllib.parse
from fastapi import APIRouter, HTTPException, Depends, status
from app.auth import get_current_user
from app.database import get_db_connection
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger("consumos_router")

_last_gas_temp_cache = {"val": 10.5, "ts": 0}

def get_cached_gas_temp() -> float:
    global _last_gas_temp_cache
    now_t = time.time()
    if now_t - _last_gas_temp_cache["ts"] < 60:
        return _last_gas_temp_cache["val"]
    try:
        influx_url = os.getenv("INFLUXDB_URL", "http://192.168.0.116:8086")
        token = os.getenv("INFLUXDB_TOKEN", "2ivBvpVNfzgfivqZzg_5K2cLIAMzXDeT4pfXOMMOj63-bbVLRyICcPfqBTUotGpyZeqJXv31Mj5c87Ec2aNUlA==")
        org = os.getenv("INFLUXDB_ORG", "elis_laundry")
        flux = '''
        from(bucket: "gas_telemetry")
          |> range(start: -2h)
          |> filter(fn: (r) => r["_measurement"] == "gas_consumption" and r["machine_id"] == "gas_general" and r["_field"] == "temperature")
          |> last()
        '''
        url = f"{influx_url}/api/v2/query?org={urllib.parse.quote(org)}"
        payload = json.dumps({"query": flux, "type": "flux"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Authorization": f"Token {token}", "Content-Type": "application/json", "Accept": "application/csv"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            txt = resp.read().decode('utf-8')
            lines = [l for l in txt.splitlines() if l and not l.startswith("#") and not l.startswith(",result,table")]
            if lines:
                val = float(lines[0].split(",")[6])
                _last_gas_temp_cache["val"] = round(val, 1)
                _last_gas_temp_cache["ts"] = now_t
                return _last_gas_temp_cache["val"]
    except Exception as e:
        logger.debug(f"No se pudo consultar temperatura de gas en Influx: {e}")
    _last_gas_temp_cache["ts"] = now_t
    return _last_gas_temp_cache["val"]

try:
    from app.services.electricity_service import (
        get_live_electricity_summary,
        get_proceso_electric_telemetry,
        VARIABLE_TO_SENSOR
    )
except Exception as e:
    logger.warning(f"No se pudo importar electricity_service: {e}")
    get_live_electricity_summary = None
    get_proceso_electric_telemetry = None
    VARIABLE_TO_SENSOR = {}

router = APIRouter(prefix="/api/consumos", tags=["Consumos"])

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
                "titulo": "Gas General",
                "variable_telemetria": "sensor_gas_general",
                "consumo_hoy_m3": 1540.0,
                "presion_vapor_bar": 9.2,
                "eficiencia_caldera_pct": 92.4,
                "icono": "fa-fire",
                "color": "orange"
            },
            "energia_electrica": {
                "titulo": "Energía Eléctrica General",
                "variable_telemetria": "I_general",
                "potencia_activa_kw": 345.2,
                "potencia_kw": 345.2,
                "consumo_hoy_kwh": 4120.0,
                "corriente_max_a": 0.0,
                "corriente_actual_a": 0.0,
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
                "titulo": "Gas Túnel VT",
                "variable_telemetria": "Túnel de Secado VT",
                "consumo_m3h": 32.5,
                "consumo_hoy_m3": 260.0,
                "temp_secado_c": 118.0,
                "icono": "fa-wind",
                "color": "orange"
            },
            "gas_calandra_1": {
                "titulo": "Gas Calandra 1",
                "variable_telemetria": "calandra1_IoT",
                "consumo_m3h": 45.0,
                "consumo_hoy_m3": 360.0,
                "temp_trabajo_c": 175.0,
                "icono": "fa-scroll",
                "color": "orange"
            },
            "gas_calandra_2": {
                "titulo": "Gas Calandra 2",
                "variable_telemetria": "Calandra 2",
                "consumo_m3h": 42.8,
                "consumo_hoy_m3": 342.4,
                "temp_trabajo_c": 175.0,
                "icono": "fa-scroll",
                "color": "orange"
            },
            "gas_calandra_3": {
                "titulo": "Gas Calandra 3",
                "variable_telemetria": "Calandra 3",
                "consumo_m3h": 48.2,
                "consumo_hoy_m3": 385.6,
                "temp_trabajo_c": 180.0,
                "icono": "fa-eye",
                "color": "orange"
            },
            "gas_caldera_1": {
                "titulo": "Gas Caldera 1",
                "variable_telemetria": "caldera1",
                "consumo_m3h": 52.4,
                "consumo_hoy_m3": 419.2,
                "temp_trabajo_c": 185.0,
                "icono": "fa-fire-burner",
                "color": "orange"
            },
            "gas_caldera_2": {
                "titulo": "Gas Caldera 2",
                "variable_telemetria": "caldera2",
                "consumo_m3h": 48.6,
                "consumo_hoy_m3": 388.8,
                "temp_trabajo_c": 182.0,
                "icono": "fa-fire-burner",
                "color": "orange"
            }
        },
        "desglose_electricidad": {
            "elec_tunel": {
                "titulo": "Electricidad Túnel",
                "variable_telemetria": "I_motor_tunel",
                "potencia_kw": 85.4,
                "consumo_hoy_kwh": 1024.8,
                "icono": "fa-circle-notch",
                "color": "amber"
            },
            "elec_calandra_1": {
                "titulo": "Electricidad Calandra 1",
                "variable_telemetria": "I_bomba_calandra1",
                "potencia_kw": 42.1,
                "consumo_hoy_kwh": 505.2,
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_calandra_2": {
                "titulo": "Electricidad Calandra 2",
                "variable_telemetria": "Bomba_calandra2",
                "potencia_kw": 39.8,
                "consumo_hoy_kwh": 477.6,
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_calandra_3": {
                "titulo": "Electricidad Calandra 3",
                "variable_telemetria": "I_bomba_calandra3",
                "potencia_kw": 46.5,
                "consumo_hoy_kwh": 558.0,
                "icono": "fa-eye",
                "color": "amber"
            },
            "elec_prensa_tunel": {
                "titulo": "Electricidad Prensa Túnel",
                "variable_telemetria": "I_prensa_tunel",
                "potencia_kw": 16.8,
                "potencia_activa_kw": 16.8,
                "consumo_hoy_kwh": 0.0,
                "corriente_max_a": 0.0,
                "corriente_actual_a": 0.0,
                "icono": "fa-compress-arrows-alt",
                "color": "amber"
            }
        }
    }

    # Integración dinámica de mediciones eléctricas en tiempo real desde el servicio de electricidad
    if get_live_electricity_summary is not None:
        try:
            live_elec = get_live_electricity_summary()
            if live_elec:
                if "I_general" in live_elec:
                    g_elec = live_elec["I_general"]
                    res["generales"]["energia_electrica"]["potencia_activa_kw"] = g_elec.get("potencia_activa_kw", 0.0)
                    res["generales"]["energia_electrica"]["potencia_kw"] = g_elec.get("potencia_kw", 0.0)
                    res["generales"]["energia_electrica"]["consumo_hoy_kwh"] = g_elec.get("consumo_hoy_kwh", 0.0)
                    res["generales"]["energia_electrica"]["corriente_max_a"] = g_elec.get("corriente_max_a", 0.0)
                    res["generales"]["energia_electrica"]["corriente_actual_a"] = g_elec.get("corriente_actual_a", 0.0)

                elec_map = {
                    "elec_tunel": "I_motor_tunel",
                    "elec_calandra_1": "I_bomba_calandra1",
                    "elec_calandra_2": "Bomba_calandra2",
                    "elec_calandra_3": "I_bomba_calandra3",
                    "elec_prensa_tunel": "I_prensa_tunel"
                }
                for card_key, v_code in elec_map.items():
                    if v_code in live_elec and card_key in res["desglose_electricidad"]:
                        c_elec = live_elec[v_code]
                        res["desglose_electricidad"][card_key]["potencia_kw"] = c_elec.get("potencia_kw", 0.0)
                        res["desglose_electricidad"][card_key]["potencia_activa_kw"] = c_elec.get("potencia_activa_kw", 0.0)
                        res["desglose_electricidad"][card_key]["consumo_hoy_kwh"] = c_elec.get("consumo_hoy_kwh", 0.0)
                        res["desglose_electricidad"][card_key]["corriente_max_a"] = c_elec.get("corriente_max_a", 0.0)
                        res["desglose_electricidad"][card_key]["corriente_actual_a"] = c_elec.get("corriente_actual_a", 0.0)
        except Exception as e:
            logger.warning(f"Error integrando live electricity en consumos summary: {e}")

    # Integración dinámica de telemetría de procesos (Gas y Agua) desde la base de datos para la jornada de hoy
    try:
        conn_proc = get_db_connection()
        today_iso = f"{datetime.now().strftime('%Y-%m-%d')} 00:00:00"

        # 1. Gas General
        row_gas = conn_proc.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM procesos_telemetria
            WHERE variable = 'sensor_gas_general' AND timestamp_iso >= ?
        """, (today_iso,)).fetchone()
        gas_hoy_m3 = round(float(row_gas[0]), 1) if row_gas and row_gas[0] is not None else 0.0

        row_last_gas = conn_proc.execute("""
            SELECT caudal_m3h
            FROM procesos_telemetria
            WHERE variable = 'sensor_gas_general'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        gas_caudal = round(float(row_last_gas[0]), 1) if row_last_gas and row_last_gas[0] is not None else 0.0

        gas_temp = get_cached_gas_temp()

        res["generales"]["gas_general"]["consumo_hoy_m3"] = gas_hoy_m3
        res["generales"]["gas_general"]["consumo_hoy_kwh"] = round(gas_hoy_m3 * 11.68, 1)
        res["generales"]["gas_general"]["caudal_m3h"] = gas_caudal
        res["generales"]["gas_general"]["temperatura_c"] = gas_temp

        # 2. Desglose de Gas por Máquina
        gas_map = {
            "gas_tunel_vt": "Túnel de Secado VT",
            "gas_calandra_1": "calandra1_IoT",
            "gas_calandra_2": "Calandra 2",
            "gas_calandra_3": "Calandra 3",
            "gas_caldera_1": "caldera1",
            "gas_caldera_2": "caldera2"
        }
        for card_key, var_name in gas_map.items():
            if card_key in res["desglose_gas"]:
                r_m3 = conn_proc.execute("""
                    SELECT COALESCE(SUM(valor), 0)
                    FROM procesos_telemetria
                    WHERE variable = ? AND timestamp_iso >= ?
                """, (var_name, today_iso)).fetchone()
                m3_val = round(float(r_m3[0]), 1) if r_m3 and r_m3[0] is not None else 0.0

                r_c = conn_proc.execute("""
                    SELECT caudal_m3h
                    FROM procesos_telemetria
                    WHERE variable = ?
                    ORDER BY id DESC LIMIT 1
                """, (var_name,)).fetchone()
                c_val = round(float(r_c[0]), 1) if r_c and r_c[0] is not None else 0.0

                res["desglose_gas"][card_key]["consumo_hoy_m3"] = m3_val
                res["desglose_gas"][card_key]["consumo_hoy_kwh"] = round(m3_val * 11.68, 1)
                res["desglose_gas"][card_key]["consumo_m3h"] = c_val
                res["desglose_gas"][card_key]["caudal_m3h"] = c_val

        # 3. Agua General
        row_agua = conn_proc.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM procesos_telemetria
            WHERE variable = 'AGUA_GENERAL' AND timestamp_iso >= ?
        """, (today_iso,)).fetchone()
        agua_hoy_m3 = round(float(row_agua[0]), 1) if row_agua and row_agua[0] is not None else 0.0

        row_last_agua = conn_proc.execute("""
            SELECT caudal_m3h
            FROM procesos_telemetria
            WHERE variable = 'AGUA_GENERAL'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        agua_caudal = round(float(row_last_agua[0]), 1) if row_last_agua and row_last_agua[0] is not None else 0.0

        res["generales"]["agua_general"]["consumo_hoy_m3"] = agua_hoy_m3
        res["generales"]["agua_general"]["caudal_m3h"] = agua_caudal

        # 4. Agua Túnel y Lavadoras
        row_at = conn_proc.execute("""
            SELECT COALESCE(SUM(valor), 0)
            FROM procesos_telemetria
            WHERE variable = 'AGUA_TUNEL_LAVADORAS' AND timestamp_iso >= ?
        """, (today_iso,)).fetchone()
        at_hoy_m3 = round(float(row_at[0]), 1) if row_at and row_at[0] is not None else 0.0

        row_last_at = conn_proc.execute("""
            SELECT caudal_m3h
            FROM procesos_telemetria
            WHERE variable = 'AGUA_TUNEL_LAVADORAS'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        at_caudal = round(float(row_last_at[0]), 1) if row_last_at and row_last_at[0] is not None else 0.0

        if "agua_tunel_lavadoras" in res["desglose_agua"]:
            res["desglose_agua"]["agua_tunel_lavadoras"]["consumo_hoy_m3"] = at_hoy_m3
            res["desglose_agua"]["agua_tunel_lavadoras"]["caudal_m3h"] = at_caudal

        conn_proc.close()
    except Exception as e_proc:
        logger.warning(f"Error integrando telemetría de procesos en consumos summary: {e_proc}")

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
    # 1. Delegar a servicio de electricidad si es sensor de corriente o energía eléctrica
    is_elec_var = (
        variable in VARIABLE_TO_SENSOR 
        or variable.lower().startswith("i_") 
        or "elec" in variable.lower() 
        or variable.lower() in ["bomba_calandra2", "i_gneral", "i_general", "energia_electrica"]
    )
    if is_elec_var and get_proceso_electric_telemetry is not None:
        return get_proceso_electric_telemetry(
            var_code=variable,
            fecha_inicio=fecha_inicio or "",
            hora_inicio=hora_inicio or "00:00:00",
            fecha_fin=fecha_fin or "",
            hora_fin=hora_fin or "23:59:59"
        )
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
