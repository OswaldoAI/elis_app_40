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

    // Configure Análisis Button
  const analisisBtn = document.getElementById('btn-module-analisis');
  const canAnalisis = !userPermissions || !userPermissions['analisis'] || userPermissions['analisis'].can_view;
  if (analisisBtn) {
    const lockBadge = analisisBtn.querySelector('.lock-badge');
    if (canAnalisis) {
      analisisBtn.classList.remove('locked');
      if (lockBadge) lockBadge.style.display = 'none';
      analisisBtn.title = '';
    } else {
      analisisBtn.classList.add('locked');
      if (lockBadge) lockBadge.style.display = 'inline-block';
      analisisBtn.title = 'Acceso Restringido para tu rol';
    }
  }

  // Configure Rendimiento Button
  const rendimientoBtn = document.getElementById('btn-module-rendimiento');
  const canRendimiento = !userPermissions || !userPermissions['rendimiento'] || userPermissions['rendimiento'].can_view;
  if (rendimientoBtn) {
    const lockBadge = rendimientoBtn.querySelector('.lock-badge');
    if (canRendimiento) {
      rendimientoBtn.classList.remove('locked');
      if (lockBadge) lockBadge.style.display = 'none';
      rendimientoBtn.title = "Acceso a Módulo Rendimiento Jetson";
    } else {
      rendimientoBtn.classList.add('locked');
      if (lockBadge) lockBadge.style.display = 'inline-block';
      rendimientoBtn.title = "Acceso Restringido para tu rol";
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

  if (viewName === 'tunel_lavado' || viewName === 'historial_turnos' || viewName === 'calandra_2' || viewName === 'calandra_3' || viewName === 'tunel_vt') {
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
  } else if (viewName === 'tunel_lavado' || viewName === 'historial_turnos' || viewName === 'filtros_turno' || viewName === 'comparar_turnos' || viewName === 'calandra_2' || viewName === 'calandra_3' || viewName === 'tunel_vt') {
    const prodBtn = document.querySelector(`.menu-btn[data-view="produccion"]`);
    if (prodBtn) prodBtn.classList.add('active');
  }

  // Update browser location hash
  window.location.hash = `#${viewName}`;

  // Load section specific data
  if (viewName === 'produccion') {
    lastProduccionRefreshTime = Date.now();
    loadProduccionData();
  }
  if (viewName === 'tunel_lavado') loadTunelLavadoDashboard();
  if (viewName === 'calandra_2') loadCalandraDashboard('CALANDRA_2');
  if (viewName === 'calandra_3') loadCalandraDashboard('CALANDRA_3');
  if (viewName === 'tunel_vt') loadTunelVTDashboard();
  if (viewName === 'historial_turnos') initHistorialTurnosScreen();
  if (viewName === 'filtros_turno') initFiltrosTurnoScreen();
  if (viewName === 'comparar_turnos') initCompararTurnosScreen();
  if (viewName === 'consumos') {
    loadConsumosData();
    if (!consumosPollingInterval) {
      consumosPollingInterval = setInterval(updateConsumosRealtime, 30000);
    }
  } else {
    if (consumosPollingInterval) {
      clearInterval(consumosPollingInterval);
      consumosPollingInterval = null;
    }
  }
  if (viewName === 'usuarios') loadUsersList();
  if (viewName === 'permisos') loadPermissionsMatrix();
  if (viewName === 'rendimiento') {
    initRendimientoScreen();
  } else {
    stopRendimientoTimer();
  }
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
        if (msg.type === 'new_carga' || msg.type === 'update_dashboard' || msg.type === 'tunel_vt_update') {
          console.log('📥 Notificación en tiempo real recibida vía WebSocket:', msg);
          const currentHash = window.location.hash.replace('#', '') || 'inicio';
          if (currentHash === 'tunel_lavado') {
            loadTunelLavadoDashboard();
          } else if (currentHash === 'calandra_2') {
            loadCalandraDashboard('CALANDRA_2');
          } else if (currentHash === 'calandra_3') {
            loadCalandraDashboard('CALANDRA_3');
          } else if (currentHash === 'tunel_vt') {
            loadTunelVTDashboard();
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

// Auto-Refresh Controller (Refresca la vista activa: dashboards individuales cada 10 seg, producción general cada 120 seg)
let autoRefreshTimer = null;
let lastProduccionRefreshTime = 0;

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
    } else if (currentHash === 'tunel_vt') {
      loadTunelVTDashboard();
    } else if (currentHash === 'produccion') {
      const now = Date.now();
      if (now - lastProduccionRefreshTime >= 120000) {
        lastProduccionRefreshTime = now;
        loadProduccionData();
      }
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
  const valleData = g.tiempo_valle || g.tiempo_valle_min || [];
  const descansoData = g.tiempo_descanso || g.tiempo_descanso_min || [];
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

  // Barras verticales de tiempo valle neto (Eje Y Derecho, stack 'valle')
  datasets.push({
    type: 'bar',
    label: 'Tiempo Valle (min)',
    data: valleData,
    backgroundColor: 'rgba(245, 158, 11, 0.75)',
    borderColor: '#fbbf24',
    borderWidth: 1,
    borderRadius: 4,
    barPercentage: 0.45,
    stack: 'valle',
    yAxisID: 'yValle'
  });

  // Barras verticales de tiempo descanso (Eje Y Derecho, stack 'valle' apilada encima en rojo oscuro)
  datasets.push({
    type: 'bar',
    label: 'Tiempo Descanso (min)',
    data: descansoData,
    backgroundColor: 'rgba(153, 27, 27, 0.90)',
    borderColor: '#b91c1c',
    borderWidth: 1,
    borderRadius: 4,
    barPercentage: 0.45,
    stack: 'valle',
    yAxisID: 'yValle'
  });

  // Actualización in-place si la instancia del gráfico y su canvas ya existen
  const chartInst = window.calandraHourlyCharts[machineId];
  if (chartInst && chartInst.ctx && chartInst.ctx.canvas === canvas) {
    chartInst.data.labels = labels;
    if (isCal2 && chartInst.data.datasets.length >= 5) {
      chartInst.data.datasets[0].data = prendasData;
      chartInst.data.datasets[1].data = (g.grandes || []);
      chartInst.data.datasets[2].data = (g.pequenas || []);
      chartInst.data.datasets[3].data = valleData;
      chartInst.data.datasets[4].data = descansoData;
      chartInst.update('none');
      return;
    } else if (!isCal2 && chartInst.data.datasets.length >= 3) {
      chartInst.data.datasets[0].data = prendasData;
      chartInst.data.datasets[1].data = valleData;
      chartInst.data.datasets[2].data = descansoData;
      chartInst.update('none');
      return;
    }
  }

  if (chartInst) {
    try {
      chartInst.destroy();
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
      animation: false,
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
          stacked: true,
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

// Chart Instance and Renderer for Túnel VT (3 Vías de Prendas + 3 Barras de Tiempo Valle)
window.tunelVTHourlyChart = null;

function renderTunelVTHourlyChart(canvasId, vt) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  const g = vt.grafica_hora_a_hora;
  if (!g) return;

  const labels = g.labels || [];
  const e1Data = g.entrada_1 || [];
  const e2Data = g.entrada_2 || [];
  const e3Data = g.entrada_3 || [];
  const v1Data = g.valle_e1 || [];
  const v2Data = g.valle_e2 || [];
  const v3Data = g.valle_e3 || [];
  const d1Data = g.descanso_e1 || g.tiempo_descanso || [];
  const d2Data = g.descanso_e2 || g.tiempo_descanso || [];
  const d3Data = g.descanso_e3 || g.tiempo_descanso || [];

  const datasets = [
    // 3 Líneas de prendas por hora (Eje Y Izquierdo: yPrendas)
    {
      type: 'line',
      label: 'Entrada 1 (Prendas)',
      data: e1Data,
      borderColor: '#ffffff',
      backgroundColor: 'rgba(255, 255, 255, 0.12)',
      borderWidth: 2.8,
      pointBackgroundColor: '#ffffff',
      pointBorderColor: '#0ea5e9',
      pointRadius: 4.5,
      pointHoverRadius: 6.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    {
      type: 'line',
      label: 'Entrada 2 (Prendas)',
      data: e2Data,
      borderColor: '#34d399',
      backgroundColor: 'rgba(52, 211, 153, 0.12)',
      borderWidth: 2.5,
      pointBackgroundColor: '#059669',
      pointBorderColor: '#34d399',
      pointRadius: 4,
      pointHoverRadius: 6,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    {
      type: 'line',
      label: 'Entrada 3 (Prendas)',
      data: e3Data,
      borderColor: '#c084fc',
      backgroundColor: 'rgba(192, 132, 252, 0.12)',
      borderWidth: 2.5,
      pointBackgroundColor: '#9333ea',
      pointBorderColor: '#c084fc',
      pointRadius: 4,
      pointHoverRadius: 6,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    // 3 Barras verticales de tiempo valle y descanso por hora (Eje Y Derecho: yValle, apiladas por vía)
    {
      type: 'bar',
      label: 'Valle E1 (min)',
      data: v1Data,
      backgroundColor: 'rgba(251, 191, 36, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.8,
      categoryPercentage: 0.8,
      stack: 'e1',
      yAxisID: 'yValle'
    },
    {
      type: 'bar',
      label: 'Descanso E1',
      data: d1Data,
      backgroundColor: 'rgba(153, 27, 27, 0.90)',
      borderColor: '#b91c1c',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.8,
      categoryPercentage: 0.8,
      stack: 'e1',
      yAxisID: 'yValle'
    },
    {
      type: 'bar',
      label: 'Valle E2 (min)',
      data: v2Data,
      backgroundColor: 'rgba(249, 115, 22, 0.75)',
      borderColor: '#f97316',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.8,
      categoryPercentage: 0.8,
      stack: 'e2',
      yAxisID: 'yValle'
    },
    {
      type: 'bar',
      label: 'Descanso E2',
      data: d2Data,
      backgroundColor: 'rgba(153, 27, 27, 0.90)',
      borderColor: '#b91c1c',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.8,
      categoryPercentage: 0.8,
      stack: 'e2',
      yAxisID: 'yValle'
    },
    {
      type: 'bar',
      label: 'Valle E3 (min)',
      data: v3Data,
      backgroundColor: 'rgba(59, 130, 246, 0.78)',
      borderColor: '#60a5fa',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.8,
      categoryPercentage: 0.8,
      stack: 'e3',
      yAxisID: 'yValle'
    },
    {
      type: 'bar',
      label: 'Descanso E3',
      data: d3Data,
      backgroundColor: 'rgba(153, 27, 27, 0.90)',
      borderColor: '#b91c1c',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.8,
      categoryPercentage: 0.8,
      stack: 'e3',
      yAxisID: 'yValle'
    }
  ];

  // Actualización in-place sin parpadear si la instancia existe
  const chartInst = window.tunelVTHourlyChart;
  if (chartInst && chartInst.ctx && chartInst.ctx.canvas === canvas) {
    chartInst.data.labels = labels;
    if (chartInst.data.datasets.length >= 9) {
      chartInst.data.datasets[0].data = e1Data;
      chartInst.data.datasets[1].data = e2Data;
      chartInst.data.datasets[2].data = e3Data;
      chartInst.data.datasets[3].data = v1Data;
      chartInst.data.datasets[4].data = d1Data;
      chartInst.data.datasets[5].data = v2Data;
      chartInst.data.datasets[6].data = d2Data;
      chartInst.data.datasets[7].data = v3Data;
      chartInst.data.datasets[8].data = d3Data;
      chartInst.update('none');
      return;
    }
  }

  if (chartInst) {
    try {
      chartInst.destroy();
    } catch (e) {
      console.warn("Error destruyendo gráfico previo de Túnel VT:", e);
    }
  }

  const ctx = canvas.getContext('2d');
  window.tunelVTHourlyChart = new Chart(ctx, {
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
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
            padding: 8,
            filter: function(legendItem) {
              if (legendItem.text === 'Descanso E2' || legendItem.text === 'Descanso E3') return false;
              if (legendItem.text === 'Descanso E1') legendItem.text = 'Tiempo Descanso (min)';
              return true;
            }
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
            text: 'Prendas por Entrada',
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
          stacked: true,
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
    if (!res.ok) {
      if (res.status === 401 || res.status === 403) {
        throw new Error('Acceso no autorizado al módulo de producción');
      } else {
        throw new Error(`Error en el servidor de producción (${res.status})`);
      }
    }
    const data = await res.json();

    let html = `
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon blue"><i class="fas fa-weight-hanging"></i></div>
          <div class="metric-info">
            <h4>Kilos Lavados Hoy</h4>
            <div class="metric-value">${(data.kilos_lavados_hoy || 0).toLocaleString('es-ES')} kg</div>
            <small style="color: var(--text-muted)">Objetivo: ${(data.objetivo_diario || 18000).toLocaleString('es-ES')} kg</small>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon green"><i class="fas fa-scroll"></i></div>
          <div class="metric-info">
            <h4>Calandra Hoy</h4>
            <div class="metric-value" style="color: #34d399;">${(data.kilos_calandras_hoy || 0).toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 1 })} kg</div>
            <small style="color: var(--text-muted)">Calandra 2: ${data.kilos_cal2_hoy_str || '0 kg'} | Calandra 3: ${data.kilos_cal3_hoy_str || '0 kg'}</small>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon purple"><i class="fas fa-cubes"></i></div>
          <div class="metric-info">
            <h4>Máquinas en Servicio</h4>
            <div class="metric-value">4 / 4</div>
            <small style="color: var(--text-muted)">Líneas 100% Operativas</small>
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
        else if (m.id === 'TUNEL_VT') clickAttr = `onclick="switchView('tunel_vt')"`;
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
      } else if (m.produccion_tunel_vt) {
        if (!m.produccion_tunel_vt.is_turno_activo) {
          statusBadgeClass = 'status-inactivo';
        } else if (m.produccion_tunel_vt.en_valle) {
          statusBadgeClass = 'status-valle-alert';
        } else {
          statusBadgeClass = 'status-operativa';
        }
      }

      let avatarHtml = `<i class="fas ${m.icono}"></i>`;
      let avatarClass = 'machine-avatar';
      if (m.id === 'CALANDRA_2' || m.calandra_num === '2') {
        avatarClass += ' calandra-avatar';
        avatarHtml = `<i class="fas fa-scroll"></i><span class="calandra-avatar-num">2</span>`;
      } else if (m.id === 'CALANDRA_3' || m.calandra_num === '3') {
        avatarClass += ' calandra-avatar';
        avatarHtml = `<i class="fas fa-scroll"></i><span class="calandra-avatar-num">3</span>`;
      }

      html += `
        <div class="${cardClass}" id="card-${m.id}" ${clickAttr}>
          ${isClickable ? '<span class="card-link-badge"><i class="fas fa-external-link-alt"></i> Dashboard Ampliado</span>' : ''}
          <div class="machine-header-row">
            <div class="machine-title-box">
              <div class="${avatarClass}">
                ${avatarHtml}
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
        } else if (m.produccion_tunel_vt) {
          const vt = m.produccion_tunel_vt;
          const de = vt.desglose_entradas;

          html += `
            <div class="section-subtitle-bar">
              <h4><i class="fas fa-wind"></i> Indicadores Túnel VT — Turno Actual</h4>
              <div class="subtitle-line"></div>
            </div>

            <div class="calandra-kpi-grid">
              <!-- 1. Prendas Totales -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-tshirt" style="color: #38bdf8;"></i>
                  <span>Prendas Totales</span>
                </div>
                <div class="calandra-kpi-val">${vt.prendas_totales_str}</div>
                ${de ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Entrada 1" style="color: #38bdf8; background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.3);">E1: ${de.entrada_1 || 0}</span>
                    <span class="cal-badge-p" title="Entrada 2" style="color: #34d399; background: rgba(52, 211, 153, 0.15); border-color: rgba(52, 211, 153, 0.3);">E2: ${de.entrada_2 || 0}</span>
                    <span class="cal-badge-g" title="Entrada 3" style="color: #c084fc; background: rgba(192, 132, 252, 0.15); border-color: rgba(192, 132, 252, 0.3);">E3: ${de.entrada_3 || 0}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 2. Kgs Totales -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-weight-hanging" style="color: #34d399;"></i>
                  <span>Kgs Totales</span>
                </div>
                <div class="calandra-kpi-val" style="color: #34d399;">${vt.kgs_totales_str}</div>
                ${de ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Kilos E1" style="color: #38bdf8; background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.3);">E1: ${de.kg_e1_str || '0,0 kg'}</span>
                    <span class="cal-badge-p" title="Kilos E2" style="color: #34d399; background: rgba(52, 211, 153, 0.15); border-color: rgba(52, 211, 153, 0.3);">E2: ${de.kg_e2_str || '0,0 kg'}</span>
                    <span class="cal-badge-g" title="Kilos E3" style="color: #c084fc; background: rgba(192, 132, 252, 0.15); border-color: rgba(192, 132, 252, 0.3);">E3: ${de.kg_e3_str || '0,0 kg'}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 3. Tiempo Valle -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-stopwatch" style="color: ${vt.en_valle ? '#f87171' : '#fbbf24'};"></i>
                  <span>Tiempo Valle</span>
                </div>
                <div class="calandra-kpi-val" style="color: ${vt.en_valle ? '#f87171' : '#fbbf24'};">${vt.tiempo_valle_str}</div>
                <div class="calandra-pill-row">
                  <span class="valle-pill ${vt.en_valle ? 'in-valle' : 'running'}">
                    ${vt.en_valle ? '⚠️ En Valle' : '⚡ Produciendo'}
                  </span>
                </div>
                ${de ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Valle E1" style="color: #fbbf24; background: rgba(251, 191, 36, 0.15); border-color: rgba(251, 191, 36, 0.3);">E1: ${de.tiempo_valle_e1_str || '0,0 min'}</span>
                    <span class="cal-badge-p" title="Valle E2" style="color: #f97316; background: rgba(249, 115, 22, 0.15); border-color: rgba(249, 115, 22, 0.3);">E2: ${de.tiempo_valle_e2_str || '0,0 min'}</span>
                    <span class="cal-badge-g" title="Valle E3" style="color: #60a5fa; background: rgba(59, 130, 246, 0.15); border-color: rgba(59, 130, 246, 0.3);">E3: ${de.tiempo_valle_e3_str || '0,0 min'}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 4. Prendas / Hora -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-tachometer-alt" style="color: #a78bfa;"></i>
                  <span>Prendas / Hora</span>
                </div>
                <div class="calandra-kpi-val" style="color: #a78bfa;">${vt.prendas_hora_str}</div>
                ${de ? `
                  <div class="calandra-pill-row">
                    <span class="cal-badge-g" title="Cadencia E1" style="color: #38bdf8; background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.3);">E1: ${de.prendas_e1_hora_str || '0 p/h'}</span>
                    <span class="cal-badge-p" title="Cadencia E2" style="color: #34d399; background: rgba(52, 211, 153, 0.15); border-color: rgba(52, 211, 153, 0.3);">E2: ${de.prendas_e2_hora_str || '0 p/h'}</span>
                    <span class="cal-badge-g" title="Cadencia E3" style="color: #c084fc; background: rgba(192, 132, 252, 0.15); border-color: rgba(192, 132, 252, 0.3);">E3: ${de.prendas_e3_hora_str || '0 p/h'}</span>
                  </div>
                ` : ''}
              </div>

              <!-- 5. Kg / Hora -->
              <div class="calandra-kpi-box">
                <div class="calandra-kpi-header">
                  <i class="fas fa-balance-scale" style="color: #f43f5e;"></i>
                  <span>Kg / Hora</span>
                </div>
                <div class="calandra-kpi-val" style="color: #f43f5e;">${vt.kg_hora_str}</div>
                <div class="calandra-pill-row">
                  <span class="cal-badge-subtle">Ritmo horario</span>
                </div>
              </div>
            </div>
          `;
        }
      }

      // Render Telemetry Grid only if metricas_clave has elements and not custom production cards
      if (m.metricas_clave && m.metricas_clave.length > 0 && !m.produccion_calandra && !m.produccion_tunel_vt) {
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

      // Rendimiento OEE y Programa Actual SOLO para Túnel de Lavado
      if (m.id === 'TUNEL_LAVADO') {
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
        `;
      }

      html += `
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

// Helpers para desgloses y botones de Calandras (evita código duplicado y permite refresco in-place)
function getCalandraCotejoBtnHtml(maquinaId, comp) {
  if (comp && comp.disponible_5002) {
    return `
      <button class="btn-header" onclick="openModalComparar5002('${maquinaId}')" style="font-size: 0.82rem; padding: 5px 12px; background: ${comp.coincidencia_exacta ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)'}; border: 1px solid ${comp.coincidencia_exacta ? '#10b981' : '#f59e0b'}; color: ${comp.coincidencia_exacta ? '#34d399' : '#fbbf24'}; cursor: pointer; border-radius: 8px;">
        <i class="fas ${comp.coincidencia_exacta ? 'fa-check-circle' : 'fa-balance-scale'}"></i> Cotejo Puerto 5002: ${comp.coincidencia_exacta ? '✅ 100% Coincidente' : 'Ver Comparativa'}
      </button>
    `;
  }
  return `
    <button class="btn-header" onclick="openModalComparar5002('${maquinaId}')" style="font-size: 0.82rem; padding: 5px 12px; background: rgba(56, 189, 248, 0.15); border: 1px solid #38bdf8; color: #38bdf8; cursor: pointer; border-radius: 8px;">
      <i class="fas fa-balance-scale"></i> Cotejo Puerto 5002
    </button>
  `;
}

function getCalandraDesglosePrendasHtml(isCal2, ind) {
  if (!isCal2 || !ind.desglose_calandra2) return '';
  return `
    <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start; gap: 8px;">
      <span class="cal-badge-g" style="font-size: 1.05rem; padding: 4px 10px;"><i class="fas fa-expand-alt"></i> ${ind.desglose_calandra2.prendas_grandes_str}</span>
      <span class="cal-badge-p" style="font-size: 1.05rem; padding: 4px 10px;"><i class="fas fa-compress-alt"></i> ${ind.desglose_calandra2.prendas_pequenas_str}</span>
    </div>
  `;
}

function getCalandraDesgloseKgsHtml(isCal2, ind) {
  if (isCal2 && ind.desglose_calandra2) {
    const d = ind.desglose_calandra2;
    const puG = d.peso_unitario_grandes_str ? ` · ${d.peso_unitario_grandes_str}` : '';
    const puP = d.peso_unitario_pequenas_str ? ` · ${d.peso_unitario_pequenas_str}` : '';
    return `
      <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start; gap: 8px;">
        <span class="cal-badge-g" style="font-size: 1.05rem; padding: 4px 10px;" title="Prendas Grandes (Peso Unitario)"><i class="fas fa-expand-alt"></i> ${d.kg_grandes_str}${puG}</span>
        <span class="cal-badge-p" style="font-size: 1.05rem; padding: 4px 10px;" title="Prendas Pequeñas (Peso Unitario)"><i class="fas fa-compress-alt"></i> ${d.kg_pequenas_str}${puP}</span>
      </div>
    `;
  } else if (!isCal2 && ind.peso_unitario_info) {
    return `
      <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start; gap: 8px;">
        <span class="cal-badge-p" style="font-size: 1.05rem; padding: 4px 10px; background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.4); color: #38bdf8;" title="Peso Unitario MQTT">
          <i class="fas fa-balance-scale"></i> ${ind.peso_unitario_info}
        </span>
      </div>
    `;
  }
  return '';
}

function getCalandraDesgloseValleHtml(isCal2, ind) {
  if (!isCal2 || !ind.desglose_calandra2) return '';
  return `
    <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start; gap: 8px;">
      <span class="cal-badge-g" style="font-size: 1.05rem; padding: 4px 10px;">${ind.desglose_calandra2.tiempo_valle_grandes_str} Gdes</span>
      <span class="cal-badge-p" style="font-size: 1.05rem; padding: 4px 10px;">${ind.desglose_calandra2.tiempo_valle_pequenas_str} Peq</span>
    </div>
  `;
}

function getCalandraDesglosePrendasHoraHtml(isCal2, ind) {
  if (!isCal2 || !ind.desglose_calandra2) return '';
  return `
    <div class="calandra-pill-row" style="margin-top: 10px; justify-content: flex-start; gap: 8px;">
      <span class="cal-badge-g" style="font-size: 1.05rem; padding: 4px 10px;">${ind.desglose_calandra2.prendas_grandes_hora_str}</span>
      <span class="cal-badge-p" style="font-size: 1.05rem; padding: 4px 10px;">${ind.desglose_calandra2.prendas_pequenas_hora_str}</span>
    </div>
  `;
}

function getCalandraDesgloseKgHoraHtml(isCal2, ind) {
  if (isCal2 && ind.desglose_calandra2) {
    return `
      <div style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 8px; margin-bottom: 8px; flex-wrap: wrap;">
        <span style="font-size: 1.05rem; font-weight: 700; color: #c084fc; background: rgba(168, 85, 247, 0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(168, 85, 247, 0.35);" title="Kg Grandes por hora">
          <i class="fas fa-expand-alt"></i> ${ind.desglose_calandra2.kg_grandes_str}
        </span>
        <span style="font-size: 1.05rem; font-weight: 700; color: #60a5fa; background: rgba(59, 130, 246, 0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(59, 130, 246, 0.35);" title="Kg Pequeñas por hora">
          <i class="fas fa-compress-alt"></i> ${ind.desglose_calandra2.kg_pequenas_str}
        </span>
      </div>
      <div style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-bottom: 10px; flex-wrap: wrap;">
        <span style="font-size: 1.02rem; font-weight: 700; color: #c084fc; background: rgba(168, 85, 247, 0.12); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(168, 85, 247, 0.25);" title="Cadencia Grandes">
          ${ind.desglose_calandra2.prendas_grandes_hora_str}
        </span>
        <span style="font-size: 1.02rem; font-weight: 700; color: #60a5fa; background: rgba(59, 130, 246, 0.12); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(59, 130, 246, 0.25);" title="Cadencia Pequeñas">
          ${ind.desglose_calandra2.prendas_pequenas_hora_str}
        </span>
      </div>
    `;
  } else {
    return `
      <div style="display: flex; gap: 8px; justify-content: center; align-items: center; margin-top: 8px; margin-bottom: 12px; flex-wrap: wrap;">
        <span style="font-size: 1.05rem; font-weight: 700; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">
          <i class="fas fa-tshirt"></i> ${ind.prendas_hora_str}
        </span>
        <span style="font-size: 1.05rem; font-weight: 700; color: #34d399; background: rgba(52, 211, 153, 0.12); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(52, 211, 153, 0.3);">
          <i class="fas fa-weight-hanging"></i> ${ind.kgs_totales_str}
        </span>
        ${ind.peso_unitario_info ? `
          <span style="font-size: 1.05rem; font-weight: 700; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(251, 191, 36, 0.3);" title="Peso Unitario MQTT">
            <i class="fas fa-balance-scale"></i> ${ind.peso_unitario_info}
          </span>
        ` : ''}
      </div>
    `;
  }
}

function getCalandraPesoBannerText(isCal2, ind) {
  if (isCal2) {
    const pPeq = ind.peso_pequenas_gr || (ind.desglose_calandra2 && ind.desglose_calandra2.peso_unitario_pequenas ? Math.round(ind.desglose_calandra2.peso_unitario_pequenas * 1000) : (ind.desglose_cal2 && ind.desglose_cal2.peso_pequenas ? Math.round(ind.desglose_cal2.peso_pequenas * 1000) : 470));
    const pGra = ind.peso_grandes_gr || (ind.desglose_calandra2 && ind.desglose_calandra2.peso_unitario_grandes ? Math.round(ind.desglose_calandra2.peso_unitario_grandes * 1000) : (ind.desglose_cal2 && ind.desglose_cal2.peso_grandes ? Math.round(ind.desglose_cal2.peso_grandes * 1000) : 780));
    return `Peq: ${pPeq}g | Gde: ${pGra}g`;
  } else {
    return ind.peso_unitario_str || `${ind.peso_unitario_gr || 1180} gr/u`;
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
    const canvasId = `chart-dashboard-${maquinaId.toLowerCase()}`;
    const canvasExists = document.getElementById(canvasId);

    if (!canvasExists) {
      let html = `
        <!-- Banner de Turno -->
        <div class="shift-banner" style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
            <span id="cal-shift-title-${maquinaId}" class="shift-title"><i class="fas fa-user-clock"></i> ${turno.nombre} (${turno.horario})</span>
            <span id="cal-shift-time-${maquinaId}" class="shift-time"><i class="fas fa-calendar-alt"></i> ${turno.fecha || ''}</span>
            <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; font-size: 0.78rem; font-weight: 600; padding: 3px 8px; border-radius: 6px;">
              <i class="fas fa-broadcast-tower"></i> Fuente: MQTT Directo
            </span>
          </div>
          <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <button onclick="openPesoModalCalandra('${maquinaId}')" class="btn-header" style="background: rgba(52, 211, 153, 0.15); border: 1px solid rgba(52, 211, 153, 0.4); color: #34d399; font-size: 0.82rem; font-weight: 700; cursor: pointer;" title="Configurar peso de prendas">
              <i class="fas fa-weight-hanging"></i> ${isCal2 ? 'Pesos:' : 'Peso Unitario:'} <span id="cal-peso-banner-${maquinaId}">${getCalandraPesoBannerText(isCal2, ind)}</span>
            </button>
            <div id="cal-cotejo-btn-wrapper-${maquinaId}">
              ${getCalandraCotejoBtnHtml(maquinaId, data.comparacion_5002)}
            </div>
          </div>
        </div>

        <!-- Alerta de Turno Inactivo -->
        <div id="cal-no-shift-alert-${maquinaId}" style="display: ${isShiftActive ? 'none' : 'flex'}; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(251, 191, 36, 0.4); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px; align-items: center; gap: 14px; color: #fbbf24;">
          <i class="fas fa-info-circle" style="font-size: 1.5rem;"></i>
          <div>
            <strong style="font-size: 1rem;">Sin Turno Activo en Curso:</strong> En este momento la planta no tiene un turno de producción en proceso. Todos los indicadores y la gráfica se presentan en cero hasta que comience el siguiente turno programado.
          </div>
        </div>

        <!-- Cuadrícula 4 Columnas x 2 Filas del Dashboard de Calandra -->
        <div class="calandra-dashboard-grid-layout">
          <!-- Columna 1, Fila 1: Prendas Totales -->
          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 1; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tshirt"></i> Prendas Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-layer-group"></i></div>
            </div>
            <div id="cal-kpi-prendas-${maquinaId}" class="kpi-big-number">${ind.prendas_totales_str}</div>
            <div class="kpi-card-subtext">Acumulado del turno en curso</div>
            <div id="cal-desglose-prendas-${maquinaId}">
              ${getCalandraDesglosePrendasHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 2, Fila 1: Kgs Totales -->
          <div class="kpi-card-striking kpi-card-green" style="grid-column: 2; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-weight-hanging"></i> Kgs Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-balance-scale-right"></i></div>
            </div>
            <div id="cal-kpi-kgs-${maquinaId}" class="kpi-big-number">${ind.kgs_totales_str}</div>
            <div class="kpi-card-subtext">Kilos procesados en el turno</div>
            <div id="cal-desglose-kgs-${maquinaId}">
              ${getCalandraDesgloseKgsHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 3, Fila 1: Tiempo Valle -->
          <div id="cal-card-valle-${maquinaId}" class="kpi-card-striking ${ind.en_valle ? 'kpi-card-red' : 'kpi-card-amber'}" style="grid-column: 3; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-stopwatch"></i> Tiempo Valle</h4>
              <div class="kpi-icon-circle">
                <i id="cal-icon-valle-${maquinaId}" class="fas ${ind.en_valle ? 'fa-exclamation-triangle' : 'fa-hourglass-half'}"></i>
              </div>
            </div>
            <div id="cal-kpi-valle-${maquinaId}" class="kpi-big-number">${ind.tiempo_valle_str}</div>
            <div class="kpi-card-subtext">
              <span id="cal-pill-valle-${maquinaId}" class="valle-pill ${ind.en_valle ? 'in-valle' : 'running'}" style="margin-right: 6px;">
                ${isShiftActive ? (ind.en_valle ? '⚠️ En Valle' : '⚡ Produciendo') : 'Sin Turno'}
              </span>
              Minutos en espera/valle
            </div>
            <div id="cal-desglose-valle-${maquinaId}">
              ${getCalandraDesgloseValleHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 4, Fila 1: Prendas / Hora -->
          <div class="kpi-card-striking kpi-card-purple" style="grid-column: 4; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tachometer-alt"></i> Prendas / Hora</h4>
              <div class="kpi-icon-circle"><i class="fas fa-bolt"></i></div>
            </div>
            <div id="cal-kpi-prendas-hora-${maquinaId}" class="kpi-big-number">${ind.prendas_hora_str}</div>
            <div class="kpi-card-subtext">Cadencia promedio horaria</div>
            <div id="cal-desglose-prendas-hora-${maquinaId}">
              ${getCalandraDesglosePrendasHoraHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 1, Fila 2: Kg / Hora (Estirada hacia abajo, idéntica a IKPROD) -->
          <div class="kpi-card-striking calandra-card-kg-hora" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div class="kpi-card-header">
                <h4 style="color: #f8fafc;"><i class="fas fa-balance-scale"></i> KG / HORA</h4>
                <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-chart-line"></i></div>
              </div>
              <div id="cal-kpi-kg-hora-${maquinaId}" class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${ind.kg_hora_str}</div>
              <div id="cal-desglose-kg-hora-${maquinaId}">
                ${getCalandraDesgloseKgHoraHtml(isCal2, ind)}
              </div>
            </div>

            <div>
              <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 6px; margin-top: 4px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                <span style="color: #818cf8;"><i class="fas fa-tachometer-alt"></i> Cadencia Turno</span>
                <span id="cal-cadencia-kg-hora-${maquinaId}" style="color: #38bdf8;">${ind.prendas_hora_str}</span>
              </div>
              <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
                <i class="fas fa-calculator"></i> Ritmo ponderado de kilogramos en tiempo productivo
              </div>
            </div>
          </div>

          <!-- Fila 2, Columnas 2 a 4: Gráfica de Producción y Tiempo Valle (Estrechada a la derecha de Kg/Hora) -->
          <div class="chart-section-card calandra-chart-section" style="grid-column: 2 / span 3; grid-row: 2;">
            <div class="chart-header-row" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
              <div class="chart-header-title">
                <i class="fas fa-chart-line" style="color: #38bdf8; font-size: 1.1rem;"></i>
                <h4 style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin: 0;">
                  Avance de Producción y Tiempo Valle Hora a Hora (${isCal2 ? 'Calandra 2' : 'Calandra 3'} - Turno Actual)
                </h4>
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span><span style="display:inline-block;width:10px;height:10px;background:#38bdf8;border-radius:2px;margin-right:4px;"></span><strong style="color: #38bdf8;">Prendas</strong> (Eje Izquierdo)</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#fbbf24;border-radius:2px;margin-right:4px;"></span><strong style="color: #fbbf24;">Tiempo Valle min</strong> (Eje Derecho)</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#b91c1c;border-radius:2px;margin-right:4px;"></span><strong style="color: #f87171;">Tiempo Descanso min</strong></span>
              </div>
            </div>
            <div class="chart-wrapper">
              <canvas id="chart-dashboard-${maquinaId.toLowerCase()}"></canvas>
            </div>
          </div>
        </div>
      `;
      container.innerHTML = html;
    } else {
      // Actualizaciones in-place sin parpadear ni re-crear canvas
      const shiftTitleEl = document.getElementById(`cal-shift-title-${maquinaId}`);
      if (shiftTitleEl) shiftTitleEl.innerHTML = `<i class="fas fa-user-clock"></i> ${turno.nombre} (${turno.horario})`;

      const shiftTimeEl = document.getElementById(`cal-shift-time-${maquinaId}`);
      if (shiftTimeEl) shiftTimeEl.innerHTML = `<i class="fas fa-calendar-alt"></i> ${turno.fecha || ''}`;

      const pesoBannerEl = document.getElementById(`cal-peso-banner-${maquinaId}`);
      if (pesoBannerEl) pesoBannerEl.textContent = getCalandraPesoBannerText(isCal2, ind);

      const cotejoWrapper = document.getElementById(`cal-cotejo-btn-wrapper-${maquinaId}`);
      if (cotejoWrapper) cotejoWrapper.innerHTML = getCalandraCotejoBtnHtml(maquinaId, data.comparacion_5002);

      const noShiftEl = document.getElementById(`cal-no-shift-alert-${maquinaId}`);
      if (noShiftEl) noShiftEl.style.display = isShiftActive ? 'none' : 'flex';

      const prendasEl = document.getElementById(`cal-kpi-prendas-${maquinaId}`);
      if (prendasEl) prendasEl.textContent = ind.prendas_totales_str;
      const desgPrendas = document.getElementById(`cal-desglose-prendas-${maquinaId}`);
      if (desgPrendas) desgPrendas.innerHTML = getCalandraDesglosePrendasHtml(isCal2, ind);

      const kgsEl = document.getElementById(`cal-kpi-kgs-${maquinaId}`);
      if (kgsEl) kgsEl.textContent = ind.kgs_totales_str;
      const desgKgs = document.getElementById(`cal-desglose-kgs-${maquinaId}`);
      if (desgKgs) desgKgs.innerHTML = getCalandraDesgloseKgsHtml(isCal2, ind);

      const cardValle = document.getElementById(`cal-card-valle-${maquinaId}`);
      if (cardValle) cardValle.className = `kpi-card-striking ${ind.en_valle ? 'kpi-card-red' : 'kpi-card-amber'}`;
      const iconValle = document.getElementById(`cal-icon-valle-${maquinaId}`);
      if (iconValle) iconValle.className = `fas ${ind.en_valle ? 'fa-exclamation-triangle' : 'fa-hourglass-half'}`;
      const valleEl = document.getElementById(`cal-kpi-valle-${maquinaId}`);
      if (valleEl) valleEl.textContent = ind.tiempo_valle_str;
      const pillValle = document.getElementById(`cal-pill-valle-${maquinaId}`);
      if (pillValle) {
        pillValle.className = `valle-pill ${ind.en_valle ? 'in-valle' : 'running'}`;
        pillValle.textContent = isShiftActive ? (ind.en_valle ? '⚠️ En Valle' : '⚡ Produciendo') : 'Sin Turno';
      }
      const desgValle = document.getElementById(`cal-desglose-valle-${maquinaId}`);
      if (desgValle) desgValle.innerHTML = getCalandraDesgloseValleHtml(isCal2, ind);

      const prendasHoraEl = document.getElementById(`cal-kpi-prendas-hora-${maquinaId}`);
      if (prendasHoraEl) prendasHoraEl.textContent = ind.prendas_hora_str;
      const desgPrendasHora = document.getElementById(`cal-desglose-prendas-hora-${maquinaId}`);
      if (desgPrendasHora) desgPrendasHora.innerHTML = getCalandraDesglosePrendasHoraHtml(isCal2, ind);

      const kgHoraEl = document.getElementById(`cal-kpi-kg-hora-${maquinaId}`);
      if (kgHoraEl) kgHoraEl.textContent = ind.kg_hora_str;
      const desgKgHora = document.getElementById(`cal-desglose-kg-hora-${maquinaId}`);
      if (desgKgHora) desgKgHora.innerHTML = getCalandraDesgloseKgHoraHtml(isCal2, ind);
      const cadenciaEl = document.getElementById(`cal-cadencia-kg-hora-${maquinaId}`);
      if (cadenciaEl) cadenciaEl.textContent = ind.prendas_hora_str;
    }

    // Renderizar / Actualizar gráfica dual axis
    renderCalandraHourlyChart(canvasId, ind, maquinaId);
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

async function loadTunelVTDashboard() {
  const container = document.getElementById('tunel-vt-dashboard-content');
  if (!container) return;

  try {
    const res = await fetch('/api/produccion/tunel-vt/dashboard');
    if (!res.ok) throw new Error(`Error ${res.status}: No se pudo cargar el dashboard de Túnel VT`);
    const data = await res.json();

    const ind = data.indicadores;
    const isShiftActive = data.is_turno_activo;
    const turno = data.turno_info;
    const de = ind.desglose_entradas || {};
    const canvasId = 'chart-dashboard-tunel-vt';
    const canvasExists = document.getElementById(canvasId);

    if (!canvasExists) {
      let html = `
        <!-- Banner de Turno -->
        <div class="shift-banner" style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
            <span id="vt-shift-title" class="shift-title"><i class="fas fa-user-clock"></i> ${turno.nombre} (${turno.horario})</span>
            <span id="vt-shift-time" class="shift-time"><i class="fas fa-calendar-alt"></i> ${turno.fecha || ''}</span>
            <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; font-size: 0.78rem; font-weight: 600; padding: 3px 8px; border-radius: 6px;">
              <i class="fas fa-broadcast-tower"></i> Fuente: MQTT Directo (datos_vt)
            </span>
          </div>
          <div>
            <button onclick="openPesoModalTunelVT()" class="btn-header" style="background: rgba(52, 211, 153, 0.15); border: 1px solid rgba(52, 211, 153, 0.4); color: #34d399; font-size: 0.82rem; font-weight: 700; cursor: pointer;">
              <i class="fas fa-weight-hanging"></i> Peso Unitario: <span id="vt-peso-unitario-banner">${ind.peso_unitario_str || '0,260 kg/u'}</span>
            </button>
          </div>
        </div>

        <!-- Alerta de Turno Inactivo -->
        <div id="vt-no-shift-alert" style="display: ${isShiftActive ? 'none' : 'flex'}; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(251, 191, 36, 0.4); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px; align-items: center; gap: 14px; color: #fbbf24;">
          <i class="fas fa-info-circle" style="font-size: 1.5rem;"></i>
          <div>
            <strong style="font-size: 1rem;">Sin Turno Activo en Curso:</strong> En este momento la planta no tiene un turno de producción en proceso. Todos los indicadores y la gráfica se presentan en cero hasta que comience el siguiente turno programado.
          </div>
        </div>

        <!-- Cuadrícula 4 Columnas x 2 Filas del Dashboard Túnel VT -->
        <div class="calandra-dashboard-grid-layout">
          <!-- Columna 1, Fila 1: Prendas Totales -->
          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 1; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tshirt"></i> Prendas Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-layer-group"></i></div>
            </div>
            <div id="vt-kpi-prendas" class="kpi-big-number">${ind.prendas_totales_str}</div>
            <div class="kpi-card-subtext">Acumulado 3 vías del turno en curso</div>
            <div id="vt-desglose-prendas" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 1">E1: ${de.entrada_1 || 0}</span>
              <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 2">E2: ${de.entrada_2 || 0}</span>
              <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 3">E3: ${de.entrada_3 || 0}</span>
            </div>
          </div>

          <!-- Columna 2, Fila 1: Kgs Totales -->
          <div class="kpi-card-striking kpi-card-green" style="grid-column: 2; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-weight-hanging"></i> Kgs Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-balance-scale-right"></i></div>
            </div>
            <div id="vt-kpi-kgs" class="kpi-big-number">${ind.kgs_totales_str}</div>
            <div class="kpi-card-subtext">Kilos calculados con peso unitario</div>
            <div id="vt-desglose-kgs" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kilos E1">E1: ${de.kg_e1_str || '0,0 kg'}</span>
              <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kilos E2">E2: ${de.kg_e2_str || '0,0 kg'}</span>
              <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kilos E3">E3: ${de.kg_e3_str || '0,0 kg'}</span>
            </div>
          </div>

          <!-- Columna 3, Fila 1: Tiempo Valle -->
          <div id="vt-card-valle" class="kpi-card-striking ${ind.en_valle ? 'kpi-card-red' : 'kpi-card-amber'}" style="grid-column: 3; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-stopwatch"></i> Tiempo Valle</h4>
              <div class="kpi-icon-circle">
                <i id="vt-icon-valle" class="fas ${ind.en_valle ? 'fa-exclamation-triangle' : 'fa-hourglass-half'}"></i>
              </div>
            </div>
            <div id="vt-kpi-valle" class="kpi-big-number">${ind.tiempo_valle_str}</div>
            <div class="kpi-card-subtext">
              <span id="vt-pill-valle" class="valle-pill ${ind.en_valle ? 'in-valle' : 'running'}" style="margin-right: 6px;">
                ${isShiftActive ? (ind.en_valle ? '⚠️ En Valle' : '⚡ Produciendo') : 'Sin Turno'}
              </span>
              Máximo tiempo valle registrado
            </div>
            <div id="vt-desglose-valle" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(251, 191, 36, 0.15); color: #fbbf24; border-color: rgba(251, 191, 36, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E1">E1: ${de.tiempo_valle_e1_str || '0,0 min'}</span>
              <span class="cal-badge-p" style="background: rgba(249, 115, 22, 0.15); color: #f97316; border-color: rgba(249, 115, 22, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E2">E2: ${de.tiempo_valle_e2_str || '0,0 min'}</span>
              <span class="cal-badge-g" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E3">E3: ${de.tiempo_valle_e3_str || '0,0 min'}</span>
            </div>
          </div>

          <!-- Columna 4, Fila 1: Prendas / Hora -->
          <div class="kpi-card-striking kpi-card-purple" style="grid-column: 4; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tachometer-alt"></i> Prendas / Hora</h4>
              <div class="kpi-icon-circle"><i class="fas fa-bolt"></i></div>
            </div>
            <div id="vt-kpi-prendas-hora" class="kpi-big-number">${ind.prendas_hora_str}</div>
            <div class="kpi-card-subtext">Cadencia combinada horaria</div>
            <div id="vt-desglose-prendas-hora" style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E1">E1: ${de.prendas_e1_hora_str || '0 p/h'}</span>
              <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E2">E2: ${de.prendas_e2_hora_str || '0 p/h'}</span>
              <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E3">E3: ${de.prendas_e3_hora_str || '0 p/h'}</span>
            </div>
          </div>

          <!-- Columna 1, Fila 2: Kg / Hora -->
          <div class="kpi-card-striking calandra-card-kg-hora" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div class="kpi-card-header">
                <h4 style="color: #f8fafc;"><i class="fas fa-balance-scale"></i> KG / HORA</h4>
                <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-chart-line"></i></div>
              </div>
              <div id="vt-kpi-kg-hora" class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${ind.kg_hora_str}</div>
              <div class="kpi-card-subtext" style="color: #94a3b8;">Ritmo ponderado por turno</div>
            </div>

            <div>
              <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 6px; margin-top: 4px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                <span style="color: #818cf8;"><i class="fas fa-tachometer-alt"></i> Cadencia Total</span>
                <span id="vt-cadencia-kg-hora" style="color: #38bdf8;">${ind.prendas_hora_str}</span>
              </div>
              <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
                <i class="fas fa-calculator"></i> Productividad ponderada en tiempo de oreado
              </div>
            </div>
          </div>

          <!-- Fila 2, Columnas 2 a 4: Gráfica de Producción y Tiempo Valle -->
          <div class="chart-section-card calandra-chart-section" style="grid-column: 2 / span 3; grid-row: 2;">
            <div class="chart-header-row" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
              <div class="chart-header-title">
                <i class="fas fa-chart-line" style="color: #38bdf8; font-size: 1.1rem;"></i>
                <h4 style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin: 0;">
                  Avance de Producción y Tiempo Valle Hora a Hora — Túnel VT (3 Vías)
                </h4>
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <span><span style="display:inline-block;width:10px;height:10px;background:#ffffff;border-radius:2px;margin-right:4px;"></span><strong style="color: #ffffff;">E1</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#34d399;border-radius:2px;margin-right:4px;"></span><strong style="color: #34d399;">E2</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#c084fc;border-radius:2px;margin-right:4px;"></span><strong style="color: #c084fc;">E3</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#fbbf24;border-radius:2px;margin-right:4px;"></span><strong style="color: #fbbf24;">Valle (min)</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#b91c1c;border-radius:2px;margin-right:4px;"></span><strong style="color: #f87171;">Descanso (min)</strong></span>
              </div>
            </div>
            <div class="chart-wrapper">
              <canvas id="chart-dashboard-tunel-vt"></canvas>
            </div>
          </div>
        </div>
      `;
      container.innerHTML = html;
    } else {
      // In-place updates sin parpadeo
      const shiftTitleEl = document.getElementById('vt-shift-title');
      if (shiftTitleEl) shiftTitleEl.innerHTML = `<i class="fas fa-user-clock"></i> ${turno.nombre} (${turno.horario})`;

      const shiftTimeEl = document.getElementById('vt-shift-time');
      if (shiftTimeEl) shiftTimeEl.innerHTML = `<i class="fas fa-calendar-alt"></i> ${turno.fecha || ''}`;

      const pesoBanner = document.getElementById('vt-peso-unitario-banner');
      if (pesoBanner) pesoBanner.textContent = ind.peso_unitario_str || '0,260 kg/u';

      const noShiftEl = document.getElementById('vt-no-shift-alert');
      if (noShiftEl) noShiftEl.style.display = isShiftActive ? 'none' : 'flex';

      const prendasEl = document.getElementById('vt-kpi-prendas');
      if (prendasEl) prendasEl.textContent = ind.prendas_totales_str;
      const desgPrendas = document.getElementById('vt-desglose-prendas');
      if (desgPrendas) {
        desgPrendas.innerHTML = `
          <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 1">E1: ${de.entrada_1 || 0}</span>
          <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 2">E2: ${de.entrada_2 || 0}</span>
          <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 3">E3: ${de.entrada_3 || 0}</span>
        `;
      }

      const kgsEl = document.getElementById('vt-kpi-kgs');
      if (kgsEl) kgsEl.textContent = ind.kgs_totales_str;
      const desgKgs = document.getElementById('vt-desglose-kgs');
      if (desgKgs) {
        desgKgs.innerHTML = `
          <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kilos E1">E1: ${de.kg_e1_str || '0,0 kg'}</span>
          <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kilos E2">E2: ${de.kg_e2_str || '0,0 kg'}</span>
          <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kilos E3">E3: ${de.kg_e3_str || '0,0 kg'}</span>
        `;
      }

      const cardValle = document.getElementById('vt-card-valle');
      if (cardValle) cardValle.className = `kpi-card-striking ${ind.en_valle ? 'kpi-card-red' : 'kpi-card-amber'}`;
      const iconValle = document.getElementById('vt-icon-valle');
      if (iconValle) iconValle.className = `fas ${ind.en_valle ? 'fa-exclamation-triangle' : 'fa-hourglass-half'}`;
      const valleEl = document.getElementById('vt-kpi-valle');
      if (valleEl) valleEl.textContent = ind.tiempo_valle_str;
      const pillValle = document.getElementById('vt-pill-valle');
      if (pillValle) {
        pillValle.className = `valle-pill ${ind.en_valle ? 'in-valle' : 'running'}`;
        pillValle.textContent = isShiftActive ? (ind.en_valle ? '⚠️ En Valle' : '⚡ Produciendo') : 'Sin Turno';
      }
      const desgValle = document.getElementById('vt-desglose-valle');
      if (desgValle) {
        desgValle.innerHTML = `
          <span class="cal-badge-g" style="background: rgba(251, 191, 36, 0.15); color: #fbbf24; border-color: rgba(251, 191, 36, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E1">E1: ${de.tiempo_valle_e1_str || '0,0 min'}</span>
          <span class="cal-badge-p" style="background: rgba(249, 115, 22, 0.15); color: #f97316; border-color: rgba(249, 115, 22, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E2">E2: ${de.tiempo_valle_e2_str || '0,0 min'}</span>
          <span class="cal-badge-g" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E3">E3: ${de.tiempo_valle_e3_str || '0,0 min'}</span>
        `;
      }

      const prendasHoraEl = document.getElementById('vt-kpi-prendas-hora');
      if (prendasHoraEl) prendasHoraEl.textContent = ind.prendas_hora_str;
      const desgPrendasHora = document.getElementById('vt-desglose-prendas-hora');
      if (desgPrendasHora) {
        desgPrendasHora.innerHTML = `
          <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E1">E1: ${de.prendas_e1_hora_str || '0 p/h'}</span>
          <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E2">E2: ${de.prendas_e2_hora_str || '0 p/h'}</span>
          <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E3">E3: ${de.prendas_e3_hora_str || '0 p/h'}</span>
        `;
      }

      const kgHoraEl = document.getElementById('vt-kpi-kg-hora');
      if (kgHoraEl) kgHoraEl.textContent = ind.kg_hora_str;
      const cadenciaEl = document.getElementById('vt-cadencia-kg-hora');
      if (cadenciaEl) cadenciaEl.textContent = ind.prendas_hora_str;
    }

    renderTunelVTHourlyChart(canvasId, ind);
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

async function openPesoModalCalandra(maquinaId) {
  const isCal2 = (maquinaId === 'CALANDRA_2');
  const modalId = isCal2 ? 'modal-peso-calandra2' : 'modal-peso-calandra3';
  const modal = document.getElementById(modalId);
  const msg = document.getElementById(isCal2 ? 'peso-cal2-msg' : 'peso-cal3-msg');
  if (msg) msg.style.display = 'none';

  try {
    const res = await fetch(`/api/produccion/calandras/${maquinaId}/peso-unitario`);
    if (res.ok) {
      const data = await res.json();
      if (isCal2) {
        const inpPeq = document.getElementById('input-peso-cal2-peq');
        const inpGra = document.getElementById('input-peso-cal2-gra');
        if (inpPeq) inpPeq.value = data.peso_pequenas_gr || Math.round((data.peso_pequenas || 0.470) * 1000);
        if (inpGra) inpGra.value = data.peso_grandes_gr || Math.round((data.peso_grandes || 0.780) * 1000);
      } else {
        const inpUni = document.getElementById('input-peso-cal3-uni');
        if (inpUni) inpUni.value = data.peso_unitario_gr || Math.round((data.peso_unitario || 1.180) * 1000);
      }
    }
  } catch (e) {
    if (isCal2) {
      const inpPeq = document.getElementById('input-peso-cal2-peq');
      const inpGra = document.getElementById('input-peso-cal2-gra');
      if (inpPeq) inpPeq.value = 470;
      if (inpGra) inpGra.value = 780;
    } else {
      const inpUni = document.getElementById('input-peso-cal3-uni');
      if (inpUni) inpUni.value = 1180;
    }
  }

  if (modal) {
    modal.classList.add('active');
    modal.style.setProperty('display', 'flex', 'important');
    modal.style.setProperty('opacity', '1', 'important');
    modal.style.setProperty('visibility', 'visible', 'important');
    modal.style.setProperty('pointer-events', 'auto', 'important');
    modal.style.setProperty('z-index', '999999', 'important');
  }
}

function closePesoModalCalandra(maquinaId) {
  const isCal2 = (maquinaId === 'CALANDRA_2');
  const modalId = isCal2 ? 'modal-peso-calandra2' : 'modal-peso-calandra3';
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
    modal.style.setProperty('display', 'none', 'important');
    modal.style.setProperty('opacity', '0', 'important');
    modal.style.setProperty('visibility', 'hidden', 'important');
    modal.style.setProperty('pointer-events', 'none', 'important');
  }
}

async function savePesoCalandra2() {
  const inpPeq = document.getElementById('input-peso-cal2-peq');
  const inpGra = document.getElementById('input-peso-cal2-gra');
  const msg = document.getElementById('peso-cal2-msg');
  if (!inpPeq || !inpGra) return;

  const valPeq = parseFloat(inpPeq.value);
  const valGra = parseFloat(inpGra.value);

  if (isNaN(valPeq) || valPeq <= 0 || isNaN(valGra) || valGra <= 0) {
    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(239, 68, 68, 0.2)';
      msg.style.color = '#f87171';
      msg.textContent = 'Por favor introduzca pesos válidos mayores a 0.';
    }
    return;
  }

  try {
    const res = await fetch('/api/produccion/calandras/CALANDRA_2/peso-unitario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        weight_pequenas_g: valPeq,
        weight_grandes_g: valGra
      })
    });
    if (!res.ok) throw new Error('Error al guardar pesos de Calandra 2');
    const data = await res.json();

    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(16, 185, 129, 0.2)';
      msg.style.color = '#34d399';
      msg.textContent = `✅ Pesos actualizados: Pequeñas ${data.peso_pequenas_gr} gr (${data.peso_pequenas} kg) | Grandes ${data.peso_grandes_gr} gr (${data.peso_grandes} kg).`;
    }

    setTimeout(() => {
      closePesoModalCalandra('CALANDRA_2');
      loadCalandraDashboard('CALANDRA_2');
      const currentHash = window.location.hash.replace('#', '') || 'inicio';
      if (currentHash === 'produccion') loadProduccionData();
    }, 800);
  } catch (err) {
    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(239, 68, 68, 0.2)';
      msg.style.color = '#f87171';
      msg.textContent = `Error: ${err.message}`;
    }
  }
}

async function savePesoCalandra3() {
  const inpUni = document.getElementById('input-peso-cal3-uni');
  const msg = document.getElementById('peso-cal3-msg');
  if (!inpUni) return;

  const valUni = parseFloat(inpUni.value);

  if (isNaN(valUni) || valUni <= 0) {
    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(239, 68, 68, 0.2)';
      msg.style.color = '#f87171';
      msg.textContent = 'Por favor introduzca un peso válido mayor a 0.';
    }
    return;
  }

  try {
    const res = await fetch('/api/produccion/calandras/CALANDRA_3/peso-unitario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        weight_g: valUni
      })
    });
    if (!res.ok) throw new Error('Error al guardar peso de Calandra 3');
    const data = await res.json();

    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(16, 185, 129, 0.2)';
      msg.style.color = '#34d399';
      msg.textContent = `✅ Peso unitario actualizado a ${data.peso_unitario} kg (${data.peso_unitario_gr} gr).`;
    }

    setTimeout(() => {
      closePesoModalCalandra('CALANDRA_3');
      loadCalandraDashboard('CALANDRA_3');
      const currentHash = window.location.hash.replace('#', '') || 'inicio';
      if (currentHash === 'produccion') loadProduccionData();
    }, 800);
  } catch (err) {
    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(239, 68, 68, 0.2)';
      msg.style.color = '#f87171';
      msg.textContent = `Error: ${err.message}`;
    }
  }
}

window.openPesoModalCalandra = openPesoModalCalandra;
window.closePesoModalCalandra = closePesoModalCalandra;
window.savePesoCalandra2 = savePesoCalandra2;
window.savePesoCalandra3 = savePesoCalandra3;

async function openPesoModalTunelVT() {
  const modal = document.getElementById('modal-peso-vt');
  const input = document.getElementById('input-peso-vt');
  const msg = document.getElementById('peso-vt-msg');
  if (msg) msg.style.display = 'none';

  try {
    const res = await fetch('/api/produccion/tunel-vt/peso-unitario');
    if (res.ok) {
      const data = await res.json();
      if (input) input.value = data.peso_unitario_gr || Math.round((data.peso_unitario || 0.260) * 1000);
    }
  } catch (e) {
    if (input) input.value = 260;
  }

  if (modal) {
    modal.classList.add('active');
    modal.style.setProperty('display', 'flex', 'important');
    modal.style.setProperty('opacity', '1', 'important');
    modal.style.setProperty('visibility', 'visible', 'important');
    modal.style.setProperty('pointer-events', 'auto', 'important');
    modal.style.setProperty('z-index', '999999', 'important');
  }
}

function closePesoModalTunelVT() {
  const modal = document.getElementById('modal-peso-vt');
  if (modal) {
    modal.classList.remove('active');
    modal.style.setProperty('display', 'none', 'important');
    modal.style.setProperty('opacity', '0', 'important');
    modal.style.setProperty('visibility', 'hidden', 'important');
    modal.style.setProperty('pointer-events', 'none', 'important');
  }
}

async function savePesoTunelVT() {
  const input = document.getElementById('input-peso-vt');
  const msg = document.getElementById('peso-vt-msg');
  if (!input) return;

  const val = parseFloat(input.value);
  if (isNaN(val) || val <= 0) {
    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(239, 68, 68, 0.2)';
      msg.style.color = '#f87171';
      msg.textContent = 'Por favor introduzca un peso válido mayor a 0.';
    }
    return;
  }

  try {
    const res = await fetch('/api/produccion/tunel-vt/peso-unitario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ weight_g: val })
    });
    if (!res.ok) throw new Error('Error al guardar peso unitario');
    const data = await res.json();

    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(16, 185, 129, 0.2)';
      msg.style.color = '#34d399';
      msg.textContent = `✅ Peso unitario actualizado a ${data.peso_unitario} kg (${data.peso_unitario_gr} gr).`;
    }

    setTimeout(() => {
      closePesoModalTunelVT();
      loadTunelVTDashboard();
      const currentHash = window.location.hash.replace('#', '') || 'inicio';
      if (currentHash === 'produccion') loadProduccionData();
    }, 800);
  } catch (err) {
    if (msg) {
      msg.style.display = 'block';
      msg.style.background = 'rgba(239, 68, 68, 0.2)';
      msg.style.color = '#f87171';
      msg.textContent = `Error: ${err.message}`;
    }
  }
}

