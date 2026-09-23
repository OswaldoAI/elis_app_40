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

    ports = [8000, 5000, 5001, 3000]
    for p in ports:
        print(f"\n--- CONSULTA A http://192.168.0.137:{p} ---")
        cmd = f"curl -m 3 -i http://192.168.0.137:{p}/ || curl -m 3 -i http://192.168.0.137:{p}/api/produccion/summary"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore')
        print(out[:500])

    ssh.close()

if __name__ == "__main__":
    main()
