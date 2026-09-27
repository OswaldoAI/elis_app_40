// ELIS NAJERA 4.0 - Application Frontend Controller

let currentUser = null;
let userPermissions = {};

document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await checkAuth();
  handleRoute();
  setupWebSocket();
  startAutoRefreshTimer();
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
      setGuestState();
    }
  } catch (err) {
    console.error('Error checking auth:', err);
    setGuestState();
  }
}

function setGuestState() {
  currentUser = { id: 0, username: 'Invitado', role: 'Invitado', full_name: 'Invitado (Acceso Libre)' };
  userPermissions = {
    'produccion': { can_view: true },
    'consumos': { can_view: true }
  };
  updateUserUI();
  renderSidebar();
}

// Update User Header Info
function updateUserUI() {
  const usernameEl = document.getElementById('current-username');
  const roleEl = document.getElementById('current-role');
  const initialEl = document.getElementById('user-initial');
  const btnLoginEl = document.getElementById('btn-open-login');
  const btnChangeUserEl = document.getElementById('btn-change-user');
  const btnLogoutEl = document.getElementById('btn-logout');

  const isGuest = !currentUser || currentUser.role === 'Invitado';

  if (isGuest) {
    if (usernameEl) usernameEl.textContent = 'Invitado';
    if (roleEl) roleEl.textContent = 'Acceso Libre';
    if (initialEl) initialEl.textContent = '?';
    if (btnLoginEl) btnLoginEl.style.display = 'flex';
    if (btnChangeUserEl) btnChangeUserEl.style.display = 'none';
    if (btnLogoutEl) btnLogoutEl.style.display = 'none';

    const adminSections = document.querySelectorAll('.admin-only');
    adminSections.forEach(el => { el.style.display = 'none'; });
    return;
  }

  if (usernameEl) usernameEl.textContent = currentUser.full_name || currentUser.username;
  if (roleEl) roleEl.textContent = currentUser.role;
  if (initialEl) initialEl.textContent = currentUser.username ? currentUser.username.charAt(0).toUpperCase() : '?';
  if (btnLoginEl) btnLoginEl.style.display = 'none';
  if (btnChangeUserEl) btnChangeUserEl.style.display = 'flex';
  if (btnLogoutEl) btnLogoutEl.style.display = 'flex';

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

  const canProduccion = userPermissions && userPermissions['produccion'] && userPermissions['produccion'].can_view;
  const canConsumos = userPermissions && userPermissions['consumos'] && userPermissions['consumos'].can_view;

  // Configure Producción Button
  if (produccionBtn) {
    const lockBadge = produccionBtn.querySelector('.lock-badge');
    if (canProduccion) {
      produccionBtn.classList.remove('locked');
      if (lockBadge) lockBadge.style.display = 'none';
      produccionBtn.title = "Acceso a Módulo Producción";
    } else {
      produccionBtn.classList.add('locked');
      if (lockBadge) lockBadge.style.display = 'inline-block';
      produccionBtn.title = "Acceso Restringido para tu rol";
    }
  }

  // Configure Consumos Button
  if (consumosBtn) {
    const lockBadge = consumosBtn.querySelector('.lock-badge');
    if (canConsumos) {
      consumosBtn.classList.remove('locked');
      if (lockBadge) lockBadge.style.display = 'none';
      consumosBtn.title = "Acceso a Módulo Consumos";
    } else {
      consumosBtn.classList.add('locked');
      if (lockBadge) lockBadge.style.display = 'inline-block';
      consumosBtn.title = "Acceso Restringido para tu rol";
    }
  }
}

// Setup Navigation and UI Event Listeners
function setupEventListeners() {
  // Iniciar Sesión button handler
  const btnOpenLogin = document.getElementById('btn-open-login');
  if (btnOpenLogin) {
    btnOpenLogin.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginModal();
    });
  }

  // Cambiar Usuario button handler
  const btnChangeUser = document.getElementById('btn-change-user');
  if (btnChangeUser) {
    btnChangeUser.addEventListener('click', (e) => {
      e.preventDefault();
      showLoginModal();
    });
  }

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
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
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
          const errEl = document.getElementById('login-error');
          if (errEl) {
            errEl.textContent = errData.detail || 'Error de autenticación';
            errEl.style.display = 'block';
          }
        }
      } catch (err) {
        console.error('Login error:', err);
      }
    });
  }

  // Logout Button
  const btnLogout = document.getElementById('btn-logout');
  if (btnLogout) {
    btnLogout.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      setGuestState();
    });
  }

  // User Preset Selector in Login Modal
  const presetSelect = document.getElementById('preset-user-select');
  if (presetSelect) {
    presetSelect.addEventListener('change', (e) => {
      const role = e.target.value;
      if (!role) return;
      const usernameInput = document.getElementById('login-username');
      const passwordInput = document.getElementById('login-password');
      if (usernameInput) usernameInput.value = role;
      if (passwordInput) passwordInput.value = (role === 'Admin') ? 'admin1' : 'admin';
    });
  }

  // User Management Form Submit
  const formCreateUser = document.getElementById('form-create-user');
  if (formCreateUser) {
    formCreateUser.addEventListener('submit', async (e) => {
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
        formCreateUser.reset();
        loadUsersList();
      } else {
        const err = await res.json();
        alert('Error: ' + (err.detail || 'No se pudo crear el usuario'));
      }
    });
  }
}

// Switch View Sections (Manages Full Screen vs Sidebar Layout)
function switchView(viewName) {
  document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
  document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));

  const sidebarEl = document.querySelector('.sidebar');

  if (viewName === 'tunel_lavado' || viewName === 'historial_turnos' || viewName === 'calandra_2' || viewName === 'calandra_3') {
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
  } else if (viewName === 'tunel_lavado' || viewName === 'historial_turnos' || viewName === 'filtros_turno' || viewName === 'comparar_turnos' || viewName === 'calandra_2' || viewName === 'calandra_3') {
    const prodBtn = document.querySelector(`.menu-btn[data-view="produccion"]`);
    if (prodBtn) prodBtn.classList.add('active');
  }

  // Update browser location hash
  window.location.hash = `#${viewName}`;

  // Load section specific data
  if (viewName === 'produccion') loadProduccionData();
  if (viewName === 'tunel_lavado') loadTunelLavadoDashboard();
  if (viewName === 'calandra_2') loadCalandraDashboard('CALANDRA_2');
  if (viewName === 'calandra_3') loadCalandraDashboard('CALANDRA_3');
  if (viewName === 'historial_turnos') initHistorialTurnosScreen();
  if (viewName === 'filtros_turno') initFiltrosTurnoScreen();
  if (viewName === 'comparar_turnos') initCompararTurnosScreen();
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
          } else if (currentHash === 'calandra_2') {
            loadCalandraDashboard('CALANDRA_2');
          } else if (currentHash === 'calandra_3') {
            loadCalandraDashboard('CALANDRA_3');
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

// Auto-Refresh Controller (Refresca la vista activa cada 10 segundos para datos e indicadores en tiempo real)
let autoRefreshTimer = null;

function startAutoRefreshTimer() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => {
    const currentHash = window.location.hash.replace('#', '') || 'inicio';
    if (currentHash === 'tunel_lavado') {
      loadTunelLavadoDashboard();
    } else if (currentHash === 'calandra_2') {
      loadCalandraDashboard('CALANDRA_2');
    } else if (currentHash === 'calandra_3') {
      loadCalandraDashboard('CALANDRA_3');
    } else if (currentHash === 'produccion') {
      loadProduccionData();
    }
  }, 10000); // 10 segundos
}

// Modal Controllers
function showLoginModal() {
  const modal = document.getElementById('login-modal');
  if (modal) {
    modal.classList.add('active');
    modal.style.setProperty('display', 'flex', 'important');
    modal.style.setProperty('opacity', '1', 'important');
    modal.style.setProperty('visibility', 'visible', 'important');
    modal.style.setProperty('pointer-events', 'auto', 'important');
    modal.style.setProperty('z-index', '999999', 'important');
  }
  const errEl = document.getElementById('login-error');
  if (errEl) errEl.style.display = 'none';
}

function closeLoginModal() {
  const modal = document.getElementById('login-modal');
  if (modal) {
    modal.classList.remove('active');
    modal.style.setProperty('display', 'none', 'important');
    modal.style.setProperty('opacity', '0', 'important');
    modal.style.setProperty('visibility', 'hidden', 'important');
    modal.style.setProperty('pointer-events', 'none', 'important');
  }
}

window.showLoginModal = showLoginModal;
window.closeLoginModal = closeLoginModal;

window.calandraHourlyCharts = window.calandraHourlyCharts || {};

