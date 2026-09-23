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

    print("\n--- DESGLOSE HORA A HORA DEL TURNO 3 DE HOY (2026-09-23_Turno_3) ---")
    cmd_t3 = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import urllib.request, json; res=urllib.request.urlopen('http://127.0.0.1:8000/api/produccion/turnos/historial-json/2026-09-23_Turno_3'); pkg=json.loads(res.read().decode('utf-8')); print(json.dumps(pkg['desglose_horario'], indent=2))\""
    stdin, stdout, stderr = ssh.exec_command(cmd_t3)
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- DESGLOSE HORA A HORA DEL TURNO 1 DE HOY (2026-09-23_Turno_1) ---")
    cmd_t1 = "echo serveriot2026 | sudo -S docker exec elis_industry4_app python -c \"import urllib.request, json; res=urllib.request.urlopen('http://127.0.0.1:8000/api/produccion/turnos/historial-json/2026-09-23_Turno_1'); pkg=json.loads(res.read().decode('utf-8')); print(json.dumps(pkg['desglose_horario'], indent=2))\""
    stdin, stdout, stderr = ssh.exec_command(cmd_t1)
    print(stdout.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
