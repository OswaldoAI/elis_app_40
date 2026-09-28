from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional
import json
from app.auth import get_current_user
from app.database import get_db_connection
from app.turnos_sync import get_cached_turnos, sync_turnos_from_server_1

router = APIRouter(prefix="/api/produccion", tags=["Producción"])

def check_produccion_permission(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") == "Invitado":
        return current_user

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
from app.utils import get_local_now_str, get_local_now

def get_current_jornada_date(dt=None) -> str:
    """
    Calcula la fecha de la jornada industrial.
    Cronológicamente la jornada abarca desde las 05:00 AM de un día hasta las 05:00 AM del día siguiente.
    Si la hora actual es antes de las 05:00 AM, pertenece a la jornada de ayer.
    """
    if dt is None:
        dt = get_local_now().replace(tzinfo=None)
    if dt.hour < 5:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")

def get_shift_start_end_iso(fecha: str, hora_inicio: str, hora_fin: str) -> tuple[str, str]:
    """
    Calcula start_iso y end_iso de un turno dentro de la jornada definida (05:00 a 05:00+1).
    Permite hasta 4 turnos por jornada, manejando cruces de medianoche y turnos de madrugada.
    """
    base_dt = datetime.strptime(fecha, "%Y-%m-%d")
    next_date_str = (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        h_start = int(hora_inicio.split(":")[0])
        h_end = int(hora_fin.split(":")[0])
    except Exception:
        h_start, h_end = 6, 14

    # Si la hora de inicio es menor que las 05:00, pertenece a la madrugada del día siguiente dentro de la misma jornada
    if h_start < 5:
        start_date_str = next_date_str
    else:
        start_date_str = fecha

    # Si la hora de fin es menor o igual que la de inicio, o si el inicio ya era de madrugada
    if h_end <= h_start or h_start < 5:
        end_date_str = next_date_str
    else:
        end_date_str = fecha

    start_iso = f"{start_date_str} {hora_inicio}:00"
    end_iso = f"{end_date_str} {hora_fin}:00"
    return start_iso, end_iso

def get_jornada_shifts_template() -> list[dict]:
    """Retorna los 4 posibles turnos de una jornada completa."""
    turnos_cache = get_cached_turnos()
    cached_shifts = turnos_cache.get("shifts") or []
    
    # Plantilla base de los 4 turnos posibles por jornada
    default_shifts = [
        {"nombre": "Turno 1", "hora_inicio": "06:00", "hora_fin": "14:00"},
        {"nombre": "Turno 2", "hora_inicio": "14:00", "hora_fin": "21:00"},
        {"nombre": "Turno 3", "hora_inicio": "21:00", "hora_fin": "02:00"},
        {"nombre": "Turno 4", "hora_inicio": "02:00", "hora_fin": "06:00"}
    ]
    
    if cached_shifts:
        merged = []
        for s in cached_shifts:
            merged.append({
                "nombre": s.get("name") or s.get("nombre"),
                "hora_inicio": s.get("start") or s.get("hora_inicio"),
                "hora_fin": s.get("end") or s.get("hora_fin")
            })
        for ds in default_shifts:
            if not any(m["nombre"] == ds["nombre"] for m in merged):
                merged.append(ds)
        return merged[:4]
    
    return default_shifts

def calculate_tunel_metrics(turno_act: dict = None):
    """Calcula indicadores reales agregados filtrando strictly por el turno activo o especificado."""
    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})

    fecha = turno_act.get("fecha") or get_current_jornada_date()
    hora_inicio = turno_act.get("hora_inicio", "06:00")
    hora_fin = turno_act.get("hora_fin", "14:00")
    
    start_iso, end_iso = get_shift_start_end_iso(fecha, hora_inicio, hora_fin)

    now_dt = get_local_now().replace(tzinfo=None)
    try:
        dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
        if now_dt >= dt_end:
            # Turno pasado y completado: los minutos transcurridos son exactamente la duración del turno
            minutos_transcurridos = max((dt_end - dt_start).total_seconds() / 60.0, 1.0)
        elif now_dt >= dt_start:
            # Turno activo en curso
            calc_min = (now_dt - dt_start).total_seconds() / 60.0
            minutos_transcurridos = max(calc_min, 1.0)
        else:
            minutos_transcurridos = float(turno_act.get("minutos_transcurridos") or 1.0)
    except Exception:
        minutos_transcurridos = float(turno_act.get("minutos_transcurridos") or 240)

    try:
        conn = get_db_connection()
        row = conn.execute("""
            SELECT 
                COUNT(*) as total_cargas,
                COALESCE(AVG(peso_kg), 0) as promedio_peso,
                COALESCE(AVG(tiempo_entre_cargas_seg), 0) as promedio_tiempo_seg,
                COALESCE(SUM(peso_kg), 0) as total_kg,
                COUNT(DISTINCT cliente) as clientes_unicos,
                COUNT(DISTINCT categoria) as programas_unicos
            FROM tunel_cargas
            WHERE timestamp_iso >= ? AND timestamp_iso <= ?
        """, (start_iso, end_iso)).fetchone()
        
        # Generar desglose horario desde inicio hasta fin del turno activo para la gráfica de avance
        try:
            dt_curr = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
            dt_end_obj = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
        except Exception:
            dt_curr = datetime.now()
            dt_end_obj = dt_curr + timedelta(hours=8)

        grafica_labels = []
        grafica_kg_hora = []
        grafica_kg_acumulado = []
        grafica_cargas_hora = []

        running_kg = 0.0

        while dt_curr < dt_end_obj:
            dt_next = dt_curr + timedelta(hours=1)
            h_start_str = dt_curr.strftime("%Y-%m-%d %H:%M:%S")
            h_end_str = dt_next.strftime("%Y-%m-%d %H:%M:%S")
            # Formato de intervalo para la barra (ej: "06:00 - 07:00")
            label_str = f"{dt_curr.strftime('%H:%M')} - {dt_next.strftime('%H:%M')}"
            
            row_h = conn.execute("""
                SELECT 
                    COUNT(*) as num_cargas,
                    COALESCE(SUM(peso_kg), 0) as kg_hora
                FROM tunel_cargas
                WHERE timestamp_iso >= ? AND timestamp_iso < ?
            """, (h_start_str, h_end_str)).fetchone()
            
            kg_val = round(row_h["kg_hora"], 1) if row_h else 0.0
            cargas_val = row_h["num_cargas"] if row_h else 0
            running_kg += kg_val

            grafica_labels.append(label_str)
            grafica_kg_hora.append(kg_val)
            grafica_kg_acumulado.append(round(running_kg, 1))
            grafica_cargas_hora.append(cargas_val)

            dt_curr = dt_next

        # No se incluye etiqueta de cierre final (ej: 14:00) para evitar puntos sobrantes sin cargas
        conn.close()

        total_cargas = row["total_cargas"] if row else 0
        clientes_unicos = row["clientes_unicos"] if row and row["clientes_unicos"] else 0
        programas_unicos = row["programas_unicos"] if row and row["programas_unicos"] else 0
        
        if total_cargas > 0:
            promedio_peso = round(row["promedio_peso"], 1)
            promedio_tiempo_seg = round(row["promedio_tiempo_seg"])
            promedio_tiempo_min = round(promedio_tiempo_seg / 60.0, 2)
            total_kg = round(row["total_kg"], 1)

            # Productividad hProd (kg/h)
            horas_trans = max(minutos_transcurridos / 60.0, 0.2)
            hprod_kgh = int(round(total_kg / horas_trans))
            hprod_str = f"{hprod_kgh:,} kg/h".replace(",", ".")

            # Indicador ikProd: (Promedio Kgs / Promedio Tiempos min)
            ikprod_neto = round(promedio_peso / max(promedio_tiempo_min, 0.01), 2)
            ikprod_pct = round((ikprod_neto / 30.0) * 100.0, 1)

            # Rango de color ikProd: Rojo (<30%), Naranja (30-60%), Verde (>60%)
            if ikprod_pct < 30.0:
                color_code = "red"
                gradient = "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)"
                subtexto_color = "#f87171"
                text_color = "#ef4444"
                border_color = "#ef4444"
            elif 30.0 <= ikprod_pct <= 60.0:
                color_code = "orange"
                gradient = "linear-gradient(135deg, #ea580c 0%, #c2410c 100%)"
                subtexto_color = "#fb923c"
                text_color = "#f97316"
                border_color = "#f97316"
            else:
                color_code = "green"
                gradient = "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                subtexto_color = "#6ee7b7"
                text_color = "#34d399"
                border_color = "#10b981"

            conn = get_db_connection()
            last_carga = conn.execute("SELECT cliente, categoria, peso_kg, timestamp FROM tunel_cargas ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()

            last_prog_str = f"Categoría #{last_carga['categoria']} — Cliente #{last_carga['cliente']} (Carga: {last_carga['peso_kg']} kg)" if last_carga else "Prog 04 - Sábanas y Mantelería Hostelería"

            return {
                "is_real": True,
                "cantidad_cargas": f"{total_cargas} cargas",
                "cargas_num": total_cargas,
                "clientes_unicos": clientes_unicos,
                "programas_unicos": programas_unicos,
                "promedio_carga": f"{promedio_peso} kg",
                "promedio_peso_num": promedio_peso,
                "promedio_tiempo_carga": f"{round(promedio_tiempo_min, 1)} min ({promedio_tiempo_seg}s)",
                "promedio_tiempo_seg": promedio_tiempo_seg,
                "kg_totales_turno": f"{int(total_kg):,} kg".replace(",", "."),
                "total_kg_num": total_kg,
                "hprod": hprod_str,
                "hprod_num": hprod_kgh,
                "grafica_labels": grafica_labels,
                "grafica_kg_hora": grafica_kg_hora,
                "grafica_kg_acumulado": grafica_kg_acumulado,
                "grafica_cargas_hora": grafica_cargas_hora,
                "ikprod": {
                    "pct": ikprod_pct,
                    "pct_str": f"{ikprod_pct}%",
                    "neto": ikprod_neto,
                    "neto_str": f"ikProd Neto: {ikprod_neto:.2f}",
                    "tprom_str": f"Tprom: {round(promedio_tiempo_min, 1)} min ({promedio_tiempo_seg}s)",
                    "formula_str": "Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%",
                    "color_code": color_code,
                    "gradient": gradient,
                    "subtexto_color": subtexto_color,
                    "text_color": text_color,
                    "border_color": border_color
                },
                "programa_actual": last_prog_str
            }
    except Exception as e:
        print(f"Error consultando tunel_cargas por turno: {e}")

    # Fallback si no hay cargas en el turno activo en curso
    return {
        "is_real": False,
        "cantidad_cargas": "0 cargas",
        "cargas_num": 0,
        "clientes_unicos": 0,
        "programas_unicos": 0,
        "promedio_carga": "0.0 kg",
        "promedio_peso_num": 0.0,
        "promedio_tiempo_carga": "0 min",
        "promedio_tiempo_seg": 0,
        "kg_totales_turno": "0 kg",
        "total_kg_num": 0,
        "hprod": "0 kg/h",
        "hprod_num": 0,
        "grafica_labels": ["06:00 - 07:00", "07:00 - 08:00", "08:00 - 09:00", "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "12:00 - 13:00", "13:00 - 14:00"],
        "grafica_kg_hora": [0.0]*8,
        "grafica_kg_acumulado": [0.0]*8,
        "grafica_cargas_hora": [0]*8,
        "ikprod": {
            "pct": 0.0,
            "pct_str": "0.0%",
            "neto": 0.0,
            "neto_str": "ikProd Neto: 0.00",
            "tprom_str": "Tprom: 0 min (0s)",
            "formula_str": "Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%",
            "color_code": "red",
            "gradient": "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)",
            "subtexto_color": "#f87171",
            "text_color": "#ef4444",
            "border_color": "#ef4444"
        },
        "programa_actual": "Sin cargas registradas aún"
    }


@router.get("/summary")
def get_produccion_summary(user: dict = Depends(check_produccion_permission)):
    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    
    nombre_turno = turno_act.get("nombre") or "Turno Activo"
    
    fecha_raw = turno_act.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    try:
        fecha_formateada = datetime.strptime(fecha_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_formateada = datetime.now().strftime("%d/%m/%Y")

    horario_base = f"{turno_act.get('hora_inicio', '06:00')} - {turno_act.get('hora_fin', '14:00')}"
    horario_con_fecha = f"{horario_base} | {fecha_formateada}"

    tunel_kpis = calculate_tunel_metrics(turno_act)
    cal2_data = get_calandra_production("CALANDRA_2", turno_act)
    cal3_data = get_calandra_production("CALANDRA_3", turno_act)

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
                    "horario": horario_con_fecha,
                    "fecha": fecha_formateada
                },
                "subtitulo_resumen": "Resumen turno actual",
                "indicadores_turno": {
                    "promedio_carga": tunel_kpis["promedio_carga"],
                    "kgs_totales": tunel_kpis["kg_totales_turno"],
                    "ikprod": tunel_kpis["ikprod"]["pct_str"],
                    "ikprod_details": tunel_kpis["ikprod"],
                    "promedio_tiempo_carga": tunel_kpis["promedio_tiempo_carga"],
                    "cantidad_cargas": tunel_kpis["cantidad_cargas"]
                },
                "metricas_clave": [],
                "progreso_carga": 85,
                "programa_actual": tunel_kpis.get("programa_actual", "Prog 04 - Sábanas y Mantelería Hostelería")
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
                "estado": ("En Tiempo Valle" if cal2_data["en_valle"] else "Operativa") if cal2_data.get("is_turno_activo") else "Sin Turno Activo",
                "icono": "fa-scroll",
                "oee": 86.4,
                "clickable": True,
                "dashboard_url": "#calandra_2",
                "turno_info": {
                    "nombre": nombre_turno if cal2_data.get("is_turno_activo") else "Sin Turno Activo",
                    "horario": horario_con_fecha if cal2_data.get("is_turno_activo") else f"Fuera de Turno | {fecha_formateada}",
                    "fecha": fecha_formateada,
                    "is_active": cal2_data.get("is_turno_activo", False)
                },
                "produccion_calandra": cal2_data,
                "progreso_carga": 90,
                "programa_actual": "Plegado Automático 3 Pliegues" if cal2_data.get("is_turno_activo") else "Sin Turno en Proceso"
            },
            {
                "id": "CALANDRA_3",
                "nombre": "CALANDRA 3",
                "tipo": "Planchado & Inspección Óptica IA",
                "estado": ("En Tiempo Valle" if cal3_data["en_valle"] else "Operativa") if cal3_data.get("is_turno_activo") else "Sin Turno Activo",
                "icono": "fa-eye",
                "oee": 93.1,
                "clickable": True,
                "dashboard_url": "#calandra_3",
                "turno_info": {
                    "nombre": nombre_turno if cal3_data.get("is_turno_activo") else "Sin Turno Activo",
                    "horario": horario_con_fecha if cal3_data.get("is_turno_activo") else f"Fuera de Turno | {fecha_formateada}",
                    "fecha": fecha_formateada,
                    "is_active": cal3_data.get("is_turno_activo", False)
                },
                "produccion_calandra": cal3_data,
                "progreso_carga": 94,
                "programa_actual": "Control Calidad Óptico Calandra 3 (Port 5000)" if cal3_data.get("is_turno_activo") else "Sin Turno en Proceso"
            }
        ]
    }

