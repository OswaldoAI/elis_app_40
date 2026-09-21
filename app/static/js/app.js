// ELIS NAJERA 4.0 - Application Frontend Controller

let currentUser = null;
let userPermissions = {};

document.addEventListener('DOMContentLoaded', async () => {
  await checkAuth();
  setupEventListeners();
  handleRoute();
  setupWebSocket();
});

// Check authentication status
async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      userPermissions = data.permissions;
      updateUserUI();
      renderSidebar();
    } else {
      showLoginModal();
    }
  } catch (err) {
    console.error('Error checking auth:', err);
    showLoginModal();
  }
}

// Update User Header Info
function updateUserUI() {
  if (!currentUser) return;
  document.getElementById('current-username').textContent = currentUser.full_name || currentUser.username;
  document.getElementById('current-role').textContent = currentUser.role;
  document.getElementById('user-initial').textContent = currentUser.username.charAt(0).toUpperCase();

  // Admin menu buttons visibility
  const adminSections = document.querySelectorAll('.admin-only');
  adminSections.forEach(el => {
    el.style.display = (currentUser.role === 'Admin') ? 'block' : 'none';
  });
}

// Render Left Sidebar Buttons with Permissions
function renderSidebar() {
  const produccionBtn = document.getElementById('btn-module-produccion');
  const consumosBtn = document.getElementById('btn-module-consumos');

  const canProduccion = userPermissions['produccion'] && userPermissions['produccion'].can_view;
  const canConsumos = userPermissions['consumos'] && userPermissions['consumos'].can_view;

  // Configure Producción Button
  if (canProduccion) {
    produccionBtn.classList.remove('locked');
    produccionBtn.querySelector('.lock-badge').style.display = 'none';
    produccionBtn.title = "Acceso a Módulo Producción";
  } else {
    produccionBtn.classList.add('locked');
    produccionBtn.querySelector('.lock-badge').style.display = 'inline-block';
    produccionBtn.title = "Acceso Restringido para tu rol";
  }

  // Configure Consumos Button
  if (canConsumos) {
    consumosBtn.classList.remove('locked');
    consumosBtn.querySelector('.lock-badge').style.display = 'none';
    consumosBtn.title = "Acceso a Módulo Consumos";
  } else {
    consumosBtn.classList.add('locked');
    consumosBtn.querySelector('.lock-badge').style.display = 'inline-block';
    consumosBtn.title = "Acceso Restringido para tu rol";
  }
}

// Setup Navigation and UI Event Listeners
function setupEventListeners() {
  // Navigation Links
  document.querySelectorAll('.menu-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetView = btn.dataset.view;

      if (btn.classList.contains('locked')) {
        alert('⚠️ Acceso Restringido: Tu perfil no tiene permisos para acceder a este módulo.');
        return;
      }

      switchView(targetView);
    });
  });

  // Login Form Submission
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value.trim();

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (res.ok) {
        const data = await res.json();
        currentUser = data.user;
        userPermissions = data.permissions;
        closeLoginModal();
        updateUserUI();
        renderSidebar();
        switchView('inicio');
      } else {
        const errData = await res.json();
        document.getElementById('login-error').textContent = errData.detail || 'Error de autenticación';
        document.getElementById('login-error').style.display = 'block';
      }
    } catch (err) {
      console.error('Login error:', err);
    }
  });

  // Logout Button
  document.getElementById('btn-logout').addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    userPermissions = {};
    showLoginModal();
  });

  // User Preset Selector in Login Modal
  document.getElementById('preset-user-select').addEventListener('change', (e) => {
    const role = e.target.value;
    if (!role) return;
    document.getElementById('login-username').value = role;
    document.getElementById('login-password').value = (role === 'Admin') ? 'admin1' : 'admin';
  });

  // User Management Form Submit
  document.getElementById('form-create-user')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('new-username').value.trim();
    const full_name = document.getElementById('new-fullname').value.trim();
    const role = document.getElementById('new-role').value;
    const password = document.getElementById('new-password').value.trim() || 'admin';

    const res = await fetch('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, full_name, role, password })
    });

    if (res.ok) {
      alert('Usuario creado correctamente');
      document.getElementById('form-create-user').reset();
      loadUsersList();
    } else {
      const err = await res.json();
      alert('Error: ' + (err.detail || 'No se pudo crear el usuario'));
    }
  });
}

// Switch View Sections (Manages Full Screen vs Sidebar Layout)
function switchView(viewName) {
  document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
  document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));

  const sidebarEl = document.querySelector('.sidebar');

  if (viewName === 'tunel_lavado') {
    // Quitar menú de la izquierda para vista panorámica completa del dashboard
    if (sidebarEl) sidebarEl.style.display = 'none';
  } else {
    // Mostrar menú de la izquierda en las demás vistas
    if (sidebarEl) sidebarEl.style.display = 'flex';
  }

  const targetSec = document.getElementById(`view-${viewName}`);
  const targetBtn = document.querySelector(`.menu-btn[data-view="${viewName}"]`);

  if (targetSec) {
    targetSec.classList.add('active');
  }
  if (targetBtn) {
    targetBtn.classList.add('active');
  } else if (viewName === 'tunel_lavado') {
    const prodBtn = document.querySelector(`.menu-btn[data-view="produccion"]`);
    if (prodBtn) prodBtn.classList.add('active');
  }

  // Update browser location hash
  window.location.hash = `#${viewName}`;

  // Load section specific data
  if (viewName === 'produccion') loadProduccionData();
  if (viewName === 'tunel_lavado') loadTunelLavadoDashboard();
  if (viewName === 'consumos') loadConsumosData();
  if (viewName === 'usuarios') loadUsersList();
  if (viewName === 'permisos') loadPermissionsMatrix();
}