window.loadTunelVTDashboard = loadTunelVTDashboard;
window.openPesoModalTunelVT = openPesoModalTunelVT;
window.closePesoModalTunelVT = closePesoModalTunelVT;
window.savePesoTunelVT = savePesoTunelVT;

async function openModalComparar5002(maquinaId) {
  const modal = document.getElementById('modal-comparar-5002');
  const title = document.getElementById('modal-comparar-title');
  const body = document.getElementById('modal-comparar-body');
  if (!modal || !body) return;

  const isCal2 = (maquinaId === 'CALANDRA_2');
  const maqName = isCal2 ? 'Calandra 2' : 'Calandra 3';
  title.innerHTML = `<i class="fas fa-balance-scale"></i> Verificación Temporal: MQTT vs Puerto 5002 — ${maqName}`;
  body.innerHTML = `
    <div style="text-align: center; padding: 30px; color: var(--text-muted);">
      <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: #38bdf8; margin-bottom: 15px;"></i>
      <p>Consultando API del Puerto 5002 y contrastando con la base de datos local MQTT...</p>
    </div>
  `;
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/api/produccion/calandras/${maquinaId}/comparar-5002`);
    if (!res.ok) throw new Error(`Error ${res.status}: No se pudo obtener la comparativa`);
    const data = await res.json();

    if (!data.disponible_5002) {
      body.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 18px; color: #f87171;">
          <h4 style="margin: 0 0 10px 0;"><i class="fas fa-exclamation-circle"></i> Puerto 5002 No Disponible</h4>
          <p style="margin: 0; font-size: 0.9rem;">${data.motivo || 'No se pudo establecer conexión con http://100.127.85.111:5002'}</p>
          <p style="margin: 10px 0 0 0; font-size: 0.85rem; color: var(--text-muted);">Nota: La aplicación continúa funcionando al 100% calculando todos los indicadores directamente desde el tópico MQTT.</p>
        </div>
      `;
      return;
    }

    const resm = data.resumen || {};
    const exact = data.coincidencia_exacta;

    let html = `
      <!-- Tarjetas de Resumen Comparativo -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
        <div style="background: var(--bg-hover); border-radius: 12px; padding: 15px; border-left: 4px solid #38bdf8;">
          <div style="color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase;">Prendas Totales</div>
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 5px;">
            <div>
              <span style="font-size: 1.3rem; font-weight: 700; color: #38bdf8;">${resm.prendas_mqtt}</span> <small style="color: var(--text-muted)">MQTT</small>
            </div>
            <div>
              <span style="font-size: 1.3rem; font-weight: 700; color: #94a3b8;">${resm.prendas_5002}</span> <small style="color: var(--text-muted)">5002</small>
            </div>
          </div>
          <div style="font-size: 0.8rem; margin-top: 6px; color: ${resm.diff_prendas === 0 ? '#34d399' : '#fbbf24'};">
            ${resm.diff_prendas === 0 ? '<i class="fas fa-check-circle"></i> Diferencia: 0 prendas' : `<i class="fas fa-info-circle"></i> Diferencia: ${resm.diff_prendas} prendas`}
          </div>
        </div>

        <div style="background: var(--bg-hover); border-radius: 12px; padding: 15px; border-left: 4px solid #f59e0b;">
          <div style="color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase;">Tiempo Valle Total</div>
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 5px;">
            <div>
              <span style="font-size: 1.3rem; font-weight: 700; color: #f59e0b;">${resm.valle_mqtt_min}</span> <small style="color: var(--text-muted)">min MQTT</small>
            </div>
            <div>
              <span style="font-size: 1.3rem; font-weight: 700; color: #94a3b8;">${resm.valle_5002_min}</span> <small style="color: var(--text-muted)">min 5002</small>
            </div>
          </div>
          <div style="font-size: 0.8rem; margin-top: 6px; color: ${Math.abs(resm.diff_valle_min) <= 0.3 ? '#34d399' : '#fbbf24'};">
            ${Math.abs(resm.diff_valle_min) <= 0.3 ? '<i class="fas fa-check-circle"></i> Coincidencia exacta' : `<i class="fas fa-info-circle"></i> Diferencia: ${resm.diff_valle_min} min`}
          </div>
        </div>

        <div style="background: var(--bg-hover); border-radius: 12px; padding: 15px; border-left: 4px solid ${exact ? '#10b981' : '#f59e0b'};">
          <div style="color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase;">Diagnóstico General</div>
          <div style="font-size: 1.05rem; font-weight: 700; margin-top: 5px; color: ${exact ? '#34d399' : '#fbbf24'};">
            ${exact ? '<i class="fas fa-check-double"></i> 100% Coincidente' : '<i class="fas fa-check-circle"></i> Cálculos Consistentes'}
          </div>
          <div style="font-size: 0.78rem; margin-top: 6px; color: var(--text-muted);">
            Hora de cotejo: ${data.timestamp_comparacion}
          </div>
        </div>
      </div>

      <!-- Tabla Detallada Franja a Franja -->
      <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem; text-align: left;">
          <thead>
            <tr style="border-bottom: 2px solid var(--border-color); color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase;">
              <th style="padding: 10px 12px;">Franja Horaria</th>
              <th style="padding: 10px 12px; text-align: right;">Prendas MQTT</th>
              <th style="padding: 10px 12px; text-align: right;">Prendas 5002</th>
              <th style="padding: 10px 12px; text-align: right;">Valle MQTT</th>
              <th style="padding: 10px 12px; text-align: right;">Valle 5002</th>
              <th style="padding: 10px 12px; text-align: center;">Cotejo</th>
            </tr>
          </thead>
          <tbody>
            ${(data.filas_comparacion || []).map(row => {
              const rowOk = row.ok_prendas && row.ok_valle;
              return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.06); background: ${rowOk ? 'transparent' : 'rgba(245, 158, 11, 0.05)'};">
                  <td style="padding: 10px 12px; font-weight: 600; color: var(--text-main);">${row.franja}</td>
                  <td style="padding: 10px 12px; text-align: right; color: #38bdf8; font-weight: 600;">${row.prendas_mqtt}</td>
                  <td style="padding: 10px 12px; text-align: right; color: #94a3b8;">${row.prendas_5002}</td>
                  <td style="padding: 10px 12px; text-align: right; color: #f59e0b; font-weight: 600;">${row.valle_mqtt}m</td>
                  <td style="padding: 10px 12px; text-align: right; color: #94a3b8;">${row.valle_5002}m</td>
                  <td style="padding: 10px 12px; text-align: center;">
                    ${rowOk 
                      ? '<span style="color: #34d399; font-weight: 600;"><i class="fas fa-check-circle"></i> Exacto</span>' 
                      : `<span style="color: #fbbf24; font-size: 0.78rem;">${row.diff_prendas !== 0 ? `ΔP:${row.diff_prendas}` : ''} ${row.diff_valle !== 0 ? `ΔV:${row.diff_valle}m` : ''}</span>`
                    }
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    `;

    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `
      <div style="color: var(--accent-red); padding: 20px;">
        <i class="fas fa-exclamation-triangle"></i> Error al ejecutar cotejo: ${err.message}
      </div>
    `;
  }
}

