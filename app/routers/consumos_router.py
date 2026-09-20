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
