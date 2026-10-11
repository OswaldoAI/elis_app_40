from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from typing import Optional
import os
import json
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

def process_tabla_horaria_payload(data: dict) -> dict:
    try:
        hour_slots = data.get("hour_slots", [])
        cells = data.get("cells", {})
        if not hour_slots or not cells:
            return data

        h_start_first = hour_slots[0].get("h_start", 0)
        
        # Slots que ocurren tras medianoche (ej: 00:00, 01:00 en Turno 3 de 21:00 a 02:10)
        midnight_slots = [s["index"] for s in hour_slots if s.get("h_start", 0) < h_start_first]
        if not midnight_slots:
            return data

        corrected_cells = {}
        for d in range(7):
            for s in hour_slots:
                s_idx = s["index"]
                
                if s_idx in midnight_slots:
                    # El Turno 3 del día `d` finaliza en la madrugada del día `d + 1`.
                    # En 5002, esa producción se guardó en la celda del día `d + 1`.
                    source_day = d + 1
                    source_key = f"{source_day}_{s_idx}"
                    raw_c = cells.get(source_key, {}) if source_day < 7 else {}
                else:
                    orig_key = f"{d}_{s_idx}"
                    raw_c = cells.get(orig_key, {})

                sm = int(raw_c.get("small", 0) or 0)
                lg = int(raw_c.get("large", 0) or 0)
                tot_c = raw_c.get("total")
                idle = float(raw_c.get("idle_min", 0.0) or 0.0)

                # Sanitizar desbordamientos anómalos de contadores absolutos de 5002
                if sm > 5000: sm = 0
                if lg > 5000: lg = 0
                if tot_c is not None and tot_c > 5000: tot_c = 0
                if idle > 300: idle = 0.0

                if tot_c is None:
                    tot_c = sm + lg

                corrected_cells[f"{d}_{s_idx}"] = {
                    "small": sm,
                    "large": lg,
                    "total": tot_c,
                    "idle_min": round(idle, 1)
                }

        data["cells"] = corrected_cells

        totals_by_day = []
        grand_total_p = 0
        grand_total_v = 0.0

        for d in range(7):
            day_small = 0
            day_large = 0
            day_v = 0.0
            for s in hour_slots:
                s_idx = s["index"]
                c = corrected_cells.get(f"{d}_{s_idx}", {})
                sm = int(c.get("small", 0) or 0)
                lg = int(c.get("large", 0) or 0)
                tot_c = c.get("total")
                if tot_c is not None and sm == 0 and lg == 0:
                    sm = int(tot_c)
                v = float(c.get("idle_min", 0.0) or 0.0)
                day_small += sm
                day_large += lg
                day_v += v

            day_v = round(day_v, 1)
            day_tot = day_small + day_large
            grand_total_p += day_tot
            grand_total_v += day_v

            totals_by_day.append({
                "day": d,
                "small": day_small,
                "large": day_large,
                "total_prendas": day_tot,
                "idle_min": day_v,
                "total_idle_min": day_v
            })

        data["totals_by_day"] = totals_by_day
        data["grand_total"] = {
            "total_prendas": grand_total_p,
            "total_idle_min": round(grand_total_v, 1),
            "idle_min": round(grand_total_v, 1)
        }

    except Exception as ex:
        print(f"Error procesando payload tabla-horaria: {ex}")
    return data

# Proxy para APIs en tiempo real y configuración de Jetson Server 1 (5002)
from app.routers.produccion_router import get_tabla_horaria_data