function closeModalComparar5002() {
  const modal = document.getElementById('modal-comparar-5002');
  if (modal) modal.style.display = 'none';
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
  const isGas = (id.includes('gas') || id.includes('calandra') || id.includes('caldera') || id.includes('secad') || varCode.includes('gas') || varCode.includes('calandra') || varCode.includes('caldera') || varCode.includes('Secado') || varCode.includes('secad'));
  const tableHeaders = isElectric
    ? `<tr>
        <th>Timestamp</th>
        <th style="color: #38bdf8;">Corriente Acumulada (Ah)</th>
        <th style="color: #16a34a;">Potencia Acumulada (${unidad})</th>
        <th style="color: #fbbf24;">Delta de Potencia (${unidad})</th>
        <th>Dispositivo</th>
       </tr>`
    : (isGas
      ? `<tr>
          <th>Timestamp ISO</th>
          <th>Pulsos (Count)</th>
          <th>Volumen (${unidad})</th>
          <th style="color: #16a34a;">Potencia (kWh)</th>
          <th style="color: #38bdf8;">Delta (m³)</th>
          <th>Caudal (m³/h)</th>
          <th>Dispositivo / Fuente</th>
         </tr>`
      : `<tr>
          <th>Timestamp ISO</th>
          <th>Pulsos (Count)</th>
          <th>Volumen (${unidad})</th>
          <th>Caudal (m³/h)</th>
          <th>Dispositivo / Fuente</th>
         </tr>`);
  const initialColspan = isElectric ? 5 : (isGas ? 7 : 5);

  return `
    <div class="metric-card clickable-card" onclick="toggleProcesoPanel('${id}', '${varCode}', '${titulo.replace(/'/g, "\\'")}', '${unidad}')" style="cursor: pointer;" title="Haz clic para expandir o colapsar la telemetría">
      <div class="metric-icon ${colorStyle}"><i class="fas ${iconClass}"></i></div>
      <div class="metric-info" style="width: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <h4>${titulo}</h4>
          <span id="badge-${id}" class="card-link-badge" style="font-size: 0.68rem; padding: 2px 6px;">🔍 Ver Telemetría</span>
        </div>
        <div id="metric-val-${id}" class="metric-value">${mainMetricValue}</div>
        <small id="metric-sub-${id}" style="color: var(--text-muted)">${subtext}</small>
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
      <style>
        .filter-date-input {
          background-color: #0f172a !important;
          color: #ffffff !important;
          border: 1px solid rgba(255, 255, 255, 0.18) !important;
          border-radius: 6px !important;
          font-weight: 600 !important;
          box-sizing: border-box !important;
        }
        .filter-date-input::-webkit-calendar-picker-indicator {
          background-color: #ffffff;
          border-radius: 4px;
          padding: 2px 4px;
          cursor: pointer;
          opacity: 0.95;
          filter: none;
        }
        .filter-date-input::-webkit-calendar-picker-indicator:hover {
          background-color: #38bdf8;
          opacity: 1;
        }
      </style>
      <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid var(--border-color); padding: 14px 16px; border-radius: 12px; margin-bottom: 20px;">
        <div style="font-size: 0.8rem; font-weight: 700; color: #38bdf8; text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
          <i class="fas fa-filter"></i> Filtro de Acumulado por Rango de Fecha y Hora
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end;">
          <div style="flex: 1 1 120px; min-width: 115px; max-width: 140px;">
            <label style="font-size: 0.72rem; color: #94a3b8; display: block; margin-bottom: 4px; font-weight: 600;">Fecha Inicio:</label>
            <input type="date" id="filter-fecha-inicio-${id}" class="form-control filter-date-input" style="font-size: 0.82rem; padding: 5px 8px; height: 35px; width: 100%;">
          </div>
          <div style="flex: 0 1 80px; min-width: 75px; max-width: 90px;">
            <label style="font-size: 0.72rem; color: #94a3b8; display: block; margin-bottom: 4px; font-weight: 600;">Hora Inicio:</label>
            <input type="time" id="filter-hora-inicio-${id}" value="00:00" class="form-control filter-date-input" style="font-size: 0.82rem; padding: 5px 6px; height: 35px; width: 100%; text-align: center;">
          </div>
          <div style="flex: 1 1 120px; min-width: 115px; max-width: 140px;">
            <label style="font-size: 0.72rem; color: #94a3b8; display: block; margin-bottom: 4px; font-weight: 600;">Fecha Fin:</label>
            <input type="date" id="filter-fecha-fin-${id}" class="form-control filter-date-input" style="font-size: 0.82rem; padding: 5px 8px; height: 35px; width: 100%;">
          </div>
          <div style="flex: 0 1 80px; min-width: 75px; max-width: 90px;">
            <label style="font-size: 0.72rem; color: #94a3b8; display: block; margin-bottom: 4px; font-weight: 600;">Hora Fin:</label>
            <input type="time" id="filter-hora-fin-${id}" value="23:59" class="form-control filter-date-input" style="font-size: 0.82rem; padding: 5px 6px; height: 35px; width: 100%; text-align: center;">
          </div>
          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: nowrap; flex: 0 0 auto;">
            <button type="button" onclick="applyProcesoFilter('${id}', '${varCode}', '${unidad}')" class="btn-primary" style="padding: 7px 13px; font-size: 0.82rem; height: 35px; white-space: nowrap; border-radius: 7px; display: inline-flex; align-items: center; gap: 6px; font-weight: 700; cursor: pointer; border: none;"><i class="fas fa-filter"></i> Aplicar Filtro</button>
            <button type="button" onclick="openProcesoGraficaView('${id}', '${varCode}', '${titulo.replace(/'/g, "\\'")}', '${unidad}')" class="btn-success" style="padding: 7px 13px; font-size: 0.82rem; height: 35px; white-space: nowrap; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; border: none; border-radius: 7px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;"><i class="fas fa-chart-bar"></i> Ver gráfica</button>
          </div>
        </div>
      </div>

      <!-- Tarjeta Acumulador Principal -->
      <div style="background: ${isElectric ? 'linear-gradient(135deg, #1e3a8a 0%, #0369a1 60%, #0f172a 100%)' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 60%, #0f172a 100%)'}; border: 1px solid ${isElectric ? '#fbbf24' : '#38bdf8'}; border-radius: 14px; padding: 20px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(2, 132, 199, 0.3);">
        <div>
          <div style="font-size: 0.8rem; font-weight: 800; color: #e0f2fe; text-transform: uppercase; letter-spacing: 0.8px;">${isElectric ? '⚡ Potencia Activa y Potencia Aparente del Rango Escogido' : `⚡ Acumulador Principal de Telemetría (${unidad})`}</div>
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
          'Agua (General)',
          'm³',
          'fa-water',
          'blue',
          'Sin Servicio',
          'Sensor en verificación'
        )}

        ${(() => {
          const m3Val = g.gas_general?.consumo_hoy_m3 || 0;
          const kwhVal = g.gas_general?.consumo_hoy_kwh || Math.round(m3Val * 11.68);
          return renderProcesoCardAndPanel(
            'gas_general',
            'sensor_gas_general',
            (g.gas_general?.titulo && g.gas_general.titulo.includes('Hoy')) ? g.gas_general.titulo : 'Gas General Hoy',
            'm³',
            'fa-fire',
            'amber',
            `${m3Val} m³ <span style="font-size: inherit; font-weight: inherit; color: #16a34a;">| ${kwhVal.toLocaleString('es-ES')} kWh</span>`,
            `Caudal: ${g.gas_general?.caudal_m3h || 0} m³/h | Temp: ${g.gas_general?.temperatura_c || 25}°C`
          );
        })()}

        ${(() => {
          const eg = g.energia_electrica || {};
          const kwhHoy = eg.consumo_hoy_kwh !== undefined ? eg.consumo_hoy_kwh : 0;
          const pKw = eg.potencia_kw !== undefined ? eg.potencia_kw : (eg.potencia_activa_kw || 0);
          const iMax = eg.corriente_max_a !== undefined ? eg.corriente_max_a : 0;
          const iCurr = eg.corriente_actual_a !== undefined ? eg.corriente_actual_a : 0;
          return renderProcesoCardAndPanel(
            'energia_electrica',
            'I_general',
            eg.titulo || 'Energía Eléctrica General',
            'kWh',
            'fa-bolt',
            'amber',
            `Hoy: ${kwhHoy} kWh <span style="font-size: inherit; font-weight: inherit; color: #fbbf24;">| ${pKw} kW</span>`,
            `Corriente Máx Hoy: ${iMax} A | I. Actual: ${iCurr} A`
          );
        })()}
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
          'Agua Túnel y Lavadoras Hoy',
          'm³',
          'fa-shower',
          'blue',
          `${agua.agua_tunel_lavadoras?.consumo_hoy_m3 !== undefined ? agua.agua_tunel_lavadoras.consumo_hoy_m3 : 0} m³`,
          `Caudal: ${agua.agua_tunel_lavadoras?.caudal_m3h !== undefined ? agua.agua_tunel_lavadoras.caudal_m3h : 0} m³/h`
        )}
      </div>

      <!-- Sección 3: Desglose de Gas por Proceso / Máquina -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>🔥 Consumos de Gas por Proceso / Máquina</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid" style="margin-bottom: 28px;">
        ${(() => {
          const renderGasCard = (id, varCode, fallbackTitle, item, icon, tempLabel) => {
            const m3Val = item?.consumo_hoy_m3 !== undefined ? item.consumo_hoy_m3 : 0;
            const kwhVal = item?.consumo_hoy_kwh !== undefined ? item.consumo_hoy_kwh : Math.round(m3Val * 11.68);
            const caudal = item?.consumo_m3h !== undefined ? item.consumo_m3h : (item?.caudal_1h_m3h || 0);
            const tempVal = item?.temp_secado_c !== undefined ? item.temp_secado_c : (item?.temp_trabajo_c !== undefined ? item.temp_trabajo_c : (item?.temperatura || 0));
            const cardTitle = (item?.titulo && item.titulo.includes('Hoy')) ? item.titulo : `${item?.titulo || fallbackTitle} Hoy`;
            return renderProcesoCardAndPanel(
              id,
              varCode,
              cardTitle,
              'm³',
              icon,
              'amber',
              `${m3Val} m³ <span style="font-size: inherit; font-weight: inherit; color: #16a34a;">| ${kwhVal.toLocaleString('es-ES')} kWh</span>`,
              tempLabel ? `Caudal: ${caudal} m³/h | ${tempLabel}: ${tempVal}°C` : `Caudal: ${caudal} m³/h`
            );
          };

          return `
            ${renderGasCard('gas_tunel_vt', 'Túnel de Secado VT', 'Gas Túnel VT', gas.gas_tunel_vt, 'fa-wind', 'Temp Secado')}
            ${renderGasCard('gas_calandra_1', 'calandra1_IoT', 'Gas Calandra 1', gas.gas_calandra_1, 'fa-scroll', null)}
            ${renderGasCard('gas_calandra_2', 'Calandra 2', 'Gas Calandra 2', gas.gas_calandra_2, 'fa-scroll', null)}
            ${renderGasCard('gas_calandra_3', 'Calandra 3', 'Gas Calandra 3', gas.gas_calandra_3, 'fa-scroll', null)}
            ${renderGasCard('gas_caldera_1', 'caldera1', 'Gas Caldera 1', gas.gas_caldera_1, 'fa-fire-burner', 'Temp Trabajo')}
            ${renderGasCard('gas_caldera_2', 'caldera2', 'Gas Caldera 2', gas.gas_caldera_2, 'fa-fire-burner', 'Temp Trabajo')}
            ${renderGasCard('gas_secadoras_man', 'secadoras_man', 'Gas Secadoras Manuales', gas.gas_secadoras_man, 'fa-hands', 'Temp Trabajo')}
            ${renderGasCard('gas_secadoras_aut', 'secadoras_aut', 'Gas Secadoras Automáticas', gas.gas_secadoras_aut, 'fa-robot', 'Temp Calculada')}
          `;
        })()}
      </div>

      <!-- Sección 4: Desglose de Electricidad por Proceso / Máquina -->
      <div class="section-subtitle-bar" style="margin-bottom: 14px;">
        <h4>⚡ Consumos de Electricidad por Proceso / Máquina</h4>
        <div class="subtitle-line"></div>
      </div>
      <div class="metrics-grid">
        ${(() => {
          const renderElecCard = (id, varCode, fallbackTitle, item, icon) => {
            const kwhHoy = item?.consumo_hoy_kwh !== undefined ? item.consumo_hoy_kwh : 0;
            const pKw = item?.potencia_kw !== undefined ? item.potencia_kw : (item?.potencia_activa_kw || 0);
            const iMax = item?.corriente_max_a !== undefined ? item.corriente_max_a : 0;
            const iCurr = item?.corriente_actual_a !== undefined ? item.corriente_actual_a : 0;
            const cardTitle = item?.titulo || fallbackTitle;
            return renderProcesoCardAndPanel(
              id,
              varCode,
              cardTitle,
              'kWh',
              icon,
              'amber',
              `Hoy: ${kwhHoy} kWh <span style="font-size: inherit; font-weight: inherit; color: #fbbf24;">| ${pKw} kW</span>`,
              `Corriente Máx Hoy: ${iMax} A | I. Actual: ${iCurr} A`
            );
          };

          return `
            ${renderElecCard('elec_tunel', 'I_motor_tunel', 'Electricidad Túnel', elec.elec_tunel, 'fa-circle-notch')}
            ${renderElecCard('elec_calandra_1', 'I_bomba_calandra1', 'Electricidad Calandra 1', elec.elec_calandra_1, 'fa-scroll')}
            ${renderElecCard('elec_calandra_2', 'Bomba_calandra2', 'Electricidad Calandra 2', elec.elec_calandra_2, 'fa-scroll')}
            ${renderElecCard('elec_calandra_3', 'I_bomba_calandra3', 'Electricidad Calandra 3', elec.elec_calandra_3, 'fa-scroll')}
            ${renderElecCard('elec_prensa_tunel', 'I_prensa_tunel', 'Electricidad Prensa Túnel', elec.elec_prensa_tunel, 'fa-compress-arrows-alt')}
          `;
        })()}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">⚠️ ${err.message}</div>`;
  }
}

let consumosPollingInterval = null;

