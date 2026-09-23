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
        sys.exit(1)

    print("\n--- 1. PROBAR ENDPOINTS EN 192.168.0.137:5001 ---")
    endpoints = [
        "/api/turnos/jornada",
        "/api/turnos/actual",
        "/api/produccion",
        "/api/tunel",
        "/api/cargas",
        "/api/metrics",
        "/api/history",
        "/api/telemetria",
        "/openapi.json"
    ]
    for ep in endpoints:
        cmd = f"curl -m 2 -i http://192.168.0.137:5001{ep}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore')
        if "200 OK" in out or "200" in out[:30]:
            print(f"✅ {ep}: {out[:300].replace('\n', ' ')}")
        else:
            first_line = out.split('\n')[0] if out else "No response"
            print(f"❌ {ep}: {first_line}")

    ssh.close()

if __name__ == "__main__":
    main()