def is_shift_active(turno_act: dict = None) -> bool:
    """Verifica si actualmente hay un turno en proceso en planta."""
    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})
    if not turno_act:
        return False
    if turno_act.get("is_active") is False:
        return False
    nombre = str(turno_act.get("nombre") or "").upper()
    if "FUERA DE TURNO" in nombre or "SIN TURNO" in nombre or "INACTIVO" in nombre:
        return False

    fecha = turno_act.get("fecha")
    hora_inicio = turno_act.get("hora_inicio")
    hora_fin = turno_act.get("hora_fin")
    if not fecha or not hora_inicio or not hora_fin:
        return False

    try:
        start_iso, end_iso = get_shift_start_end_iso(fecha, hora_inicio, hora_fin)
        now_str = get_local_now_str()
        return start_iso <= now_str <= end_iso
    except Exception:
        return False

@router.get("/turnos/sync-status")
def get_turnos_sync_status(user: dict = Depends(check_produccion_permission)):
    """Informa sobre el estado de la sincronización de turnos desde http://100.127.85.111:5001."""
    cached = get_cached_turnos()
    return {
        "status": "success",
        "fuente_principal": "http://100.127.85.111:5001",
        "intervalo_sincronizacion_seg": 1800,
        "intervalo_sincronizacion_min": 30,
        "cache_actualizado_el": cached.get("cache_updated_at"),
        "sincronizado_desde": cached.get("synced_from_url") or "http://100.127.85.111:5001",
        "jornada": cached.get("jornada"),
        "turno_actual": cached.get("turno_actual"),
        "is_shift_active": is_shift_active(cached.get("turno_actual", {})),
        "turnos_jornada": cached.get("shifts", [])
    }

@router.post("/turnos/sync-now")
def trigger_turnos_sync_now(user: dict = Depends(check_produccion_permission)):
    """Fuerza una sincronización inmediata desde la aplicación de turnos (http://100.127.85.111:5001)."""
    ok = sync_turnos_from_server_1()
    cached = get_cached_turnos()
    return {
        "status": "success" if ok else "warning",
        "message": "Turnos sincronizados correctamente desde http://100.127.85.111:5001" if ok else "No se pudo contactar http://100.127.85.111:5001, usando caché",
        "timestamp": get_local_now_str(),
        "turno_actual": cached.get("turno_actual"),
        "turnos_jornada": cached.get("shifts", [])
    }

@router.get("/calandras/live")
def get_calandras_live_data(user: dict = Depends(check_produccion_permission)):
    """Retorna las métricas instantáneas y gráficas hora a hora de Calandra 2 y Calandra 3."""
    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    return {
        "status": "success",
        "timestamp": get_local_now_str(),
        "calandra_2": get_calandra_production("CALANDRA_2", turno_act),
        "calandra_3": get_calandra_production("CALANDRA_3", turno_act)
    }