async function updateConsumosRealtime() {
  if (window.location.hash !== '#consumos') {
    if (consumosPollingInterval) {
      clearInterval(consumosPollingInterval);
      consumosPollingInterval = null;
    }
    return;
  }
  try {
    const res = await fetch('/api/consumos/summary');
    if (!res.ok) return;
    const data = await res.json();
    const g = data.generales || {};
    const gas = data.desglose_gas || {};
    const agua = data.desglose_agua || {};
    const elec = data.desglose_electricidad || {};

    const setCard = (id, mainVal, subVal) => {
      const valEl = document.getElementById(`metric-val-${id}`);
      const subEl = document.getElementById(`metric-sub-${id}`);
      if (valEl && mainVal !== undefined) valEl.innerHTML = mainVal;
      if (subEl && subVal !== undefined) subEl.textContent = subVal;
    };

    if (g.gas_general) {
      const m3Hoy = g.gas_general.consumo_hoy_m3 !== undefined ? g.gas_general.consumo_hoy_m3 : 0;
      const kwhHoy = g.gas_general.consumo_hoy_kwh !== undefined ? g.gas_general.consumo_hoy_kwh : Math.round(m3Hoy * 11.68);
      const caudalVal = g.gas_general.caudal_m3h !== undefined ? g.gas_general.caudal_m3h : (g.gas_general.consumo_m3h || 0);
      const tempVal = g.gas_general.temperatura_c !== undefined ? g.gas_general.temperatura_c : 21;
      setCard('gas_general', valHtml, `Caudal: ${caudalVal} m³/h | Temp: ${tempVal}°C`);
    }
    if (g.agua_general) {
      setCard('agua_general', 'Sin Servicio', 'Sensor en verificación');
    }
    if (agua.agua_tunel_lavadoras) {
      const at = agua.agua_tunel_lavadoras;
      const m3Hoy = at.consumo_hoy_m3 !== undefined ? at.consumo_hoy_m3 : 0;
      const caudal = at.caudal_m3h !== undefined ? at.caudal_m3h : 0;
      setCard('agua_tunel_lavadoras', `${m3Hoy} m³`, `Caudal: ${caudal} m³/h`);
    }
    if (g.energia_electrica) {
      const kwh = g.energia_electrica.consumo_hoy_kwh !== undefined ? g.energia_electrica.consumo_hoy_kwh : 0;
      const pKw = g.energia_electrica.potencia_kw !== undefined ? g.energia_electrica.potencia_kw : (g.energia_electrica.potencia_activa_kw || 0);
      const mainVal = `Hoy: ${kwh} kWh <span style="font-size: inherit; font-weight: inherit; color: #fbbf24;">| ${pKw} kW</span>`;
      const subVal = `Corriente Máx Hoy: ${g.energia_electrica.corriente_max_a || 0} A | I. Actual: ${g.energia_electrica.corriente_actual_a || 0} A`;
      setCard('energia_electrica', mainVal, subVal);
    }

    const setElecCard = (key, item) => {
      if (!item) return;
      const kwh = item.consumo_hoy_kwh !== undefined ? item.consumo_hoy_kwh : 0;
      const pKw = item.potencia_kw !== undefined ? item.potencia_kw : (item.potencia_activa_kw || 0);
      const mainVal = `Hoy: ${kwh} kWh <span style="font-size: inherit; font-weight: inherit; color: #fbbf24;">| ${pKw} kW</span>`;
      const subVal = `Corriente Máx Hoy: ${item.corriente_max_a || 0} A | I. Actual: ${item.corriente_actual_a || 0} A`;
      setCard(key, mainVal, subVal);
    };

    setElecCard('elec_tunel', elec.elec_tunel);
    setElecCard('elec_calandra_1', elec.elec_calandra_1);
    setElecCard('elec_calandra_2', elec.elec_calandra_2);
    setElecCard('elec_calandra_3', elec.elec_calandra_3);
    setElecCard('elec_prensa_tunel', elec.elec_prensa_tunel);

    const setGasCard = (key, item, tempLabel) => {
      if (!item) return;
      const m3 = item.consumo_hoy_m3 !== undefined ? item.consumo_hoy_m3 : 0;
      const kwh = item.consumo_hoy_kwh !== undefined ? item.consumo_hoy_kwh : Math.round(m3 * 11.68);
      const valHtml = `${m3} m³ <span style="font-size: inherit; font-weight: inherit; color: #16a34a;">| ${kwh.toLocaleString('es-ES')} kWh</span>`;
      const caudal = item.consumo_m3h !== undefined ? item.consumo_m3h : (item.caudal_1h_m3h || 0);
      const tempVal = item.temp_secado_c !== undefined ? item.temp_secado_c : (item.temp_trabajo_c !== undefined ? item.temp_trabajo_c : (item.temperatura || 0));
      const sub = tempLabel ? `Caudal: ${caudal} m³/h | ${tempLabel}: ${tempVal}°C` : `Caudal: ${caudal} m³/h`;
      setCard(key, valHtml, sub);
    };

    setGasCard('gas_tunel_vt', gas.gas_tunel_vt, 'Temp Secado');
    setGasCard('gas_calandra_1', gas.gas_calandra_1, null);
    setGasCard('gas_calandra_2', gas.gas_calandra_2, null);
    setGasCard('gas_calandra_3', gas.gas_calandra_3, null);
    setGasCard('gas_caldera_1', gas.gas_caldera_1, 'Temp Trabajo');
    setGasCard('gas_caldera_2', gas.gas_caldera_2, 'Temp Trabajo');
    setGasCard('gas_secadoras_man', gas.gas_secadoras_man, 'Temp Trabajo');
    setGasCard('gas_secadoras_aut', gas.gas_secadoras_aut, 'Temp Calculada');
  } catch (err) {
    console.warn('Error en sondeo cada 3s de consumos:', err);
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

// ==========================================
// VISTA DEDICADA DE GRÁFICA DE CONSUMOS
// Con barras, línea de tendencia y división dinámica en X
// ==========================================
window.procesoGraficaChart = null;

function renderTablaRegistrosRows(registros, isGas, isElectric, unitStr) {
  if (!registros || registros.length === 0) {
    const colspan = isElectric ? 5 : (isGas ? 7 : 5);
    return `<tr><td colspan="${colspan}" style="text-align: center; color: var(--text-muted); padding: 18px;">No se encontraron registros en el rango seleccionado.</td></tr>`;
  }

  // Mostrar únicamente los últimos 100 registros
  const displayRegistros = registros.slice(0, 100);

  return displayRegistros.map(r => {
    if (isElectric) {
      return `
        <tr>
          <td style="font-family: monospace;">${r.timestamp || r.timestamp_iso || '-'}</td>
          <td style="color: #38bdf8; font-weight: 700;">${(r.corriente_acumulada_ah !== undefined ? r.corriente_acumulada_ah : 0).toLocaleString('es-ES')}</td>
          <td style="color: #16a34a; font-weight: 700;">${(r.potencia_acumulada_kwh !== undefined ? r.potencia_acumulada_kwh : (r.valor || 0)).toLocaleString('es-ES')}</td>
          <td style="color: #fbbf24; font-weight: 700;">${(r.delta_potencia_kwh !== undefined ? r.delta_potencia_kwh : 0).toLocaleString('es-ES')}</td>
          <td style="color: var(--text-muted); font-size: 0.76rem;">${r.dispositivo || '-'}</td>
        </tr>
      `;
    } else if (isGas) {
      const vol = r.valor !== undefined ? r.valor : 0;
      const kwh = r.kwh !== undefined ? r.kwh : Math.round(vol * 11.68);
      const delta = r.delta_m3 !== undefined ? r.delta_m3 : 0;
      const caudal = r.caudal_m3h !== undefined ? r.caudal_m3h : 0;
      return `
        <tr>
          <td style="font-family: monospace;">${r.timestamp || r.timestamp_iso || '-'}</td>
          <td style="color: #94a3b8;">${(r.pulsos || 0).toLocaleString('es-ES')}</td>
          <td style="font-weight: 700; color: #ffffff;">${vol.toLocaleString('es-ES')}</td>
          <td style="color: #16a34a; font-weight: 700;">${kwh.toLocaleString('es-ES')}</td>
          <td style="color: #38bdf8; font-weight: 700;">+${delta.toLocaleString('es-ES')}</td>
          <td style="color: #fbbf24; font-weight: 700;">${caudal.toLocaleString('es-ES')}</td>
          <td style="color: var(--text-muted); font-size: 0.76rem;">${r.dispositivo || '-'}</td>
        </tr>
      `;
    } else {
      const vol = r.valor !== undefined ? r.valor : 0;
      const caudal = r.caudal_m3h !== undefined ? r.caudal_m3h : 0;
      return `
        <tr>
          <td style="font-family: monospace;">${r.timestamp || r.timestamp_iso || '-'}</td>
          <td style="color: #94a3b8;">${(r.pulsos || 0).toLocaleString('es-ES')}</td>
          <td style="font-weight: 700; color: #ffffff;">${vol.toLocaleString('es-ES')}</td>
          <td style="color: #38bdf8; font-weight: 700;">${caudal.toLocaleString('es-ES')}</td>
          <td style="color: var(--text-muted); font-size: 0.76rem;">${r.dispositivo || '-'}</td>
        </tr>
      `;
    }
  }).join('');
}

function computeMovingAverage(data, windowSize = 3) {
  if (!data || data.length === 0) return [];
  const w = Math.max(2, Math.min(windowSize, Math.floor(data.length / 2) || 2));
  return data.map((val, idx, arr) => {
    const start = Math.max(0, idx - w + 1);
    const subset = arr.slice(start, idx + 1);
    const sum = subset.reduce((acc, v) => acc + v, 0);
    return Math.round((sum / subset.length) * 100) / 100;
  });
}

function computeDynamicChartBins(records, containerWidth, isGas, unitStr) {
  // Ordenar cronológicamente ascendente (del más antiguo al más reciente)
  const sorted = [...records].reverse();
  const totalPoints = sorted.length;
  if (totalPoints === 0) {
    return { labels: [], barData: [], lineData: [], info: 'Sin datos registrados', numBins: 0 };
  }

  // Ancho mínimo por punto: ~42px para garantizar legibilidad de etiquetas
  const idealPoints = Math.max(8, Math.min(36, Math.floor(containerWidth / 44)));

  if (totalPoints <= idealPoints) {
    const labels = [];
    const barData = [];
    const lineData = [];
    let runningAccum = 0;

    sorted.forEach((r, idx) => {
      let delta = 0;
      if (r.delta_m3 !== undefined) delta = r.delta_m3;
      else if (r.delta_potencia_kwh !== undefined) delta = r.delta_potencia_kwh;
      else if (idx > 0) {
        const prev = sorted[idx - 1];
        const valCurr = r.valor !== undefined ? r.valor : 0;
        const valPrev = prev.valor !== undefined ? prev.valor : 0;
        delta = Math.max(0, valCurr - valPrev);
      }

      runningAccum += delta;

      const ts = r.timestamp || r.timestamp_iso || '';
      const parts = ts.split(' ');
      const timePart = parts.length > 1 ? parts[1].substring(0, 5) : ts;
      const datePart = parts[0] ? parts[0].substring(0, 5) : '';
      const label = totalPoints <= 14 ? `${datePart} ${timePart}` : timePart;

      labels.push(label);
      barData.push(Math.round(delta * 100) / 100);
      lineData.push(Math.round(runningAccum * 100) / 100);
    });

    const movingAvgData = computeMovingAverage(barData, Math.max(2, Math.min(5, Math.round(barData.length / 6) || 3)));
    return {
      labels,
      barData,
      movingAvgData,
      lineData,
      info: `División exacta: ${totalPoints} puntos directos para ${Math.round(containerWidth)}px de ancho`,
      numBins: totalPoints
    };
  }

  // Agrupación dinámica en N bins homogéneos
  const numBins = idealPoints;
  const binSize = totalPoints / numBins;
  const labels = [];
  const barData = [];
  const lineData = [];
  let runningAccum = 0;

  for (let b = 0; b < numBins; b++) {
    const startIdx = Math.floor(b * binSize);
    const endIdx = Math.min(totalPoints, Math.floor((b + 1) * binSize));
    const slice = sorted.slice(startIdx, endIdx);
    if (slice.length === 0) continue;

    let binDeltaSum = 0;
    slice.forEach(r => {
      let d = 0;
      if (r.delta_m3 !== undefined) d = r.delta_m3;
      else if (r.delta_potencia_kwh !== undefined) d = r.delta_potencia_kwh;
      binDeltaSum += d;
    });

    runningAccum += binDeltaSum;

    // Etiqueta del intervalo
    const midPoint = slice[Math.floor(slice.length / 2)];
    const ts = midPoint.timestamp || midPoint.timestamp_iso || '';
    const parts = ts.split(' ');
    const timePart = parts.length > 1 ? parts[1].substring(0, 5) : ts;
    const datePart = parts[0] ? parts[0].substring(0, 5) : '';

    const firstDate = sorted[0].timestamp ? sorted[0].timestamp.split(' ')[0] : '';
    const lastDate = sorted[sorted.length - 1].timestamp ? sorted[sorted.length - 1].timestamp.split(' ')[0] : '';
    const label = (firstDate !== lastDate) ? `${datePart} ${timePart}` : timePart;

    labels.push(label);
    barData.push(Math.round(binDeltaSum * 100) / 100);
    lineData.push(Math.round(runningAccum * 100) / 100);
  }

  const movingAvgData = computeMovingAverage(barData, Math.max(2, Math.min(5, Math.round(barData.length / 6) || 3)));
  return {
    labels,
    barData,
    movingAvgData,
    lineData,
    info: `División dinámica: ${numBins} intervalos calculados para ${Math.round(containerWidth)}px (de ${totalPoints} registros totales)`,
    numBins
  };
}

function renderProcesoChartWithDynamicBins(records, unitStr, isGas) {
  const canvas = document.getElementById('canvas-proceso-grafica');
  const chartCard = document.getElementById('grafica-chart-card');
  if (!canvas || !chartCard) return;

  const containerWidth = chartCard.clientWidth - 44;
  const binResults = computeDynamicChartBins(records, containerWidth, isGas, unitStr);

  const infoEl = document.getElementById('grafica-division-dinamica-info');
  if (infoEl) infoEl.textContent = binResults.info;

  const metricXEl = document.getElementById('metric-puntos-x');
  if (metricXEl) {
    metricXEl.innerHTML = `${binResults.numBins} <span style="font-size: 1.0rem; color: #94a3b8;">puntos graficados (${records.length} totales)</span>`;
  }

  if (window.procesoGraficaChart) {
    window.procesoGraficaChart.destroy();
    window.procesoGraficaChart = null;
  }

  const ctx = canvas.getContext('2d');
  window.procesoGraficaChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: binResults.labels,
      datasets: [
        {
          type: 'bar',
          label: `Consumo Intervalo (${unitStr})`,
          data: binResults.barData,
          backgroundColor: isGas ? 'rgba(245, 158, 11, 0.75)' : 'rgba(2, 132, 199, 0.75)',
          borderColor: isGas ? '#fbbf24' : '#38bdf8',
          borderWidth: 1.5,
          borderRadius: 4,
          barPercentage: 0.65,
          yAxisID: 'yBar',
          order: 3
        },
        {
          type: 'line',
          label: `Línea de Intervalos (${unitStr})`,
          data: binResults.barData,
          borderColor: '#10b981',
          backgroundColor: 'transparent',
          borderWidth: 2.5,
          pointRadius: 3.5,
          pointHoverRadius: 6,
          pointBackgroundColor: '#10b981',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 1.5,
          tension: 0.2,
          fill: false,
          yAxisID: 'yBar',
          order: 1
        },
        {
          type: 'line',
          label: `Línea de Tendencia Acumulada (${unitStr})`,
          data: binResults.lineData,
          borderColor: '#00f0ff',
          backgroundColor: 'rgba(0, 240, 255, 0.08)',
          borderWidth: 3,
          pointBackgroundColor: '#0284c7',
          pointBorderColor: '#00f0ff',
          pointRadius: 3.5,
          tension: 0.35,
          fill: false,
          yAxisID: 'yLine'
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
          ticks: { color: '#94a3b8', font: { weight: 'bold', size: 10 }, maxRotation: 45, minRotation: 0 }
        },
        yBar: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: `Consumo Intervalo (${unitStr})`, color: isGas ? '#fbbf24' : '#38bdf8', font: { weight: 'bold', size: 11 } },
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: isGas ? '#fbbf24' : '#38bdf8', font: { weight: 'bold', size: 10 } },
          suggestedMin: 0
        },
        yLine: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: `Tendencia Acumulada (${unitStr})`, color: '#00f0ff', font: { weight: 'bold', size: 11 } },
          grid: { drawOnChartArea: false },
          ticks: { color: '#00f0ff', font: { weight: 'bold', size: 10 } },
          suggestedMin: 0
        }
      },
      plugins: {
        legend: {
          labels: { color: '#f8fafc', font: { weight: 'bold', size: 11 } }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#ffffff',
          borderColor: 'rgba(255, 255, 255, 0.15)',
          borderWidth: 1,
          padding: 10
        }
      }
    }
  });
}

async function openProcesoGraficaView(id, varCode, titulo, unidad) {
  const container = document.getElementById('consumos-content');
  if (!container) return;

  const fechaInicio = document.getElementById(`filter-fecha-inicio-${id}`)?.value || '';
  const horaInicio = document.getElementById(`filter-hora-inicio-${id}`)?.value || '00:00';
  const fechaFin = document.getElementById(`filter-fecha-fin-${id}`)?.value || '';
  const horaFin = document.getElementById(`filter-hora-fin-${id}`)?.value || '23:59';

  container.innerHTML = `
    <div style="text-align: center; padding: 70px 20px;">
      <i class="fas fa-spinner fa-spin" style="font-size: 2.5rem; color: #38bdf8; margin-bottom: 16px;"></i>
      <h3 style="color: var(--text-main);">Cargando telemetría de ${titulo}...</h3>
      <p style="color: var(--text-muted); font-size: 0.88rem;">Generando gráfica con división dinámica de puntos...</p>
    </div>
  `;

  try {
    const params = new URLSearchParams({
      variable: varCode,
      fecha_inicio: fechaInicio,
      hora_inicio: horaInicio.length === 5 ? `${horaInicio}:00` : horaInicio,
      fecha_fin: fechaFin,
      hora_fin: horaFin.length === 5 ? `${horaFin}:59` : horaFin
    });

    const res = await fetch(`/api/consumos/telemetria?${params.toString()}`);
    if (!res.ok) throw new Error('Error al consultar telemetría');
    const data = await res.json();

    const registros = data.registros || [];
    const rawAcumulado = (data.acumulado !== undefined && data.acumulado !== null)
      ? data.acumulado
      : ((data.potencia_activa_rango_kwh !== undefined && data.potencia_activa_rango_kwh !== null)
        ? data.potencia_activa_rango_kwh
        : 0);
    const unitStr = data.unidad || unidad || 'm³';
    const isGas = (id.includes('gas') || varCode.includes('gas') || id.includes('calandra') || id.includes('caldera') || id.includes('secad'));
    const isElectric = (unitStr === 'kWh' || varCode.startsWith('I_') || id.includes('electr'));
    const acumulado = Number(rawAcumulado) || 0;
    const acumuladoStr = acumulado.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    const kwhStr = isGas ? ` | ${Math.round(acumulado * 11.68).toLocaleString('es-ES')} kWh` : '';
    const kvahStr = (isElectric && data.potencia_aparente_rango_kvah !== undefined && data.potencia_aparente_rango_kvah !== null)
      ? ` | ${Number(data.potencia_aparente_rango_kvah).toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} kVAh`
      : '';
    const rangoTexto = `${fechaInicio || 'Hoy'} ${horaInicio} — ${fechaFin || 'Hoy'} ${horaFin}`;

    window.lastConsumoGraficaData = {
      id,
      varCode,
      titulo,
      unidad: unitStr,
      isGas,
      isElectric,
      acumulado,
      acumuladoStr,
      kwhStr,
      kvahStr,
      rangoTexto,
      fechaInicio,
      horaInicio,
      fechaFin,
      horaFin,
      totalPulsos: data.total_pulsos || registros.length,
      totalRegistros: registros.length,
      registros,
      data
    };

    container.innerHTML = `
      <!-- Header Superior -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 22px; background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 20px; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
          <button type="button" onclick="closeProcesoGraficaView('${id}', '${varCode}', '${titulo.replace(/'/g, "\\'")}', '${unidad}')" class="btn-secondary" style="display: inline-flex; align-items: center; gap: 8px; padding: 9px 18px; border-radius: 8px; font-weight: 700; cursor: pointer; background: rgba(255,255,255,0.08); border: 1px solid var(--border-color); color: #38bdf8; font-size: 0.9rem;">
            <i class="fas fa-arrow-left"></i> Volver a panel de consumos
          </button>
          <button type="button" onclick="openInformePdfConsumoModal()" class="btn-header" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; border: none; font-weight: 700; padding: 9px 18px; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4); font-size: 0.9rem; display: inline-flex; align-items: center; gap: 8px;" title="Generar y previsualizar Informe PDF de consumos">
            <i class="fas fa-file-pdf"></i> Informe PDF
          </button>
        </div>
        <div style="text-align: right;">
          <h3 style="color: var(--text-main); font-size: 1.25rem; margin: 0; display: flex; align-items: center; gap: 8px; justify-content: flex-end;">
            <i class="fas fa-chart-bar" style="color: #fbbf24;"></i> Gráfica de Consumo: ${titulo}
          </h3>
          <small style="color: var(--text-muted); font-size: 0.8rem;">
            Rango: <strong style="color: #38bdf8;">${rangoTexto}</strong> | Variable: <strong>${varCode}</strong>
          </small>
        </div>
      </div>

      <!-- Tarjetas Resumen -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 22px;">
        <div style="background: linear-gradient(135deg, rgba(2, 132, 199, 0.25) 0%, rgba(15, 23, 42, 0.8) 100%); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 16px;">
          <small style="color: #94a3b8; text-transform: uppercase; font-weight: 700; font-size: 0.75rem;">Consumo Acumulado en Rango</small>
          <div style="font-size: 1.8rem; font-weight: 900; color: #ffffff; margin-top: 4px;">
            ${acumuladoStr} <span style="font-size: 1.1rem; color: #38bdf8;">${unitStr}</span>
            <span style="font-size: 1.0rem; color: #16a34a; font-weight: 700;">${kwhStr}</span>
            <span style="font-size: 1.0rem; color: #fbbf24; font-weight: 700;">${kvahStr}</span>
          </div>
        </div>

        <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(15, 23, 42, 0.8) 100%); border: 1px solid rgba(251, 191, 36, 0.4); border-radius: 12px; padding: 16px;">
          <small style="color: #94a3b8; text-transform: uppercase; font-weight: 700; font-size: 0.75rem;">Total Pulsos / Lecturas</small>
          <div style="font-size: 1.8rem; font-weight: 900; color: #fbbf24; margin-top: 4px;">
            ${(data.total_pulsos || registros.length).toLocaleString('es-ES')} <span style="font-size: 1.0rem; color: #94a3b8;">pulsos</span>
          </div>
        </div>

        <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(15, 23, 42, 0.8) 100%); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 16px;">
          <small style="color: #94a3b8; text-transform: uppercase; font-weight: 700; font-size: 0.75rem;">Puntos en Gráfica / Registros</small>
          <div id="metric-puntos-x" style="font-size: 1.8rem; font-weight: 900; color: #10b981; margin-top: 4px;">
            ${registros.length} <span style="font-size: 1.0rem; color: #94a3b8;">registros</span>
          </div>
        </div>
      </div>

      <!-- Contenedor del Gráfico -->
      <div id="grafica-chart-card" style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 14px; padding: 22px; margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
          <div style="font-size: 0.88rem; font-weight: 800; color: #fbbf24; text-transform: uppercase; letter-spacing: 0.6px; display: flex; align-items: center; gap: 8px;">
            <i class="fas fa-chart-area"></i> Consumo por Intervalo (Barras y Línea) con Tendencia Acumulada
          </div>
          <div id="grafica-division-dinamica-info" style="font-size: 0.75rem; color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2);">
            Calculando división dinámica...
          </div>
        </div>
        <div style="height: 400px; position: relative; width: 100%;">
          <canvas id="canvas-proceso-grafica"></canvas>
        </div>
      </div>

      <!-- Tabla de Datos del Rango Escogido -->
      <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 14px; padding: 22px; margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <h4 style="color: var(--text-main); font-size: 1.0rem; margin: 0; display: flex; align-items: center; gap: 8px;">
            <i class="fas fa-table" style="color: #38bdf8;"></i> Tabla de Datos del Rango Escogido
          </h4>
          <span style="font-size: 0.8rem; color: #38bdf8; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 6px; padding: 3px 10px; font-weight: 600;">${registros.length > 100 ? `Mostrando últimos 100 de ${registros.length.toLocaleString('es-ES')} registros` : `${registros.length.toLocaleString('es-ES')} registros`}</span>
        </div>
        <div style="max-height: 380px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 10px; background: rgba(15, 23, 42, 0.6);">
          <table class="data-table" style="margin-top: 0; font-size: 0.82rem;">
            <thead>
              ${isElectric ? `
                <tr>
                  <th>Timestamp</th>
                  <th style="color: #38bdf8;">Corriente Acumulada (Ah)</th>
                  <th style="color: #16a34a;">Potencia Acumulada (${unitStr})</th>
                  <th style="color: #fbbf24;">Delta de Potencia (${unitStr})</th>
                  <th>Dispositivo</th>
                </tr>
              ` : (isGas ? `
                <tr>
                  <th>Timestamp ISO</th>
                  <th>Pulsos (Count)</th>
                  <th>Volumen (${unitStr})</th>
                  <th style="color: #16a34a;">Potencia (kWh)</th>
                  <th style="color: #38bdf8;">Delta (m³)</th>
                  <th>Caudal (m³/h)</th>
                  <th>Dispositivo / Fuente</th>
                </tr>
              ` : `
                <tr>
                  <th>Timestamp ISO</th>
                  <th>Pulsos (Count)</th>
                  <th>Volumen (${unitStr})</th>
                  <th>Caudal (m³/h)</th>
                  <th>Dispositivo / Fuente</th>
                </tr>
              `)}
            </thead>
            <tbody>
              ${renderTablaRegistrosRows(registros, isGas, isElectric, unitStr)}
            </tbody>
          </table>
        </div>

        <!-- Botones Inferiores para volver e informe PDF -->
        <div style="margin-top: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <button type="button" onclick="closeProcesoGraficaView('${id}', '${varCode}', '${titulo.replace(/'/g, "\\'")}', '${unidad}')" class="btn-secondary" style="display: inline-flex; align-items: center; gap: 8px; padding: 10px 22px; border-radius: 8px; font-weight: 700; cursor: pointer; background: rgba(255,255,255,0.08); border: 1px solid var(--border-color); color: #38bdf8; font-size: 0.92rem;">
            <i class="fas fa-arrow-left"></i> Volver a panel de consumos
          </button>
          <button type="button" onclick="openInformePdfConsumoModal()" class="btn-header" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; border: none; font-weight: 700; padding: 10px 22px; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4); font-size: 0.92rem; display: inline-flex; align-items: center; gap: 8px;" title="Generar y previsualizar Informe PDF de consumos">
            <i class="fas fa-file-pdf"></i> Informe PDF
          </button>
        </div>
      </div>
    `;

    setTimeout(() => {
      renderProcesoChartWithDynamicBins(registros, unitStr, isGas);
    }, 60);

  } catch (err) {
    container.innerHTML = `
      <div style="padding: 30px; text-align: center;">
        <div style="color: var(--accent-red); font-size: 1.1rem; margin-bottom: 16px;">⚠️ ${err.message}</div>
        <button onclick="closeProcesoGraficaView('${id}', '${varCode}', '${titulo.replace(/'/g, "\\'")}', '${unidad}')" class="btn-secondary" style="padding: 8px 16px; border-radius: 8px; cursor: pointer;">
          <i class="fas fa-arrow-left"></i> Volver a panel de consumos
        </button>
      </div>
    `;
  }
}

