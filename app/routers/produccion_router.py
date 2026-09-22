from fastapi import APIRouter, HTTPException, Depends, status
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

def calculate_tunel_metrics(turno_act: dict = None):
    """Calcula indicadores reales agregados filtrando estrictamente por el turno activo de Jetson Server 1."""
    if not turno_act:
        turnos_cache = get_cached_turnos()
        turno_act = turnos_cache.get("turno_actual", {})

    fecha = turno_act.get("fecha") or datetime.now().strftime("%Y-%m-%d")
    hora_inicio = turno_act.get("hora_inicio", "06:00")
    hora_fin = turno_act.get("hora_fin", "14:00")
    
    start_iso = f"{fecha} {hora_inicio}:00"
    
    now_dt = get_local_now()
    try:
        dt_start = datetime.strptime(start_iso, "%Y-%m-%d %H:%M:%S")
        if now_dt >= dt_start:
            calc_min = (now_dt - dt_start).total_seconds() / 60.0
            minutos_transcurridos = max(calc_min, 1.0)
        else:
            minutos_transcurridos = float(turno_act.get("minutos_transcurridos") or 1.0)
    except Exception:
        minutos_transcurridos = float(turno_act.get("minutos_transcurridos") or 240)
    
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
            label_str = dt_curr.strftime("%H:00")
            
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

        # Incluir etiqueta final de cierre del turno
        label_fin = dt_end_obj.strftime("%H:00")
        if label_fin not in grafica_labels:
            grafica_labels.append(label_fin)
            grafica_kg_hora.append(0.0)
            grafica_kg_acumulado.append(round(running_kg, 1))
            grafica_cargas_hora.append(0)

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
        "grafica_labels": ["06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00"],
        "grafica_kg_hora": [0.0]*9,
        "grafica_kg_acumulado": [0.0]*9,
        "grafica_cargas_hora": [0]*9,
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

