import json
import logging
import threading
import time
from datetime import datetime
import paho.mqtt.client as mqtt
from app.database import get_db_connection

MQTT_BROKER = "192.168.0.116"
MQTT_PORT = 1883
MQTT_USER = "elis_laundry_admin"
MQTT_PASS = "elis_mqtt_secure_2026"
MQTT_TOPIC_TUNEL = "elis/lavanderia/tunel/carga"
MQTT_TOPIC_CALANDRA2 = "elis/calandra2/produccion"
MQTT_TOPIC_CALANDRA3 = "elis/calandra3/produccion"

# Cache en memoria de última telemetría recibida de cada calandra
calandras_live_cache = {
    "CALANDRA_2": {},
    "CALANDRA_3": {}
}

def get_calandras_live_cache():
    """Devuelve copia del último estado recibido por MQTT para ambas calandras."""
    return calandras_live_cache

logger = logging.getLogger("mqtt_subscriber")
logging.basicConfig(level=logging.INFO)

def parse_timestamp_to_iso(ts_str: str) -> str:
    """Convierte cualquier formato de timestamp (DD/MM/YYYY HH:MM:SS, YYYY-MM-DD HH:MM:SS, ISO) a YYYY-MM-DD HH:MM:SS."""
    if not ts_str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_clean = str(ts_str).strip().replace("T", " ")
    try:
        parts = ts_clean.split(" ")
        date_part = parts[0]
        time_part = parts[1] if len(parts) > 1 else "00:00:00"
        time_part = time_part.split(".")[0].split("+")[0]  # Remover microsegundos y zona horaria
        
        if "/" in date_part:
            d_parts = date_part.split("/")
            if len(d_parts) == 3:
                return f"{d_parts[2]}-{d_parts[1].zfill(2)}-{d_parts[0].zfill(2)} {time_part}"
        elif "-" in date_part:
            d_parts = date_part.split("-")
            if len(d_parts) == 3:
                if len(d_parts[0]) == 4:
                    return f"{d_parts[0]}-{d_parts[1].zfill(2)}-{d_parts[2].zfill(2)} {time_part}"
                elif len(d_parts[2]) == 4:
                    return f"{d_parts[2]}-{d_parts[1].zfill(2)}-{d_parts[0].zfill(2)} {time_part}"
    except Exception:
        pass
    return ts_clean

def save_calandra_to_db(maquina: str, payload: dict):
    """Guarda un registro de telemetría de producción de Calandra 2 o 3 en SQLite."""
    try:
        ts_raw = payload.get("timestamp") or datetime.now().isoformat()
        ts_iso = parse_timestamp_to_iso(ts_raw)
        session_id = str(payload.get("session_id", ""))
        sequence_id = int(payload.get("sequence_id", 0))
        shift_name = str(payload.get("shift_name", ""))
        
        if maquina == "CALANDRA_2":
            c_grandes = int(payload.get("count_grandes", 0))
            c_pequenas = int(payload.get("count_pequenas", 0))
            c_total = int(payload.get("count_total", c_grandes + c_pequenas))
            d_grandes = int(payload.get("delta_grandes", 0))
            d_pequenas = int(payload.get("delta_pequenas", 0))
            d_total = int(payload.get("delta_total", d_grandes + d_pequenas))
            w_grandes = float(payload.get("weight_grandes_kg", 0.0))
            w_pequenas = float(payload.get("weight_pequenas_kg", 0.0))
            w_total = float(payload.get("total_weight_kg", w_grandes + w_pequenas))
            idle_g = float(payload.get("idle_min_grandes", 0.0))
            idle_p = float(payload.get("idle_min_pequenas", 0.0))
            idle_tot = max(idle_g, idle_p)
            in_idle = 1 if (payload.get("in_idle_grandes") or payload.get("in_idle_pequenas")) else 0
        else: # CALANDRA_3
            c_total = int(payload.get("count", payload.get("total_historical", 0)))
            c_grandes = c_total
            c_pequenas = 0
            d_total = int(payload.get("delta_count", 0))
            d_grandes = d_total
            d_pequenas = 0
            w_total = float(payload.get("total_weight_kg", 0.0))
            w_grandes = w_total
            w_pequenas = 0.0
            idle_tot = float(payload.get("idle_min", 0.0))
            idle_g = idle_tot
            idle_p = 0.0
            in_idle = 1 if payload.get("in_idle") else 0

        raw_json_str = json.dumps(payload)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO calandras_produccion (
                maquina, timestamp, timestamp_iso, session_id, sequence_id, shift_name,
                count_total, count_grandes, count_pequenas,
                delta_total, delta_grandes, delta_pequenas,
                weight_total_kg, weight_grandes_kg, weight_pequenas_kg,
                idle_min_total, idle_min_grandes, idle_min_pequenas, in_idle, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            maquina, ts_raw, ts_iso, session_id, sequence_id, shift_name,
            c_total, c_grandes, c_pequenas,
            d_total, d_grandes, d_pequenas,
            w_total, w_grandes, w_pequenas,
            idle_tot, idle_g, idle_p, in_idle, raw_json_str
        ))
        conn.commit()
        conn.close()

        # Actualizar cache en memoria
        calandras_live_cache[maquina] = payload

        logger.info(f"✅ [{maquina} MQTT] Guardado: {c_total} prendas (+{d_total}) | {w_total} kg | Idle: {idle_tot:.1f}m")

        # Emitir actualización WS si aplica
        try:
            from app.websocket_manager import ws_manager
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast({"type": "calandra_update", "maquina": maquina, "count": c_total}),
                    loop
                )
            except RuntimeError:
                pass
        except Exception:
            pass

        return True
    except Exception as e:
        logger.error(f"❌ Error guardando telemetría {maquina} en DB: {e}")
        return False

