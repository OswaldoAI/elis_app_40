from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
import os
from pathlib import Path
import urllib.request

from app.database import init_db
from app.seed import seed_database
from app.turnos_sync import start_turnos_background_sync, sync_turnos_from_server_1
from app.mqtt_subscriber import start_mqtt_background_subscriber
from app.telemetria_sync import start_telemetria_background_sync
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
start_telemetria_background_sync(app)


# 3. Servir Archivos Estáticos
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 4. Registrar Routers de la API
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(modules_router.router)
app.include_router(produccion_router.router)
app.include_router(consumos_router.router)
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from app.websocket_manager import ws_manager

# 5. Ruta WebSocket para Telemetría y Notificación en Tiempo Real
@app.websocket("/ws/tunel")
async def websocket_tunel_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

import re

# Proxy para APIs en tiempo real y configuración de Jetson Server 1 (5002)
@app.api_route("/api/conteo_live", methods=["GET", "POST"])
@app.api_route("/api/calandra2/conteo_live", methods=["GET", "POST"])
@app.api_route("/api/config/weight", methods=["GET", "POST"])
async def proxy_5002_api(request: Request):
    path = request.url.path
    target_url = f"http://100.127.85.111:5002{path}"
    if request.query_params:
        target_url += f"?{str(request.query_params)}"
    
    data_bytes = None
    headers = {"User-Agent": request.headers.get("user-agent", "Mozilla/5.0")}

    if request.method in ["POST", "PUT", "PATCH"]:
        data_bytes = await request.body()
        headers["Content-Type"] = request.headers.get("content-type", "application/json")
        
        # Interceptar POST de peso para Calandra 3 en 5002 y sincronizarlo localmente
        if path == "/api/config/weight" and data_bytes:
            try:
                import json
                from app.database import get_db_connection
                b_data = json.loads(data_bytes.decode("utf-8"))
                val = b_data.get("weight_g") or b_data.get("unit_weight_g") or b_data.get("weight") or b_data.get("peso") or b_data.get("peso_unitario")
                if val is not None:
                    w_num = float(val)
                    w_kg = round(w_num / 1000.0, 3) if w_num > 50 else round(w_num, 3)
                    conn = get_db_connection()
                    conn.execute("""
                        INSERT INTO calandras_peso_unitario (maquina, peso_unitario, updated_at)
                        VALUES ('CALANDRA_3', ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(maquina) DO UPDATE SET peso_unitario = excluded.peso_unitario, updated_at = CURRENT_TIMESTAMP
                    """, (w_kg,))
                    conn.commit()
                    conn.close()
            except Exception as ex:
                print(f"Error sincronizando peso C3 local: {ex}")

    req = urllib.request.Request(
        target_url,
        headers=headers,
        method=request.method,
        data=data_bytes
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return Response(content=response.read(), status_code=response.status, media_type=response.headers.get("content-type", "application/json"))
    except Exception as e:
        return Response(content=f'{{"error": "{str(e)}"}}', status_code=502, media_type="application/json")

# 6. Proxy Transparente para Tablas de Producción y Monitoreo (Jetson Server 1)
@app.api_route("/5002", methods=["GET", "POST"])
@app.api_route("/5002/", methods=["GET", "POST"])
@app.api_route("/5002/{path:path}", methods=["GET", "POST"])
@app.api_route("/monitoreo", methods=["GET", "POST"])
@app.api_route("/tabla", methods=["GET", "POST"])
@app.api_route("/tabla/", methods=["GET", "POST"])
@app.api_route("/tabla/{path:path}", methods=["GET", "POST"])
def proxy_tabla_produccion(request: Request, path: str = ""):
    req_path = request.url.path
    if req_path == "/5002" or req_path == "/5002/":
        target_url = "http://100.127.85.111:5002/"
    elif req_path.startswith("/5002/"):
        sub = req_path[6:]
        target_url = f"http://100.127.85.111:5002/{sub}"
    elif not path or path == "/":
        target_url = "http://100.127.85.111:5002/"
    elif path.startswith("http"):
        target_url = path
    else:
        target_url = f"http://100.127.85.111:5002/tabla/{path}"
    
    if request.query_params:
        target_url += f"?{str(request.query_params)}"
    
    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": request.headers.get("user-agent", "Mozilla/5.0")},
        method=request.method
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw_content = response.read()
            status_code = response.status
            content_type = response.headers.get("content-type", "text/html; charset=utf-8")
            
            if "text/html" in content_type.lower():
                html = raw_content.decode("utf-8", errors="ignore")
                
                # Inyectar CSS de FontAwesome si no está presente
                fa_link = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
                if "font-awesome" not in html and "</head>" in html:
                    html = html.replace("</head>", f"{fa_link}\n</head>")
                
                # Caso Dashboard Principal (Monitoreo 5002): Inyectar botón y modal para Calandra 2 si no están presentes
                if "CALANDRA 2 (GRANDES Y PEQUEÑAS)" in html and "openWeightModalCalandra2" not in html:
                    target_header = """<div class="panel-title">
                        ⚙️ CALANDRA 2 (GRANDES Y PEQUEÑAS)
                        <span class="panel-badge" id="c2Shift">TURNO 1</span>
                    </div>
                </div>"""
                    replacement_header = """<div class="panel-title">
                        ⚙️ CALANDRA 2 (GRANDES Y PEQUEÑAS)
                        <span class="panel-badge" id="c2Shift">TURNO 1</span>
                    </div>
                    <button class="btn-config" onclick="openWeightModalCalandra2()">
                        ⚙️ Configurar Peso
                    </button>
                </div>"""
                    if target_header in html:
                        html = html.replace(target_header, replacement_header)
                    else:
                        pattern = r'(<div class="panel-title">[\s\S]*?CALANDRA 2[\s\S]*?</span>\s*</div>)(\s*</div>)'
                        replacement = r'\1\n                    <button class="btn-config" onclick="openWeightModalCalandra2()">\n                        ⚙️ Configurar Peso\n                    </button>\2'
                        html = re.sub(pattern, replacement, html)

                    modal_c2_dash = """
                    <div class="modal-overlay" id="weightModalCalandra2">
                        <div class="modal-card">
                            <div class="modal-header">
                                <div class="modal-title">⚙️ Peso por Unidad (Calandra 2)</div>
                                <button class="modal-close" type="button" onclick="closeWeightModalCalandra2()">&times;</button>
                            </div>
                            <form id="weightFormCalandra2" onsubmit="saveWeightConfigCalandra2(event)">
                                <div class="form-group">
                                    <label class="form-label">Prendas Pequeñas (Servilletas) (kg):</label>
                                    <div class="form-input-group">
                                        <input type="number" id="inputWeightPequenas" class="form-input" min="0.001" step="0.001" placeholder="0.080" required>
                                        <span class="form-unit">kg</span>
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Prendas Grandes (Manteles) (kg):</label>
                                    <div class="form-input-group">
                                        <input type="number" id="inputWeightGrandes" class="form-input" min="0.001" step="0.001" placeholder="0.350" required>
                                        <span class="form-unit">kg</span>
                                    </div>
                                </div>
                                <div class="modal-actions">
                                    <button type="button" class="btn-cancel" onclick="closeWeightModalCalandra2()">Cancelar</button>
                                    <button type="submit" class="btn-save">Guardar Configuración</button>
                                </div>
                            </form>
                        </div>
                    </div>

                    <script>
                        async function openWeightModalCalandra2() {
                            try {
                                const res = await fetch('/api/produccion/calandras/CALANDRA_2/peso-unitario');
                                const data = await res.json();
                                if (data.peso_pequenas !== undefined) {
                                    document.getElementById('inputWeightPequenas').value = data.peso_pequenas;
                                }
                                if (data.peso_grandes !== undefined) {
                                    document.getElementById('inputWeightGrandes').value = data.peso_grandes;
                                }
                            } catch(e) { console.error("Error cargando peso C2:", e); }
                            document.getElementById('weightModalCalandra2').classList.add('active');
                        }

                        function closeWeightModalCalandra2() {
                            document.getElementById('weightModalCalandra2').classList.remove('active');
                        }

                        async function saveWeightConfigCalandra2(e) {
                            e.preventDefault();
                            const peq = parseFloat(document.getElementById('inputWeightPequenas').value);
                            const gra = parseFloat(document.getElementById('inputWeightGrandes').value);
                            if (isNaN(peq) || peq <= 0 || isNaN(gra) || gra <= 0) {
                                alert('Por favor ingrese valores de peso válidos');
                                return;
                            }

                            try {
                                const res = await fetch('/api/produccion/calandras/CALANDRA_2/peso-unitario', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ peso_pequenas: peq, peso_grandes: gra })
                                });
                                const data = await res.json();
                                if (data.status === 'success') {
                                    closeWeightModalCalandra2();
                                    if (typeof showToast === 'function') {
                                        showToast("✅ Pesos C2 actualizados: " + peq + " kg / " + gra + " kg");
                                    } else {
                                        alert("✅ Pesos unitarios de Calandra 2 guardados correctamente");
                                    }
                                    if (typeof updateDashboard === 'function') updateDashboard();
                                } else {
                                    alert("Error: " + (data.message || 'No se pudo guardar'));
                                }
                            } catch(err) {
                                alert("Error guardando configuración C2: " + err);
                            }
                        }
                    </script>
                    """
                    if "</body>" in html:
                        html = html.replace("</body>", f"{modal_c2_dash}\n</body>")
                
                btn_html = '<button class="btn-action btn-blue" onclick="openPesoModal()"><i class="fas fa-balance-scale"></i> Peso x Unidad</button>'
                
                if "calandra3" in path.lower():
                    modal_html = """
                    <div id="modalPeso" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:99999; justify-content:center; align-items:center;">
                      <div style="background:#0f172a; border:1px solid #334155; border-radius:14px; width:380px; padding:1.5rem; color:#fff; box-shadow: 0 20px 40px rgba(0,0,0,0.8); font-family: 'Plus Jakarta Sans', sans-serif;">
                        <h3 style="margin-top:0; font-size:1.15rem; color:#60a5fa; display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                          <i class="fas fa-balance-scale"></i> Peso Unitario - Calandra 3
                        </h3>
                        <p style="font-size:0.8rem; color:#94a3b8; margin-bottom:1.2rem;">Configure el peso medio por prenda (Sábanas) en Kilogramos:</p>
                        <div style="margin-bottom:1.2rem;">
                          <label style="font-size:0.82rem; font-weight:700; color:#cbd5e1; display:block; margin-bottom:0.4rem;">Peso Unitario Sábanas (kg):</label>
                          <input type="number" id="pesoUnitarioSabanas" step="0.001" min="0.001" placeholder="Ej. 0.400" style="width:100%; background:#1e293b; border:1px solid #475569; border-radius:8px; padding:0.65rem; color:#fff; font-weight:700; font-size:1rem; outline:none;">
                        </div>
                        <div style="display:flex; justify-content:flex-end; gap:0.6rem; margin-top:1.5rem;">
                          <button onclick="closePesoModal()" style="background:#334155; color:#fff; border:none; padding:0.55rem 1.1rem; border-radius:8px; font-weight:700; cursor:pointer;">Cancelar</button>
                          <button onclick="savePesoUnitario('CALANDRA_3')" style="background:#2563eb; color:#fff; border:none; padding:0.55rem 1.3rem; border-radius:8px; font-weight:700; cursor:pointer;">Guardar</button>
                        </div>
                      </div>
                    </div>
                    <script>
                    async function openPesoModal() {
                      document.getElementById('modalPeso').style.display = 'flex';
                      try {
                        const res = await fetch('/api/produccion/calandras/CALANDRA_3/peso-unitario');
                        const data = await res.json();
                        if (data.peso_unitario !== undefined) {
                          document.getElementById('pesoUnitarioSabanas').value = data.peso_unitario;
                        }
                      } catch(e) { console.error('Error cargando peso:', e); }
                    }
                    function closePesoModal() { document.getElementById('modalPeso').style.display = 'none'; }
                    async function savePesoUnitario(mId) {
                      const val = parseFloat(document.getElementById('pesoUnitarioSabanas').value);
                      if (isNaN(val) || val <= 0) { alert('Por favor ingrese un peso válido en kg (ej. 0.400)'); return; }
                      try {
                        const res = await fetch('/api/produccion/calandras/' + mId + '/peso-unitario', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({peso_unitario: val})
                        });
                        const data = await res.json();
                        alert('✅ Peso unitario de Calandra 3 guardado correctamente (' + val + ' kg)');
                        closePesoModal();
                      } catch(e) { alert('Error guardando peso: ' + e); }
                    }
                    </script>
                    """
                    if '<div class="action-btns">' in html:
                        html = html.replace('<div class="action-btns">', f'<div class="action-btns">\n{btn_html}')
                    if "</body>" in html:
                        html = html.replace("</body>", f"{modal_html}\n</body>")

                elif "calandra2" in path.lower():
                    modal_html = """
                    <div id="modalPeso" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:99999; justify-content:center; align-items:center;">
                      <div style="background:#0f172a; border:1px solid #334155; border-radius:14px; width:400px; padding:1.5rem; color:#fff; box-shadow: 0 20px 40px rgba(0,0,0,0.8); font-family: 'Plus Jakarta Sans', sans-serif;">
                        <h3 style="margin-top:0; font-size:1.15rem; color:#60a5fa; display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                          <i class="fas fa-balance-scale"></i> Peso Unitario - Calandra 2
                        </h3>
                        <p style="font-size:0.8rem; color:#94a3b8; margin-bottom:1.2rem;">Configure el peso medio en Kilogramos para cada tipo de prenda:</p>
                        <div style="margin-bottom:1rem;">
                          <label style="font-size:0.82rem; font-weight:700; color:#cbd5e1; display:block; margin-bottom:0.4rem;">Prendas Pequeñas (Servilletas) (kg):</label>
                          <input type="number" id="pesoUnitarioPequenas" step="0.001" min="0.001" placeholder="Ej. 0.080" style="width:100%; background:#1e293b; border:1px solid #475569; border-radius:8px; padding:0.65rem; color:#fff; font-weight:700; font-size:1rem; outline:none;">
                        </div>
                        <div style="margin-bottom:1.2rem;">
                          <label style="font-size:0.82rem; font-weight:700; color:#cbd5e1; display:block; margin-bottom:0.4rem;">Prendas Grandes (Manteles) (kg):</label>
                          <input type="number" id="pesoUnitarioGrandes" step="0.001" min="0.001" placeholder="Ej. 0.350" style="width:100%; background:#1e293b; border:1px solid #475569; border-radius:8px; padding:0.65rem; color:#fff; font-weight:700; font-size:1rem; outline:none;">
                        </div>
                        <div style="display:flex; justify-content:flex-end; gap:0.6rem; margin-top:1.5rem;">
                          <button onclick="closePesoModal()" style="background:#334155; color:#fff; border:none; padding:0.55rem 1.1rem; border-radius:8px; font-weight:700; cursor:pointer;">Cancelar</button>
                          <button onclick="savePesoUnitario('CALANDRA_2')" style="background:#2563eb; color:#fff; border:none; padding:0.55rem 1.3rem; border-radius:8px; font-weight:700; cursor:pointer;">Guardar</button>
                        </div>
                      </div>
                    </div>
                    <script>
                    async function openPesoModal() {
                      document.getElementById('modalPeso').style.display = 'flex';
                      try {
                        const res = await fetch('/api/produccion/calandras/CALANDRA_2/peso-unitario');
                        const data = await res.json();
                        if (data.peso_pequenas !== undefined) {
                          document.getElementById('pesoUnitarioPequenas').value = data.peso_pequenas;
                        }
                        if (data.peso_grandes !== undefined) {
                          document.getElementById('pesoUnitarioGrandes').value = data.peso_grandes;
                        }
                      } catch(e) { console.error('Error cargando pesos:', e); }
                    }
                    function closePesoModal() { document.getElementById('modalPeso').style.display = 'none'; }
                    async function savePesoUnitario(mId) {
                      const peq = parseFloat(document.getElementById('pesoUnitarioPequenas').value);
                      const gra = parseFloat(document.getElementById('pesoUnitarioGrandes').value);
                      if (isNaN(peq) || peq <= 0 || isNaN(gra) || gra <= 0) {
                        alert('Por favor ingrese valores de peso válidos en kg para prendas pequeñas y grandes');
                        return;
                      }
                      try {
                        const res = await fetch('/api/produccion/calandras/' + mId + '/peso-unitario', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({peso_pequenas: peq, peso_grandes: gra})
                        });
                        const data = await res.json();
                        alert('✅ Pesos unitarios de Calandra 2 guardados correctamente');
                        closePesoModal();
                      } catch(e) { alert('Error guardando pesos: ' + e); }
                    }
                    </script>
                    """
                    if '<div class="action-btns">' in html:
                        html = html.replace('<div class="action-btns">', f'<div class="action-btns">\n{btn_html}')
                    if "</body>" in html:
                        html = html.replace("</body>", f"{modal_html}\n</body>")
                
                return Response(content=html.encode("utf-8"), status_code=status_code, media_type=content_type)
            
            return Response(content=raw_content, status_code=status_code, media_type=content_type)
    except Exception as e:
        print(f"ERROR PROXY 5002: target_url={target_url}, error={e}")
        return Response(content=f"Error al conectar con tablas de producción ({target_url}): {str(e)}", status_code=502)

# 7. Rutas Principales de la Aplicación
@app.get("/")
def read_root():
    return RedirectResponse(url="/inicio")

@app.get("/inicio")
def read_inicio():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(BASE_DIR / "static" / "images" / "elis_logo.png")
