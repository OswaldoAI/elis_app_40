from fastapi import APIRouter, HTTPException, Depends, status
from app.auth import get_current_user
from app.database import get_db_connection

router = APIRouter(prefix="/api/consumos", tags=["Consumos"])

def check_consumos_permission(current_user: dict = Depends(get_current_user)):
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
                "caudal_m3h": 18.5,
                "consumo_hoy_m3": 210.4,
                "reciclaje_pct": 42.0,
                "icono": "fa-water",
                "color": "blue"
            },
            "gas_general": {
                "titulo": "Gas General",
                "consumo_hoy_m3": 1540.0,
                "presion_vapor_bar": 9.2,
                "eficiencia_caldera_pct": 92.4,
                "icono": "fa-fire",
                "color": "orange"
            },
            "energia_electrica": {
                "titulo": "Energía Eléctrica",
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
                "consumo_m3h": 32.5,
                "consumo_hoy_m3": 260.0,
                "temp_secado_c": 118.0,
                "icono": "fa-wind",
                "color": "orange"
            },
            "gas_calandra_1": {
                "titulo": "Gas Calandra 1",
                "consumo_m3h": 45.0,
                "consumo_hoy_m3": 360.0,
                "temp_trabajo_c": 175.0,
                "icono": "fa-scroll",
                "color": "orange"
            },
            "gas_calandra_2": {
                "titulo": "Gas Calandra 2",
                "consumo_m3h": 42.8,
                "consumo_hoy_m3": 342.4,
                "temp_trabajo_c": 175.0,
                "icono": "fa-scroll",
                "color": "orange"
            },
            "gas_calandra_3": {
                "titulo": "Gas Calandra 3",
                "consumo_m3h": 48.2,
                "consumo_hoy_m3": 385.6,
                "temp_trabajo_c": 180.0,
                "icono": "fa-eye",
                "color": "orange"
            }
        },
        "desglose_electricidad": {
            "elec_tunel": {
                "titulo": "Electricidad Túnel",
                "potencia_kw": 85.4,
                "consumo_hoy_kwh": 1024.8,
                "icono": "fa-circle-notch",
                "color": "amber"
            },
            "elec_calandra_1": {
                "titulo": "Electricidad Calandra 1",
                "potencia_kw": 42.1,
                "consumo_hoy_kwh": 505.2,
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_calandra_2": {
                "titulo": "Electricidad Calandra 2",
                "potencia_kw": 39.8,
                "consumo_hoy_kwh": 477.6,
                "icono": "fa-scroll",
                "color": "amber"
            },
            "elec_calandra_3": {
                "titulo": "Electricidad Calandra 3",
                "potencia_kw": 46.5,
                "consumo_hoy_kwh": 558.0,
                "icono": "fa-eye",
                "color": "amber"
            }
        },
        # Claves para retrocompatibilidad
        "electricidad": {
            "potencia_activa_kw": 345.2,
            "consumo_hoy_kwh": 4120.0,
            "factor_potencia": 0.96,
            "estado": "Normal"
        },
        "agua": {
            "caudal_m3h": 18.5,
            "consumo_hoy_m3": 210.4,
            "reciclaje_porcentaje": 42.0,
            "temperatura_entrada": 15.2
        },
        "gas_vapor": {
            "presion_vapor_bar": 9.2,
            "consumo_gas_hoy_m3": 1540.0,
            "temp_caldera": 178.5,
            "eficiencia_caldera": 92.4
        }
    }


from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AguaIngestaPayload(BaseModel):
    pulsos: int
    caudal_m3h: Optional[float] = 0.0
    dispositivo: Optional[str] = "Contador Pulsos Agua 192.168.0.116:3000"
    timestamp: Optional[str] = None


@router.get("/agua-tunel/telemetria")
def get_agua_tunel_telemetria(
    fecha_inicio: Optional[str] = None,
    hora_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    hora_fin: Optional[str] = None,
    user: dict = Depends(check_consumos_permission)
):
    """Consulta la telemetría de Agua Túnel y Lavadoras (0.1 m3/pulso) con filtros por rango de fecha/hora."""
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
        SELECT id, variable, timestamp, timestamp_iso, pulsos, volumen_m3, caudal_m3h, dispositivo, created_at
        FROM agua_tunel_telemetria
        WHERE timestamp_iso >= ? AND timestamp_iso <= ?
        ORDER BY timestamp_iso DESC
    """, (start_iso, end_iso)).fetchall()

    total_agg = conn.execute("""
        SELECT 
            COALESCE(SUM(pulsos), 0) as total_pulsos,
            COALESCE(SUM(volumen_m3), 0) as total_volumen
        FROM agua_tunel_telemetria
        WHERE timestamp_iso >= ? AND timestamp_iso <= ?
    """, (start_iso, end_iso)).fetchone()
    conn.close()

    total_pulsos = total_agg["total_pulsos"] if total_agg else 0
    acumulado_m3 = round(total_agg["total_volumen"], 2) if total_agg else 0.0

    registros = []
    for r in rows:
        registros.append({
            "id": r["id"],
            "variable": r["variable"],
            "timestamp": r["timestamp"],
            "timestamp_iso": r["timestamp_iso"],
            "pulsos": r["pulsos"],
            "volumen_m3": round(r["volumen_m3"], 2),
            "caudal_m3h": round(r["caudal_m3h"], 1),
            "dispositivo": r["dispositivo"]
        })

    return {
        "variable": "AGUA_TUNEL_LAVADORAS",
        "factor_conversion": "1 pulso = 0.1 m3 (100 Litros)",
        "acumulado_m3": acumulado_m3,
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


@router.post("/agua-tunel/ingesta")
def registrar_ingesta_agua(
    payload: AguaIngestaPayload,
    user: dict = Depends(check_consumos_permission)
):
    """Registra una lectura de pulso de Agua Túnel y Lavadoras (1 pulso = 0.1 m3)."""
    now_dt = datetime.now()
    timestamp_str = payload.timestamp or now_dt.strftime("%d/%m/%Y %H:%M:%S")
    timestamp_iso = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    volumen_m3 = round(payload.pulsos * 0.1, 2)
    caudal_m3h = float(payload.caudal_m3h or 0.0)
    dispositivo = payload.dispositivo or "Contador Pulsos Agua 192.168.0.116:3000"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agua_tunel_telemetria (variable, timestamp, timestamp_iso, pulsos, volumen_m3, caudal_m3h, dispositivo)
        VALUES ('AGUA_TUNEL_LAVADORAS', ?, ?, ?, ?, ?, ?)
    """, (timestamp_str, timestamp_iso, payload.pulsos, volumen_m3, caudal_m3h, dispositivo))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "pulsos": payload.pulsos,
        "volumen_m3": volumen_m3,
        "caudal_m3h": caudal_m3h,
        "timestamp_iso": timestamp_iso
    }
