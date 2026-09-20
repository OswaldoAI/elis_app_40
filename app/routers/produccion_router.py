from fastapi import APIRouter, HTTPException, Depends, status
from app.auth import get_current_user
from app.database import get_db_connection

router = APIRouter(prefix="/api/produccion", tags=["Producción"])

def check_produccion_permission(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    perm = conn.execute("""
        SELECT can_view FROM role_permissions WHERE role = ? AND module_code = 'produccion'
    """, (current_user["role"],)).fetchone()
    conn.close()

    if not perm or not perm["can_view"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para acceder al módulo de Producción"
        )
    return current_user

@router.get("/summary")
def get_produccion_summary(user: dict = Depends(check_produccion_permission)):
    return {
        "status": "online",
        "planta": "ELIS NÁJERA 4.0",
        "lineas_activas": 4,
        "kilos_lavados_hoy": 14280,
        "objetivo_diario": 18000,
        "eficiencia_global_oee": 87.5,
        "prendas_procesadas": 28500,
        "lineas": [
            {"id": "L1", "nombre": "Lavadora Industrial Túnel 1", "estado": "Operativa", "velocidad": "1200 kg/h", "temperatura": "72°C"},
            {"id": "L2", "nombre": "Lavadora Industrial Túnel 2", "estado": "Operativa", "velocidad": "1150 kg/h", "temperatura": "70°C"},
            {"id": "L3", "nombre": "Prensa Deshidratadora P3", "estado": "Operativa", "presion": "42 bar", "ciclo": "Normal"},
            {"id": "L4", "nombre": "Secadoras Continuas S1-S4", "estado": "Operativa", "temp_secado": "85°C", "humedad_res": "3%"}
        ]
    }