function handleRoute() {
  const hash = window.location.hash.replace('#', '') || 'inicio';
  switchView(hash);
}

// WebSocket Connection Controller for Real-Time Telemetry Updates
let appSocket = null;

function setupWebSocket() {
  if (appSocket && (appSocket.readyState === WebSocket.OPEN || appSocket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/tunel`;

  try {
    appSocket = new WebSocket(wsUrl);

    appSocket.onopen = () => {
      console.log('⚡ Conexión WebSocket activada para datos en tiempo real');
    };

    appSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'new_carga' || msg.type === 'update_dashboard') {
          console.log('📥 Notificación en tiempo real recibida vía WebSocket:', msg);
          const currentHash = window.location.hash.replace('#', '') || 'inicio';
          if (currentHash === 'tunel_lavado') {
            loadTunelLavadoDashboard();
          } else if (currentHash === 'produccion') {
            loadProduccionData();
          }
        }
      } catch (e) {
        console.error('Error procesando mensaje WebSocket:', e);
      }
    };

    appSocket.onclose = () => {
      console.warn('⚠️ WebSocket desconectado. Reintentando reconexión en 5s...');
      setTimeout(setupWebSocket, 5000);
    };

    appSocket.onerror = (err) => {
      console.error('Error WebSocket:', err);
    };
  } catch (err) {
    console.error('Error al inicializar WebSocket:', err);
  }
}

// Modal Controllers
function showLoginModal() {
  document.getElementById('login-modal').classList.add('active');
  document.getElementById('login-error').style.display = 'none';
}

function closeLoginModal() {
  document.getElementById('login-modal').classList.remove('active');
}

// Load Produccion Data: Rendering Graphic Cards for Machines
async function loadProduccionData() {
  const container = document.getElementById('produccion-content');
  try {
    const res = await fetch('/api/produccion/summary');
    if (!res.ok) throw new Error('Acceso no autorizado al módulo de producción');
    const data = await res.json();

    let html = `
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon blue"><i class="fas fa-weight-hanging"></i></div>
          <div class="metric-info">
            <h4>Kilos Lavados Hoy</h4>
            <div class="metric-value">${data.kilos_lavados_hoy.toLocaleString()} kg</div>
            <small style="color: var(--text-muted)">Objetivo: ${data.objetivo_diario.toLocaleString()} kg</small>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon green"><i class="fas fa-chart-pie"></i></div>
          <div class="metric-info">
            <h4>Eficiencia Global OEE</h4>
            <div class="metric-value" style="color: #34d399;">${data.eficiencia_global_oee}%</div>
            <small style="color: var(--text-muted)">Líneas 100% Operativas</small>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon purple"><i class="fas fa-cubes"></i></div>
          <div class="metric-info">
            <h4>Máquinas en Servicio</h4>
            <div class="metric-value">4 / 4</div>
            <small style="color: var(--text-muted)">Inspección Óptica Activa</small>
          </div>
        </div>
      </div>

      <h3 style="margin-top: 32px; margin-bottom: 8px; font-size: 1.3rem; color: var(--text-main);">
        🏭 Monitoreo en Tiempo Real de Máquinas y Procesos
      </h3>
      <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 20px;">
        Haz clic sobre la tarjeta de la máquina para acceder a su Dashboard Ampliado en tiempo real:
      </p>

      <div class="machines-grid">
    `;

    data.maquinas.forEach(m => {
      const isClickable = m.clickable;
      const clickAttr = isClickable ? `onclick="switchView('tunel_lavado')"` : '';
      const cardClass = isClickable ? 'machine-card clickable-card' : 'machine-card';

      html += `
        <div class="${cardClass}" id="card-${m.id}" ${clickAttr}>
          ${isClickable ? '<span class="card-link-badge"><i class="fas fa-external-link-alt"></i> Dashboard Ampliado</span>' : ''}
          <div class="machine-header-row">
            <div class="machine-title-box">
              <div class="machine-avatar">
                <i class="fas ${m.icono}"></i>
              </div>
              <div class="machine-title-text">
                <h3>${m.nombre}</h3>
                <span class="machine-subtitle">${m.tipo}</span>
              </div>
            </div>
            <div class="machine-status-badge status-operativa">
              <span class="status-dot"></span>
              ${m.estado}
            </div>
          </div>
      `;

      // Custom Shift Banner and Shift Indicators
      if (m.turno_info) {
        html += `
          <div class="shift-banner">
            <span class="shift-title"><i class="fas fa-user-clock"></i> ${m.turno_info.nombre} (${m.turno_info.horario})</span>
            <span class="shift-time"><i class="fas fa-calendar-alt"></i> ${m.turno_info.fecha || ''}</span>
          </div>

          <div class="section-subtitle-bar">
            <h4>${m.subtitulo_resumen || 'Resumen turno actual'}</h4>
            <div class="subtitle-line"></div>
          </div>

          <div class="shift-indicators-grid">
            <div class="shift-indicator-box">
              <span class="shift-indicator-label">Promedio Carga</span>
              <span class="shift-indicator-val">${m.indicadores_turno.promedio_carga}</span>
            </div>
            <div class="shift-indicator-box">
              <span class="shift-indicator-label">Promedio Tiempo</span>
              <span class="shift-indicator-val">${m.indicadores_turno.promedio_tiempo_carga}</span>
            </div>
            <div class="shift-indicator-box">
              <span class="shift-indicator-label">Cant. Cargas</span>
              <span class="shift-indicator-val">${m.indicadores_turno.cantidad_cargas}</span>
            </div>
          </div>
        `;
      }

      // Render Telemetry Grid only if metricas_clave has elements
      if (m.metricas_clave && m.metricas_clave.length > 0) {
        html += `
          <div class="telemetry-grid">
            ${m.metricas_clave.map(met => `
              <div class="telemetry-item">
                <span class="telemetry-label">${met.label}</span>
                <span class="telemetry-value">${met.val}</span>
              </div>
            `).join('')}
          </div>
        `;
      }

      html += `
          <div class="performance-section">
            <div class="performance-header">
              <span>Rendimiento OEE / Disponibilidad</span>
              <span class="oee-value-tag">${m.oee}% OEE</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${m.oee}%;"></div>
            </div>
          </div>

          <div class="program-footer">
            <i class="fas fa-play-circle" style="color: #38bdf8;"></i>
            <span><strong>Programa Actual:</strong> ${m.programa_actual}</span>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// Load Tunel de Lavado Ampliado Dashboard (Sin Menú Izquierdo y Sin Telemetría)
async function loadTunelLavadoDashboard() {
  const container = document.getElementById('tunel-lavado-dashboard-content');
  try {
    const res = await fetch('/api/produccion/tunel-lavado/dashboard');
    if (!res.ok) throw new Error('No autorizado');
    const data = await res.json();

    const kgInfo = data.indicadores_destacados.kg_totales_turno;
    const cargasInfo = data.indicadores_destacados.cargas_totales_turno;
    const hprodInfo = data.indicadores_destacados.hprod;
    const ikprodInfo = data.indicadores_destacados.ikprod;
    const clientesInfo = data.indicadores_destacados.clientes_unicos || { titulo: 'Clientes Atendidos', valor: '0 clientes', subtexto: 'Códigos únicos de cliente en turno', icono: 'fa-users' };
    const programasInfo = data.indicadores_destacados.programas_unicos || { titulo: 'Programas Ejecutados', valor: '0 programas', subtexto: 'Categorías/Programas únicos en turno', icono: 'fa-layer-group' };

    // Determinar color de semáforo para el texto numérico de porcentaje de ikProd
    let ikprodTextColor = ikprodInfo.text_color;
    let ikprodBorderColor = ikprodInfo.border_color;
    if (!ikprodTextColor) {
      if (ikprodInfo.color_codigo === 'red') {
        ikprodTextColor = '#ef4444';
        ikprodBorderColor = '#ef4444';
      } else if (ikprodInfo.color_codigo === 'orange') {
        ikprodTextColor = '#f97316';
        ikprodBorderColor = '#f97316';
      } else {
        ikprodTextColor = '#34d399';
        ikprodBorderColor = '#10b981';
      }
    }

    container.innerHTML = `
      <!-- Banner Sincronización de Turno -->
      <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; padding: 10px 16px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 36px; height: 36px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
            <i class="fas fa-user-clock"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 0.95rem;">${data.turno_activo.nombre} (${data.turno_activo.horario}) — <span style="color: #38bdf8;">📅 ${data.turno_activo.fecha || ''}</span></h4>
            <small style="color: var(--text-muted); font-size: 0.72rem;">Sincronizado desde: ${data.sync_info.origen} | Frecuencia: ${data.sync_info.frecuencia_sync}</small>
          </div>
        </div>

        <div style="text-align: right;">
          <span style="font-size: 0.8rem; color: #34d399; font-weight: 700;">🟢 CONEXIÓN ACTIVADA</span>
          <div style="font-size: 0.7rem; color: var(--text-muted);">Cache: ${data.sync_info.cache_actualizado}</div>
        </div>
      </div>

      <!-- Cuadrícula 4 Columnas x 2 Filas del Dashboard -->
      <div class="dashboard-grid-layout">
        <!-- Columna 1, Fila 1: Kg Totales Turno -->
        <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 1; grid-row: 1;">
          <div class="kpi-card-header">
            <h4>${kgInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${kgInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${kgInfo.valor}</div>
          <div class="kpi-card-subtext">${kgInfo.subtexto}</div>
        </div>

        <!-- Columna 1, Fila 2: ikProd (stacked verticalmente bajo Kg Totales) -->
        <div class="kpi-card-striking" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid ${ikprodBorderColor}; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
          <div class="kpi-card-header">
            <h4 style="color: #f8fafc;">${ikprodInfo.titulo}</h4>
            <div class="kpi-icon-circle" style="background: rgba(255, 255, 255, 0.08); color: ${ikprodTextColor};"><i class="fas ${ikprodInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: ${ikprodTextColor}; text-shadow: 0 0 16px ${ikprodTextColor}60;">${ikprodInfo.valor}</div>
          <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 6px; margin-top: 2px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
            <span style="color: #38bdf8;"><i class="fas fa-clock"></i> ${ikprodInfo.tprom_str || ''}</span>
            <span>${ikprodInfo.neto_str}</span>
          </div>
          <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
            <i class="fas fa-calculator"></i> ${ikprodInfo.subtexto}
          </div>
        </div>

        <!-- Columna 2, Fila 1: Cargas Totales Turno -->
        <div class="kpi-card-striking kpi-card-amber" style="grid-column: 2; grid-row: 1;">
          <div class="kpi-card-header">
            <h4>${cargasInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${cargasInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${cargasInfo.valor}</div>
          <div class="kpi-card-subtext">${cargasInfo.subtexto}</div>
        </div>

        <!-- Columna 3, Fila 1: Productividad hProd (kg/h) -->
        <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 3; grid-row: 1; background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
          <div class="kpi-card-header">
            <h4>${hprodInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${hprodInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${hprodInfo.valor}</div>
          <div class="kpi-card-subtext">${hprodInfo.subtexto}</div>
        </div>

        <!-- Columna 4, Fila 1: Clientes y Programas (stacked verticalmente) -->
        <div class="col-secondary-kpis" style="grid-column: 4; grid-row: 1;">
          <div class="kpi-card-compact">
            <div class="kpi-compact-info">
              <h5>${clientesInfo.titulo}</h5>
              <div class="kpi-compact-value">${clientesInfo.valor}</div>
              <div class="kpi-compact-sub">${clientesInfo.subtexto}</div>
            </div>
            <div class="kpi-compact-icon"><i class="fas ${clientesInfo.icono}"></i></div>
          </div>

          <div class="kpi-card-compact">
            <div class="kpi-compact-info">
              <h5>${programasInfo.titulo}</h5>
              <div class="kpi-compact-value">${programasInfo.valor}</div>
              <div class="kpi-compact-sub">${programasInfo.subtexto}</div>
            </div>
            <div class="kpi-compact-icon"><i class="fas ${programasInfo.icono}"></i></div>
          </div>
        </div>

        <!-- Fila 2, Columnas 2 a 4: Gráfica de Avance Productivo -->
        <div class="chart-section-card" style="grid-column: 2 / span 3; grid-row: 2;">
          <div class="chart-header-row">
            <div class="chart-header-title">
              <i class="fas fa-chart-line" style="color: #38bdf8; font-size: 1.1rem;"></i>
              <h4>Avance Productivo del Turno (Kg Acumulados vs Kg Hora vs Cargas/Hora)</h4>
            </div>
            <small style="color: var(--text-muted); font-weight: 600; font-size: 0.72rem;">Eje Y Izq: Kg totales y por hora | Eje Y Der: Cargas por hora</small>
          </div>
          <div class="chart-wrapper">
            <canvas id="chart-avance-turno"></canvas>
          </div>
        </div>
      </div>
    `;

    // Renderizar / Actualizar gráfica Chart.js
    renderAvanceChart(data.grafica_avance);

  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// Chart.js Manager for Shift Progress Chart
let avanceChartInstance = null;

function renderAvanceChart(graficaData) {
  if (!graficaData || !graficaData.labels) return;
  const canvasEl = document.getElementById('chart-avance-turno');
  if (!canvasEl) return;

  if (avanceChartInstance) {
    avanceChartInstance.destroy();
  }

  const ctx = canvasEl.getContext('2d');
  avanceChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: graficaData.labels,
      datasets: [
        {
          type: 'line',
          label: 'Kg Acumulados Turno (kg)',
          data: graficaData.kg_acumulado,
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          borderWidth: 3,
          pointBackgroundColor: '#0284c7',
          pointBorderColor: '#38bdf8',
          pointRadius: 4,
          tension: 0.3,
          fill: false,
          yAxisID: 'yKg'
        },
        {
          type: 'line',
          label: 'Kg de la Hora (kg)',
          data: graficaData.kg_por_hora,
          borderColor: '#34d399',
          borderDash: [5, 5],
          borderWidth: 2.5,
          pointBackgroundColor: '#059669',
          pointBorderColor: '#34d399',
          pointRadius: 4,
          tension: 0.3,
          fill: false,
          yAxisID: 'yKg'
        },
        {
          type: 'bar',
          label: 'Cargas / Hora',
          data: graficaData.cargas_por_hora,
          backgroundColor: 'rgba(245, 158, 11, 0.75)',
          borderColor: '#fbbf24',
          borderWidth: 1,
          borderRadius: 5,
          barPercentage: 0.45,
          yAxisID: 'yCargas'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#94a3b8', font: { weight: 'bold', size: 10 } }
        },
        yKg: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Kg Producidos (kg)', color: '#38bdf8', font: { weight: 'bold', size: 11 } },
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#38bdf8', font: { weight: 'bold', size: 10 } }
        },
        yCargas: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'Cargas / Hora', color: '#fbbf24', font: { weight: 'bold', size: 11 } },
          grid: { drawOnChartArea: false },
          ticks: { color: '#fbbf24', font: { weight: 'bold', size: 10 }, stepSize: 1, precision: 0 }
        }
      },
      plugins: {
        legend: {
          labels: { color: '#f8fafc', font: { weight: 'bold', size: 11 } }
        }
      }
    }
  });
}

