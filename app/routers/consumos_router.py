from fastapi import APIRouter, HTTPException, Depends, status
from app.auth import get_current_user
from app.database import get_db_connection
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

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
    return {
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
                "variable_telemetria": "I_gneral",
                "potencia_activa_kw": 345.2,
                "consumo_hoy_kwh": 4120.0,
                "factor_potencia": 0.96,
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
            }
        }
    }


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
