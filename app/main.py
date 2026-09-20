from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import os
from pathlib import Path

from app.database import init_db
from app.seed import seed_database
from app.turnos_sync import start_turnos_background_sync, sync_turnos_from_server_1
from app.mqtt_subscriber import start_mqtt_background_subscriber
from app.routers import (
    auth_router,
    users_router,
    modules_router,
    produccion_router,
    consumos_router
)

app = FastAPI(title="ELIS NAJERA 4.0 - Sistema de Supervisión", version="4.0.0")

# 1. Inicializar base de datos e insertar usuarios/permisos por defecto
@app.on_event("startup")
def startup_event():
    seed_database()

# 2. Iniciar sincronizaciones en segundo plano
start_turnos_background_sync(app)
start_mqtt_background_subscriber(app)


# 3. Servir Archivos Estáticos
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 4. Registrar Routers de la API
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(modules_router.router)
app.include_router(produccion_router.router)
app.include_router(consumos_router.router)

# 5. Rutas Principales de la Aplicación
@app.get("/")
def read_root():
    return RedirectResponse(url="/inicio")

@app.get("/inicio")
def read_inicio():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(BASE_DIR / "static" / "images" / "elis_logo.png")
