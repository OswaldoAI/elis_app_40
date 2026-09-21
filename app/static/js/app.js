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
      <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; padding: 14px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <div style="width: 40px; height: 40px; border-radius: 10px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
            <i class="fas fa-user-clock"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 1.05rem;">${data.turno_activo.nombre} (${data.turno_activo.horario}) — <span style="color: #38bdf8;">📅 ${data.turno_activo.fecha || ''}</span></h4>
            <small style="color: var(--text-muted)">Sincronizado desde: ${data.sync_info.origen} | Frecuencia: ${data.sync_info.frecuencia_sync}</small>
          </div>
        </div>

        <div style="text-align: right;">
          <span style="font-size: 0.85rem; color: #34d399; font-weight: 700;">🟢 CONEXIÓN ACTIVADA</span>
          <div style="font-size: 0.75rem; color: var(--text-muted);">Cache: ${data.sync_info.cache_actualizado}</div>
        </div>
      </div>

      <!-- Cuadrícula de Tarjetas Principales del Turno -->
      <h3 style="color: var(--text-main); font-size: 1.25rem; margin-bottom: 16px;">📊 Indicadores Principales del Turno Actual</h3>
      
      <div class="dashboard-kpi-grid">
        <!-- Tarjeta 1: Kg Totales Turno -->
        <div class="kpi-card-striking kpi-card-cyan">
          <div class="kpi-card-header">
            <h4>${kgInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${kgInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${kgInfo.valor}</div>
          <div class="kpi-card-subtext">${kgInfo.subtexto}</div>
        </div>

        <!-- Tarjeta 2: Cargas Totales Turno -->
        <div class="kpi-card-striking kpi-card-amber">
          <div class="kpi-card-header">
            <h4>${cargasInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${cargasInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${cargasInfo.valor}</div>
          <div class="kpi-card-subtext">${cargasInfo.subtexto}</div>
        </div>

        <!-- Tarjeta 3: Productividad hProd (kg/h) -->
        <div class="kpi-card-striking kpi-card-cyan" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
          <div class="kpi-card-header">
            <h4>${hprodInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${hprodInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${hprodInfo.valor}</div>
          <div class="kpi-card-subtext">${hprodInfo.subtexto}</div>
        </div>

        <!-- Tarjeta 4: Índice de Eficiencia ikProd (%) -->
        <div class="kpi-card-striking" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid ${ikprodBorderColor}; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);">
          <div class="kpi-card-header">
            <h4 style="color: #f8fafc;">${ikprodInfo.titulo}</h4>
            <div class="kpi-icon-circle" style="background: rgba(255, 255, 255, 0.08); color: ${ikprodTextColor};"><i class="fas ${ikprodInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number" style="font-size: 3.3rem; font-weight: 900; color: ${ikprodTextColor}; text-shadow: 0 0 20px ${ikprodTextColor}60;">${ikprodInfo.valor}</div>
          <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 6px 12px; border-radius: 8px; margin-top: 4px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="color: #38bdf8;"><i class="fas fa-clock"></i> ${ikprodInfo.tprom_str || ''}</span>
            <span>${ikprodInfo.neto_str}</span>
          </div>
          <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 8px; font-weight: 600;">
            <i class="fas fa-calculator"></i> ${ikprodInfo.subtexto}
          </div>
        </div>
      </div>

      <!-- Tarjetas Secundarias Compactas (Clientes Atendidos y Programas Ejecutados) -->
      <div class="dashboard-secondary-kpi-grid">
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

      <!-- Gráfica de Avance Productivo del Turno (Dual-Axis) -->
      <div class="chart-section-card">
        <div class="chart-header-row">
          <div class="chart-header-title">
            <i class="fas fa-chart-line" style="color: #38bdf8; font-size: 1.3rem;"></i>
            <h4>Avance Productivo del Turno (Kg/Hora vs Tiempo Acumulado entre Cargas)</h4>
          </div>
          <small style="color: var(--text-muted); font-weight: 600;">Eje Y Izquierdo: Kg producidos | Eje Y Derecho: Tiempo acumulado (min)</small>
        </div>
        <div class="chart-wrapper">
          <canvas id="chart-avance-turno"></canvas>
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
          label: 'Kg Producidos / Hora (kg)',
          data: graficaData.kg_por_hora,
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.15)',
          borderWidth: 3,
          pointBackgroundColor: '#0284c7',
          pointBorderColor: '#38bdf8',
          pointRadius: 5,
          tension: 0.3,
          fill: true,
          yAxisID: 'yKg'
        },
        {
          type: 'bar',
          label: 'Tiempo Acumulado entre Cargas (min)',
          data: graficaData.tiempo_acum_por_hora,
          backgroundColor: 'rgba(245, 158, 11, 0.75)',
          borderColor: '#fbbf24',
          borderWidth: 1,
          borderRadius: 6,
          barPercentage: 0.45,
          yAxisID: 'yTiempo'
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
          ticks: { color: '#94a3b8', font: { weight: 'bold' } }
        },
        yKg: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Kg Producidos (kg)', color: '#38bdf8', font: { weight: 'bold' } },
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#38bdf8', font: { weight: 'bold' } }
        },
        yTiempo: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'Tiempo Acumulado entre Cargas (min)', color: '#fbbf24', font: { weight: 'bold' } },
          grid: { drawOnChartArea: false },
          ticks: { color: '#fbbf24', font: { weight: 'bold' } }
        }
      },
      plugins: {
        legend: {
          labels: { color: '#f8fafc', font: { weight: 'bold', size: 12 } }
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

    container.innerHTML = `
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon amber"><i class="fas fa-bolt"></i></div>
          <div class="metric-info">
            <h4>Potencia Activa (kW)</h4>
            <div class="metric-value">${data.electricidad.potencia_activa_kw} kW</div>
            <small style="color: var(--text-muted)">Hoy: ${data.electricidad.consumo_hoy_kwh} kWh</small>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon blue"><i class="fas fa-water"></i></div>
          <div class="metric-info">
            <h4>Caudal de Agua</h4>
            <div class="metric-value">${data.agua.caudal_m3h} m³/h</div>
            <small style="color: var(--text-muted)">Reciclaje: ${data.agua.reciclaje_porcentaje}%</small>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon green"><i class="fas fa-fire"></i></div>
          <div class="metric-info">
            <h4>Presión de Vapor</h4>
            <div class="metric-value">${data.gas_vapor.presion_vapor_bar} bar</div>
            <small style="color: var(--text-muted)">Caldera: ${data.gas_vapor.temp_caldera}°C</small>
          </div>
        </div>
      </div>
    `;
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
