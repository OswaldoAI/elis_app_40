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
    """
    Retorna la lista de turnos programados para la jornada según la aplicación
    de programación de turnos (http://192.168.0.137:5001).
    Solo incluye los turnos que están realmente programados (no se agregan turnos inexistentes como Turno 4).
    """
    turnos_cache = get_cached_turnos()
    cached_shifts = turnos_cache.get("shifts") or []

    if cached_shifts:
        shifts = []
        for idx, s in enumerate(cached_shifts):
            nombre = s.get("name") or s.get("nombre") or f"Turno {idx + 1}"
            h_start = s.get("start") or s.get("hora_inicio") or "06:00"
            h_end = s.get("end") or s.get("hora_fin") or "14:00"
            shifts.append({
                "nombre": nombre,
                "hora_inicio": str(h_start)[:5],
                "hora_fin": str(h_end)[:5]
            })
        return shifts

    # Fallback predeterminado estándar de la planta (3 turnos) si la API no estuviese accesible
    return [
        {"nombre": "Turno 1", "hora_inicio": "06:00", "hora_fin": "14:00"},
        {"nombre": "Turno 2", "hora_inicio": "14:00", "hora_fin": "21:00"},
        {"nombre": "Turno 3", "hora_inicio": "21:00", "hora_fin": "02:00"}
    ]

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
            WHERE timestamp_iso >= ? AND timestamp_iso <= ? AND load_id IS NOT NULL AND peso_kg > 0
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
                WHERE timestamp_iso >= ? AND timestamp_iso < ? AND load_id IS NOT NULL AND peso_kg > 0
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
            last_carga = conn.execute("SELECT cliente, categoria, peso_kg, timestamp FROM tunel_cargas WHERE load_id IS NOT NULL AND peso_kg > 0 ORDER BY id DESC LIMIT 1").fetchone()
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
    vt_data = get_tunel_vt_production(turno_act)

    # Consolidado del día completo (desde el inicio de la jornada a las 06:00)
    inicio_jornada = f"{fecha_raw} 06:00:00"
    conn_sum = get_db_connection()
    try:
        row_kl_hoy = conn_sum.execute("""
            SELECT COALESCE(SUM(peso_kg), 0)
            FROM tunel_cargas
            WHERE timestamp_iso >= ? AND load_id IS NOT NULL AND peso_kg > 0
        """, (inicio_jornada,)).fetchone()
        kilos_lavados_hoy = round(float(row_kl_hoy[0])) if row_kl_hoy and row_kl_hoy[0] else int(tunel_kpis.get("total_kg_num", 0))

        # Sincronizar turno actual de calandras para que persista
        try:
            if is_shift_active(turno_act):
                pkg2 = build_calandra_shift_json("CALANDRA_2", fecha_raw, turno_act)
                save_calandra_shift_json(pkg2)
                pkg3 = build_calandra_shift_json("CALANDRA_3", fecha_raw, turno_act)
                save_calandra_shift_json(pkg3)
        except Exception:
            pass

        row_c2 = conn_sum.execute("""
            SELECT COALESCE(SUM(kgs_totales), 0)
            FROM calandra_2_turnos_persistencia
            WHERE fecha = ? AND UPPER(nombre_turno) NOT LIKE '%FUERA%' AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
        """, (fecha_raw,)).fetchone()
        kg_c2_hoy = round(float(row_c2[0]), 1) if row_c2 else 0.0

        row_c3 = conn_sum.execute("""
            SELECT COALESCE(SUM(kgs_totales), 0)
            FROM calandra_3_turnos_persistencia
            WHERE fecha = ? AND UPPER(nombre_turno) NOT LIKE '%FUERA%' AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
        """, (fecha_raw,)).fetchone()
        kg_c3_hoy = round(float(row_c3[0]), 1) if row_c3 else 0.0

        kilos_calandras_hoy = round(kg_c2_hoy + kg_c3_hoy, 1)

        def _fmt_kg_str(val: float) -> str:
            p = f"{val:,.1f}".split(".")
            int_part = p[0].replace(",", ".")
            dec_part = p[1]
            return f"{int_part} kg" if dec_part == "0" else f"{int_part},{dec_part} kg"

        kilos_cal2_hoy_str = _fmt_kg_str(kg_c2_hoy)
        kilos_cal3_hoy_str = _fmt_kg_str(kg_c3_hoy)
    except Exception as e:
        logger.error(f"Error calculando consolidados hoy en summary: {e}")
        kilos_lavados_hoy = int(tunel_kpis.get("total_kg_num", 0))
        kilos_calandras_hoy = 0
        kilos_cal2_hoy_str = "0 kg"
        kilos_cal3_hoy_str = "0 kg"
    finally:
        conn_sum.close()

    return {
        "status": "online",
        "planta": "ELIS NÁJERA 4.0",
        "kilos_lavados_hoy": kilos_lavados_hoy,
        "kilos_calandras_hoy": kilos_calandras_hoy,
        "kilos_cal2_hoy_str": kilos_cal2_hoy_str,
        "kilos_cal3_hoy_str": kilos_cal3_hoy_str,
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
                "estado": ("En Tiempo Valle" if vt_data["en_valle"] else "Operativa") if vt_data.get("is_turno_activo") else "Sin Turno Activo",
                "icono": "fa-wind",
                "oee": 88.7,
                "clickable": True,
                "dashboard_url": "#tunel_vt",
                "turno_info": {
                    "nombre": nombre_turno if vt_data.get("is_turno_activo") else "Sin Turno Activo",
                    "horario": horario_con_fecha if vt_data.get("is_turno_activo") else f"Fuera de Turno | {fecha_formateada}",
                    "fecha": fecha_formateada,
                    "is_active": vt_data.get("is_turno_activo", False)
                },
                "produccion_tunel_vt": vt_data,
                "metricas_clave": [
                    {"label": "Prendas Totales", "val": vt_data["prendas_totales_str"]},
                    {"label": "Kgs Totales", "val": vt_data["kgs_totales_str"]},
                    {"label": "Cadencia", "val": vt_data["prendas_hora_str"]},
                    {"label": "Tiempo Valle", "val": vt_data["tiempo_valle_total_str"]}
                ],
                "progreso_carga": 82,
                "programa_actual": "Conteo 3 Vías + Tiempos Valles (MQTT)" if vt_data.get("is_turno_activo") else "Sin Turno en Proceso"
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
    """Informa sobre el estado de la sincronización de turnos desde http://192.168.0.137:5001."""
    cached = get_cached_turnos()
    return {
        "status": "success",
        "fuente_principal": "http://192.168.0.137:5001",
        "intervalo_sincronizacion_seg": 1800,
        "intervalo_sincronizacion_min": 30,
        "cache_actualizado_el": cached.get("cache_updated_at"),
        "sincronizado_desde": cached.get("synced_from_url") or "http://192.168.0.137:5001",
        "jornada": cached.get("jornada"),
        "turno_actual": cached.get("turno_actual"),
        "is_shift_active": is_shift_active(cached.get("turno_actual", {})),
        "turnos_jornada": cached.get("shifts", [])
    }

@router.post("/turnos/sync-now")
def trigger_turnos_sync_now(user: dict = Depends(check_produccion_permission)):
    """Fuerza una sincronización inmediata desde la aplicación de turnos (http://192.168.0.137:5001)."""
    ok = sync_turnos_from_server_1()
    cached = get_cached_turnos()
    return {
        "status": "success" if ok else "warning",
        "message": "Turnos sincronizados correctamente desde http://192.168.0.137:5001" if ok else "No se pudo contactar http://192.168.0.137:5001, usando caché",
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
        "grafica_hora_a_hora": prod.get("grafica_hora_a_hora", {}),
        "comparacion_5002": prod.get("comparacion_5002", {})
    }


@router.get("/calandras/{maquina_id}/comparar-5002")
def get_calandra_comparar_5002(maquina_id: str, user: dict = Depends(check_produccion_permission)):
    """
    Retorna la auditoría comparativa hora a hora entre los datos calculados
    exclusivamente desde MQTT y la API del puerto 5002.
    """
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    turnos_cache = get_cached_turnos()
    turno_act = turnos_cache.get("turno_actual", {})
    prod_mqtt = get_calandra_production(m_id, turno_act)
    return compare_calandra_mqtt_vs_5002(m_id, prod_mqtt, turno_act)


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


def get_shift_breaks(turno_data: dict = None) -> list:
    """
    Obtiene la lista de descansos programados consultando dinámicamente
    la caché de la aplicación de turnos (http://192.168.0.137:5001/api/turnos/jornada).
    Los descansos NO son fijos y se adaptan automáticamente a cualquier cambio semanal.
    """
    turnos_cache = get_cached_turnos()
    cached_breaks = turnos_cache.get("breaks", [])

    if cached_breaks:
        cleaned = []
        for b in cached_breaks:
            b_copy = dict(b)
            start_str = b_copy.get("start") or b_copy.get("inicio")
            end_str = b_copy.get("end") or b_copy.get("fin")
            dur = b_copy.get("durationMinutes") or b_copy.get("duracion_min")

            if not start_str:
                continue

            try:
                sh, sm = map(int, start_str.split(":")[:2])
                if dur and float(dur) > 0:
                    dur_min = float(dur)
                    tot_m = sm + int(round(dur_min))
                    eh = (sh + (tot_m // 60)) % 24
                    em = tot_m % 60
                    b_copy["durationMinutes"] = dur_min
                    b_copy["end"] = f"{eh:02d}:{em:02d}"
                elif end_str:
                    eh, em = map(int, end_str.split(":")[:2])
                    dur_min = (eh * 60 + em) - (sh * 60 + sm)
                    if dur_min <= 0:
                        dur_min += 24 * 60
                    b_copy["durationMinutes"] = float(dur_min)
                    b_copy["end"] = end_str
                else:
                    b_copy["durationMinutes"] = 30.0
                    b_copy["end"] = f"{sh:02d}:{(sm+30)%60:02d}"

                cleaned.append(b_copy)
            except Exception:
                cleaned.append(b_copy)

        if cleaned:
            return cleaned

    # Fallback secundario de respaldo únicamente si la API de turnos no responde o no devuelve descansos
    return [
        {"name": "Descanso 1", "start": "10:00", "end": "10:30", "durationMinutes": 30, "shiftIndex": 0},
        {"name": "Descanso 2", "start": "18:00", "end": "18:20", "durationMinutes": 20, "shiftIndex": 1}
    ]


def get_break_overlap_for_slot(s_start_iso: str, s_end_iso: str, breaks: list) -> float:
    """Calcula los minutos de descanso programado que caen dentro del slot horario."""
    if not s_start_iso or not s_end_iso or not breaks:
        return 0.0

    dt_start = None
    dt_end = None
    clean_start = s_start_iso.replace('T', ' ')
    clean_end = s_end_iso.replace('T', ' ')

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            if not dt_start:
                dt_start = datetime.strptime(clean_start[:19], fmt)
        except Exception:
            pass
        try:
            if not dt_end:
                dt_end = datetime.strptime(clean_end[:19], fmt)
        except Exception:
            pass

    if not dt_start or not dt_end:
        return 0.0

    total_break_min = 0.0
    for b in breaks:
        b_start_str = b.get("start") or b.get("inicio") or b.get("hora_inicio")
        b_end_str = b.get("end") or b.get("fin") or b.get("hora_fin")
        dur = b.get("durationMinutes") or b.get("duracion_min")

        if not b_start_str:
            continue

        try:
            bh, bm = map(int, b_start_str.split(":")[:2])
            b_start_dt = dt_start.replace(hour=bh, minute=bm, second=0, microsecond=0)

            if dur and dur > 0:
                b_end_dt = b_start_dt + timedelta(minutes=float(dur))
            elif b_end_str:
                eh, em = map(int, b_end_str.split(":")[:2])
                b_end_dt = dt_start.replace(hour=eh, minute=em, second=0, microsecond=0)
                if b_end_dt <= b_start_dt:
                    b_end_dt += timedelta(days=1)
            else:
                continue

            o_start = max(dt_start, b_start_dt)
            o_end = min(dt_end, b_end_dt)
            if o_end > o_start:
                total_break_min += (o_end - o_start).total_seconds() / 60.0
        except Exception:
            pass
    return round(total_break_min, 1)


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

    # Utilizar el cálculo unificado y validado desde MQTT
    prod_live = get_calandra_production(m_id, shift_data)
    labels = prod_live.get("grafica_hora_a_hora", {}).get("labels", [])
    prendas = prod_live.get("grafica_hora_a_hora", {}).get("prendas", [])
    valle = prod_live.get("grafica_hora_a_hora", {}).get("tiempo_valle", [])
    descanso = prod_live.get("grafica_hora_a_hora", {}).get("tiempo_descanso", [0.0] * len(labels))
    valle_raw = prod_live.get("grafica_hora_a_hora", {}).get("tiempo_valle_raw", valle)
    grandes = prod_live.get("grafica_hora_a_hora", {}).get("grandes") or [0] * len(labels)
    pequenas = prod_live.get("grafica_hora_a_hora", {}).get("pequenas") or [0] * len(labels)

    tot_prendas = prod_live.get("prendas_totales", 0)
    tot_kg = prod_live.get("kgs_totales", 0.0)
    tot_valle = prod_live.get("tiempo_valle_min", 0.0)

    if m_id == "CALANDRA_2":
        desg = prod_live.get("desglose_calandra2") or {}
        tot_grandes = desg.get("prendas_grandes", 0)
        tot_pequenas = desg.get("prendas_pequenas", 0)
        kg_grandes = desg.get("kg_grandes", 0.0)
        kg_pequenas = desg.get("kg_pequenas", 0.0)
    else:
        tot_grandes = 0
        tot_pequenas = 0
        kg_grandes = 0.0
        kg_pequenas = 0.0

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
        p_gra_unit = float(desg.get("peso_unitario_grandes") or 0.780)
        p_peq_unit = float(desg.get("peso_unitario_pequenas") or 0.470)
        desglose_cal2 = {
            "prendas_grandes": tot_grandes,
            "prendas_grandes_str": f"{tot_grandes:,}".replace(",", ".") + " grandes",
            "prendas_pequenas": tot_pequenas,
            "prendas_pequenas_str": f"{tot_pequenas:,}".replace(",", ".") + " pequeñas",
            "kg_grandes": kg_grandes,
            "kg_grandes_str": f"{kg_grandes:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "kg_pequenas": kg_pequenas,
            "kg_pequenas_str": f"{kg_pequenas:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "peso_unitario_grandes": p_gra_unit,
            "peso_unitario_grandes_str": f"{int(round(p_gra_unit * 1000))} gr ({p_gra_unit:.3f} kg)",
            "peso_unitario_pequenas": p_peq_unit,
            "peso_unitario_pequenas_str": f"{int(round(p_peq_unit * 1000))} gr ({p_peq_unit:.3f} kg)",
            "tiempo_valle_grandes": tot_valle,
            "tiempo_valle_grandes_str": f"{tot_valle:.1f} min",
            "tiempo_valle_pequenas": tot_valle,
            "tiempo_valle_pequenas_str": f"{tot_valle:.1f} min",
            "prendas_grandes_hora": g_h,
            "prendas_grandes_hora_str": f"{g_h:,} g/h".replace(",", "."),
            "prendas_pequenas_hora": p_h,
            "prendas_pequenas_hora_str": f"{p_h:,} p/h".replace(",", ".")
        }

    p_c3_unit = float(prod_live.get("peso_unitario") or 1.180)

    indicadores_res = {
        "prendas_totales": tot_prendas,
        "prendas_totales_str": prendas_totales_str,
        "kgs_totales": tot_kg,
        "kgs_totales_str": kgs_totales_str,
        "tiempo_valle_min": tot_valle,
        "tiempo_valle_str": tiempo_valle_str,
        "tiempo_descanso_min": prod_live.get("tiempo_descanso_min", 0.0),
        "tiempo_descanso_str": prod_live.get("tiempo_descanso_str", "0,0 min"),
        "prendas_hora": prendas_h,
        "prendas_hora_str": prendas_hora_str,
        "kg_hora": kg_h,
        "kg_hora_str": kg_hora_str,
        "en_valle": False,
        "desglose_calandra2": desglose_cal2
    }

    if m_id == "CALANDRA_2":
        indicadores_res["peso_grandes"] = p_gra_unit
        indicadores_res["peso_grandes_gr"] = int(round(p_gra_unit * 1000))
        indicadores_res["peso_pequenas"] = p_peq_unit
        indicadores_res["peso_pequenas_gr"] = int(round(p_peq_unit * 1000))
    else:
        indicadores_res["peso_unitario"] = p_c3_unit
        indicadores_res["peso_unitario_gr"] = int(round(p_c3_unit * 1000))
        indicadores_res["peso_unitario_str"] = f"{int(round(p_c3_unit * 1000))} gr ({p_c3_unit:.3f} kg)"

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
        "indicadores_dashboard": indicadores_res,
        "desglose_hora_a_hora": {
            "labels": labels,
            "prendas": prendas,
            "tiempo_valle": valle,
            "tiempo_valle_min": valle,
            "tiempo_descanso": descanso,
            "tiempo_descanso_min": descanso,
            "tiempo_valle_raw": valle_raw,
            "tiempo_valle_raw_min": valle_raw,
            "grandes": grandes if m_id == "CALANDRA_2" else None,
            "pequenas": pequenas if m_id == "CALANDRA_2" else None
        }
    }


def save_calandra_shift_json(shift_package: dict) -> bool:
    """Almacena o actualiza un paquete JSON de turno para Calandras en SQLite, en tablas separadas por máquina."""
    shift_key = shift_package["shift_key"]
    maquina = shift_package["maquina"].upper()
    fecha = shift_package["fecha"]
    turno_identificador = shift_package["turno_identificador"]
    meta = shift_package.get("meta_info", {})
    nombre_turno = meta.get("nombre_turno", turno_identificador)
    hora_inicio = shift_package["hora_inicio"]
    hora_fin = shift_package["hora_fin"]
    rango_horario = shift_package.get("rango_horario", f"{hora_inicio} - {hora_fin}")

    # Validación estricta: NO persistir registros inválidos de 'fuera de turno', 'sin turno' o inactivos
    nombre_upper = (nombre_turno or "").upper()
    key_upper = (shift_key or "").upper()
    if any(x in nombre_upper or x in key_upper for x in ["FUERA", "SIN TURNO", "SIN_TURNO", "INACTIVO"]):
        return False

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

    if maquina == "CALANDRA_2":
        desg = ind.get("desglose_calandra2") or {}
        p_grandes = int(desg.get("prendas_grandes", 0))
        p_pequenas = int(desg.get("prendas_pequenas", 0))
        kg_grandes = float(desg.get("kg_grandes", 0.0))
        kg_pequenas = float(desg.get("kg_pequenas", 0.0))
        v_grandes = float(desg.get("tiempo_valle_grandes", tiempo_valle_min))
        v_pequenas = float(desg.get("tiempo_valle_pequenas", tiempo_valle_min))

        cursor.execute("""
            INSERT INTO calandra_2_turnos_persistencia (
                shift_key, fecha, turno_identificador, nombre_turno,
                hora_inicio, hora_fin, rango_horario,
                prendas_totales, prendas_grandes, prendas_pequenas,
                kgs_totales, kg_grandes, kg_pequenas,
                tiempo_valle_min, tiempo_valle_grandes_min, tiempo_valle_pequenas_min,
                prendas_hora, kg_hora, data_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shift_key) DO UPDATE SET
                fecha = excluded.fecha,
                turno_identificador = excluded.turno_identificador,
                nombre_turno = excluded.nombre_turno,
                hora_inicio = excluded.hora_inicio,
                hora_fin = excluded.hora_fin,
                rango_horario = excluded.rango_horario,
                prendas_totales = excluded.prendas_totales,
                prendas_grandes = excluded.prendas_grandes,
                prendas_pequenas = excluded.prendas_pequenas,
                kgs_totales = excluded.kgs_totales,
                kg_grandes = excluded.kg_grandes,
                kg_pequenas = excluded.kg_pequenas,
                tiempo_valle_min = excluded.tiempo_valle_min,
                tiempo_valle_grandes_min = excluded.tiempo_valle_grandes_min,
                tiempo_valle_pequenas_min = excluded.tiempo_valle_pequenas_min,
                prendas_hora = excluded.prendas_hora,
                kg_hora = excluded.kg_hora,
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (
            shift_key, fecha, turno_identificador, nombre_turno,
            hora_inicio, hora_fin, rango_horario,
            prendas_totales, p_grandes, p_pequenas,
            kgs_totales, kg_grandes, kg_pequenas,
            tiempo_valle_min, v_grandes, v_pequenas,
            prendas_hora, kg_hora, data_json, now_local
        ))
    elif maquina == "CALANDRA_3":
        peso_u = float(ind.get("peso_unitario") or 1.180)
        cursor.execute("""
            INSERT INTO calandra_3_turnos_persistencia (
                shift_key, fecha, turno_identificador, nombre_turno,
                hora_inicio, hora_fin, rango_horario,
                prendas_totales, kgs_totales, tiempo_valle_min,
                peso_unitario, prendas_hora, kg_hora, data_json, updated_at
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
                peso_unitario = excluded.peso_unitario,
                prendas_hora = excluded.prendas_hora,
                kg_hora = excluded.kg_hora,
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        """, (
            shift_key, fecha, turno_identificador, nombre_turno,
            hora_inicio, hora_fin, rango_horario,
            prendas_totales, kgs_totales, tiempo_valle_min,
            peso_u, prendas_hora, kg_hora, data_json, now_local
        ))

    # Guardar también en tabla unificada de compatibilidad
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
    """Consulta la lista de turnos guardados en SQLite para Calandra 2 o Calandra 3 desde su tabla separada."""
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no válida")

    table_name = "calandra_2_turnos_persistencia" if m_id == "CALANDRA_2" else "calandra_3_turnos_persistencia"
    conn = get_db_connection()
    if fecha:
        rows = conn.execute(f"""
            SELECT shift_key, fecha, turno_identificador, nombre_turno,
                   hora_inicio, hora_fin, rango_horario,
                   prendas_totales, kgs_totales, tiempo_valle_min,
                   prendas_hora, kg_hora, updated_at
            FROM {table_name}
            WHERE fecha = ?
              AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
              AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
              AND UPPER(shift_key) NOT LIKE '%FUERA%'
            ORDER BY hora_inicio ASC
        """, (fecha,)).fetchall()
    else:
        rows = conn.execute(f"""
            SELECT shift_key, fecha, turno_identificador, nombre_turno,
                   hora_inicio, hora_fin, rango_horario,
                   prendas_totales, kgs_totales, tiempo_valle_min,
                   prendas_hora, kg_hora, updated_at
            FROM {table_name}
            WHERE UPPER(nombre_turno) NOT LIKE '%FUERA%' 
              AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
              AND UPPER(shift_key) NOT LIKE '%FUERA%'
            ORDER BY fecha DESC, hora_inicio ASC
        """).fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "shift_key": r["shift_key"],
            "maquina": m_id,
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
    table_name = "calandra_2_turnos_persistencia" if m_id == "CALANDRA_2" else "calandra_3_turnos_persistencia"
    conn = get_db_connection()
    row = conn.execute(f"SELECT data_json FROM {table_name} WHERE shift_key = ?", (shift_key,)).fetchone()
    if not row:
        row = conn.execute("SELECT data_json FROM calandras_turnos_persistencia WHERE maquina = ? AND shift_key = ?", (m_id, shift_key)).fetchone()
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
    """Retorna la lista de fechas disponibles con registros de producción o turnos guardados en SQLite."""
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no válida")

    table_name = "calandra_2_turnos_persistencia" if m_id == "CALANDRA_2" else "calandra_3_turnos_persistencia"
    conn = get_db_connection()
    rows_prod = conn.execute("SELECT DISTINCT substr(timestamp_iso, 1, 10) as f FROM calandras_produccion WHERE maquina = ? ORDER BY f DESC", (m_id,)).fetchall()
    rows_turnos = conn.execute(f"SELECT DISTINCT fecha as f FROM {table_name} ORDER BY f DESC").fetchall()
    conn.close()

    fechas = sorted(list(set([r["f"] for r in rows_prod if r["f"]] + [r["f"] for r in rows_turnos if r["f"]])), reverse=True)
    jornada_hoy = get_current_jornada_date()
    if jornada_hoy not in fechas:
        fechas.insert(0, jornada_hoy)

    return {
        "status": "success",
        "maquina": m_id,
        "fechas": fechas,
        "hoy": jornada_hoy
    }


@router.get("/calandras/{maquina_id}/turnos-por-fecha/{fecha}")
def get_calandra_shifts_by_date(
    maquina_id: str,
    fecha: str,
    user: dict = Depends(check_produccion_permission)
):
    """
    Obtiene la lista de turnos de la jornada especificada para Calandra 2 o Calandra 3.
    Reconstruye los indicadores y guarda/actualiza el paquete JSON en la tabla separada de la máquina.
    """
    m_id = maquina_id.upper()
    if m_id not in ["CALANDRA_2", "CALANDRA_3"]:
        raise HTTPException(status_code=404, detail="Máquina no válida")

    table_name = "calandra_2_turnos_persistencia" if m_id == "CALANDRA_2" else "calandra_3_turnos_persistencia"
    current_jornada = get_current_jornada_date()
    is_current_jornada = (fecha == current_jornada)
    now_dt = get_local_now().replace(tzinfo=None)

    shifts_template = get_jornada_shifts_template()
    result = []
    seen_keys = set()

    conn = get_db_connection()

    for idx, s_info in enumerate(shifts_template):
        nombre = s_info["nombre"]
        nombre_upper = (nombre or "").upper()
        if any(x in nombre_upper for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

        h_start = s_info["hora_inicio"]
        h_end = s_info["hora_fin"]
        turno_id = f"Turno {idx + 1}"
        shift_key = f"{m_id}_{fecha}_{turno_id.replace(' ', '_')}"

        start_iso, end_iso = get_shift_start_end_iso(fecha, h_start, h_end)
        try:
            dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

        is_in_process = (dt_start <= now_dt < dt_end) and is_current_jornada

        # Contar producción en la BD para el intervalo del turno
        row_prod = conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(delta_total), 0)
            FROM calandras_produccion
            WHERE maquina = ? AND timestamp_iso >= ? AND timestamp_iso < ?
        """, (m_id, start_iso, end_iso)).fetchone()

        num_records = row_prod[0] if row_prod else 0
        total_prendas_db = row_prod[1] if row_prod else 0

        # Criterio: Se incluye si tiene producción registrada o está en proceso actualmente
        should_include = (total_prendas_db > 0) or is_in_process

        if should_include:
            turno_dict = {
                "nombre": turno_id,
                "fecha": fecha,
                "hora_inicio": h_start,
                "hora_fin": h_end,
                "is_active": is_in_process
            }
            pkg = build_calandra_shift_json(m_id, fecha=fecha, shift_data=turno_dict, turno_numero=idx+1)
            save_calandra_shift_json(pkg)

            ind = pkg.get("indicadores_dashboard", {})
            p_tot = ind.get("prendas_totales", 0)
            kg_tot = ind.get("kgs_totales", 0.0)
            valle_min = ind.get("tiempo_valle_min", 0.0)

            result.append({
                "shift_key": shift_key,
                "maquina": m_id,
                "fecha": fecha,
                "turno_identificador": turno_id,
                "nombre_turno": nombre,
                "horario": f"{h_start} - {h_end}",
                "prendas_totales": p_tot,
                "prendas_totales_str": ind.get("prendas_totales_str", f"{p_tot} prendas"),
                "kgs_totales": kg_tot,
                "kgs_totales_str": ind.get("kgs_totales_str", f"{kg_tot} kg"),
                "tiempo_valle_min": valle_min,
                "tiempo_valle_str": ind.get("tiempo_valle_str", f"{valle_min} min"),
                "prendas_hora": ind.get("prendas_hora", 0),
                "kg_hora": ind.get("kg_hora", 0.0),
                "is_in_progress": is_in_process,
                "estado": "En proceso" if is_in_process else "Procesado",
                "updated_at": pkg.get("meta_info", {}).get("timestamp_actualizacion")
            })
            seen_keys.add(shift_key)

    # Revisar si hay otros registros persistidos previamente para esa fecha en la tabla separada
    persisted_rows = conn.execute(f"""
        SELECT shift_key, fecha, turno_identificador, nombre_turno, hora_inicio, hora_fin,
               prendas_totales, kgs_totales, tiempo_valle_min, prendas_hora, kg_hora, updated_at
        FROM {table_name}
        WHERE fecha = ?
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
          AND prendas_totales > 0
        ORDER BY hora_inicio ASC, id ASC
    """, (fecha,)).fetchall()
    valid_turno_ids = {f"Turno {i+1}" for i in range(len(shifts_template))}
    for r in persisted_rows:
        if r["shift_key"] not in seen_keys and r["turno_identificador"] in valid_turno_ids:
            result.append({
                "shift_key": r["shift_key"],
                "maquina": m_id,
                "fecha": r["fecha"],
                "turno_identificador": r["turno_identificador"],
                "nombre_turno": r["nombre_turno"],
                "horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "prendas_totales": r["prendas_totales"],
                "prendas_totales_str": f"{r['prendas_totales']:,}".replace(",", ".") + " prendas",
                "kgs_totales": r["kgs_totales"],
                "kgs_totales_str": f"{r['kgs_totales']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
                "tiempo_valle_min": r["tiempo_valle_min"],
                "tiempo_valle_str": f"{r['tiempo_valle_min']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
                "prendas_hora": r["prendas_hora"],
                "kg_hora": r["kg_hora"],
                "is_in_progress": False,
                "estado": "Procesado",
                "updated_at": r["updated_at"]
            })

    return {"status": "success", "maquina": m_id, "fecha": fecha, "turnos": result}


def sync_all_historical_calandra_shifts(maquina_id: str) -> int:
    """
    Recorre todas las fechas con registros en calandras_produccion para la máquina indicada
    y genera/actualiza los paquetes JSON para todos los turnos que tuvieron producción.
    """
    m_id = maquina_id.upper()
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT substr(timestamp_iso, 1, 10) as f
        FROM calandras_produccion
        WHERE maquina = ? AND timestamp_iso IS NOT NULL AND timestamp_iso != ''
        ORDER BY f ASC
    """, (m_id,)).fetchall()
    conn.close()

    fechas = [r["f"] for r in rows if r["f"]]
    turnos_plantilla = get_jornada_shifts_template()

    total_synced = 0
    for fecha in fechas:
        for idx, t_info in enumerate(turnos_plantilla):
            h_start = t_info["hora_inicio"]
            h_end = t_info["hora_fin"]

            start_iso, end_iso = get_shift_start_end_iso(fecha, h_start, h_end)

            conn_check = get_db_connection()
            count_prod = conn_check.execute("""
                SELECT COUNT(*), COALESCE(SUM(delta_total), 0)
                FROM calandras_produccion
                WHERE maquina = ? AND timestamp_iso >= ? AND timestamp_iso < ?
            """, (m_id, start_iso, end_iso)).fetchone()
            conn_check.close()

            num_rec = count_prod[0] if count_prod else 0
            tot_p = count_prod[1] if count_prod else 0

            if num_rec > 0 or tot_p > 0:
                t_dict = {
                    "nombre": f"Turno {idx + 1}",
                    "fecha": fecha,
                    "hora_inicio": h_start,
                    "hora_fin": h_end,
                    "is_active": False
                }
                pkg = build_calandra_shift_json(m_id, fecha=fecha, shift_data=t_dict, turno_numero=idx+1)
                save_calandra_shift_json(pkg)
                total_synced += 1

    return total_synced


def get_tunel_vt_production(turno_act: dict = None) -> dict:
    """
    Calcula los indicadores y la matriz hora a hora para el Túnel VT
    a partir de los mensajes MQTT (tópico 'datos_vt'), la base de datos SQLite
    tunel_vt_produccion y la configuración de peso unitario tunel_vt_peso_unitario.
    Si no hay turno activo en curso, todos los valores se devuelven en cero.
    """
    from app.mqtt_subscriber import get_tunel_vt_live_cache, get_peso_unitario_tunel_vt_db
    import urllib.request

    live_cache = get_tunel_vt_live_cache() or {}

    # Fallback rápido si live_cache aún no tiene datos recibidos por MQTT (ej. arranque en frío)
    if not live_cache.get("count_total") and not live_cache.get("entrada_1") and not live_cache.get("entrada_2") and not live_cache.get("entrada_3"):
        for url_vt in ["http://100.127.85.111:8000/api/conteo_vt_data", "http://192.168.0.137:8000/api/conteo_vt_data"]:
            try:
                req = urllib.request.Request(url_vt, headers={"User-Agent": "Elis4.0"})
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    if resp.status == 200:
                        vt_remote = json.loads(resp.read().decode("utf-8"))
                        c1 = int(vt_remote.get("e1Count", 0) or 0)
                        c2 = int(vt_remote.get("e2Count", 0) or 0)
                        c3 = int(vt_remote.get("e3Count", 0) or 0)
                        v1 = float(vt_remote.get("e1Idle", 0.0) or 0.0)
                        v2 = float(vt_remote.get("e2Idle", 0.0) or 0.0)
                        v3 = float(vt_remote.get("e3Idle", 0.0) or 0.0)
                        tot_c = c1 + c2 + c3
                        peso_u = get_peso_unitario_tunel_vt_db()
                        live_cache.update({
                            "entrada_1": c1, "entrada_2": c2, "entrada_3": c3,
                            "count_total": tot_c,
                            "tiempo_valle_e1_min": v1, "tiempo_valle_e2_min": v2, "tiempo_valle_e3_min": v3,
                            "tiempo_valle_total_min": round(max(v1, v2, v3), 1),
                            "peso_unitario_kg": peso_u,
                            "weight_total_kg": round(tot_c * peso_u, 2),
                            "updated_at": get_local_now_str()
                        })
                        break
            except Exception:
                continue

    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})

    shift_active = is_shift_active(turno_act)
    peso_u = get_peso_unitario_tunel_vt_db()

    default_labels = ["06:00 - 07:00", "07:00 - 08:00", "08:00 - 09:00", "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "12:00 - 13:00", "13:00 - 14:00"]
    n_lbl = len(default_labels)

    nombre_act = str(turno_act.get("nombre") or "").upper()
    is_fuera = any(x in nombre_act for x in ["FUERA", "SIN TURNO", "INACTIVO"])

    if not turno_act or is_fuera:
        return {
            "maquina": "TUNEL_VT",
            "is_turno_activo": False,
            "en_valle": False,
            "prendas_totales": 0,
            "prendas_totales_str": "0 prendas",
            "kgs_totales": 0.0,
            "kgs_totales_str": "0,0 kg",
            "tiempo_valle_min": 0.0,
            "tiempo_valle_str": "0,0 min",
            "tiempo_valle_total_str": "0,0 min",
            "tiempo_descanso_min": 0.0,
            "tiempo_descanso_str": "0,0 min",
            "prendas_hora": 0,
            "prendas_hora_str": "0 prendas/h",
            "kg_hora": 0.0,
            "kg_hora_str": "0,0 kg/h",
            "peso_unitario": peso_u,
            "peso_unitario_str": f"{peso_u:,.3f} kg/u".replace(".", ","),
            "desglose_entradas": {
                "entrada_1": 0, "entrada_1_str": "0 prendas",
                "entrada_2": 0, "entrada_2_str": "0 prendas",
                "entrada_3": 0, "entrada_3_str": "0 prendas",
                "kg_e1": 0.0, "kg_e1_str": "0,0 kg",
                "kg_e2": 0.0, "kg_e2_str": "0,0 kg",
                "kg_e3": 0.0, "kg_e3_str": "0,0 kg",
                "tiempo_valle_e1": 0.0, "tiempo_valle_e1_str": "0,0 min",
                "tiempo_valle_e2": 0.0, "tiempo_valle_e2_str": "0,0 min",
                "tiempo_valle_e3": 0.0, "tiempo_valle_e3_str": "0,0 min",
                "prendas_e1_hora": 0, "prendas_e1_hora_str": "0 p/h",
                "prendas_e2_hora": 0, "prendas_e2_hora_str": "0 p/h",
                "prendas_e3_hora": 0, "prendas_e3_hora_str": "0 p/h"
            },
            "grafica_hora_a_hora": {
                "labels": default_labels,
                "entrada_1": [0] * n_lbl,
                "entrada_2": [0] * n_lbl,
                "entrada_3": [0] * n_lbl,
                "prendas_totales": [0] * n_lbl,
                "valle_e1": [0.0] * n_lbl,
                "valle_e2": [0.0] * n_lbl,
                "valle_e3": [0.0] * n_lbl,
                "descanso_e1": [0.0] * n_lbl,
                "descanso_e2": [0.0] * n_lbl,
                "descanso_e3": [0.0] * n_lbl,
                "tiempo_descanso": [0.0] * n_lbl,
                "valle_total": [0.0] * n_lbl
            }
        }

    fecha_raw = turno_act.get("fecha") or get_local_now().strftime("%Y-%m-%d")
    if "/" in str(fecha_raw):
        try:
            d_p = str(fecha_raw).split("/")
            fecha_iso = f"{d_p[2]}-{d_p[1].zfill(2)}-{d_p[0].zfill(2)}"
        except Exception:
            fecha_iso = get_local_now().strftime("%Y-%m-%d")
    else:
        fecha_iso = str(fecha_raw)

    h_ini_str = str(turno_act.get("hora_inicio", "06:00"))[:5]
    h_fin_str = str(turno_act.get("hora_fin", "14:00"))[:5]
    try:
        start_h = int(h_ini_str.split(":")[0])
        end_h = int(h_fin_str.split(":")[0])
        if end_h <= start_h:
            end_h += 24
    except Exception:
        start_h, end_h = 6, 14

    labels = []
    slot_ranges = []
    try:
        dt_base = datetime.strptime(fecha_iso, "%Y-%m-%d")
    except Exception:
        dt_base = get_local_now().replace(tzinfo=None)

    for h in range(start_h, end_h):
        h1 = h % 24
        h2 = (h + 1) % 24
        labels.append(f"{h1:02d}:00 - {h2:02d}:00")

        day_offset_start = h // 24
        day_offset_end = (h + 1) // 24
        dt_s = dt_base + timedelta(days=day_offset_start)
        dt_e = dt_base + timedelta(days=day_offset_end) if h2 == 0 else dt_base + timedelta(days=day_offset_start)

        slot_start_iso = f"{dt_s.strftime('%Y-%m-%d')} {h1:02d}:00:00"
        slot_end_iso = f"{dt_e.strftime('%Y-%m-%d')} {h2:02d}:00:00"
        slot_ranges.append((slot_start_iso, slot_end_iso))

    shift_start_iso = slot_ranges[0][0] if slot_ranges else f"{fecha_iso} 06:00:00"
    shift_end_iso = slot_ranges[-1][1] if slot_ranges else f"{fecha_iso} 14:00:00"

    # Consultar SQLite tunel_vt_produccion para todo el turno
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener el registro base inmediatamente anterior al inicio del turno para no arrastrar acumulados del turno previo
    base_row = cursor.execute("""
        SELECT entrada_1, entrada_2, entrada_3, count_total,
               tiempo_valle_e1_min, tiempo_valle_e2_min, tiempo_valle_e3_min, tiempo_valle_total_min
        FROM tunel_vt_produccion
        WHERE timestamp_iso < ?
        ORDER BY timestamp_iso DESC
        LIMIT 1
    """, (shift_start_iso,)).fetchone()

    db_rows = cursor.execute("""
        SELECT 
            timestamp, timestamp_iso, entrada_1, entrada_2, entrada_3, count_total,
            tiempo_valle_e1_min, tiempo_valle_e2_min, tiempo_valle_e3_min, tiempo_valle_total_min
        FROM tunel_vt_produccion
        WHERE timestamp_iso >= ? AND timestamp_iso < ?
        ORDER BY timestamp_iso ASC
    """, (shift_start_iso, shift_end_iso)).fetchall()
    conn.close()

    deltas = []
    prev_e1 = int(base_row["entrada_1"] or 0) if base_row else None
    prev_e2 = int(base_row["entrada_2"] or 0) if base_row else None
    prev_e3 = int(base_row["entrada_3"] or 0) if base_row else None
    prev_v1 = float(base_row["tiempo_valle_e1_min"] or 0.0) if base_row else None
    prev_v2 = float(base_row["tiempo_valle_e2_min"] or 0.0) if base_row else None
    prev_v3 = float(base_row["tiempo_valle_e3_min"] or 0.0) if base_row else None

    for r in db_rows:
        ts = r["timestamp_iso"]
        c1 = int(r["entrada_1"] or 0)
        c2 = int(r["entrada_2"] or 0)
        c3 = int(r["entrada_3"] or 0)
        v1 = float(r["tiempo_valle_e1_min"] or 0.0)
        v2 = float(r["tiempo_valle_e2_min"] or 0.0)
        v3 = float(r["tiempo_valle_e3_min"] or 0.0)

        if prev_e1 is None:
            d1, d2, d3 = 0, 0, 0
        else:
            d1 = (c1 - prev_e1) if c1 >= prev_e1 else c1
            d2 = (c2 - prev_e2) if c2 >= prev_e2 else c2
            d3 = (c3 - prev_e3) if c3 >= prev_e3 else c3

        if prev_v1 is None:
            dv1, dv2, dv3 = 0.0, 0.0, 0.0
        else:
            dv1 = (v1 - prev_v1) if v1 >= prev_v1 else v1
            dv2 = (v2 - prev_v2) if v2 >= prev_v2 else v2
            dv3 = (v3 - prev_v3) if v3 >= prev_v3 else v3

        prev_e1, prev_e2, prev_e3 = c1, c2, c3
        prev_v1, prev_v2, prev_v3 = v1, v2, v3

        deltas.append({
            "ts": ts,
            "d1": max(0, d1), "d2": max(0, d2), "d3": max(0, d3),
            "dv1": max(0.0, dv1), "dv2": max(0.0, dv2), "dv3": max(0.0, dv3),
        })

    breaks_list = get_shift_breaks(turno_act)
    e1_slots = []
    e2_slots = []
    e3_slots = []
    tot_slots = []
    v1_slots = []
    v2_slots = []
    v3_slots = []
    d1_slots = []
    d2_slots = []
    d3_slots = []
    v_total_slots = []

    for s_start, s_end in slot_ranges:
        s_items = [it for it in deltas if s_start <= it["ts"] < s_end]
        s_d1 = sum(it["d1"] for it in s_items)
        s_d2 = sum(it["d2"] for it in s_items)
        s_d3 = sum(it["d3"] for it in s_items)
        s_tot = s_d1 + s_d2 + s_d3

        s_v1 = min(round(sum(it["dv1"] for it in s_items), 1), 60.0)
        s_v2 = min(round(sum(it["dv2"] for it in s_items), 1), 60.0)
        s_v3 = min(round(sum(it["dv3"] for it in s_items), 1), 60.0)
        s_vtot = max(s_v1, s_v2, s_v3)

        b_min = get_break_overlap_for_slot(s_start, s_end, breaks_list)
        try:
            s_start_dt = datetime.strptime(s_start.replace('T', ' ')[:19], "%Y-%m-%d %H:%M:%S")
            is_slot_started = (now_dt >= s_start_dt)
        except Exception:
            is_slot_started = True

        d_break = b_min if (is_slot_started and b_min > 0) else 0.0

        v1_neto = max(round(s_v1 - min(s_v1, d_break), 1), 0.0)
        v2_neto = max(round(s_v2 - min(s_v2, d_break), 1), 0.0)
        v3_neto = max(round(s_v3 - min(s_v3, d_break), 1), 0.0)
        v_neto_tot = max(round(s_vtot - min(s_vtot, d_break), 1), 0.0)

        e1_slots.append(s_d1)
        e2_slots.append(s_d2)
        e3_slots.append(s_d3)
        tot_slots.append(s_tot)
        v1_slots.append(v1_neto)
        v2_slots.append(v2_neto)
        v3_slots.append(v3_neto)
        v_total_slots.append(v_neto_tot)
        d1_slots.append(d_break)
        d2_slots.append(d_break)
        d3_slots.append(d_break)

    latest_e1 = sum(e1_slots)
    latest_e2 = sum(e2_slots)
    latest_e3 = sum(e3_slots)
    p_totales = latest_e1 + latest_e2 + latest_e3

    latest_v1 = min(round(sum(v1_slots), 1), float(len(slot_ranges) * 60))
    latest_v2 = min(round(sum(v2_slots), 1), float(len(slot_ranges) * 60))
    latest_v3 = min(round(sum(v3_slots), 1), float(len(slot_ranges) * 60))
    v_total = round(max(latest_v1, latest_v2, latest_v3), 1)
    tot_descanso = round(max(sum(d1_slots), sum(d2_slots), sum(d3_slots)), 1)

    if shift_active:
        dur_min = float(turno_act.get("minutos_transcurridos") or 60)
        horas_transcurridas = max(dur_min / 60.0, 0.25)
        in_valle = bool(live_cache.get("en_valle", False))
        live_valle = float(live_cache.get("tiempo_valle_total_min", 0.0) or 0.0)
        if live_valle > v_total:
            v_total = round(live_valle, 1)
    else:
        # Turno completado en el pasado o consulta histórica
        horas_transcurridas = max(float(len(slot_ranges)), 1.0)
        in_valle = False

    w_totales = round(p_totales * peso_u, 1)
    prendas_h = int(round(p_totales / horas_transcurridas))
    kg_h = round(w_totales / horas_transcurridas, 1)

    prendas_totales_str = f"{p_totales:,}".replace(",", ".") + " prendas"
    kgs_totales_str = f"{w_totales:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg"
    tiempo_valle_str = f"{v_total:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min"
    prendas_hora_str = f"{prendas_h:,}".replace(",", ".") + " prendas/h"
    kg_hora_str = f"{kg_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"

    return {
        "maquina": "TUNEL_VT",
        "is_turno_activo": shift_active,
        "en_valle": in_valle,
        "fuente_datos": "MQTT_DIRECTO",
        "prendas_totales": p_totales,
        "prendas_totales_str": prendas_totales_str,
        "kgs_totales": w_totales,
        "kgs_totales_str": kgs_totales_str,
        "tiempo_valle_min": v_total,
        "tiempo_valle_str": tiempo_valle_str,
        "tiempo_valle_total_str": tiempo_valle_str,
        "tiempo_descanso_min": tot_descanso,
        "tiempo_descanso_str": f"{tot_descanso:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
        "prendas_hora": prendas_h,
        "prendas_hora_str": prendas_hora_str,
        "kg_hora": kg_h,
        "kg_hora_str": kg_hora_str,
        "peso_unitario": peso_u,
        "peso_unitario_str": f"{peso_u:,.3f} kg/u".replace(".", ","),
        "desglose_entradas": {
            "entrada_1": latest_e1,
            "entrada_1_str": f"{latest_e1:,}".replace(",", ".") + " prendas",
            "entrada_2": latest_e2,
            "entrada_2_str": f"{latest_e2:,}".replace(",", ".") + " prendas",
            "entrada_3": latest_e3,
            "entrada_3_str": f"{latest_e3:,}".replace(",", ".") + " prendas",
            "kg_e1": round(latest_e1 * peso_u, 1),
            "kg_e1_str": f"{round(latest_e1 * peso_u, 1):,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "kg_e2": round(latest_e2 * peso_u, 1),
            "kg_e2_str": f"{round(latest_e2 * peso_u, 1):,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "kg_e3": round(latest_e3 * peso_u, 1),
            "kg_e3_str": f"{round(latest_e3 * peso_u, 1):,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "tiempo_valle_e1": latest_v1,
            "tiempo_valle_e1_str": f"{latest_v1:.1f} min",
            "tiempo_valle_e2": latest_v2,
            "tiempo_valle_e2_str": f"{latest_v2:.1f} min",
            "tiempo_valle_e3": latest_v3,
            "tiempo_valle_e3_str": f"{latest_v3:.1f} min",
            "prendas_e1_hora": int(round(latest_e1 / horas_transcurridas)),
            "prendas_e1_hora_str": f"{int(round(latest_e1 / horas_transcurridas)):,} p/h".replace(",", "."),
            "prendas_e2_hora": int(round(latest_e2 / horas_transcurridas)),
            "prendas_e2_hora_str": f"{int(round(latest_e2 / horas_transcurridas)):,} p/h".replace(",", "."),
            "prendas_e3_hora": int(round(latest_e3 / horas_transcurridas)),
            "prendas_e3_hora_str": f"{int(round(latest_e3 / horas_transcurridas)):,} p/h".replace(",", ".")
        },
        "grafica_hora_a_hora": {
            "labels": labels,
            "entrada_1": e1_slots,
            "entrada_2": e2_slots,
            "entrada_3": e3_slots,
            "prendas_totales": tot_slots,
            "valle_e1": v1_slots,
            "valle_e2": v2_slots,
            "valle_e3": v3_slots,
            "descanso_e1": d1_slots,
            "descanso_e2": d2_slots,
            "descanso_e3": d3_slots,
            "tiempo_descanso": d1_slots,
            "valle_total": v_total_slots
        }
    }


def build_tunel_vt_shift_json(fecha: str = None, shift_data: dict = None, turno_numero: int = None) -> dict:
    """
    Construye el paquete JSON completo de un turno para el Túnel VT,
    guardando la información hora a hora por cada una de las 3 entradas,
    tiempos valles e indicadores del dashboard.
    """
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
    else:
        turno_identificador, _ = get_turno_identificador(shift_data, shifts_list)

    fecha_turno = fecha or shift_data.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora_inicio = str(shift_data.get("hora_inicio") or shift_data.get("start") or "06:00")[:5]
    hora_fin = str(shift_data.get("hora_fin") or shift_data.get("end") or "14:00")[:5]
    rango_horario = f"{hora_inicio} - {hora_fin}"

    try:
        fecha_formateada = datetime.strptime(fecha_turno, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        fecha_formateada = fecha_turno

    shift_key = f"TUNEL_VT_{fecha_turno}_{turno_identificador.replace(' ', '_')}"

    prod_live = get_tunel_vt_production(shift_data)
    g = prod_live.get("grafica_hora_a_hora", {})

    return {
        "shift_key": shift_key,
        "maquina": "TUNEL_VT",
        "fecha": fecha_turno,
        "turno_identificador": turno_identificador,
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "rango_horario": rango_horario,
        "meta_info": {
            "planta": "ELIS NÁJERA 4.0",
            "maquina_id": "TUNEL_VT",
            "maquina_nombre": "Túnel VT",
            "fecha": fecha_turno,
            "fecha_formateada": fecha_formateada,
            "turno_identificador": turno_identificador,
            "nombre_turno": shift_data.get("nombre") or turno_identificador,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "rango_horario": rango_horario,
            "timestamp_actualizacion": get_local_now_str()
        },
        "indicadores_dashboard": prod_live,
        "desglose_hora_a_hora": g
    }


def save_tunel_vt_shift_json(shift_package: dict) -> bool:
    """Almacena o actualiza un paquete JSON de turno para Túnel VT en SQLite."""
    shift_key = shift_package["shift_key"]
    fecha = shift_package["fecha"]
    turno_identificador = shift_package["turno_identificador"]
    meta = shift_package.get("meta_info", {})
    nombre_turno = meta.get("nombre_turno", turno_identificador)
    hora_inicio = shift_package["hora_inicio"]
    hora_fin = shift_package["hora_fin"]
    rango_horario = shift_package.get("rango_horario", f"{hora_inicio} - {hora_fin}")

    ind = shift_package.get("indicadores_dashboard", {})
    prendas_totales = int(ind.get("prendas_totales", 0))
    desg = ind.get("desglose_entradas", {})
    e1 = int(desg.get("entrada_1", 0))
    e2 = int(desg.get("entrada_2", 0))
    e3 = int(desg.get("entrada_3", 0))
    ve1 = float(desg.get("tiempo_valle_e1", 0.0))
    ve2 = float(desg.get("tiempo_valle_e2", 0.0))
    ve3 = float(desg.get("tiempo_valle_e3", 0.0))
    ve_tot = float(ind.get("tiempo_valle_min", 0.0))
    kgs_totales = float(ind.get("kgs_totales", 0.0))
    peso_unitario = float(ind.get("peso_unitario", 0.260))
    prendas_hora = int(ind.get("prendas_hora", 0))
    kg_hora = float(ind.get("kg_hora", 0.0))

    data_json = json.dumps(shift_package, ensure_ascii=False)
    now_local = get_local_now_str()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tunel_vt_turnos_persistencia (
            shift_key, fecha, turno_identificador, nombre_turno,
            hora_inicio, hora_fin, rango_horario,
            prendas_totales, entrada_1, entrada_2, entrada_3,
            tiempo_valle_e1_min, tiempo_valle_e2_min, tiempo_valle_e3_min, tiempo_valle_total_min,
            kgs_totales, peso_unitario, prendas_hora, kg_hora,
            data_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(shift_key) DO UPDATE SET
            fecha = excluded.fecha,
            turno_identificador = excluded.turno_identificador,
            nombre_turno = excluded.nombre_turno,
            hora_inicio = excluded.hora_inicio,
            hora_fin = excluded.hora_fin,
            rango_horario = excluded.rango_horario,
            prendas_totales = excluded.prendas_totales,
            entrada_1 = excluded.entrada_1,
            entrada_2 = excluded.entrada_2,
            entrada_3 = excluded.entrada_3,
            tiempo_valle_e1_min = excluded.tiempo_valle_e1_min,
            tiempo_valle_e2_min = excluded.tiempo_valle_e2_min,
            tiempo_valle_e3_min = excluded.tiempo_valle_e3_min,
            tiempo_valle_total_min = excluded.tiempo_valle_total_min,
            kgs_totales = excluded.kgs_totales,
            peso_unitario = excluded.peso_unitario,
            prendas_hora = excluded.prendas_hora,
            kg_hora = excluded.kg_hora,
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
    """, (
        shift_key, fecha, turno_identificador, nombre_turno,
        hora_inicio, hora_fin, rango_horario,
        prendas_totales, e1, e2, e3,
        ve1, ve2, ve3, ve_tot,
        kgs_totales, peso_unitario, prendas_hora, kg_hora,
        data_json, now_local
    ))
    conn.commit()
    conn.close()
    return True


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
    n_lbl = len(default_labels)

    nombre_act = str(turno_act.get("nombre") or "").upper()
    is_fuera = any(x in nombre_act for x in ["FUERA", "SIN TURNO", "INACTIVO"])

    if not turno_act or is_fuera:
        conn_p = get_db_connection()
        p_row = conn_p.execute("SELECT * FROM calandras_peso_unitario WHERE maquina = ?", (maquina_id,)).fetchone()
        conn_p.close()
        p_def_peq = float(p_row["peso_pequenas"]) if p_row and p_row["peso_pequenas"] is not None else 0.470
        p_def_gra = float(p_row["peso_grandes"]) if p_row and p_row["peso_grandes"] is not None else 0.780
        p_def_uni = float(p_row["peso_unitario"]) if p_row and p_row["peso_unitario"] is not None else 1.180

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
            "tiempo_descanso_min": 0.0,
            "tiempo_descanso_str": "0,0 min",
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
                "peso_unitario_grandes": p_def_gra,
                "peso_unitario_grandes_str": f"{int(round(p_def_gra * 1000))} gr ({p_def_gra:.3f} kg)",
                "peso_unitario_pequenas": p_def_peq,
                "peso_unitario_pequenas_str": f"{int(round(p_def_peq * 1000))} gr ({p_def_peq:.3f} kg)",
                "tiempo_valle_grandes": 0.0,
                "tiempo_valle_grandes_str": "0.0 min",
                "tiempo_valle_pequenas": 0.0,
                "tiempo_valle_pequenas_str": "0.0 min",
                "prendas_grandes_hora": 0,
                "prendas_grandes_hora_str": "0 g/h",
                "prendas_pequenas_hora": 0,
                "prendas_pequenas_hora_str": "0 p/h"
            } if maquina_id == "CALANDRA_2" else None,
            "peso_pequenas": p_def_peq if maquina_id == "CALANDRA_2" else None,
            "peso_pequenas_gr": int(round(p_def_peq * 1000)) if maquina_id == "CALANDRA_2" else None,
            "peso_grandes": p_def_gra if maquina_id == "CALANDRA_2" else None,
            "peso_grandes_gr": int(round(p_def_gra * 1000)) if maquina_id == "CALANDRA_2" else None,
            "peso_unitario_info": f"Gdes: {int(round(p_def_gra * 1000))}g | Peq: {int(round(p_def_peq * 1000))}g" if maquina_id == "CALANDRA_2" else f"{int(round(p_def_uni * 1000))} gr ({p_def_uni:.3f} kg)",
            "peso_unitario": p_def_gra if maquina_id == "CALANDRA_2" else p_def_uni,
            "peso_unitario_gr": int(round((p_def_gra if maquina_id == "CALANDRA_2" else p_def_uni) * 1000)),
            "peso_unitario_str": f"{int(round(p_def_uni * 1000))} gr/u" if maquina_id == "CALANDRA_3" else f"P: {int(round(p_def_peq * 1000))}g | G: {int(round(p_def_gra * 1000))}g",
            "grafica_hora_a_hora": {
                "labels": default_labels,
                "prendas": [0] * n_lbl,
                "tiempo_valle": [0.0] * n_lbl,
                "tiempo_descanso": [0.0] * n_lbl,
                "tiempo_valle_raw": [0.0] * n_lbl,
                "grandes": [0] * n_lbl if maquina_id == "CALANDRA_2" else None,
                "pequenas": [0] * n_lbl if maquina_id == "CALANDRA_2" else None
            }
        }

    fecha_raw = turno_act.get("fecha") or get_local_now().strftime("%Y-%m-%d")
    if "/" in str(fecha_raw):
        try:
            d_p = str(fecha_raw).split("/")
            fecha_iso = f"{d_p[2]}-{d_p[1].zfill(2)}-{d_p[0].zfill(2)}"
        except Exception:
            fecha_iso = get_local_now().strftime("%Y-%m-%d")
    else:
        fecha_iso = str(fecha_raw)

    h_ini_str = str(turno_act.get("hora_inicio", "06:00"))[:5]
    h_fin_str = str(turno_act.get("hora_fin", "14:00"))[:5]
    try:
        start_h = int(h_ini_str.split(":")[0])
        end_h = int(h_fin_str.split(":")[0])
        if end_h <= start_h:
            end_h += 24
    except Exception:
        start_h, end_h = 6, 14

    labels = []
    slot_ranges = []
    try:
        dt_base = datetime.strptime(fecha_iso, "%Y-%m-%d")
    except Exception:
        dt_base = get_local_now().replace(tzinfo=None)

    for h in range(start_h, end_h):
        h1 = h % 24
        h2 = (h + 1) % 24
        labels.append(f"{h1:02d}:00 - {h2:02d}:00")

        day_offset_start = h // 24
        day_offset_end = (h + 1) // 24
        dt_s = dt_base + timedelta(days=day_offset_start)
        dt_e = dt_base + timedelta(days=day_offset_end) if h2 == 0 else dt_base + timedelta(days=day_offset_start)

        slot_start_iso = f"{dt_s.strftime('%Y-%m-%d')} {h1:02d}:00:00"
        slot_end_iso = f"{dt_e.strftime('%Y-%m-%d')} {h2:02d}:00:00"
        slot_ranges.append((slot_start_iso, slot_end_iso))

    shift_start_iso = slot_ranges[0][0] if slot_ranges else f"{fecha_iso} 06:00:00"
    shift_end_iso = slot_ranges[-1][1] if slot_ranges else f"{fecha_iso} 14:00:00"

    # Consultar SQLite calandras_produccion para todo el turno (ingesta MQTT directa)
    conn = get_db_connection()
    cursor = conn.cursor()
    db_rows = cursor.execute("""
        SELECT 
            timestamp, timestamp_iso, count_total, count_grandes, count_pequenas,
            delta_total, delta_grandes, delta_pequenas, idle_min_total, in_idle
        FROM calandras_produccion
        WHERE maquina = ? 
          AND timestamp_iso >= ? AND timestamp_iso < ?
        ORDER BY timestamp_iso ASC
    """, (maquina_id, shift_start_iso, shift_end_iso)).fetchall()
    conn.close()

    norm_rows = []
    for r in db_rows:
        norm_rows.append({
            "ts": r["timestamp_iso"],
            "count_total": int(r["count_total"] or 0),
            "count_grandes": int(r["count_grandes"] or 0),
            "count_pequenas": int(r["count_pequenas"] or 0),
            "delta_total": int(r["delta_total"] or 0),
            "delta_grandes": int(r["delta_grandes"] or 0),
            "delta_pequenas": int(r["delta_pequenas"] or 0),
            "idle_min_total": float(r["idle_min_total"] or 0.0),
            "in_idle": int(r["in_idle"] or 0)
        })

    breaks_list = get_shift_breaks(turno_act)
    prendas = []
    valle = []
    descanso = []
    valle_raw = []
    grandes = []
    pequenas = []
    prev_idle = norm_rows[0]["idle_min_total"] if norm_rows else None

    for s_start, s_end in slot_ranges:
        slot_items = [it for it in norm_rows if s_start <= it["ts"] < s_end]
        tot_slot = sum(it["delta_total"] for it in slot_items)
        g_slot = sum(it["delta_grandes"] for it in slot_items)
        p_slot = sum(it["delta_pequenas"] for it in slot_items)

        # Fallback a variación de contador si deltas estuviesen en 0
        if tot_slot == 0 and len(slot_items) > 1:
            c_max = max(it["count_total"] for it in slot_items)
            c_min = min(it["count_total"] for it in slot_items)
            if c_max > c_min:
                tot_slot = c_max - c_min
                if maquina_id == "CALANDRA_2":
                    g_slot = max(it["count_grandes"] for it in slot_items) - min(it["count_grandes"] for it in slot_items)
                    p_slot = max(it["count_pequenas"] for it in slot_items) - min(it["count_pequenas"] for it in slot_items)

        # Cálculo de tiempo valle continuo por deltas positivos acumulados
        v_slot_delta = 0.0
        for it in slot_items:
            curr_idle = it["idle_min_total"]
            if prev_idle is not None:
                if curr_idle >= prev_idle:
                    v_slot_delta += (curr_idle - prev_idle)
                elif curr_idle < 60.0:
                    v_slot_delta += curr_idle
            prev_idle = curr_idle

        v_slot_delta = min(round(v_slot_delta, 1), 60.0)

        # Descontar el descanso del tiempo valle
        b_min = get_break_overlap_for_slot(s_start, s_end, breaks_list)
        try:
            s_start_dt = datetime.strptime(s_start.replace('T', ' ')[:19], "%Y-%m-%d %H:%M:%S")
            is_slot_started = (now_dt >= s_start_dt)
        except Exception:
            is_slot_started = True

        d_slot = b_min if (is_slot_started and b_min > 0) else 0.0
        v_neto = max(round(v_slot_delta - min(v_slot_delta, d_slot), 1), 0.0)

        prendas.append(tot_slot)
        grandes.append(g_slot)
        pequenas.append(p_slot)
        valle.append(v_neto)
        descanso.append(d_slot)
        valle_raw.append(v_slot_delta)

    tot_prendas_remotas = sum(prendas)
    tot_grandes_remotas = sum(grandes)
    tot_pequenas_remotas = sum(pequenas)
    tot_valle_remoto = round(sum(valle), 1)
    tot_descanso_remoto = round(sum(descanso), 1)

    conn = get_db_connection()
    peso_row = conn.execute("SELECT * FROM calandras_peso_unitario WHERE maquina = ?", (maquina_id,)).fetchone()
    conn.close()

    if maquina_id == "CALANDRA_2":
        p_grandes = tot_grandes_remotas
        p_pequenas = tot_pequenas_remotas
        p_totales = tot_prendas_remotas or (p_grandes + p_pequenas)

        # Prioridad de peso unitario: 1. Live MQTT cache -> 2. BD calandras_peso_unitario -> 3. Default real (0.78 / 0.47)
        p_gra_unit = float(
            live_cache.get("peso_unitario_grandes")
            or (peso_row["peso_grandes"] if peso_row and peso_row["peso_grandes"] is not None else 0.780)
        )
        p_peq_unit = float(
            live_cache.get("peso_unitario_pequenas")
            or (peso_row["peso_pequenas"] if peso_row and peso_row["peso_pequenas"] is not None else 0.470)
        )

        w_grandes = round(p_grandes * p_gra_unit, 1)
        w_pequenas = round(p_pequenas * p_peq_unit, 1)
        w_totales = round(w_grandes + w_pequenas, 1)

        v_total = tot_valle_remoto
        v_grandes = v_total
        v_pequenas = v_total
        in_idle = bool(live_cache.get("in_idle_grandes") or live_cache.get("in_idle_pequenas") or live_cache.get("in_idle") or (norm_rows and norm_rows[-1]["in_idle"]))
    else:
        # CALANDRA_3
        p_totales = tot_prendas_remotas
        p_grandes = 0
        p_pequenas = tot_prendas_remotas

        # Prioridad de peso unitario para Calandra 3:
        # Descartar 0.25 (residuo antiguo por defecto de la cámara) y usar peso real (1.18 kg)
        live_w = float(live_cache.get("peso_unitario") or 0.0)
        db_w = float(peso_row["peso_unitario"] if peso_row and peso_row["peso_unitario"] is not None else 0.0)

        if live_w > 0 and round(live_w, 2) != 0.25:
            p_unit = live_w
        elif db_w > 0 and round(db_w, 2) != 0.25:
            p_unit = db_w
        else:
            p_unit = 1.180

        w_totales = round(p_totales * p_unit, 1)
        w_grandes = 0.0
        w_pequenas = w_totales
        v_total = tot_valle_remoto
        v_grandes = 0.0
        v_pequenas = v_total
        in_idle = bool(live_cache.get("in_idle") or (norm_rows and norm_rows[-1]["in_idle"]))

    # Calcular horas transcurridas de turno
    duracion_horas = max(len(labels), 1)
    if shift_active:
        now_dt = get_local_now().replace(tzinfo=None)
        start_iso, end_iso = get_shift_start_end_iso(fecha_iso, h_ini_str, h_fin_str)
        try:
            dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
            if now_dt >= dt_end:
                horas_transcurridas = max((dt_end - dt_start).total_seconds() / 3600.0, 1.0)
            elif now_dt >= dt_start:
                horas_transcurridas = max((now_dt - dt_start).total_seconds() / 3600.0, 0.25)
            else:
                horas_transcurridas = max(float(duracion_horas), 1.0)
        except Exception:
            horas_transcurridas = max(float(duracion_horas), 1.0)
        en_valle_res = in_idle
    else:
        horas_transcurridas = max(float(duracion_horas), 1.0)
        en_valle_res = False

    prendas_h = int(round(p_totales / horas_transcurridas))
    kg_h = round(w_totales / horas_transcurridas, 1)

    prendas_totales_str = f"{p_totales:,}".replace(",", ".") + " prendas"
    kgs_totales_str = f"{w_totales:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg"
    tiempo_valle_str = f"{v_total:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min"
    prendas_hora_str = f"{prendas_h:,}".replace(",", ".") + " prendas/h"
    kg_hora_str = f"{kg_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"

    res_prod = {
        "maquina": maquina_id,
        "is_turno_activo": shift_active,
        "en_valle": en_valle_res,
        "fuente_datos": "MQTT_DIRECTO",
        "prendas_totales": p_totales,
        "prendas_totales_str": prendas_totales_str,
        "kgs_totales": w_totales,
        "kgs_totales_str": kgs_totales_str,
        "tiempo_valle_min": v_total,
        "tiempo_valle_str": tiempo_valle_str,
        "tiempo_descanso_min": tot_descanso_remoto,
        "tiempo_descanso_str": f"{tot_descanso_remoto:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
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
            "peso_unitario_grandes": p_gra_unit,
            "peso_unitario_grandes_str": f"{int(round(p_gra_unit * 1000))} gr ({p_gra_unit:.3f} kg)",
            "peso_unitario_pequenas": p_peq_unit,
            "peso_unitario_pequenas_str": f"{int(round(p_peq_unit * 1000))} gr ({p_peq_unit:.3f} kg)",
            "tiempo_valle_grandes": v_grandes,
            "tiempo_valle_grandes_str": f"{v_grandes:.1f} min",
            "tiempo_valle_pequenas": v_pequenas,
            "tiempo_valle_pequenas_str": f"{v_pequenas:.1f} min",
            "prendas_grandes_hora": int(round(p_grandes / horas_transcurridas)),
            "prendas_grandes_hora_str": f"{int(round(p_grandes / horas_transcurridas)):,} g/h".replace(",", "."),
            "prendas_pequenas_hora": int(round(p_pequenas / horas_transcurridas)),
            "prendas_pequenas_hora_str": f"{int(round(p_pequenas / horas_transcurridas)):,} p/h".replace(",", ".")
        } if maquina_id == "CALANDRA_2" else None,
        "peso_pequenas": p_peq_unit if maquina_id == "CALANDRA_2" else None,
        "peso_pequenas_gr": int(round(p_peq_unit * 1000)) if maquina_id == "CALANDRA_2" else None,
        "peso_grandes": p_gra_unit if maquina_id == "CALANDRA_2" else None,
        "peso_grandes_gr": int(round(p_gra_unit * 1000)) if maquina_id == "CALANDRA_2" else None,
        "peso_unitario_info": f"Gdes: {int(round(p_gra_unit * 1000))}g | Peq: {int(round(p_peq_unit * 1000))}g" if maquina_id == "CALANDRA_2" else f"{int(round(p_unit * 1000))} gr ({p_unit:.3f} kg)",
        "peso_unitario": p_gra_unit if maquina_id == "CALANDRA_2" else p_unit,
        "peso_unitario_gr": int(round((p_gra_unit if maquina_id == "CALANDRA_2" else p_unit) * 1000)),
        "peso_unitario_str": f"{int(round(p_unit * 1000))} gr/u" if maquina_id == "CALANDRA_3" else f"P: {int(round(p_peq_unit * 1000))}g | G: {int(round(p_gra_unit * 1000))}g",
        "grafica_hora_a_hora": {
            "labels": labels,
            "prendas": prendas,
            "tiempo_valle": valle,
            "tiempo_descanso": descanso,
            "tiempo_valle_raw": valle_raw,
            "grandes": grandes if maquina_id == "CALANDRA_2" else None,
            "pequenas": pequenas if maquina_id == "CALANDRA_2" else None
        }
    }

    # Comparación temporal con la API del puerto 5002 para verificar igualdad
    try:
        res_prod["comparacion_5002"] = compare_calandra_mqtt_vs_5002(maquina_id, res_prod, turno_act)
    except Exception as e:
        res_prod["comparacion_5002"] = {"disponible_5002": False, "motivo": str(e)}

    return res_prod


