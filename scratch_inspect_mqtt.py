import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='ignore')

JETSON_IPS = ["192.168.0.116", "100.121.212.67"]
JETSON_USER = "elisnajera"
JETSON_PASS = "serveriot2026"

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connected_ip = None
    for ip in JETSON_IPS:
        try:
            ssh.connect(ip, username=JETSON_USER, password=JETSON_PASS, timeout=5, look_for_keys=False, allow_agent=False)
            connected_ip = ip
            break
        except Exception:
            pass
            
    if not connected_ip:
        print("Could not connect to Jetson")
        sys.exit(1)

    print("\n--- 1. ULTIMOS LOGS DEL SUSCRIPTOR MQTT EN DOCKER ---")
    cmd_logs = "echo serveriot2026 | sudo -S docker logs --tail 40 elis_industry4_app"
    stdin, stdout, stderr = ssh.exec_command(cmd_logs)
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- 2. ULTIMAS CARGAS REGISTRADAS EN BD (TOTAL Y REALES MQTT) ---")
    cmd_db = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import sqlite3; conn=sqlite3.connect('/app/data/elis_40.db'); print('Ultimas 5 cargas totales:'); [print(r) for r in conn.execute('SELECT load_id, timestamp, timestamp_iso, cliente, categoria, peso_kg, raw_hex FROM tunel_cargas ORDER BY load_id DESC LIMIT 5').fetchall()]; print('\\nUltima carga REAL MQTT (raw_hex != 32B0 4010):'); [print(r) for r in conn.execute(\\\"SELECT load_id, timestamp, timestamp_iso, cliente, categoria, peso_kg, raw_hex FROM tunel_cargas WHERE raw_hex NOT LIKE '%32B0 4010%' ORDER BY load_id DESC LIMIT 1\\\").fetchall()]\""
    stdin, stdout, stderr = ssh.exec_command(cmd_db)
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- 3. PRUEBA DE MENSAJES RETAINED EN EL BROKER MOSQUITTO ---")
    # Intentar suscribirse con timeout de 2 segundos para ver si hay algún mensaje retain
    cmd_mosq = "echo serveriot2026 | sudo -S docker exec elis_mosquitto mosquitto_sub -t 'elis/lavanderia/tunel/#' -W 2 -v"
    stdin, stdout, stderr = ssh.exec_command(cmd_mosq)
    print(stdout.read().decode('utf-8', errors='ignore'))
    print(stderr.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