function closeProcesoGraficaView(id, varCode, titulo, unidad) {
  if (window.procesoGraficaChart) {
    window.procesoGraficaChart.destroy();
    window.procesoGraficaChart = null;
  }
  loadConsumosData().then(() => {
    setTimeout(() => {
      toggleProcesoPanel(id, varCode, titulo, unidad);
    }, 120);
  });
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
  const isGas = (id.includes('gas') || id.includes('calandra') || id.includes('caldera') || id.includes('secad') || varCode.includes('gas') || varCode.includes('calandra') || varCode.includes('caldera') || varCode.includes('Secado') || varCode.includes('secad')) && !isElectric;
  const colspanNum = isElectric ? 5 : (isGas ? 7 : 5);

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

    const unitStr = data.unidad || unidad || (isElectric ? 'kWh' : 'm³');
    if (valorAccEl) {
      if (isElectric) {
        const pActivaNum = (data.potencia_activa_rango_kwh !== undefined && data.potencia_activa_rango_kwh !== null) 
          ? Number(data.potencia_activa_rango_kwh) 
          : (Number(data.acumulado) || 0);
        const pAparenteNum = (data.potencia_aparente_rango_kvah !== undefined && data.potencia_aparente_rango_kvah !== null)
          ? Number(data.potencia_aparente_rango_kvah)
          : (pActivaNum > 0 ? +(pActivaNum / 0.90).toFixed(2) : 0.0);
        const pActivaKwh = pActivaNum.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
        const pAparenteKvah = pAparenteNum.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 });
        valorAccEl.innerHTML = `<span style="color: #ffffff;">${pActivaKwh} kWh</span> <span style="font-size: 1.8rem; color: #fbbf24; margin-left: 14px; font-weight: 800;">| ${pAparenteKvah} kVAh</span>`;
      } else if (isGas) {
        const kwhTotal = (data.acumulado_kwh !== undefined ? data.acumulado_kwh : (data.acumulado * 11.68)).toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        valorAccEl.innerHTML = `${data.acumulado} ${unitStr} <span style="font-size: 1.8rem; color: #16a34a; margin-left: 14px; font-weight: 800;">| ${kwhTotal} kWh</span>`;
      } else {
        valorAccEl.textContent = `${data.acumulado} ${unitStr}`;
      }
    }
    if (subtextAccEl) {
      if (isElectric) {
        const pActMedia = data.potencia_activa_media_kw !== undefined ? `${data.potencia_activa_media_kw} kW` : '-';
        const pApMedia = data.potencia_aparente_media_kva !== undefined ? `${data.potencia_aparente_media_kva} kVA` : '-';
        const iMaxR = data.corriente_max_rango_a !== undefined ? `${data.corriente_max_rango_a} A` : '-';
        const iConsumida = data.corriente_acumulada_rango_ah !== undefined ? `${data.corriente_acumulada_rango_ah.toLocaleString('es-ES')} Ah` : '-';
        subtextAccEl.innerHTML = `Consumo Corriente: <strong>${iConsumida}</strong> | P. Activa Media: <strong>${pActMedia}</strong> | P. Aparente Media: <strong>${pApMedia}</strong> | I. Máx Rango: <strong>${iMaxR}</strong> | Variable: ${varCode}`;
      } else {
        subtextAccEl.textContent = `Total Lecturas: ${(data.total_pulsos || data.total_registros || 0).toLocaleString()} | Variable: ${varCode} | Rango: ${data.filtro.start_iso} ➔ ${data.filtro.end_iso}`;
      }
    }
    const totalRegs = data.total_registros || (data.registros ? data.registros.length : 0);
    if (countEl) {
      if (totalRegs > 100) {
        countEl.textContent = `100 de ${totalRegs.toLocaleString('es-ES')} registros`;
      } else {
        countEl.textContent = `${totalRegs.toLocaleString('es-ES')} registros`;
      }
    }

    if (tbody) {
      if (!data.registros || data.registros.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colspanNum}" style="text-align: center; color: var(--text-muted); padding: 15px;">No se encontraron lecturas para ${varCode} en el rango seleccionado.</td></tr>`;
      } else {
        const displayRegistros = data.registros.slice(0, 100);
        tbody.innerHTML = displayRegistros.map((r, idx) => {
          const kwhVal = r.kwh !== undefined ? r.kwh : (r.valor !== undefined ? +(r.valor * 11.68).toFixed(2) : 0);
          const kwhCol = isGas ? `<td><span style="color: #16a34a; font-weight: 800;">${kwhVal.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kWh</span></td>` : '';
          
          let deltaVal = 0.0;
          let hasDelta = false;
          if (idx < displayRegistros.length - 1) {
            hasDelta = true;
            if (r.delta_m3 !== undefined && r.delta_m3 !== null && r.delta_m3 > 0) {
              deltaVal = r.delta_m3;
            } else {
              deltaVal = Math.round((r.valor - displayRegistros[idx + 1].valor) * 100) / 100;
            }
          }
          const deltaStr = hasDelta
            ? `<span style="color: #38bdf8; font-weight: 700;">+${deltaVal.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} m³</span>`
            : `<span style="color: var(--text-muted);">-</span>`;
          const deltaCol = isGas ? `<td>${deltaStr}</td>` : '';

          if (isElectric) {
            const currVal = r.corriente_a !== undefined ? r.corriente_a : 0;
            const ahVal = r.corriente_acumulada_ah !== undefined ? r.corriente_acumulada_ah : 0;
            const pAcum = r.potencia_acumulada_kwh !== undefined ? r.potencia_acumulada_kwh : 0;
            let deltaVal = 0.0;
            if (r.delta_potencia_kwh !== undefined) {
              deltaVal = r.delta_potencia_kwh;
            } else if (idx < displayRegistros.length - 1) {
              deltaVal = Math.round((pAcum - (displayRegistros[idx + 1].potencia_acumulada_kwh || 0)) * 1000) / 1000;
            }
            const deltaStr = deltaVal > 0 
              ? `<span style="color: #fbbf24; font-weight: 700;">+${deltaVal.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 3 })} kWh</span>`
              : `<span style="color: var(--text-muted);">-</span>`;

            return `
              <tr>
                <td><strong style="color: #38bdf8;">${r.timestamp_iso || r.timestamp}</strong></td>
                <td>
                  <span style="color: #38bdf8; font-weight: 800;">${ahVal.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} Ah</span>
                  <small style="color: var(--text-muted); display: block; font-size: 0.72rem;">Inst: ${currVal.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} A</small>
                </td>
                <td><span style="color: #16a34a; font-weight: 800;">${pAcum.toLocaleString('es-ES', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} kWh</span></td>
                <td>${deltaStr}</td>
                <td><small style="color: var(--text-muted);">${r.dispositivo || varCode}</small></td>
              </tr>
            `;
          }

          return `
          <tr>
            <td><strong style="color: #38bdf8;">${r.timestamp_iso}</strong></td>
            <td><span style="color: #fbbf24; font-weight: 700;">${r.pulsos} pulsos</span></td>
            <td><span style="color: #34d399; font-weight: 800;">${r.valor} ${r.unidad}</span></td>
            ${kwhCol}
            ${deltaCol}
            <td>${r.caudal_m3h} m³/h</td>
            <td><small style="color: var(--text-muted);">${r.dispositivo}</small></td>
          </tr>
        `;
        }).join('');
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
// SECCIÓN: HISTORIAL DE TURNOS MULTI-MÁQUINA
// (Túnel de Lavado, Calandra 2, Calandra 3, Túnel VT)
// ==========================================
let currentHistorialMachine = 'TUNEL_LAVADO';
let chartHistorialTurno = null;

function getLocalJornadaDate() {
  const now = new Date();
  if (now.getHours() < 5) {
    now.setDate(now.getDate() - 1);
  }
  return now.toLocaleDateString('sv-SE'); // Formato YYYY-MM-DD
}

function updateHistorialHeadersAndBackBtn() {
  const btnText = document.getElementById('historial-btn-volver-text');
  const title = document.getElementById('historial-title');
  const subtitle = document.getElementById('historial-subtitle');

  let machineName = 'Túnel de Lavado';
  let icon = '🌊';
  if (currentHistorialMachine === 'CALANDRA_2') {
    machineName = 'Calandra 2';
    icon = '📜';
  } else if (currentHistorialMachine === 'CALANDRA_3') {
    machineName = 'Calandra 3';
    icon = '👁️';
  } else if (currentHistorialMachine === 'TUNEL_VT') {
    machineName = 'Túnel VT';
    icon = '💨';
  }

  if (btnText) btnText.textContent = `Volver a ${machineName}`;
  if (title) title.innerHTML = `📜 Historial de Turnos — ${icon} ${machineName}`;
  if (subtitle) subtitle.textContent = `Consulta la producción, indicadores y gráficas persistidas por fecha y turno para ${machineName}`;
}

function openMachineHistorial(maquinaId) {
  currentHistorialMachine = maquinaId || 'TUNEL_LAVADO';
  const sel = document.getElementById('historial-maquina-select');
  if (sel) sel.value = currentHistorialMachine;
  updateHistorialHeadersAndBackBtn();
  resetHistorialView();
  switchView('historial_turnos');
  initHistorialTurnosScreen();
}
window.openMachineHistorial = openMachineHistorial;

function volverDesdeHistorial() {
  if (currentHistorialMachine === 'CALANDRA_2') {
    switchView('calandra_2');
  } else if (currentHistorialMachine === 'CALANDRA_3') {
    switchView('calandra_3');
  } else if (currentHistorialMachine === 'TUNEL_VT') {
    switchView('tunel_vt');
  } else {
    switchView('tunel_lavado');
  }
}
window.volverDesdeHistorial = volverDesdeHistorial;

function onHistorialMachineChange() {
  const sel = document.getElementById('historial-maquina-select');
  if (sel) currentHistorialMachine = sel.value;
  updateHistorialHeadersAndBackBtn();
  resetHistorialView();
  initHistorialTurnosScreen();
}
window.onHistorialMachineChange = onHistorialMachineChange;

async function initHistorialTurnosScreen() {
  const fechaPicker = document.getElementById('historial-fecha-picker');
  const turnoSelect = document.getElementById('historial-turno-select');
  const maquinaSelect = document.getElementById('historial-maquina-select');

  if (maquinaSelect && maquinaSelect.value !== currentHistorialMachine) {
    maquinaSelect.value = currentHistorialMachine;
  }
  updateHistorialHeadersAndBackBtn();

  if (!fechaPicker || !turnoSelect) return;

  const currentJornada = getLocalJornadaDate();
  fechaPicker.max = currentJornada;

  // Registrar listeners de eventos una sola vez
  if (!fechaPicker.dataset.eventsAttached) {
    fechaPicker.dataset.eventsAttached = 'true';

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

    turnoSelect.addEventListener('change', async (e) => {
      const shiftKey = e.target.value;
      if (shiftKey) {
        await loadReconstructedShiftDashboard(shiftKey);
      } else {
        resetHistorialView();
      }
    });
  }

  // Consultar fechas disponibles según la máquina activa
  try {
    let endpoint = '/api/produccion/turnos/fechas-disponibles';
    if (currentHistorialMachine === 'CALANDRA_2' || currentHistorialMachine === 'CALANDRA_3') {
      endpoint = `/api/produccion/calandras/${currentHistorialMachine}/turnos-fechas`;
    } else if (currentHistorialMachine === 'TUNEL_VT') {
      endpoint = '/api/produccion/tunel-vt/turnos-fechas';
    }

    const res = await fetch(endpoint);
    let targetFecha = currentJornada;
    if (res.ok) {
      const data = await res.json();
      if (data.hoy) targetFecha = data.hoy;
      else if (data.fechas && data.fechas.length > 0) {
        targetFecha = data.fechas[0];
      }
    }

    if (!fechaPicker.value || fechaPicker.value > targetFecha) {
      fechaPicker.value = targetFecha;
    }

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
    try {
      chartHistorialTurno.destroy();
    } catch (e) {
      console.warn("Error destruyendo chartHistorialTurno:", e);
    }
    chartHistorialTurno = null;
  }
}

async function loadShiftsForHistorialDate(fechaStr) {
  const turnoSelect = document.getElementById('historial-turno-select');
  if (!turnoSelect) return;

  try {
    turnoSelect.innerHTML = '<option value="">Cargando turnos...</option>';
    turnoSelect.disabled = true;

    let endpoint = `/api/produccion/turnos/por-fecha/${fechaStr}`;
    if (currentHistorialMachine === 'CALANDRA_2' || currentHistorialMachine === 'CALANDRA_3') {
      endpoint = `/api/produccion/calandras/${currentHistorialMachine}/turnos-por-fecha/${fechaStr}`;
    } else if (currentHistorialMachine === 'TUNEL_VT') {
      endpoint = `/api/produccion/tunel-vt/turnos-por-fecha/${fechaStr}`;
    }

    const res = await fetch(endpoint);
    if (!res.ok) throw new Error('Error al obtener turnos de la fecha');
    const data = await res.json();

    turnoSelect.innerHTML = '<option value="">-- Seleccionar Turno --</option>';

    if (data.turnos && data.turnos.length > 0) {
      const validos = data.turnos.filter(t => {
        const nombreUpper = (t.nombre_turno || t.turno_identificador || '').toUpperCase();
        const keyUpper = (t.shift_key || '').toUpperCase();
        return !nombreUpper.includes('FUERA') && !keyUpper.includes('FUERA') && !nombreUpper.includes('SIN TURNO') && !nombreUpper.includes('INACTIVO');
      });

      if (validos.length > 0) {
        validos.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t.shift_key;
          const estadoTag = t.is_in_progress ? ' [En proceso]' : '';

          if (currentHistorialMachine === 'TUNEL_LAVADO') {
            const totalKgStr = typeof t.total_kg === 'number' ? Math.round(t.total_kg).toLocaleString('es-ES') : (t.total_kg || 0);
            opt.textContent = `${t.nombre_turno} (${t.horario}) — ${totalKgStr} kg${estadoTag}`;
          } else {
            const pTot = Math.round(t.prendas_totales || 0).toLocaleString('es-ES');
            const kgTot = (typeof t.kgs_totales === 'number' ? t.kgs_totales.toFixed(1) : (t.kgs_totales || 0)).toLocaleString('es-ES');
            const horarioStr = t.horario || t.rango_horario || '';
            opt.textContent = `${t.nombre_turno} (${horarioStr}) — ${pTot} p | ${kgTot} kg${estadoTag}`;
          }

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
    dashboardContainer.innerHTML = '<p style="color: var(--text-muted); padding: 20px;"><i class="fas fa-spinner fa-spin"></i> Cargando dashboard del turno...</p>';

    if (chartHistorialTurno) {
      try {
        chartHistorialTurno.destroy();
      } catch (e) {
        console.warn("Destruyendo gráfico anterior:", e);
      }
      chartHistorialTurno = null;
    }

    let endpoint = `/api/produccion/turnos/historial-json/${shiftKey}`;
    if (currentHistorialMachine === 'CALANDRA_2' || currentHistorialMachine === 'CALANDRA_3') {
      endpoint = `/api/produccion/calandras/${currentHistorialMachine}/turnos-historial/${shiftKey}`;
    } else if (currentHistorialMachine === 'TUNEL_VT') {
      endpoint = `/api/produccion/tunel-vt/turnos-historial/${shiftKey}`;
    }

    const res = await fetch(endpoint);
    if (!res.ok) throw new Error('No se pudo cargar el paquete JSON del turno');
    const pkg = await res.json();

    if (placeholder) placeholder.style.display = 'none';

    // RENDERIZADO 1: TÚNEL DE LAVADO
    if (currentHistorialMachine === 'TUNEL_LAVADO') {
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

        <div class="dashboard-grid-layout">
          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 1; grid-row: 1;">
            <div class="kpi-card-header">
              <h4>${kgInfo.titulo}</h4>
              <div class="kpi-icon-circle"><i class="fas ${kgInfo.icono}"></i></div>
            </div>
            <div class="kpi-big-number">${kgInfo.valor}</div>
            <div class="kpi-card-subtext">${kgInfo.subtexto}</div>
          </div>

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

          <div class="kpi-card-striking kpi-card-amber" style="grid-column: 2; grid-row: 1;">
            <div class="kpi-card-header">
              <h4>${cargasInfo.titulo}</h4>
              <div class="kpi-icon-circle"><i class="fas ${cargasInfo.icono}"></i></div>
            </div>
            <div class="kpi-big-number">${cargasInfo.valor}</div>
            <div class="kpi-card-subtext">${cargasInfo.subtexto}</div>
          </div>

          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 3; grid-row: 1; background: linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #0f172a 100%);">
            <div class="kpi-card-header">
              <h4>${hprodInfo.titulo}</h4>
              <div class="kpi-icon-circle"><i class="fas ${hprodInfo.icono}"></i></div>
            </div>
            <div class="kpi-big-number">${hprodInfo.valor}</div>
            <div class="kpi-card-subtext">${hprodInfo.subtexto}</div>
          </div>

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

      const graficaData = {
        labels: desglose.labels || [],
        kg_por_hora: desglose.kg_por_hora || [],
        cargas_por_hora: desglose.cargas_por_hora || [],
        kg_acumulado: desglose.kg_acumulado_por_hora || desglose.kg_acumulado || []
      };
      renderAvanceChart(graficaData, 'chart-historial-turno');
      return;
    }

    // RENDERIZADO 2: CALANDRA 2 O CALANDRA 3
    if (currentHistorialMachine === 'CALANDRA_2' || currentHistorialMachine === 'CALANDRA_3') {
      const isCal2 = (currentHistorialMachine === 'CALANDRA_2');
      const ind = pkg.indicadores_dashboard || pkg.indicadores || {};
      const meta = pkg.meta_info || {};
      const turno = {
        nombre: meta.nombre_turno || pkg.turno_identificador || pkg.nombre_turno || 'Turno',
        horario: meta.rango_horario || pkg.rango_horario || `${pkg.hora_inicio || ''} - ${pkg.hora_fin || ''}`,
        fecha: meta.fecha_formateada || meta.fecha || pkg.fecha || ''
      };
      const g = pkg.desglose_hora_a_hora || pkg.grafica_hora_a_hora || ind.grafica_hora_a_hora || {};

      dashboardContainer.innerHTML = `
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; padding: 12px 18px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
            <div style="width: 44px; height: 44px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.12rem; gap: 3px; border: 1px solid rgba(56, 189, 248, 0.3);">
              <i class="fas fa-scroll"></i><span style="font-weight: 800; font-size: 1.18rem; line-height: 1;">${isCal2 ? '2' : '3'}</span>
            </div>
            <div>
              <h4 style="color: var(--text-main); font-size: 1rem;">${turno.nombre || 'Turno'} (${turno.horario || ''}) — <span style="color: #38bdf8;">📅 ${turno.fecha || pkg.fecha}</span></h4>
              <small style="color: var(--text-muted); font-size: 0.78rem;">Origen: Persistencia SQLite ${isCal2 ? 'Calandra 2' : 'Calandra 3'} (Clave: ${pkg.shift_key || shiftKey})</small>
            </div>
          </div>
          <div style="text-align: right;">
            <span style="font-size: 0.82rem; color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.4);">📜 HISTORIAL DE TURNO</span>
          </div>
        </div>

        <div class="calandra-dashboard-grid-layout">
          <!-- Columna 1, Fila 1: Prendas Totales -->
          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 1; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tshirt"></i> Prendas Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-layer-group"></i></div>
            </div>
            <div class="kpi-big-number">${ind.prendas_totales_str || '0'}</div>
            <div class="kpi-card-subtext">Acumulado del turno</div>
            <div>
              ${getCalandraDesglosePrendasHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 2, Fila 1: Kgs Totales -->
          <div class="kpi-card-striking kpi-card-green" style="grid-column: 2; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-weight-hanging"></i> Kgs Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-balance-scale-right"></i></div>
            </div>
            <div class="kpi-big-number">${ind.kgs_totales_str || '0 kg'}</div>
            <div class="kpi-card-subtext">Kilos procesados en el turno</div>
            <div>
              ${getCalandraDesgloseKgsHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 3, Fila 1: Tiempo Valle -->
          <div class="kpi-card-striking kpi-card-amber" style="grid-column: 3; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-stopwatch"></i> Tiempo Valle</h4>
              <div class="kpi-icon-circle"><i class="fas fa-hourglass-half"></i></div>
            </div>
            <div class="kpi-big-number">${ind.tiempo_valle_str || '0,0 min'}</div>
            <div class="kpi-card-subtext">Minutos de valle acumulados</div>
            <div>
              ${getCalandraDesgloseValleHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 4, Fila 1: Prendas / Hora -->
          <div class="kpi-card-striking kpi-card-purple" style="grid-column: 4; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tachometer-alt"></i> Prendas / Hora</h4>
              <div class="kpi-icon-circle"><i class="fas fa-bolt"></i></div>
            </div>
            <div class="kpi-big-number">${ind.prendas_hora_str || '0 p/h'}</div>
            <div class="kpi-card-subtext">Cadencia promedio horaria</div>
            <div>
              ${getCalandraDesglosePrendasHoraHtml(isCal2, ind)}
            </div>
          </div>

          <!-- Columna 1, Fila 2: Kg / Hora -->
          <div class="kpi-card-striking calandra-card-kg-hora" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div class="kpi-card-header">
                <h4 style="color: #f8fafc;"><i class="fas fa-balance-scale"></i> KG / HORA</h4>
                <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-chart-line"></i></div>
              </div>
              <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${ind.kg_hora_str || '0,0 kg/h'}</div>
              <div>
                ${getCalandraDesgloseKgHoraHtml(isCal2, ind)}
              </div>
            </div>

            <div>
              <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 6px; margin-top: 4px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                <span style="color: #818cf8;"><i class="fas fa-tachometer-alt"></i> Cadencia Turno</span>
                <span style="color: #38bdf8;">${ind.prendas_hora_str || '0 p/h'}</span>
              </div>
              <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
                <i class="fas fa-calculator"></i> Ritmo ponderado de kilogramos en tiempo productivo
              </div>
            </div>
          </div>

          <!-- Fila 2, Columnas 2 a 4: Gráfica de Producción y Tiempo Valle -->
          <div class="chart-section-card calandra-chart-section" style="grid-column: 2 / span 3; grid-row: 2;">
            <div class="chart-header-row" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
              <div class="chart-header-title">
                <i class="fas fa-chart-line" style="color: #38bdf8; font-size: 1.1rem;"></i>
                <h4 style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin: 0;">
                  Avance de Producción y Tiempo Valle Hora a Hora (${isCal2 ? 'Calandra 2' : 'Calandra 3'})
                </h4>
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span><span style="display:inline-block;width:10px;height:10px;background:#38bdf8;border-radius:2px;margin-right:4px;"></span><strong style="color: #38bdf8;">Prendas</strong> (Eje Izquierdo)</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#fbbf24;border-radius:2px;margin-right:4px;"></span><strong style="color: #fbbf24;">Tiempo Valle min</strong> (Eje Derecho)</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#b91c1c;border-radius:2px;margin-right:4px;"></span><strong style="color: #f87171;">Tiempo Descanso min</strong></span>
              </div>
            </div>
            <div class="chart-wrapper">
              <canvas id="chart-historial-turno"></canvas>
            </div>
          </div>
        </div>
      `;

      // Renderizar gráfico de Calandra en chart-historial-turno
      const canvasEl = document.getElementById('chart-historial-turno');
      if (canvasEl) {
        const labels = g.labels || [];
        const prendasData = g.prendas || [];
        const valleData = g.tiempo_valle_min || g.tiempo_valle || [];
        const descansoData = g.tiempo_descanso || g.tiempo_descanso_min || [];
        const datasets = [];

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
            borderColor: '#34d399',
            borderWidth: 1.5,
            borderDash: [4, 4],
            pointBackgroundColor: '#059669',
            pointBorderColor: '#34d399',
            pointRadius: 3,
            tension: 0.35,
            fill: false,
            yAxisID: 'yPrendas'
          });
        }

        // Barras verticales de tiempo valle neto (Eje Y Derecho, stack 'valle')
        datasets.push({
          type: 'bar',
          label: 'Tiempo Valle (min)',
          data: valleData,
          backgroundColor: 'rgba(251, 191, 36, 0.75)',
          borderColor: '#fbbf24',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.45,
          stack: 'valle',
          yAxisID: 'yValle'
        });

        // Barras verticales de tiempo descanso (Eje Y Derecho, stack 'valle' apilada en rojo oscuro)
        datasets.push({
          type: 'bar',
          label: 'Tiempo Descanso (min)',
          data: descansoData,
          backgroundColor: 'rgba(153, 27, 27, 0.90)',
          borderColor: '#b91c1c',
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.45,
          stack: 'valle',
          yAxisID: 'yValle'
        });

        const ctx = canvasEl.getContext('2d');
        chartHistorialTurno = new Chart(ctx, {
          data: { labels: labels, datasets: datasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              legend: {
                display: true,
                position: 'top',
                labels: { boxWidth: 12, boxHeight: 10, color: '#94a3b8', font: { size: 10 } }
              },
              tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                titleColor: '#f8fafc',
                bodyColor: '#e2e8f0',
                borderColor: 'rgba(255, 255, 255, 0.12)',
                borderWidth: 1
              }
            },
            scales: {
              x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8', font: { size: 9.5 } } },
              yPrendas: {
                type: 'linear', position: 'left', beginAtZero: true,
                grid: { color: 'rgba(56, 189, 248, 0.1)' },
                ticks: { color: '#38bdf8', font: { size: 9.5 } }
              },
              yValle: {
                type: 'linear', position: 'right', beginAtZero: true, max: 60,
                stacked: true,
                grid: { drawOnChartArea: false },
                ticks: { color: '#fbbf24', font: { size: 9.5 }, callback: v => v + ' min' }
              }
            }
          }
        });
      }
      return;
    }

    // RENDERIZADO 3: TÚNEL VT
    if (currentHistorialMachine === 'TUNEL_VT') {
      const ind = pkg.indicadores_dashboard || pkg.indicadores || {};
      const meta = pkg.meta_info || {};
      const turno = {
        nombre: meta.nombre_turno || pkg.turno_identificador || pkg.nombre_turno || 'Turno',
        horario: meta.rango_horario || pkg.rango_horario || `${pkg.hora_inicio || ''} - ${pkg.hora_fin || ''}`,
        fecha: meta.fecha_formateada || meta.fecha || pkg.fecha || ''
      };
      const de = ind.desglose_entradas || {};
      const g = pkg.desglose_hora_a_hora || pkg.grafica_hora_a_hora || ind.grafica_hora_a_hora || {};

      dashboardContainer.innerHTML = `
        <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; padding: 12px 18px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 38px; height: 38px; border-radius: 8px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
              <i class="fas fa-wind"></i>
            </div>
            <div>
              <h4 style="color: var(--text-main); font-size: 1rem;">${turno.nombre || 'Turno'} (${turno.horario || ''}) — <span style="color: #38bdf8;">📅 ${turno.fecha || pkg.fecha}</span></h4>
              <small style="color: var(--text-muted); font-size: 0.78rem;">Origen: Persistencia SQLite Túnel VT (Clave: ${pkg.shift_key || shiftKey}) | Peso aplicado: <strong>${ind.peso_unitario_str || '0,260 kg/u'}</strong></small>
            </div>
          </div>
          <div style="text-align: right;">
            <span style="font-size: 0.82rem; color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.15); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.4);">📜 HISTORIAL DE TURNO</span>
          </div>
        </div>

        <div class="calandra-dashboard-grid-layout">
          <!-- Columna 1, Fila 1: Prendas Totales -->
          <div class="kpi-card-striking kpi-card-cyan" style="grid-column: 1; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tshirt"></i> Prendas Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-layer-group"></i></div>
            </div>
            <div class="kpi-big-number">${ind.prendas_totales_str || '0'}</div>
            <div class="kpi-card-subtext">Acumulado en el turno</div>
            <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 1">E1: ${de.entrada_1 || 0}</span>
              <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 2">E2: ${de.entrada_2 || 0}</span>
              <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Entrada 3">E3: ${de.entrada_3 || 0}</span>
            </div>
          </div>

          <!-- Columna 2, Fila 1: Kgs Totales -->
          <div class="kpi-card-striking kpi-card-green" style="grid-column: 2; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-weight-hanging"></i> Kgs Totales</h4>
              <div class="kpi-icon-circle"><i class="fas fa-balance-scale-right"></i></div>
            </div>
            <div class="kpi-big-number">${ind.kgs_totales_str || '0 kg'}</div>
            <div class="kpi-card-subtext">Kilos totales calculados</div>
            <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kg E1">E1: ${de.kg_e1_str || '0,0 kg'}</span>
              <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kg E2">E2: ${de.kg_e2_str || '0,0 kg'}</span>
              <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Kg E3">E3: ${de.kg_e3_str || '0,0 kg'}</span>
            </div>
          </div>

          <!-- Columna 3, Fila 1: Tiempo Valle Total -->
          <div class="kpi-card-striking kpi-card-amber" style="grid-column: 3; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-stopwatch"></i> Tiempo Valle Total</h4>
              <div class="kpi-icon-circle"><i class="fas fa-hourglass-half"></i></div>
            </div>
            <div class="kpi-big-number">${ind.tiempo_valle_str || '0,0 min'}</div>
            <div class="kpi-card-subtext">Minutos de valle del turno</div>
            <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(251, 191, 36, 0.15); color: #fbbf24; border-color: rgba(251, 191, 36, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E1">E1: ${de.tiempo_valle_e1_str || '0,0 min'}</span>
              <span class="cal-badge-p" style="background: rgba(249, 115, 22, 0.15); color: #f97316; border-color: rgba(249, 115, 22, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E2">E2: ${de.tiempo_valle_e2_str || '0,0 min'}</span>
              <span class="cal-badge-g" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Valle E3">E3: ${de.tiempo_valle_e3_str || '0,0 min'}</span>
            </div>
          </div>

          <!-- Columna 4, Fila 1: Prendas / Hora -->
          <div class="kpi-card-striking kpi-card-purple" style="grid-column: 4; grid-row: 1;">
            <div class="kpi-card-header">
              <h4><i class="fas fa-tachometer-alt"></i> Prendas / Hora</h4>
              <div class="kpi-icon-circle"><i class="fas fa-bolt"></i></div>
            </div>
            <div class="kpi-big-number">${ind.prendas_hora_str || '0 p/h'}</div>
            <div class="kpi-card-subtext">Cadencia horaria total</div>
            <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap;">
              <span class="cal-badge-g" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E1">E1: ${de.prendas_e1_hora_str || '0 p/h'}</span>
              <span class="cal-badge-p" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E2">E2: ${de.prendas_e2_hora_str || '0 p/h'}</span>
              <span class="cal-badge-g" style="background: rgba(192, 132, 252, 0.15); color: #c084fc; border-color: rgba(192, 132, 252, 0.3); font-size: 1.05rem; font-weight: 700; padding: 4px 10px; border-radius: 6px;" title="Cadencia E3">E3: ${de.prendas_e3_hora_str || '0 p/h'}</span>
            </div>
          </div>

          <!-- Columna 1, Fila 2: Kg / Hora -->
          <div class="kpi-card-striking calandra-card-kg-hora" style="grid-column: 1; grid-row: 2; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div class="kpi-card-header">
                <h4 style="color: #f8fafc;"><i class="fas fa-balance-scale"></i> KG / HORA</h4>
                <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-chart-line"></i></div>
              </div>
              <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${ind.kg_hora_str || '0,0 kg/h'}</div>
              <div style="color: var(--text-muted); font-size: 0.8rem; margin-top: 4px;">
                Cálculo basado en cadencia real y peso configurado
              </div>
            </div>

            <div>
              <div style="font-size: 0.8rem; font-weight: 700; color: #ffffff; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); padding: 6px 10px; border-radius: 6px; margin-top: 4px; display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                <span style="color: #818cf8;"><i class="fas fa-tachometer-alt"></i> Cadencia Turno</span>
                <span style="color: #38bdf8;">${ind.prendas_hora_str || '0 p/h'}</span>
              </div>
              <div style="font-size: 0.68rem; color: #94a3b8; margin-top: 6px; font-weight: 600;">
                <i class="fas fa-calculator"></i> Ritmo ponderado de kilogramos en tiempo productivo
              </div>
            </div>
          </div>

          <!-- Fila 2, Columnas 2 a 4: Gráfica de Producción y Tiempo Valle por Entrada -->
          <div class="chart-section-card calandra-chart-section" style="grid-column: 2 / span 3; grid-row: 2;">
            <div class="chart-header-row" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
              <div class="chart-header-title">
                <i class="fas fa-chart-line" style="color: #38bdf8; font-size: 1.1rem;"></i>
                <h4 style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin: 0;">
                  Avance de Producción y Tiempo Valle Hora a Hora — Túnel VT (3 Vías)
                </h4>
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <span><span style="display:inline-block;width:10px;height:10px;background:#ffffff;border-radius:2px;margin-right:4px;"></span><strong style="color: #ffffff;">E1</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#34d399;border-radius:2px;margin-right:4px;"></span><strong style="color: #34d399;">E2</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#c084fc;border-radius:2px;margin-right:4px;"></span><strong style="color: #c084fc;">E3</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#fbbf24;border-radius:2px;margin-right:4px;"></span><strong style="color: #fbbf24;">Valle (min)</strong></span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#b91c1c;border-radius:2px;margin-right:4px;"></span><strong style="color: #f87171;">Descanso (min)</strong></span>
              </div>
            </div>
            <div class="chart-wrapper">
              <canvas id="chart-historial-turno"></canvas>
            </div>
          </div>
        </div>
      `;

      // Renderizar gráfico de Túnel VT en chart-historial-turno (Líneas para Prendas + Barras para Valles)
      const canvasEl = document.getElementById('chart-historial-turno');
      if (canvasEl) {
        const labels = g.labels || [];
        const e1Data = g.entrada_1 || [];
        const e2Data = g.entrada_2 || [];
        const e3Data = g.entrada_3 || [];
        const v1Data = g.valle_e1 || [];
        const v2Data = g.valle_e2 || [];
        const v3Data = g.valle_e3 || [];
        const d1Data = g.descanso_e1 || g.tiempo_descanso || [];
        const d2Data = g.descanso_e2 || g.tiempo_descanso || [];
        const d3Data = g.descanso_e3 || g.tiempo_descanso || [];

        const datasets = [
          // 3 Líneas de prendas por hora (Eje Y Izquierdo: yPrendas)
          {
            type: 'line',
            label: 'Entrada 1 (Prendas)',
            data: e1Data,
            borderColor: '#ffffff',
            backgroundColor: 'rgba(255, 255, 255, 0.12)',
            borderWidth: 2.8,
            pointBackgroundColor: '#ffffff',
            pointBorderColor: '#0ea5e9',
            pointRadius: 4.5,
            pointHoverRadius: 6.5,
            tension: 0.35,
            fill: false,
            yAxisID: 'yPrendas'
          },
          {
            type: 'line',
            label: 'Entrada 2 (Prendas)',
            data: e2Data,
            borderColor: '#34d399',
            backgroundColor: 'rgba(52, 211, 153, 0.12)',
            borderWidth: 2.5,
            pointBackgroundColor: '#059669',
            pointBorderColor: '#34d399',
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.35,
            fill: false,
            yAxisID: 'yPrendas'
          },
          {
            type: 'line',
            label: 'Entrada 3 (Prendas)',
            data: e3Data,
            borderColor: '#c084fc',
            backgroundColor: 'rgba(192, 132, 252, 0.12)',
            borderWidth: 2.5,
            pointBackgroundColor: '#9333ea',
            pointBorderColor: '#c084fc',
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.35,
            fill: false,
            yAxisID: 'yPrendas'
          },
          // 3 Barras verticales de tiempo valle y descanso por hora (Eje Y Derecho: yValle, apiladas por vía)
          {
            type: 'bar',
            label: 'Valle E1 (min)',
            data: v1Data,
            backgroundColor: 'rgba(251, 191, 36, 0.75)',
            borderColor: '#fbbf24',
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.8,
            categoryPercentage: 0.8,
            stack: 'e1',
            yAxisID: 'yValle'
          },
          {
            type: 'bar',
            label: 'Descanso E1',
            data: d1Data,
            backgroundColor: 'rgba(153, 27, 27, 0.90)',
            borderColor: '#b91c1c',
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.8,
            categoryPercentage: 0.8,
            stack: 'e1',
            yAxisID: 'yValle'
          },
          {
            type: 'bar',
            label: 'Valle E2 (min)',
            data: v2Data,
            backgroundColor: 'rgba(249, 115, 22, 0.75)',
            borderColor: '#f97316',
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.8,
            categoryPercentage: 0.8,
            stack: 'e2',
            yAxisID: 'yValle'
          },
          {
            type: 'bar',
            label: 'Descanso E2',
            data: d2Data,
            backgroundColor: 'rgba(153, 27, 27, 0.90)',
            borderColor: '#b91c1c',
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.8,
            categoryPercentage: 0.8,
            stack: 'e2',
            yAxisID: 'yValle'
          },
          {
            type: 'bar',
            label: 'Valle E3 (min)',
            data: v3Data,
            backgroundColor: 'rgba(59, 130, 246, 0.78)',
            borderColor: '#60a5fa',
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.8,
            categoryPercentage: 0.8,
            stack: 'e3',
            yAxisID: 'yValle'
          },
          {
            type: 'bar',
            label: 'Descanso E3',
            data: d3Data,
            backgroundColor: 'rgba(153, 27, 27, 0.90)',
            borderColor: '#b91c1c',
            borderWidth: 1,
            borderRadius: 4,
            barPercentage: 0.8,
            categoryPercentage: 0.8,
            stack: 'e3',
            yAxisID: 'yValle'
          }
        ];

        const ctx = canvasEl.getContext('2d');
        chartHistorialTurno = new Chart(ctx, {
          data: { labels: labels, datasets: datasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              legend: {
                display: true,
                position: 'top',
                labels: {
                  boxWidth: 12,
                  boxHeight: 10,
                  color: '#94a3b8',
                  font: { size: 10, family: 'Inter, system-ui, sans-serif' },
                  padding: 8,
                  filter: function(legendItem, chartData) {
                    if (legendItem.text === 'Descanso E2' || legendItem.text === 'Descanso E3') return false;
                    if (legendItem.text === 'Descanso E1') {
                      legendItem.text = 'Tiempo Descanso (min)';
                    }
                    return true;
                  }
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
                  text: 'Prendas por Entrada',
                  color: '#38bdf8',
                  font: { size: 10.5, weight: 'bold' }
                },
                grid: { color: 'rgba(56, 189, 248, 0.06)' },
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
                stacked: true,
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
      return;
    }
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
let currentFiltrosMachine = 'TUNEL_LAVADO';

function openMachineFiltros(maquinaId) {
  currentFiltrosMachine = maquinaId || 'TUNEL_LAVADO';
  const sel = document.getElementById('filtros-maquina-select');
  if (sel) sel.value = currentFiltrosMachine;
  updateFiltrosHeadersAndBackBtn();
  resetFiltrosView();
  switchView('filtros_turno');
  initFiltrosTurnoScreen();
}
window.openMachineFiltros = openMachineFiltros;

function volverDesdeFiltros() {
  if (currentFiltrosMachine === 'CALANDRA_2') {
    switchView('calandra_2');
  } else if (currentFiltrosMachine === 'CALANDRA_3') {
    switchView('calandra_3');
  } else if (currentFiltrosMachine === 'TUNEL_VT') {
    switchView('tunel_vt');
  } else {
    switchView('tunel_lavado');
  }
}
window.volverDesdeFiltros = volverDesdeFiltros;

function onFiltrosMachineChange() {
  const sel = document.getElementById('filtros-maquina-select');
  if (sel) currentFiltrosMachine = sel.value;
  updateFiltrosHeadersAndBackBtn();
  resetFiltrosView();
}
window.onFiltrosMachineChange = onFiltrosMachineChange;

function updateFiltrosHeadersAndBackBtn() {
  const btnText = document.getElementById('filtros-btn-volver-text');
  const title = document.getElementById('filtros-title');
  const subtitle = document.getElementById('filtros-turno-info');

  let machineName = 'Túnel de Lavado';
  let icon = '🌊';
  if (currentFiltrosMachine === 'CALANDRA_2') {
    machineName = 'Calandra 2';
    icon = '📄';
  } else if (currentFiltrosMachine === 'CALANDRA_3') {
    machineName = 'Calandra 3';
    icon = '👁️';
  } else if (currentFiltrosMachine === 'TUNEL_VT') {
    machineName = 'Túnel VT';
    icon = '👕';
  }

  if (btnText) btnText.textContent = `Volver a ${machineName}`;
  if (title) title.innerHTML = `<i class="fas fa-sliders-h" style="margin-right: 8px;"></i> Filtros y Totales por Período — ${icon} ${machineName}`;
  if (subtitle) {
    if (currentFiltrosMachine === 'TUNEL_LAVADO') {
      subtitle.textContent = 'Calcula y consolida los datos totales (Kg, Cargas, ikProd y Kg/Hora) concatenando los turnos del período seleccionado';
    } else {
      subtitle.textContent = `Calcula y consolida los datos totales de producción (Prendas, Kg, Tiempos Valle y Rendimiento Horario) concatenando los turnos del período para ${machineName}`;
    }
  }
}

let lastFiltrosPeriodoData = null;

function resetFiltrosView() {
  const placeholderSelect = document.getElementById('filtros-placeholder-select');
  const dashboardContainer = document.getElementById('filtros-dashboard-container');
  if (placeholderSelect) placeholderSelect.style.display = 'block';
  if (dashboardContainer) {
    dashboardContainer.style.display = 'none';
    dashboardContainer.innerHTML = '';
  }
  lastFiltrosPeriodoData = null;
  updateFiltrosPdfButtonState(false);
}

function initFiltrosTurnoScreen() {
  const sel = document.getElementById('filtros-maquina-select');
  if (sel && sel.value !== currentFiltrosMachine) {
    sel.value = currentFiltrosMachine;
  }
  updateFiltrosHeadersAndBackBtn();

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

  // Registrar listeners de cambio de filtros para bloquear botón PDF si se cambian los parámetros
  if (desdeFechaInput && !desdeFechaInput.dataset.pdfListenerAttached) {
    [desdeFechaInput, hastaFechaInput, desdeHoraInput, hastaHoraInput].forEach(inp => {
      if (inp) {
        inp.dataset.pdfListenerAttached = 'true';
        inp.addEventListener('change', () => {
          lastFiltrosPeriodoData = null;
          updateFiltrosPdfButtonState(false);
        });
      }
    });
  }

  updateFiltrosPdfButtonState(false);
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

  lastFiltrosPeriodoData = null;
  updateFiltrosPdfButtonState(false);

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

    const url = `/api/produccion/turnos/totales-periodo?maquina=${encodeURIComponent(currentFiltrosMachine)}&fecha_inicio=${encodeURIComponent(fechaDesde)}&hora_inicio=${encodeURIComponent(horaDesde)}&fecha_fin=${encodeURIComponent(fechaHasta)}&hora_fin=${encodeURIComponent(horaHasta)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Error al calcular totales del período');
    }
    const data = await res.json();

    if (!data.totales || data.totales.total_turnos === 0) {
      lastFiltrosPeriodoData = null;
      updateFiltrosPdfButtonState(false);
      dashboardContainer.innerHTML = `
        <div style="text-align: center; padding: 60px 20px; background: rgba(15, 23, 42, 0.7); border-radius: 14px; border: 1px dashed rgba(239, 68, 68, 0.4);">
          <i class="fas fa-info-circle" style="font-size: 3rem; color: #ef4444; opacity: 0.8; margin-bottom: 16px;"></i>
          <h4 style="color: #f8fafc; font-size: 1.3rem;">No se encontraron turnos en este período</h4>
          <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 8px;">No hay turnos registrados entre el ${data.ventana_solicitada.inicio_formateado} y el ${data.ventana_solicitada.fin_formateado}. Prueba ampliando el rango de fechas u horarios.</p>
        </div>
      `;
      return;
    }

    lastFiltrosPeriodoData = data;
    updateFiltrosPdfButtonState(true);

    if (currentFiltrosMachine === 'CALANDRA_2') {
      renderFiltrosCalandra2(data, dashboardContainer);
    } else if (currentFiltrosMachine === 'CALANDRA_3') {
      renderFiltrosCalandra3(data, dashboardContainer);
    } else if (currentFiltrosMachine === 'TUNEL_VT') {
      renderFiltrosTunelVT(data, dashboardContainer);
    } else {
      renderFiltrosTunelLavado(data, dashboardContainer);
    }
  } catch (err) {
    lastFiltrosPeriodoData = null;
    updateFiltrosPdfButtonState(false);
    console.error('Error calculando totales del período:', err);
    dashboardContainer.innerHTML = `<div style="color: var(--accent-red); padding: 20px; background: rgba(239,68,68,0.1); border-radius: 8px; border: 1px solid rgba(239,68,68,0.3);">⚠️ ${err.message}</div>`;
  }
}
window.applyFiltroPeriodo = applyFiltroPeriodo;

function renderFiltrosTunelLavado(data, dashboardContainer) {
  const t = data.totales;
  const v = data.ventana_solicitada;

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
}

function renderFiltrosCalandra2(data, dashboardContainer) {
  const t = data.totales;
  const v = data.ventana_solicitada;

  dashboardContainer.innerHTML = `
    <!-- Banner Superior Informativo -->
    <div style="background: rgba(15, 23, 42, 0.9); border: 1.5px solid #818cf8; padding: 14px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div style="width: 44px; height: 44px; border-radius: 10px; background: rgba(99, 102, 241, 0.2); color: #818cf8; display: flex; align-items: center; justify-content: center; font-size: 1.12rem; gap: 3px; border: 1px solid rgba(129, 140, 248, 0.3);">
          <i class="fas fa-scroll"></i><span style="font-weight: 800; font-size: 1.18rem; line-height: 1;">2</span>
        </div>
        <div>
          <h4 style="color: var(--text-main); font-size: 1.1rem; margin: 0;">Totales Consolidados del Período — Calandra 2</h4>
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
      <!-- 1. Prendas Totales -->
      <div class="kpi-card-striking kpi-card-cyan" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Prendas Totales del Período</h4>
          <div class="kpi-icon-circle"><i class="fas fa-tshirt"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_prendas_str}</div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 6px;">Gdes: ${t.total_grandes_str} (${t.pct_grandes}%)</span>
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); padding: 2px 8px; border-radius: 6px;">Peq: ${t.total_pequenas_str} (${t.pct_pequenas}%)</span>
        </div>
        <div class="kpi-card-subtext" style="margin-top: 8px;">Total piezas planchadas en los ${t.total_turnos} turnos</div>
      </div>

      <!-- 2. Kg Totales -->
      <div class="kpi-card-striking kpi-card-green" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Kg Totales del Período</h4>
          <div class="kpi-icon-circle"><i class="fas fa-weight-hanging"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_kg_str}</div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 6px;">Gdes: ${t.total_kg_grandes_str}</span>
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); padding: 2px 8px; border-radius: 6px;">Peq: ${t.total_kg_pequenas_str}</span>
        </div>
        <div class="kpi-card-subtext" style="margin-top: 8px;">Kilos calculados con pesos configurados por prenda</div>
      </div>

      <!-- 3. Tiempo Valle Total -->
      <div class="kpi-card-striking kpi-card-amber" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Tiempo Valle Total</h4>
          <div class="kpi-icon-circle"><i class="fas fa-stopwatch"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_tiempo_valle_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(251, 191, 36, 0.3);">
            <i class="fas fa-calculator"></i> ${t.promedio_valle_turno_str}
          </span>
        </div>
        <div class="kpi-card-subtext">Minutos acumulados en espera/valle en el período</div>
      </div>

      <!-- 4. Kg / Hora General -->
      <div class="kpi-card-striking calandra-card-kg-hora" style="margin: 0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
        <div class="kpi-card-header">
          <h4 style="color: #f8fafc;">Kg / Hora General</h4>
          <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-tachometer-alt"></i></div>
        </div>
        <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${t.kg_hora_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">
            <i class="fas fa-bolt"></i> Cadencia: ${t.prendas_hora_str}
          </span>
        </div>
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
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-chart-pie" style="color: #fbbf24;"></i> Mix de Prendas</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.pct_grandes}% <span style="font-size: 0.85rem; color: #94a3b8; font-weight: 600;">G /</span> ${t.pct_pequenas}% <span style="font-size: 0.85rem; color: #94a3b8; font-weight: 600;">P</span></div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Proporción grandes vs pequeñas</div>
      </div>

      <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-tachometer-alt" style="color: #34d399;"></i> Cadencia Media Horaria</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.prendas_hora_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Prendas procesadas por hora efectiva</div>
      </div>

      <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-calendar-day" style="color: #818cf8;"></i> Promedio por Turno</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.promedio_prendas_turno_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">${t.promedio_kg_turno_str} de media por turno</div>
      </div>
    </div>

    <!-- Fila 3: Tabla Detallada de Turnos Concatenados -->
    <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
        <div>
          <h4 style="color: #f8fafc; font-size: 1.1rem; margin: 0;"><i class="fas fa-list-check" style="color: #818cf8; margin-right: 8px;"></i> Turnos de Producción Concatenados — Calandra 2 (${t.total_turnos})</h4>
          <small style="color: #94a3b8; font-size: 0.8rem;">Detalle cronológico de los turnos sumados contiguamente en la ventana seleccionada</small>
        </div>
        <span style="font-size: 0.78rem; color: #94a3b8; background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 6px;">
          Fuente: calandra_2_turnos_persistencia
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
              <th style="padding: 10px 14px; text-align: right;">Prendas Totales</th>
              <th style="padding: 10px 14px; text-align: right;">Grandes</th>
              <th style="padding: 10px 14px; text-align: right;">Pequeñas</th>
              <th style="padding: 10px 14px; text-align: right;">Kg Totales</th>
              <th style="padding: 10px 14px; text-align: right;">Tiempo Valle</th>
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
                <td style="padding: 12px 14px; text-align: right; color: #38bdf8; font-weight: 700;">${item.prendas_totales_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #cbd5e1;">${item.prendas_grandes_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #cbd5e1;">${item.prendas_pequenas_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #34d399; font-weight: 700;">${item.total_kg_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #fbbf24; font-weight: 700;">${item.tiempo_valle_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #f8fafc; font-weight: 700;">${item.kg_hora_str}</td>
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr style="border-top: 2px solid rgba(129, 140, 248, 0.4); background: rgba(99, 102, 241, 0.08); font-weight: 800;">
              <td colspan="4" style="padding: 14px; color: #818cf8;">TOTALES CONSOLIDADOS (${t.total_turnos} turnos)</td>
              <td style="padding: 14px; color: #f8fafc;">${t.horas_efectivas_str}</td>
              <td style="padding: 14px; text-align: right; color: #38bdf8; font-size: 1rem;">${t.total_prendas_str}</td>
              <td style="padding: 14px; text-align: right; color: #cbd5e1; font-size: 0.9rem;">${t.total_grandes_str}</td>
              <td style="padding: 14px; text-align: right; color: #cbd5e1; font-size: 0.9rem;">${t.total_pequenas_str}</td>
              <td style="padding: 14px; text-align: right; color: #34d399; font-size: 1rem;">${t.total_kg_str}</td>
              <td style="padding: 14px; text-align: right; color: #fbbf24; font-size: 1rem;">${t.total_tiempo_valle_str}</td>
              <td style="padding: 14px; text-align: right; color: #f8fafc; font-size: 1rem;">${t.kg_hora_str}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;
}

function renderFiltrosCalandra3(data, dashboardContainer) {
  const t = data.totales;
  const v = data.ventana_solicitada;

  dashboardContainer.innerHTML = `
    <!-- Banner Superior Informativo -->
    <div style="background: rgba(15, 23, 42, 0.9); border: 1.5px solid #818cf8; padding: 14px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
        <div style="width: 44px; height: 44px; border-radius: 10px; background: rgba(99, 102, 241, 0.2); color: #818cf8; display: flex; align-items: center; justify-content: center; font-size: 1.12rem; gap: 3px; border: 1px solid rgba(129, 140, 248, 0.3);">
          <i class="fas fa-scroll"></i><span style="font-weight: 800; font-size: 1.18rem; line-height: 1;">3</span>
        </div>
        <div>
          <h4 style="color: var(--text-main); font-size: 1.1rem; margin: 0;">Totales Consolidados del Período — Calandra 3</h4>
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
      <!-- 1. Prendas Totales -->
      <div class="kpi-card-striking kpi-card-cyan" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Prendas Totales del Período</h4>
          <div class="kpi-icon-circle"><i class="fas fa-tshirt"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_prendas_str}</div>
        <div class="kpi-card-subtext">Total sábanas/piezas procesadas en los ${t.total_turnos} turnos</div>
      </div>

      <!-- 2. Kg Totales -->
      <div class="kpi-card-striking kpi-card-green" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Kg Totales del Período</h4>
          <div class="kpi-icon-circle"><i class="fas fa-weight-hanging"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_kg_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #34d399; background: rgba(52, 211, 153, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(52, 211, 153, 0.3);">
            <i class="fas fa-weight-hanging"></i> Peso Unitario: ${t.peso_unitario_str}
          </span>
        </div>
        <div class="kpi-card-subtext">Kilos calculados con peso unitario configurado</div>
      </div>

      <!-- 3. Tiempo Valle Total -->
      <div class="kpi-card-striking kpi-card-amber" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Tiempo Valle Total</h4>
          <div class="kpi-icon-circle"><i class="fas fa-stopwatch"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_tiempo_valle_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(251, 191, 36, 0.3);">
            <i class="fas fa-calculator"></i> ${t.promedio_valle_turno_str}
          </span>
        </div>
        <div class="kpi-card-subtext">Minutos acumulados en espera/valle en el período</div>
      </div>

      <!-- 4. Kg / Hora General -->
      <div class="kpi-card-striking calandra-card-kg-hora" style="margin: 0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
        <div class="kpi-card-header">
          <h4 style="color: #f8fafc;">Kg / Hora General</h4>
          <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-tachometer-alt"></i></div>
        </div>
        <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${t.kg_hora_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">
            <i class="fas fa-bolt"></i> Cadencia: ${t.prendas_hora_str}
          </span>
        </div>
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
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-balance-scale" style="color: #fbbf24;"></i> Peso Unitario</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.peso_unitario_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Configurado en Calandra 3</div>
      </div>

      <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-tachometer-alt" style="color: #34d399;"></i> Cadencia Media Horaria</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.prendas_hora_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Prendas procesadas por hora efectiva</div>
      </div>

      <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-calendar-day" style="color: #818cf8;"></i> Promedio por Turno</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.promedio_prendas_turno_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">${t.promedio_kg_turno_str} de media por turno</div>
      </div>
    </div>

    <!-- Fila 3: Tabla Detallada de Turnos Concatenados -->
    <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
        <div>
          <h4 style="color: #f8fafc; font-size: 1.1rem; margin: 0;"><i class="fas fa-list-check" style="color: #818cf8; margin-right: 8px;"></i> Turnos de Producción Concatenados — Calandra 3 (${t.total_turnos})</h4>
          <small style="color: #94a3b8; font-size: 0.8rem;">Detalle cronológico de los turnos sumados contiguamente en la ventana seleccionada</small>
        </div>
        <span style="font-size: 0.78rem; color: #94a3b8; background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 6px;">
          Fuente: calandra_3_turnos_persistencia
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
              <th style="padding: 10px 14px; text-align: right;">Prendas Totales</th>
              <th style="padding: 10px 14px; text-align: right;">Kg Totales</th>
              <th style="padding: 10px 14px; text-align: right;">Tiempo Valle</th>
              <th style="padding: 10px 14px; text-align: right;">Prendas / Hora</th>
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
                <td style="padding: 12px 14px; text-align: right; color: #38bdf8; font-weight: 700;">${item.prendas_totales_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #34d399; font-weight: 700;">${item.total_kg_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #fbbf24; font-weight: 700;">${item.tiempo_valle_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #cbd5e1; font-weight: 700;">${item.prendas_hora_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #f8fafc; font-weight: 700;">${item.kg_hora_str}</td>
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr style="border-top: 2px solid rgba(129, 140, 248, 0.4); background: rgba(99, 102, 241, 0.08); font-weight: 800;">
              <td colspan="4" style="padding: 14px; color: #818cf8;">TOTALES CONSOLIDADOS (${t.total_turnos} turnos)</td>
              <td style="padding: 14px; color: #f8fafc;">${t.horas_efectivas_str}</td>
              <td style="padding: 14px; text-align: right; color: #38bdf8; font-size: 1rem;">${t.total_prendas_str}</td>
              <td style="padding: 14px; text-align: right; color: #34d399; font-size: 1rem;">${t.total_kg_str}</td>
              <td style="padding: 14px; text-align: right; color: #fbbf24; font-size: 1rem;">${t.total_tiempo_valle_str}</td>
              <td style="padding: 14px; text-align: right; color: #cbd5e1; font-size: 1rem;">${t.prendas_hora_str}</td>
              <td style="padding: 14px; text-align: right; color: #f8fafc; font-size: 1rem;">${t.kg_hora_str}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;
}

function renderFiltrosTunelVT(data, dashboardContainer) {
  const t = data.totales;
  const v = data.ventana_solicitada;

  dashboardContainer.innerHTML = `
    <!-- Banner Superior Informativo -->
    <div style="background: rgba(15, 23, 42, 0.9); border: 1.5px solid #818cf8; padding: 14px 20px; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; gap: 14px;">
      <div style="display: flex; align-items: center; gap: 14px;">
        <div style="width: 44px; height: 44px; border-radius: 10px; background: rgba(99, 102, 241, 0.2); color: #818cf8; display: flex; align-items: center; justify-content: center; font-size: 1.4rem;">
          <i class="fas fa-wind"></i>
        </div>
        <div>
          <h4 style="color: var(--text-main); font-size: 1.1rem; margin: 0;">Totales Consolidados del Período — Túnel VT</h4>
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
      <!-- 1. Prendas Totales -->
      <div class="kpi-card-striking kpi-card-cyan" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Prendas Totales del Período</h4>
          <div class="kpi-icon-circle"><i class="fas fa-tshirt"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_prendas_str}</div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 6px;">E1: ${t.total_e1_str} (${t.pct_e1}%)</span>
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); padding: 2px 8px; border-radius: 6px;">E2: ${t.total_e2_str} (${t.pct_e2}%)</span>
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(192, 132, 252, 0.15); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.3); padding: 2px 8px; border-radius: 6px;">E3: ${t.total_e3_str} (${t.pct_e3}%)</span>
        </div>
        <div class="kpi-card-subtext" style="margin-top: 8px;">Total prendas procesadas por las 3 vías en los ${t.total_turnos} turnos</div>
      </div>

      <!-- 2. Kg Totales -->
      <div class="kpi-card-striking kpi-card-green" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Kg Totales del Período</h4>
          <div class="kpi-icon-circle"><i class="fas fa-weight-hanging"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_kg_str}</div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 6px;">E1: ${t.kg_e1_str}</span>
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); padding: 2px 8px; border-radius: 6px;">E2: ${t.kg_e2_str}</span>
          <span style="font-size: 0.76rem; font-weight: 700; background: rgba(192, 132, 252, 0.15); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.3); padding: 2px 8px; border-radius: 6px;">E3: ${t.kg_e3_str}</span>
        </div>
        <div class="kpi-card-subtext" style="margin-top: 8px;">Kilos calculados con peso unitario (${t.peso_unitario_str})</div>
      </div>

      <!-- 3. Tiempo Valle Total -->
      <div class="kpi-card-striking kpi-card-amber" style="margin: 0;">
        <div class="kpi-card-header">
          <h4>Tiempo Valle Total</h4>
          <div class="kpi-icon-circle"><i class="fas fa-stopwatch"></i></div>
        </div>
        <div class="kpi-big-number">${t.total_tiempo_valle_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #fbbf24; background: rgba(251, 191, 36, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(251, 191, 36, 0.3);">
            <i class="fas fa-calculator"></i> ${t.promedio_valle_turno_str}
          </span>
        </div>
        <div class="kpi-card-subtext">Minutos acumulados en espera/valle en el período</div>
      </div>

      <!-- 4. Kg / Hora General -->
      <div class="kpi-card-striking calandra-card-kg-hora" style="margin: 0; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #818cf8; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);">
        <div class="kpi-card-header">
          <h4 style="color: #f8fafc;">Kg / Hora General</h4>
          <div class="kpi-icon-circle" style="background: rgba(129, 140, 248, 0.15); color: #818cf8;"><i class="fas fa-tachometer-alt"></i></div>
        </div>
        <div class="kpi-big-number" style="font-size: 2.5rem; font-weight: 900; color: #818cf8; text-shadow: 0 0 16px rgba(129, 140, 248, 0.4);">${t.kg_hora_str}</div>
        <div style="display: flex; gap: 6px; justify-content: center; align-items: center; margin-top: 4px; margin-bottom: 4px;">
          <span style="font-size: 0.78rem; font-weight: 700; color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">
            <i class="fas fa-bolt"></i> Cadencia: ${t.prendas_hora_str}
          </span>
        </div>
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
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-chart-pie" style="color: #fbbf24;"></i> Mix por Entradas</div>
        <div style="font-size: 1.25rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">E1: ${t.pct_e1}% | E2: ${t.pct_e2}% | E3: ${t.pct_e3}%</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Distribución de carga entre vías</div>
      </div>

      <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-tachometer-alt" style="color: #34d399;"></i> Cadencia Media Horaria</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.prendas_hora_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">Prendas procesadas por hora efectiva</div>
      </div>

      <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600;"><i class="fas fa-calendar-day" style="color: #818cf8;"></i> Promedio por Turno</div>
        <div style="font-size: 1.4rem; font-weight: 800; color: #f8fafc; margin-top: 4px;">${t.promedio_prendas_turno_str}</div>
        <div style="font-size: 0.74rem; color: #64748b; margin-top: 2px;">${t.promedio_kg_turno_str} de media por turno</div>
      </div>
    </div>

    <!-- Fila 3: Tabla Detallada de Turnos Concatenados -->
    <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px;">
        <div>
          <h4 style="color: #f8fafc; font-size: 1.1rem; margin: 0;"><i class="fas fa-list-check" style="color: #818cf8; margin-right: 8px;"></i> Turnos de Producción Concatenados — Túnel VT (${t.total_turnos})</h4>
          <small style="color: #94a3b8; font-size: 0.8rem;">Detalle cronológico de los turnos sumados contiguamente en la ventana seleccionada</small>
        </div>
        <span style="font-size: 0.78rem; color: #94a3b8; background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 6px;">
          Fuente: tunel_vt_turnos_persistencia
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
              <th style="padding: 10px 14px; text-align: right;">Prendas Totales</th>
              <th style="padding: 10px 14px; text-align: right;">E1</th>
              <th style="padding: 10px 14px; text-align: right;">E2</th>
              <th style="padding: 10px 14px; text-align: right;">E3</th>
              <th style="padding: 10px 14px; text-align: right;">Kg Totales</th>
              <th style="padding: 10px 14px; text-align: right;">Tiempo Valle</th>
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
                <td style="padding: 12px 14px; text-align: right; color: #38bdf8; font-weight: 700;">${item.prendas_totales_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #cbd5e1;">${item.entrada_1_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #cbd5e1;">${item.entrada_2_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #cbd5e1;">${item.entrada_3_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #34d399; font-weight: 700;">${item.total_kg_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #fbbf24; font-weight: 700;">${item.tiempo_valle_str}</td>
                <td style="padding: 12px 14px; text-align: right; color: #f8fafc; font-weight: 700;">${item.kg_hora_str}</td>
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr style="border-top: 2px solid rgba(129, 140, 248, 0.4); background: rgba(99, 102, 241, 0.08); font-weight: 800;">
              <td colspan="4" style="padding: 14px; color: #818cf8;">TOTALES CONSOLIDADOS (${t.total_turnos} turnos)</td>
              <td style="padding: 14px; color: #f8fafc;">${t.horas_efectivas_str}</td>
              <td style="padding: 14px; text-align: right; color: #38bdf8; font-size: 1rem;">${t.total_prendas_str}</td>
              <td style="padding: 14px; text-align: right; color: #cbd5e1; font-size: 0.9rem;">${t.total_e1_str}</td>
              <td style="padding: 14px; text-align: right; color: #cbd5e1; font-size: 0.9rem;">${t.total_e2_str}</td>
              <td style="padding: 14px; text-align: right; color: #cbd5e1; font-size: 0.9rem;">${t.total_e3_str}</td>
              <td style="padding: 14px; text-align: right; color: #34d399; font-size: 1rem;">${t.total_kg_str}</td>
              <td style="padding: 14px; text-align: right; color: #fbbf24; font-size: 1rem;">${t.total_tiempo_valle_str}</td>
              <td style="padding: 14px; text-align: right; color: #f8fafc; font-size: 1rem;">${t.kg_hora_str}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;
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

/* ==========================================================================
   MÓDULO: INFORME PDF DE PRODUCCIÓN (TÚNEL DE LAVADO, CALANDRA 2 Y 3, TÚNEL VT)
   ========================================================================== */

function getFiltrosMachineMeta(machineCode) {
  switch (machineCode) {
    case 'CALANDRA_2':
      return { code: 'CALANDRA_2', title: 'INFORME DE PRODUCCIÓN CALANDRA 2', shortName: 'Calandra 2', tag: 'Calandra_2' };
    case 'CALANDRA_3':
      return { code: 'CALANDRA_3', title: 'INFORME DE PRODUCCIÓN CALANDRA 3', shortName: 'Calandra 3', tag: 'Calandra_3' };
    case 'TUNEL_VT':
      return { code: 'TUNEL_VT', title: 'INFORME DE PRODUCCIÓN TÚNEL VT', shortName: 'Túnel VT', tag: 'Tunel_VT' };
    case 'TUNEL_LAVADO':
    default:
      return { code: 'TUNEL_LAVADO', title: 'INFORME DE PRODUCCIÓN TÚNEL DE LAVADO', shortName: 'Túnel de Lavado', tag: 'Tunel_Lavado' };
  }
}

function updateFiltrosPdfButtonState(enabled) {
  const btn = document.getElementById('filtros-btn-pdf');
  if (!btn) return;
  if (enabled && lastFiltrosPeriodoData) {
    btn.disabled = false;
    btn.style.cursor = 'pointer';
    btn.style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    btn.style.color = '#ffffff';
    btn.style.border = '1px solid #ef4444';
    btn.style.boxShadow = '0 4px 14px rgba(239, 68, 68, 0.4)';
    btn.title = 'Generar y previsualizar Informe PDF de producción';
  } else {
    btn.disabled = true;
    btn.style.cursor = 'not-allowed';
    btn.style.background = 'rgba(148, 163, 184, 0.15)';
    btn.style.color = '#64748b';
    btn.style.border = '1px solid rgba(148, 163, 184, 0.25)';
    btn.style.boxShadow = 'none';
    btn.title = 'Calcula totales primero para habilitar el informe PDF';
  }
}
window.updateFiltrosPdfButtonState = updateFiltrosPdfButtonState;

let currentInformePdfType = 'produccion';
window.currentInformePdfType = currentInformePdfType;

function openInformePdfModal() {
  if (!lastFiltrosPeriodoData) {
    alert('Primero debes calcular los totales del período para generar el informe PDF.');
    return;
  }
  window.currentInformePdfType = 'produccion';
  const modal = document.getElementById('modal-informe-pdf');
  const paper = document.getElementById('informe-pdf-paper');
  if (!modal || !paper) return;

  const html = buildInformePdfHtml(lastFiltrosPeriodoData);
  paper.innerHTML = html;

  const machineCode = (lastFiltrosPeriodoData && lastFiltrosPeriodoData.maquina) || currentFiltrosMachine || 'TUNEL_LAVADO';
  const meta = getFiltrosMachineMeta(machineCode);
  const headerTitle = document.getElementById('modal-pdf-header-title');
  if (headerTitle) {
    headerTitle.textContent = `Vista Previa — ${meta.title}`;
  }
  const headerSub = document.getElementById('modal-pdf-header-subtitle');
  if (headerSub) {
    headerSub.textContent = 'Documento ejecutivo para impresión y descarga en PDF';
  }

  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
window.openInformePdfModal = openInformePdfModal;

function openInformePdfConsumoModal() {
  if (!window.lastConsumoGraficaData) {
    alert('No hay datos de consumo disponibles para generar el informe.');
    return;
  }
  window.currentInformePdfType = 'consumos';
  const modal = document.getElementById('modal-informe-pdf');
  const paper = document.getElementById('informe-pdf-paper');
  if (!modal || !paper) return;

  // Extraer imagen del canvas de la gráfica activa
  let chartImg = '';
  try {
    if (window.procesoGraficaChart && typeof window.procesoGraficaChart.toBase64Image === 'function') {
      chartImg = window.procesoGraficaChart.toBase64Image('image/png', 1.0);
    } else {
      const cvs = document.getElementById('canvas-proceso-grafica');
      if (cvs) chartImg = cvs.toDataURL('image/png');
    }
  } catch (e) {
    console.warn('No se pudo extraer imagen del gráfico para el PDF:', e);
  }

  const html = buildInformePdfConsumoHtml(window.lastConsumoGraficaData, chartImg);
  paper.innerHTML = html;

  let reportTitle = (window.lastConsumoGraficaData.titulo || 'Informe de Consumo').trim();
  const tUpper = reportTitle.toUpperCase();
  if (tUpper === 'GAS GENERAL HOY' || tUpper === 'GAS GENERAL' || window.lastConsumoGraficaData.varCode === 'sensor_gas_general') {
    reportTitle = 'INFORME DE CONSUMO DE GAS';
  } else if (!reportTitle.toUpperCase().startsWith('INFORME')) {
    reportTitle = `INFORME DE CONSUMO: ${reportTitle}`;
  }

  const headerTitle = document.getElementById('modal-pdf-header-title');
  if (headerTitle) {
    headerTitle.textContent = `Vista Previa — ${reportTitle}`;
  }
  const headerSub = document.getElementById('modal-pdf-header-subtitle');
  if (headerSub) {
    headerSub.textContent = 'Documento ejecutivo de telemetría y consumos para impresión y descarga en PDF';
  }

  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}
window.openInformePdfConsumoModal = openInformePdfConsumoModal;

function closeInformePdfModal() {
  const modal = document.getElementById('modal-informe-pdf');
  if (modal) {
    modal.style.display = 'none';
  }
  document.body.style.overflow = 'auto';
}
window.closeInformePdfModal = closeInformePdfModal;

function imprimirInformePdf() {
  window.print();
}
window.imprimirInformePdf = imprimirInformePdf;

async function descargarInformePdf() {
  const paper = document.getElementById('informe-pdf-paper');
  const btnDescargar = document.getElementById('modal-pdf-btn-descargar');
  if (!paper) return;

  let filename = '';
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');

  if (window.currentInformePdfType === 'consumos') {
    const cData = window.lastConsumoGraficaData || {};
    let safeTitle = (cData.titulo || 'Consumo').trim();
    const tUpper = safeTitle.toUpperCase();
    if (tUpper === 'GAS GENERAL HOY' || tUpper === 'GAS GENERAL' || cData.varCode === 'sensor_gas_general') {
      safeTitle = 'CONSUMO_DE_GAS';
    } else {
      safeTitle = safeTitle.replace(/[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ_]/g, '_');
    }
    filename = `Informe_${safeTitle}_${yyyy}${mm}${dd}.pdf`;
  } else {
    const machineCode = (lastFiltrosPeriodoData && lastFiltrosPeriodoData.maquina) || currentFiltrosMachine || 'TUNEL_LAVADO';
    const meta = getFiltrosMachineMeta(machineCode);
    filename = `Informe_Produccion_${meta.tag}_${yyyy}${mm}${dd}.pdf`;
  }

  if (typeof html2pdf === 'undefined') {
    alert('La biblioteca de exportación PDF no está disponible. Abriendo diálogo de impresión...');
    window.print();
    return;
  }

  const originalContent = btnDescargar ? btnDescargar.innerHTML : '';
  if (btnDescargar) {
    btnDescargar.disabled = true;
    btnDescargar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Generando PDF...</span>';
  }

  const opt = {
    margin: [6, 6, 6, 6],
    filename: filename,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, logging: false },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };

  try {
    await html2pdf().set(opt).from(paper).save();
  } catch (err) {
    console.error('Error generando PDF con html2pdf:', err);
    alert('Ocurrió un error al generar el archivo PDF. Usando impresión nativa...');
    window.print();
  } finally {
    if (btnDescargar) {
      btnDescargar.disabled = false;
      btnDescargar.innerHTML = originalContent;
    }
  }
}
window.descargarInformePdf = descargarInformePdf;


function buildInformePdfConsumoHtml(cData, chartImg) {
  const hoy = new Date();
  const fechaHoyStr = hoy.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
  const horaHoyStr = hoy.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit'
  });

  const displayRegistros = (cData.registros || []).slice(0, 100);

  let reportTitle = (cData.titulo || 'Informe de Consumo').trim();
  const tUpper = reportTitle.toUpperCase();
  if (tUpper === 'GAS GENERAL HOY' || tUpper === 'GAS GENERAL' || cData.varCode === 'sensor_gas_general') {
    reportTitle = 'INFORME DE CONSUMO DE GAS';
  }

  return `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.4; font-size: 9.5pt;">
      <!-- ENCABEZADO -->
      <div style="border-bottom: 2.5px solid #1e3a8a; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <img src="/static/images/elis_logo.png" style="height: 48px; max-width: 130px; object-fit: contain;" alt="Elis Logo" onerror="this.style.display='none'">
          <div>
            <h1 style="margin: 0; font-size: 15pt; font-weight: 800; color: #1e3a8a; letter-spacing: -0.3px; text-transform: uppercase;">
              ${reportTitle}
            </h1>
            <div style="font-size: 8.5pt; color: #475569; font-weight: 600; margin-top: 2px;">
              Planta Nájera &bull; Sistema de Monitorización Industrial 4.0 &bull; Control de Consumos
            </div>
          </div>
        </div>
        <div style="text-align: right; font-size: 8.5pt; color: #334155;">
          <div style="font-weight: 700; color: #0f172a;">FECHA: <span style="color: #1e3a8a;">${fechaHoyStr}</span></div>
          <div style="color: #64748b; font-size: 7.5pt; margin-top: 1px;">Hora emisión: ${horaHoyStr}</div>
          <div style="display: inline-block; background: #e0e7ff; color: #3730a3; padding: 2px 7px; border-radius: 4px; font-weight: 700; font-size: 7.5pt; margin-top: 3px;">
            VARIABLE: ${cData.varCode}
          </div>
        </div>
      </div>

      <!-- RANGO DE FECHA DEL INFORME -->
      <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #0284c7; border-radius: 6px; padding: 8px 14px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
          <span style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">Rango de Fecha Consultado:</span>
          <div style="font-size: 9.5pt; font-weight: 700; color: #0f172a; margin-top: 1px;">
            <span>${cData.fechaInicio || 'Inicio'} ${cData.horaInicio || '00:00'}</span>
            <span style="color: #64748b; margin: 0 8px;">&rarr;</span>
            <span>${cData.fechaFin || 'Fin'} ${cData.horaFin || '23:59'}</span>
          </div>
        </div>
        <div style="font-size: 8.5pt; color: #475569; font-weight: 600;">
          Total registros evaluados: <strong style="color: #0f172a;">${(cData.totalRegistros || 0).toLocaleString('es-ES')}</strong>
        </div>
      </div>

      <!-- TARJETAS DE INDICADORES DEL RANGO -->
      <div style="margin-bottom: 16px;">
        <div style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
          Indicadores del Rango Consultado
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
          <!-- 1. Consumo Acumulado -->
          <div style="background: #eff6ff; border: 1.5px solid #93c5fd; border-radius: 8px; padding: 10px; text-align: center;">
            <div style="font-size: 8pt; font-weight: 700; color: #1d4ed8; text-transform: uppercase;">Consumo Acumulado</div>
            <div style="font-size: 15pt; font-weight: 900; color: #1e40af; margin: 2px 0;">
              ${cData.acumuladoStr} <span style="font-size: 9pt;">${cData.unidad}</span>
            </div>
            <div style="font-size: 7.2pt; color: #1e3a8a; font-weight: 700;">
              ${cData.isElectric ? (cData.kvahStr.replace('|', '').trim() || 'Acometida Eléctrica') : (cData.isGas ? (cData.kwhStr.replace('|', '').trim() || 'Gas Natural') : 'Consumo Medido')}
            </div>
          </div>

          <!-- 2. Pulsos / Lecturas -->
          <div style="background: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 10px; text-align: center;">
            <div style="font-size: 8pt; font-weight: 700; color: #b45309; text-transform: uppercase;">Total Pulsos / Lecturas</div>
            <div style="font-size: 15pt; font-weight: 900; color: #92400e; margin: 2px 0;">
              ${(cData.totalPulsos || 0).toLocaleString('es-ES')}
            </div>
            <div style="font-size: 7.2pt; color: #78350f; font-weight: 600;">
              Eventos de telemetría registrados
            </div>
          </div>

          <!-- 3. Registros en Base de Datos -->
          <div style="background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 8px; padding: 10px; text-align: center;">
            <div style="font-size: 8pt; font-weight: 700; color: #15803d; text-transform: uppercase;">Registros Evaluados</div>
            <div style="font-size: 15pt; font-weight: 900; color: #166534; margin: 2px 0;">
              ${(cData.totalRegistros || 0).toLocaleString('es-ES')}
            </div>
            <div style="font-size: 7.2pt; color: #14532d; font-weight: 600;">
              ${displayRegistros.length} incluidos en tabla
            </div>
          </div>

          <!-- 4. Indicador Técnico / Energético -->
          <div style="background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 8px; padding: 10px; text-align: center;">
            <div style="font-size: 8pt; font-weight: 700; color: #7e22ce; text-transform: uppercase;">
              ${cData.isElectric ? 'Potencia Aparente' : (cData.isGas ? 'Equiv. Energético' : 'Variable')}
            </div>
            <div style="font-size: 14pt; font-weight: 900; color: #6b21a8; margin: 2px 0;">
              ${cData.isElectric ? (cData.kvahStr.replace('|', '').trim() || '--') : (cData.isGas ? `${Math.round((cData.acumulado || 0) * 11.68).toLocaleString('es-ES')} kWh` : cData.varCode)}
            </div>
            <div style="font-size: 7.2pt; color: #581c87; font-weight: 700;">
              ${cData.isElectric ? 'FP Estimado: ~0.90' : (cData.isGas ? 'PCS: 11.68 kWh/m³' : 'Telemetría de Proceso')}
            </div>
          </div>
        </div>
      </div>

      <!-- GRÁFICA DE CONSUMO -->
      ${chartImg ? `
        <div style="margin-bottom: 16px; page-break-inside: avoid;">
          <div style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
            <span>Gráfica de Consumo por Intervalo y Tendencia Acumulada</span>
            <span style="font-size: 7.2pt; color: #64748b; font-weight: normal;">Visualización cronológica</span>
          </div>
          <div style="background: #0f172a; border: 1.5px solid #334155; border-radius: 8px; padding: 10px; text-align: center;">
            <img src="${chartImg}" style="width: 100%; max-height: 250px; object-fit: contain; display: block; margin: 0 auto;" alt="Gráfica de Consumo">
          </div>
        </div>
      ` : ''}

      <!-- TABLA DETALLADA DE ÚLTIMOS 100 REGISTROS -->
      <div style="margin-bottom: 12px;">
        <div style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
          <span>Tabla de Telemetría (Mostrando últimos ${displayRegistros.length} de ${(cData.totalRegistros || 0).toLocaleString('es-ES')} registros)</span>
          <span style="font-size: 7.2pt; color: #94a3b8; font-weight: normal;">Orden cronológico</span>
        </div>

        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 7.2pt;">
          <thead>
            <tr style="background: #1e3a8a; border-top: 1px solid #1e3a8a; border-bottom: 1.5px solid #172554; color: #ffffff; font-size: 7.0pt; text-transform: uppercase; font-weight: 800;">
              <th style="padding: 5px 6px; width: 28px; text-align: center;">#</th>
              <th style="padding: 5px 6px;">Timestamp</th>
              ${cData.isElectric ? `
                <th style="padding: 5px 6px; text-align: right;">I. Acum (Ah)</th>
                <th style="padding: 5px 6px; text-align: right;">Pot. Acum (${cData.unidad})</th>
                <th style="padding: 5px 6px; text-align: right;">Delta (${cData.unidad})</th>
                <th style="padding: 5px 6px;">Dispositivo / Sensor</th>
              ` : (cData.isGas ? `
                <th style="padding: 5px 6px; text-align: right;">Pulsos</th>
                <th style="padding: 5px 6px; text-align: right;">Volumen (${cData.unidad})</th>
                <th style="padding: 5px 6px; text-align: right;">Potencia (kWh)</th>
                <th style="padding: 5px 6px; text-align: right;">Delta (m³)</th>
                <th style="padding: 5px 6px; text-align: right;">Caudal (m³/h)</th>
                <th style="padding: 5px 6px;">Dispositivo / Fuente</th>
              ` : `
                <th style="padding: 5px 6px; text-align: right;">Pulsos</th>
                <th style="padding: 5px 6px; text-align: right;">Volumen (${cData.unidad})</th>
                <th style="padding: 5px 6px; text-align: right;">Caudal (m³/h)</th>
                <th style="padding: 5px 6px;">Dispositivo / Fuente</th>
              `)}
            </tr>
          </thead>
          <tbody>
            ${displayRegistros.map((r, idx) => {
              const bg = (idx % 2 === 1) ? 'background: #f8fafc;' : 'background: #ffffff;';
              if (cData.isElectric) {
                const ah = (r.corriente_acumulada_ah !== undefined && r.corriente_acumulada_ah !== null ? r.corriente_acumulada_ah : 0).toLocaleString('es-ES');
                const pAcum = (r.potencia_acumulada_kwh !== undefined && r.potencia_acumulada_kwh !== null ? r.potencia_acumulada_kwh : (r.valor || 0)).toLocaleString('es-ES');
                const dVal = (r.delta_potencia_kwh !== undefined && r.delta_potencia_kwh !== null) ? Number(r.delta_potencia_kwh) : 0;
                const deltaStr = dVal > 0 ? `+${dVal.toLocaleString('es-ES')}` : '-';
                return `
                  <tr style="border-bottom: 1px solid #e2e8f0; ${bg} page-break-inside: avoid;">
                    <td style="padding: 4px 6px; font-weight: 700; color: #64748b; text-align: center;">${idx + 1}</td>
                    <td style="padding: 4px 6px; font-family: monospace; font-size: 6.8pt; color: #0f172a;">${r.timestamp || r.timestamp_iso || '-'}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #0284c7; font-weight: 600;">${ah}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #166534; font-weight: 700;">${pAcum}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #b45309; font-weight: 700;">${deltaStr}</td>
                    <td style="padding: 4px 6px; color: #475569; font-size: 6.8pt;">${r.dispositivo || '-'}</td>
                  </tr>
                `;
              } else if (cData.isGas) {
                const vol = (r.valor !== undefined && r.valor !== null ? r.valor : 0).toLocaleString('es-ES');
                const kwh = (r.kwh !== undefined && r.kwh !== null ? r.kwh : Math.round((r.valor || 0) * 11.68)).toLocaleString('es-ES');
                const dVal = (r.delta_m3 !== undefined && r.delta_m3 !== null) ? Number(r.delta_m3) : 0;
                const deltaStr = dVal > 0 ? `+${dVal.toLocaleString('es-ES')}` : '-';
                const caudal = (r.caudal_m3h !== undefined && r.caudal_m3h !== null ? r.caudal_m3h : 0).toLocaleString('es-ES');
                return `
                  <tr style="border-bottom: 1px solid #e2e8f0; ${bg} page-break-inside: avoid;">
                    <td style="padding: 4px 6px; font-weight: 700; color: #64748b; text-align: center;">${idx + 1}</td>
                    <td style="padding: 4px 6px; font-family: monospace; font-size: 6.8pt; color: #0f172a;">${r.timestamp || r.timestamp_iso || '-'}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #64748b;">${(r.pulsos || 0).toLocaleString('es-ES')}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #0f172a; font-weight: 700;">${vol}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #166534; font-weight: 700;">${kwh}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #0284c7; font-weight: 700;">${deltaStr}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #b45309; font-weight: 600;">${caudal}</td>
                    <td style="padding: 4px 6px; color: #475569; font-size: 6.8pt;">${r.dispositivo || '-'}</td>
                  </tr>
                `;
              } else {
                const vol = (r.valor !== undefined && r.valor !== null ? r.valor : 0).toLocaleString('es-ES');
                const caudal = (r.caudal_m3h !== undefined && r.caudal_m3h !== null ? r.caudal_m3h : 0).toLocaleString('es-ES');
                return `
                  <tr style="border-bottom: 1px solid #e2e8f0; ${bg} page-break-inside: avoid;">
                    <td style="padding: 4px 6px; font-weight: 700; color: #64748b; text-align: center;">${idx + 1}</td>
                    <td style="padding: 4px 6px; font-family: monospace; font-size: 6.8pt; color: #0f172a;">${r.timestamp || r.timestamp_iso || '-'}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #64748b;">${(r.pulsos || 0).toLocaleString('es-ES')}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #0f172a; font-weight: 700;">${vol}</td>
                    <td style="padding: 4px 6px; text-align: right; color: #0284c7; font-weight: 600;">${caudal}</td>
                    <td style="padding: 4px 6px; color: #475569; font-size: 6.8pt;">${r.dispositivo || '-'}</td>
                  </tr>
                `;
              }
            }).join('')}
          </tbody>
        </table>
      </div>

      <!-- PIE DE PÁGINA -->
      <div style="border-top: 1px solid #cbd5e1; padding-top: 8px; margin-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 7.2pt; color: #94a3b8;">
        <div>Elis Manomatic &bull; Departamento de Mantenimiento y Gestión Energética &bull; Planta Nájera</div>
        <div>Documento generado automáticamente &bull; Sistema Elis 4.0</div>
      </div>
    </div>
  `;
}
window.buildInformePdfConsumoHtml = buildInformePdfConsumoHtml;