def save_carga_to_db(payload: dict):
    """Guarda un registro de carga recibido por MQTT en la base de datos SQLite."""
    try:
        load_id = payload.get("load_id")
        site = payload.get("site", "Elis Lavanderia Industrial")
        device = payload.get("device", "")
        timestamp_str = payload.get("timestamp", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        timestamp_iso = parse_timestamp_to_iso(timestamp_str)
        cliente = payload.get("cliente", 0)
        categoria = payload.get("categoria", 0)
        peso_kg = float(payload.get("peso_kg", 0.0))
        tiempo_entre_cargas_seg = int(payload.get("tiempo_entre_cargas_seg", 0))
        raw_hex = payload.get("raw_hex", "")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO tunel_cargas 
            (load_id, site, device, timestamp, timestamp_iso, cliente, categoria, peso_kg, tiempo_entre_cargas_seg, raw_hex)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (load_id, site, device, timestamp_str, timestamp_iso, cliente, categoria, peso_kg, tiempo_entre_cargas_seg, raw_hex))
        
        inserted = cursor.rowcount > 0
        conn.commit()
        conn.close()


        if inserted:
            logger.info(f"✅ Nueva Carga #{load_id} registrada: {peso_kg} kg | {tiempo_entre_cargas_seg}s | Cliente #{cliente}")
            # Emitir evento WebSocket en tiempo real
            try:
                from app.websocket_manager import ws_manager
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.run_coroutine_threadsafe(
                        ws_manager.broadcast({"type": "new_carga", "load_id": load_id}),
                        loop
                    )
                except RuntimeError:
                    pass
            except Exception as e:
                logger.warning(f"No se pudo emitir evento WS: {e}")
        else:
            logger.info(f"ℹ️ Carga #{load_id} ya existía en DB (Ignorada duplicada)")
        return True
    except Exception as e:
        logger.error(f"❌ Error guardando carga MQTT en DB: {e}")
        return False

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"✅ Conectado exitosamente al Broker MQTT ({MQTT_BROKER}:{MQTT_PORT})")
        client.subscribe(MQTT_TOPIC_TUNEL)
        client.subscribe(MQTT_TOPIC_CALANDRA2)
        client.subscribe(MQTT_TOPIC_CALANDRA3)
        logger.info(f"📡 Subscrito a tópicos: {MQTT_TOPIC_TUNEL}, {MQTT_TOPIC_CALANDRA2}, {MQTT_TOPIC_CALANDRA3}")
    else:
        logger.warning(f"⚠️ Fallo conexión a Broker MQTT con código resultado: {rc}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        if msg.topic == MQTT_TOPIC_TUNEL:
            logger.info(f"📥 Mensaje MQTT Túnel recibido: {payload_str[:120]}")
            save_carga_to_db(data)
        elif msg.topic == MQTT_TOPIC_CALANDRA2:
            logger.info(f"📥 Mensaje MQTT Calandra 2 recibido: {payload_str[:120]}")
            save_calandra_to_db("CALANDRA_2", data)
        elif msg.topic == MQTT_TOPIC_CALANDRA3:
            logger.info(f"📥 Mensaje MQTT Calandra 3 recibido: {payload_str[:120]}")
            save_calandra_to_db("CALANDRA_3", data)
        else:
            logger.info(f"📥 Mensaje MQTT tópico desconocido [{msg.topic}]: {payload_str[:100]}")
    except Exception as e:
        logger.error(f"❌ Error al procesar mensaje MQTT en {msg.topic}: {e}")

def run_mqtt_loop():
    """Ejecuta el cliente MQTT en bucle de segundo plano con reconexión automática."""
    client = mqtt.Client(client_id="elis_app40_backend", clean_session=False)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            logger.info(f"Intentando conectar a MQTT Broker {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            logger.warning(f"⚠️ Error en cliente MQTT: {e}. Reintentando en 10 segundos...")
            time.sleep(10)

def start_mqtt_background_subscriber(app):
    """Inicia el hilo secundario del subscriptor MQTT al arrancar FastAPI."""
    @app.on_event("startup")
    def launch_mqtt():
        thread = threading.Thread(target=run_mqtt_loop, daemon=True)
        thread.start()
        logger.info("🚀 Hilo secundario de suscripción MQTT iniciado.")
