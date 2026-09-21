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