@router.get("/calandras/{maquina_id}/dashboard")
def get_calandra_dashboard(maquina_id: str, user: dict = Depends(check_produccion_permission)):
    """Retorna los datos completos para el Dashboard Ampliado de Calandra 2 o Calandra 3."""
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    shift_active = is_shift_active(turno_act)

    nombre_turno = turno_act.get("nombre") or "Turno Activo"
    fecha_raw = turno_act.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    try:
        fecha_formateada = datetime.strptime(fecha_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_formateada = datetime.now().strftime("%d/%m/%Y")

    horario_base = f"{turno_act.get('hora_inicio', '06:00')} - {turno_act.get('hora_fin', '14:00')}"
    horario_con_fecha = f"{horario_base} | {fecha_formateada}"

    prod = get_calandra_production(m_id, turno_act)

    if shift_active:
        try:
            cal_pkg = build_calandra_shift_json(m_id, fecha_raw, turno_act)
            save_calandra_shift_json(cal_pkg)
        except Exception as e:
            print(f"Error auto-guardando turno calandra: {e}")

    return {
        "status": "success",
        "maquina_id": m_id,
        "nombre": "CALANDRA 2" if m_id == "CALANDRA_2" else "CALANDRA 3",
        "tipo": "Planchado y Plegado Automático" if m_id == "CALANDRA_2" else "Planchado & Inspección Óptica IA",
        "icono": "fa-scroll" if m_id == "CALANDRA_2" else "fa-eye",
        "is_turno_activo": shift_active,
        "turno_info": {
            "nombre": nombre_turno if shift_active else "Sin Turno Activo",
            "horario": horario_con_fecha if shift_active else f"Fuera de Turno | {fecha_formateada}",
            "fecha": fecha_formateada,
            "is_active": shift_active
        },
        "indicadores": prod,
        "grafica_hora_a_hora": prod.get("grafica_hora_a_hora", {})
    }


def get_turno_identificador(turno_dict: dict, shifts_list: list = None) -> tuple[str, int]:
    """
    Determina la identificación estandarizada del turno: 'Turno 1', 'Turno 2', etc.
    Devuelve (turno_identificador, turno_numero).
    """
    import re
    if not turno_dict:
        return "Turno 1", 1

    hora_ini = str(turno_dict.get("hora_inicio") or turno_dict.get("start") or "")[:5]
    nombre = str(turno_dict.get("nombre") or turno_dict.get("name") or "")

    if shifts_list:
        for idx, s in enumerate(shifts_list):
            s_start = str(s.get("hora_inicio") or s.get("start") or "")[:5]
            s_name = str(s.get("nombre") or s.get("name") or "")
            if hora_ini and s_start and hora_ini == s_start:
                return f"Turno {idx + 1}", idx + 1
            if nombre and s_name and (nombre.lower() in s_name.lower() or s_name.lower() in nombre.lower()):
                return f"Turno {idx + 1}", idx + 1

    # Extraer numeral si está presente en el nombre
    match = re.search(r'\b(?:turno\s*)?([1-9])\b', nombre, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        return f"Turno {num}", num

    return "Turno 1", 1


def build_calandra_shift_json(maquina_id: str, fecha: str = None, shift_data: dict = None, turno_numero: int = None) -> dict:
    """
    Construye el paquete JSON completo de un turno para Calandra 2 o Calandra 3,
    guardando la información hora a hora de cantidad de prendas y tiempo valle
    y de los indicadores del dashboard. Cada JSON contiene fecha y hora del turno
    y es identificado formalmente como 'Turno 1', 'Turno 2', etc.
    """
    m_id = maquina_id.upper()
    turnos_cache = get_cached_turnos()
    shifts_list = turnos_cache.get("shifts", [])

    if not shift_data:
        turno_act = turnos_cache.get("turno_actual", {})
        if is_shift_active(turno_act):
            shift_data = turno_act
        elif shifts_list:
            shift_data = shifts_list[0]
        else:
            shift_data = {
                "nombre": "Turno 1",
                "hora_inicio": "06:00",
                "hora_fin": "14:00",
                "fecha": fecha or datetime.now().strftime("%Y-%m-%d")
            }

    if turno_numero:
        turno_identificador = f"Turno {turno_numero}"
        t_num = turno_numero
    else:
        turno_identificador, t_num = get_turno_identificador(shift_data, shifts_list)

    fecha_turno = fecha or shift_data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora_inicio = str(shift_data.get("hora_inicio") or shift_data.get("start") or "06:00")[:5]
    hora_fin = str(shift_data.get("hora_fin") or shift_data.get("end") or "14:00")[:5]
    rango_horario = f"{hora_inicio} - {hora_fin}"

    try:
        fecha_formateada = datetime.strptime(fecha_turno, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_formateada = fecha_turno

    shift_key = f"{m_id}_{fecha_turno}_{turno_identificador.replace(' ', '_')}"

    # Obtener franjas horarias del turno
    try:
        h_ini_int = int(hora_inicio[:2])
        h_fin_int = int(hora_fin[:2])
    except Exception:
        h_ini_int, h_fin_int = 6, 14
    if h_fin_int <= h_ini_int:
        h_fin_int += 24

    labels = []
    prendas = []
    valle = []
    grandes = []
    pequenas = []

    conn = get_db_connection()
    cursor = conn.cursor()

    for h in range(h_ini_int, h_fin_int):
        h1 = h % 24
        h2 = (h + 1) % 24
        lbl = f"{h1:02d}:00 - {h2:02d}:00"
        labels.append(lbl)

        day_offset = h // 24
        dt_day = datetime.strptime(fecha_turno, "%Y-%m-%d") + timedelta(days=day_offset)
        slot_start_iso = f"{dt_day.strftime('%Y-%m-%d')} {h1:02d}:00:00"
        slot_end_iso = f"{dt_day.strftime('%Y-%m-%d')} {h2:02d}:00:00" if h2 != 0 else f"{(dt_day + timedelta(days=1)).strftime('%Y-%m-%d')} 00:00:00"

        row = cursor.execute("""
            SELECT 
                COALESCE(SUM(delta_total), 0) as tot_delta,
                COALESCE(SUM(delta_grandes), 0) as tot_g,
                COALESCE(SUM(delta_pequenas), 0) as tot_p,
                COALESCE(SUM(idle_min_total), 0.0) as tot_valle,
                MAX(count_total) - MIN(count_total) as span_tot
            FROM calandras_produccion
            WHERE maquina = ? AND timestamp_iso >= ? AND timestamp_iso < ?
        """, (m_id, slot_start_iso, slot_end_iso)).fetchone()

        tot_slot = 0
        g_slot = 0
        p_slot = 0
        v_slot = 0.0

        if row and (row["tot_delta"] > 0 or (row["span_tot"] and row["span_tot"] > 0)):
            tot_slot = row["tot_delta"] if row["tot_delta"] > 0 else (row["span_tot"] or 0)
            g_slot = row["tot_g"]
            p_slot = row["tot_p"]
            v_slot = round(float(row["tot_valle"]), 1)

        prendas.append(tot_slot)
        grandes.append(g_slot)
        pequenas.append(p_slot)
        valle.append(v_slot)

    conn.close()

    # Si SQLite aún no tiene cargas y coincide con el turno actual en vivo, consultar datos remotos
    if sum(prendas) == 0 and sum(valle) == 0.0 and fecha_turno == datetime.now().strftime("%Y-%m-%d"):
        prod_live = get_calandra_production(m_id, shift_data)
        g_live = prod_live.get("grafica_hora_a_hora", {})
        if g_live.get("prendas") and sum(g_live.get("prendas", [])) > 0:
            labels = g_live.get("labels", labels)
            prendas = g_live.get("prendas", prendas)
            valle = g_live.get("tiempo_valle", valle)
            if m_id == "CALANDRA_2":
                grandes = g_live.get("grandes", grandes)
                pequenas = g_live.get("pequenas", pequenas)

    if m_id == "CALANDRA_2":
        tot_grandes = sum(grandes) if grandes else 0
        tot_pequenas = sum(pequenas) if pequenas else 0
        tot_prendas = sum(prendas) or (tot_grandes + tot_pequenas)
        kg_grandes = round(tot_grandes * 0.45, 1)
        kg_pequenas = round(tot_pequenas * 0.15, 1)
        tot_kg = round(kg_grandes + kg_pequenas, 1)
    else:
        tot_prendas = sum(prendas)
        tot_grandes = 0
        tot_pequenas = 0
        kg_grandes = 0.0
        kg_pequenas = 0.0
        tot_kg = round(tot_prendas * 0.25, 1)
    tot_valle = round(sum(valle), 1)

    duracion_horas = max(len(labels), 1)
    now_dt = get_local_now().replace(tzinfo=None)
    start_iso, end_iso = get_shift_start_end_iso(fecha_turno, hora_inicio, hora_fin)
    now_str = get_local_now_str()
    if start_iso <= now_str <= end_iso:
        dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
        mins = max((now_dt - dt_start).total_seconds() / 60.0, 15.0)
        horas_calc = max(mins / 60.0, 0.25)
    else:
        horas_calc = float(duracion_horas)

    prendas_h = int(round(tot_prendas / horas_calc)) if horas_calc > 0 else 0
    kg_h = round(tot_kg / horas_calc, 1) if horas_calc > 0 else 0.0

    prendas_totales_str = f"{tot_prendas:,}".replace(",", ".") + " prendas"
    kgs_totales_str = f"{tot_kg:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg"
    tiempo_valle_str = f"{tot_valle:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min"
    prendas_hora_str = f"{prendas_h:,}".replace(",", ".") + " prendas/h"
    kg_hora_str = f"{kg_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"

    desglose_cal2 = None
    if m_id == "CALANDRA_2":
        g_h = int(round(tot_grandes / horas_calc)) if horas_calc > 0 else 0
        p_h = int(round(tot_pequenas / horas_calc)) if horas_calc > 0 else 0
        desglose_cal2 = {
            "prendas_grandes": tot_grandes,
            "prendas_grandes_str": f"{tot_grandes:,}".replace(",", ".") + " grandes",
            "prendas_pequenas": tot_pequenas,
            "prendas_pequenas_str": f"{tot_pequenas:,}".replace(",", ".") + " pequeñas",
            "kg_grandes": kg_grandes,
            "kg_grandes_str": f"{kg_grandes:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "kg_pequenas": kg_pequenas,
            "kg_pequenas_str": f"{kg_pequenas:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "tiempo_valle_grandes": tot_valle,
            "tiempo_valle_grandes_str": f"{tot_valle:.1f} min",
            "tiempo_valle_pequenas": tot_valle,
            "tiempo_valle_pequenas_str": f"{tot_valle:.1f} min",
            "prendas_grandes_hora": g_h,
            "prendas_grandes_hora_str": f"{g_h:,} g/h".replace(",", "."),
            "prendas_pequenas_hora": p_h,
            "prendas_pequenas_hora_str": f"{p_h:,} p/h".replace(",", ".")
        }

    return {
        "shift_key": shift_key,
        "maquina": m_id,
        "fecha": fecha_turno,
        "turno_identificador": turno_identificador,
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "rango_horario": rango_horario,
        "meta_info": {
            "planta": "ELIS NÁJERA 4.0",
            "maquina_id": m_id,
            "maquina_nombre": "Calandra 2" if m_id == "CALANDRA_2" else "Calandra 3",
            "fecha": fecha_turno,
            "fecha_formateada": fecha_formateada,
            "turno_identificador": turno_identificador,
            "nombre_turno": shift_data.get("nombre") or turno_identificador,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "rango_horario": rango_horario,
            "timestamp_actualizacion": get_local_now_str()
        },
        "indicadores_dashboard": {
            "prendas_totales": tot_prendas,
            "prendas_totales_str": prendas_totales_str,
            "kgs_totales": tot_kg,
            "kgs_totales_str": kgs_totales_str,
            "tiempo_valle_min": tot_valle,
            "tiempo_valle_str": tiempo_valle_str,
            "prendas_hora": prendas_h,
            "prendas_hora_str": prendas_hora_str,
            "kg_hora": kg_h,
            "kg_hora_str": kg_hora_str,
            "en_valle": False,
            "desglose_calandra2": desglose_cal2
        },
        "desglose_hora_a_hora": {
            "labels": labels,
            "prendas": prendas,
            "tiempo_valle_min": valle,
            "grandes": grandes if m_id == "CALANDRA_2" else None,
            "pequenas": pequenas if m_id == "CALANDRA_2" else None
        }
    }


def save_calandra_shift_json(shift_package: dict) -> bool:
    """Almacena o actualiza un paquete JSON de turno para Calandras en SQLite."""
    shift_key = shift_package["shift_key"]
    maquina = shift_package["maquina"]
    fecha = shift_package["fecha"]
    turno_identificador = shift_package["turno_identificador"]
    meta = shift_package.get("meta_info", {})
    nombre_turno = meta.get("nombre_turno", turno_identificador)
    hora_inicio = shift_package["hora_inicio"]
    hora_fin = shift_package["hora_fin"]
    rango_horario = shift_package.get("rango_horario", f"{hora_inicio} - {hora_fin}")

    ind = shift_package.get("indicadores_dashboard", {})
    prendas_totales = int(ind.get("prendas_totales", 0))
    kgs_totales = float(ind.get("kgs_totales", 0.0))
    tiempo_valle_min = float(ind.get("tiempo_valle_min", 0.0))
    prendas_hora = int(ind.get("prendas_hora", 0))
    kg_hora = float(ind.get("kg_hora", 0.0))

    data_json = json.dumps(shift_package, ensure_ascii=False)
    now_local = get_local_now_str()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO calandras_turnos_persistencia (
            shift_key, maquina, fecha, turno_identificador, nombre_turno,
            hora_inicio, hora_fin, rango_horario,
            prendas_totales, kgs_totales, tiempo_valle_min,
            prendas_hora, kg_hora, data_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(shift_key) DO UPDATE SET
            fecha = excluded.fecha,
            turno_identificador = excluded.turno_identificador,
            nombre_turno = excluded.nombre_turno,
            hora_inicio = excluded.hora_inicio,
            hora_fin = excluded.hora_fin,
            rango_horario = excluded.rango_horario,
            prendas_totales = excluded.prendas_totales,
            kgs_totales = excluded.kgs_totales,
            tiempo_valle_min = excluded.tiempo_valle_min,
            prendas_hora = excluded.prendas_hora,
            kg_hora = excluded.kg_hora,
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
    """, (
        shift_key, maquina, fecha, turno_identificador, nombre_turno,
        hora_inicio, hora_fin, rango_horario,
        prendas_totales, kgs_totales, tiempo_valle_min,
        prendas_hora, kg_hora, data_json, now_local
    ))
    conn.commit()
    conn.close()
    return True


@router.post("/calandras/{maquina_id}/guardar-turno-json")
def trigger_save_calandra_shift_json(
    maquina_id: str,
    fecha: Optional[str] = None,
    turno_numero: Optional[int] = None,
    user: dict = Depends(check_produccion_permission)
):
    """Genera y guarda en la base de datos local SQLite el paquete JSON del turno para Calandra 2 o Calandra 3."""
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no válida")

    pkg = build_calandra_shift_json(m_id, fecha=fecha, turno_numero=turno_numero)
    ok = save_calandra_shift_json(pkg)
    return {
        "status": "success" if ok else "error",
        "message": f"Turno {pkg['turno_identificador']} guardado exitosamente en SQLite para {m_id}",
        "shift_key": pkg["shift_key"],
        "maquina": m_id,
        "fecha": pkg["fecha"],
        "turno_identificador": pkg["turno_identificador"],
        "hora_inicio": pkg["hora_inicio"],
        "hora_fin": pkg["hora_fin"],
        "rango_horario": pkg["rango_horario"],
        "indicadores_dashboard": pkg["indicadores_dashboard"],
        "desglose_hora_a_hora": pkg["desglose_hora_a_hora"]
    }


@router.get("/calandras/{maquina_id}/turnos-historial")
def get_calandras_turnos_historial(
    maquina_id: str,
    fecha: Optional[str] = None,
    user: dict = Depends(check_produccion_permission)
):
    """Consulta la lista de turnos guardados en SQLite para Calandra 2 o Calandra 3."""
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no válida")

    conn = get_db_connection()
    if fecha:
        rows = conn.execute("""
            SELECT shift_key, maquina, fecha, turno_identificador, nombre_turno,
                   hora_inicio, hora_fin, rango_horario,
                   prendas_totales, kgs_totales, tiempo_valle_min,
                   prendas_hora, kg_hora, updated_at
            FROM calandras_turnos_persistencia
            WHERE maquina = ? AND fecha = ?
            ORDER BY hora_inicio ASC
        """, (m_id, fecha)).fetchall()
    else:
        rows = conn.execute("""
            SELECT shift_key, maquina, fecha, turno_identificador, nombre_turno,
                   hora_inicio, hora_fin, rango_horario,
                   prendas_totales, kgs_totales, tiempo_valle_min,
                   prendas_hora, kg_hora, updated_at
            FROM calandras_turnos_persistencia
            WHERE maquina = ?
            ORDER BY fecha DESC, hora_inicio ASC
        """, (m_id,)).fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "shift_key": r["shift_key"],
            "maquina": r["maquina"],
            "fecha": r["fecha"],
            "turno_identificador": r["turno_identificador"],
            "nombre_turno": r["nombre_turno"],
            "hora_inicio": r["hora_inicio"],
            "hora_fin": r["hora_fin"],
            "rango_horario": r["rango_horario"],
            "prendas_totales": r["prendas_totales"],
            "prendas_totales_str": f"{r['prendas_totales']:,}".replace(",", ".") + " prendas",
            "kgs_totales": r["kgs_totales"],
            "kgs_totales_str": f"{r['kgs_totales']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "tiempo_valle_min": r["tiempo_valle_min"],
            "tiempo_valle_str": f"{r['tiempo_valle_min']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
            "prendas_hora": r["prendas_hora"],
            "prendas_hora_str": f"{r['prendas_hora']:,}".replace(",", ".") + " prendas/h",
            "kg_hora": r["kg_hora"],
            "kg_hora_str": f"{r['kg_hora']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h",
            "updated_at": r["updated_at"]
        })

    return {
        "status": "success",
        "maquina": m_id,
        "total": len(results),
        "turnos": results
    }


@router.get("/calandras/{maquina_id}/turnos-historial/{shift_key}")
def get_calandras_turno_json_detalle(
    maquina_id: str,
    shift_key: str,
    user: dict = Depends(check_produccion_permission)
):
    """Retorna el paquete JSON completo de un turno persistido para Calandra 2 o Calandra 3."""
    m_id = maquina_id.upper()
    conn = get_db_connection()
    row = conn.execute("""
        SELECT data_json FROM calandras_turnos_persistencia
        WHERE maquina = ? AND shift_key = ?
    """, (m_id, shift_key)).fetchone()
    conn.close()

    if not row or not row["data_json"]:
        raise HTTPException(status_code=404, detail="Turno no encontrado en persistencia")

    try:
        return json.loads(row["data_json"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parseando JSON: {e}")


@router.get("/calandras/{maquina_id}/turnos-fechas")
def get_calandras_turnos_fechas_disponibles(
    maquina_id: str,
    user: dict = Depends(check_produccion_permission)
):
    """Retorna la lista de fechas disponibles con turnos guardados en SQLite."""
    m_id = maquina_id.upper()
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT fecha FROM calandras_turnos_persistencia
        WHERE maquina = ?
        ORDER BY fecha DESC
    """, (m_id,)).fetchall()
    conn.close()

    return {
        "status": "success",
        "maquina": m_id,
        "fechas": [r["fecha"] for r in rows]
    }


def get_calandra_production(maquina_id: str, turno_act: dict = None) -> dict:
    """
    Calcula los indicadores y la matriz hora a hora para Calandra 2 o Calandra 3
    a partir de los mensajes MQTT (elis/calandra2/produccion o elis/calandra3/produccion),
    la base de datos SQLite calandras_produccion y la sincronización con el servicio de producción.
    Si no hay turno activo en curso, todos los valores se devuelven en cero.
    """
    from app.mqtt_subscriber import get_calandras_live_cache
    import urllib.request

    live_cache = get_calandras_live_cache().get(maquina_id, {})
    maq_param = "calandra_2" if maquina_id == "CALANDRA_2" else "calandra_3"

    now_dt = get_local_now().replace(tzinfo=None)
    w_idx = now_dt.weekday()

    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})

    shift_active = is_shift_active(turno_act)

    # Franjas horarias estándar de turno (para cuando no hay turno activo o fallback)
    default_labels = ["06:00 - 07:00", "07:00 - 08:00", "08:00 - 09:00", "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "12:00 - 13:00", "13:00 - 14:00"]

    if not shift_active:
        n_lbl = len(default_labels)
        return {
            "maquina": maquina_id,
            "is_turno_activo": False,
            "en_valle": False,
            "prendas_totales": 0,
            "prendas_totales_str": "0 prendas",
            "kgs_totales": 0.0,
            "kgs_totales_str": "0,0 kg",
            "tiempo_valle_min": 0.0,
            "tiempo_valle_str": "0,0 min",
            "prendas_hora": 0,
            "prendas_hora_str": "0 prendas/h",
            "kg_hora": 0.0,
            "kg_hora_str": "0,0 kg/h",
            "desglose_calandra2": {
                "prendas_grandes": 0,
                "prendas_grandes_str": "0 grandes",
                "prendas_pequenas": 0,
                "prendas_pequenas_str": "0 pequeñas",
                "kg_grandes": 0.0,
                "kg_grandes_str": "0,0 kg",
                "kg_pequenas": 0.0,
                "kg_pequenas_str": "0,0 kg",
                "tiempo_valle_grandes": 0.0,
                "tiempo_valle_grandes_str": "0.0 min",
                "tiempo_valle_pequenas": 0.0,
                "tiempo_valle_pequenas_str": "0.0 min",
                "prendas_grandes_hora": 0,
                "prendas_grandes_hora_str": "0 g/h",
                "prendas_pequenas_hora": 0,
                "prendas_pequenas_hora_str": "0 p/h"
            } if maquina_id == "CALANDRA_2" else None,
            "grafica_hora_a_hora": {
                "labels": default_labels,
                "prendas": [0] * n_lbl,
                "tiempo_valle": [0.0] * n_lbl,
                "grandes": [0] * n_lbl if maquina_id == "CALANDRA_2" else None,
                "pequenas": [0] * n_lbl if maquina_id == "CALANDRA_2" else None
            }
        }

    labels = []
    prendas = []
    valle = []
    grandes = []
    pequenas = []

    # 1. Intentar consultar la matriz horaria procesada del día y turno actual
    try:
        url = f"http://100.127.85.111:5002/api/tabla-horaria?machine_id={maq_param}"
        req = urllib.request.urlopen(url, timeout=3)
        t_data = json.loads(req.read().decode('utf-8'))
        hour_slots = t_data.get("hour_slots", [])
        cells = t_data.get("cells", {})

        for s in hour_slots:
            lbl = f"{s['startStr']} - {s['endStr']}"
            labels.append(lbl)
            cell_key = f"{w_idx}_{s['index']}"
            c = cells.get(cell_key, {})
            l = int(c.get("large", 0) or 0)
            p = int(c.get("small", 0) or 0)
            tot_val = c.get("total")
            tot = int(tot_val if tot_val is not None else (l + p))
            v = round(float(c.get("idle_min", 0.0) or 0.0), 1)

            prendas.append(tot)
            grandes.append(l)
            pequenas.append(p)
            valle.append(v)
    except Exception:
        h_ini = str(turno_act.get("hora_inicio", "06:00"))[:2]
        h_fin = str(turno_act.get("hora_fin", "14:00"))[:2]
        try:
            start_h = int(h_ini)
            end_h = int(h_fin)
            if end_h <= start_h:
                end_h += 24
        except Exception:
            start_h, end_h = 6, 14

        for h in range(start_h, end_h):
            h1 = h % 24
            h2 = (h + 1) % 24
            labels.append(f"{h1:02d}:00 - {h2:02d}:00")
            prendas.append(0)
            valle.append(0.0)
            grandes.append(0)
            pequenas.append(0)

    tot_prendas_remotas = sum(prendas)
    tot_grandes_remotas = sum(grandes)
    tot_pequenas_remotas = sum(pequenas)
    tot_valle_remoto = round(sum(valle), 1)

    if maquina_id == "CALANDRA_2":
        p_grandes = tot_grandes_remotas
        p_pequenas = tot_pequenas_remotas
        p_totales = tot_prendas_remotas or (p_grandes + p_pequenas)

        w_grandes = round(p_grandes * 0.45, 1)
        w_pequenas = round(p_pequenas * 0.15, 1)
        w_totales = round(w_grandes + w_pequenas, 1)

        v_total = tot_valle_remoto
        v_grandes = v_total
        v_pequenas = v_total
        in_idle = bool(live_cache.get("in_idle_grandes") or live_cache.get("in_idle_pequenas") or live_cache.get("in_idle"))
    else:
        # CALANDRA_3
        p_totales = tot_prendas_remotas
        p_grandes = 0
        p_pequenas = tot_prendas_remotas
        w_totales = round(p_totales * 0.25, 1)
        w_grandes = 0.0
        w_pequenas = w_totales
        v_total = tot_valle_remoto
        v_grandes = 0.0
        v_pequenas = v_total
        in_idle = bool(live_cache.get("in_idle"))

    # Calcular horas transcurridas de turno
    dur_min = float(turno_act.get("minutos_transcurridos") or 60)
    horas_transcurridas = max(dur_min / 60.0, 0.25)

    prendas_h = int(round(p_totales / horas_transcurridas))
    kg_h = round(w_totales / horas_transcurridas, 1)

    prendas_totales_str = f"{p_totales:,}".replace(",", ".") + " prendas"
    kgs_totales_str = f"{w_totales:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg"
    tiempo_valle_str = f"{v_total:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min"
    prendas_hora_str = f"{prendas_h:,}".replace(",", ".") + " prendas/h"
    kg_hora_str = f"{kg_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"

    return {
        "maquina": maquina_id,
        "is_turno_activo": True,
        "en_valle": in_idle,
        "prendas_totales": p_totales,
        "prendas_totales_str": prendas_totales_str,
        "kgs_totales": w_totales,
        "kgs_totales_str": kgs_totales_str,
        "tiempo_valle_min": v_total,
        "tiempo_valle_str": tiempo_valle_str,
        "prendas_hora": prendas_h,
        "prendas_hora_str": prendas_hora_str,
        "kg_hora": kg_h,
        "kg_hora_str": kg_hora_str,
        "desglose_calandra2": {
            "prendas_grandes": p_grandes,
            "prendas_grandes_str": f"{p_grandes:,}".replace(",", ".") + " grandes",
            "prendas_pequenas": p_pequenas,
            "prendas_pequenas_str": f"{p_pequenas:,}".replace(",", ".") + " pequeñas",
            "kg_grandes": w_grandes,
            "kg_grandes_str": f"{w_grandes:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "kg_pequenas": w_pequenas,
            "kg_pequenas_str": f"{w_pequenas:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "tiempo_valle_grandes": v_grandes,
            "tiempo_valle_grandes_str": f"{v_grandes:.1f} min",
            "tiempo_valle_pequenas": v_pequenas,
            "tiempo_valle_pequenas_str": f"{v_pequenas:.1f} min",
            "prendas_grandes_hora": int(round(p_grandes / horas_transcurridas)),
            "prendas_grandes_hora_str": f"{int(round(p_grandes / horas_transcurridas)):,} g/h".replace(",", "."),
            "prendas_pequenas_hora": int(round(p_pequenas / horas_transcurridas)),
            "prendas_pequenas_hora_str": f"{int(round(p_pequenas / horas_transcurridas)):,} p/h".replace(",", ".")
        } if maquina_id == "CALANDRA_2" else None,
        "grafica_hora_a_hora": {
            "labels": labels,
            "prendas": prendas,
            "tiempo_valle": valle,
            "grandes": grandes if maquina_id == "CALANDRA_2" else None,
            "pequenas": pequenas if maquina_id == "CALANDRA_2" else None
        }
    }

from datetime import datetime, timedelta
from app.utils import get_local_now_str, get_local_now

def calculate_shift_duration_and_objetivo(turno_act: dict) -> tuple[float, float]:
    """
    Calcula la duración del turno en minutos y el objetivo dinámico de kg.
    Fórmula: (minutos_del_turno / 2) * 60 kg = (horas_del_turno * 60 / 2) * 60 kg
    """
    duracion_min = 0.0
    if turno_act and "duracion_total_minutos" in turno_act and float(turno_act.get("duracion_total_minutos") or 0) > 0:
        duracion_min = float(turno_act["duracion_total_minutos"])
    else:
        h_start_str = turno_act.get("hora_inicio", "06:00") if turno_act else "06:00"
        h_end_str = turno_act.get("hora_fin", "14:00") if turno_act else "14:00"
        try:
            h_start, m_start = map(int, h_start_str.split(":")[:2])
            h_end, m_end = map(int, h_end_str.split(":")[:2])
            start_min = h_start * 60 + m_start
            end_min = h_end * 60 + m_end
            if end_min <= start_min:
                end_min += 24 * 60
            duracion_min = float(end_min - start_min)
        except Exception:
            duracion_min = 480.0

    if duracion_min <= 0:
        duracion_min = 480.0

    objetivo_kg = (duracion_min / 2.0) * 60.0
    return duracion_min, objetivo_kg


@router.get("/tunel-lavado/dashboard")
def get_tunel_lavado_dashboard(user: dict = Depends(check_produccion_permission)):
    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    
    nombre_turno = turno_act.get("nombre") or "Turno Mañana"

    fecha_raw = turno_act.get("fecha") or get_local_now_str("%Y-%m-%d")
    try:
        fecha_formateada = datetime.strptime(fecha_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_formateada = get_local_now_str("%d/%m/%Y")

    horario_base = f"{turno_act.get('hora_inicio', '06:00')} - {turno_act.get('hora_fin', '14:00')}"
    horario_con_fecha = f"{horario_base} | {fecha_formateada}"

    # Calcular duración del turno y objetivo dinámico de kg
    duracion_total_min, objetivo_kg = calculate_shift_duration_and_objetivo(turno_act)
    objetivo_kg_str = f"{int(objetivo_kg):,}".replace(",", ".")

    # Calcular progreso dinámico del turno
    try:
        now_dt = get_local_now()
        h_start_str = turno_act.get("hora_inicio", "06:00")
        h_start, m_start = map(int, h_start_str.split(":")[:2])
        dt_start = now_dt.replace(hour=h_start, minute=m_start, second=0, microsecond=0)
        if now_dt < dt_start:
            dt_start -= timedelta(days=1)
        elapsed_min = max((now_dt - dt_start).total_seconds() / 60.0, 0.0)
        progreso_turno = round(min((elapsed_min / duracion_total_min) * 100.0, 100.0), 1)
    except Exception:
        progreso_turno = turno_act.get("progreso_porcentaje") or 68.5

    tunel_kpis = calculate_tunel_metrics(turno_act)

    # Hora de actualización local en tiempo real
    now_local_formatted = get_local_now_str("%Y-%m-%d %H:%M:%S")

    dash_response = {
        "maquina": "TÚNEL DE LAVADO",
        "planta": "ELIS NÁJERA 4.0",
        "estado": "Operativa",
        "oee": 91.2,
        "sync_info": {
            "origen": "MQTT Mosquitto (192.168.0.116:1883) | Turnos Jetson Server 1",
            "cache_actualizado": now_local_formatted,
            "frecuencia_sync": "Tiempo Real MQTT + Polling 30m Turnos"
        },
        "turno_activo": {
            "nombre": nombre_turno,
            "horario": horario_con_fecha,
            "fecha": fecha_formateada,
            "progreso_porcentaje": progreso_turno,
            "minutos_transcurridos": turno_act.get("minutos_transcurridos", 240)
        },
        "indicadores_destacados": {
            "kg_totales_turno": {
                "titulo": "Kg Totales Turno",
                "valor": tunel_kpis["kg_totales_turno"],
                "subtexto": f"Objetivo Turno: {objetivo_kg_str} kg ({'Real MQTT' if tunel_kpis['is_real'] else 'Simulado'})",
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
            "hprod": {
                "titulo": "Productividad hProd",
                "valor": tunel_kpis["hprod"],
                "subtexto": f"Tiempo prom: {tunel_kpis['promedio_tiempo_carga']}",
                "color_gradiente": "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)",
                "icono": "fa-tachometer-alt"
            },
            "ikprod": {
                "titulo": "Índice de Eficiencia (ikProd)",
                "valor": tunel_kpis["ikprod"]["pct_str"],
                "neto_str": tunel_kpis["ikprod"]["neto_str"],
                "tprom_str": tunel_kpis["ikprod"]["tprom_str"],
                "promedio_carga_str": f"Prom: {tunel_kpis['promedio_carga']}/carga",
                "promedio_tiempo_str": f"Tprom: {tunel_kpis['promedio_tiempo_carga']}",
                "subtexto": tunel_kpis["ikprod"]["formula_str"],
                "color_gradiente": tunel_kpis["ikprod"]["gradient"],
                "color_codigo": tunel_kpis["ikprod"]["color_code"],
                "subtexto_color": tunel_kpis["ikprod"]["subtexto_color"],
                "text_color": tunel_kpis["ikprod"]["text_color"],
                "border_color": tunel_kpis["ikprod"]["border_color"],
                "icono": "fa-chart-line"
            },
            "clientes_unicos": {
                "titulo": "Clientes Atendidos",
                "valor": f"{tunel_kpis.get('clientes_unicos', 0)} clientes",
                "subtexto": "Códigos únicos de cliente en turno",
                "icono": "fa-users"
            },
            "programas_unicos": {
                "titulo": "Programas Ejecutados",
                "valor": f"{tunel_kpis.get('programas_unicos', 0)} programas",
                "subtexto": "Categorías/Programas únicos en turno",
                "icono": "fa-layer-group"
            }
        },
        "grafica_avance": {
            "labels": tunel_kpis.get("grafica_labels", []),
            "kg_por_hora": tunel_kpis.get("grafica_kg_hora", []),
            "kg_acumulado": tunel_kpis.get("grafica_kg_acumulado", []),
            "cargas_por_hora": tunel_kpis.get("grafica_cargas_hora", [])
        }
    }

    # Auto-guardado dinámico de persistencia del paquete JSON de turno
    try:
        pkg = build_shift_json_package(turno_act)
        save_shift_json_package(pkg)
    except Exception as e:
        print(f"Error auto-guardando paquete json de turno: {e}")

    return dash_response


def get_current_active_shift() -> dict:
    """
    Retorna el turno activo en el momento actual considerando la hora local.
    Soporta turnos diurnos y nocturnos que cruzan medianoche.
    """
    turnos_cache = get_cached_turnos()
    now_dt = get_local_now()
    now_hm = now_dt.strftime("%H:%M")
    today_str = now_dt.strftime("%Y-%m-%d")
    yesterday_str = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    shifts = turnos_cache.get("shifts") or [
        {"name": "Turno 1", "start": "06:00", "end": "14:00", "color": "#10b981"},
        {"name": "Turno 2", "start": "14:00", "end": "21:00", "color": "#3b82f6"},
        {"name": "Turno 3", "start": "21:00", "end": "02:00", "color": "#831843"}
    ]

    for s in shifts:
        s_name = s.get("name")
        start = s.get("start")
        end = s.get("end")
        if not start or not end:
            continue

        if start < end:
            if start <= now_hm < end:
                return {
                    "is_active": True,
                    "nombre": s_name,
                    "hora_inicio": start,
                    "hora_fin": end,
                    "fecha": today_str,
                    "color": s.get("color")
                }
        else:
            if now_hm >= start:
                return {
                    "is_active": True,
                    "nombre": s_name,
                    "hora_inicio": start,
                    "hora_fin": end,
                    "fecha": today_str,
                    "color": s.get("color")
                }
            elif now_hm < end:
                return {
                    "is_active": True,
                    "nombre": s_name,
                    "hora_inicio": start,
                    "hora_fin": end,
                    "fecha": yesterday_str,
                    "color": s.get("color")
                }

    return {
        "is_active": False,
        "nombre": "Sin turno activo",
        "fecha": today_str
    }


@router.get("/tunel-lavado/dashboard-filtrado")
def get_tunel_lavado_dashboard_filtrado(
    hora_desde: Optional[str] = None,
    hora_hasta: Optional[str] = None,
    user: dict = Depends(check_produccion_permission)
):
    shift_info = get_current_active_shift()
    if not shift_info.get("is_active"):
        return {
            "shift_active": False,
            "detail": "No hay turno en ejecución"
        }

    # Si no se proporcionan horas de filtro, retornar metadatos del turno activo
    if not hora_desde or not hora_hasta:
        try:
            fecha_fmt = datetime.strptime(shift_info["fecha"], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            fecha_fmt = shift_info["fecha"]
        return {
            "shift_active": True,
            "turno": {
                "nombre": shift_info["nombre"],
                "hora_inicio": shift_info["hora_inicio"],
                "hora_fin": shift_info["hora_fin"],
                "fecha": shift_info["fecha"],
                "fecha_formateada": fecha_fmt
            }
        }

    # Validar formato HH:MM
    try:
        datetime.strptime(hora_desde, "%H:%M")
        datetime.strptime(hora_hasta, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de hora inválido. Utilice HH:MM (ej. 08:30 o 23:20)."
        )

    fecha = shift_info["fecha"]
    hora_inicio = shift_info["hora_inicio"]
    hora_fin = shift_info["hora_fin"]

    base_date = datetime.strptime(fecha, "%Y-%m-%d")
    next_date_str = (base_date + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        h_start = int(hora_inicio.split(":")[0])
        h_end = int(hora_fin.split(":")[0])
    except Exception:
        h_start, h_end = 6, 14

    crosses_midnight = (h_end < h_start)

    if crosses_midnight:
        start_date_str = fecha if hora_desde >= hora_inicio else next_date_str
        end_date_str = fecha if hora_hasta >= hora_inicio else next_date_str
    else:
        start_date_str = fecha
        end_date_str = fecha

    start_iso = f"{start_date_str} {hora_desde}:00"
    end_iso = f"{end_date_str} {hora_hasta}:00"

    dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
    dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")

    if dt_end <= dt_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La hora 'Hasta' debe ser posterior a la hora 'Desde' dentro de la continuidad del turno."
        )

    duracion_minutos = (dt_end - dt_start).total_seconds() / 60.0
    horas_trans = max(duracion_minutos / 60.0, 0.1)

    # Consultar datos reales en tunel_cargas
    conn = get_db_connection()
    row = conn.execute("""
        SELECT 
            COUNT(*) as total_cargas,
            COALESCE(AVG(peso_kg), 0) as promedio_peso,
            COALESCE(AVG(tiempo_entre_cargas_seg), 0) as promedio_tiempo_seg,
            COALESCE(SUM(peso_kg), 0) as total_kg,
            COUNT(DISTINCT cliente) as clientes_unicos,
            COUNT(DISTINCT categoria) as programas_unicos
        FROM tunel_cargas
        WHERE timestamp_iso >= ? AND timestamp_iso <= ?
    """, (start_iso, end_iso)).fetchone()

    # Generar desglose horario convencional para la gráfica (bloques de horas completas ej: 06:00 - 07:00)
    slot_curr = dt_start.replace(minute=0, second=0, microsecond=0)
    if dt_end.minute == 0 and dt_end.second == 0:
        slots_end = dt_end
    else:
        slots_end = dt_end.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    grafica_labels = []
    grafica_kg_hora = []
    grafica_kg_acumulado = []
    grafica_cargas_hora = []
    running_kg = 0.0

    while slot_curr < slots_end:
        slot_next = slot_curr + timedelta(hours=1)
        label_str = f"{slot_curr.strftime('%H:%M')} - {slot_next.strftime('%H:%M')}"

        q_start = max(dt_start, slot_curr)
        q_end = min(dt_end, slot_next)
        q_start_str = q_start.strftime("%Y-%m-%d %H:%M:%S")
        q_end_str = q_end.strftime("%Y-%m-%d %H:%M:%S")

        if q_end >= dt_end:
            q = "SELECT COUNT(*) as num_cargas, COALESCE(SUM(peso_kg), 0) as kg_hora FROM tunel_cargas WHERE timestamp_iso >= ? AND timestamp_iso <= ?"
        else:
            q = "SELECT COUNT(*) as num_cargas, COALESCE(SUM(peso_kg), 0) as kg_hora FROM tunel_cargas WHERE timestamp_iso >= ? AND timestamp_iso < ?"

        row_h = conn.execute(q, (q_start_str, q_end_str)).fetchone()
        kg_val = round(row_h["kg_hora"], 1) if row_h else 0.0
        cargas_val = row_h["num_cargas"] if row_h else 0
        running_kg += kg_val

        grafica_labels.append(label_str)
        grafica_kg_hora.append(kg_val)
        grafica_kg_acumulado.append(round(running_kg, 1))
        grafica_cargas_hora.append(cargas_val)

        slot_curr = slot_next

    # Obtener último programa dentro del rango
    last_load = conn.execute("""
        SELECT categoria, cliente, timestamp_iso FROM tunel_cargas
        WHERE timestamp_iso >= ? AND timestamp_iso <= ?
        ORDER BY timestamp_iso DESC LIMIT 1
    """, (start_iso, end_iso)).fetchone()
    conn.close()

    if last_load:
        hora_c = last_load['timestamp_iso'].split(' ')[1][:5] if ' ' in last_load['timestamp_iso'] else ''
        last_prog_str = f"Prog {last_load['categoria']:02d} | Cliente {last_load['cliente']} ({hora_c})"
    else:
        last_prog_str = "Sin cargas en el rango seleccionado"

    total_cargas = row["total_cargas"] if row else 0
    total_kg = round(row["total_kg"], 1) if row else 0.0
    promedio_peso = round(row["promedio_peso"], 1) if row else 0.0
    promedio_tiempo_seg = round(row["promedio_tiempo_seg"]) if row else 0
    promedio_tiempo_min = round(promedio_tiempo_seg / 60.0, 2)
    clientes_unicos = row["clientes_unicos"] if row and row["clientes_unicos"] else 0
    programas_unicos = row["programas_unicos"] if row and row["programas_unicos"] else 0

    hprod_kgh = int(round(total_kg / horas_trans))
    hprod_str = f"{hprod_kgh:,} kg/h".replace(",", ".")

    ikprod_neto = round(promedio_peso / max(promedio_tiempo_min, 0.01), 2) if total_cargas > 0 else 0.0
    ikprod_pct = round((ikprod_neto / 30.0) * 100.0, 1) if total_cargas > 0 else 0.0

    if ikprod_pct < 30.0:
        color_code = "red"
        gradient = "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)"
        subtexto_color = "#f87171"
        text_color = "#ef4444"
        border_color = "#ef4444"
    elif ikprod_pct < 60.0:
        color_code = "orange"
        gradient = "linear-gradient(135deg, #d97706 0%, #b45309 100%)"
        subtexto_color = "#fcd34d"
        text_color = "#f59e0b"
        border_color = "#f59e0b"
    else:
        color_code = "green"
        gradient = "linear-gradient(135deg, #059669 0%, #047857 100%)"
        subtexto_color = "#6ee7b7"
        text_color = "#10b981"
        border_color = "#10b981"

    objetivo_kg = (duracion_minutos / 2.0) * 60.0
    objetivo_kg_str = f"{int(objetivo_kg):,}".replace(",", ".")

    try:
        fecha_fmt = datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_fmt = fecha

    return {
        "shift_active": True,
        "maquina": "TÚNEL DE LAVADO",
        "planta": "ELIS NÁJERA 4.0",
        "estado": "Operativa",
        "oee": 91.2,
        "turno_info": {
            "nombre": shift_info["nombre"],
            "horario_completo": f"{shift_info['hora_inicio']} - {shift_info['hora_fin']}",
            "fecha": fecha_fmt,
            "rango_filtrado": f"{hora_desde} - {hora_hasta}",
            "duracion_minutos": round(duracion_minutos, 1)
        },
        "indicadores_destacados": {
            "kg_totales_turno": {
                "titulo": "Kg Totales (Rango)",
                "valor": f"{total_kg:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "subtexto": f"Objetivo Rango: {objetivo_kg_str} kg ({duracion_minutos:.0f} min)",
                "color_gradiente": "linear-gradient(135deg, #0284c7 0%, #06b6d4 100%)",
                "icono": "fa-weight-hanging"
            },
            "cargas_totales_turno": {
                "titulo": "Cargas Totales (Rango)",
                "valor": f"{total_cargas} cargas",
                "subtexto": f"Promedio: {promedio_peso} kg/carga",
                "color_gradiente": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                "icono": "fa-boxes"
            },
            "hprod": {
                "titulo": "Productividad hProd",
                "valor": hprod_str,
                "subtexto": f"Tiempo prom: {promedio_tiempo_min} min",
                "color_gradiente": "linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%)",
                "icono": "fa-tachometer-alt"
            },
            "ikprod": {
                "titulo": "Índice de Eficiencia (ikProd)",
                "valor": f"{ikprod_pct}%",
                "pct": ikprod_pct,
                "pct_str": f"{ikprod_pct}%",
                "neto": ikprod_neto,
                "neto_str": f"ikProd Neto: {ikprod_neto:.2f}",
                "tprom_str": f"Tprom: {promedio_tiempo_min} min ({promedio_tiempo_seg}s)",
                "promedio_carga_str": f"Prom: {promedio_peso} kg/carga",
                "promedio_tiempo_str": f"Tprom: {promedio_tiempo_min} min",
                "subtexto": "Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%",
                "color_gradiente": gradient,
                "color_codigo": color_code,
                "subtexto_color": subtexto_color,
                "text_color": text_color,
                "border_color": border_color,
                "icono": "fa-chart-line"
            },
            "clientes_unicos": {
                "titulo": "Clientes Atendidos",
                "valor": f"{clientes_unicos} clientes",
                "subtexto": "Códigos únicos de cliente en rango",
                "icono": "fa-users"
            },
            "programas_unicos": {
                "titulo": "Programas Ejecutados",
                "valor": f"{programas_unicos} programas",
                "subtexto": "Categorías/Programas únicos en rango",
                "icono": "fa-layer-group"
            }
        },
        "grafica_avance": {
            "labels": grafica_labels,
            "kg_por_hora": grafica_kg_hora,
            "kg_acumulado": grafica_kg_acumulado,
            "cargas_por_hora": grafica_cargas_hora
        },
        "programa_actual": last_prog_str
    }


def build_shift_json_package(turno_act: dict = None):
    """Construye dinámicamente el paquete JSON completo de persistencia del turno."""
    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})

    nombre_turno = turno_act.get("nombre") or "Turno Mañana"
    hora_inicio = turno_act.get("hora_inicio", "06:00")
    hora_fin = turno_act.get("hora_fin", "14:00")
    fecha_raw = turno_act.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    try:
        fecha_formateada = datetime.strptime(fecha_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_formateada = datetime.now().strftime("%d/%m/%Y")

    horario_completo = f"{hora_inicio} - {hora_fin} | {fecha_formateada}"
    shift_key = f"{fecha_raw}_{nombre_turno.replace(' ', '_')}"

    tunel_kpis = calculate_tunel_metrics(turno_act)
    ikprod = tunel_kpis.get("ikprod", {})

    total_kg_num = float(tunel_kpis.get("total_kg_num", 0.0))
    _, objetivo_kg = calculate_shift_duration_and_objetivo(turno_act)
    cumplimiento_pct = round((total_kg_num / objetivo_kg) * 100.0, 2) if objetivo_kg > 0 else 0.0

    shift_package = {
        "shift_key": shift_key,
        "meta_info": {
            "planta": "ELIS NÁJERA 4.0",
            "maquina": "TÚNEL DE LAVADO",
            "fecha": fecha_raw,
            "fecha_formateada": fecha_formateada,
            "nombre_turno": nombre_turno,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "horario_completo": horario_completo,
            "timestamp_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "es_datos_reales": tunel_kpis.get("is_real", False)
        },
        "indicadores_ampliados": {
            "kg_totales_turno": {
                "valor_num": total_kg_num,
                "valor_str": tunel_kpis.get("kg_totales_turno", "0 kg"),
                "objetivo_kg": int(objetivo_kg),
                "cumplimiento_pct": cumplimiento_pct
            },
            "cargas_totales_turno": {
                "valor_num": tunel_kpis.get("cargas_num", 0),
                "valor_str": tunel_kpis.get("cantidad_cargas", "0 cargas")
            },
            "productividad_hprod": {
                "valor_num": tunel_kpis.get("hprod_num", 0),
                "valor_str": tunel_kpis.get("hprod", "0 kg/h")
            },
            "indice_eficiencia_ikprod": {
                "pct_num": ikprod.get("pct", 0.0),
                "pct_str": ikprod.get("pct_str", "0.0%"),
                "neto_num": ikprod.get("neto", 0.0),
                "neto_str": ikprod.get("neto_str", "ikProd Neto: 0.00"),
                "color_codigo": ikprod.get("color_code", "red"),
                "text_color": ikprod.get("text_color", "#ef4444"),
                "subtexto_color": ikprod.get("subtexto_color", "#f87171"),
                "border_color": ikprod.get("border_color", "#ef4444"),
                "tprom_str": ikprod.get("tprom_str", "Tprom: 0 min (0s)"),
                "formula": ikprod.get("formula_str", "Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%")
            },
            "clientes_unicos": {
                "valor_num": tunel_kpis.get("clientes_unicos", 0),
                "valor_str": f"{tunel_kpis.get('clientes_unicos', 0)} clientes"
            },
            "programas_unicos": {
                "valor_num": tunel_kpis.get("programas_unicos", 0),
                "valor_str": f"{tunel_kpis.get('programas_unicos', 0)} programas"
            }
        },
        "totales_promedios": {
            "promedio_peso_carga_kg": tunel_kpis.get("promedio_peso_num", 0.0),
            "promedio_tiempo_entre_cargas_min": round(tunel_kpis.get("promedio_tiempo_seg", 0) / 60.0, 2),
            "promedio_tiempo_entre_cargas_seg": tunel_kpis.get("promedio_tiempo_seg", 0),
            "objetivo_turno_kg": int(objetivo_kg),
            "cumplimiento_objetivo_pct": cumplimiento_pct
        },
        "desglose_horario": {
            "labels": tunel_kpis.get("grafica_labels", []),
            "kg_por_hora": tunel_kpis.get("grafica_kg_hora", []),
            "cargas_por_hora": tunel_kpis.get("grafica_cargas_hora", []),
            "kg_acumulado_por_hora": tunel_kpis.get("grafica_kg_acumulado", [])
        },
        "programa_actual": tunel_kpis.get("programa_actual", "Sin cargas registradas aún")
    }

    return shift_package


def save_shift_json_package(shift_package: dict):
    """Almacena o actualiza un paquete JSON de turno en la base de datos local SQLite."""
    shift_key = shift_package["shift_key"]
    meta = shift_package["meta_info"]
    fecha = meta["fecha"]
    nombre_turno = meta["nombre_turno"]
    hora_inicio = meta["hora_inicio"]
    hora_fin = meta["hora_fin"]
    total_kg = shift_package["indicadores_ampliados"]["kg_totales_turno"]["valor_num"]
    total_cargas = shift_package["indicadores_ampliados"]["cargas_totales_turno"]["valor_num"]
    ikprod_pct = shift_package["indicadores_ampliados"]["indice_eficiencia_ikprod"]["pct_num"]
    data_json = json.dumps(shift_package, ensure_ascii=False)
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO turnos_persistencia (
            shift_key, fecha, nombre_turno, hora_inicio, hora_fin,
            total_kg, total_cargas, ikprod_pct, data_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(shift_key) DO UPDATE SET
            fecha = excluded.fecha,
            nombre_turno = excluded.nombre_turno,
            hora_inicio = excluded.hora_inicio,
            hora_fin = excluded.hora_fin,
            total_kg = excluded.total_kg,
            total_cargas = excluded.total_cargas,
            ikprod_pct = excluded.ikprod_pct,
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
    """, (shift_key, fecha, nombre_turno, hora_inicio, hora_fin, total_kg, total_cargas, ikprod_pct, data_json, now_local))

    # Guardar o actualizar en la tabla rápida de comparación: resultados_turnos
    rango_horario = f"{hora_inicio} - {hora_fin}"
    cursor.execute("""
        INSERT INTO resultados_turnos (
            shift_key, fecha, nombre_turno, rango_horario,
            total_kg, ikprod, total_cargas, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(shift_key) DO UPDATE SET
            fecha = excluded.fecha,
            nombre_turno = excluded.nombre_turno,
            rango_horario = excluded.rango_horario,
            total_kg = excluded.total_kg,
            ikprod = excluded.ikprod,
            total_cargas = excluded.total_cargas,
            updated_at = excluded.updated_at
    """, (shift_key, fecha, nombre_turno, rango_horario, total_kg, ikprod_pct, total_cargas, now_local))

    conn.commit()
    conn.close()
    return True


@router.get("/turnos/json-paquete")
def get_shift_json_package(user: dict = Depends(check_produccion_permission)):
    """Genera dinámicamente y auto-guarda en BD local el paquete JSON del turno activo."""
    pkg = build_shift_json_package()
    try:
        save_shift_json_package(pkg)
    except Exception as e:
        print(f"Error guardando paquete json: {e}")
    return pkg


@router.post("/turnos/guardar-json")
def save_current_shift_json(user: dict = Depends(check_produccion_permission)):
    """Guarda/actualiza explícitamente el paquete JSON de persistencia del turno activo en SQLite."""
    pkg = build_shift_json_package()
    success = save_shift_json_package(pkg)
    return {
        "status": "success" if success else "error",
        "shift_key": pkg["shift_key"],
        "paquete": pkg
    }


@router.get("/turnos/historial-json")
def list_shift_json_history(user: dict = Depends(check_produccion_permission)):
    """Lista todos los paquetes JSON de turnos persistidos en la base de datos local."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT shift_key, fecha, nombre_turno, hora_inicio, hora_fin, total_kg, total_cargas, ikprod_pct, updated_at
        FROM turnos_persistencia
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "shift_key": r["shift_key"],
            "fecha": r["fecha"],
            "nombre_turno": r["nombre_turno"],
            "horario": f"{r['hora_inicio']} - {r['hora_fin']}",
            "total_kg": r["total_kg"],
            "total_cargas": r["total_cargas"],
            "ikprod_pct": r["ikprod_pct"],
            "updated_at": r["updated_at"]
        })
    return {"total": len(result), "historial": result}


@router.get("/turnos/historial-json/{shift_key}")
def get_shift_json_by_key(shift_key: str, user: dict = Depends(check_produccion_permission)):
    """Recupera el paquete JSON completo de un turno específico guardado en la BD local."""
    conn = get_db_connection()
    row = conn.execute("SELECT data_json FROM turnos_persistencia WHERE shift_key = ?", (shift_key,)).fetchone()
    conn.close()

    if not row or not row["data_json"]:
        raise HTTPException(status_code=404, detail="Paquete JSON de turno no encontrado")

    return json.loads(row["data_json"])


@router.post("/turnos/force-sync")
def force_turnos_sync(admin: dict = Depends(check_produccion_permission)):
    success = sync_turnos_from_server_1()
    return {"status": "success" if success else "warning", "synced": success}


@router.get("/turnos/fechas-disponibles")
def get_available_shift_dates(user: dict = Depends(check_produccion_permission)):
    """Obtiene la lista de fechas únicas de jornadas registradas en la persistencia de turnos."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT fecha FROM turnos_persistencia
        ORDER BY fecha DESC
    """).fetchall()
    conn.close()
    
    dates = [r["fecha"] for r in rows if r["fecha"]]
    jornada_hoy = get_current_jornada_date()
    if jornada_hoy not in dates:
        dates.insert(0, jornada_hoy)
        
    return {"fechas": dates, "hoy": jornada_hoy}


@router.get("/turnos/por-fecha/{fecha}")
def get_shifts_by_date(fecha: str, user: dict = Depends(check_produccion_permission)):
    """
    Obtiene la lista de turnos de la jornada especificada.
    Carga en el selector de turnos los turnos que ya se hayan procesado y/o estén en proceso.
    """
    current_jornada = get_current_jornada_date()
    is_current_jornada = (fecha == current_jornada)
    now_dt = get_local_now().replace(tzinfo=None)

    shifts_template = get_jornada_shifts_template()
    result = []
    seen_keys = set()

    conn = get_db_connection()

    for s_info in shifts_template:
        nombre = s_info["nombre"]
        h_start = s_info["hora_inicio"]
        h_end = s_info["hora_fin"]
        shift_key = f"{fecha}_{nombre.replace(' ', '_')}"

        start_iso, end_iso = get_shift_start_end_iso(fecha, h_start, h_end)
        try:
            dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

        # Determinar si el turno está en proceso actualmente
        is_in_process = (dt_start <= now_dt < dt_end) and is_current_jornada

        # Contar cargas en la BD para el intervalo del turno
        row_cargas = conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(peso_kg), 0)
            FROM tunel_cargas
            WHERE timestamp_iso >= ? AND timestamp_iso < ?
        """, (start_iso, end_iso)).fetchone()
        
        num_cargas = row_cargas[0] if row_cargas else 0
        total_kg_db = row_cargas[1] if row_cargas else 0.0

        # Criterio: Se incluye si ya se ha procesado (tiene cargas registradas) o está en proceso
        should_include = (num_cargas > 0) or is_in_process

        if should_include:
            turno_dict = {
                "nombre": nombre,
                "fecha": fecha,
                "hora_inicio": h_start,
                "hora_fin": h_end
            }
            # Auto-construir y persistir/actualizar paquete de turno
            pkg = build_shift_json_package(turno_dict)
            save_shift_json_package(pkg)

            ind = pkg.get("indicadores_ampliados", {})
            kg_totales = ind.get("kg_totales_turno", {}).get("valor_num", total_kg_db)
            cargas_totales = ind.get("cargas_totales_turno", {}).get("valor_num", num_cargas)
            ikprod_pct = ind.get("indice_eficiencia_ikprod", {}).get("pct_num", 0.0)

            estado_label = "En proceso" if is_in_process else "Procesado"

            result.append({
                "shift_key": shift_key,
                "fecha": fecha,
                "nombre_turno": nombre,
                "horario": f"{h_start} - {h_end}",
                "total_kg": kg_totales,
                "total_cargas": cargas_totales,
                "ikprod_pct": ikprod_pct,
                "is_in_progress": is_in_process,
                "estado": estado_label,
                "updated_at": pkg.get("meta_info", {}).get("timestamp_actualizacion")
            })
            seen_keys.add(shift_key)

    # Revisar si hay otros registros persistidos previamente para esa fecha
    persisted_rows = conn.execute("""
        SELECT shift_key, fecha, nombre_turno, hora_inicio, hora_fin, total_kg, total_cargas, ikprod_pct, updated_at
        FROM turnos_persistencia
        WHERE fecha = ?
        ORDER BY hora_inicio ASC, id ASC
    """, (fecha,)).fetchall()
    conn.close()

    for r in persisted_rows:
        if r["shift_key"] not in seen_keys:
            result.append({
                "shift_key": r["shift_key"],
                "fecha": r["fecha"],
                "nombre_turno": r["nombre_turno"],
                "horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "total_kg": r["total_kg"],
                "total_cargas": r["total_cargas"],
                "ikprod_pct": r["ikprod_pct"],
                "is_in_progress": False,
                "estado": "Procesado",
                "updated_at": r["updated_at"]
            })
            seen_keys.add(r["shift_key"])

    # Ordenar cronológicamente por horario de inicio
    result.sort(key=lambda x: x["horario"])

    return {"fecha": fecha, "total": len(result), "turnos": result}


@router.get("/turnos/resultados")
def get_shift_results_summary(user: dict = Depends(check_produccion_permission)):
    """Consulta la tabla rápida de resultados de turnos (resultados_turnos) para comparaciones rápidas."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, shift_key, fecha, nombre_turno, rango_horario, total_kg, ikprod, total_cargas, updated_at
        FROM resultados_turnos
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    resultados = []
    for r in rows:
        resultados.append({
            "id": r["id"],
            "shift_key": r["shift_key"],
            "fecha": r["fecha"],
            "nombre_turno": r["nombre_turno"],
            "rango_horario": r["rango_horario"],
            "total_kg": r["total_kg"],
            "ikprod": r["ikprod"],
            "total_cargas": r["total_cargas"],
            "updated_at": r["updated_at"]
        })
    return {"total": len(resultados), "resultados": resultados}


@router.get("/turnos/resultados/por-fecha/{fecha}")
def get_shift_results_by_date(fecha: str, user: dict = Depends(check_produccion_permission)):
    """Consulta los resultados de turnos filtrados por una fecha específica."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT id, shift_key, fecha, nombre_turno, rango_horario, total_kg, ikprod, total_cargas, updated_at
        FROM resultados_turnos
        WHERE fecha = ?
        ORDER BY rango_horario ASC, id ASC
    """, (fecha,)).fetchall()
    conn.close()

    resultados = []
    for r in rows:
        resultados.append({
            "id": r["id"],
            "shift_key": r["shift_key"],
            "fecha": r["fecha"],
            "nombre_turno": r["nombre_turno"],
            "rango_horario": r["rango_horario"],
            "total_kg": r["total_kg"],
            "ikprod": r["ikprod"],
            "total_cargas": r["total_cargas"],
            "updated_at": r["updated_at"]
        })
    return {"fecha": fecha, "total": len(resultados), "resultados": resultados}


def sync_all_historical_shifts():
    """Recorre todas las fechas con registros de cargas en tunel_cargas y genera/actualiza 
    los paquetes JSON y resultados para todos los turnos históricos."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT substr(timestamp_iso, 1, 10) as f 
        FROM tunel_cargas 
        WHERE timestamp_iso IS NOT NULL AND timestamp_iso != ''
        ORDER BY f ASC
    """).fetchall()
    conn.close()

    fechas = [r["f"] for r in rows if r["f"]]
    turnos_plantilla = [
        {"nombre": "Turno 1", "hora_inicio": "06:00", "hora_fin": "14:00"},
        {"nombre": "Turno 2", "hora_inicio": "14:00", "hora_fin": "21:00"},
        {"nombre": "Turno 3", "hora_inicio": "21:00", "hora_fin": "02:00"},
        {"nombre": "Turno 4", "hora_inicio": "02:00", "hora_fin": "06:00"}
    ]

    total_synced = 0
    for fecha in fechas:
        try:
            dt_f = datetime.strptime(fecha, "%Y-%m-%d")
        except Exception:
            continue
            
        for t_info in turnos_plantilla:
            nombre = t_info["nombre"]
            h_start = t_info["hora_inicio"]
            h_end = t_info["hora_fin"]
            
            start_iso, end_iso = get_shift_start_end_iso(fecha, h_start, h_end)

            # Verificar si hay al menos 1 carga en el intervalo
            conn_check = get_db_connection()
            count_cargas = conn_check.execute("""
                SELECT COUNT(*) FROM tunel_cargas
                WHERE timestamp_iso >= ? AND timestamp_iso < ?
            """, (start_iso, end_iso)).fetchone()[0]
            conn_check.close()

            if count_cargas > 0:
                turno_dict = {
                    "nombre": nombre,
                    "fecha": fecha,
                    "hora_inicio": h_start,
                    "hora_fin": h_end
                }
                pkg = build_shift_json_package(turno_dict)
                save_shift_json_package(pkg)
                total_synced += 1

    return total_synced