// Load Consumos Data
async function loadConsumosData() {
  const container = document.getElementById('consumos-content');
  try {
    const res = await fetch('/api/consumos/summary');
    if (!res.ok) throw new Error('Acceso no autorizado');
    const data = await res.json();

    const g = data.generales || {};
    const agua = data.desglose_agua || {};
    const gas = data.desglose_gas || {};
    const elec = data.desglose_electricidad || {};

    container.innerHTML = `
      <!-- Header Módulo Consumos -->
      <div style="margin-bottom: 24px;">
        <h3 style="color: var(--text-main); font-size: 1.3rem; margin-bottom: 6px;">⚡ Supervisión de Consumos Energéticos e Industriales</h3>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Monitoreo en tiempo real por procesos: Agua, Gas y Energía Eléctrica en Planta ELIS Nájera 4.0</p>
      </div>

      <!-- Sección 1: Consumos Generales de Planta -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>🌐 Consumos Generales de Planta</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid" style="margin-bottom: 28px;">
        <!-- 1. Agua General -->
        <div class="metric-card">
          <div class="metric-icon blue"><i class="fas fa-water"></i></div>
          <div class="metric-info">
            <h4>${g.agua_general?.titulo || 'Agua (General)'}</h4>
            <div class="metric-value">${g.agua_general?.caudal_m3h || 18.5} m³/h</div>
            <small style="color: var(--text-muted)">Hoy: ${g.agua_general?.consumo_hoy_m3 || 210.4} m³ | Reciclaje: ${g.agua_general?.reciclaje_pct || 42}%</small>
          </div>
        </div>

        <!-- 2. Gas General -->
        <div class="metric-card">
          <div class="metric-icon amber" style="background: rgba(234, 88, 12, 0.2); color: #f97316;"><i class="fas fa-fire"></i></div>
          <div class="metric-info">
            <h4>${g.gas_general?.titulo || 'Gas General'}</h4>
            <div class="metric-value">${g.gas_general?.consumo_hoy_m3 || 1540} m³</div>
            <small style="color: var(--text-muted)">Presión: ${g.gas_general?.presion_vapor_bar || 9.2} bar | Caldera: ${g.gas_general?.eficiencia_caldera_pct || 92.4}% ef</small>
          </div>
        </div>

        <!-- 3. Energía Eléctrica General -->
        <div class="metric-card">
          <div class="metric-icon amber"><i class="fas fa-bolt"></i></div>
          <div class="metric-info">
            <h4>${g.energia_electrica?.titulo || 'Energía Eléctrica'}</h4>
            <div class="metric-value">${g.energia_electrica?.potencia_activa_kw || 345.2} kW</div>
            <small style="color: var(--text-muted)">Hoy: ${g.energia_electrica?.consumo_hoy_kwh || 4120} kWh | FP: ${g.energia_electrica?.factor_potencia || 0.96}</small>
          </div>
        </div>
      </div>

      <!-- Sección 2: Desglose de Agua por Proceso -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>💧 Consumos de Agua por Proceso</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid" style="margin-bottom: 20px;">
        <!-- 4. Agua Túnel y Lavadoras (Clicable para expandir/colapsar telemetría) -->
        <div class="metric-card clickable-card" onclick="toggleAguaTunelPanel()" style="cursor: pointer;" title="Haz clic para expandir o colapsar la telemetría">
          <div class="metric-icon blue"><i class="fas fa-shower"></i></div>
          <div class="metric-info" style="width: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <h4>${agua.agua_tunel_lavadoras?.titulo || 'Agua Túnel y Lavadoras'}</h4>
              <span id="agua-tunel-badge" class="card-link-badge" style="font-size: 0.68rem; padding: 2px 6px;">🔍 Ver Telemetría</span>
            </div>
            <div class="metric-value">${agua.agua_tunel_lavadoras?.caudal_m3h || 14.2} m³/h</div>
            <small style="color: var(--text-muted)">Esp: ${agua.agua_tunel_lavadoras?.consumo_especifico_l_kg || 4.8} L/kg | Hoy: ${agua.agua_tunel_lavadoras?.consumo_hoy_m3 || 168.5} m³</small>
          </div>
        </div>
      </div>

      <!-- Panel de Telemetría Incorporado: Agua Túnel y Lavadoras (Colapsado por defecto) -->
      <div id="panel-agua-tunel-telemetria" style="display: none; background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-color); border-radius: 14px; padding: 20px; margin-bottom: 28px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 36px; height: 36px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
              <i class="fas fa-shower"></i>
            </div>
            <div>
              <h4 style="color: var(--text-main); font-size: 1.1rem; margin: 0;">Telemetría Agua Túnel y Lavadoras</h4>
              <small style="color: var(--text-muted); font-size: 0.75rem;">Variable: <strong>AGUA_TUNEL_LAVADORAS</strong> | Factor: <strong>1 pulso = 0,1 m³ (100 Litros)</strong></small>
            </div>
          </div>
        </div>

        <!-- Filtros por Rango de Fechas y Horas -->
        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid var(--border-color); padding: 14px 16px; border-radius: 12px; margin-bottom: 20px;">
          <div style="font-size: 0.8rem; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
            <i class="fas fa-filter"></i> Filtro de Acumulado por Rango de Fecha y Hora
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; align-items: flex-end;">
            <div>
              <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Fecha Inicio:</label>
              <input type="date" id="agua-filter-fecha-inicio" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
            </div>
            <div>
              <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Hora Inicio:</label>
              <input type="time" id="agua-filter-hora-inicio" value="00:00" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
            </div>
            <div>
              <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Fecha Fin:</label>
              <input type="date" id="agua-filter-fecha-fin" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
            </div>
            <div>
              <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Hora Fin:</label>
              <input type="time" id="agua-filter-hora-fin" value="23:59" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
            </div>
            <div>
              <button type="button" onclick="applyAguaTunelFilter()" class="btn-primary" style="padding: 8px 14px; font-size: 0.85rem;">🔍 Aplicar Filtro</button>
            </div>
          </div>
        </div>

        <!-- Tarjeta Acumulador Principal -->
        <div style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 60%, #0f172a 100%); border: 1px solid #38bdf8; border-radius: 14px; padding: 20px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(2, 132, 199, 0.3);">
          <div>
            <div style="font-size: 0.8rem; font-weight: 800; color: #e0f2fe; text-transform: uppercase; letter-spacing: 0.8px;">💧 Acumulador Principal de Consumo</div>
            <div id="agua-acumulado-valor" style="font-size: 2.6rem; font-weight: 900; color: #ffffff; line-height: 1.1; margin: 6px 0;">0.00 m³</div>
            <div id="agua-acumulado-subtexto" style="font-size: 0.78rem; color: #bae6fd; font-weight: 600;">Total Pulsos: 0 | Rango: Hoy</div>
          </div>
          <div style="width: 56px; height: 56px; border-radius: 50%; background: rgba(255, 255, 255, 0.18); display: flex; align-items: center; justify-content: center; font-size: 1.8rem; color: white;">
            <i class="fas fa-hand-holding-water"></i>
          </div>
        </div>

        <!-- Tabla de Registros Entrantes -->
        <div style="font-size: 0.85rem; font-weight: 800; color: var(--text-main); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
          <span>📋 Historial de Pulsos y Lecturas Entrantes</span>
          <span id="agua-tabla-total-count" style="font-size: 0.75rem; color: var(--text-muted);">0 registros</span>
        </div>
        <div style="max-height: 220px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 10px; background: rgba(15, 23, 42, 0.6);">
          <table class="data-table" style="margin-top: 0; font-size: 0.82rem;">
            <thead>
              <tr>
                <th>Timestamp ISO</th>
                <th>Pulsos (Count)</th>
                <th>Volumen (m³)</th>
                <th>Caudal (m³/h)</th>
                <th>Dispositivo / Fuente</th>
              </tr>
            </thead>
            <tbody id="agua-telemetria-table-body">
              <tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Cargando telemetría...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Sección 3: Desglose de Gas por Proceso / Máquina -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>🔥 Consumos de Gas por Proceso / Máquina</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid" style="margin-bottom: 28px;">
        <!-- 5. Gas Túnel VT -->
        <div class="metric-card">
          <div class="metric-icon amber" style="background: rgba(234, 88, 12, 0.2); color: #f97316;"><i class="fas fa-wind"></i></div>
          <div class="metric-info">
            <h4>${gas.gas_tunel_vt?.titulo || 'Gas Túnel VT'}</h4>
            <div class="metric-value">${gas.gas_tunel_vt?.consumo_m3h || 32.5} m³/h</div>
            <small style="color: var(--text-muted)">Hoy: ${gas.gas_tunel_vt?.consumo_hoy_m3 || 260} m³ | Temp Secado: ${gas.gas_tunel_vt?.temp_secado_c || 118}°C</small>
          </div>
        </div>

        <!-- 6. Gas Calandra 1 -->
        <div class="metric-card">
          <div class="metric-icon amber" style="background: rgba(234, 88, 12, 0.2); color: #f97316;"><i class="fas fa-scroll"></i></div>
          <div class="metric-info">
            <h4>${gas.gas_calandra_1?.titulo || 'Gas Calandra 1'}</h4>
            <div class="metric-value">${gas.gas_calandra_1?.consumo_m3h || 45.0} m³/h</div>
            <small style="color: var(--text-muted)">Hoy: ${gas.gas_calandra_1?.consumo_hoy_m3 || 360} m³ | Temp Rodillo: ${gas.gas_calandra_1?.temp_trabajo_c || 175}°C</small>
          </div>
        </div>

        <!-- 7. Gas Calandra 2 -->
        <div class="metric-card">
          <div class="metric-icon amber" style="background: rgba(234, 88, 12, 0.2); color: #f97316;"><i class="fas fa-scroll"></i></div>
          <div class="metric-info">
            <h4>${gas.gas_calandra_2?.titulo || 'Gas Calandra 2'}</h4>
            <div class="metric-value">${gas.gas_calandra_2?.consumo_m3h || 42.8} m³/h</div>
            <small style="color: var(--text-muted)">Hoy: ${gas.gas_calandra_2?.consumo_hoy_m3 || 342.4} m³ | Temp Rodillo: ${gas.gas_calandra_2?.temp_trabajo_c || 175}°C</small>
          </div>
        </div>

        <!-- 8. Gas Calandra 3 -->
        <div class="metric-card">
          <div class="metric-icon amber" style="background: rgba(234, 88, 12, 0.2); color: #f97316;"><i class="fas fa-eye"></i></div>
          <div class="metric-info">
            <h4>${gas.gas_calandra_3?.titulo || 'Gas Calandra 3'}</h4>
            <div class="metric-value">${gas.gas_calandra_3?.consumo_m3h || 48.2} m³/h</div>
            <small style="color: var(--text-muted)">Hoy: ${gas.gas_calandra_3?.consumo_hoy_m3 || 385.6} m³ | Temp Rodillo: ${gas.gas_calandra_3?.temp_trabajo_c || 180}°C</small>
          </div>
        </div>
      </div>

      <!-- Sección 4: Desglose de Electricidad por Proceso / Máquina -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>⚡ Consumos de Electricidad por Proceso / Máquina</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid">
        <!-- 9. Electricidad Túnel -->
        <div class="metric-card">
          <div class="metric-icon amber"><i class="fas fa-circle-notch"></i></div>
          <div class="metric-info">
            <h4>${elec.elec_tunel?.titulo || 'Electricidad Túnel'}</h4>
            <div class="metric-value">${elec.elec_tunel?.potencia_kw || 85.4} kW</div>
            <small style="color: var(--text-muted)">Hoy: ${elec.elec_tunel?.consumo_hoy_kwh || 1024.8} kWh</small>
          </div>
        </div>

        <!-- 10. Electricidad Calandra 1 -->
        <div class="metric-card">
          <div class="metric-icon amber"><i class="fas fa-scroll"></i></div>
          <div class="metric-info">
            <h4>${elec.elec_calandra_1?.titulo || 'Electricidad Calandra 1'}</h4>
            <div class="metric-value">${elec.elec_calandra_1?.potencia_kw || 42.1} kW</div>
            <small style="color: var(--text-muted)">Hoy: ${elec.elec_calandra_1?.consumo_hoy_kwh || 505.2} kWh</small>
          </div>
        </div>

        <!-- 11. Electricidad Calandra 2 -->
        <div class="metric-card">
          <div class="metric-icon amber"><i class="fas fa-scroll"></i></div>
          <div class="metric-info">
            <h4>${elec.elec_calandra_2?.titulo || 'Electricidad Calandra 2'}</h4>
            <div class="metric-value">${elec.elec_calandra_2?.potencia_kw || 39.8} kW</div>
            <small style="color: var(--text-muted)">Hoy: ${elec.elec_calandra_2?.consumo_hoy_kwh || 477.6} kWh</small>
          </div>
        </div>

        <!-- 12. Electricidad Calandra 3 -->
        <div class="metric-card">
          <div class="metric-icon amber"><i class="fas fa-eye"></i></div>
          <div class="metric-info">
            <h4>${elec.elec_calandra_3?.titulo || 'Electricidad Calandra 3'}</h4>
            <div class="metric-value">${elec.elec_calandra_3?.potencia_kw || 46.5} kW</div>
            <small style="color: var(--text-muted)">Hoy: ${elec.elec_calandra_3?.consumo_hoy_kwh || 558.0} kWh</small>
          </div>
        </div>
      </div>
    `;

    // Cargar fechas por defecto y autoejecutar telemetría
    const todayStr = new Date().toISOString().split('T')[0];
    const fechaInicioInput = document.getElementById('agua-filter-fecha-inicio');
    const fechaFinInput = document.getElementById('agua-filter-fecha-fin');
    if (fechaInicioInput && !fechaInicioInput.value) fechaInicioInput.value = todayStr;
    if (fechaFinInput && !fechaFinInput.value) fechaFinInput.value = todayStr;

    fetchAguaTunelData();

  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// Load Users List for Admin
async function loadUsersList() {
  const tbody = document.getElementById('users-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/users');
    if (!res.ok) return;
    const users = await res.json();

    tbody.innerHTML = users.map(u => `
      <tr>
        <td><strong>${u.username}</strong></td>
        <td>${u.full_name}</td>
        <td><span class="badge badge-${u.role.toLowerCase()}">${u.role}</span></td>
        <td>${u.is_active ? '🟢 Activo' : '🔴 Inactivo'}</td>
        <td>
          <button class="btn-header" onclick="resetUserPassword(${u.id}, '${u.username}')">🔑 Pass</button>
          ${u.username !== 'Admin' ? `<button class="btn-header btn-logout" onclick="deleteUser(${u.id})">🗑️ Delete</button>` : ''}
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading users:', err);
  }
}

async function resetUserPassword(userId, username) {
  const newPass = prompt(`Introduce nueva contraseña para ${username}:`, username === 'Admin' ? 'admin1' : 'admin');
  if (!newPass) return;

  const res = await fetch(`/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: newPass })
  });

  if (res.ok) alert('Contraseña actualizada correctamente');
}

