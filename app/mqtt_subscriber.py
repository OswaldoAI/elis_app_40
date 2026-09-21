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
MQTT_TOPIC = "elis/lavanderia/tunel/carga"

logger = logging.getLogger("mqtt_subscriber")
logging.basicConfig(level=logging.INFO)

def parse_timestamp_to_iso(ts_str: str) -> str:
    """Convierte formato DD/MM/YYYY HH:MM:SS a YYYY-MM-DD HH:MM:SS para ordenamiento ISO en SQLite."""
    try:
        parts = ts_str.strip().split(" ")
        date_parts = parts[0].split("/")
        time_part = parts[1] if len(parts) > 1 else "00:00:00"
        return f"{date_parts[2]}-{date_parts[1].zfill(2)}-{date_parts[0].zfill(2)} {time_part}"
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        client.subscribe(MQTT_TOPIC)
        logger.info(f"📡 Subscrito al tópico: {MQTT_TOPIC}")
    else:
        logger.warning(f"⚠️ Fallo conexión a Broker MQTT con código resultado: {rc}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        logger.info(f"📥 Mensaje MQTT recibido en [{msg.topic}]: {payload_str}")
        data = json.loads(payload_str)
        save_carga_to_db(data)
    except Exception as e:
        logger.error(f"❌ Error al procesar mensaje MQTT: {e}")

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