function buildInformePdfHtml(data) {
  const t = data.totales || {};
  const v = data.ventana_solicitada || {};
  const turnos = data.turnos_concatenados || [];
  const machineCode = data.maquina || currentFiltrosMachine || 'TUNEL_LAVADO';
  const meta = getFiltrosMachineMeta(machineCode);

  const isLavado = meta.code === 'TUNEL_LAVADO';
  const isC2 = meta.code === 'CALANDRA_2';
  const isC3 = meta.code === 'CALANDRA_3';
  const isVT = meta.code === 'TUNEL_VT';

  // Fecha actual de emisión del informe DD/MM/YYYY
  const hoy = new Date();
  const fechaHoyStr = hoy.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
  const horaHoyStr = hoy.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit'
  });

  // Cálculo de análisis por turno y por jornada
  const turnosMap = {};
  const jornadasMap = {};

  turnos.forEach(item => {
    const tn = item.nombre_turno || 'Sin Turno';
    if (!turnosMap[tn]) {
      turnosMap[tn] = { nombre: tn, count: 0, prendas: 0, cargas: 0, kg: 0.0, horas: 0.0, valle: 0.0, ikprod_sum: 0.0 };
    }
    turnosMap[tn].count += 1;
    turnosMap[tn].prendas += Number(item.prendas_totales || 0);
    turnosMap[tn].cargas += Number(item.total_cargas || 0);
    turnosMap[tn].kg += Number(item.total_kg || 0);
    turnosMap[tn].horas += Number(item.duracion_horas || 0);
    turnosMap[tn].valle += Number(item.tiempo_valle_min || 0);
    turnosMap[tn].ikprod_sum += Number(item.ikprod || 0);

    const f = item.fecha_formateada || item.fecha || 'Sin Fecha';
    if (!jornadasMap[f]) {
      jornadasMap[f] = { fecha: f, count: 0, prendas: 0, cargas: 0, kg: 0.0, horas: 0.0, valle: 0.0, ikprod_sum: 0.0 };
    }
    jornadasMap[f].count += 1;
    jornadasMap[f].prendas += Number(item.prendas_totales || 0);
    jornadasMap[f].cargas += Number(item.total_cargas || 0);
    jornadasMap[f].kg += Number(item.total_kg || 0);
    jornadasMap[f].horas += Number(item.duracion_horas || 0);
    jornadasMap[f].valle += Number(item.tiempo_valle_min || 0);
    jornadasMap[f].ikprod_sum += Number(item.ikprod || 0);
  });

  const turnosStats = Object.values(turnosMap).map(vItem => ({
    ...vItem,
    kg_hora_num: vItem.horas > 0 ? (vItem.kg / vItem.horas) : 0,
    kg_hora: vItem.horas > 0 ? (vItem.kg / vItem.horas).toFixed(1) : '0.0',
    prendas_hora: vItem.horas > 0 ? Math.round(vItem.prendas / vItem.horas) : 0,
    cargas_turno: Math.round(vItem.cargas / (vItem.count || 1)),
    ikprod_prom: (vItem.ikprod_sum / (vItem.count || 1)).toFixed(1),
    prom_prendas: Math.round(vItem.prendas / (vItem.count || 1)),
    prom_kg: (vItem.kg / (vItem.count || 1)).toFixed(1),
    prom_valle: (vItem.valle / (vItem.count || 1)).toFixed(1)
  })).sort((a, b) => b.kg_hora_num - a.kg_hora_num);

  const jornadasStats = Object.values(jornadasMap).map(jItem => ({
    ...jItem,
    kg_hora_num: jItem.horas > 0 ? (jItem.kg / jItem.horas) : 0,
    kg_hora: jItem.horas > 0 ? (jItem.kg / jItem.horas).toFixed(1) : '0.0',
    prendas_hora: jItem.horas > 0 ? Math.round(jItem.prendas / jItem.horas) : 0,
    cargas_total: jItem.cargas,
    ikprod_prom: (jItem.ikprod_sum / (jItem.count || 1)).toFixed(1)
  })).sort((a, b) => b.kg_hora_num - a.kg_hora_num);

  const mejorTurno = turnosStats.length > 0 ? turnosStats[0] : null;
  const menorTurno = turnosStats.length > 1 ? turnosStats[turnosStats.length - 1] : null;

  // Condición: más de 2 jornadas completas (días de producción)
  const tieneMasDe2Jornadas = jornadasStats.length > 2;
  const mejorJornada = tieneMasDe2Jornadas ? jornadasStats[0] : null;
  const menorJornada = tieneMasDe2Jornadas ? jornadasStats[jornadasStats.length - 1] : null;

  return `
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.4; font-size: 9.5pt;">
      <!-- ENCABEZADO -->
      <div style="border-bottom: 2.5px solid #1e3a8a; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
        <div style="display: flex; align-items: center; gap: 14px;">
          <img src="/static/images/elis_logo.png" style="height: 48px; max-width: 130px; object-fit: contain;" alt="Elis Logo" onerror="this.style.display='none'">
          <div>
            <h1 style="margin: 0; font-size: 15pt; font-weight: 800; color: #1e3a8a; letter-spacing: -0.3px; text-transform: uppercase;">
              ${meta.title}
            </h1>
            <div style="font-size: 8.5pt; color: #475569; font-weight: 600; margin-top: 2px;">
              Planta Nájera &bull; Sistema de Monitorización Industrial 4.0
            </div>
          </div>
        </div>
        <div style="text-align: right; font-size: 8.5pt; color: #334155;">
          <div style="font-weight: 700; color: #0f172a;">FECHA: <span style="color: #1e3a8a;">${fechaHoyStr}</span></div>
          <div style="color: #64748b; font-size: 7.5pt; margin-top: 1px;">Hora emisión: ${horaHoyStr}</div>
          <div style="display: inline-block; background: #e0e7ff; color: #3730a3; padding: 2px 7px; border-radius: 4px; font-weight: 700; font-size: 7.5pt; margin-top: 3px;">
            ${t.total_turnos || 0} TURNOS CONCATENADOS
          </div>
        </div>
      </div>

      <!-- RANGO DE FECHA DEL INFORME -->
      <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 8px 14px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
          <span style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">Rango de Fecha del Informe:</span>
          <div style="font-size: 9.5pt; font-weight: 700; color: #0f172a; margin-top: 1px;">
            <span>${v.inicio_formateado || '--'}</span>
            <span style="color: #64748b; margin: 0 8px;">&rarr;</span>
            <span>${v.fin_formateado || '--'}</span>
          </div>
        </div>
        <div style="font-size: 8.5pt; color: #475569; font-weight: 600;">
          Horas Efectivas Evaluadas: <strong style="color: #0f172a;">${t.horas_efectivas_str || '0.0h'}</strong>
        </div>
      </div>

      <!-- TARJETAS DE INDICADORES (MISMO FORMATO DE PANTALLA FILTROS) -->
      <div style="margin-bottom: 16px;">
        <div style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
          Indicadores Globales Consolidados
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
          ${isLavado ? `
            <!-- 1. Kg Totales (Túnel Lavado) -->
            <div style="background: #eff6ff; border: 1.5px solid #93c5fd; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #1d4ed8; text-transform: uppercase;">Kg Totales</div>
              <div style="font-size: 16pt; font-weight: 900; color: #1e40af; margin: 2px 0;">${t.total_kg_str || '0.0 kg'}</div>
              <div style="font-size: 7.2pt; color: #1e3a8a; font-weight: 600;">
                Prom. Carga: ${t.promedio_peso_str || '--'}
              </div>
            </div>

            <!-- 2. Cargas Totales (Túnel Lavado) -->
            <div style="background: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #b45309; text-transform: uppercase;">Cargas Totales</div>
              <div style="font-size: 16pt; font-weight: 900; color: #92400e; margin: 2px 0;">${t.total_cargas_str || '0'}</div>
              <div style="font-size: 7.2pt; color: #78350f; font-weight: 600;">
                Tprom: ${t.promedio_tiempo_str || '--'}
              </div>
            </div>

            <!-- 3. ikProd General (Túnel Lavado) -->
            <div style="background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #15803d; text-transform: uppercase;">ikProd General</div>
              <div style="font-size: 16pt; font-weight: 900; color: #166534; margin: 2px 0;">${(t.ikprod && t.ikprod.pct_str) || '--'}</div>
              <div style="font-size: 7.2pt; color: #14532d; font-weight: 600;">
                ${(t.ikprod && t.ikprod.neto_str) || 'Ideal: 30 = 100%'}
              </div>
            </div>

            <!-- 4. Kg / Hora (Túnel Lavado) -->
            <div style="background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #7e22ce; text-transform: uppercase;">Kg / Hora General</div>
              <div style="font-size: 16pt; font-weight: 900; color: #6b21a8; margin: 2px 0;">${t.kg_hora_str || '0.0 kg/h'}</div>
              <div style="font-size: 7.2pt; color: #581c87; font-weight: 700;">
                Efectivas: ${t.horas_efectivas_str || '0h'}
              </div>
            </div>
          ` : `
            <!-- 1. Prendas Totales (Calandra / VT) -->
            <div style="background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #15803d; text-transform: uppercase;">Prendas Totales</div>
              <div style="font-size: 16pt; font-weight: 900; color: #166534; margin: 2px 0;">${t.total_prendas_str || '0'}</div>
              ${isC2 ? `
                <div style="font-size: 7.2pt; color: #14532d; font-weight: 600; display: flex; justify-content: center; gap: 6px;">
                  <span>G: ${t.total_grandes_str || '0'} (${t.pct_grandes || 0}%)</span>
                  <span>&bull;</span>
                  <span>P: ${t.total_pequenas_str || '0'} (${t.pct_pequenas || 0}%)</span>
                </div>
              ` : isVT ? `
                <div style="font-size: 7.2pt; color: #14532d; font-weight: 600; display: flex; justify-content: center; gap: 4px;">
                  <span>E1: ${t.total_e1_str || '0'}</span>
                  <span>&bull;</span>
                  <span>E2: ${t.total_e2_str || '0'}</span>
                  <span>&bull;</span>
                  <span>E3: ${t.total_e3_str || '0'}</span>
                </div>
              ` : `
                <div style="font-size: 7.2pt; color: #14532d; font-weight: 600;">
                  Prom. Turno: ${t.promedio_prendas_turno_str || '0'}
                </div>
              `}
            </div>

            <!-- 2. Kg Totales (Calandra / VT) -->
            <div style="background: #eff6ff; border: 1.5px solid #93c5fd; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #1d4ed8; text-transform: uppercase;">Kg Totales</div>
              <div style="font-size: 16pt; font-weight: 900; color: #1e40af; margin: 2px 0;">${t.total_kg_str || '0.0 kg'}</div>
              ${isC2 ? `
                <div style="font-size: 7.2pt; color: #1e3a8a; font-weight: 600; display: flex; justify-content: center; gap: 6px;">
                  <span>G: ${t.total_kg_grandes_str || '0.0 kg'}</span>
                  <span>&bull;</span>
                  <span>P: ${t.total_kg_pequenas_str || '0.0 kg'}</span>
                </div>
              ` : isVT ? `
                <div style="font-size: 7.2pt; color: #1e3a8a; font-weight: 600; display: flex; justify-content: center; gap: 4px;">
                  <span>E1: ${t.kg_e1_str || '0 kg'}</span>
                  <span>&bull;</span>
                  <span>E2: ${t.kg_e2_str || '0 kg'}</span>
                  <span>&bull;</span>
                  <span>E3: ${t.kg_e3_str || '0 kg'}</span>
                </div>
              ` : `
                <div style="font-size: 7.2pt; color: #1e3a8a; font-weight: 600;">
                  Peso unit: ${t.peso_unitario_str || '--'}
                </div>
              `}
            </div>

            <!-- 3. Tiempo Valle Total (Calandra / VT) -->
            <div style="background: #fffbeb; border: 1.5px solid #fde68a; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #b45309; text-transform: uppercase;">Tiempo Valle Total</div>
              <div style="font-size: 16pt; font-weight: 900; color: #92400e; margin: 2px 0;">${t.total_tiempo_valle_str || '0 min'}</div>
              <div style="font-size: 7.2pt; color: #78350f; font-weight: 600;">
                Prom. Turno: ${t.promedio_valle_turno_str || '0 min'}
              </div>
            </div>

            <!-- 4. Productividad Media (Calandra / VT) -->
            <div style="background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 8px; padding: 10px; text-align: center;">
              <div style="font-size: 8pt; font-weight: 700; color: #7e22ce; text-transform: uppercase;">Productividad Media</div>
              <div style="font-size: 16pt; font-weight: 900; color: #6b21a8; margin: 2px 0;">${t.kg_hora_str || '0.0 kg/h'}</div>
              <div style="font-size: 7.2pt; color: #581c87; font-weight: 700;">
                Cadencia: ${t.prendas_hora_str || '0 prendas/h'}
              </div>
            </div>
          `}
        </div>
      </div>

      <!-- ANÁLISIS DE PRODUCTIVIDAD -->
      <div style="background: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
        <div style="display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 10px;">
          <div style="width: 20px; height: 20px; border-radius: 4px; background: #3b82f6; color: white; display: flex; align-items: center; justify-content: center; font-size: 8pt; font-weight: 800;">
            i
          </div>
          <h3 style="margin: 0; font-size: 10pt; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: 0.3px;">
            Análisis de Resultados y Rendimiento Productivo
          </h3>
        </div>

        <!-- 1. Análisis de Turnos (Promedios) -->
        <div style="margin-bottom: 10px;">
          <div style="font-size: 8.5pt; font-weight: 700; color: #1e3a8a; margin-bottom: 4px;">
            1. Comparativa de Productividad por Tipo de Turno (Promedio en el período):
          </div>
          ${mejorTurno ? `
            <div style="font-size: 8.5pt; color: #334155; margin-bottom: 6px; line-height: 1.45;">
              En el período evaluado, el turno con <strong>mayor indicador de productividad</strong> es el 
              <span style="background: #dcfce7; color: #15803d; font-weight: 800; padding: 1px 6px; border-radius: 4px;">${mejorTurno.nombre}</span> 
              con una media de <strong>${mejorTurno.kg_hora} Kg/h</strong> 
              ${isLavado ? `(${mejorTurno.cargas_turno} cargas/turno, ikProd prom: ${mejorTurno.ikprod_prom}%)` : `(${mejorTurno.prendas_hora} prendas/h, promedio ${mejorTurno.prom_valle} min tiempo valle)`}.
              ${menorTurno && menorTurno.nombre !== mejorTurno.nombre ? `
                Por otro lado, el turno con <strong>menor indicador de productividad</strong> es el 
                <span style="background: #fee2e2; color: #b91c1c; font-weight: 800; padding: 1px 6px; border-radius: 4px;">${menorTurno.nombre}</span> 
                con una media de <strong>${menorTurno.kg_hora} Kg/h</strong> 
                ${isLavado ? `(${menorTurno.cargas_turno} cargas/turno, ikProd prom: ${menorTurno.ikprod_prom}%)` : `(${menorTurno.prendas_hora} prendas/h, promedio ${menorTurno.prom_valle} min tiempo valle)`}.
              ` : ''}
            </div>
          ` : `
            <div style="font-size: 8.5pt; color: #64748b;">No hay suficientes datos de turnos para calcular promedios.</div>
          `}

          <!-- Pequeña tabla comparativa de turnos -->
          <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px;">
            ${turnosStats.map(ts => `
              <div style="flex: 1; min-width: 140px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; font-size: 7.8pt;">
                <div style="font-weight: 700; color: #0f172a; display: flex; justify-content: space-between;">
                  <span>${ts.nombre}</span>
                  <span style="color: #64748b;">(${ts.count} turnos)</span>
                </div>
                <div style="color: #2563eb; font-weight: 700; margin-top: 2px;">
                  ${ts.kg_hora} Kg/h ${isLavado ? `&bull; ${ts.cargas_turno} cargas` : `&bull; ${ts.prendas_hora} p/h`}
                </div>
                <div style="color: #64748b; font-size: 7.2pt; margin-top: 1px;">
                  ${isLavado ? `ikProd: ${ts.ikprod_prom}% &bull; ${ts.prom_kg} kg/turno` : `Valle: ${ts.prom_valle} min &bull; ${ts.prom_prendas} prendas/t`}
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- 2. Análisis de Jornadas Completas (Solo si > 2 jornadas) -->
        ${tieneMasDe2Jornadas ? `
          <div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed #cbd5e1;">
            <div style="font-size: 8.5pt; font-weight: 700; color: #1e3a8a; margin-bottom: 4px;">
              2. Comparativa por Jornadas Completas (${jornadasStats.length} días de producción evaluados):
            </div>
            <div style="font-size: 8.5pt; color: #334155; line-height: 1.45;">
              Al abarcar la consulta más de 2 jornadas completas, se constata que la jornada con <strong>mayor productividad</strong> correspondió al 
              <span style="background: #dcfce7; color: #15803d; font-weight: 800; padding: 1px 6px; border-radius: 4px;">${mejorJornada.fecha}</span> 
              alcanzando <strong>${mejorJornada.kg_hora} Kg/h</strong> ${isLavado ? `(${mejorJornada.cargas_total} cargas en ${mejorJornada.horas}h)` : `(${mejorJornada.prendas_hora} prendas/h en ${mejorJornada.horas}h)`}.
              En contraste, la jornada con <strong>menor productividad</strong> fue el 
              <span style="background: #fee2e2; color: #b91c1c; font-weight: 800; padding: 1px 6px; border-radius: 4px;">${menorJornada.fecha}</span> 
              registrando <strong>${menorJornada.kg_hora} Kg/h</strong> ${isLavado ? `(${menorJornada.cargas_total} cargas en ${menorJornada.horas}h)` : `(${menorJornada.prendas_hora} prendas/h en ${menorJornada.horas}h)`}.
            </div>
          </div>
        ` : ''}
      </div>

      <!-- TABLA DETALLADA DE TURNOS CONCATENADOS -->
      <div style="margin-bottom: 12px;">
        <div style="font-size: 8pt; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center;">
          <span>Detalle Cronológico de Turnos Concatenados (${turnos.length})</span>
          <span style="font-size: 7.2pt; color: #94a3b8; font-weight: normal;">Orden cronológico de ejecución</span>
        </div>

        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 7.8pt;">
          <thead>
            <tr style="background: #f1f5f9; border-top: 1px solid #cbd5e1; border-bottom: 1.5px solid #94a3b8; color: #334155; font-size: 7.2pt; text-transform: uppercase; font-weight: 800;">
              <th style="padding: 6px 8px;">#</th>
              <th style="padding: 6px 8px;">Fecha</th>
              <th style="padding: 6px 8px;">Turno</th>
              <th style="padding: 6px 8px;">Horario</th>
              <th style="padding: 6px 8px; text-align: center;">Duración</th>
              ${isLavado ? `
                <th style="padding: 6px 8px; text-align: right;">Kg Totales</th>
                <th style="padding: 6px 8px; text-align: right;">Cargas</th>
                <th style="padding: 6px 8px; text-align: right;">ikProd</th>
                <th style="padding: 6px 8px; text-align: right;">Kg / Hora</th>
              ` : `
                <th style="padding: 6px 8px; text-align: right;">Prendas Tot.</th>
                ${isC2 ? `
                  <th style="padding: 6px 8px; text-align: right;">Grandes</th>
                  <th style="padding: 6px 8px; text-align: right;">Pequeñas</th>
                ` : isVT ? `
                  <th style="padding: 6px 8px; text-align: right;">E1</th>
                  <th style="padding: 6px 8px; text-align: right;">E2</th>
                  <th style="padding: 6px 8px; text-align: right;">E3</th>
                ` : ''}
                <th style="padding: 6px 8px; text-align: right;">Kg Totales</th>
                <th style="padding: 6px 8px; text-align: right;">T. Valle</th>
                ${isC3 ? `<th style="padding: 6px 8px; text-align: right;">Prendas/h</th>` : ''}
                <th style="padding: 6px 8px; text-align: right;">Kg / Hora</th>
              `}
            </tr>
          </thead>
          <tbody>
            ${turnos.map((item, idx) => `
              <tr style="border-bottom: 1px solid #e2e8f0; ${idx % 2 === 1 ? 'background: #f8fafc;' : ''}">
                <td style="padding: 5px 8px; font-weight: 700; color: #64748b;">${idx + 1}</td>
                <td style="padding: 5px 8px; font-weight: 600; color: #0f172a;">${item.fecha_formateada}</td>
                <td style="padding: 5px 8px; font-weight: 700; color: #1e3a8a;">${item.nombre_turno}</td>
                <td style="padding: 5px 8px; color: #475569;">${item.rango_horario}</td>
                <td style="padding: 5px 8px; text-align: center; color: #475569;">${item.duracion_horas}h</td>
                ${isLavado ? `
                  <td style="padding: 5px 8px; text-align: right; font-weight: 700; color: #15803d;">${item.total_kg_str}</td>
                  <td style="padding: 5px 8px; text-align: right; color: #b45309; font-weight: 600;">${item.total_cargas_str}</td>
                  <td style="padding: 5px 8px; text-align: right; font-weight: 700; color: #059669;">${item.ikprod_str}</td>
                  <td style="padding: 5px 8px; text-align: right; font-weight: 800; color: #1e40af;">${item.hprod_str || item.kg_hora_str}</td>
                ` : `
                  <td style="padding: 5px 8px; text-align: right; font-weight: 700; color: #0f172a;">${item.prendas_totales_str}</td>
                  ${isC2 ? `
                    <td style="padding: 5px 8px; text-align: right; color: #475569;">${item.prendas_grandes_str}</td>
                    <td style="padding: 5px 8px; text-align: right; color: #475569;">${item.prendas_pequenas_str}</td>
                  ` : isVT ? `
                    <td style="padding: 5px 8px; text-align: right; color: #475569;">${item.entrada_1_str || item.e1_str || '0'}</td>
                    <td style="padding: 5px 8px; text-align: right; color: #475569;">${item.entrada_2_str || item.e2_str || '0'}</td>
                    <td style="padding: 5px 8px; text-align: right; color: #475569;">${item.entrada_3_str || item.e3_str || '0'}</td>
                  ` : ''}
                  <td style="padding: 5px 8px; text-align: right; font-weight: 700; color: #15803d;">${item.total_kg_str}</td>
                  <td style="padding: 5px 8px; text-align: right; color: #b45309; font-weight: 600;">${item.tiempo_valle_str}</td>
                  ${isC3 ? `<td style="padding: 5px 8px; text-align: right; color: #475569;">${item.prendas_hora_str}</td>` : ''}
                  <td style="padding: 5px 8px; text-align: right; font-weight: 800; color: #1e40af;">${item.kg_hora_str}</td>
                `}
              </tr>
            `).join('')}
          </tbody>
          <tfoot>
            <tr style="background: #e2e8f0; border-top: 2px solid #64748b; border-bottom: 2px solid #64748b; font-weight: 800; color: #0f172a;">
              <td colspan="4" style="padding: 7px 8px; text-transform: uppercase; font-size: 7.5pt; letter-spacing: 0.5px;">TOTALES CONSOLIDADOS (${t.total_turnos || 0} TURNOS)</td>
              <td style="padding: 7px 8px; text-align: center;">${t.horas_efectivas_str}</td>
              ${isLavado ? `
                <td style="padding: 7px 8px; text-align: right; font-size: 8.5pt; color: #166534;">${t.total_kg_str}</td>
                <td style="padding: 7px 8px; text-align: right; font-size: 8.5pt; color: #92400e;">${t.total_cargas_str}</td>
                <td style="padding: 7px 8px; text-align: right; font-size: 8.5pt; color: #059669;">${(t.ikprod && t.ikprod.pct_str) || '--'}</td>
                <td style="padding: 7px 8px; text-align: right; font-size: 9pt; color: #1e3a8a;">${t.kg_hora_str}</td>
              ` : `
                <td style="padding: 7px 8px; text-align: right; font-size: 8.5pt; color: #0f172a;">${t.total_prendas_str}</td>
                ${isC2 ? `
                  <td style="padding: 7px 8px; text-align: right; color: #334155;">${t.total_grandes_str}</td>
                  <td style="padding: 7px 8px; text-align: right; color: #334155;">${t.total_pequenas_str}</td>
                ` : isVT ? `
                  <td style="padding: 7px 8px; text-align: right; color: #334155;">${t.total_e1_str}</td>
                  <td style="padding: 7px 8px; text-align: right; color: #334155;">${t.total_e2_str}</td>
                  <td style="padding: 7px 8px; text-align: right; color: #334155;">${t.total_e3_str}</td>
                ` : ''}
                <td style="padding: 7px 8px; text-align: right; font-size: 8.5pt; color: #166534;">${t.total_kg_str}</td>
                <td style="padding: 7px 8px; text-align: right; font-size: 8.5pt; color: #92400e;">${t.total_tiempo_valle_str}</td>
                ${isC3 ? `<td style="padding: 7px 8px; text-align: right; color: #334155;">${t.prendas_hora_str}</td>` : ''}
                <td style="padding: 7px 8px; text-align: right; font-size: 9pt; color: #1e3a8a;">${t.kg_hora_str}</td>
              `}
            </tr>
          </tfoot>
        </table>
      </div>

      <!-- PIE DE PÁGINA -->
      <div style="border-top: 1px solid #cbd5e1; padding-top: 8px; margin-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 7.2pt; color: #94a3b8;">
        <div>Elis Manomatic &bull; Departamento de Mantenimiento y Producción &bull; Nájera</div>
        <div>Documento generado automáticamente &bull; Sistema Elis 4.0</div>
      </div>
    </div>
  `;
}

/* ========================================================
   MÓDULO DE RENDIMIENTO Y MONITOR HARDWARE JETSON NANO (180s)
   ======================================================== */
let rendCountdownSec = 180;
let rendTimerInterval = null;
let chartRendLoad = null;
let chartRendTemp = null;
let isRendimientoMeasuring = false;

// Inicialización de la pantalla de rendimiento
function initRendimientoScreen() {
  rendCountdownSec = 180;
  loadRendimientoData();
  loadRendimientoHistory();
  startRendimientoTimer();
}

// Iniciar temporizador de cuenta regresiva de 180 segundos
function startRendimientoTimer() {
  stopRendimientoTimer();
  const countdownEl = document.getElementById('rend-countdown');
  if (countdownEl) countdownEl.textContent = `${rendCountdownSec}s`;

  rendTimerInterval = setInterval(() => {
    rendCountdownSec--;
    if (countdownEl) countdownEl.textContent = `${rendCountdownSec}s`;

    if (rendCountdownSec <= 0) {
      rendCountdownSec = 180;
      loadRendimientoData();
      loadRendimientoHistory();
    }
  }, 1000);
}

// Detener temporizador al salir de la vista
function stopRendimientoTimer() {
  if (rendTimerInterval) {
    clearInterval(rendTimerInterval);
    rendTimerInterval = null;
  }
}

// Cargar métricas en tiempo real
async function loadRendimientoData() {
  try {
    const res = await fetch('/api/rendimiento/current');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderRendimientoUI(data);
  } catch (err) {
    console.error('Error cargando métricas de rendimiento:', err);
    showRendAlert(`⚠️ No se pudo obtener la telemetría del servidor Jetson: ${err.message}`, 'danger');
  }
}

// Cargar histórico para gráficos
async function loadRendimientoHistory() {
  try {
    const res = await fetch('/api/rendimiento/history?limit=30');
    if (!res.ok) return;
    const history = await res.json();
    renderRendimientoCharts(history);
  } catch (err) {
    console.error('Error cargando histórico de rendimiento:', err);
  }
}

// Ejecutar medición manual inmediata
async function ejecutarMedicionManual() {
  if (isRendimientoMeasuring) return;
  isRendimientoMeasuring = true;

  const btn = document.getElementById('btn-medir-manual');
  const icon = document.getElementById('icon-medir-manual');
  const txt = document.getElementById('text-medir-manual');

  if (btn) btn.disabled = true;
  if (icon) icon.className = 'fas fa-spinner fa-spin';
  if (txt) txt.textContent = 'Midiendo...';

  try {
    const res = await fetch('/api/rendimiento/medir', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const result = await res.json();
    
    if (result.data) {
      renderRendimientoUI(result.data);
    }
    await loadRendimientoHistory();

    // Reiniciar ciclo de 180s
    rendCountdownSec = 180;
    const countdownEl = document.getElementById('rend-countdown');
    if (countdownEl) countdownEl.textContent = '180s';

    showRendAlert('✅ Medición completa de hardware ejecutada y registrada en el historial correctamente.', 'success');
  } catch (err) {
    console.error('Error en medición manual:', err);
    showRendAlert(`❌ Error ejecutando la medición manual: ${err.message}`, 'danger');
  } finally {
    isRendimientoMeasuring = false;
    if (btn) btn.disabled = false;
    if (icon) icon.className = 'fas fa-sync-alt';
    if (txt) txt.textContent = 'Medir Ahora';
  }
}

// Mostrar banner de alerta / notificación
function showRendAlert(msg, type = 'info') {
  const banner = document.getElementById('rend-alert-banner');
  if (!banner) return;

  banner.textContent = msg;
  banner.style.display = 'block';
  if (type === 'success') {
    banner.style.backgroundColor = 'rgba(16, 185, 129, 0.2)';
    banner.style.border = '1px solid #10b981';
    banner.style.color = '#34d399';
  } else if (type === 'danger') {
    banner.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
    banner.style.border = '1px solid #ef4444';
    banner.style.color = '#f87171';
  } else {
    banner.style.backgroundColor = 'rgba(2, 132, 199, 0.2)';
    banner.style.border = '1px solid #0284c7';
    banner.style.color = '#38bdf8';
  }

  setTimeout(() => {
    banner.style.display = 'none';
  }, 4500);
}

// Renderizado integral de la interfaz gráfica de rendimiento
function renderRendimientoUI(data) {
  if (!data) return;

  // 1. Marca de tiempo
  const tsEl = document.getElementById('rend-last-timestamp');
  if (tsEl) tsEl.textContent = data.timestamp ? data.timestamp.split(' ')[1] : '--:--:--';

  // 2. CPU Total
  const cpuPct = (data.cpu && data.cpu.total_percent) !== undefined ? data.cpu.total_percent : 0;
  const cpuValEl = document.getElementById('kpi-cpu-val');
  const cpuBarEl = document.getElementById('kpi-cpu-bar');
  const cpuLoadavgEl = document.getElementById('kpi-cpu-loadavg');

  if (cpuValEl) cpuValEl.textContent = `${cpuPct}%`;
  if (cpuBarEl) {
    cpuBarEl.style.width = `${Math.min(100, Math.max(0, cpuPct))}%`;
    cpuBarEl.className = 'rend-progress-fill ' + (cpuPct > 80 ? 'red' : cpuPct > 55 ? 'amber' : 'blue');
  }
  if (cpuLoadavgEl && data.cpu && data.cpu.load_average) {
    const la = data.cpu.load_average;
    cpuLoadavgEl.textContent = `${la['1m']}, ${la['5m']}, ${la['15m']}`;
  }

  // 3. Memoria RAM y SWAP
  const mem = data.memory || {};
  const ramPct = mem.ram_percent || 0;
  const ramValEl = document.getElementById('kpi-ram-val');
  const ramSubEl = document.getElementById('kpi-ram-sub');
  const ramBarEl = document.getElementById('kpi-ram-bar');
  const swapInfoEl = document.getElementById('kpi-swap-info');

  if (ramValEl) ramValEl.textContent = `${ramPct}%`;
  if (ramSubEl) ramSubEl.textContent = `${mem.ram_used_mb || 0} / ${mem.ram_total_mb || 0} MB`;
  if (ramBarEl) {
    ramBarEl.style.width = `${Math.min(100, Math.max(0, ramPct))}%`;
    ramBarEl.className = 'rend-progress-fill ' + (ramPct > 85 ? 'red' : ramPct > 70 ? 'amber' : 'cyan');
  }
  if (swapInfoEl) {
    swapInfoEl.textContent = `${mem.swap_percent || 0}% (${mem.swap_used_mb || 0} MB)`;
  }

  // 4. GPU Tegra
  const gpu = data.gpu || {};
  const gpuPct = gpu.load_percent !== undefined ? gpu.load_percent : 0;
  const gpuValEl = document.getElementById('kpi-gpu-val');
  const gpuBarEl = document.getElementById('kpi-gpu-bar');
  if (gpuValEl) gpuValEl.textContent = `${gpuPct}%`;
  if (gpuBarEl) {
    gpuBarEl.style.width = `${Math.min(100, Math.max(0, gpuPct))}%`;
    gpuBarEl.className = 'rend-progress-fill ' + (gpuPct > 80 ? 'red' : 'purple');
  }

  // 5. Térmicas y Ventilador
  const thermals = data.thermals || {};
  const cooling = data.cooling || {};
  const cpuTemp = thermals.cpu_temp || 0;
  const gpuTemp = thermals.gpu_temp || 0;
  const maxTemp = Math.max(cpuTemp, gpuTemp);

  const tempValEl = document.getElementById('kpi-temp-val');
  const tempSubEl = document.getElementById('kpi-temp-sub');
  const tempBarEl = document.getElementById('kpi-temp-bar');
  const tempBadgeEl = document.getElementById('kpi-temp-badge');
  const fanInfoEl = document.getElementById('kpi-fan-info');

  if (tempValEl) tempValEl.textContent = `${maxTemp}°C`;
  if (tempSubEl) tempSubEl.textContent = `CPU: ${cpuTemp}°C | GPU: ${gpuTemp}°C`;
  if (tempBarEl) {
    const tempPct = Math.min(100, Math.round((maxTemp / 85.0) * 100));
    tempBarEl.style.width = `${tempPct}%`;
    tempBarEl.className = 'rend-progress-fill ' + (maxTemp >= 75 ? 'red' : maxTemp >= 60 ? 'amber' : 'green');
  }
  if (tempBadgeEl) {
    tempBadgeEl.textContent = thermals.status || 'Normal';
    tempBadgeEl.className = 'rend-pill-badge ' + (thermals.badge || 'green');
  }
  if (fanInfoEl) {
    fanInfoEl.textContent = `${cooling.fan_percent || 0}% (PWM ${cooling.fan_pwm || 0}/255)`;
  }

  // 6. Disco NVMe
  const disks = (data.storage && data.storage.disks) || [];
  const rootDisk = disks[0] || {};
  const diskPct = rootDisk.percent || 0;
  const diskValEl = document.getElementById('kpi-disk-val');
  const diskSubEl = document.getElementById('kpi-disk-sub');
  const diskBarEl = document.getElementById('kpi-disk-bar');
  const diskFreeEl = document.getElementById('kpi-disk-free');

  if (diskValEl) diskValEl.textContent = `${diskPct}%`;
  if (diskSubEl) diskSubEl.textContent = `${rootDisk.used_gb || 0} / ${rootDisk.total_gb || 0} GB`;
  if (diskBarEl) {
    diskBarEl.style.width = `${Math.min(100, Math.max(0, diskPct))}%`;
    diskBarEl.className = 'rend-progress-fill ' + (diskPct > 85 ? 'red' : diskPct > 70 ? 'amber' : 'blue');
  }
  if (diskFreeEl) {
    diskFreeEl.textContent = `${rootDisk.free_gb || 0} GB`;
  }

  // 7. Sistema & Uptime
  const sys = data.system || {};
  const uptimeEl = document.getElementById('kpi-uptime-val');
  const powerModeEl = document.getElementById('kpi-power-mode');
  const l4tEl = document.getElementById('kpi-l4t-info');
  const dbSizeEl = document.getElementById('kpi-db-size');

  if (uptimeEl) uptimeEl.textContent = sys.uptime_formatted || '--';
  if (powerModeEl) powerModeEl.textContent = sys.power_mode || '5W';
  if (l4tEl) l4tEl.textContent = sys.l4t || 'L4T R32.7.6';
  if (dbSizeEl && data.storage) dbSizeEl.textContent = `${data.storage.db_size_mb || 0} MB`;

  // 8. Desglose de Cores CPU
  const coresList = (data.cpu && data.cpu.cores) || [];
  const coresContainer = document.getElementById('rend-cores-list');
  if (coresContainer) {
    coresContainer.innerHTML = coresList.map(c => {
      const u = c.usage_percent !== undefined ? c.usage_percent : 0;
      const freq = c.freq_mhz ? `${c.freq_mhz} MHz` : (c.online ? 'Online' : 'Offline');
      const barColor = u > 80 ? '#ef4444' : u > 50 ? '#f59e0b' : '#38bdf8';
      return `
        <div class="rend-core-box">
          <div class="rend-core-name">Core ${c.core}</div>
          <div class="rend-core-val" style="color: ${barColor}">${u}%</div>
          <div class="rend-progress-track" style="height: 6px; margin: 4px 0;">
            <div style="height: 100%; width: ${Math.min(100, Math.max(0, u))}%; background: ${barColor}; border-radius: 6px;"></div>
          </div>
          <div class="rend-core-freq">${freq}</div>
        </div>
      `;
    }).join('');
  }

  // 9. Sensores Térmicos
  const thermalsList = document.getElementById('rend-thermals-list');
  if (thermalsList && thermals.all_zones) {
    const zones = thermals.all_zones;
    thermalsList.innerHTML = Object.keys(zones).map(z => {
      const val = zones[z];
      const color = val >= 75 ? '#ef4444' : val >= 60 ? '#f59e0b' : '#34d399';
      return `
        <div class="rend-thermal-item">
          <div class="rend-thermal-label">${z}</div>
          <div class="rend-thermal-temp" style="color: ${color}">${val}°C</div>
        </div>
      `;
    }).join('');
  }

  // 10. Servicios Docker
  const services = (data.services && data.services.docker_containers) || [];
  const servicesTbody = document.getElementById('rend-services-tbody');
  const servicesBadge = document.getElementById('rend-services-badge');

  if (servicesBadge && data.services) {
    servicesBadge.textContent = `${data.services.running_containers || 0} / ${data.services.total_containers || 0} En Ejecución`;
  }

  if (servicesTbody) {
    if (services.length === 0) {
      servicesTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 16px;">No se detectaron servicios Docker activos.</td></tr>`;
    } else {
      servicesTbody.innerHTML = services.map(s => {
        const isRunning = s.state === 'running';
        const statusBadge = isRunning
          ? `<span class="rend-status-tag running"><i class="fas fa-check-circle"></i> Activo</span>`
          : `<span class="rend-status-tag stopped"><i class="fas fa-times-circle"></i> Detenido</span>`;
        const memStr = s.mem_usage_mb !== null && s.mem_usage_mb !== undefined ? `${s.mem_usage_mb} MB` : '--';
        return `
          <tr>
            <td>
              <strong style="color: #38bdf8; font-size: 0.95rem;">${s.name}</strong>
            </td>
            <td>${statusBadge}</td>
            <td style="color: #cbd5e1; font-size: 0.82rem;">${s.status || 'N/A'}</td>
            <td><strong style="color: #34d399;">${memStr}</strong></td>
            <td><span class="rend-code-pill">${s.ports}</span></td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${s.image}</td>
          </tr>
        `;
      }).join('');
    }
  }

  // 11. Top Procesos
  const procs = (data.processes && data.processes.top_processes) || [];
  const procTbody = document.getElementById('rend-processes-tbody');
  const procCountBadge = document.getElementById('rend-proc-count-badge');

  if (procCountBadge && data.processes) {
    procCountBadge.textContent = `${data.processes.total_count || 0} Procesos Totales`;
  }

  if (procTbody) {
    if (procs.length === 0) {
      procTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 16px;">No hay procesos para listar.</td></tr>`;
    } else {
      procTbody.innerHTML = procs.map(p => {
        return `
          <tr>
            <td><span class="rend-code-pill">${p.pid}</span></td>
            <td><span style="color: #94a3b8; font-weight: 600;">${p.user}</span></td>
            <td><strong style="color: #f8fafc;">${p.name}</strong></td>
            <td><strong style="color: #38bdf8;">${p.mem_pct}%</strong></td>
            <td style="color: #34d399;">${p.mem_mb} MB</td>
            <td><span style="color: #cbd5e1; font-size: 0.8rem;">${p.state}</span></td>
            <td style="font-family: monospace; font-size: 0.76rem; color: #94a3b8; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${p.cmd}">${p.cmd}</td>
          </tr>
        `;
      }).join('');
    }
  }
}

