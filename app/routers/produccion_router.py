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
        "kilos_lavados_hoy": 14280,
        "objetivo_diario": 18000,
        "eficiencia_global_oee": 89.85,
        "maquinas": [
            {
                "id": "TUNEL_LAVADO",
                "nombre": "TÚNEL DE LAVADO",
                "tipo": "Lavado Continuo Industrial",
                "estado": "Operativa",
                "icono": "fa-water",
                "oee": 91.2,
                "metricas_clave": [
                    {"label": "Rendimiento", "val": "1.250 kg/h"},
                    {"label": "Temp. Agua", "val": "74,5 °C"},
                    {"label": "Presión Prensa", "val": "44 bar"},
                    {"label": "Dosis Detergente", "val": "4.2 L/min"}
                ],
                "progreso_carga": 85,
                "programa_actual": "Prog 04 - Sábanas y Mantelería Hostelería"
            },
            {
                "id": "TUNEL_VT",
                "nombre": "TÚNEL VT",
                "tipo": "Secado y Oreado Continuo VT",
                "estado": "Operativa",
                "icono": "fa-wind",
                "oee": 88.7,
                "metricas_clave": [
                    {"label": "Rendimiento", "val": "1.100 kg/h"},
                    {"label": "Temp. Secado", "val": "118 °C"},
                    {"label": "Humedad Residual", "val": "2,8 %"},
                    {"label": "Caudal Aire", "val": "3.400 m³/h"}
                ],
                "progreso_carga": 78,
                "programa_actual": "Prog 02 - Secado Rápido VT High-Speed"
            },
            {
                "id": "CALANDRA_2",
                "nombre": "CALANDRA 2",
                "tipo": "Planchado y Plegado Automático",
                "estado": "Operativa",
                "icono": "fa-scroll",
                "oee": 86.4,
                "metricas_clave": [
                    {"label": "Velocidad", "val": "28 m/min"},
                    {"label": "Procesamiento", "val": "1.450 prendas/h"},
                    {"label": "Temp. Rodillo", "val": "175 °C"},
                    {"label": "Presión Vapor", "val": "8,8 bar"}
                ],
                "progreso_carga": 90,
                "programa_actual": "Plegado Automático 3 Pliegues"
            },
            {
                "id": "CALANDRA_3",
                "nombre": "CALANDRA 3",
                "tipo": "Planchado & Inspección Óptica IA",
                "estado": "Operativa",
                "icono": "fa-eye",
                "oee": 93.1,
                "metricas_clave": [
                    {"label": "Velocidad", "val": "32 m/min"},
                    {"label": "Procesamiento", "val": "1.680 prendas/h"},
                    {"label": "Temp. Rodillo", "val": "180 °C"},
                    {"label": "Inspección IA", "val": "99.4% Conforme"}
                ],
                "progreso_carga": 94,
                "programa_actual": "Control Calidad Óptico Calandra 3 (Port 5000)"
            }
        ]
    }