def compare_calandra_mqtt_vs_5002(maquina_id: str, prod_mqtt: dict, turno_act: dict = None) -> dict:
    """
    Compara temporalmente los datos calculados exclusivamente por MQTT con la API del puerto 5002
    para verificar que a cada lado los datos se construyen igual.
    """
    import urllib.request
    maq_param = "calandra_2" if maquina_id == "CALANDRA_2" else "calandra_3"
    w_idx = get_local_now().weekday()

    comparativa = {
        "maquina": maquina_id,
        "disponible_5002": False,
        "coincidencia_exacta": False,
        "timestamp_comparacion": get_local_now_str(),
        "resumen": {
            "prendas_mqtt": prod_mqtt.get("prendas_totales", 0),
            "prendas_5002": 0,
            "valle_mqtt_min": prod_mqtt.get("tiempo_valle_min", 0.0),
            "valle_5002_min": 0.0,
            "diff_prendas": 0,
            "diff_valle_min": 0.0
        },
        "filas_comparacion": []
    }

    try:
        url = f"http://100.127.85.111:5002/api/tabla-horaria?machine_id={maq_param}"
        req = urllib.request.urlopen(url, timeout=2.0)
        t_data = json.loads(req.read().decode('utf-8'))
        hour_slots = t_data.get("hour_slots", [])
        cells = t_data.get("cells", {})

        g_mqtt = prod_mqtt.get("grafica_hora_a_hora", {})
        mqtt_labels = g_mqtt.get("labels", [])
        mqtt_prendas = g_mqtt.get("prendas", [])
        mqtt_valle = g_mqtt.get("tiempo_valle", [])

        tot_5002_p = 0
        tot_5002_v = 0.0
        exact_all = True

        for s in hour_slots:
            lbl = f"{s['startStr']} - {s['endStr']}"
            cell_key = f"{w_idx}_{s['index']}"
            c = cells.get(cell_key, {})
            l = int(c.get("large", 0) or 0)
            p = int(c.get("small", 0) or 0)
            tot_val = c.get("total")
            p_5002 = int(tot_val if tot_val is not None else (l + p))
            v_5002 = round(float(c.get("idle_min", 0.0) or 0.0), 1)

            tot_5002_p += p_5002
            tot_5002_v += v_5002

            p_mq = 0
            v_mq = 0.0
            if lbl in mqtt_labels:
                idx = mqtt_labels.index(lbl)
                p_mq = mqtt_prendas[idx] if idx < len(mqtt_prendas) else 0
                v_mq = mqtt_valle[idx] if idx < len(mqtt_valle) else 0.0

            ok_p = (p_mq == p_5002)
            ok_v = (abs(v_mq - v_5002) <= 0.3)
            if not (ok_p and ok_v):
                exact_all = False

            comparativa["filas_comparacion"].append({
                "franja": lbl,
                "prendas_mqtt": p_mq,
                "prendas_5002": p_5002,
                "valle_mqtt": v_mq,
                "valle_5002": v_5002,
                "diff_prendas": p_mq - p_5002,
                "diff_valle": round(v_mq - v_5002, 1),
                "ok_prendas": ok_p,
                "ok_valle": ok_v,
                "coincide": ok_p and ok_v
            })

        tot_5002_v = round(tot_5002_v, 1)
        tot_mq_p = prod_mqtt.get("prendas_totales", 0)
        tot_mq_v = prod_mqtt.get("tiempo_valle_min", 0.0)

        comparativa["disponible_5002"] = True
        comparativa["coincidencia_exacta"] = exact_all
        comparativa["resumen"]["prendas_5002"] = tot_5002_p
        comparativa["resumen"]["valle_5002_min"] = tot_5002_v
        comparativa["resumen"]["diff_prendas"] = tot_mq_p - tot_5002_p
        comparativa["resumen"]["diff_valle_min"] = round(tot_mq_v - tot_5002_v, 1)
    except Exception as e:
        comparativa["motivo"] = f"API 5002 no disponible o timeout: {e}"

    return comparativa

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
        nombre_t_up = (nombre_turno or "").upper()
        if is_shift_active(turno_act) and not any(x in nombre_t_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
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
            q = "SELECT COUNT(*) as num_cargas, COALESCE(SUM(peso_kg), 0) as kg_hora FROM tunel_cargas WHERE timestamp_iso >= ? AND timestamp_iso <= ? AND load_id IS NOT NULL AND peso_kg > 0"
        else:
            q = "SELECT COUNT(*) as num_cargas, COALESCE(SUM(peso_kg), 0) as kg_hora FROM tunel_cargas WHERE timestamp_iso >= ? AND timestamp_iso < ? AND load_id IS NOT NULL AND peso_kg > 0"

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
    shift_key = shift_package.get("shift_key", "")
    meta = shift_package.get("meta_info", {})
    fecha = meta.get("fecha")
    nombre_turno = meta.get("nombre_turno", "")
    hora_inicio = meta.get("hora_inicio")
    hora_fin = meta.get("hora_fin")

    # Validación estricta: NO persistir registros inválidos de 'fuera de turno', 'sin turno' o inactivos
    nombre_upper = (nombre_turno or "").upper()
    key_upper = (shift_key or "").upper()
    if any(x in nombre_upper or x in key_upper for x in ["FUERA", "SIN TURNO", "SIN_TURNO", "INACTIVO"]):
        return False
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
        WHERE UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
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
        WHERE UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
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
        nombre_upper = (nombre or "").upper()
        if any(x in nombre_upper for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

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

    # Revisar si hay otros registros persistidos previamente para esa fecha (filtrando fuera de turno)
    persisted_rows = conn.execute("""
        SELECT shift_key, fecha, nombre_turno, hora_inicio, hora_fin, total_kg, total_cargas, ikprod_pct, updated_at
        FROM turnos_persistencia
        WHERE fecha = ?
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
          AND (total_kg > 0 OR total_cargas > 0)
        ORDER BY hora_inicio ASC, id ASC
    """, (fecha,)).fetchall()
    conn.close()

    for r in persisted_rows:
        n_up = (r["nombre_turno"] or "").upper()
        k_up = (r["shift_key"] or "").upper()
        if any(x in n_up or x in k_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue
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
        WHERE UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
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
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
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
    turnos_plantilla = get_jornada_shifts_template()

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
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
    """, (fecha_inicio, fecha_fin)).fetchall()
    conn.close()

    turnos_evaluados = []
    for r in rows:
        n_up = (r["nombre_turno"] or "").upper()
        k_up = (r["shift_key"] or "").upper()
        if any(x in n_up or x in k_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

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
    maquina: str = "TUNEL_LAVADO",
    current_user: dict = Depends(check_produccion_permission)
):
    """
    Calcula los totales consolidados de un período concatenando los turnos comprendidos en la ventana seleccionada.
    No se toman en cuenta baches de tiempo intermedios (ej: fines de semana o noches sin producción).
    Los turnos incluidos se asumen contiguos para el cálculo de horas efectivas y kg/hora.
    """
    m_up = (maquina or "TUNEL_LAVADO").upper()
    if m_up in ["CALANDRA_2", "CALANDRA2", "CAL_2"]:
        return get_calandra_2_totales_periodo(fecha_inicio, hora_inicio, fecha_fin, hora_fin)
    elif m_up in ["CALANDRA_3", "CALANDRA3", "CAL_3"]:
        return get_calandra_3_totales_periodo(fecha_inicio, hora_inicio, fecha_fin, hora_fin)
    elif m_up in ["TUNEL_VT", "TUNELVT", "VT"]:
        return get_tunel_vt_totales_periodo(fecha_inicio, hora_inicio, fecha_fin, hora_fin)

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
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
        ORDER BY fecha ASC, hora_inicio ASC
    """, (q_start_date, q_end_date)).fetchall()
    conn.close()

    turnos_concatenados = []
    total_kg_acum = 0.0
    total_cargas_acum = 0
    total_segundos_efectivos = 0.0

    for r in rows:
        n_up = (r["nombre_turno"] or "").upper()
        k_up = (r["shift_key"] or "").upper()
        if any(x in n_up or x in k_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

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


def get_calandra_2_totales_periodo(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00"
) -> dict:
    """Calcula los totales consolidados de un período concatenando los turnos de Calandra 2."""
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

    q_start_date = (dt_start - timedelta(days=1)).strftime("%Y-%m-%d")
    q_end_date = (dt_end + timedelta(days=1)).strftime("%Y-%m-%d")

    # Sincronizar turno actual en curso si cae en la ventana
    try:
        cur_j = get_current_jornada_date()
        if cur_j >= q_start_date and cur_j <= q_end_date:
            turnos_cache = get_cached_turnos()
            turno_act = turnos_cache.get("turno_actual", {})
            if is_shift_active(turno_act):
                pkg = build_calandra_shift_json("CALANDRA_2", cur_j, turno_act)
                save_calandra_shift_json(pkg)
    except Exception:
        pass

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT shift_key, fecha, turno_identificador, nombre_turno, hora_inicio, hora_fin,
               prendas_totales, prendas_grandes, prendas_pequenas,
               kgs_totales, kg_grandes, kg_pequenas,
               tiempo_valle_min, prendas_hora, kg_hora, data_json, updated_at
        FROM calandra_2_turnos_persistencia
        WHERE fecha >= ? AND fecha <= ?
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
        ORDER BY fecha ASC, hora_inicio ASC, id ASC
    """, (q_start_date, q_end_date)).fetchall()
    conn.close()

    turnos_concatenados = []
    total_prendas_acum = 0
    total_grandes_acum = 0
    total_pequenas_acum = 0
    total_kg_acum = 0.0
    total_kg_grandes_acum = 0.0
    total_kg_pequenas_acum = 0.0
    total_valle_acum = 0.0
    total_segundos_efectivos = 0.0

    for r in rows:
        n_up = (r["nombre_turno"] or "").upper()
        k_up = (r["shift_key"] or "").upper()
        if any(x in n_up or x in k_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

        shift_start_iso, shift_end_iso = get_shift_start_end_iso(r["fecha"], r["hora_inicio"], r["hora_fin"])
        
        if shift_end_iso > window_start_str and shift_start_iso < window_end_str:
            p_tot = int(r["prendas_totales"] or 0)
            p_gra = int(r["prendas_grandes"] or 0)
            p_peq = int(r["prendas_pequenas"] or 0)
            if p_tot > 0 and (p_gra + p_peq == 0):
                p_peq = p_tot

            k_tot = float(r["kgs_totales"] or 0.0)
            k_gra = float(r["kg_grandes"] or 0.0)
            k_peq = float(r["kg_pequenas"] or 0.0)
            v_min = float(r["tiempo_valle_min"] or 0.0)

            try:
                dt_s = datetime.strptime(shift_start_iso, "%Y-%m-%d %H:%M:%S")
                dt_e = datetime.strptime(shift_end_iso, "%Y-%m-%d %H:%M:%S")
                dur_seg = max((dt_e - dt_s).total_seconds(), 60.0)
            except Exception:
                dur_seg = 8 * 3600.0

            dur_horas = dur_seg / 3600.0

            p_h = r["prendas_hora"] or (int(round(p_tot / dur_horas)) if dur_horas > 0 else 0)
            k_h = r["kg_hora"] or (round(k_tot / dur_horas, 1) if dur_horas > 0 else 0.0)

            total_prendas_acum += p_tot
            total_grandes_acum += p_gra
            total_pequenas_acum += p_peq
            total_kg_acum += k_tot
            total_kg_grandes_acum += k_gra
            total_kg_pequenas_acum += k_peq
            total_valle_acum += v_min
            total_segundos_efectivos += dur_seg

            turnos_concatenados.append({
                "shift_key": r["shift_key"],
                "fecha": r["fecha"],
                "fecha_formateada": datetime.strptime(r["fecha"], "%Y-%m-%d").strftime("%d/%m/%Y") if "-" in r["fecha"] else r["fecha"],
                "turno_identificador": r["turno_identificador"],
                "nombre_turno": r["nombre_turno"],
                "hora_inicio": r["hora_inicio"],
                "hora_fin": r["hora_fin"],
                "rango_horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "duracion_horas": round(dur_horas, 1),
                "prendas_totales": p_tot,
                "prendas_totales_str": f"{p_tot:,}".replace(",", ".") + " prendas",
                "prendas_grandes": p_gra,
                "prendas_grandes_str": f"{p_gra:,}".replace(",", ".") + " grandes",
                "prendas_pequenas": p_peq,
                "prendas_pequenas_str": f"{p_peq:,}".replace(",", ".") + " pequeñas",
                "total_kg": round(k_tot, 1),
                "total_kg_str": f"{k_tot:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "kg_grandes": round(k_gra, 1),
                "kg_grandes_str": f"{k_gra:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "kg_pequenas": round(k_peq, 1),
                "kg_pequenas_str": f"{k_peq:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "tiempo_valle_min": round(v_min, 1),
                "tiempo_valle_str": f"{v_min:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
                "prendas_hora": p_h,
                "prendas_hora_str": f"{p_h:,}".replace(",", ".") + " p/h",
                "kg_hora": k_h,
                "kg_hora_str": f"{k_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"
            })

    total_horas_efectivas = total_segundos_efectivos / 3600.0
    horas_int = int(total_horas_efectivas)
    minutos_rem = int(round((total_horas_efectivas - horas_int) * 60))

    kg_hora_periodo = round(total_kg_acum / total_horas_efectivas, 1) if total_horas_efectivas > 0 else 0.0
    prendas_hora_periodo = int(round(total_prendas_acum / total_horas_efectivas)) if total_horas_efectivas > 0 else 0

    n_turnos = len(turnos_concatenados)
    pct_grandes = round((total_grandes_acum / total_prendas_acum) * 100, 1) if total_prendas_acum > 0 else 0.0
    pct_pequenas = round((total_pequenas_acum / total_prendas_acum) * 100, 1) if total_prendas_acum > 0 else 0.0
    prom_prendas_turno = int(round(total_prendas_acum / n_turnos)) if n_turnos > 0 else 0
    prom_kg_turno = round(total_kg_acum / n_turnos, 1) if n_turnos > 0 else 0.0
    prom_valle_turno = round(total_valle_acum / n_turnos, 1) if n_turnos > 0 else 0.0

    return {
        "status": "success",
        "maquina": "CALANDRA_2",
        "maquina_nombre": "Calandra 2",
        "icono": "fa-scroll",
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
            "total_turnos": n_turnos,
            "total_prendas": total_prendas_acum,
            "total_prendas_str": f"{total_prendas_acum:,}".replace(",", ".") + " prendas",
            "total_grandes": total_grandes_acum,
            "total_grandes_str": f"{total_grandes_acum:,}".replace(",", ".") + " grandes",
            "total_pequenas": total_pequenas_acum,
            "total_pequenas_str": f"{total_pequenas_acum:,}".replace(",", ".") + " pequeñas",
            "pct_grandes": pct_grandes,
            "pct_pequenas": pct_pequenas,
            "total_kg": round(total_kg_acum, 1),
            "total_kg_str": f"{total_kg_acum:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "total_kg_grandes": round(total_kg_grandes_acum, 1),
            "total_kg_grandes_str": f"{total_kg_grandes_acum:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "total_kg_pequenas": round(total_kg_pequenas_acum, 1),
            "total_kg_pequenas_str": f"{total_kg_pequenas_acum:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "total_tiempo_valle_min": round(total_valle_acum, 1),
            "total_tiempo_valle_str": f"{total_valle_acum:,.1f} min".replace(",", "@").replace(".", ",").replace("@", "."),
            "horas_efectivas": round(total_horas_efectivas, 1),
            "horas_efectivas_str": f"{horas_int}h {minutos_rem}m ({round(total_horas_efectivas, 1)}h)",
            "prendas_hora": prendas_hora_periodo,
            "prendas_hora_str": f"{prendas_hora_periodo:,} p/h".replace(",", "."),
            "kg_hora": kg_hora_periodo,
            "kg_hora_str": f"{kg_hora_periodo:,.1f} kg/h".replace(",", "@").replace(".", ",").replace("@", "."),
            "promedio_prendas_turno": prom_prendas_turno,
            "promedio_prendas_turno_str": f"{prom_prendas_turno:,} p/turno".replace(",", "."),
            "promedio_kg_turno": prom_kg_turno,
            "promedio_kg_turno_str": f"{prom_kg_turno:,.1f} kg/turno".replace(",", "@").replace(".", ",").replace("@", "."),
            "promedio_valle_turno": prom_valle_turno,
            "promedio_valle_turno_str": f"{prom_valle_turno:,.1f} min/turno".replace(",", "@").replace(".", ",").replace("@", ".")
        },
        "turnos_concatenados": turnos_concatenados
    }


def get_calandra_3_totales_periodo(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00"
) -> dict:
    """Calcula los totales consolidados de un período concatenando los turnos de Calandra 3."""
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

    q_start_date = (dt_start - timedelta(days=1)).strftime("%Y-%m-%d")
    q_end_date = (dt_end + timedelta(days=1)).strftime("%Y-%m-%d")

    # Sincronizar turno actual en curso si cae en la ventana
    try:
        cur_j = get_current_jornada_date()
        if cur_j >= q_start_date and cur_j <= q_end_date:
            turnos_cache = get_cached_turnos()
            turno_act = turnos_cache.get("turno_actual", {})
            if is_shift_active(turno_act):
                pkg = build_calandra_shift_json("CALANDRA_3", cur_j, turno_act)
                save_calandra_shift_json(pkg)
    except Exception:
        pass

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT shift_key, fecha, turno_identificador, nombre_turno, hora_inicio, hora_fin,
               prendas_totales, kgs_totales, tiempo_valle_min, peso_unitario,
               prendas_hora, kg_hora, data_json, updated_at
        FROM calandra_3_turnos_persistencia
        WHERE fecha >= ? AND fecha <= ?
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
        ORDER BY fecha ASC, hora_inicio ASC, id ASC
    """, (q_start_date, q_end_date)).fetchall()
    conn.close()

    turnos_concatenados = []
    total_prendas_acum = 0
    total_kg_acum = 0.0
    total_valle_acum = 0.0
    total_segundos_efectivos = 0.0
    last_peso_unitario = 1.180

    for r in rows:
        n_up = (r["nombre_turno"] or "").upper()
        k_up = (r["shift_key"] or "").upper()
        if any(x in n_up or x in k_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

        shift_start_iso, shift_end_iso = get_shift_start_end_iso(r["fecha"], r["hora_inicio"], r["hora_fin"])
        
        if shift_end_iso > window_start_str and shift_start_iso < window_end_str:
            p_tot = int(r["prendas_totales"] or 0)
            k_tot = float(r["kgs_totales"] or 0.0)
            v_min = float(r["tiempo_valle_min"] or 0.0)
            p_uni = float(r["peso_unitario"] or 1.180)
            if p_uni > 0:
                last_peso_unitario = p_uni

            try:
                dt_s = datetime.strptime(shift_start_iso, "%Y-%m-%d %H:%M:%S")
                dt_e = datetime.strptime(shift_end_iso, "%Y-%m-%d %H:%M:%S")
                dur_seg = max((dt_e - dt_s).total_seconds(), 60.0)
            except Exception:
                dur_seg = 8 * 3600.0

            dur_horas = dur_seg / 3600.0

            p_h = r["prendas_hora"] or (int(round(p_tot / dur_horas)) if dur_horas > 0 else 0)
            k_h = r["kg_hora"] or (round(k_tot / dur_horas, 1) if dur_horas > 0 else 0.0)

            total_prendas_acum += p_tot
            total_kg_acum += k_tot
            total_valle_acum += v_min
            total_segundos_efectivos += dur_seg

            turnos_concatenados.append({
                "shift_key": r["shift_key"],
                "fecha": r["fecha"],
                "fecha_formateada": datetime.strptime(r["fecha"], "%Y-%m-%d").strftime("%d/%m/%Y") if "-" in r["fecha"] else r["fecha"],
                "turno_identificador": r["turno_identificador"],
                "nombre_turno": r["nombre_turno"],
                "hora_inicio": r["hora_inicio"],
                "hora_fin": r["hora_fin"],
                "rango_horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "duracion_horas": round(dur_horas, 1),
                "prendas_totales": p_tot,
                "prendas_totales_str": f"{p_tot:,}".replace(",", ".") + " prendas",
                "total_kg": round(k_tot, 1),
                "total_kg_str": f"{k_tot:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "peso_unitario": p_uni,
                "peso_unitario_str": f"{int(round(p_uni * 1000))} gr ({p_uni:.3f} kg)",
                "tiempo_valle_min": round(v_min, 1),
                "tiempo_valle_str": f"{v_min:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
                "prendas_hora": p_h,
                "prendas_hora_str": f"{p_h:,}".replace(",", ".") + " p/h",
                "kg_hora": k_h,
                "kg_hora_str": f"{k_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"
            })

    total_horas_efectivas = total_segundos_efectivos / 3600.0
    horas_int = int(total_horas_efectivas)
    minutos_rem = int(round((total_horas_efectivas - horas_int) * 60))

    kg_hora_periodo = round(total_kg_acum / total_horas_efectivas, 1) if total_horas_efectivas > 0 else 0.0
    prendas_hora_periodo = int(round(total_prendas_acum / total_horas_efectivas)) if total_horas_efectivas > 0 else 0

    n_turnos = len(turnos_concatenados)
    prom_prendas_turno = int(round(total_prendas_acum / n_turnos)) if n_turnos > 0 else 0
    prom_kg_turno = round(total_kg_acum / n_turnos, 1) if n_turnos > 0 else 0.0
    prom_valle_turno = round(total_valle_acum / n_turnos, 1) if n_turnos > 0 else 0.0

    return {
        "status": "success",
        "maquina": "CALANDRA_3",
        "maquina_nombre": "Calandra 3",
        "icono": "fa-eye",
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
            "total_turnos": n_turnos,
            "total_prendas": total_prendas_acum,
            "total_prendas_str": f"{total_prendas_acum:,}".replace(",", ".") + " prendas",
            "total_kg": round(total_kg_acum, 1),
            "total_kg_str": f"{total_kg_acum:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "peso_unitario": last_peso_unitario,
            "peso_unitario_str": f"{int(round(last_peso_unitario * 1000))} gr/u ({last_peso_unitario:.3f} kg)",
            "total_tiempo_valle_min": round(total_valle_acum, 1),
            "total_tiempo_valle_str": f"{total_valle_acum:,.1f} min".replace(",", "@").replace(".", ",").replace("@", "."),
            "horas_efectivas": round(total_horas_efectivas, 1),
            "horas_efectivas_str": f"{horas_int}h {minutos_rem}m ({round(total_horas_efectivas, 1)}h)",
            "prendas_hora": prendas_hora_periodo,
            "prendas_hora_str": f"{prendas_hora_periodo:,} p/h".replace(",", "."),
            "kg_hora": kg_hora_periodo,
            "kg_hora_str": f"{kg_hora_periodo:,.1f} kg/h".replace(",", "@").replace(".", ",").replace("@", "."),
            "promedio_prendas_turno": prom_prendas_turno,
            "promedio_prendas_turno_str": f"{prom_prendas_turno:,} p/turno".replace(",", "."),
            "promedio_kg_turno": prom_kg_turno,
            "promedio_kg_turno_str": f"{prom_kg_turno:,.1f} kg/turno".replace(",", "@").replace(".", ",").replace("@", "."),
            "promedio_valle_turno": prom_valle_turno,
            "promedio_valle_turno_str": f"{prom_valle_turno:,.1f} min/turno".replace(",", "@").replace(".", ",").replace("@", ".")
        },
        "turnos_concatenados": turnos_concatenados
    }


def get_tunel_vt_totales_periodo(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00"
) -> dict:
    """Calcula los totales consolidados de un período concatenando los turnos de Túnel VT."""
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

    q_start_date = (dt_start - timedelta(days=1)).strftime("%Y-%m-%d")
    q_end_date = (dt_end + timedelta(days=1)).strftime("%Y-%m-%d")

    # Sincronizar turno actual en curso si cae en la ventana
    try:
        cur_j = get_current_jornada_date()
        if cur_j >= q_start_date and cur_j <= q_end_date:
            turnos_cache = get_cached_turnos()
            turno_act = turnos_cache.get("turno_actual", {})
            if is_shift_active(turno_act):
                pkg = build_tunel_vt_shift_json(cur_j, turno_act)
                save_tunel_vt_shift_json(pkg)
    except Exception:
        pass

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT shift_key, fecha, turno_identificador, nombre_turno, hora_inicio, hora_fin,
               prendas_totales, entrada_1, entrada_2, entrada_3,
               tiempo_valle_e1_min, tiempo_valle_e2_min, tiempo_valle_e3_min, tiempo_valle_total_min,
               kgs_totales, peso_unitario, prendas_hora, kg_hora, data_json, updated_at
        FROM tunel_vt_turnos_persistencia
        WHERE fecha >= ? AND fecha <= ?
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
        ORDER BY fecha ASC, hora_inicio ASC, id ASC
    """, (q_start_date, q_end_date)).fetchall()
    conn.close()

    turnos_concatenados = []
    total_prendas_acum = 0
    total_e1_acum = 0
    total_e2_acum = 0
    total_e3_acum = 0
    total_kg_acum = 0.0
    total_valle_acum = 0.0
    total_valle_e1_acum = 0.0
    total_valle_e2_acum = 0.0
    total_valle_e3_acum = 0.0
    total_segundos_efectivos = 0.0
    last_peso_unitario = 0.260

    for r in rows:
        n_up = (r["nombre_turno"] or "").upper()
        k_up = (r["shift_key"] or "").upper()
        if any(x in n_up or x in k_up for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

        shift_start_iso, shift_end_iso = get_shift_start_end_iso(r["fecha"], r["hora_inicio"], r["hora_fin"])
        
        if shift_end_iso > window_start_str and shift_start_iso < window_end_str:
            p_tot = int(r["prendas_totales"] or 0)
            e1 = int(r["entrada_1"] or 0)
            e2 = int(r["entrada_2"] or 0)
            e3 = int(r["entrada_3"] or 0)
            if p_tot > 0 and (e1 + e2 + e3 == 0):
                e1 = p_tot

            k_tot = float(r["kgs_totales"] or 0.0)
            p_uni = float(r["peso_unitario"] or 0.260)
            if p_uni > 0:
                last_peso_unitario = p_uni

            kg_e1 = round(e1 * p_uni, 1)
            kg_e2 = round(e2 * p_uni, 1)
            kg_e3 = round(e3 * p_uni, 1)

            v_tot = float(r["tiempo_valle_total_min"] or 0.0)
            v_e1 = float(r["tiempo_valle_e1_min"] or 0.0)
            v_e2 = float(r["tiempo_valle_e2_min"] or 0.0)
            v_e3 = float(r["tiempo_valle_e3_min"] or 0.0)

            try:
                dt_s = datetime.strptime(shift_start_iso, "%Y-%m-%d %H:%M:%S")
                dt_e = datetime.strptime(shift_end_iso, "%Y-%m-%d %H:%M:%S")
                dur_seg = max((dt_e - dt_s).total_seconds(), 60.0)
            except Exception:
                dur_seg = 8 * 3600.0

            dur_horas = dur_seg / 3600.0

            p_h = r["prendas_hora"] or (int(round(p_tot / dur_horas)) if dur_horas > 0 else 0)
            k_h = r["kg_hora"] or (round(k_tot / dur_horas, 1) if dur_horas > 0 else 0.0)

            total_prendas_acum += p_tot
            total_e1_acum += e1
            total_e2_acum += e2
            total_e3_acum += e3
            total_kg_acum += k_tot
            total_valle_acum += v_tot
            total_valle_e1_acum += v_e1
            total_valle_e2_acum += v_e2
            total_valle_e3_acum += v_e3
            total_segundos_efectivos += dur_seg

            turnos_concatenados.append({
                "shift_key": r["shift_key"],
                "fecha": r["fecha"],
                "fecha_formateada": datetime.strptime(r["fecha"], "%Y-%m-%d").strftime("%d/%m/%Y") if "-" in r["fecha"] else r["fecha"],
                "turno_identificador": r["turno_identificador"],
                "nombre_turno": r["nombre_turno"],
                "hora_inicio": r["hora_inicio"],
                "hora_fin": r["hora_fin"],
                "rango_horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "duracion_horas": round(dur_horas, 1),
                "prendas_totales": p_tot,
                "prendas_totales_str": f"{p_tot:,}".replace(",", ".") + " prendas",
                "entrada_1": e1,
                "entrada_1_str": f"{e1:,}".replace(",", ".") + " E1",
                "entrada_2": e2,
                "entrada_2_str": f"{e2:,}".replace(",", ".") + " E2",
                "entrada_3": e3,
                "entrada_3_str": f"{e3:,}".replace(",", ".") + " E3",
                "total_kg": round(k_tot, 1),
                "total_kg_str": f"{k_tot:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "kg_e1": kg_e1,
                "kg_e1_str": f"{kg_e1:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "kg_e2": kg_e2,
                "kg_e2_str": f"{kg_e2:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "kg_e3": kg_e3,
                "kg_e3_str": f"{kg_e3:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
                "peso_unitario": p_uni,
                "peso_unitario_str": f"{int(round(p_uni * 1000))} gr ({p_uni:.3f} kg)",
                "tiempo_valle_min": round(v_tot, 1),
                "tiempo_valle_str": f"{v_tot:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
                "prendas_hora": p_h,
                "prendas_hora_str": f"{p_h:,}".replace(",", ".") + " p/h",
                "kg_hora": k_h,
                "kg_hora_str": f"{k_h:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h"
            })

    total_horas_efectivas = total_segundos_efectivos / 3600.0
    horas_int = int(total_horas_efectivas)
    minutos_rem = int(round((total_horas_efectivas - horas_int) * 60))

    kg_hora_periodo = round(total_kg_acum / total_horas_efectivas, 1) if total_horas_efectivas > 0 else 0.0
    prendas_hora_periodo = int(round(total_prendas_acum / total_horas_efectivas)) if total_horas_efectivas > 0 else 0

    n_turnos = len(turnos_concatenados)
    pct_e1 = round((total_e1_acum / total_prendas_acum) * 100, 1) if total_prendas_acum > 0 else 0.0
    pct_e2 = round((total_e2_acum / total_prendas_acum) * 100, 1) if total_prendas_acum > 0 else 0.0
    pct_e3 = round((total_e3_acum / total_prendas_acum) * 100, 1) if total_prendas_acum > 0 else 0.0
    prom_prendas_turno = int(round(total_prendas_acum / n_turnos)) if n_turnos > 0 else 0
    prom_kg_turno = round(total_kg_acum / n_turnos, 1) if n_turnos > 0 else 0.0
    prom_valle_turno = round(total_valle_acum / n_turnos, 1) if n_turnos > 0 else 0.0

    return {
        "status": "success",
        "maquina": "TUNEL_VT",
        "maquina_nombre": "Túnel VT",
        "icono": "fa-wind",
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
            "total_turnos": n_turnos,
            "total_prendas": total_prendas_acum,
            "total_prendas_str": f"{total_prendas_acum:,}".replace(",", ".") + " prendas",
            "total_e1": total_e1_acum,
            "total_e1_str": f"{total_e1_acum:,}".replace(",", ".") + " E1",
            "total_e2": total_e2_acum,
            "total_e2_str": f"{total_e2_acum:,}".replace(",", ".") + " E2",
            "total_e3": total_e3_acum,
            "total_e3_str": f"{total_e3_acum:,}".replace(",", ".") + " E3",
            "pct_e1": pct_e1,
            "pct_e2": pct_e2,
            "pct_e3": pct_e3,
            "total_kg": round(total_kg_acum, 1),
            "total_kg_str": f"{total_kg_acum:,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "kg_e1_str": f"{round(total_e1_acum * last_peso_unitario, 1):,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "kg_e2_str": f"{round(total_e2_acum * last_peso_unitario, 1):,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "kg_e3_str": f"{round(total_e3_acum * last_peso_unitario, 1):,.1f} kg".replace(",", "@").replace(".", ",").replace("@", "."),
            "peso_unitario": last_peso_unitario,
            "peso_unitario_str": f"{int(round(last_peso_unitario * 1000))} gr/u ({last_peso_unitario:.3f} kg)",
            "total_tiempo_valle_min": round(total_valle_acum, 1),
            "total_tiempo_valle_str": f"{total_valle_acum:,.1f} min".replace(",", "@").replace(".", ",").replace("@", "."),
            "valle_e1_min": round(total_valle_e1_acum, 1),
            "valle_e2_min": round(total_valle_e2_acum, 1),
            "valle_e3_min": round(total_valle_e3_acum, 1),
            "horas_efectivas": round(total_horas_efectivas, 1),
            "horas_efectivas_str": f"{horas_int}h {minutos_rem}m ({round(total_horas_efectivas, 1)}h)",
            "prendas_hora": prendas_hora_periodo,
            "prendas_hora_str": f"{prendas_hora_periodo:,} p/h".replace(",", "."),
            "kg_hora": kg_hora_periodo,
            "kg_hora_str": f"{kg_hora_periodo:,.1f} kg/h".replace(",", "@").replace(".", ",").replace("@", "."),
            "promedio_prendas_turno": prom_prendas_turno,
            "promedio_prendas_turno_str": f"{prom_prendas_turno:,} p/turno".replace(",", "."),
            "promedio_kg_turno": prom_kg_turno,
            "promedio_kg_turno_str": f"{prom_kg_turno:,.1f} kg/turno".replace(",", "@").replace(".", ",").replace("@", "."),
            "promedio_valle_turno": prom_valle_turno,
            "promedio_valle_turno_str": f"{prom_valle_turno:,.1f} min/turno".replace(",", "@").replace(".", ",").replace("@", ".")
        },
        "turnos_concatenados": turnos_concatenados
    }


@router.get("/calandras/CALANDRA_2/totales-periodo")
def get_totales_periodo_calandra2_endpoint(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00",
    user: dict = Depends(check_produccion_permission)
):
    """Calcula totales del período para Calandra 2."""
    return get_calandra_2_totales_periodo(fecha_inicio, hora_inicio, fecha_fin, hora_fin)


@router.get("/calandras/CALANDRA_3/totales-periodo")
def get_totales_periodo_calandra3_endpoint(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00",
    user: dict = Depends(check_produccion_permission)
):
    """Calcula totales del período para Calandra 3."""
    return get_calandra_3_totales_periodo(fecha_inicio, hora_inicio, fecha_fin, hora_fin)


@router.get("/tunel-vt/totales-periodo")
def get_totales_periodo_tunel_vt_endpoint(
    fecha_inicio: str,
    hora_inicio: str = "06:00",
    fecha_fin: str = None,
    hora_fin: str = "22:00",
    user: dict = Depends(check_produccion_permission)
):
    """Calcula totales del período para Túnel VT."""
    return get_tunel_vt_totales_periodo(fecha_inicio, hora_inicio, fecha_fin, hora_fin)


@router.get("/calandras/{maquina_id}/peso-unitario")
def get_peso_unitario_calandra(maquina_id: str):
    """Retorna la configuración de peso unitario para Calandra 2 o Calandra 3."""
    m_id = maquina_id.upper()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM calandras_peso_unitario WHERE maquina = ?", (m_id,)).fetchone()
    conn.close()

    if not row:
        if m_id == "CALANDRA_2":
            return {
                "status": "success",
                "maquina": m_id,
                "peso_pequenas": 0.470,
                "peso_pequenas_gr": 470,
                "peso_grandes": 0.780,
                "peso_grandes_gr": 780,
                "unidad": "kg"
            }
        else:
            return {
                "status": "success",
                "maquina": m_id,
                "peso_unitario": 1.180,
                "peso_unitario_gr": 1180,
                "unidad": "kg"
            }

    if m_id == "CALANDRA_2":
        p_peq = float(row["peso_pequenas"] if row["peso_pequenas"] is not None else 0.470)
        p_gra = float(row["peso_grandes"] if row["peso_grandes"] is not None else 0.780)
        return {
            "status": "success",
            "maquina": m_id,
            "peso_pequenas": p_peq,
            "peso_pequenas_gr": int(round(p_peq * 1000)),
            "peso_grandes": p_gra,
            "peso_grandes_gr": int(round(p_gra * 1000)),
            "unidad": "kg"
        }
    else:
        p_uni = float(row["peso_unitario"] if row["peso_unitario"] is not None else 1.180)
        return {
            "status": "success",
            "maquina": m_id,
            "peso_unitario": p_uni,
            "peso_unitario_gr": int(round(p_uni * 1000)),
            "unidad": "kg"
        }

@router.post("/calandras/{maquina_id}/peso-unitario")
def set_peso_unitario_calandra(maquina_id: str, data: dict):
    """Guarda la configuración de peso unitario para Calandra 2 o Calandra 3 y actualiza el turno en curso."""
    m_id = maquina_id.upper()
    conn = get_db_connection()
    cursor = conn.cursor()

    if m_id == "CALANDRA_2":
        val_peq = data.get("peso_pequenas") or data.get("weight_pequenas_g") or data.get("pequenas_g") or data.get("pequenas") or 470
        val_gra = data.get("peso_grandes") or data.get("weight_grandes_g") or data.get("grandes_g") or data.get("grandes") or 780
        p_peq = float(val_peq)
        p_gra = float(val_gra)
        if p_peq > 10:
            p_peq = round(p_peq / 1000.0, 3)
        if p_gra > 10:
            p_gra = round(p_gra / 1000.0, 3)

        cursor.execute("""
            INSERT INTO calandras_peso_unitario (maquina, peso_pequenas, peso_grandes, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(maquina) DO UPDATE SET
                peso_pequenas = excluded.peso_pequenas,
                peso_grandes = excluded.peso_grandes,
                updated_at = CURRENT_TIMESTAMP
        """, (m_id, p_peq, p_gra))
    else:
        val = data.get("peso_unitario") or data.get("weight_g") or data.get("weight") or data.get("peso") or 1180
        p_uni = float(val)
        if p_uni > 10:
            p_uni = round(p_uni / 1000.0, 3)

        cursor.execute("""
            INSERT INTO calandras_peso_unitario (maquina, peso_unitario, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(maquina) DO UPDATE SET
                peso_unitario = excluded.peso_unitario,
                updated_at = CURRENT_TIMESTAMP
        """, (m_id, p_uni))

    conn.commit()
    conn.close()

    if m_id == "CALANDRA_3":
        try:
            import urllib.request
            import json
            req_data = json.dumps({"weight_g": int(round(p_uni * 1000))}).encode("utf-8")
            req = urllib.request.Request(
                "http://100.127.85.111:5002/api/config/weight",
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                pass
        except Exception as ex:
            print(f"Error sincronizando peso C3 con 5002: {ex}")

    # Regenerar inmediatamente el paquete JSON del turno activo para guardar los nuevos pesos
    try:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})
        if is_shift_active(turno_act):
            fecha_raw = turno_act.get("fecha") or datetime.now().strftime("%Y-%m-%d")
            pkg = build_calandra_shift_json(m_id, fecha=fecha_raw, shift_data=turno_act)
            save_calandra_shift_json(pkg)
    except Exception as e:
        print(f"Error actualizando paquete JSON al cambiar peso {m_id}: {e}")

    if m_id == "CALANDRA_2":
        return {
            "status": "success",
            "message": f"Pesos de Calandra 2 actualizados correctamente",
            "peso_pequenas": p_peq,
            "peso_pequenas_gr": int(round(p_peq * 1000)),
            "peso_grandes": p_gra,
            "peso_grandes_gr": int(round(p_gra * 1000))
        }
    else:
        return {
            "status": "success",
            "message": f"Peso unitario de Calandra 3 actualizado correctamente",
            "peso_unitario": p_uni,
            "peso_unitario_gr": int(round(p_uni * 1000))
        }


# ==========================================
# ENDPOINTS TÚNEL VT (SECADO Y OREADO CONTINUO)
# ==========================================

@router.get("/tunel-vt/dashboard")
def get_tunel_vt_dashboard(user: dict = Depends(check_produccion_permission)):
    """Retorna los datos completos para el Dashboard Ampliado del Túnel VT."""
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

    prod = get_tunel_vt_production(turno_act)

    if shift_active:
        try:
            vt_pkg = build_tunel_vt_shift_json(fecha_raw, turno_act)
            save_tunel_vt_shift_json(vt_pkg)
        except Exception as e:
            print(f"Error auto-guardando turno túnel VT: {e}")

    return {
        "status": "success",
        "maquina_id": "TUNEL_VT",
        "nombre": "TÚNEL VT",
        "tipo": "Secado y Oreado Continuo VT",
        "icono": "fa-wind",
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


@router.get("/tunel-vt/peso-unitario")
def get_peso_unitario_tunel_vt():
    """Retorna la configuración de peso unitario para el Túnel VT."""
    from app.mqtt_subscriber import get_peso_unitario_tunel_vt_db
    p_u = get_peso_unitario_tunel_vt_db()
    return {
        "status": "success",
        "maquina": "TUNEL_VT",
        "peso_unitario": p_u,
        "peso_unitario_gr": int(round(p_u * 1000)),
        "unidad": "kg"
    }


@router.post("/tunel-vt/peso-unitario")
def set_peso_unitario_tunel_vt(data: dict):
    """Guarda la configuración de peso unitario para el Túnel VT."""
    from app.mqtt_subscriber import update_peso_unitario_tunel_vt_db
    val = data.get("peso_unitario") or data.get("weight_g") or data.get("weight") or data.get("peso") or 0.260
    p_uni = float(val)
    if p_uni > 50:
        p_uni = round(p_uni / 1000.0, 3)

    update_peso_unitario_tunel_vt_db(p_uni)
    return {
        "status": "success",
        "message": "Peso unitario de Túnel VT actualizado correctamente",
        "peso_unitario": p_uni,
        "peso_unitario_gr": int(round(p_uni * 1000))
    }


@router.post("/tunel-vt/guardar-turno-json")
def trigger_save_tunel_vt_shift_json(
    fecha: Optional[str] = None,
    turno_numero: Optional[int] = None,
    user: dict = Depends(check_produccion_permission)
):
    """Genera y guarda en la base de datos local SQLite el paquete JSON del turno para Túnel VT."""
    pkg = build_tunel_vt_shift_json(fecha=fecha, turno_numero=turno_numero)
    ok = save_tunel_vt_shift_json(pkg)
    return {
        "status": "success" if ok else "error",
        "message": f"Turno {pkg['turno_identificador']} guardado exitosamente en SQLite para Túnel VT",
        "shift_key": pkg["shift_key"],
        "maquina": "TUNEL_VT",
        "fecha": pkg["fecha"],
        "turno_identificador": pkg["turno_identificador"],
        "hora_inicio": pkg["hora_inicio"],
        "hora_fin": pkg["hora_fin"],
        "rango_horario": pkg["rango_horario"],
        "indicadores_dashboard": pkg["indicadores_dashboard"],
        "desglose_hora_a_hora": pkg["desglose_hora_a_hora"]
    }


@router.get("/tunel-vt/turnos-historial")
def get_tunel_vt_turnos_historial(
    fecha: Optional[str] = None,
    user: dict = Depends(check_produccion_permission)
):
    """Consulta la lista de turnos guardados en SQLite para el Túnel VT."""
    conn = get_db_connection()
    if fecha:
        rows = conn.execute("""
            SELECT shift_key, fecha, turno_identificador, nombre_turno,
                   hora_inicio, hora_fin, rango_horario,
                   prendas_totales, entrada_1, entrada_2, entrada_3,
                   tiempo_valle_e1_min, tiempo_valle_e2_min, tiempo_valle_e3_min, tiempo_valle_total_min,
                   kgs_totales, peso_unitario, prendas_hora, kg_hora, updated_at
            FROM tunel_vt_turnos_persistencia
            WHERE fecha = ? AND prendas_totales > 0
            ORDER BY hora_inicio ASC
        """, (fecha,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT shift_key, fecha, turno_identificador, nombre_turno,
                   hora_inicio, hora_fin, rango_horario,
                   prendas_totales, entrada_1, entrada_2, entrada_3,
                   tiempo_valle_e1_min, tiempo_valle_e2_min, tiempo_valle_e3_min, tiempo_valle_total_min,
                   kgs_totales, peso_unitario, prendas_hora, kg_hora, updated_at
            FROM tunel_vt_turnos_persistencia
            WHERE prendas_totales > 0
            ORDER BY fecha DESC, hora_inicio ASC
        """).fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "shift_key": r["shift_key"],
            "maquina": "TUNEL_VT",
            "fecha": r["fecha"],
            "turno_identificador": r["turno_identificador"],
            "nombre_turno": r["nombre_turno"],
            "hora_inicio": r["hora_inicio"],
            "hora_fin": r["hora_fin"],
            "rango_horario": r["rango_horario"],
            "prendas_totales": r["prendas_totales"],
            "prendas_totales_str": f"{r['prendas_totales']:,}".replace(",", ".") + " prendas",
            "entrada_1": r["entrada_1"],
            "entrada_2": r["entrada_2"],
            "entrada_3": r["entrada_3"],
            "kgs_totales": r["kgs_totales"],
            "kgs_totales_str": f"{r['kgs_totales']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
            "tiempo_valle_min": r["tiempo_valle_total_min"],
            "tiempo_valle_str": f"{r['tiempo_valle_total_min']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
            "prendas_hora": r["prendas_hora"],
            "prendas_hora_str": f"{r['prendas_hora']:,}".replace(",", ".") + " prendas/h",
            "kg_hora": r["kg_hora"],
            "kg_hora_str": f"{r['kg_hora']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg/h",
            "updated_at": r["updated_at"]
        })

    return {
        "status": "success",
        "maquina": "TUNEL_VT",
        "total": len(results),
        "turnos": results
    }


@router.get("/tunel-vt/turnos-historial/{shift_key}")
def get_tunel_vt_turno_json_detalle(
    shift_key: str,
    user: dict = Depends(check_produccion_permission)
):
    """Retorna el paquete JSON completo de un turno persistido para Túnel VT."""
    conn = get_db_connection()
    row = conn.execute("""
        SELECT data_json, fecha, turno_identificador, hora_inicio, hora_fin FROM tunel_vt_turnos_persistencia
        WHERE shift_key = ?
    """, (shift_key,)).fetchone()
    conn.close()

    if not row or not row["data_json"]:
        raise HTTPException(status_code=404, detail="Turno no encontrado en persistencia de Túnel VT")

    # Si el turno consultado es el turno activo en progreso, recalcularlo con la telemetría viva
    now_dt = get_local_now().replace(tzinfo=None)
    current_jornada = get_current_jornada_date()
    fecha_turno = row["fecha"]
    h_start = row["hora_inicio"]
    h_end = row["hora_fin"]
    start_iso, end_iso = get_shift_start_end_iso(fecha_turno, h_start, h_end)
    try:
        dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
        dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
        if (dt_start <= now_dt < dt_end) and (fecha_turno == current_jornada):
            turno_num = int(str(row["turno_identificador"]).replace("Turno", "").strip() or 1)
            turno_dict = {
                "nombre": row["turno_identificador"],
                "fecha": fecha_turno,
                "hora_inicio": h_start,
                "hora_fin": h_end,
                "is_active": True
            }
            pkg = build_tunel_vt_shift_json(fecha=fecha_turno, shift_data=turno_dict, turno_numero=turno_num)
            save_tunel_vt_shift_json(pkg)
            return pkg
    except Exception as ex:
        logger.warning(f"Error refrescando turno activo VT en historial: {ex}")

    try:
        return json.loads(row["data_json"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parseando JSON: {e}")


@router.get("/tunel-vt/turnos-por-fecha/{fecha}")
def get_tunel_vt_shifts_by_date(
    fecha: str,
    user: dict = Depends(check_produccion_permission)
):
    """
    Obtiene la lista de turnos de la jornada especificada para Túnel VT.
    Reconstruye los indicadores y guarda/actualiza el paquete JSON en tunel_vt_turnos_persistencia.
    """
    current_jornada = get_current_jornada_date()
    is_current_jornada = (fecha == current_jornada)
    now_dt = get_local_now().replace(tzinfo=None)

    shifts_template = get_jornada_shifts_template()
    result = []
    seen_keys = set()

    conn = get_db_connection()

    for idx, s_info in enumerate(shifts_template):
        nombre = s_info["nombre"]
        nombre_upper = (nombre or "").upper()
        if any(x in nombre_upper for x in ["FUERA", "SIN TURNO", "INACTIVO"]):
            continue

        h_start = s_info["hora_inicio"]
        h_end = s_info["hora_fin"]
        turno_id = f"Turno {idx + 1}"
        shift_key = f"TUNEL_VT_{fecha}_{turno_id.replace(' ', '_')}"

        start_iso, end_iso = get_shift_start_end_iso(fecha, h_start, h_end)
        try:
            dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
            dt_end = datetime.strptime(end_iso, "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

        is_in_process = (dt_start <= now_dt < dt_end) and is_current_jornada

        # Contar producción en la BD para el intervalo del turno
        row_prod = conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(count_total), 0)
            FROM tunel_vt_produccion
            WHERE timestamp_iso >= ? AND timestamp_iso < ?
        """, (start_iso, end_iso)).fetchone()

        num_records = row_prod[0] if row_prod else 0
        total_prendas_db = row_prod[1] if row_prod else 0

        should_include = (total_prendas_db > 0) or is_in_process

        if should_include:
            turno_dict = {
                "nombre": turno_id,
                "fecha": fecha,
                "hora_inicio": h_start,
                "hora_fin": h_end,
                "is_active": is_in_process
            }
            pkg = build_tunel_vt_shift_json(fecha=fecha, shift_data=turno_dict, turno_numero=idx+1)
            save_tunel_vt_shift_json(pkg)

            ind = pkg.get("indicadores_dashboard", {})
            p_tot = ind.get("prendas_totales", 0)
            kg_tot = ind.get("kgs_totales", 0.0)
            valle_min = ind.get("tiempo_valle_min", 0.0)

            result.append({
                "shift_key": shift_key,
                "maquina": "TUNEL_VT",
                "fecha": fecha,
                "turno_identificador": turno_id,
                "nombre_turno": nombre,
                "horario": f"{h_start} - {h_end}",
                "prendas_totales": p_tot,
                "prendas_totales_str": ind.get("prendas_totales_str", f"{p_tot} prendas"),
                "kgs_totales": kg_tot,
                "kgs_totales_str": ind.get("kgs_totales_str", f"{kg_tot} kg"),
                "tiempo_valle_min": valle_min,
                "tiempo_valle_str": ind.get("tiempo_valle_str", f"{valle_min} min"),
                "prendas_hora": ind.get("prendas_hora", 0),
                "kg_hora": ind.get("kg_hora", 0.0),
                "is_in_progress": is_in_process,
                "estado": "En proceso" if is_in_process else "Procesado",
                "updated_at": pkg.get("meta_info", {}).get("timestamp_actualizacion")
            })
            seen_keys.add(shift_key)

    # Persistidos en tunel_vt_turnos_persistencia
    persisted_rows = conn.execute("""
        SELECT shift_key, fecha, turno_identificador, nombre_turno, hora_inicio, hora_fin,
               prendas_totales, kgs_totales, tiempo_valle_total_min, prendas_hora, kg_hora, updated_at
        FROM tunel_vt_turnos_persistencia
        WHERE fecha = ?
          AND UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
          AND prendas_totales > 0
        ORDER BY hora_inicio ASC, id ASC
    """, (fecha,)).fetchall()
    valid_turno_ids = {f"Turno {i+1}" for i in range(len(shifts_template))}
    for r in persisted_rows:
        if r["shift_key"] not in seen_keys and r["turno_identificador"] in valid_turno_ids:
            result.append({
                "shift_key": r["shift_key"],
                "maquina": "TUNEL_VT",
                "fecha": r["fecha"],
                "turno_identificador": r["turno_identificador"],
                "nombre_turno": r["nombre_turno"],
                "horario": f"{r['hora_inicio']} - {r['hora_fin']}",
                "prendas_totales": r["prendas_totales"],
                "prendas_totales_str": f"{r['prendas_totales']:,}".replace(",", ".") + " prendas",
                "kgs_totales": r["kgs_totales"],
                "kgs_totales_str": f"{r['kgs_totales']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " kg",
                "tiempo_valle_min": r["tiempo_valle_total_min"],
                "tiempo_valle_str": f"{r['tiempo_valle_total_min']:,.1f}".replace(",", "@").replace(".", ",").replace("@", ".") + " min",
                "prendas_hora": r["prendas_hora"],
                "kg_hora": r["kg_hora"],
                "is_in_progress": False,
                "estado": "Procesado",
                "updated_at": r["updated_at"]
            })

    return {"status": "success", "maquina": "TUNEL_VT", "fecha": fecha, "turnos": result}


@router.get("/tunel-vt/turnos-fechas")
def get_tunel_vt_turnos_fechas_disponibles(
    user: dict = Depends(check_produccion_permission)
):
    """Retorna la lista de fechas disponibles con registros de producción o turnos de Túnel VT en SQLite."""
    conn = get_db_connection()
    rows_prod = conn.execute("SELECT DISTINCT substr(timestamp_iso, 1, 10) as f FROM tunel_vt_produccion WHERE count_total > 0 ORDER BY f DESC").fetchall()
    rows_turnos = conn.execute("""
        SELECT DISTINCT fecha as f FROM tunel_vt_turnos_persistencia
        WHERE UPPER(nombre_turno) NOT LIKE '%FUERA%' 
          AND UPPER(nombre_turno) NOT LIKE '%SIN TURNO%'
          AND UPPER(shift_key) NOT LIKE '%FUERA%'
          AND prendas_totales > 0
        ORDER BY f DESC
    """).fetchall()
    conn.close()

    fechas = sorted(list(set([r["f"] for r in rows_prod if r["f"]] + [r["f"] for r in rows_turnos if r["f"]])), reverse=True)
    jornada_hoy = get_current_jornada_date()
    if jornada_hoy not in fechas:
        fechas.insert(0, jornada_hoy)

    return {
        "status": "success",
        "maquina": "TUNEL_VT",
        "fechas": fechas,
        "hoy": jornada_hoy
    }


def sync_all_historical_tunel_vt_shifts() -> int:
    """
    Recorre todas las fechas con registros en tunel_vt_produccion
    y genera/actualiza los paquetes JSON para todos los turnos que tuvieron producción.
    """
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT DISTINCT substr(timestamp_iso, 1, 10) as f
        FROM tunel_vt_produccion
        WHERE timestamp_iso IS NOT NULL AND timestamp_iso != ''
        ORDER BY f ASC
    """).fetchall()
    conn.close()

    fechas = [r["f"] for r in rows if r["f"]]
    turnos_plantilla = get_jornada_shifts_template()

    total_synced = 0
    for fecha in fechas:
        for idx, t_info in enumerate(turnos_plantilla):
            h_start = t_info["hora_inicio"]
            h_end = t_info["hora_fin"]

            start_iso, end_iso = get_shift_start_end_iso(fecha, h_start, h_end)

            conn_check = get_db_connection()
            count_prod = conn_check.execute("""
                SELECT COUNT(*), COALESCE(SUM(count_total), 0)
                FROM tunel_vt_produccion
                WHERE timestamp_iso >= ? AND timestamp_iso < ?
            """, (start_iso, end_iso)).fetchone()
            conn_check.close()

            num_rec = count_prod[0] if count_prod else 0
            tot_p = count_prod[1] if count_prod else 0

            if tot_p > 0:
                t_dict = {
                    "nombre": f"Turno {idx + 1}",
                    "fecha": fecha,
                    "hora_inicio": h_start,
                    "hora_fin": h_end,
                    "is_active": False
                }
                pkg = build_tunel_vt_shift_json(fecha=fecha, shift_data=t_dict, turno_numero=idx+1)
                save_tunel_vt_shift_json(pkg)
                total_synced += 1

    return total_synced


@router.post("/turnos/sync-all-machines")
def sync_all_machines_shifts_endpoint(admin: dict = Depends(check_produccion_permission)):
    """Sincroniza y persiste todos los turnos históricos para Túnel de Lavado, Calandra 2, Calandra 3 y Túnel VT."""
    n_lavado = sync_all_historical_shifts()
    n_c2 = sync_all_historical_calandra_shifts("CALANDRA_2")
    n_c3 = sync_all_historical_calandra_shifts("CALANDRA_3")
    n_vt = sync_all_historical_tunel_vt_shifts()
    return {
        "status": "success",
        "synced": {
            "tunel_lavado": n_lavado,
            "calandra_2": n_c2,
            "calandra_3": n_c3,
            "tunel_vt": n_vt
        }
    }


def get_tabla_horaria_data(machine_id: str = "calandra_3", shift_index: Optional[int] = None) -> dict:
    """
    Construye la matriz semanal hora a hora (cells, hour_slots, totals_by_day, grand_total)
    directamente desde las tablas de persistencia en SQLite (calandra_2_turnos_persistencia y calandra_3_turnos_persistencia).
    Soporta navegación por turnos y actualización en tiempo real.
    """
    m_id_raw = (machine_id or "calandra_3").lower()
    if "2" in m_id_raw:
        db_maquina = "CALANDRA_2"
        table_name = "calandra_2_turnos_persistencia"
        machine_name = "Calandra 2"
        clean_machine_id = "calandra_2"
        is_c2 = True
    else:
        db_maquina = "CALANDRA_3"
        table_name = "calandra_3_turnos_persistencia"
        machine_name = "Calandra 3"
        clean_machine_id = "calandra_3"
        is_c2 = False

    turnos_cache = get_cached_turnos()
    shifts_list = turnos_cache.get("shifts") or [
        {"nombre": "Turno 1", "hora_inicio": "06:00", "hora_fin": "14:00"},
        {"nombre": "Turno 2", "hora_inicio": "14:00", "hora_fin": "21:00"},
        {"nombre": "Turno 3", "hora_inicio": "21:00", "hora_fin": "02:10"}
    ]

    all_shifts = []
    for idx, s in enumerate(shifts_list):
        all_shifts.append({
            "index": idx,
            "name": s.get("nombre") or s.get("name") or f"Turno {idx+1}",
            "start": str(s.get("hora_inicio") or s.get("start") or "06:00")[:5],
            "end": str(s.get("hora_fin") or s.get("end") or "14:00")[:5],
            "is_executing": False
        })

    turno_act = turnos_cache.get("turno_actual", {})
    shift_active = is_shift_active(turno_act)
    current_executing_index = 0
    executing_found = False

    if shift_active:
        t_id, t_num = get_turno_identificador(turno_act, shifts_list)
        if t_num is not None and t_num > 0:
            current_executing_index = max(0, t_num - 1)
            executing_found = True

    if not executing_found:
        now_dt = get_local_now().replace(tzinfo=None)
        now_str = now_dt.strftime("%H:%M")
        for s_idx, s_info in enumerate(all_shifts):
            s_start = s_info["start"]
            s_end = s_info["end"]
            if s_start <= s_end:
                if s_start <= now_str < s_end:
                    current_executing_index = s_idx
                    executing_found = True
                    break
            else:
                if now_str >= s_start or now_str < s_end:
                    current_executing_index = s_idx
                    executing_found = True
                    break

    if current_executing_index < len(all_shifts):
        all_shifts[current_executing_index]["is_executing"] = True

    selected_shift_idx = shift_index if shift_index is not None else current_executing_index
    if selected_shift_idx < 0 or selected_shift_idx >= len(all_shifts):
        selected_shift_idx = 0

    sel_shift = all_shifts[selected_shift_idx]
    shift_name = sel_shift["name"]
    turno_identificador = f"Turno {selected_shift_idx + 1}"
    h_start_str = sel_shift["start"]
    h_end_str = sel_shift["end"]

    curr_jornada = get_current_jornada_date()
    try:
        curr_dt = datetime.strptime(curr_jornada, "%Y-%m-%d")
    except Exception:
        curr_dt = datetime.now()
    
    monday_dt = curr_dt - timedelta(days=curr_dt.weekday())

    day_names = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
    days = []
    for d in range(7):
        d_dt = monday_dt + timedelta(days=d)
        d_str = d_dt.strftime("%Y-%m-%d")
        days.append({
            "index": d,
            "name": day_names[d],
            "date": d_str,
            "date_formatted": d_dt.strftime("%d/%m")
        })

    week_start = days[0]["date"]
    week_end = days[6]["date"]

    try:
        hs = int(h_start_str.split(":")[0])
        he = int(h_end_str.split(":")[0])
        if he <= hs:
            num_hours = (24 - hs) + he
        else:
            num_hours = he - hs
    except Exception:
        hs, he, num_hours = 6, 14, 8

    hour_slots = []
    for s_idx in range(num_hours):
        h1 = (hs + s_idx) % 24
        h2 = (h1 + 1) % 24
        s_start = f"{h1:02d}:00"
        s_end = f"{h2:02d}:00"
        hour_slots.append({
            "index": s_idx,
            "label": f"{s_start} - {s_end}",
            "h_start": h1,
            "h_end": h2,
            "startStr": s_start,
            "endStr": s_end
        })

    # Si el turno seleccionado es el turno activo actual de la jornada de hoy, auto-guardar avance
    if selected_shift_idx == current_executing_index:
        try:
            pkg = build_calandra_shift_json(db_maquina, fecha=curr_jornada, shift_data=turno_act, turno_numero=selected_shift_idx + 1)
            save_calandra_shift_json(pkg)
        except Exception as ex:
            print(f"Error actualizando turno activo para tabla-horaria: {ex}")

    cells = {}
    conn = get_db_connection()

    for d_info in days:
        d_idx = d_info["index"]
        d_date = d_info["date"]

        row = conn.execute(f"""
            SELECT data_json FROM {table_name}
            WHERE fecha = ? AND (turno_identificador = ? OR turno_identificador = ? OR nombre_turno = ?)
            LIMIT 1
        """, (d_date, turno_identificador, shift_name, shift_name)).fetchone()

        desglose = None
        if row and row["data_json"]:
            try:
                pkg_data = json.loads(row["data_json"])
                desglose = pkg_data.get("desglose_hora_a_hora")
            except Exception:
                desglose = None

        if desglose:
            d_prendas = desglose.get("prendas") or []
            d_valle = desglose.get("tiempo_valle_min") or []
            d_grandes = desglose.get("grandes") or []
            d_pequenas = desglose.get("pequenas") or []

            for s_idx in range(num_hours):
                cell_key = f"{d_idx}_{s_idx}"
                sm = int(d_pequenas[s_idx]) if (is_c2 and d_pequenas and s_idx < len(d_pequenas)) else (int(d_prendas[s_idx]) if s_idx < len(d_prendas) else 0)
                lg = int(d_grandes[s_idx]) if (is_c2 and d_grandes and s_idx < len(d_grandes)) else 0
                tot = sm + lg if is_c2 else (int(d_prendas[s_idx]) if s_idx < len(d_prendas) else 0)
                idle = float(d_valle[s_idx]) if s_idx < len(d_valle) else 0.0

                cells[cell_key] = {
                    "small": max(0, sm),
                    "large": max(0, lg),
                    "total": max(0, tot),
                    "idle_min": round(max(0.0, idle), 1)
                }
        else:
            for s_idx in range(num_hours):
                cells[f"{d_idx}_{s_idx}"] = {
                    "small": 0,
                    "large": 0,
                    "total": 0,
                    "idle_min": 0.0
                }

    conn.close()

    totals_by_day = []
    grand_p = 0
    grand_v = 0.0

    for d_idx in range(7):
        d_small = 0
        d_large = 0
        d_idle = 0.0
        for s_idx in range(num_hours):
            c = cells.get(f"{d_idx}_{s_idx}", {})
            d_small += int(c.get("small", 0))
            d_large += int(c.get("large", 0))
            d_idle += float(c.get("idle_min", 0.0))

        d_idle = round(d_idle, 1)
        d_tot = d_small + d_large
        grand_p += d_tot
        grand_v += d_idle

        totals_by_day.append({
            "day": d_idx,
            "small": d_small,
            "large": d_large,
            "total_prendas": d_tot,
            "idle_min": d_idle,
            "total_idle_min": d_idle
        })

    curr_slot_idx = None
    if selected_shift_idx == current_executing_index:
        now_h = get_local_now().hour
        for slot in hour_slots:
            if slot["h_start"] == now_h:
                curr_slot_idx = slot["index"]
                break

    return {
        "success": True,
        "machine_id": clean_machine_id,
        "machine_name": machine_name,
        "shift_index": selected_shift_idx,
        "shift_name": shift_name,
        "shift_start": h_start_str,
        "shift_end": h_end_str,
        "current_executing_shift_index": curr_slot_idx if curr_slot_idx is not None else 0,
        "current_planta_date": curr_jornada,
        "current_planta_hour": get_local_now().hour,
        "week_start": week_start,
        "week_end": week_end,
        "all_shifts": all_shifts,
        "days": days,
        "hour_slots": hour_slots,
        "cells": cells,
        "totals_by_day": totals_by_day,
        "grand_total": {
            "small": sum(t["small"] for t in totals_by_day),
            "large": sum(t["large"] for t in totals_by_day),
            "total_prendas": grand_p,
            "idle_min": round(grand_v, 1),
            "total_idle_min": round(grand_v, 1)
        }
    }


@router.get("/tabla-horaria")
def get_tabla_horaria_api(machine_id: str = "calandra_3", shift_index: Optional[int] = None):
    return get_tabla_horaria_data(machine_id=machine_id, shift_index=shift_index)

