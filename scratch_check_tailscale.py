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
        print("Could not connect")
        sys.exit(1)

    print("--- 1. CONTENEDORES DOCKER CORRIENDO ---")
    stdin, stdout, stderr = ssh.exec_command("echo serveriot2026 | sudo -S docker ps")
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("--- 2. PUERTOS ESCUCHANDO EN EL HOST ---")
    stdin, stdout, stderr = ssh.exec_command("echo serveriot2026 | sudo -S netstat -tulnp | grep -E '80|443|8084|8000|8080'")
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("--- 3. CONFIGURACION DE TAILSCALE SERVE / FUNNEL ---")
    stdin, stdout, stderr = ssh.exec_command("echo serveriot2026 | sudo -S tailscale serve status")
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("--- 4. NGINX O CADDY SI EXISTEN ---")
    stdin, stdout, stderr = ssh.exec_command("echo serveriot2026 | sudo -S systemctl status nginx caddy 2>&1 | grep -i -E 'active|running|loaded'")
    print(stdout.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