# Route para servir /api/tabla-horaria directamente desde SQLite (calandra_2_turnos_persistencia y calandra_3_turnos_persistencia)
@app.api_route("/api/tabla-horaria", methods=["GET", "POST"])
async def api_tabla_horaria_native(request: Request, machine_id: str = "calandra_3", shift_index: Optional[int] = None):
    m_id = request.query_params.get("machine_id") or machine_id
    s_idx = request.query_params.get("shift_index")
    if s_idx is not None:
        try:
            s_idx = int(s_idx)
        except Exception:
            s_idx = shift_index
    else:
        s_idx = shift_index

    data = get_tabla_horaria_data(machine_id=m_id, shift_index=s_idx)
    return Response(content=json.dumps(data, ensure_ascii=False), media_type="application/json")

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
            res_body = response.read()
            return Response(content=res_body, status_code=response.status, media_type=response.headers.get("content-type", "application/json"))
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
                
                # Caso Dashboard Principal (Monitoreo 5002): Inyectar botón y modal para Calandra 2 si no están presentes (solo en monitoreo principal, no en tablas)
                if "CALANDRA 2 (GRANDES Y PEQUEÑAS)" in html and not req_path.lower().startswith("/tabla") and "openWeightModalCalandra2" not in html:
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
                
                # Redirigir el enlace/botón Volver al Dashboard a /inicio
                html = html.replace('href="/"', 'href="/inicio"')
                html = html.replace('href=""', 'href="/inicio"')
                
                # Inyectar auto-refresco de tabla cada 15 segundos y escucha de visibilidad de pestaña
                refresh_script = """
                <script>
                (function() {
                  if (window.EventSource && !window._eventSourcePatched) {
                    window._eventSourcePatched = true;
                    const OrigES = window.EventSource;
                    window.EventSource = function(url, options) {
                      if (url && (url.includes('tabla-stream') || url.includes('stream'))) {
                        return {
                          addEventListener: function() {},
                          removeEventListener: function() {},
                          close: function() {},
                          onerror: null, onmessage: null, onopen: null
                        };
                      }
                      return new OrigES(url, options);
                    };
                  }

                  window._userSelectedShift = null;

                  function patchLoadTableData() {
                    if (typeof window.loadTableData === 'function' && !window.loadTableData._isPatched) {
                      const origLoadTableData = window.loadTableData;
                      window.loadTableData = function(shiftIndex, isExplicit) {
                        if (isExplicit !== undefined) {
                          window._userSelectedShift = isExplicit ? shiftIndex : null;
                        } else if (shiftIndex !== undefined && shiftIndex !== null) {
                          window._userSelectedShift = shiftIndex;
                        }
                        let targetShift = window._userSelectedShift;
                        return origLoadTableData(targetShift !== null ? targetShift : undefined);
                      };
                      window.loadTableData._isPatched = true;
                    }
                  }

                  patchLoadTableData();
                  document.addEventListener('DOMContentLoaded', patchLoadTableData);
                  window.addEventListener('load', patchLoadTableData);

                  setInterval(() => {
                    patchLoadTableData();
                    if (typeof window.loadTableData === 'function') {
                      window.loadTableData();
                    }
                  }, 15000);

                  const triggerInstantRefresh = () => {
                    patchLoadTableData();
                    if (typeof window.loadTableData === 'function') {
                      window.loadTableData();
                    }
                  };

                  document.addEventListener('visibilitychange', () => {
                    if (document.visibilityState === 'visible') {
                      triggerInstantRefresh();
                    }
                  });

                  window.addEventListener('focus', triggerInstantRefresh);
                })();
                </script>
                """
                if "font-awesome" not in html and "</head>" in html:
                    html = html.replace("</head>", f"{fa_link}\n{refresh_script}\n</head>")
                elif "</head>" in html:
                    html = html.replace("</head>", f"{refresh_script}\n</head>")

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

# 8. Rutas Públicas Web Funnel para Versión Móvil y Tablet (Producción)
@app.get("/funnel")
def redirect_funnel():
    return RedirectResponse(url="/funnel/produccion")

@app.get("/funnel/produccion")
def read_funnel_produccion():
    return FileResponse(BASE_DIR / "static" / "funnel_produccion.html")

@app.get("/movil")
@app.get("/mobile")
@app.get("/movil/produccion")
@app.get("/mobile/produccion")
def redirect_mobile_aliases():
    return RedirectResponse(url="/funnel/produccion")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(BASE_DIR / "static" / "images" / "elis_logo.png")

