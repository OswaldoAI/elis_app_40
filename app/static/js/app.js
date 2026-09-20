// ELIS NAJERA 4.0 - Application Frontend Controller

let currentUser = null;
let userPermissions = {};

document.addEventListener('DOMContentLoaded', async () => {
  await checkAuth();
  setupEventListeners();
  handleRoute();
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

// Switch View Sections
function switchView(viewName) {
  document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
  document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));

  const targetSec = document.getElementById(`view-${viewName}`);
  const targetBtn = document.querySelector(`.menu-btn[data-view="${viewName}"]`);

  if (targetSec) {
    targetSec.classList.add('active');
  }
  if (targetBtn) {
    targetBtn.classList.add('active');
  }

  // Update browser location hash
  window.location.hash = `#${viewName}`;

  // Load section specific data
  if (viewName === 'produccion') loadProduccionData();
  if (viewName === 'consumos') loadConsumosData();
  if (viewName === 'usuarios') loadUsersList();
  if (viewName === 'permisos') loadPermissionsMatrix();
}

function handleRoute() {
  const hash = window.location.hash.replace('#', '') || 'inicio';
  switchView(hash);
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
        Telemetría y estado operativo de las máquinas principales de la planta ELIS Nájera 4.0:
      </p>

      <div class="machines-grid">
    `;

    data.maquinas.forEach(m => {
      html += `
        <div class="machine-card" id="card-${m.id}">
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
            <span class="shift-title"><i class="fas fa-user-clock"></i> ${m.turno_info.nombre}</span>
            <span class="shift-time"><i class="fas fa-clock"></i> ${m.turno_info.horario}</span>
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
