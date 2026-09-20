import paramiko
import os
import sys
from pathlib import Path

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8', errors='ignore')

JETSON_IP = "100.121.212.67"
JETSON_USER = "elisnajera"
JETSON_PASS = "serveriot2026"
REMOTE_DIR = "/home/elisnajera/elis_4.0_v1"
CONTAINER_NAME = "elis_industry4_app"
HOST_PORT = 8084

def deploy():
    print(f"Connecting to Jetson Server A at {JETSON_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(JETSON_IP, username=JETSON_USER, password=JETSON_PASS, timeout=15)
    print("SSH Connection established.")

    sftp = ssh.open_sftp()

    def remote_mkdir(path):
        try:
            sftp.mkdir(path)
        except IOError:
            pass

    remote_mkdir(REMOTE_DIR)
    remote_mkdir(f"{REMOTE_DIR}/app")
    remote_mkdir(f"{REMOTE_DIR}/app/routers")
    remote_mkdir(f"{REMOTE_DIR}/app/static")
    remote_mkdir(f"{REMOTE_DIR}/app/static/css")
    remote_mkdir(f"{REMOTE_DIR}/app/static/js")
    remote_mkdir(f"{REMOTE_DIR}/app/static/images")

    local_root = Path(__file__).parent.resolve()

    files_to_upload = [
        "Dockerfile",
        "docker-compose.yml",
        "requirements.txt",
        "app/__init__.py",
        "app/database.py",
        "app/models.py",
        "app/auth.py",
        "app/seed.py",
        "app/turnos_sync.py",
        "app/mqtt_subscriber.py",
        "app/main.py",
        "app/routers/__init__.py",
        "app/routers/auth_router.py",
        "app/routers/users_router.py",
        "app/routers/modules_router.py",
        "app/routers/produccion_router.py",
        "app/routers/consumos_router.py",
        "app/static/index.html",
        "app/static/css/styles.css",
        "app/static/js/app.js",
        "app/static/images/elis_logo.png",
        "app/static/images/industria_40.png"
    ]


    print("Uploading project files to Jetson Server A...")
    for rel_path in files_to_upload:
        local_file = local_root / rel_path
        remote_file = f"{REMOTE_DIR}/{rel_path}"
        if local_file.exists():
            sftp.put(str(local_file), remote_file)
            print(f"  Uploaded: {rel_path}")

    sftp.close()

    print("\nDeploying Docker container on Jetson Server A...")
    sudo_pass = f"echo {JETSON_PASS} | sudo -S"

    commands = [
        f"{sudo_pass} chown -R elisnajera:elisnajera /home/elisnajera/.docker || true",
        f"{sudo_pass} docker stop {CONTAINER_NAME} || true",
        f"{sudo_pass} docker rm {CONTAINER_NAME} || true",
        f"cd {REMOTE_DIR} && {sudo_pass} DOCKER_BUILDKIT=0 docker build -t elis_industry4_img .",
        f"{sudo_pass} docker run -d --name {CONTAINER_NAME} -p {HOST_PORT}:8000 --restart always -v elis_data:/app/data elis_industry4_img",
        f"{sudo_pass} docker ps | grep {CONTAINER_NAME}"
    ]

    for cmd in commands:
        print(f"\nExecuting: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', 'ignore')
        err = stderr.read().decode('utf-8', 'ignore')
        if out:
            print(f"STDOUT:\n{out}")
        if err:
            print(f"STDERR:\n{err}")

    # Check container logs
    print("\nFetching container logs...")
    stdin, stdout, stderr = ssh.exec_command(f"{sudo_pass} docker logs --tail 20 {CONTAINER_NAME}")
    print(stdout.read().decode('utf-8', 'ignore'))
    print(stderr.read().decode('utf-8', 'ignore'))

    ssh.close()
    print(f"\nDeployment completed successfully!")
    print(f"URL: http://{JETSON_IP}:{HOST_PORT}/inicio")

if __name__ == "__main__":
    deploy()
