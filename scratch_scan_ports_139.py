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

    print("\n--- SCAN RAPIDO DE PUERTOS EN 192.168.0.139 ---")
    cmd = "python3 -c \"import socket; ports=[80, 8080, 8000, 8084, 5000, 5001, 3000, 1883, 102, 502, 8081, 8082, 8085, 9000]; [print(f'Puerto {p}: ABIERTO') if (lambda s: (s.settimeout(0.5), s.connect_ex(('192.168.0.139', p))==0)[1])(socket.socket()) else print(f'Puerto {p}: Cerrado/No responde') for p in ports]\""
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode('utf-8', errors='ignore'))

    ssh.close()

if __name__ == "__main__":
    main()