async function deleteUser(userId) {
  if (!confirm('¿Eliminar este usuario?')) return;
  const res = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
  if (res.ok) loadUsersList();
}

// Load Permissions Matrix for Admin
async function loadPermissionsMatrix() {
  const container = document.getElementById('permissions-matrix-content');
  if (!container) return;

  try {
    const res = await fetch('/api/modules/permissions');
    if (!res.ok) return;
    const perms = await res.json();

    const roles = ['Admin', 'Dirección', 'producción', 'mtto'];
    const modules = ['produccion', 'consumos'];

    let html = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Rol</th>
            <th>Módulo Producción (Ver)</th>
            <th>Módulo Consumos (Ver)</th>
          </tr>
        </thead>
        <tbody>
    `;

    roles.forEach(role => {
      html += `<tr><td><span class="badge badge-${role.toLowerCase()}">${role}</span></td>`;
      modules.forEach(mod => {
        const item = perms.find(p => p.role === role && p.module_code === mod);
        const canView = item ? item.can_view : false;
        html += `
          <td>
            <input type="checkbox" ${canView ? 'checked' : ''} onchange="togglePermission('${role}', '${mod}', this.checked)">
            <label style="margin-left: 6px; font-size: 0.85rem;">${canView ? 'Permitido' : 'Bloqueado'}</label>
          </td>
        `;
      });
      html += `</tr>`;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    console.error('Error loading permissions:', err);
  }
}

async function togglePermission(role, module_code, can_view) {
  await fetch('/api/modules/permissions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role, module_code, can_view })
  });
  // Refresh sidebar if active user role changed
  await checkAuth();
}

// Telemetría & Panel Incorporado Agua Túnel y Lavadoras (AGUA_TUNEL_LAVADORAS - 0.1 m3/pulso)
function toggleAguaTunelPanel() {
  const panel = document.getElementById('panel-agua-tunel-telemetria');
  const badge = document.getElementById('agua-tunel-badge');
  if (!panel) return;

  const isHidden = panel.style.display === 'none' || panel.style.display === '';
  if (isHidden) {
    panel.style.display = 'block';
    if (badge) badge.innerHTML = '🔼 Ocultar Telemetría';

    const todayStr = new Date().toISOString().split('T')[0];
    const fechaInicioInput = document.getElementById('agua-filter-fecha-inicio');
    const fechaFinInput = document.getElementById('agua-filter-fecha-fin');
    if (fechaInicioInput && !fechaInicioInput.value) fechaInicioInput.value = todayStr;
    if (fechaFinInput && !fechaFinInput.value) fechaFinInput.value = todayStr;

    fetchAguaTunelData();
  } else {
    panel.style.display = 'none';
    if (badge) badge.innerHTML = '🔍 Ver Telemetría';
  }
}

function openAguaTunelModal() {
  toggleAguaTunelPanel();
}

function closeAguaTunelModal() {
  const panel = document.getElementById('panel-agua-tunel-telemetria');
  if (panel) panel.style.display = 'none';
}

function applyAguaTunelFilter() {
  fetchAguaTunelData();
}

async function fetchAguaTunelData() {
  const fechaInicio = document.getElementById('agua-filter-fecha-inicio')?.value || '';
  const horaInicio = document.getElementById('agua-filter-hora-inicio')?.value || '00:00';
  const fechaFin = document.getElementById('agua-filter-fecha-fin')?.value || '';
  const horaFin = document.getElementById('agua-filter-hora-fin')?.value || '23:59';

  const tbody = document.getElementById('agua-telemetria-table-body');
  const valorAccEl = document.getElementById('agua-acumulado-valor');
  const subtextAccEl = document.getElementById('agua-acumulado-subtexto');
  const countEl = document.getElementById('agua-tabla-total-count');

  if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Cargando telemetría...</td></tr>`;

  try {
    const params = new URLSearchParams({
      fecha_inicio: fechaInicio,
      hora_inicio: horaInicio.length === 5 ? `${horaInicio}:00` : horaInicio,
      fecha_fin: fechaFin,
      hora_fin: horaFin.length === 5 ? `${horaFin}:59` : horaFin
    });

    const res = await fetch(`/api/consumos/agua-tunel/telemetria?${params.toString()}`);
    if (!res.ok) throw new Error('Error consultando telemetría de agua');
    const data = await res.json();

    if (valorAccEl) valorAccEl.textContent = `${data.acumulado_m3} m³`;
    if (subtextAccEl) subtextAccEl.textContent = `Total Pulsos: ${data.total_pulsos.toLocaleString()} (0,1 m³/pulso) | Rango: ${data.filtro.start_iso} ➔ ${data.filtro.end_iso}`;
    if (countEl) countEl.textContent = `${data.total_registros} registros`;

    if (tbody) {
      if (data.registros.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 15px;">No se encontraron lecturas en el rango seleccionado.</td></tr>`;
      } else {
        tbody.innerHTML = data.registros.map(r => `
          <tr>
            <td><strong style="color: #38bdf8;">${r.timestamp_iso}</strong></td>
            <td><span style="color: #fbbf24; font-weight: 700;">${r.pulsos} pulsos</span></td>
            <td><span style="color: #34d399; font-weight: 800;">${r.volumen_m3} m³</span></td>
            <td>${r.caudal_m3h} m³/h</td>
            <td><small style="color: var(--text-muted);">${r.dispositivo}</small></td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="color: var(--accent-red); text-align: center;">⚠️ ${err.message}</td></tr>`;
  }
}