@router.post("/turnos/sincronizar-historico")
def trigger_historical_sync(user: dict = Depends(check_produccion_permission)):
    """Sincroniza y pobla retroactivamente todos los turnos históricos desde la tabla tunel_cargas."""
    synced_count = sync_all_historical_shifts()
    return {
        "status": "success",
        "turnos_sincronizados": synced_count
    }


@router.get("/turnos/ranking")
def get_shifts_ranking(
    fecha_inicio: str,
    fecha_fin: str,
    criterio: str,
    user: dict = Depends(check_produccion_permission)
):
    """
    Busca y clasifica de mayor a menor los mejores 5 turnos según el criterio seleccionado 
    (ikprod, total_kg, total_cargas, kg_hora) dentro del rango [fecha_inicio, fecha_fin].
    """
    valid_criterios = {"ikprod", "total_kg", "total_cargas", "kg_hora"}
    if criterio not in valid_criterios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Criterio inválido '{criterio}'. Criterios válidos: {list(valid_criterios)}"
        )

    try:
        dt_ini = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        dt_fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de fechas inválido. Utilice YYYY-MM-DD."
        )

    if dt_fin < dt_ini:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha fin debe ser posterior o igual a la fecha inicio."
        )

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT shift_key, fecha, nombre_turno, hora_inicio, hora_fin, total_kg, total_cargas, ikprod_pct, data_json, updated_at
        FROM turnos_persistencia
        WHERE fecha >= ? AND fecha <= ?
    """, (fecha_inicio, fecha_fin)).fetchall()
    conn.close()

    turnos_evaluados = []
    for r in rows:
        data_pkg = {}
        if r["data_json"]:
            try:
                data_pkg = json.loads(r["data_json"])
            except Exception:
                pass

        ind = data_pkg.get("indicadores_ampliados", {})
        hprod_val = ind.get("productividad_hprod", {}).get("valor_num", 0)
        hprod_str = ind.get("productividad_hprod", {}).get("valor_str", "0 kg/h")

        total_kg = float(r["total_kg"] or 0.0)
        total_cargas = int(r["total_cargas"] or 0)
        ikprod = float(r["ikprod_pct"] or 0.0)

        # Si hprod no vino en el paquete, calcularlo como fallback
        if not hprod_val and total_kg > 0:
            h_start_s, h_end_s = r["hora_inicio"], r["hora_fin"]
            try:
                hs = int(h_start_s.split(":")[0])
                he = int(h_end_s.split(":")[0])
                dur = (he - hs) if he >= hs else (he + 24 - hs)
                hprod_val = int(round(total_kg / max(dur, 1.0)))
                hprod_str = f"{hprod_val:,} kg/h".replace(",", ".")
            except Exception:
                hprod_val = 0
                hprod_str = "0 kg/h"

        fecha_str = r["fecha"]
        try:
            fecha_fmt = datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            fecha_fmt = fecha_str

        # Determinar valor numérico de ordenamiento según criterio
        if criterio == "ikprod":
            criterio_val = ikprod
            criterio_label = f"{ikprod:.1f}%"
        elif criterio == "total_kg":
            criterio_val = total_kg
            criterio_label = f"{total_kg:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", ".")
        elif criterio == "total_cargas":
            criterio_val = total_cargas
            criterio_label = f"{total_cargas} cargas"
        elif criterio == "kg_hora":
            criterio_val = hprod_val
            criterio_label = hprod_str

        turnos_evaluados.append({
            "shift_key": r["shift_key"],
            "fecha": fecha_str,
            "fecha_formateada": fecha_fmt,
            "nombre_turno": r["nombre_turno"],
            "rango_horario": f"{r['hora_inicio']} - {r['hora_fin']}",
            "criterio_seleccionado": criterio,
            "criterio_valor": criterio_val,
            "criterio_label": criterio_label,
            "total_kg": total_kg,
            "total_kg_str": f"{total_kg:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "total_cargas": total_cargas,
            "total_cargas_str": f"{total_cargas} cargas",
            "ikprod": ikprod,
            "ikprod_str": f"{ikprod:.1f}%",
            "hprod": hprod_val,
            "hprod_str": hprod_str,
            "updated_at": r["updated_at"]
        })

    # Ordenar de mayor a menor y tomar el Top 5
    turnos_evaluados.sort(key=lambda x: x["criterio_valor"], reverse=True)
    top_5 = turnos_evaluados[:5]

    for idx, item in enumerate(top_5, 1):
        item["posicion"] = idx

    criterio_titulos = {
        "ikprod": "Índice de Eficiencia (ikProd)",
        "total_kg": "Kg Totales Procesados",
        "total_cargas": "Cargas Totales",
        "kg_hora": "Productividad (Kg / Hora)"
    }

    return {
        "status": "success",
        "criterio": criterio,
        "criterio_titulo": criterio_titulos.get(criterio, criterio),
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_turnos_evaluados": len(turnos_evaluados),
        "ranking": top_5
    }

@router.get("/turnos/totales-periodo")
def get_totales_periodo(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00",
    current_user: dict = Depends(check_produccion_permission)
):
    """
    Calcula los totales consolidados de un período concatenando los turnos comprendidos en la ventana seleccionada.
    No se toman en cuenta baches de tiempo intermedios (ej: fines de semana o noches sin producción).
    Los turnos incluidos se asumen contiguos para el cálculo de horas efectivas y kg/hora.
    """
    if not fecha_fin:
        fecha_fin = fecha_inicio

    try:
        dt_start = datetime.strptime(f"{fecha_inicio} {hora_inicio}:00", "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.strptime(f"{fecha_fin} {hora_fin}:00", "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de fecha u hora inválido: {e}"
        )

    if dt_end <= dt_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha y hora de fin debe ser posterior a la fecha y hora de inicio."
        )

    window_start_str = dt_start.strftime("%Y-%m-%d %H:%M:%S")
    window_end_str = dt_end.strftime("%Y-%m-%d %H:%M:%S")

    # Consultar turnos_persistencia con margen de 1 día antes y 1 día después para cubrir turnos nocturnos
    q_start_date = (dt_start - timedelta(days=1)).strftime("%Y-%m-%d")
    q_end_date = (dt_end + timedelta(days=1)).strftime("%Y-%m-%d")

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT shift_key, fecha, nombre_turno, hora_inicio, hora_fin, total_kg, total_cargas, ikprod_pct, data_json, updated_at
        FROM turnos_persistencia
        WHERE fecha >= ? AND fecha <= ?
        ORDER BY fecha ASC, hora_inicio ASC
    """, (q_start_date, q_end_date)).fetchall()
    conn.close()

    turnos_concatenados = []
    total_kg_acum = 0.0
    total_cargas_acum = 0
    total_segundos_efectivos = 0.0

    for r in rows:
        shift_start_iso, shift_end_iso = get_shift_start_end_iso(r["fecha"], r["hora_inicio"], r["hora_fin"])
        
        # Verificar si el turno cae dentro de la ventana de tiempo escogida (intersección)
        if shift_end_iso > window_start_str and shift_start_iso < window_end_str:
            t_kg = float(r["total_kg"] or 0.0)
            t_cargas = int(r["total_cargas"] or 0)
            ikprod = float(r["ikprod_pct"] or 0.0)

            # Duración del turno sin considerar baches entre turnos
            try:
                dt_s = datetime.strptime(shift_start_iso, "%Y-%m-%d %H:%M:%S")
                dt_e = datetime.strptime(shift_end_iso, "%Y-%m-%d %H:%M:%S")
                dur_seg = max((dt_e - dt_s).total_seconds(), 60.0)
            except Exception:
                dur_seg = 8 * 3600.0

            dur_horas = dur_seg / 3600.0
            
            # Obtener hprod del turno
            data_pkg = {}
            if r["data_json"]:
                try:
                    data_pkg = json.loads(r["data_json"])
                except Exception:
                    pass
            ind = data_pkg.get("indicadores_ampliados", {})
            hprod_val = ind.get("productividad_hprod", {}).get("valor_num")
            if not hprod_val and t_kg > 0 and dur_horas > 0:
                hprod_val = int(round(t_kg / dur_horas))

            total_kg_acum += t_kg
            total_cargas_acum += t_cargas
            total_segundos_efectivos += dur_seg

            turnos_concatenados.append({
                "shift_key": r["shift_key"],
                "fecha": r["fecha"],
                "fecha_formateada": datetime.strptime(r["fecha"], "%Y-%m-%d").strftime("%d/%m/%Y") if "-" in r["fecha"] else r["fecha"],
                "nombre_turno": r["nombre_turno"],
                "hora_inicio": r["hora_inicio"],
                "hora_fin": r["hora_fin"],
                "rango_horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "duracion_horas": round(dur_horas, 1),
                "total_kg": t_kg,
                "total_kg_str": f"{t_kg:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "total_cargas": t_cargas,
                "total_cargas_str": f"{t_cargas} cargas",
                "ikprod": ikprod,
                "ikprod_str": f"{ikprod:.1f}%",
                "hprod": hprod_val or 0,
                "hprod_str": f"{(hprod_val or 0):,} kg/h".replace(",", ".")
            })

    total_horas_efectivas = total_segundos_efectivos / 3600.0
    total_minutos_efectivos = total_segundos_efectivos / 60.0

    # Kg/Hora del período (kilos totales / horas efectivas de turnos concatenados)
    if total_horas_efectivas > 0 and total_kg_acum > 0:
        kg_hora_periodo = int(round(total_kg_acum / total_horas_efectivas))
    else:
        kg_hora_periodo = 0

    # ikProd General del período
    if total_cargas_acum > 0:
        promedio_peso_periodo = round(total_kg_acum / total_cargas_acum, 1)
        promedio_tiempo_min_periodo = round(total_minutos_efectivos / total_cargas_acum, 2)
        ikprod_neto_periodo = round(promedio_peso_periodo / max(promedio_tiempo_min_periodo, 0.01), 2)
        ikprod_general_pct = round((ikprod_neto_periodo / 30.0) * 100.0, 1)
    else:
        promedio_peso_periodo = 0.0
        promedio_tiempo_min_periodo = 0.0
        ikprod_neto_periodo = 0.0
        ikprod_general_pct = 0.0

    # Semáforo ikProd
    if ikprod_general_pct < 30.0:
        color_code = "red"
        gradient = "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)"
        subtexto_color = "#f87171"
        text_color = "#ef4444"
        border_color = "#ef4444"
    elif 30.0 <= ikprod_general_pct <= 60.0:
        color_code = "orange"
        gradient = "linear-gradient(135deg, #ea580c 0%, #c2410c 100%)"
        subtexto_color = "#fb923c"
        text_color = "#f97316"
        border_color = "#f97316"
    else:
        color_code = "green"
        gradient = "linear-gradient(135deg, #10b981 0%, #059669 100%)"
        subtexto_color = "#6ee7b7"
        text_color = "#34d399"
        border_color = "#10b981"

    horas_int = int(total_horas_efectivas)
    minutos_rem = int(round((total_horas_efectivas - horas_int) * 60))

    return {
        "status": "success",
        "ventana_solicitada": {
            "fecha_inicio": fecha_inicio,
            "hora_inicio": hora_inicio,
            "fecha_fin": fecha_fin,
            "hora_fin": hora_fin,
            "inicio_iso": window_start_str,
            "fin_iso": window_end_str,
            "inicio_formateado": f"{datetime.strptime(fecha_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')} {hora_inicio}",
            "fin_formateado": f"{datetime.strptime(fecha_fin, '%Y-%m-%d').strftime('%d/%m/%Y')} {hora_fin}"
        },
        "totales": {
            "total_turnos": len(turnos_concatenados),
            "total_kg": round(total_kg_acum, 1),
            "total_kg_str": f"{total_kg_acum:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "total_cargas": total_cargas_acum,
            "total_cargas_str": f"{total_cargas_acum} cargas",
            "kg_hora": kg_hora_periodo,
            "kg_hora_str": f"{kg_hora_periodo:,} kg/h".replace(",", "."),
            "horas_efectivas": round(total_horas_efectivas, 1),
            "horas_efectivas_str": f"{horas_int}h {minutos_rem}m ({round(total_horas_efectivas, 1)}h)",
            "promedio_peso": promedio_peso_periodo,
            "promedio_peso_str": f"{promedio_peso_periodo} kg/carga",
            "promedio_tiempo_min": promedio_tiempo_min_periodo,
            "promedio_tiempo_str": f"{promedio_tiempo_min_periodo} min/carga ({int(round(promedio_tiempo_min_periodo * 60))}s)",
            "ikprod": {
                "pct": ikprod_general_pct,
                "pct_str": f"{ikprod_general_pct:.1f}%",
                "neto": ikprod_neto_periodo,
                "neto_str": f"ikProd Neto: {ikprod_neto_periodo:.2f}",
                "color_code": color_code,
                "gradient": gradient,
                "subtexto_color": subtexto_color,
                "text_color": text_color,
                "border_color": border_color
            }
        },
        "turnos_concatenados": turnos_concatenados
    }