function renderCalandraHourlyChart(canvasId, cal, machineId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const g = cal.grafica_hora_a_hora;
  if (!g) return;

  const labels = g.labels || [];
  const prendasData = g.prendas || [];
  const valleData = g.tiempo_valle || [];
  const isCal2 = (machineId === 'CALANDRA_2');

  const datasets = [];

  // Línea de prendas producidas (Eje Y Izquierdo)
  datasets.push({
    type: 'line',
    label: isCal2 ? 'Prendas Totales' : 'Prendas Producidas',
    data: prendasData,
    borderColor: '#38bdf8',
    backgroundColor: 'rgba(56, 189, 248, 0.12)',
    borderWidth: 2.5,
    pointBackgroundColor: '#0284c7',
    pointBorderColor: '#38bdf8',
    pointRadius: 4,
    pointHoverRadius: 6,
    tension: 0.35,
    fill: false,
    yAxisID: 'yPrendas'
  });

  if (isCal2 && g.grandes && g.pequenas) {
    datasets.push({
      type: 'line',
      label: 'Prendas Grandes',
      data: g.grandes,
      borderColor: '#c084fc',
      borderWidth: 1.5,
      borderDash: [4, 4],
      pointBackgroundColor: '#9333ea',
      pointBorderColor: '#c084fc',
      pointRadius: 3,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });
    datasets.push({
      type: 'line',
      label: 'Prendas Pequeñas',
      data: g.pequenas,
      borderColor: '#60a5fa',
      borderWidth: 1.5,
      borderDash: [2, 2],
      pointBackgroundColor: '#2563eb',
      pointBorderColor: '#60a5fa',
      pointRadius: 3,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });
  }

  // Barras verticales de tiempo valle (Eje Y Derecho)
  datasets.push({
    type: 'bar',
    label: 'Tiempo Valle (min)',
    data: valleData,
    backgroundColor: 'rgba(245, 158, 11, 0.65)',
    borderColor: '#fbbf24',
    borderWidth: 1,
    borderRadius: 4,
    barPercentage: 0.45,
    yAxisID: 'yValle'
  });

  if (window.calandraHourlyCharts[machineId]) {
    try {
      window.calandraHourlyCharts[machineId].destroy();
    } catch (e) {
      console.warn("Error destruyendo gráfico anterior de calandra:", e);
    }
  }

  const ctx = canvas.getContext('2d');
  window.calandraHourlyCharts[machineId] = new Chart(ctx, {
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            boxWidth: 12,
            boxHeight: 10,
            color: '#94a3b8',
            font: { size: 10, family: 'Inter, system-ui, sans-serif' },
            padding: 8
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#f8fafc',
          bodyColor: '#e2e8f0',
          borderColor: 'rgba(255, 255, 255, 0.12)',
          borderWidth: 1,
          padding: 8,
          cornerRadius: 6,
          bodyFont: { size: 10.5 },
          titleFont: { size: 11, weight: 'bold' }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 9.5 } }
        },
        yPrendas: {
          type: 'linear',
          position: 'left',
          beginAtZero: true,
          title: {
            display: true,
            text: 'Prendas',
            color: '#38bdf8',
            font: { size: 10.5, weight: 'bold' }
          },
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: {
            color: '#38bdf8',
            font: { size: 9.5 },
            precision: 0
          }
        },
        yValle: {
          type: 'linear',
          position: 'right',
          min: 0,
          max: 60,
          title: {
            display: true,
            text: 'Tiempo Valle (min)',
            color: '#fbbf24',
            font: { size: 10.5, weight: 'bold' }
          },
          grid: { drawOnChartArea: false },
          ticks: {
            color: '#fbbf24',
            font: { size: 9.5 },
            callback: function(v) { return v + ' min'; }
          }
        }
      }
    }
  });
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
      let clickAttr = '';
      if (isClickable) {
        if (m.id === 'TUNEL_LAVADO') clickAttr = `onclick="switchView('tunel_lavado')"`;
        else if (m.id === 'CALANDRA_2') clickAttr = `onclick="switchView('calandra_2')"`;
        else if (m.id === 'CALANDRA_3') clickAttr = `onclick="switchView('calandra_3')"`;
        else if (m.dashboard_url) clickAttr = `onclick="switchView('${m.dashboard_url.replace('#', '')}')"`;
      }
      const cardClass = isClickable ? 'machine-card clickable-card' : 'machine-card';

      let statusBadgeClass = 'status-operativa';
      if (m.produccion_calandra) {
        if (!m.produccion_calandra.is_turno_activo) {
          statusBadgeClass = 'status-inactivo';
        } else if (m.produccion_calandra.en_valle) {
          statusBadgeClass = 'status-valle-alert';
        } else {
          statusBadgeClass = 'status-operativa';
        }
      }

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
            <div class="machine-status-badge ${statusBadgeClass}">
              <span class="status-dot"></span>
              ${m.estado}
            </div>
          </div>
      `;

      // Banner de Turno y Métricas
      if (m.turno_info) {
        html += `
          <div class="shift-banner">
            <span class="shift-title"><i class="fas fa-user-clock"></i> ${m.turno_info.nombre} (${m.turno_info.horario})</span>
            <span class="shift-time"><i class="fas fa-calendar-alt"></i> ${m.turno_info.fecha || ''}</span>
          </div>
        `;

        if (m.indicadores_turno) {
          html += `
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
                <span class="shift-indicator-label">Kgs Totales</span>
                <span class="shift-indicator-val">${m.indicadores_turno.kgs_totales || m.indicadores_turno.promedio_tiempo_carga}</span>
              </div>
              <div class="shift-indicator-box">
                <span class="shift-indicator-label">Cant. Cargas</span>
                <span class="shift-indicator-val">${m.indicadores_turno.cantidad_cargas}</span>
              </div>
            </div>
          `;
        } else if (m.produccion_calandra) {
          const cal = m.produccion_calandra;
          const isCal2 = (m.id === 'CALANDRA_2');

          html += `
            <div class="section-subtitle-bar">
              <h4><i class="fas fa-industry"></i> Indicadores de Producción - Turno Actual</h4>
              <div class="subtitle-line"></div>
            </div>

            <div class="calandra-kpi-grid">
              <!-- 1. Prendas Totales -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-tshirt" style="color: #38bdf8;"></i>
                  <span>Prendas Totales</span>
                </div>
                <div class="calandra-kpi-val">${cal.prendas_totales_str}</div>
                ${isCal2 && cal.desglose_calandra2 ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Prendas Grandes"><i class="fas fa-expand-alt"></i> ${cal.desglose_calandra2.prendas_grandes_str}</span>
                    <span class="cal-badge-p" title="Prendas Pequeñas"><i class="fas fa-compress-alt"></i> ${cal.desglose_calandra2.prendas_pequenas_str}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 2. Kgs Totales -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-weight-hanging" style="color: #34d399;"></i>
                  <span>Kgs Totales</span>
                </div>
                <div class="calandra-kpi-val" style="color: #34d399;">${cal.kgs_totales_str}</div>
                ${isCal2 && cal.desglose_calandra2 ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Kilos Grandes">${cal.desglose_calandra2.kg_grandes_str}</span>
                    <span class="cal-badge-p" title="Kilos Pequeñas">${cal.desglose_calandra2.kg_pequenas_str}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 3. Tiempo Valle -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-stopwatch" style="color: ${cal.en_valle ? '#f87171' : '#fbbf24'};"></i>
                  <span>Tiempo Valle</span>
                </div>
                <div class="calandra-kpi-val" style="color: ${cal.en_valle ? '#f87171' : '#fbbf24'};">${cal.tiempo_valle_str}</div>
                <div class="calandra-pill-row">
                  <span class="valle-pill ${cal.en_valle ? 'in-valle' : 'running'}">
                    ${cal.en_valle ? '⚠️ En Valle' : '⚡ Produciendo'}
                  </span>
                </div>
                ${isCal2 && cal.desglose_calandra2 ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Valle Grandes">${cal.desglose_calandra2.tiempo_valle_grandes_str} Gdes</span>
                    <span class="cal-badge-p" title="Valle Pequeñas">${cal.desglose_calandra2.tiempo_valle_pequenas_str} Peq</span>
                  </div>
                ` : ''}
              </div>

              <!-- 4. Prendas / Hora -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-tachometer-alt" style="color: #a78bfa;"></i>
                  <span>Prendas / Hora</span>
                </div>
                <div class="calandra-kpi-val" style="color: #a78bfa;">${cal.prendas_hora_str}</div>
                ${isCal2 && cal.desglose_calandra2 ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Ritmo Grandes">${cal.desglose_calandra2.prendas_grandes_hora_str}</span>
                    <span class="cal-badge-p" title="Ritmo Pequeñas">${cal.desglose_calandra2.prendas_pequenas_hora_str}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 5. Kg / Hora -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-balance-scale" style="color: #f43f5e;"></i>
                  <span>Kg / Hora</span>
                </div>
                <div class="calandra-kpi-val" style="color: #f43f5e;">${cal.kg_hora_str}</div>
                <div class="calandra-pill-row">
                  <span class="cal-badge-subtle">Ritmo horario</span>
                </div>
              </div>
            </div>
          `;
        }
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
              <span>${m.indicadores_turno?.ikprod_details ? 'Rendimiento ikProd / Eficiencia' : 'Rendimiento OEE / Disponibilidad'}</span>
              <span class="oee-value-tag" style="${m.indicadores_turno?.ikprod_details ? `color: ${m.indicadores_turno.ikprod_details.text_color}; border-color: ${m.indicadores_turno.ikprod_details.border_color};` : ''}">
                ${m.indicadores_turno?.ikprod_details ? `${m.indicadores_turno.ikprod_details.pct_str} ikProd` : `${m.oee}% OEE`}
              </span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${m.indicadores_turno?.ikprod_details ? Math.min(m.indicadores_turno.ikprod_details.pct, 100) : m.oee}%; ${m.indicadores_turno?.ikprod_details ? `background: ${m.indicadores_turno.ikprod_details.gradient};` : ''}"></div>
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

// Load Dashboard Ampliado para Calandra 2 o Calandra 3
async function loadCalandraDashboard(maquinaId) {
  const isCal2 = (maquinaId === 'CALANDRA_2');
  const containerId = isCal2 ? 'calandra-2-dashboard-content' : 'calandra-3-dashboard-content';
  const container = document.getElementById(containerId);
  if (!container) return;

  try {
    const res = await fetch(`/api/produccion/calandras/${maquinaId}/dashboard`);
    if (!res.ok) throw new Error(`Error ${res.status}: No se pudo cargar el dashboard de ${maquinaId}`);
    const data = await res.json();

    const ind = data.indicadores;
    const isShiftActive = data.is_turno_activo;
    const turno = data.turno_info;

    let html = `
      <!-- Banner de Turno -->
      <div class="shift-banner" style="margin-bottom: 20px;">
        <span class="shift-title"><i class="fas fa-user-clock"></i> ${turno.nombre} (${turno.horario})</span>
        <span class="shift-time"><i class="fas fa-calendar-alt"></i> ${turno.fecha || ''}</span>
      </div>
    `;

    if (!isShiftActive) {
      html += `
        <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(251, 191, 36, 0.4); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px; display: flex; align-items: center; gap: 14px; color: #fbbf24;">
          <i class="fas fa-info-circle" style="font-size: 1.5rem;"></i>
          <div>
            <strong style="font-size: 1rem;">Sin Turno Activo en Curso:</strong> En este momento la planta no tiene un turno de producción en proceso. Todos los indicadores y la gráfica se presentan en cero hasta que comience el siguiente turno programado.
          </div>
        </div>
      `;
    }

    html += `
      <!-- Tarjetas Principales de Producción (5 KPIs) -->
      <div class="dashboard-kpi-grid">
        <!-- 1. Prendas Totales -->
        <div class="kpi-card-striking kpi-card-cyan">
          <div class="kpi-card-header">
            <h4><i class="fas fa-tshirt"></i> Prendas Totales</h4>
            <div class="kpi-icon-circle"><i class="fas fa-layer-group"></i></div>
          </div>
          <div class="kpi-big-number">${ind.prendas_totales_str}</div>
          <div class="kpi-card-subtext">Acumulado del turno en curso</div>
          ${isCal2 && ind.desglose_calandra2 ? `
            <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start;">
              <span class="cal-badge-g"><i class="fas fa-expand-alt"></i> ${ind.desglose_calandra2.prendas_grandes_str}</span>
              <span class="cal-badge-p"><i class="fas fa-compress-alt"></i> ${ind.desglose_calandra2.prendas_pequenas_str}</span>
            </div>
          ` : ''}
        </div>

        <!-- 2. Kgs Totales -->
        <div class="kpi-card-striking kpi-card-green">
          <div class="kpi-card-header">
            <h4><i class="fas fa-weight-hanging"></i> Kgs Totales</h4>
            <div class="kpi-icon-circle"><i class="fas fa-balance-scale-right"></i></div>
          </div>
          <div class="kpi-big-number">${ind.kgs_totales_str}</div>
          <div class="kpi-card-subtext">Kilos procesados en el turno</div>
          ${isCal2 && ind.desglose_calandra2 ? `
            <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start;">
              <span class="cal-badge-g">${ind.desglose_calandra2.kg_grandes_str}</span>
              <span class="cal-badge-p">${ind.desglose_calandra2.kg_pequenas_str}</span>
            </div>
          ` : ''}
        </div>

        <!-- 3. Tiempo Valle -->
        <div class="kpi-card-striking ${ind.en_valle ? 'kpi-card-red' : 'kpi-card-amber'}">
          <div class="kpi-card-header">
            <h4><i class="fas fa-stopwatch"></i> Tiempo Valle</h4>
            <div class="kpi-icon-circle">
              <i class="fas ${ind.en_valle ? 'fa-exclamation-triangle' : 'fa-hourglass-half'}"></i>
            </div>
          </div>
          <div class="kpi-big-number">${ind.tiempo_valle_str}</div>
          <div class="kpi-card-subtext">
            <span class="valle-pill ${ind.en_valle ? 'in-valle' : 'running'}" style="margin-right: 6px;">
              ${isShiftActive ? (ind.en_valle ? '⚠️ En Valle' : '⚡ Produciendo') : 'Sin Turno'}
            </span>
            Minutos en espera/valle
          </div>
          ${isCal2 && ind.desglose_calandra2 ? `
            <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start;">
              <span class="cal-badge-g">${ind.desglose_calandra2.tiempo_valle_grandes_str} Gdes</span>
              <span class="cal-badge-p">${ind.desglose_calandra2.tiempo_valle_pequenas_str} Peq</span>
            </div>
          ` : ''}
        </div>

        <!-- 4. Prendas / Hora -->
        <div class="kpi-card-striking kpi-card-purple">
          <div class="kpi-card-header">
            <h4><i class="fas fa-tachometer-alt"></i> Prendas / Hora</h4>
            <div class="kpi-icon-circle"><i class="fas fa-bolt"></i></div>
          </div>
          <div class="kpi-big-number">${ind.prendas_hora_str}</div>
          <div class="kpi-card-subtext">Cadencia promedio horaria</div>
          ${isCal2 && ind.desglose_calandra2 ? `
            <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start;">
              <span class="cal-badge-g">${ind.desglose_calandra2.prendas_grandes_hora_str}</span>
              <span class="cal-badge-p">${ind.desglose_calandra2.prendas_pequenas_hora_str}</span>
            </div>
          ` : ''}
        </div>

        <!-- 5. Kg / Hora -->
        <div class="kpi-card-striking kpi-card-indigo">
          <div class="kpi-card-header">
            <h4><i class="fas fa-balance-scale"></i> Kg / Hora</h4>
            <div class="kpi-icon-circle"><i class="fas fa-chart-line"></i></div>
          </div>
          <div class="kpi-big-number">${ind.kg_hora_str}</div>
          <div class="kpi-card-subtext">Ritmo horario de kilogramos</div>
        </div>
      </div>

      <!-- Gráfica de Producción y Tiempo Valle Hora a Hora -->
      <div class="chart-card" style="margin-top: 24px; background: rgba(30, 41, 59, 0.7); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px;">
        <div class="chart-header-row" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
          <div class="chart-header-title">
            <h4 style="font-size: 1.15rem; color: #f8fafc; font-weight: 700; margin: 0;">
              <i class="fas fa-chart-line" style="color: #38bdf8; margin-right: 8px;"></i>
              Producción y Tiempo Valle Hora a Hora (Turno Actual)
            </h4>
          </div>
          <div style="font-size: 0.82rem; color: #94a3b8;">
            <span style="display:inline-block;width:12px;height:12px;background:#38bdf8;border-radius:3px;margin-right:4px;"></span>
            <strong style="color: #38bdf8;">Prendas</strong> (Eje Izquierdo)
            <span style="display:inline-block;width:12px;height:12px;background:#fbbf24;border-radius:3px;margin-left:14px;margin-right:4px;"></span>
            <strong style="color: #fbbf24;">Tiempo Valle min</strong> (Eje Derecho)
          </div>
        </div>
        <div style="position: relative; height: 350px; width: 100%;">
          <canvas id="chart-dashboard-${maquinaId.toLowerCase()}"></canvas>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // Renderizar gráfica dual axis
    renderCalandraHourlyChart(`chart-dashboard-${maquinaId.toLowerCase()}`, ind, maquinaId);
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

    const canvasExists = document.getElementById('chart-avance-turno');
    if (!canvasExists) {
      container.innerHTML = `
        <!-- Banner Sincronización de Turno -->
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; padding: 10px 16px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 36px; height: 36px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.1rem;">
              <i class="fas fa-user-clock"></i>
            </div>
            <div>
              <h4 id="dash-shift-header" style="color: var(--text-main); font-size: 0.95rem;">${data.turno_activo.nombre} (${data.turno_activo.horario}) — <span style="color: #38bdf8;">📅 ${data.turno_activo.fecha || ''}</span></h4>
              <small style="color: var(--text-muted); font-size: 0.72rem;">Sincronizado desde: ${data.sync_info.origen} | Frecuencia: ${data.sync_info.frecuencia_sync}</small>
            </div>
          </div>

          <div style="text-align: right;">
            <span style="font-size: 0.8rem; color: #34d399; font-weight: 700;">🟢 CONEXIÓN ACTIVADA</span>
            <div id="dash-cache-timestamp" style="font-size: 0.7rem; color: var(--text-muted);">Cache: ${data.sync_info.cache_actualizado}</div>
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
            <div id="dash-kpi-kg-totales" class="kpi-big-number">${kgInfo.valor}</div>
            <div id="dash-sub-kg-totales" class="kpi-card-subtext">${kgInfo.subtexto}</div>
          </div>

          <!-- Columna 1, Fila 2: ikProd (stacked verticalmente bajo Kg Totales) -->
          <div id="dash-card-ikprod" class="kpi-card-striking" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid ${ikprodBorderColor}; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
            <div class="kpi-card-header">
              <h4 style="color: #f8fafc;">${ikprodInfo.titulo}</h4>
              <div id="dash-icon-ikprod" class="kpi-icon-circle" style="background: rgba(255, 255, 255, 0.08); color: ${ikprodTextColor};"><i class="fas ${ikprodInfo.icono}"></i></div>
            </div>
            <div id="dash-kpi-ikprod" class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: ${ikprodTextColor}; text-shadow: 0 0 16px ${ikprodTextColor}60;">${ikprodInfo.valor}</div>
            <div id="dash-labels-ikprod" style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 2px; margin-bottom: 6px; flex-wrap: wrap;">
              <span id="dash-prom-carga-ikprod" style="font-size: 0.72rem; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.3);"><i class="fas fa-weight-hanging"></i> ${ikprodInfo.promedio_carga_str || 'Prom: 0.0 kg/carga'}</span>
              <span id="dash-prom-tiempo-ikprod" style="font-size: 0.72rem; font-weight: 600; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(251, 191, 36, 0.3);"><i class="fas fa-stopwatch"></i> ${ikprodInfo.promedio_tiempo_str || ikprodInfo.tprom_str || 'Tprom: 0 min'}</span>
            </div>
            <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 6px; margin-top: 2px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
              <span id="dash-tprom-ikprod" style="color: #38bdf8;"><i class="fas fa-clock"></i> ${ikprodInfo.tprom_str || ''}</span>
              <span id="dash-neto-ikprod">${ikprodInfo.neto_str}</span>
            </div>
            <div id="dash-sub-ikprod" style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
              <i class="fas fa-calculator"></i> ${ikprodInfo.subtexto}
            </div>
          </div>

          <!-- Columna 2, Fila 1: Cargas Totales Turno -->
          <div class="kpi-card-striking kpi-card-amber" style="grid-column: 2; grid-row: 1;">
            <div class="kpi-card-header">
              <h4>${cargasInfo.titulo}</h4>
              <div class="kpi-icon-circle"><i class="fas ${cargasInfo.icono}"></i></div>
            </div>
            <div id="dash-kpi-cargas-totales" class="kpi-big-number">${cargasInfo.valor}</div>
            <div id="dash-sub-cargas-totales" class="kpi-card-subtext">${cargasInfo.subtexto}</div>
          </div>

          <!-- Columna 3, Fila 1: Productividad hProd (kg/h) -->
          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 3; grid-row: 1; background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
            <div class="kpi-card-header">
              <h4>${hprodInfo.titulo}</h4>
              <div class="kpi-icon-circle"><i class="fas ${hprodInfo.icono}"></i></div>
            </div>
            <div id="dash-kpi-hprod" class="kpi-big-number">${hprodInfo.valor}</div>
            <div id="dash-sub-hprod" class="kpi-card-subtext">${hprodInfo.subtexto}</div>
          </div>

          <!-- Columna 4, Fila 1: Clientes y Programas (stacked verticalmente) -->
          <div class="col-secondary-kpis" style="grid-column: 4; grid-row: 1;">
            <div class="kpi-card-compact">
              <div class="kpi-compact-info">
                <h5>${clientesInfo.titulo}</h5>
                <div id="dash-kpi-clientes" class="kpi-compact-value">${clientesInfo.valor}</div>
                <div class="kpi-compact-sub">${clientesInfo.subtexto}</div>
              </div>
              <div class="kpi-compact-icon"><i class="fas ${clientesInfo.icono}"></i></div>
            </div>

            <div class="kpi-card-compact">
              <div class="kpi-compact-info">
                <h5>${programasInfo.titulo}</h5>
                <div id="dash-kpi-programas" class="kpi-compact-value">${programasInfo.valor}</div>
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
              <small style="color: var(--text-muted); font-weight: 600; font-size: 0.72rem;">Eje Y Izq 1: Kg/Hora (rosa magenta) | Eje Y Izq 2: Kg Acumulados (azul cían) | Eje Y Der: Cargas por hora (oro)</small>
            </div>
            <div class="chart-wrapper">
              <canvas id="chart-avance-turno"></canvas>
            </div>
          </div>
        </div>
      `;
    } else {
      // Actualizaciones in-place sin parpadear ni re-crear canvas
      const cacheEl = document.getElementById('dash-cache-timestamp');
      if (cacheEl) cacheEl.textContent = `Cache: ${data.sync_info.cache_actualizado}`;

      const shiftHeadEl = document.getElementById('dash-shift-header');
      if (shiftHeadEl) shiftHeadEl.innerHTML = `${data.turno_activo.nombre} (${data.turno_activo.horario}) — <span style="color: #38bdf8;">📅 ${data.turno_activo.fecha || ''}</span>`;

      const kgEl = document.getElementById('dash-kpi-kg-totales');
      if (kgEl) kgEl.textContent = kgInfo.valor;
      const subKgEl = document.getElementById('dash-sub-kg-totales');
      if (subKgEl) subKgEl.textContent = kgInfo.subtexto;

      const cargasEl = document.getElementById('dash-kpi-cargas-totales');
      if (cargasEl) cargasEl.textContent = cargasInfo.valor;
      const subCargasEl = document.getElementById('dash-sub-cargas-totales');
      if (subCargasEl) subCargasEl.textContent = cargasInfo.subtexto;

      const hprodEl = document.getElementById('dash-kpi-hprod');
      if (hprodEl) hprodEl.textContent = hprodInfo.valor;
      const subHprodEl = document.getElementById('dash-sub-hprod');
      if (subHprodEl) subHprodEl.textContent = hprodInfo.subtexto;

      const ikprodEl = document.getElementById('dash-kpi-ikprod');
      if (ikprodEl) {
        ikprodEl.textContent = ikprodInfo.valor;
        ikprodEl.style.color = ikprodTextColor;
        ikprodEl.style.textShadow = `0 0 16px ${ikprodTextColor}60`;
      }
      const promCargaEl = document.getElementById('dash-prom-carga-ikprod');
      if (promCargaEl) promCargaEl.innerHTML = `<i class="fas fa-weight-hanging"></i> ${ikprodInfo.promedio_carga_str || 'Prom: 0.0 kg/carga'}`;
      const promTiempoEl = document.getElementById('dash-prom-tiempo-ikprod');
      if (promTiempoEl) promTiempoEl.innerHTML = `<i class="fas fa-stopwatch"></i> ${ikprodInfo.promedio_tiempo_str || ikprodInfo.tprom_str || 'Tprom: 0 min'}`;
      const ikprodCard = document.getElementById('dash-card-ikprod');
      if (ikprodCard) ikprodCard.style.borderColor = ikprodBorderColor;
      const ikprodIcon = document.getElementById('dash-icon-ikprod');
      if (ikprodIcon) ikprodIcon.style.color = ikprodTextColor;
      const ikprodTprom = document.getElementById('dash-tprom-ikprod');
      if (ikprodTprom) ikprodTprom.innerHTML = `<i class="fas fa-clock"></i> ${ikprodInfo.tprom_str || ''}`;
      const ikprodNeto = document.getElementById('dash-neto-ikprod');
      if (ikprodNeto) ikprodNeto.textContent = ikprodInfo.neto_str;

      const clientesEl = document.getElementById('dash-kpi-clientes');
      if (clientesEl) clientesEl.textContent = clientesInfo.valor;

      const programasEl = document.getElementById('dash-kpi-programas');
      if (programasEl) programasEl.textContent = programasInfo.valor;
    }

    // Renderizar / Actualizar gráfica Chart.js
    renderAvanceChart(data.grafica_avance);

  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// Chart.js Manager for Shift Progress Chart
let avanceChartInstance = null;
let historialChartInstance = null;
let filtrosChartInstance = null;
let compararChartInstance = null;

function renderAvanceChart(graficaData, canvasId = 'chart-avance-turno') {
  if (!graficaData || !graficaData.labels) return;
  const canvasEl = document.getElementById(canvasId);
  if (!canvasEl) return;

  const isHistorial = (canvasId === 'chart-historial-turno');
  const isFiltros = (canvasId === 'chart-filtros-turno');
  const isComparar = (canvasId === 'chart-comparar-turno');
  let chartInst = isHistorial ? historialChartInstance : (isFiltros ? filtrosChartInstance : (isComparar ? compararChartInstance : avanceChartInstance));

  const rawLabels = [...graficaData.labels];
  const rawKgHora = [...(graficaData.kg_por_hora || [])];
  const rawCargasHora = [...(graficaData.cargas_por_hora || [])];
  const rawKgAcum = [...(graficaData.kg_acumulado || graficaData.kg_acumulado_por_hora || [])];

  // Normalización de etiquetas: Si vienen como horas sueltas ["06:00", "07:00", ..., "14:00"],
  // convertirlas a rangos de horas ["06:00 - 07:00", ...] y descartar la última etiqueta vacía de cierre.
  let formattedLabels = [];
  let formattedKgHora = rawKgHora;
  let formattedCargasHora = rawCargasHora;
  let formattedKgAcum = rawKgAcum;

  if (rawLabels.length > 0 && !rawLabels[0].includes(' - ')) {
    for (let i = 0; i < rawLabels.length - 1; i++) {
      formattedLabels.push(`${rawLabels[i]} - ${rawLabels[i+1]}`);
    }
    const numSlots = formattedLabels.length;
    formattedKgHora = rawKgHora.slice(0, numSlots);
    formattedCargasHora = rawCargasHora.slice(0, numSlots);
    formattedKgAcum = rawKgAcum.slice(0, numSlots);
  } else {
    formattedLabels = rawLabels;
  }

  // Actualización in-place en la misma instancia de gráfica (sin animación de cero y sin parpadeo)
  if (chartInst && chartInst.ctx && chartInst.ctx.canvas === canvasEl) {
    chartInst.data.labels = formattedLabels;
    chartInst.data.datasets[0].data = formattedKgAcum;
    chartInst.data.datasets[1].data = formattedKgHora;
    chartInst.data.datasets[2].data = formattedCargasHora;
    chartInst.update('none');
    return;
  }

  if (chartInst) {
    chartInst.destroy();
  }

  const ctx = canvasEl.getContext('2d');
  const newChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: formattedLabels,
      datasets: [
        {
          type: 'line',
          label: 'Kg Acumulados Turno (kg)',
          data: formattedKgAcum,
          borderColor: '#00f0ff',
          backgroundColor: 'rgba(0, 240, 255, 0.08)',
          borderWidth: 3.5,
          pointBackgroundColor: '#0284c7',
          pointBorderColor: '#00f0ff',
          pointRadius: 4,
          tension: 0.3,
          fill: false,
          yAxisID: 'yKgAcumulado'
        },
        {
          type: 'line',
          label: 'Kg de la Hora (kg)',
          data: formattedKgHora,
          borderColor: '#ff3b70',
          backgroundColor: 'rgba(255, 59, 112, 0.08)',
          borderWidth: 3.5,
          pointBackgroundColor: '#e11d48',
          pointBorderColor: '#ff3b70',
          pointRadius: 4,
          tension: 0.3,
          fill: false,
          yAxisID: 'yKgHora'
        },
        {
          type: 'bar',
          label: 'Cargas / Hora',
          data: formattedCargasHora,
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
        yKgHora: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Kg / Hora (kg)', color: '#ff3b70', font: { weight: 'bold', size: 10 } },
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#ff3b70', font: { weight: 'bold', size: 10 } },
          suggestedMin: 0
        },
        yKgAcumulado: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Kg Acumulados (kg)', color: '#00f0ff', font: { weight: 'bold', size: 10 } },
          grid: { drawOnChartArea: false },
          ticks: { color: '#00f0ff', font: { weight: 'bold', size: 10 } },
          suggestedMin: 0
        },
        yCargas: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'Cargas / Hora', color: '#fbbf24', font: { weight: 'bold', size: 10 } },
          grid: { drawOnChartArea: false },
          ticks: { color: '#fbbf24', font: { weight: 'bold', size: 10 }, stepSize: 1, precision: 0 },
          suggestedMin: 0
        }
      },
      plugins: {
        legend: {
          labels: { color: '#f8fafc', font: { weight: 'bold', size: 11 } }
        }
      }
    }
  });

  if (isHistorial) {
    historialChartInstance = newChart;
  } else if (isFiltros) {
    filtrosChartInstance = newChart;
  } else if (isComparar) {
    compararChartInstance = newChart;
  } else {
    avanceChartInstance = newChart;
  }
}

// Render process card with expandable telemetry panel
function renderProcesoCardAndPanel(id, varCode, titulo, unidad, iconClass, colorStyle, mainMetricValue, subtext) {
  const isElectric = (unidad === 'kWh');
  const tableHeaders = isElectric
    ? `<tr>
        <th>Timestamp ISO</th>
        <th>Conteos / Lecturas</th>
        <th>Energía (${unidad})</th>
        <th>Dispositivo / Fuente</th>
       </tr>`
    : `<tr>
        <th>Timestamp ISO</th>
        <th>Pulsos (Count)</th>
        <th>Volumen (${unidad})</th>
        <th>Caudal (m³/h)</th>
        <th>Dispositivo / Fuente</th>
       </tr>`;
  const initialColspan = isElectric ? 4 : 5;

  return `
    <div class="metric-card clickable-card" onclick="toggleProcesoPanel('${id}', '${varCode}', '${titulo.replace(/'/g, "\\'")}', '${unidad}')" style="cursor: pointer;" title="Haz clic para expandir o colapsar la telemetría">
      <div class="metric-icon ${colorStyle}"><i class="fas ${iconClass}"></i></div>
      <div class="metric-info" style="width: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h4>${titulo}</h4>
          <span id="badge-${id}" class="card-link-badge" style="font-size: 0.68rem; padding: 2px 6px;">🔍 Ver Telemetría</span>
        </div>
        <div class="metric-value">${mainMetricValue}</div>
        <small style="color: var(--text-muted)">${subtext}</small>
      </div>
    </div>

    <!-- Panel de Telemetría Incorporado (${titulo}) -->
    <div id="panel-telemetria-${id}" style="display: none; grid-column: 1 / -1; background: rgba(15, 23, 42, 0.75); border: 1px solid var(--border-color); border-radius: 14px; padding: 20px; margin-top: 10px; margin-bottom: 24px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 12px;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <div style="width: 36px; height: 36px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
            <i class="fas ${iconClass}"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 1.1rem; margin: 0;">Telemetría de ${titulo}</h4>
            <small style="color: var(--text-muted); font-size: 0.75rem;">Variable Monitor: <strong style="color: #38bdf8;">${varCode}</strong> | Unidad: <strong>${unidad}</strong></small>
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
            <input type="date" id="filter-fecha-inicio-${id}" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
          </div>
          <div>
            <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Hora Inicio:</label>
            <input type="time" id="filter-hora-inicio-${id}" value="00:00" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
          </div>
          <div>
            <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Fecha Fin:</label>
            <input type="date" id="filter-fecha-fin-${id}" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
          </div>
          <div>
            <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 4px;">Hora Fin:</label>
            <input type="time" id="filter-hora-fin-${id}" value="23:59" class="form-control" style="font-size: 0.85rem; padding: 6px 10px;">
          </div>
          <div>
            <button type="button" onclick="applyProcesoFilter('${id}', '${varCode}', '${unidad}')" class="btn-primary" style="padding: 8px 14px; font-size: 0.85rem;">🔍 Aplicar Filtro</button>
          </div>
        </div>
      </div>

      <!-- Tarjeta Acumulador Principal -->
      <div style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 60%, #0f172a 100%); border: 1px solid #38bdf8; border-radius: 14px; padding: 20px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(2, 132, 199, 0.3);">
        <div>
          <div style="font-size: 0.8rem; font-weight: 800; color: #e0f2fe; text-transform: uppercase; letter-spacing: 0.8px;">⚡ Acumulador Principal de Telemetría (${unidad})</div>
          <div id="acumulado-valor-${id}" style="font-size: 2.6rem; font-weight: 900; color: #ffffff; line-height: 1.1; margin: 6px 0;">0.00 ${unidad}</div>
          <div id="acumulado-subtexto-${id}" style="font-size: 0.78rem; color: #bae6fd; font-weight: 600;">Lecturas: 0 | Variable: ${varCode}</div>
        </div>
        <div style="width: 56px; height: 56px; border-radius: 50%; background: rgba(255, 255, 255, 0.18); display: flex; align-items: center; justify-content: center; font-size: 1.8rem; color: white;">
          <i class="fas fa-chart-line"></i>
        </div>
      </div>

      <!-- Tabla de Registros Entrantes -->
      <div style="font-size: 0.85rem; font-weight: 800; color: var(--text-main); margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
        <span>📋 Historial de Pulsos y Lecturas Entrantes</span>
        <span id="tabla-count-${id}" style="font-size: 0.75rem; color: var(--text-muted);">0 registros</span>
      </div>
      <div style="max-height: 220px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 10px; background: rgba(15, 23, 42, 0.6);">
        <table class="data-table" style="margin-top: 0; font-size: 0.82rem;">
          <thead>
            ${tableHeaders}
          </thead>
          <tbody id="table-body-${id}">
            <tr><td colspan="${initialColspan}" style="text-align: center; color: var(--text-muted);">Haz clic en Aplicar Filtro para consultar...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// Load Consumos Data with Expandable Telemetry Panels for all 14 Cards
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
        ${renderProcesoCardAndPanel(
          'agua_general',
          'AGUA_GENERAL',
          g.agua_general?.titulo || 'Agua (General)',
          'm³',
          'fa-water',
          'blue',
          `${g.agua_general?.caudal_m3h || 18.5} m³/h`,
          `Hoy: ${g.agua_general?.consumo_hoy_m3 || 210.4} m³ | Reciclaje: ${g.agua_general?.reciclaje_pct || 42}%`
        )}

        ${renderProcesoCardAndPanel(
          'gas_general',
          'sensor_gas_general',
          g.gas_general?.titulo || 'Gas General',
          'm³',
          'fa-fire',
          'amber',
          `${g.gas_general?.consumo_hoy_m3 || 1540} m³`,
          `Presión: ${g.gas_general?.presion_vapor_bar || 9.2} bar | Caldera: ${g.gas_general?.eficiencia_caldera_pct || 92.4}% ef`
        )}

        ${renderProcesoCardAndPanel(
          'energia_electrica',
          'I_gneral',
          g.energia_electrica?.titulo || 'Energía Eléctrica General',
          'kWh',
          'fa-bolt',
          'amber',
          `${g.energia_electrica?.potencia_activa_kw || 345.2} kW`,
          `Hoy: ${g.energia_electrica?.consumo_hoy_kwh || 4120} kWh | FP: ${g.energia_electrica?.factor_potencia || 0.96}`
        )}
      </div>

      <!-- Sección 2: Desglose de Agua por Proceso -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>💧 Consumos de Agua por Proceso</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid" style="margin-bottom: 28px;">
        ${renderProcesoCardAndPanel(
          'agua_tunel_lavadoras',
          'AGUA_TUNEL_LAVADORAS',
          agua.agua_tunel_lavadoras?.titulo || 'Agua Túnel y Lavadoras',
          'm³',
          'fa-shower',
          'blue',
          `${agua.agua_tunel_lavadoras?.caudal_m3h || 14.2} m³/h`,
          `Esp: ${agua.agua_tunel_lavadoras?.consumo_especifico_l_kg || 4.8} L/kg | Hoy: ${agua.agua_tunel_lavadoras?.consumo_hoy_m3 || 168.5} m³`
        )}
      </div>

      <!-- Sección 3: Desglose de Gas por Proceso / Máquina -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>🔥 Consumos de Gas por Proceso / Máquina</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid" style="margin-bottom: 28px;">
        ${renderProcesoCardAndPanel(
          'gas_tunel_vt',
          'Túnel de Secado VT',
          gas.gas_tunel_vt?.titulo || 'Gas Túnel VT',
          'm³',
          'fa-wind',
          'amber',
          `${gas.gas_tunel_vt?.consumo_m3h || 32.5} m³/h`,
          `Hoy: ${gas.gas_tunel_vt?.consumo_hoy_m3 || 260} m³ | Temp Secado: ${gas.gas_tunel_vt?.temp_secado_c || 118}°C`
        )}

        ${renderProcesoCardAndPanel(
          'gas_calandra_1',
          'calandra1_IoT',
          gas.gas_calandra_1?.titulo || 'Gas Calandra 1',
          'm³',
          'fa-scroll',
          'amber',
          `${gas.gas_calandra_1?.consumo_m3h || 45.0} m³/h`,
          `Hoy: ${gas.gas_calandra_1?.consumo_hoy_m3 || 360} m³ | Temp Rodillo: ${gas.gas_calandra_1?.temp_trabajo_c || 175}°C`
        )}

        ${renderProcesoCardAndPanel(
          'gas_calandra_2',
          'Calandra 2',
          gas.gas_calandra_2?.titulo || 'Gas Calandra 2',
          'm³',
          'fa-scroll',
          'amber',
          `${gas.gas_calandra_2?.consumo_m3h || 42.8} m³/h`,
          `Hoy: ${gas.gas_calandra_2?.consumo_hoy_m3 || 342.4} m³ | Temp Rodillo: ${gas.gas_calandra_2?.temp_trabajo_c || 175}°C`
        )}

        ${renderProcesoCardAndPanel(
          'gas_calandra_3',
          'Calandra 3',
          gas.gas_calandra_3?.titulo || 'Gas Calandra 3',
          'm³',
          'fa-eye',
          'amber',
          `${gas.gas_calandra_3?.consumo_m3h || 48.2} m³/h`,
          `Hoy: ${gas.gas_calandra_3?.consumo_hoy_m3 || 385.6} m³ | Temp Rodillo: ${gas.gas_calandra_3?.temp_trabajo_c || 180}°C`
        )}

        ${renderProcesoCardAndPanel(
          'gas_caldera_1',
          'caldera1',
          gas.gas_caldera_1?.titulo || 'Gas Caldera 1',
          'm³',
          'fa-fire-burner',
          'amber',
          `${gas.gas_caldera_1?.consumo_m3h || 52.4} m³/h`,
          `Hoy: ${gas.gas_caldera_1?.consumo_hoy_m3 || 419.2} m³ | Temp Trabajo: ${gas.gas_caldera_1?.temp_trabajo_c || 185}°C`
        )}

        ${renderProcesoCardAndPanel(
          'gas_caldera_2',
          'caldera2',
          gas.gas_caldera_2?.titulo || 'Gas Caldera 2',
          'm³',
          'fa-fire-burner',
          'amber',
          `${gas.gas_caldera_2?.consumo_m3h || 48.6} m³/h`,
          `Hoy: ${gas.gas_caldera_2?.consumo_hoy_m3 || 388.8} m³ | Temp Trabajo: ${gas.gas_caldera_2?.temp_trabajo_c || 182}°C`
        )}
      </div>

      <!-- Sección 4: Desglose de Electricidad por Proceso / Máquina -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>⚡ Consumos de Electricidad por Proceso / Máquina</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid">
        ${renderProcesoCardAndPanel(
          'elec_tunel',
          'I_motor_tunel',
          elec.elec_tunel?.titulo || 'Electricidad Túnel',
          'kWh',
          'fa-circle-notch',
          'amber',
          `${elec.elec_tunel?.potencia_kw || 85.4} kW`,
          `Hoy: ${elec.elec_tunel?.consumo_hoy_kwh || 1024.8} kWh`
        )}

        ${renderProcesoCardAndPanel(
          'elec_calandra_1',
          'I_bomba_calandra1',
          elec.elec_calandra_1?.titulo || 'Electricidad Calandra 1',
          'kWh',
          'fa-scroll',
          'amber',
          `${elec.elec_calandra_1?.potencia_kw || 42.1} kW`,
          `Hoy: ${elec.elec_calandra_1?.consumo_hoy_kwh || 505.2} kWh`
        )}

        ${renderProcesoCardAndPanel(
          'elec_calandra_2',
          'Bomba_calandra2',
          elec.elec_calandra_2?.titulo || 'Electricidad Calandra 2',
          'kWh',
          'fa-scroll',
          'amber',
          `${elec.elec_calandra_2?.potencia_kw || 39.8} kW`,
          `Hoy: ${elec.elec_calandra_2?.consumo_hoy_kwh || 477.6} kWh`
        )}

        ${renderProcesoCardAndPanel(
          'elec_calandra_3',
          'I_bomba_calandra3',
          elec.elec_calandra_3?.titulo || 'Electricidad Calandra 3',
          'kWh',
          'fa-eye',
          'amber',
          `${elec.elec_calandra_3?.potencia_kw || 46.5} kW`,
          `Hoy: ${elec.elec_calandra_3?.consumo_hoy_kwh || 558.0} kWh`
        )}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// Handler functions for expandable process panels
function toggleProcesoPanel(id, varCode, titulo, unidad) {
  const panel = document.getElementById(`panel-telemetria-${id}`);
  const badge = document.getElementById(`badge-${id}`);
  if (!panel) return;

  const isHidden = panel.style.display === 'none' || panel.style.display === '';
  if (isHidden) {
    panel.style.display = 'block';
    if (badge) badge.innerHTML = '🔼 Ocultar Telemetría';

    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const todayStr = today.toISOString().split('T')[0];
    const yesterdayStr = yesterday.toISOString().split('T')[0];

    const fechaInicioInput = document.getElementById(`filter-fecha-inicio-${id}`);
    const fechaFinInput = document.getElementById(`filter-fecha-fin-${id}`);
    if (fechaInicioInput && !fechaInicioInput.value) fechaInicioInput.value = yesterdayStr;
    if (fechaFinInput && !fechaFinInput.value) fechaFinInput.value = todayStr;

    fetchProcesoTelemetria(id, varCode, unidad);
  } else {
    panel.style.display = 'none';
    if (badge) badge.innerHTML = '🔍 Ver Telemetría';
  }
}

function applyProcesoFilter(id, varCode, unidad) {
  fetchProcesoTelemetria(id, varCode, unidad);
}

async function fetchProcesoTelemetria(id, varCode, unidad) {
  const fechaInicio = document.getElementById(`filter-fecha-inicio-${id}`)?.value || '';
  const horaInicio = document.getElementById(`filter-hora-inicio-${id}`)?.value || '00:00';
  const fechaFin = document.getElementById(`filter-fecha-fin-${id}`)?.value || '';
  const horaFin = document.getElementById(`filter-hora-fin-${id}`)?.value || '23:59';

  const tbody = document.getElementById(`table-body-${id}`);
  const valorAccEl = document.getElementById(`acumulado-valor-${id}`);
  const subtextAccEl = document.getElementById(`acumulado-subtexto-${id}`);
  const countEl = document.getElementById(`tabla-count-${id}`);

  const isElectric = (unidad === 'kWh');
  const colspanNum = isElectric ? 4 : 5;

  if (tbody) tbody.innerHTML = `<tr><td colspan="${colspanNum}" style="text-align: center; color: var(--text-muted);">Cargando telemetría...</td></tr>`;

  try {
    const params = new URLSearchParams({
      variable: varCode,
      fecha_inicio: fechaInicio,
      hora_inicio: horaInicio.length === 5 ? `${horaInicio}:00` : horaInicio,
      fecha_fin: fechaFin,
      hora_fin: horaFin.length === 5 ? `${horaFin}:59` : horaFin
    });

    const res = await fetch(`/api/consumos/telemetria?${params.toString()}`);
    if (!res.ok) throw new Error('Error consultando telemetría de proceso');
    const data = await res.json();

    const unitStr = data.unidad || unidad || 'm³';
    if (valorAccEl) valorAccEl.textContent = `${data.acumulado} ${unitStr}`;
    if (subtextAccEl) subtextAccEl.textContent = `Total Lecturas: ${data.total_pulsos.toLocaleString()} | Variable: ${varCode} | Rango: ${data.filtro.start_iso} ➔ ${data.filtro.end_iso}`;
    if (countEl) countEl.textContent = `${data.total_registros} registros`;

    if (tbody) {
      if (data.registros.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colspanNum}" style="text-align: center; color: var(--text-muted); padding: 15px;">No se encontraron lecturas para ${varCode} en el rango seleccionado.</td></tr>`;
      } else {
        tbody.innerHTML = data.registros.map(r => `
          <tr>
            <td><strong style="color: #38bdf8;">${r.timestamp_iso}</strong></td>
            <td><span style="color: #fbbf24; font-weight: 700;">${r.pulsos} ${isElectric ? 'lecturas' : 'pulsos'}</span></td>
            <td><span style="color: #34d399; font-weight: 800;">${r.valor} ${r.unidad}</span></td>
            ${isElectric ? '' : `<td>${r.caudal_m3h} m³/h</td>`}
            <td><small style="color: var(--text-muted);">${r.dispositivo}</small></td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="${colspanNum}" style="color: var(--accent-red); text-align: center;">⚠️ ${err.message}</td></tr>`;
  }
}

// Backward compatibility wrappers for Agua Túnel
function toggleAguaTunelPanel() {
  toggleProcesoPanel('agua_tunel_lavadoras', 'AGUA_TUNEL_LAVADORAS', 'Agua Túnel y Lavadoras', 'm³');
}

function openAguaTunelModal() {
  toggleAguaTunelPanel();
}

function closeAguaTunelModal() {
  const panel = document.getElementById('panel-telemetria-agua_tunel_lavadoras');
  if (panel) panel.style.display = 'none';
}

function applyAguaTunelFilter() {
  applyProcesoFilter('agua_tunel_lavadoras', 'AGUA_TUNEL_LAVADORAS', 'm³');
}

function fetchAguaTunelData() {
  fetchProcesoTelemetria('agua_tunel_lavadoras', 'AGUA_TUNEL_LAVADORAS', 'm³');
}

// ==========================================
// ==========================================
// SECCIÓN: HISTORIAL DE TURNOS
// ==========================================
let chartHistorialTurno = null;

function getLocalJornadaDate() {
  const now = new Date();
  if (now.getHours() < 5) {
    now.setDate(now.getDate() - 1);
  }
  return now.toLocaleDateString('sv-SE'); // Formato YYYY-MM-DD
}

async function initHistorialTurnosScreen() {
  const fechaPicker = document.getElementById('historial-fecha-picker');
  const turnoSelect = document.getElementById('historial-turno-select');

  if (!fechaPicker || !turnoSelect) return;

  const currentJornada = getLocalJornadaDate();
  fechaPicker.max = currentJornada;

  // Registrar listeners de eventos una sola vez
  if (!fechaPicker.dataset.eventsAttached) {
    fechaPicker.dataset.eventsAttached = 'true';

    // Event Listener al cambiar fecha
    fechaPicker.addEventListener('change', async (e) => {
      const val = e.target.value;
      if (val) {
        await loadShiftsForHistorialDate(val);
      } else {
        turnoSelect.innerHTML = '<option value="">-- Seleccionar Turno --</option>';
        turnoSelect.disabled = true;
        resetHistorialView();
      }
    });

    // Event Listener al seleccionar turno
    turnoSelect.addEventListener('change', async (e) => {
      const shiftKey = e.target.value;
      if (shiftKey) {
        await loadReconstructedShiftDashboard(shiftKey);
      } else {
        resetHistorialView();
      }
    });
  }

  // Al ingresar a la pantalla de Historial, consultar la jornada y cargar turnos inmediatamente
  try {
    const res = await fetch('/api/produccion/turnos/fechas-disponibles');
    let targetFecha = currentJornada;
    if (res.ok) {
      const data = await res.json();
      if (data.hoy) targetFecha = data.hoy;
    }

    if (!fechaPicker.value || fechaPicker.value > targetFecha) {
      fechaPicker.value = targetFecha;
    }

    // Cargar SIEMPRE los turnos disponibles para la jornada en curso o seleccionada
    await loadShiftsForHistorialDate(fechaPicker.value);
  } catch (e) {
    console.error('Error inicializando pantalla de Historial:', e);
    if (!fechaPicker.value) {
      fechaPicker.value = currentJornada;
    }
    await loadShiftsForHistorialDate(fechaPicker.value);
  }
}

function resetHistorialView() {
  const placeholder = document.getElementById('historial-placeholder');
  const dashboardContainer = document.getElementById('historial-dashboard-container');
  if (placeholder) placeholder.style.display = 'block';
  if (dashboardContainer) {
    dashboardContainer.style.display = 'none';
    dashboardContainer.innerHTML = '';
  }
  if (chartHistorialTurno) {
    chartHistorialTurno.destroy();
    chartHistorialTurno = null;
  }
}

async function loadShiftsForHistorialDate(fechaStr) {
  const turnoSelect = document.getElementById('historial-turno-select');
  if (!turnoSelect) return;

  try {
    turnoSelect.innerHTML = '<option value="">Cargando turnos...</option>';
    turnoSelect.disabled = true;

    const res = await fetch(`/api/produccion/turnos/por-fecha/${fechaStr}`);
    if (!res.ok) throw new Error('Error al obtener turnos de la fecha');
    const data = await res.json();

    turnoSelect.innerHTML = '<option value="">-- Seleccionar Turno --</option>';

    if (data.turnos && data.turnos.length > 0) {
      data.turnos.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.shift_key;
        const totalKgStr = typeof t.total_kg === 'number' ? Math.round(t.total_kg).toLocaleString('es-ES') : t.total_kg;
        const estadoTag = t.is_in_progress ? ' [En proceso]' : '';
        opt.textContent = `${t.nombre_turno} (${t.horario}) — ${totalKgStr} kg${estadoTag}`;
        if (t.is_in_progress) {
          opt.dataset.inProgress = 'true';
        }
        turnoSelect.appendChild(opt);
      });
      turnoSelect.disabled = false;
    } else {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Sin turnos procesados en esta jornada';
      turnoSelect.appendChild(opt);
      turnoSelect.disabled = true;
    }

    resetHistorialView();
  } catch (err) {
    console.error('Error cargando turnos por fecha:', err);
    turnoSelect.innerHTML = '<option value="">Error cargando turnos</option>';
    turnoSelect.disabled = true;
    resetHistorialView();
  }
}

async function loadReconstructedShiftDashboard(shiftKey) {
  const placeholder = document.getElementById('historial-placeholder');
  const dashboardContainer = document.getElementById('historial-dashboard-container');
  if (!dashboardContainer) return;

  try {
    dashboardContainer.style.display = 'block';
    dashboardContainer.innerHTML = '<p style="color: var(--text-muted); padding: 20px;">Cargando dashboard del turno...</p>';

    const res = await fetch(`/api/produccion/turnos/historial-json/${shiftKey}`);
    if (!res.ok) throw new Error('No se pudo cargar el paquete JSON del turno');
    const pkg = await res.json();

    if (placeholder) placeholder.style.display = 'none';

    // Formatear datos para el layout del dashboard
    const meta = pkg.meta_info || {};
    const ind = pkg.indicadores_ampliados || {};
    const tot = pkg.totales_promedios || {};
    const desglose = pkg.desglose_horario || {};

    const kgInfo = {
      titulo: 'Kg Totales Turno',
      valor: ind.kg_totales_turno?.valor_str || '0 kg',
      subtexto: `Objetivo Turno: ${(tot.objetivo_turno_kg || 0).toLocaleString('es-ES')} kg (${meta.es_datos_reales ? 'Real MQTT' : 'Simulado'})`,
      icono: 'fa-balance-scale'
    };

    const cargasInfo = {
      titulo: 'Cargas Totales Turno',
      valor: ind.cargas_totales_turno?.valor_str || '0 cargas',
      subtexto: `Promedio: ${tot.promedio_peso_carga_kg || 0} kg/carga`,
      icono: 'fa-boxes'
    };

    const hprodInfo = {
      titulo: 'Productividad (hProd)',
      valor: ind.productividad_hprod?.valor_str || '0 kg/h',
      subtexto: `Tiempo prom: ${tot.promedio_tiempo_entre_cargas_min || 0} min (${tot.promedio_tiempo_entre_cargas_seg || 0}s)`,
      icono: 'fa-tachometer-alt'
    };

    const ikprodInfo = ind.indice_eficiencia_ikprod || {
      pct_str: '0.0%',
      neto_str: 'ikProd Neto: 0.00',
      color_codigo: 'red',
      tprom_str: 'Tprom: 0 min',
      subtexto: 'Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%'
    };

    const clientesInfo = {
      titulo: 'Clientes Atendidos',
      valor: ind.clientes_unicos?.valor_str || '0 clientes',
      subtexto: 'Códigos únicos de cliente en turno',
      icono: 'fa-users'
    };

    const programasInfo = {
      titulo: 'Programas Ejecutados',
      valor: ind.programas_unicos?.valor_str || '0 programas',
      subtexto: 'Categorías/Programas únicos en turno',
      icono: 'fa-layer-group'
    };

    let ikprodTextColor = ikprodInfo.text_color || (ikprodInfo.color_codigo === 'red' ? '#ef4444' : ikprodInfo.color_codigo === 'orange' ? '#f97316' : '#34d399');
    let ikprodBorderColor = ikprodInfo.border_color || (ikprodInfo.color_codigo === 'red' ? '#ef4444' : ikprodInfo.color_codigo === 'orange' ? '#f97316' : '#10b981');

    dashboardContainer.innerHTML = `
      <!-- Banner Sincronización del Turno -->
      <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; padding: 12px 18px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 38px; height: 38px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
            <i class="fas fa-history"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 1rem;">${meta.nombre_turno || 'Turno'} (${meta.hora_inicio || ''} - ${meta.hora_fin || ''}) — <span style="color: #38bdf8;">📅 ${meta.fecha_formateada || meta.fecha}</span></h4>
            <small style="color: var(--text-muted); font-size: 0.78rem;">Origen: Persistencia SQLite (Clave: ${pkg.shift_key}) | Guardado el: ${meta.timestamp_actualizacion || ''}</small>
          </div>
        </div>

        <div style="text-align: right;">
          ${meta.is_in_progress ?
            `<span style="font-size: 0.82rem; color: #34d399; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.4);"><i class="fas fa-spinner fa-spin" style="margin-right: 5px;"></i> TURNO EN PROCESO</span>` :
            `<span style="font-size: 0.82rem; color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.4);">📜 HISTORIAL DE TURNO</span>`
          }
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

        <!-- Columna 1, Fila 2: ikProd (stacked verticalmente) -->
        <div class="kpi-card-striking" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid ${ikprodBorderColor}; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
          <div class="kpi-card-header">
            <h4 style="color: #f8fafc;">ÍNDICE DE EFICIENCIA (IKPROD)</h4>
            <div class="kpi-icon-circle" style="background: rgba(255, 255, 255, 0.08); color: ${ikprodTextColor};"><i class="fas fa-chart-line"></i></div>
          </div>
          <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: ${ikprodTextColor}; text-shadow: 0 0 16px ${ikprodTextColor}60;">${ikprodInfo.pct_str}</div>
          <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 2px; margin-bottom: 6px; flex-wrap: wrap;">
            <span style="font-size: 0.72rem; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.3);"><i class="fas fa-weight-hanging"></i> Prom: ${tot.promedio_peso_carga_kg || 0} kg/carga</span>
            <span style="font-size: 0.72rem; font-weight: 600; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(251, 191, 36, 0.3);"><i class="fas fa-stopwatch"></i> ${ikprodInfo.tprom_str || 'Tprom: 0 min'}</span>
          </div>
          <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 6px; margin-top: 2px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
            <span style="color: #38bdf8;"><i class="fas fa-clock"></i> ${ikprodInfo.tprom_str || ''}</span>
            <span>${ikprodInfo.neto_str}</span>
          </div>
          <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
            <i class="fas fa-calculator"></i> ${ikprodInfo.formula || 'Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%'}
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

        <!-- Columna 3, Fila 1: Productividad hProd -->
        <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 3; grid-row: 1; background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
          <div class="kpi-card-header">
            <h4>${hprodInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${hprodInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${hprodInfo.valor}</div>
          <div class="kpi-card-subtext">${hprodInfo.subtexto}</div>
        </div>

        <!-- Columna 4, Fila 1: Clientes y Programas -->
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
            <div style="font-size: 0.72rem; color: #94a3b8;">Eje Y Izq 1: Kg/Hora (rosa) | Eje Y Izq 2: Kg Acum (cian) | Eje Y Der: Cargas (oro)</div>
          </div>
          <div class="chart-wrapper">
            <canvas id="chart-historial-turno"></canvas>
          </div>
        </div>
      </div>
    `;

    // Renderizar gráfico exacto con renderAvanceChart
    const graficaData = {
      labels: desglose.labels || [],
      kg_por_hora: desglose.kg_por_hora || [],
      cargas_por_hora: desglose.cargas_por_hora || [],
      kg_acumulado: desglose.kg_acumulado_por_hora || desglose.kg_acumulado || []
    };
    renderAvanceChart(graficaData, 'chart-historial-turno');
  } catch (err) {
    console.error('Error cargando turno reconstruido:', err);
    dashboardContainer.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// ==========================================
// PANTALLA: FILTRADO POR RANGO HORARIO (TURNO ACTUAL)
// ==========================================
// ==========================================
// PANTALLA: FILTROS Y TOTALES POR PERÍODO
// ==========================================
function initFiltrosTurnoScreen() {
  const placeholderSelect = document.getElementById('filtros-placeholder-select');
  const dashboardContainer = document.getElementById('filtros-dashboard-container');
  const desdeFechaInput = document.getElementById('filtros-fecha-desde');
  const hastaFechaInput = document.getElementById('filtros-fecha-hasta');
  const desdeHoraInput = document.getElementById('filtros-hora-desde');
  const hastaHoraInput = document.getElementById('filtros-hora-hasta');

  if (placeholderSelect) placeholderSelect.style.display = 'block';
  if (dashboardContainer) {
    dashboardContainer.style.display = 'none';
    dashboardContainer.innerHTML = '';
  }

  // Pre-llenar fechas si están vacías: últimos 7 días hasta hoy
  const today = new Date();
  const pastWeek = new Date();
  pastWeek.setDate(today.getDate() - 7);

  const fmtDate = (d) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  if (desdeFechaInput && !desdeFechaInput.value) {
    desdeFechaInput.value = fmtDate(pastWeek);
  }
  if (hastaFechaInput && !hastaFechaInput.value) {
    hastaFechaInput.value = fmtDate(today);
  }
  if (desdeHoraInput && !desdeHoraInput.value) {
    desdeHoraInput.value = '06:00';
  }
  if (hastaHoraInput && !hastaHoraInput.value) {
    hastaHoraInput.value = '22:00';
  }
}

async function applyFiltroPeriodo() {
  const desdeFechaInput = document.getElementById('filtros-fecha-desde');
  const hastaFechaInput = document.getElementById('filtros-fecha-hasta');
  const desdeHoraInput = document.getElementById('filtros-hora-desde');
  const hastaHoraInput = document.getElementById('filtros-hora-hasta');
  const placeholderSelect = document.getElementById('filtros-placeholder-select');
  const dashboardContainer = document.getElementById('filtros-dashboard-container');

  const fechaDesde = desdeFechaInput ? desdeFechaInput.value : '';
  const horaDesde = desdeHoraInput ? desdeHoraInput.value : '06:00';
  const fechaHasta = hastaFechaInput ? hastaFechaInput.value : '';
  const horaHasta = hastaHoraInput ? hastaHoraInput.value : '22:00';

  if (!fechaDesde || !fechaHasta) {
    alert('Por favor selecciona las fechas "Desde" y "Hasta".');
    return;
  }

  try {
    dashboardContainer.style.display = 'block';
    dashboardContainer.innerHTML = `
      <div style="text-align: center; padding: 60px 20px; color: var(--text-muted);">
        <i class="fas fa-spinner fa-spin" style="font-size: 2.5rem; color: #818cf8; margin-bottom: 16px;"></i>
        <h4 style="color: #f8fafc; font-size: 1.15rem;">Calculando totales del período...</h4>
        <p style="font-size: 0.88rem; margin-top: 6px;">Concatenando turnos de producción en la ventana seleccionada</p>
      </div>
    `;
    if (placeholderSelect) placeholderSelect.style.display = 'none';

    const url = `/api/produccion/turnos/totales-periodo?fecha_inicio=${encodeURIComponent(fechaDesde)}&hora_inicio=${encodeURIComponent(horaDesde)}&fecha_fin=${encodeURIComponent(fechaHasta)}&hora_fin=${encodeURIComponent(horaHasta)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error al calcular totales del período');
    }
    const data = await res.json();

    if (!data.totales || data.totales.total_turnos === 0) {
      dashboardContainer.innerHTML = `
        <div style="text-align: center; padding: 60px 20px; background: rgba(15, 23, 42, 0.7); border-radius: 14px; border: 1px dashed rgba(239, 68, 68, 0.4);">
          <i class="fas fa-info-circle" style="font-size: 3rem; color: #ef4444; opacity: 0.8; margin-bottom: 16px;"></i>
          <h4 style="color: #f8fafc; font-size: 1.3rem;">No se encontraron turnos en este período</h4>
          <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 8px;">No hay turnos registrados entre el ${data.ventana_solicitada.inicio_formateado} y el ${data.ventana_solicitada.fin_formateado}. Prueba ampliando el rango de fechas u horarios.</p>
        </div>
      `;
      return;
    }

    const t = data.totales;
    const v = data.ventana_solicitada;

    // Renderizar Dashboard de Tarjetas de Totales
    dashboardContainer.innerHTML = `
      <!-- Banner Superior Informativo -->
      <div style="background: rgba(15, 23, 42, 0.9); border: 1.5px solid #818cf8; padding: 14px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <div style="width: 44px; height: 44px; border-radius: 10px; background: rgba(99, 102, 241, 0.2); color: #818cf8; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
            <i class="fas fa-calendar-check"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 1.1rem; margin: 0;">Totales Consolidados del Período</h4>
            <div style="color: #38bdf8; font-size: 0.86rem; font-weight: 600; margin-top: 3px;">
              <i class="fas fa-clock"></i> ${v.inicio_formateado} &nbsp;➔&nbsp; ${v.fin_formateado}
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
          <span style="font-size: 0.82rem; color: #34d399; font-weight: 700; background: rgba(52, 211, 153, 0.15); padding: 5px 12px; border-radius: 6px; border: 1px solid rgba(52, 211, 153, 0.4);">
            <i class="fas fa-layer-group"></i> ${t.total_turnos} Turnos Concatenados
          </span>
          <span style="font-size: 0.82rem; color: #818cf8; font-weight: 700; background: rgba(99, 102, 241, 0.15); padding: 5px 12px; border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.4);">
            <i class="fas fa-hourglass-half"></i> ${t.horas_efectivas_str} Efectivas
          </span>
          <span style="font-size: 0.82rem; color: #fbbf24; font-weight: 700; background: rgba(251, 191, 36, 0.15); padding: 5px 12px; border-radius: 6px; border: 1px solid rgba(251, 191, 36, 0.4);">
            <i class="fas fa-link"></i> Sin Baches Intermedios
          </span>
        </div>
      </div>

      <!-- Fila 1: 4 Tarjetas de Indicadores Principales -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 20px;">
        <!-- 1. Kg Totales -->
        <div class="kpi-card-striking kpi-card-cyan" style="margin: 0;">
          <div class="kpi-card-header">
            <h4>Kg Totales del Período</h4>
            <div class="kpi-icon-circle"><i class="fas fa-weight-hanging"></i></div>
          </div>
          <div class="kpi-big-number">${t.total_kg_str}</div>
          <div class="kpi-card-subtext">Kilos totales procesados en los ${t.total_turnos} turnos</div>
        </div>

        <!-- 2. Cargas Totales -->
        <div class="kpi-card-striking kpi-card-amber" style="margin: 0;">
          <div class="kpi-card-header">
            <h4>Cargas Totales del Período</h4>
            <div class="kpi-icon-circle"><i class="fas fa-layer-group"></i></div>
          </div>
          <div class="kpi-big-number">${t.total_cargas_str}</div>
          <div class="kpi-card-subtext">Cargas efectivas descargadas en el período</div>
        </div>

        <!-- 3. ikProd General del Período -->
        <div class="kpi-card-striking" style="margin: 0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid ${t.ikprod.border_color}; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
          <div class="kpi-card-header">
            <h4 style="color: #f8fafc;">ikProd General del Período</h4>
            <div class="kpi-icon-circle" style="background: rgba(255, 255, 255, 0.08); color: ${t.ikprod.text_color};"><i class="fas fa-chart-line"></i></div>
          </div>
          <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: ${t.ikprod.text_color}; text-shadow: 0 0 16px ${t.ikprod.text_color}60;">${t.ikprod.pct_str}</div>
          <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 2px; margin-bottom: 6px; flex-wrap: wrap;">
            <span style="font-size: 0.72rem; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.3);"><i class="fas fa-weight-hanging"></i> ${t.promedio_peso_str}</span>
            <span style="font-size: 0.72rem; font-weight: 600; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(251, 191, 36, 0.3);"><i class="fas fa-stopwatch"></i> ${t.promedio_tiempo_str}</span>
          </div>
          <div style="font-size: 0.75rem; color: #94a3b8; font-weight: 600; text-align: center;">
            <i class="fas fa-calculator"></i> ${t.ikprod.neto_str} | Ideal: 30 = 100%
          </div>
        </div>

        <!-- 4. Kg / Hora General -->
        <div class="kpi-card-striking kpi-card-cyan" style="margin: 0; background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
          <div class="kpi-card-header">
            <h4>Kg / Hora General</h4>
            <div class="kpi-icon-circle"><i class="fas fa-tachometer-alt"></i></div>
          </div>
          <div class="kpi-big-number">${t.kg_hora_str}</div>
          <div class="kpi-card-subtext">Productividad real sobre ${t.horas_efectivas_str}</div>
        </div>
      </div>

      <!-- Fila 2: 4 Tarjetas Métricas Complementarias -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 24px;">
        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
          <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-clock" style="color: #38bdf8;"></i> Horas Efectivas Totales</div>
          <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.horas_efectivas_str}</div>
          <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Suma neta de los turnos concatenados</div>
        </div>

        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
          <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-weight-hanging" style="color: #fbbf24;"></i> Peso Promedio por Carga</div>
          <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.promedio_peso_str}</div>
          <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Relación Kg Totales / Cargas Totales</div>
        </div>

        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
          <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-stopwatch" style="color: #34d399;"></i> Cadencia Promedio (Tprom)</div>
          <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.promedio_tiempo_str}</div>
          <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Tiempo medio entre descargas sucesivas</div>
        </div>

        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
          <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-industry" style="color: #818cf8;"></i> Promedio Kg por Turno</div>
          <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${((t.total_kg / Math.max(t.total_turnos, 1)).toFixed(1)).replace('.', ',')} kg</div>
          <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Media de producción por turno analizado</div>
        </div>
      </div>

      <!-- Fila 3: Tabla Detallada de Turnos Concatenados -->
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
          <div>
            <h4 style="color: #f8fafc; font-size: 1.1rem; margin: 0;"><i class="fas fa-list-check" style="color: #818cf8; margin-right: 8px;"></i> Turnos de Producción Concatenados (${t.total_turnos})</h4>
            <small style="color: #94a3b8; font-size: 0.8rem;">Detalle cronológico de los turnos sumados contiguamente en la ventana seleccionada</small>
          </div>
          <span style="font-size: 0.78rem; color: #94a3b8; background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 6px;">
            Fuente: Tabla de Persistencia de Turnos
          </span>
        </div>

        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 0.88rem;">
            <thead>
              <tr style="border-bottom: 1.5px solid rgba(255, 255, 255, 0.12); color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">
                <th style="padding: 10px 14px;">#</th>
                <th style="padding: 10px 14px;">Fecha</th>
                <th style="padding: 10px 14px;">Turno</th>
                <th style="padding: 10px 14px;">Horario</th>
                <th style="padding: 10px 14px;">Duración</th>
                <th style="padding: 10px 14px; text-align: right;">Kg Totales</th>
                <th style="padding: 10px 14px; text-align: right;">Cargas</th>
                <th style="padding: 10px 14px; text-align: right;">ikProd</th>
                <th style="padding: 10px 14px; text-align: right;">Kg / Hora</th>
              </tr>
            </thead>
            <tbody>
              ${data.turnos_concatenados.map((item, idx) => `
                <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.06); transition: background 0.2s ease;">
                  <td style="padding: 12px 14px; color: #818cf8; font-weight: 700;">#${idx + 1}</td>
                  <td style="padding: 12px 14px; color: #f8fafc; font-weight: 600;">${item.fecha_formateada}</td>
                  <td style="padding: 12px 14px; color: #38bdf8; font-weight: 700;">${item.nombre_turno}</td>
                  <td style="padding: 12px 14px; color: #cbd5e1;">${item.rango_horario}</td>
                  <td style="padding: 12px 14px; color: #94a3b8;">${item.duracion_horas}h</td>
                  <td style="padding: 12px 14px; text-align: right; color: #38bdf8; font-weight: 700;">${item.total_kg_str}</td>
                  <td style="padding: 12px 14px; text-align: right; color: #fbbf24; font-weight: 700;">${item.total_cargas_str}</td>
                  <td style="padding: 12px 14px; text-align: right; color: #34d399; font-weight: 700;">${item.ikprod_str}</td>
                  <td style="padding: 12px 14px; text-align: right; color: #f8fafc; font-weight: 700;">${item.hprod_str}</td>
                </tr>
              `).join('')}
            </tbody>
            <tfoot>
              <tr style="border-top: 2px solid rgba(129, 140, 248, 0.4); background: rgba(99, 102, 241, 0.08); font-weight: 800;">
                <td colspan="4" style="padding: 14px; color: #818cf8;">TOTALES CONSOLIDADOS (${t.total_turnos} turnos)</td>
                <td style="padding: 14px; color: #f8fafc;">${t.horas_efectivas_str}</td>
                <td style="padding: 14px; text-align: right; color: #38bdf8; font-size: 1rem;">${t.total_kg_str}</td>
                <td style="padding: 14px; text-align: right; color: #fbbf24; font-size: 1rem;">${t.total_cargas_str}</td>
                <td style="padding: 14px; text-align: right; color: #34d399; font-size: 1rem;">${t.ikprod.pct_str}</td>
                <td style="padding: 14px; text-align: right; color: #f8fafc; font-size: 1rem;">${t.kg_hora_str}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    `;
  } catch (err) {
    console.error('Error calculando totales del período:', err);
    dashboardContainer.innerHTML = `<div style="color: var(--accent-red); padding: 20px; background: rgba(239,68,68,0.1); border-radius: 8px; border: 1px solid rgba(239,68,68,0.3);">⚠️ ${err.message}</div>`;
  }
}

// ==========================================
// PANTALLA: COMPARAR TURNOS Y RANKING TOP 5
// ==========================================
function initCompararTurnosScreen() {
  const fechaIniInput = document.getElementById('comparar-fecha-inicio');
  const fechaFinInput = document.getElementById('comparar-fecha-fin');
  const placeholder = document.getElementById('comparar-placeholder');
  const rankingContainer = document.getElementById('comparar-ranking-container');
  const dashboardContainer = document.getElementById('comparar-dashboard-container');

  if (placeholder) placeholder.style.display = 'block';
  if (rankingContainer) {
    rankingContainer.style.display = 'none';
    rankingContainer.innerHTML = '';
  }
  if (dashboardContainer) {
    dashboardContainer.style.display = 'none';
    dashboardContainer.innerHTML = '';
  }

  // Fechas predeterminadas: últimos 7 días hasta hoy
  const now = new Date();
  const past7 = new Date();
  past7.setDate(now.getDate() - 7);

  const formatYMD = (d) => {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  if (fechaFinInput && !fechaFinInput.value) {
    fechaFinInput.value = formatYMD(now);
  }
  if (fechaIniInput && !fechaIniInput.value) {
    fechaIniInput.value = formatYMD(past7);
  }
}

async function buscarComparativaTurnos() {
  const fechaIniInput = document.getElementById('comparar-fecha-inicio');
  const fechaFinInput = document.getElementById('comparar-fecha-fin');
  const criterioSelect = document.getElementById('comparar-criterio-select');
  const placeholder = document.getElementById('comparar-placeholder');
  const rankingContainer = document.getElementById('comparar-ranking-container');
  const dashboardContainer = document.getElementById('comparar-dashboard-container');

  const fechaInicio = fechaIniInput ? fechaIniInput.value : '';
  const fechaFin = fechaFinInput ? fechaFinInput.value : '';
  const criterio = criterioSelect ? criterioSelect.value : 'ikprod';

  if (!fechaInicio || !fechaFin) {
    alert('Por favor selecciona la Fecha Inicio y la Fecha Fin.');
    return;
  }
  if (fechaFin < fechaInicio) {
    alert('La Fecha Fin debe ser posterior o igual a la Fecha Inicio.');
    return;
  }

  if (placeholder) placeholder.style.display = 'none';
  if (dashboardContainer) {
    dashboardContainer.style.display = 'none';
    dashboardContainer.innerHTML = '';
  }

  if (rankingContainer) {
    rankingContainer.style.display = 'block';
    rankingContainer.innerHTML = `
      <div style="text-align: center; padding: 40px; color: var(--text-muted);">
        <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #34d399; margin-bottom: 12px;"></i>
        <p>Analizando y clasificando los 5 mejores turnos...</p>
      </div>
    `;
  }

  try {
    const url = `/api/produccion/turnos/ranking?fecha_inicio=${encodeURIComponent(fechaInicio)}&fecha_fin=${encodeURIComponent(fechaFin)}&criterio=${encodeURIComponent(criterio)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error al obtener comparativa');
    }
    const data = await res.json();

    if (!data.ranking || data.ranking.length === 0) {
      rankingContainer.innerHTML = `
        <div style="text-align: center; padding: 60px 20px; background: rgba(15, 23, 42, 0.7); border-radius: 14px; border: 1px dashed rgba(239, 68, 68, 0.4);">
          <i class="fas fa-info-circle" style="font-size: 3rem; color: #ef4444; opacity: 0.8; margin-bottom: 16px;"></i>
          <h4 style="color: #f8fafc; font-size: 1.3rem;">No se encontraron turnos en este rango</h4>
          <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 8px;">No hay turnos registrados entre el ${fechaInicio} y el ${fechaFin}. Prueba ampliando el rango de fechas.</p>
        </div>
      `;
      return;
    }

    // Estilos de posiciones del Top 5
    const badgesInfo = {
      1: { label: '#1', color: '#fbbf24', border: '#f59e0b', bg: 'rgba(251, 191, 36, 0.15)', glow: '0 4px 20px rgba(245, 158, 11, 0.25)' },
      2: { label: '#2', color: '#e2e8f0', border: '#94a3b8', bg: 'rgba(148, 163, 184, 0.15)', glow: '0 4px 16px rgba(148, 163, 184, 0.2)' },
      3: { label: '#3', color: '#f97316', border: '#d97706', bg: 'rgba(217, 119, 6, 0.15)', glow: '0 4px 16px rgba(217, 119, 6, 0.2)' },
      4: { label: '#4', color: '#38bdf8', border: '#0284c7', bg: 'rgba(56, 189, 248, 0.12)', glow: 'none' },
      5: { label: '#5', color: '#818cf8', border: '#6366f1', bg: 'rgba(129, 140, 248, 0.12)', glow: 'none' }
    };

    let html = `
      <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(52, 211, 153, 0.4); border-radius: 12px; padding: 14px 20px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 40px; height: 40px; border-radius: 10px; background: rgba(52, 211, 153, 0.2); color: #34d399; display: flex; align-items: center; justify-content: center; font-size: 1.3rem;">
            <i class="fas fa-trophy"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 1.05rem; margin: 0;">Top 5 de Turnos: <span style="color: #34d399;">${data.criterio_titulo}</span></h4>
            <small style="color: var(--text-muted); font-size: 0.78rem;">Rango analizado: ${fechaInicio} al ${fechaFin} | Turnos evaluados: <strong>${data.total_turnos_evaluados}</strong></small>
          </div>
        </div>
        <span style="font-size: 0.78rem; color: #34d399; font-weight: 700; background: rgba(52, 211, 153, 0.15); padding: 4px 12px; border-radius: 6px; border: 1px solid rgba(52, 211, 153, 0.3);">
          ⚡ Haz clic en un turno para abrir su Dashboard
        </span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 12px;">
    `;

    data.ranking.forEach(item => {
      const b = badgesInfo[item.posicion] || badgesInfo[5];
      html += `
        <div class="comparar-ranking-card" onclick="mostrarDashboardTurnoComparado('${item.shift_key}')" style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%); border: 1.5px solid ${b.border}; border-radius: 14px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; transition: all 0.25s ease; box-shadow: ${b.glow}; gap: 16px; flex-wrap: wrap;">
          <!-- Columna Izquierda: Posición e Identificación del Turno -->
          <div style="display: flex; align-items: center; gap: 16px; min-width: 240px;">
            <div style="width: 48px; height: 48px; border-radius: 12px; background: ${b.bg}; border: 1.5px solid ${b.border}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
              <span style="font-size: 1.25rem; font-weight: 900; color: ${b.color}; letter-spacing: -0.5px;">${b.label}</span>
            </div>
            <div>
              <h4 style="font-size: 1.15rem; color: #f8fafc; margin: 0; font-weight: 700;">${item.nombre_turno}</h4>
              <div style="color: #38bdf8; font-size: 0.84rem; font-weight: 600; margin-top: 2px;">
                <i class="fas fa-calendar-alt"></i> ${item.fecha_formateada} &nbsp;|&nbsp; <i class="fas fa-clock"></i> ${item.rango_horario}
              </div>
            </div>
          </div>

          <!-- Columna Centro: Métricas Secundarias -->
          <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <span style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 12px; font-size: 0.8rem; color: #cbd5e1;">
              <i class="fas fa-weight-hanging" style="color: #38bdf8;"></i> <strong>${item.total_kg_str}</strong>
            </span>
            <span style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 12px; font-size: 0.8rem; color: #cbd5e1;">
              <i class="fas fa-boxes" style="color: #fbbf24;"></i> <strong>${item.total_cargas_str}</strong>
            </span>
            <span style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 12px; font-size: 0.8rem; color: #cbd5e1;">
              <i class="fas fa-chart-line" style="color: #34d399;"></i> <strong>${item.ikprod_str}</strong> ikProd
            </span>
            <span style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 12px; font-size: 0.8rem; color: #cbd5e1;">
              <i class="fas fa-tachometer-alt" style="color: #0ea5e9;"></i> <strong>${item.hprod_str}</strong>
            </span>
          </div>

          <!-- Columna Derecha: Métrica Destacada y Botón de Acción -->
          <div style="display: flex; align-items: center; gap: 16px; text-align: right;">
            <div>
              <div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px;">${data.criterio_titulo}</div>
              <div style="font-size: 1.5rem; font-weight: 900; color: ${b.color}; line-height: 1.1; margin-top: 2px;">${item.criterio_label}</div>
            </div>
            <div style="width: 38px; height: 38px; border-radius: 50%; background: rgba(52, 211, 153, 0.15); color: #34d399; display: flex; align-items: center; justify-content: center; font-size: 1rem; border: 1px solid rgba(52, 211, 153, 0.4);">
              <i class="fas fa-chevron-right"></i>
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    rankingContainer.innerHTML = html;
  } catch (err) {
    console.error('Error buscando comparativa de turnos:', err);
    rankingContainer.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

async function mostrarDashboardTurnoComparado(shiftKey) {
  const dashboardContainer = document.getElementById('comparar-dashboard-container');
  if (!dashboardContainer) return;

  dashboardContainer.style.display = 'block';
  dashboardContainer.innerHTML = `
    <div style="text-align: center; padding: 40px; color: var(--text-muted);">
      <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #34d399; margin-bottom: 12px;"></i>
      <p>Cargando Dashboard completo del turno seleccionado...</p>
    </div>
  `;

  try {
    const res = await fetch(`/api/produccion/turnos/historial-json/${shiftKey}`);
    if (!res.ok) throw new Error('No se pudo cargar el paquete completo del turno');
    const pkg = await res.json();

    const meta = pkg.meta_info || {};
    const ind = pkg.indicadores_ampliados || {};
    const tot = pkg.totales_promedios || {};
    const desglose = pkg.desglose_horario || {};

    const kgInfo = {
      titulo: 'Kg Totales Turno',
      valor: ind.kg_totales_turno?.valor_str || '0 kg',
      subtexto: `Objetivo Turno: ${(tot.objetivo_turno_kg || 0).toLocaleString('es-ES')} kg (${meta.es_datos_reales ? 'Real MQTT' : 'Simulado'})`,
      icono: 'fa-balance-scale'
    };

    const cargasInfo = {
      titulo: 'Cargas Totales Turno',
      valor: ind.cargas_totales_turno?.valor_str || '0 cargas',
      subtexto: `Promedio: ${tot.promedio_peso_carga_kg || 0} kg/carga`,
      icono: 'fa-boxes'
    };

    const hprodInfo = {
      titulo: 'Productividad (hProd)',
      valor: ind.productividad_hprod?.valor_str || '0 kg/h',
      subtexto: `Tiempo prom: ${tot.promedio_tiempo_entre_cargas_min || 0} min (${tot.promedio_tiempo_entre_cargas_seg || 0}s)`,
      icono: 'fa-tachometer-alt'
    };

    const ikprodInfo = ind.indice_eficiencia_ikprod || {
      pct_str: '0.0%',
      neto_str: 'ikProd Neto: 0.00',
      color_codigo: 'red',
      tprom_str: 'Tprom: 0 min',
      subtexto: 'Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%'
    };

    const clientesInfo = {
      titulo: 'Clientes Atendidos',
      valor: ind.clientes_unicos?.valor_str || '0 clientes',
      subtexto: 'Códigos únicos de cliente en turno',
      icono: 'fa-users'
    };

    const programasInfo = {
      titulo: 'Programas Ejecutados',
      valor: ind.programas_unicos?.valor_str || '0 programas',
      subtexto: 'Categorías/Programas únicos en turno',
      icono: 'fa-layer-group'
    };

    let ikprodTextColor = ikprodInfo.text_color || (ikprodInfo.color_codigo === 'red' ? '#ef4444' : ikprodInfo.color_codigo === 'orange' ? '#f97316' : '#34d399');
    let ikprodBorderColor = ikprodInfo.border_color || (ikprodInfo.color_codigo === 'red' ? '#ef4444' : ikprodInfo.color_codigo === 'orange' ? '#f97316' : '#10b981');

    dashboardContainer.innerHTML = `
      <!-- Barra Superior con Botón para Ocultar / Subir al Ranking -->
      <div style="background: rgba(15, 23, 42, 0.95); border: 1.5px solid #34d399; padding: 14px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <div style="width: 42px; height: 42px; border-radius: 10px; background: rgba(52, 211, 153, 0.2); color: #34d399; display: flex; align-items: center; justify-content: center; font-size: 1.3rem;">
            <i class="fas fa-chart-pie"></i>
          </div>
          <div>
            <h4 style="color: var(--text-main); font-size: 1.15rem; margin: 0;">${meta.nombre_turno || 'Turno'} (${meta.hora_inicio || ''} - ${meta.hora_fin || ''}) — <span style="color: #34d399;">📅 ${meta.fecha_formateada || meta.fecha}</span></h4>
            <small style="color: var(--text-muted); font-size: 0.8rem;">Detalle completo de turno seleccionado en la comparativa</small>
          </div>
        </div>

        <button class="btn-header" onclick="ocultarDashboardTurnoComparado()" style="background: rgba(148, 163, 184, 0.15); border: 1px solid #64748b; color: #f8fafc; font-size: 0.85rem;">
          <i class="fas fa-times"></i> Cerrar Detalle
        </button>
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

        <!-- Columna 1, Fila 2: ikProd (stacked verticalmente) -->
        <div class="kpi-card-striking" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid ${ikprodBorderColor}; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
          <div class="kpi-card-header">
            <h4 style="color: #f8fafc;">ÍNDICE DE EFICIENCIA (IKPROD)</h4>
            <div class="kpi-icon-circle" style="background: rgba(255, 255, 255, 0.08); color: ${ikprodTextColor};"><i class="fas fa-chart-line"></i></div>
          </div>
          <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: ${ikprodTextColor}; text-shadow: 0 0 16px ${ikprodTextColor}60;">${ikprodInfo.pct_str}</div>
          <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 2px; margin-bottom: 6px; flex-wrap: wrap;">
            <span style="font-size: 0.72rem; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.3);"><i class="fas fa-weight-hanging"></i> Prom: ${tot.promedio_peso_carga_kg || 0} kg/carga</span>
            <span style="font-size: 0.72rem; font-weight: 600; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(251, 191, 36, 0.3);"><i class="fas fa-stopwatch"></i> ${ikprodInfo.tprom_str || 'Tprom: 0 min'}</span>
          </div>
          <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 6px; margin-top: 2px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
            <span style="color: #38bdf8;"><i class="fas fa-clock"></i> ${ikprodInfo.tprom_str || ''}</span>
            <span>${ikprodInfo.neto_str}</span>
          </div>
          <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
            <i class="fas fa-calculator"></i> ${ikprodInfo.formula || 'Fórmula: (Kg Prom. / Tprom min) | Ideal: 30 = 100%'}
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

        <!-- Columna 3, Fila 1: Productividad hProd -->
        <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 3; grid-row: 1; background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
          <div class="kpi-card-header">
            <h4>${hprodInfo.titulo}</h4>
            <div class="kpi-icon-circle"><i class="fas ${hprodInfo.icono}"></i></div>
          </div>
          <div class="kpi-big-number">${hprodInfo.valor}</div>
          <div class="kpi-card-subtext">${hprodInfo.subtexto}</div>
        </div>

        <!-- Columna 4, Fila 1: Clientes y Programas -->
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
            <div style="font-size: 0.72rem; color: #94a3b8;">Eje Y Izq 1: Kg/Hora (rosa) | Eje Y Izq 2: Kg Acum (cian) | Eje Y Der: Cargas (oro)</div>
          </div>
          <div class="chart-wrapper">
            <canvas id="chart-comparar-turno"></canvas>
          </div>
        </div>
      </div>
    `;

    const graficaData = {
      labels: desglose.labels || [],
      kg_por_hora: desglose.kg_por_hora || [],
      cargas_por_hora: desglose.cargas_por_hora || [],
      kg_acumulado: desglose.kg_acumulado_por_hora || desglose.kg_acumulado || []
    };
    renderAvanceChart(graficaData, 'chart-comparar-turno');

    // Desplazamiento suave hacia el dashboard del turno
    dashboardContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    console.error('Error cargando detalle del turno seleccionado:', err);
    dashboardContainer.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

function ocultarDashboardTurnoComparado() {
  const dashboardContainer = document.getElementById('comparar-dashboard-container');
  if (dashboardContainer) {
    dashboardContainer.style.display = 'none';
    dashboardContainer.innerHTML = '';
  }
  const rankingContainer = document.getElementById('comparar-ranking-container');
  if (rankingContainer) {
    rankingContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

