from fastapi import APIRouter, HTTPException, Depends, status
from app.auth import get_current_user
from app.database import get_db_connection
from app.turnos_sync import get_cached_turnos, sync_turnos_from_server_1

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
    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    
    nombre_turno = turno_act.get("nombre") or "Turno Activo"
    horario_turno = f"{turno_act.get('hora_inicio', '06:00')} - {turno_act.get('hora_fin', '14:00')}"

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
                "icono": "fa-circle-notch",
                "oee": 91.2,
                "clickable": True,
                "dashboard_url": "#tunel_lavado",
                "turno_info": {
                    "nombre": nombre_turno,
                    "horario": horario_turno
                },
                "subtitulo_resumen": "Resumen turno actual",
                "indicadores_turno": {
                    "promedio_carga": "52.4 kg",
                    "promedio_tiempo_carga": "2.1 min",
                    "cantidad_cargas": "38 cargas"
                },
                "metricas_clave": [],
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
                "clickable": False,
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
                "clickable": False,
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
                "clickable": False,
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

@router.get("/tunel-lavado/dashboard")
def get_tunel_lavado_dashboard(user: dict = Depends(check_produccion_permission)):
    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    
    nombre_turno = turno_act.get("nombre") or "Turno Mañana"
    horario_turno = f"{turno_act.get('hora_inicio', '06:00')} - {turno_act.get('hora_fin', '14:00')}"
    progreso_turno = turno_act.get("progreso_porcentaje") or 68.5

    return {
        "maquina": "TÚNEL DE LAVADO",
        "planta": "ELIS NÁJERA 4.0",
        "estado": "Operativa",
        "oee": 91.2,
        "sync_info": {
            "origen": "Jetson Server 1 (192.168.0.137:5001)",
            "cache_actualizado": turnos_cache.get("cache_updated_at", "Reciente"),
            "frecuencia_sync": "Cada 30 minutos (Cache Local SQLite)"
        },
        "turno_activo": {
            "nombre": nombre_turno,
            "horario": horario_turno,
            "progreso_porcentaje": progreso_turno,
            "minutos_transcurridos": turno_act.get("minutos_transcurridos", 240)
        },
        "indicadores_destacados": {
            "kg_totales_turno": {
                "titulo": "Kg Totales Turno",
                "valor": "14.280 kg",
                "subtexto": "Objetivo Turno: 16.000 kg",
                "color_gradiente": "linear-gradient(135deg, #0284c7 0%, #06b6d4 100%)",
                "icono": "fa-weight-hanging"
            },
            "cargas_totales_turno": {
                "titulo": "Cargas Totales Turno",
                "valor": "272 cargas",
                "subtexto": "Promedio: 52.5 kg/carga",
                "color_gradiente": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                "icono": "fa-boxes"
            },
            "kpi_productividad_iprod": {
                "titulo": "KPI Productividad (iProd)",
                "valor": "1,45 Tn/h",
                "subtexto": "Índice iProd: 94.8% (Excelente)",
                "color_gradiente": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                "icono": "fa-chart-line"
            }
        },
        "telemetria_adicional": [
            {"parametro": "Tiempo Medio por Carga", "valor": "2,1 min", "estado": "Óptimo"},
            {"parametro": "Temperatura de Lavado", "valor": "74,5 °C", "estado": "Estable"},
            {"parametro": "Presión Deshidratado Prensa", "valor": "44,0 bar", "estado": "Normal"},
            {"parametro": "Inyección Química Activa", "valor": "4,2 L/min", "estado": "Correcto"}
        ]
    }

@router.post("/turnos/force-sync")
def force_turnos_sync(admin: dict = Depends(check_produccion_permission)):
    success = sync_turnos_from_server_1()
    return {"status": "success" if success else "warning", "synced": success}
