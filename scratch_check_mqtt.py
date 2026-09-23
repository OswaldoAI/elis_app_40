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
        except Exception as e:
            pass
            
    if not connected_ip:
        sys.exit(1)

    print("\n--- CARGAS REALES MQTT REGISTRADAS ---")
    cmd_db = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import sqlite3; conn=sqlite3.connect('/app/data/elis_40.db'); rows=conn.execute(\\\"SELECT load_id, timestamp, cliente, categoria, peso_kg, raw_hex FROM tunel_cargas WHERE raw_hex NOT LIKE '%32B0 4010%' ORDER BY load_id DESC\\\").fetchall(); [print(r) for r in rows]\""
    stdin, stdout, stderr = ssh.exec_command(cmd_db)
    print(stdout.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
