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

    print("\n--- 1. TABLA ARP EN JETSON ---")
    stdin, stdout, stderr = ssh.exec_command("arp -a || ip neigh")
    print(stdout.read().decode('utf-8', errors='ignore'))

    print("\n--- 2. PROBAR PINGS A IP CONOCIDAS EN RED LOCAL ---")
    ips_to_test = ["192.168.0.137", "192.168.0.139", "192.168.0.116", "192.168.0.100", "192.168.0.1", "192.168.0.250"]
    for test_ip in ips_to_test:
        cmd = f"ping -c 1 -W 1 {test_ip}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        res = stdout.read().decode('utf-8', errors='ignore')
        if "1 received" in res or "ttl=" in res.lower():
            print(f"  ✅ IP ALCANZABLE: {test_ip}")
        else:
            print(f"  ❌ IP INALCANZABLE: {test_ip}")

    print("\n--- 3. PROBAR CURL A HTTP 192.168.0.137:5001 Y 192.168.0.137:8080 Y OTROS ---")
    ports_to_test = [
        "http://192.168.0.137:5001/api/turnos/jornada",
        "http://192.168.0.137:5001/api/cargas",
        "http://192.168.0.137:8080",
        "http://192.168.0.139:8080",
        "http://192.168.0.139:5001"
    ]
    for url in ports_to_test:
        cmd = f"curl -m 3 -i {url}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore')
        if out:
            print(f"\n--- Respuesta de {url} ---")
            print(out[:400])

    ssh.close()

if __name__ == "__main__":
    main()
