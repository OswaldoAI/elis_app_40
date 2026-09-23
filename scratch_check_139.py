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
        print("Could not connect to Jetson Server A")
        sys.exit(1)

    print("\n--- 1. PING A 192.168.0.139 DESDE JETSON ---")
    stdin, stdout, stderr = ssh.exec_command("ping -c 3 192.168.0.139")
    print(stdout.read().decode('utf-8', errors='ignore'))
    print(stderr.read().decode('utf-8', errors='ignore'))

    print("\n--- 2. CONSULTA HTTP A http://192.168.0.139:8080 ---")
    stdin, stdout, stderr = ssh.exec_command("curl -m 5 -i http://192.168.0.139:8080/ || curl -m 5 -i http://192.168.0.139:8080/api/produccion/summary")
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- 3. BUSQUEDA DE APIS / ENDPOINTS EN 192.168.0.139 ---")
    stdin, stdout, stderr = ssh.exec_command("curl -m 5 -i http://192.168.0.139:8080/docs || curl -m 5 -i http://192.168.0.139:8080/openapi.json")
    print(stdout.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
