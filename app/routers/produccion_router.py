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

from datetime import datetime, timedelta

def calculate_tunel_metrics(turno_act: dict = None):
    """Calcula indicadores reales agregados filtrando estrictamente por el turno activo de Jetson Server 1."""
    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})

    fecha = turno_act.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora_inicio = turno_act.get("hora_inicio", "06:00")
    hora_fin = turno_act.get("hora_fin", "14:00")
    minutos_transcurridos = float(turno_act.get("minutos_transcurridos") or 240)

    start_iso = f"{fecha} {hora_inicio}:00"
    
    # Manejo de turnos que cruzan medianoche (ej. 21:00 a 02:00)
    try:
        h_start = int(hora_inicio.split(":")[0])
        h_end = int(hora_fin.split(":")[0])
        if h_end < h_start:
            end_date = (datetime.strptime(fecha, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            end_iso = f"{end_date} {hora_fin}:00"
        else:
            end_iso = f"{fecha} {hora_fin}:00"
    except Exception:
        end_iso = f"{fecha} {hora_fin}:00"

    try:
        conn = get_db_connection()
        row = conn.execute("""
            SELECT 
                COUNT(*) as total_cargas,
                COALESCE(AVG(peso_kg), 0) as promedio_peso,
                COALESCE(AVG(tiempo_entre_cargas_seg), 0) as promedio_tiempo_seg,
                COALESCE(SUM(peso_kg), 0) as total_kg
            FROM tunel_cargas
            WHERE (timestamp_iso >= ? AND timestamp_iso <= ?)
               OR (timestamp >= ? AND timestamp <= ?)
        """, (start_iso, end_iso, start_iso, end_iso)).fetchone()
        conn.close()

        total_cargas = row["total_cargas"] if row else 0
        
        if total_cargas > 0:
            promedio_peso = round(row["promedio_peso"], 1)
            promedio_tiempo_seg = round(row["promedio_tiempo_seg"])
            promedio_tiempo_min = round(promedio_tiempo_seg / 60.0, 1)
            total_kg = round(row["total_kg"], 1)

            # Productividad Tn/h basada en el tiempo transcurrido del turno activo
            horas_trans = max(minutos_transcurridos / 60.0, 0.2)
            iprod_tnh = round((total_kg / 1000.0) / horas_trans, 2)

            return {
                "is_real": True,
                "cantidad_cargas": f"{total_cargas} cargas",
                "cargas_num": total_cargas,
                "promedio_carga": f"{promedio_peso} kg",
                "promedio_peso_num": promedio_peso,
                "promedio_tiempo_carga": f"{promedio_tiempo_min} min ({promedio_tiempo_seg}s)",
                "promedio_tiempo_seg": promedio_tiempo_seg,
                "kg_totales_turno": f"{int(total_kg):,} kg".replace(",", "."),
                "total_kg_num": total_kg,
                "iprod": f"{iprod_tnh} Tn/h",
                "iprod_num": iprod_tnh
            }
    except Exception as e:
        print(f"Error consultando tunel_cargas por turno: {e}")

    # Fallback si no hay cargas en el turno activo en curso
    return {
        "is_real": False,
        "cantidad_cargas": "0 cargas",
        "cargas_num": 0,
        "promedio_carga": "0.0 kg",
        "promedio_peso_num": 0.0,
        "promedio_tiempo_carga": "0 min",
        "promedio_tiempo_seg": 0,
        "kg_totales_turno": "0 kg",
        "total_kg_num": 0,
        "iprod": "0,00 Tn/h",
        "iprod_num": 0.0
    }


@router.get("/summary")
def get_produccion_summary(user: dict = Depends(check_produccion_permission)):
    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    
    nombre_turno = turno_act.get("nombre") or "Turno Activo"
    horario_turno = f"{turno_act.get('hora_inicio', '06:00')} - {turno_act.get('hora_fin', '14:00')}"

    tunel_kpis = calculate_tunel_metrics(turno_act)


    return {
        "status": "online",
        "planta": "ELIS NÁJERA 4.0",
        "kilos_lavados_hoy": int(tunel_kpis["total_kg_num"]),
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
                    "promedio_carga": tunel_kpis["promedio_carga"],
                    "promedio_tiempo_carga": tunel_kpis["promedio_tiempo_carga"],
                    "cantidad_cargas": tunel_kpis["cantidad_cargas"]
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

    tunel_kpis = calculate_tunel_metrics(turno_act)


    return {
        "maquina": "TÚNEL DE LAVADO",
        "planta": "ELIS NÁJERA 4.0",
        "estado": "Operativa",
        "oee": 91.2,
        "sync_info": {
            "origen": "MQTT Mosquitto (192.168.0.116:1883) | Turnos Jetson Server 1",
            "cache_actualizado": turnos_cache.get("cache_updated_at", "Reciente"),
            "frecuencia_sync": "Tiempo Real MQTT + Polling 30m Turnos"
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
                "valor": tunel_kpis["kg_totales_turno"],
                "subtexto": f"Objetivo Turno: 16.000 kg ({'Real MQTT' if tunel_kpis['is_real'] else 'Simulado'})",
                "color_gradiente": "linear-gradient(135deg, #0284c7 0%, #06b6d4 100%)",
                "icono": "fa-weight-hanging"
            },
            "cargas_totales_turno": {
                "titulo": "Cargas Totales Turno",
                "valor": tunel_kpis["cantidad_cargas"],
                "subtexto": f"Promedio: {tunel_kpis['promedio_carga']}/carga",
                "color_gradiente": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                "icono": "fa-boxes"
            },
            "kpi_productividad_iprod": {
                "titulo": "KPI Productividad (iProd)",
                "valor": tunel_kpis["iprod"],
                "subtexto": f"Tiempo prom: {tunel_kpis['promedio_tiempo_carga']}",
                "color_gradiente": "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                "icono": "fa-chart-line"
            }
        }
    }

@router.post("/turnos/force-sync")
def force_turnos_sync(admin: dict = Depends(check_produccion_permission)):
    success = sync_turnos_from_server_1()
    return {"status": "success" if success else "warning", "synced": success}