// Renderizar gráficos de evolución histórica con Chart.js
function renderRendimientoCharts(history) {
  if (!history || !Array.isArray(history) || history.length === 0) return;

  const labels = history.map(h => h.timestamp);
  const cpuData = history.map(h => h.cpu_total);
  const ramData = history.map(h => h.ram_percent);
  const gpuData = history.map(h => h.gpu_load);
  const tempCpuData = history.map(h => h.temp_cpu);
  const tempGpuData = history.map(h => h.temp_gpu);
  const tempAoData = history.map(h => h.temp_ao);

  // Gráfico 1: Carga (%)
  const ctxLoad = document.getElementById('chart-rendimiento-load');
  if (ctxLoad) {
    if (chartRendLoad) chartRendLoad.destroy();
    chartRendLoad = new Chart(ctxLoad, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'CPU Total (%)',
            data: cpuData,
            borderColor: '#38bdf8',
            backgroundColor: 'rgba(56, 189, 248, 0.1)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: '#38bdf8'
          },
          {
            label: 'Memoria RAM (%)',
            data: ramData,
            borderColor: '#34d399',
            backgroundColor: 'rgba(52, 211, 153, 0.05)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.2,
            pointRadius: 3,
            pointBackgroundColor: '#34d399'
          },
          {
            label: 'GPU Tegra (%)',
            data: gpuData,
            borderColor: '#c084fc',
            backgroundColor: 'rgba(192, 132, 252, 0.05)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.2,
            pointRadius: 3,
            pointBackgroundColor: '#c084fc'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { color: '#cbd5e1', font: { size: 11, weight: 'bold' }, boxWidth: 12 }
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: '#334155',
            borderWidth: 1,
            titleColor: '#38bdf8',
            bodyColor: '#f8fafc'
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(51, 65, 85, 0.3)' },
            ticks: { color: '#94a3b8', font: { size: 10 } }
          },
          y: {
            min: 0,
            max: 100,
            grid: { color: 'rgba(51, 65, 85, 0.3)' },
            ticks: {
              color: '#94a3b8',
              font: { size: 10 },
              callback: v => `${v}%`
            }
          }
        }
      }
    });
  }

  // Gráfico 2: Temperaturas (°C)
  const ctxTemp = document.getElementById('chart-rendimiento-temp');
  if (ctxTemp) {
    if (chartRendTemp) chartRendTemp.destroy();
    chartRendTemp = new Chart(ctxTemp, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Temp CPU (°C)',
            data: tempCpuData,
            borderColor: '#f87171',
            backgroundColor: 'rgba(248, 113, 113, 0.1)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: '#f87171'
          },
          {
            label: 'Temp GPU (°C)',
            data: tempGpuData,
            borderColor: '#fbbf24',
            backgroundColor: 'rgba(251, 191, 36, 0.05)',
            fill: false,
            tension: 0.35,
            borderWidth: 2.2,
            pointRadius: 3,
            pointBackgroundColor: '#fbbf24'
          },
          {
            label: 'Temp Ambiente AO (°C)',
            data: tempAoData,
            borderColor: '#38bdf8',
            backgroundColor: 'rgba(56, 189, 248, 0.05)',
            fill: false,
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 2,
            pointBackgroundColor: '#38bdf8'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { color: '#cbd5e1', font: { size: 11, weight: 'bold' }, boxWidth: 12 }
          },
          tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: '#334155',
            borderWidth: 1,
            titleColor: '#f87171',
            bodyColor: '#f8fafc'
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(51, 65, 85, 0.3)' },
            ticks: { color: '#94a3b8', font: { size: 10 } }
          },
          y: {
            min: 20,
            max: 85,
            grid: { color: 'rgba(51, 65, 85, 0.3)' },
            ticks: {
              color: '#94a3b8',
              font: { size: 10 },
              callback: v => `${v}°C`
            }
          }
        }
      }
    });
  }
}




