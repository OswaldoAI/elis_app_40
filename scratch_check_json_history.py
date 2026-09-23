import paramiko
import sys
import json

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

    print("\n--- 1. REGISTROS EN TABLA turnos_persistencia (BD SQLite) ---")
    cmd_db = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import sqlite3, json; conn=sqlite3.connect('/app/data/elis_40.db'); rows=conn.execute('SELECT id, shift_key, fecha, nombre_turno, total_kg, total_cargas, ikprod_pct, updated_at FROM turnos_persistencia ORDER BY id DESC').fetchall(); [print(r) for r in rows]\""
    stdin, stdout, stderr = ssh.exec_command(cmd_db)
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- 2. RESPUESTA DEL ENDPOINT /api/produccion/turnos/historial-json ---")
    cmd_hist = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import urllib.request, json; res=urllib.request.urlopen('http://127.0.0.1:8000/api/produccion/turnos/historial-json'); print(json.dumps(json.loads(res.read().decode('utf-8')), indent=2))\""
    stdin, stdout, stderr = ssh.exec_command(cmd_hist)
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- 3. MUESTRA DEL JSON DEL TURNO ACTUAL ---")
    cmd_pkg = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import urllib.request, json; res=urllib.request.urlopen('http://127.0.0.1:8000/api/produccion/turnos/json-paquete'); print(json.dumps(json.loads(res.read().decode('utf-8')), indent=2)[:800])\""
    stdin, stdout, stderr = ssh.exec_command(cmd_pkg)
    print(stdout.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
