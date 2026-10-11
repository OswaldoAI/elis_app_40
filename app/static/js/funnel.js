/**
 * ELIS NÁJERA 4.0 - FUNNEL MÓVIL Y TABLET (PRODUCCIÓN)
 * Script interactivo y reactivo optimizado para pantallas táctiles y auto-orientación.
 * Gráficas de líneas de producción idénticas a los dashboards ampliados (Kg, Prendas, Valle y Cargas).
 */

// Helper robusto para extraer texto o valores numéricos de cualquier campo (sea string, número u objeto)
function getVal(item, fallback = '--') {
  if (item === null || item === undefined) return fallback;
  if (typeof item === 'string' || typeof item === 'number') return String(item);
  if (typeof item === 'object') {
    if (item.valor_str !== undefined && item.valor_str !== null) return String(item.valor_str);
    if (item.valor !== undefined && item.valor !== null) return String(item.valor);
    if (item.val !== undefined && item.val !== null) return String(item.val);
    if (item.valor_num !== undefined && item.valor_num !== null) return String(item.valor_num);
    if (item.pct_str !== undefined && item.pct_str !== null) return String(item.pct_str);
    if (item.str !== undefined && item.str !== null) return String(item.str);
    return fallback;
  }
  return fallback;
}

// Normalización de etiquetas de horas (ej: si vienen horas sueltas o intervalos)
function cleanHourLabels(rawLabels) {
  if (!rawLabels || !Array.isArray(rawLabels)) return [];
  return rawLabels.map(l => {
    if (typeof l !== 'string') return String(l);
    // Si viene "06:00 - 07:00", mostrar de forma compacta para móvil
    return l.split(' - ')[0] || l;
  });
}

// Estado global de la aplicación funnel
const state = {
  activeTab: 'resumen',
  summaryData: null,
  machinesData: {
    TUNEL_LAVADO: null,
    CALANDRA_2: null,
    CALANDRA_3: null,
    TUNEL_VT: null
  },
  charts: {
    resumen: null,
    TUNEL_LAVADO: null,
    CALANDRA_2: null,
    CALANDRA_3: null,
    TUNEL_VT: null
  },
  chartMetrics: {
    resumen: 'kg', // 'kg' | 'prendas'
    TUNEL_LAVADO: 'combo', // 'combo' | 'kg' | 'cargas'
    CALANDRA_2: 'combo', // 'combo' | 'kg' | 'prendas'
    CALANDRA_3: 'combo', // 'combo' | 'kg' | 'prendas'
    TUNEL_VT: 'combo' // 'combo' | 'kg' | 'prendas'
  },
  historial: {
    currentMachine: 'TUNEL_LAVADO',
    previousTab: 'resumen',
    chart: null,
    eventsBound: false
  },
  isLoading: false,
  lastUpdated: null,
  refreshTimer: null
};

// Inicialización al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
  initUrlHash();
  bindEvents();
  loadAllFunnelData();
  
  // Auto-refresco inteligente cada 12 segundos
  state.refreshTimer = setInterval(() => {
    loadAllFunnelData(true);
  }, 12000);

  // Escuchar cambios de visibilidad para refresco instantáneo al volver a la app en móvil
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      loadAllFunnelData(true);
    }
  });

  // Redimensionar gráficos al rotar pantalla (portrait <-> landscape)
  window.addEventListener('orientationchange', () => {
    setTimeout(resizeCurrentChart, 250);
  });
  window.addEventListener('resize', () => {
    debounce(resizeCurrentChart, 150)();
  });
});

// Manejo del hash de URL para navegación directa
function initUrlHash() {
  const hash = window.location.hash.replace('#', '');
  if (['resumen', 'tunel_lavado', 'calandra_2', 'calandra_3', 'tunel_vt', 'historial'].includes(hash)) {
    state.activeTab = hash;
  } else {
    state.activeTab = 'resumen';
  }
  updateTabUI(state.activeTab);
}

function bindEvents() {
  // Pestañas
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      switchTab(tab);
    });
  });

  // Eventos de controles de historial
  bindMobileHistorialEvents();

  // Botón refrescar
  const btnRefresh = document.getElementById('btn-funnel-refresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      if (navigator.vibrate) navigator.vibrate(30);
      btnRefresh.classList.add('spinning');
      loadAllFunnelData(false).finally(() => {
        setTimeout(() => btnRefresh.classList.remove('spinning'), 600);
      });
    });
  }
}

// Cambio de pestaña
function switchTab(tabId) {
  state.activeTab = tabId;
  window.location.hash = tabId;
  updateTabUI(tabId);

  // Ocultar todas las vistas
  document.querySelectorAll('.funnel-view').forEach(v => v.style.display = 'none');

  if (tabId === 'resumen') {
    const view = document.getElementById('view-funnel-resumen');
    if (view) {
      view.style.display = 'block';
      renderResumenGeneralChart();
    }
  } else if (tabId === 'historial') {
    const view = document.getElementById('view-funnel-historial');
    if (view) {
      view.style.display = 'block';
      initMobileHistorialScreen();
    }
  } else {
    const view = document.getElementById(`view-funnel-${tabId}`);
    if (view) {
      view.style.display = 'block';
      renderMachineDetail(tabId.toUpperCase());
    }
  }

  // Desplazar suavemente hacia arriba
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Asegurar renderizado correcto del gráfico de la pestaña activa
  setTimeout(resizeCurrentChart, 100);
}

function updateTabUI(activeTab) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    if (btn.dataset.tab === activeTab) {
      btn.classList.add('active');
      btn.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    } else {
      btn.classList.remove('active');
    }
  });
}

// Carga de datos de todas las APIs
async function loadAllFunnelData(silent = false) {
  if (state.isLoading) return;
  state.isLoading = true;

  try {
    // 1. Resumen global
    const resSummary = await fetch('/api/produccion/summary');
    if (resSummary.ok) {
      state.summaryData = await resSummary.json();
      renderGlobalSummary(state.summaryData);
    }

    // 2. Fetch de máquinas en paralelo
    const [resTunel, resCal2, resCal3, resVT] = await Promise.allSettled([
      fetch('/api/produccion/tunel-lavado/dashboard').then(r => r.ok ? r.json() : null),
      fetch('/api/produccion/calandras/CALANDRA_2/dashboard').then(r => r.ok ? r.json() : null),
      fetch('/api/produccion/calandras/CALANDRA_3/dashboard').then(r => r.ok ? r.json() : null),
      fetch('/api/produccion/tunel-vt/dashboard').then(r => r.ok ? r.json() : null)
    ]);

    if (resTunel.status === 'fulfilled' && resTunel.value) state.machinesData.TUNEL_LAVADO = resTunel.value;
    if (resCal2.status === 'fulfilled' && resCal2.value) state.machinesData.CALANDRA_2 = resCal2.value;
    if (resCal3.status === 'fulfilled' && resCal3.value) state.machinesData.CALANDRA_3 = resCal3.value;
    if (resVT.status === 'fulfilled' && resVT.value) state.machinesData.TUNEL_VT = resVT.value;

    // Renderizar tarjetas de la vista general
    renderOverviewMachineCards();
    renderResumenGeneralChart();

    // Si estamos en una vista de máquina, actualizarla
    if (state.activeTab !== 'resumen') {
      renderMachineDetail(state.activeTab.toUpperCase());
    }

    // Actualizar timestamp
    state.lastUpdated = new Date();
    const timeStr = state.lastUpdated.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const elClock = document.getElementById('last-sync-clock');
    if (elClock) elClock.textContent = timeStr;

  } catch (err) {
    console.error('Error cargando datos funnel móvil:', err);
  } finally {
    state.isLoading = false;
  }
}

// Renderizado del resumen global superior (Hero KPIs)
function renderGlobalSummary(data) {
  if (!data) return;

  const kilosLavados = data.kilos_lavados_hoy || 0;
  const objetivo = data.objetivo_diario || 18000;
  const pctObj = Math.min(Math.round((kilosLavados / objetivo) * 100), 100);
  const kilosCalandras = data.kilos_calandras_hoy || 0;

  // Actualizar valores en DOM
  setElementText('kpi-kilos-lavados', `${kilosLavados.toLocaleString('es-ES')} kg`);
  setElementText('kpi-objetivo-sub', `${pctObj}% del objetivo (${objetivo.toLocaleString('es-ES')} kg)`);
  const fillBar = document.getElementById('kpi-progreso-bar');
  if (fillBar) fillBar.style.width = `${pctObj}%`;

  setElementText('kpi-kilos-calandras', `${Math.round(kilosCalandras).toLocaleString('es-ES')} kg`);
  setElementText('kpi-calandras-sub', `C2: ${data.kilos_cal2_hoy_str || '0 kg'} | C3: ${data.kilos_cal3_hoy_str || '0 kg'}`);

  setElementText('kpi-maquinas-activas', '4 / 4');
  setElementText('kpi-eficiencia-global', `${data.eficiencia_global_oee || 89.8}% OEE`);

  // Strip de turno
  if (data.maquinas && data.maquinas[0] && data.maquinas[0].turno_info) {
    const t = data.maquinas[0].turno_info;
    setElementText('shift-strip-nombre', t.nombre || 'Turno Activo');
    setElementText('shift-strip-horario', t.horario || '');
    setElementText('shift-strip-fecha', t.fecha || '');
  }
}

// Renderizado de las 4 tarjetas principales en la vista Resumen
function renderOverviewMachineCards() {
  const container = document.getElementById('funnel-machines-grid');
  if (!container || !state.summaryData || !state.summaryData.maquinas) return;

  let html = '';
  state.summaryData.maquinas.forEach(m => {
    let tabTarget = '';
    let avatarIcon = 'fa-cogs';
    let avatarNum = '';

    if (m.id === 'TUNEL_LAVADO') {
      tabTarget = 'tunel_lavado';
      avatarIcon = 'fa-circle-notch';
    } else if (m.id === 'CALANDRA_2') {
      tabTarget = 'calandra_2';
      avatarIcon = 'fa-scroll';
      avatarNum = '<span class="calandra-badge-num">2</span>';
    } else if (m.id === 'CALANDRA_3') {
      tabTarget = 'calandra_3';
      avatarIcon = 'fa-scroll';
      avatarNum = '<span class="calandra-badge-num">3</span>';
    } else if (m.id === 'TUNEL_VT') {
      tabTarget = 'tunel_vt';
      avatarIcon = 'fa-wind';
    }

    // Estado
    let statusClass = 'operativa';
    let statusText = m.estado || 'Operativa';
    if (m.produccion_calandra) {
      if (!m.produccion_calandra.is_turno_activo) {
        statusClass = 'inactiva';
        statusText = 'Inactiva';
      } else if (m.produccion_calandra.en_valle) {
        statusClass = 'valle';
        statusText = 'En Valle';
      }
    } else if (m.produccion_tunel_vt) {
      if (!m.produccion_tunel_vt.is_turno_activo) {
        statusClass = 'inactiva';
        statusText = 'Inactiva';
      } else if (m.produccion_tunel_vt.en_valle) {
        statusClass = 'valle';
        statusText = 'En Valle';
      }
    }

    // Métricas por tipo de máquina
    let chipsHtml = '';
    if (m.id === 'TUNEL_LAVADO') {
      const ind = m.indicadores_turno || {};
      const ik = ind.ikprod_details || {};
      const ritmoStr = (state.machinesData.TUNEL_LAVADO && state.machinesData.TUNEL_LAVADO.indicadores_destacados && state.machinesData.TUNEL_LAVADO.indicadores_destacados.hprod) 
        ? getVal(state.machinesData.TUNEL_LAVADO.indicadores_destacados.hprod) 
        : (ind.promedio_carga || '53 kg');

      chipsHtml = `
        <div class="mini-kpi-chip">
          <span class="chip-label">Kilos Turno</span>
          <span class="chip-val" style="color: #38bdf8;">${ind.kgs_totales || '0 kg'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Cargas</span>
          <span class="chip-val">${ind.cantidad_cargas || '0'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Ritmo hProd</span>
          <span class="chip-val">${ritmoStr}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">ikProd Eficiencia</span>
          <span class="chip-val" style="color: ${ik.text_color || '#34d399'};">${ind.ikprod || ik.pct_str || '0%'}</span>
        </div>
      `;
    } else if (m.id === 'CALANDRA_2' || m.id === 'CALANDRA_3') {
      const cal = m.produccion_calandra || {};
      chipsHtml = `
        <div class="mini-kpi-chip">
          <span class="chip-label">Prendas Totales</span>
          <span class="chip-val" style="color: #34d399;">${cal.prendas_totales_str || '0 prendas'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Kilos Totales</span>
          <span class="chip-val">${cal.kgs_totales_str || '0 kg'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Prendas / Hora</span>
          <span class="chip-val">${cal.prendas_hora_str || '0/h'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Tiempo Valle</span>
          <span class="chip-val" style="color: ${cal.tiempo_valle_min > 30 ? '#f87171' : '#f59e0b'};">${cal.tiempo_valle_str || '0 min'}</span>
        </div>
      `;
    } else if (m.id === 'TUNEL_VT') {
      const vt = m.produccion_tunel_vt || {};
      chipsHtml = `
        <div class="mini-kpi-chip">
          <span class="chip-label">Prendas Totales</span>
          <span class="chip-val" style="color: #818cf8;">${vt.prendas_totales_str || '0 prendas'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Kilos Totales</span>
          <span class="chip-val">${vt.kgs_totales_str || '0 kg'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Prendas / Hora</span>
          <span class="chip-val">${vt.prendas_hora_str || '0/h'}</span>
        </div>
        <div class="mini-kpi-chip">
          <span class="chip-label">Tiempo Valle</span>
          <span class="chip-val" style="color: ${vt.tiempo_valle_min > 30 ? '#f87171' : '#f59e0b'};">${vt.tiempo_valle_total_str || vt.tiempo_valle_str || '0 min'}</span>
        </div>
      `;
    }

    html += `
      <div class="funnel-machine-card" onclick="switchTab('${tabTarget}')">
        <div class="machine-top-bar">
          <div class="machine-identity">
            <div class="machine-avatar-badge">
              <i class="fas ${avatarIcon}"></i>
              ${avatarNum}
            </div>
            <div class="machine-meta">
              <h3>${m.nombre}</h3>
              <span>${m.tipo}</span>
            </div>
          </div>
          <div class="status-badge-chip ${statusClass}">
            <span class="status-dot-mini"></span>
            ${statusText}
          </div>
        </div>

        <div class="machine-kpis-chips">
          ${chipsHtml}
        </div>

        <button class="btn-card-action" type="button">
          <span>Ver Dashboard & Gráfica</span>
          <i class="fas fa-chevron-right"></i>
        </button>
      </div>
    `;
  });

  container.innerHTML = html;
}

// Gráfico comparativo general de líneas en la vista Resumen
function renderResumenGeneralChart() {
  const canvas = document.getElementById('chart-resumen-general');
  if (!canvas) return;

  const tl = state.machinesData.TUNEL_LAVADO;
  const c2 = state.machinesData.CALANDRA_2;
  const c3 = state.machinesData.CALANDRA_3;
  const vt = state.machinesData.TUNEL_VT;

  // Extraer etiquetas comunes
  let labels = [];
  if (tl && tl.grafica_avance && tl.grafica_avance.labels) {
    labels = cleanHourLabels(tl.grafica_avance.labels);
  } else if (c2 && c2.indicadores && c2.indicadores.grafica_hora_a_hora) {
    labels = cleanHourLabels(c2.indicadores.grafica_hora_a_hora.labels);
  }

  if (labels.length === 0) return;

  const metric = state.chartMetrics.resumen || 'kg';
  const datasets = [];

  if (metric === 'kg') {
    if (tl && tl.grafica_avance && tl.grafica_avance.kg_por_hora) {
      datasets.push({
        type: 'line',
        label: 'Túnel Lavado (Kg/h)',
        data: tl.grafica_avance.kg_por_hora,
        borderColor: '#00f0ff',
        backgroundColor: 'rgba(0, 240, 255, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
    if (c2 && c2.indicadores && c2.indicadores.grafica_hora_a_hora) {
      const g = c2.indicadores.grafica_hora_a_hora;
      const pGrandes = (c2.indicadores.desglose_calandra2 && c2.indicadores.desglose_calandra2.peso_unitario_grandes) || 0.78;
      const pPequenas = (c2.indicadores.desglose_calandra2 && c2.indicadores.desglose_calandra2.peso_unitario_pequenas) || 0.47;
      const kgData = (g.prendas || []).map((p, idx) => {
        const gr = (g.grandes && g.grandes[idx]) || 0;
        const pq = (g.pequenas && g.pequenas[idx]) || (p - gr);
        return Math.round((gr * pGrandes) + (pq * pPequenas));
      });
      datasets.push({
        type: 'line',
        label: 'Calandra 2 (Kg/h)',
        data: kgData,
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
    if (c3 && c3.indicadores && c3.indicadores.grafica_hora_a_hora) {
      const pUnit = (c3.indicadores.peso_unitario_info && c3.indicadores.peso_unitario_info.peso_unitario) || 1.18;
      const kgData = (c3.indicadores.grafica_hora_a_hora.prendas || []).map(p => Math.round(p * pUnit));
      datasets.push({
        type: 'line',
        label: 'Calandra 3 (Kg/h)',
        data: kgData,
        borderColor: '#34d399',
        backgroundColor: 'rgba(52, 211, 153, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
    if (vt && vt.indicadores && vt.indicadores.grafica_hora_a_hora) {
      const pUnit = vt.indicadores.peso_unitario || 0.25;
      const kgData = (vt.indicadores.grafica_hora_a_hora.prendas_totales || []).map(p => Math.round(p * pUnit));
      datasets.push({
        type: 'line',
        label: 'Túnel VT (Kg/h)',
        data: kgData,
        borderColor: '#c084fc',
        backgroundColor: 'rgba(192, 132, 252, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
  } else {
    // Modo prendas
    if (c2 && c2.indicadores && c2.indicadores.grafica_hora_a_hora) {
      datasets.push({
        type: 'line',
        label: 'Calandra 2 (Prendas/h)',
        data: c2.indicadores.grafica_hora_a_hora.prendas || [],
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56, 189, 248, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
    if (c3 && c3.indicadores && c3.indicadores.grafica_hora_a_hora) {
      datasets.push({
        type: 'line',
        label: 'Calandra 3 (Prendas/h)',
        data: c3.indicadores.grafica_hora_a_hora.prendas || [],
        borderColor: '#34d399',
        backgroundColor: 'rgba(52, 211, 153, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
    if (vt && vt.indicadores && vt.indicadores.grafica_hora_a_hora) {
      datasets.push({
        type: 'line',
        label: 'Túnel VT (Prendas/h)',
        data: vt.indicadores.grafica_hora_a_hora.prendas_totales || [],
        borderColor: '#c084fc',
        backgroundColor: 'rgba(192, 132, 252, 0.08)',
        borderWidth: 2.5,
        pointRadius: 3,
        tension: 0.35,
        fill: false
      });
    }
  }

  const ctx = canvas.getContext('2d');
  if (state.charts.resumen) {
    state.charts.resumen.destroy();
  }

  state.charts.resumen = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(56, 189, 248, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: { color: '#94a3b8', font: { size: 9 } },
          beginAtZero: true
        }
      }
    }
  });
}

function toggleResumenChart(metric) {
  state.chartMetrics.resumen = metric;
  const container = document.getElementById('toggles-resumen');
  if (container) {
    container.querySelectorAll('.btn-toggle-metric').forEach(btn => {
      if (btn.dataset.metric === metric) btn.classList.add('active');
      else btn.classList.remove('active');
    });
  }
  renderResumenGeneralChart();
}

// Renderizado del detalle de máquina seleccionada
function renderMachineDetail(machineKey) {
  const data = state.machinesData[machineKey];
  if (!data) return;

  if (machineKey === 'TUNEL_LAVADO') {
    renderTunelLavadoDetail(data);
  } else if (machineKey === 'CALANDRA_2') {
    renderCalandraDetail('CALANDRA_2', data);
  } else if (machineKey === 'CALANDRA_3') {
    renderCalandraDetail('CALANDRA_3', data);
  } else if (machineKey === 'TUNEL_VT') {
    renderTunelVTDetail(data);
  }
}

// 1. Detalle de Túnel de Lavado (Idéntico al Dashboard Ampliado)
function renderTunelLavadoDetail(data) {
  const ind = data.indicadores_destacados || {};
  const turno = data.turno_activo || {};

  setElementText('tl-turno-titulo', `${turno.nombre || 'Turno Activo'} (${turno.horario || ''})`);
  setElementText('tl-turno-fecha', turno.fecha || '');
  
  // Extraer valores reales evitando [object Object]
  setElementText('tl-kilos-turno', getVal(ind.kg_totales_turno, '0 kg'));
  setElementText('tl-cargas-turno', getVal(ind.cargas_totales_turno, '0 cargas'));
  setElementText('tl-ritmo-hprod', getVal(ind.hprod, '0 kg/h'));
  
  const ik = ind.ikprod || {};
  const ikVal = typeof ik === 'object' ? (ik.valor || ik.pct_str || '0%') : String(ik);
  const ikNeto = typeof ik === 'object' ? (ik.neto_str || '') : '';
  const ikTprom = typeof ik === 'object' ? (ik.tprom_str || '') : '';
  const ikColor = typeof ik === 'object' ? (ik.text_color || '#34d399') : '#34d399';

  setElementText('tl-ikprod-val', ikVal);
  setElementText('tl-ikprod-sub', `${ikNeto} | ${ikTprom}`);
  const ikEl = document.getElementById('tl-ikprod-val');
  if (ikEl) ikEl.style.color = ikColor;

  // Información Operativa extra
  setElementText('tl-clientes-unicos', getVal(ind.clientes_unicos, '0 clientes'));
  setElementText('tl-programas-unicos', getVal(ind.programas_unicos, '0 programas'));
  setElementText('tl-minutos-transcurridos', `${turno.minutos_transcurridos || 0} min`);

  // Renderizar gráfico de Túnel
  renderTunelChart(data.grafica_avance);
}

function renderTunelChart(grafica) {
  const canvas = document.getElementById('chart-tunel-lavado');
  if (!canvas || !grafica) return;

  const ctx = canvas.getContext('2d');
  if (state.charts.TUNEL_LAVADO) {
    state.charts.TUNEL_LAVADO.destroy();
  }

  const metric = state.chartMetrics.TUNEL_LAVADO || 'combo';
  const labels = cleanHourLabels(grafica.labels || []);
  const kgAcumulado = grafica.kg_acumulado || [];
  const kgPorHora = grafica.kg_por_hora || [];
  const cargasPorHora = grafica.cargas_por_hora || [];

  const datasets = [];
  const scales = {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
    }
  };

  if (metric === 'combo') {
    // 1. Línea Kg Acumulados
    datasets.push({
      type: 'line',
      label: 'Kg Acumulados',
      data: kgAcumulado,
      borderColor: '#00f0ff',
      backgroundColor: 'rgba(0, 240, 255, 0.08)',
      borderWidth: 2.8,
      pointRadius: 4,
      pointBackgroundColor: '#0284c7',
      pointBorderColor: '#00f0ff',
      tension: 0.3,
      fill: true,
      yAxisID: 'yKg'
    });

    // 2. Línea Kg / Hora
    datasets.push({
      type: 'line',
      label: 'Kg / Hora',
      data: kgPorHora,
      borderColor: '#ff3b70',
      backgroundColor: 'rgba(255, 59, 112, 0.08)',
      borderWidth: 2.8,
      pointRadius: 4,
      pointBackgroundColor: '#e11d48',
      pointBorderColor: '#ff3b70',
      tension: 0.3,
      fill: false,
      yAxisID: 'yKg'
    });

    // 3. Barras Cargas / Hora (Eje Derecho)
    datasets.push({
      type: 'bar',
      label: 'Cargas / Hora',
      data: cargasPorHora,
      backgroundColor: 'rgba(245, 158, 11, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.45,
      yAxisID: 'yCargas'
    });

    scales.yKg = {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Kg', color: '#00f0ff', font: { weight: 'bold', size: 9 } },
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#00f0ff', font: { size: 9 } },
      beginAtZero: true
    };

    scales.yCargas = {
      type: 'linear',
      position: 'right',
      title: { display: true, text: 'Cargas', color: '#fbbf24', font: { weight: 'bold', size: 9 } },
      grid: { drawOnChartArea: false },
      ticks: { color: '#fbbf24', font: { size: 9 }, stepSize: 1, precision: 0 },
      beginAtZero: true
    };

  } else if (metric === 'kg') {
    datasets.push({
      type: 'line',
      label: 'Kg Acumulados',
      data: kgAcumulado,
      borderColor: '#00f0ff',
      backgroundColor: 'rgba(0, 240, 255, 0.08)',
      borderWidth: 2.8,
      pointRadius: 4,
      tension: 0.3,
      fill: true
    });
    datasets.push({
      type: 'line',
      label: 'Kg / Hora',
      data: kgPorHora,
      borderColor: '#ff3b70',
      borderWidth: 2.8,
      pointRadius: 4,
      tension: 0.3,
      fill: false
    });
    scales.y = {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#00f0ff', font: { size: 9 } },
      beginAtZero: true
    };

  } else {
    // Solo cargas
    datasets.push({
      type: 'bar',
      label: 'Cargas / Hora',
      data: cargasPorHora,
      backgroundColor: 'rgba(245, 158, 11, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4
    });
    scales.y = {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#fbbf24', font: { size: 9 }, stepSize: 1, precision: 0 },
      beginAtZero: true
    };
  }

  state.charts.TUNEL_LAVADO = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(56, 189, 248, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales: scales
    }
  });
}

// 2. Detalle de Calandra 2 y 3 (Líneas de Prendas, Kg y Barras de Valle idénticas al Dashboard Ampliado)
function renderCalandraDetail(machineKey, data) {
  const prefix = machineKey === 'CALANDRA_2' ? 'c2' : 'c3';
  const ind = data.indicadores || {};
  const turno = data.turno_info || {};

  setElementText(`${prefix}-turno-titulo`, `${turno.nombre || 'Turno Activo'} (${turno.horario || ''})`);
  setElementText(`${prefix}-turno-fecha`, turno.fecha || '');
  setElementText(`${prefix}-prendas-totales`, ind.prendas_totales_str || (ind.prendas_totales ? `${ind.prendas_totales.toLocaleString('es-ES')} prendas` : '0 prendas'));
  setElementText(`${prefix}-kgs-totales`, ind.kgs_totales_str || '0 kg');
  setElementText(`${prefix}-ritmo-prendas`, ind.prendas_hora_str || '0 /h');
  setElementText(`${prefix}-tiempo-valle`, ind.tiempo_valle_str || '0 min');
  setElementText(`${prefix}-tiempo-descanso`, ind.tiempo_descanso_str || '0 min');

  // Desglose específico para Calandra 2 (Grandes vs Pequeñas)
  if (machineKey === 'CALANDRA_2' && ind.desglose_calandra2) {
    const d = ind.desglose_calandra2;
    setElementText('c2-pequenas-val', `${d.prendas_pequenas_str || '0 pequeñas'} (${d.kg_pequenas_str || '0 kg'})`);
    setElementText('c2-grandes-val', `${d.prendas_grandes_str || '0 grandes'} (${d.kg_grandes_str || '0 kg'})`);
  }

  // Información específica para Calandra 3 (Inspección Óptica IA)
  if (machineKey === 'CALANDRA_3') {
    setElementText('c3-peso-val', ind.peso_unitario_str || '1180 gr/u');
    setElementText('c3-kg-hora-val', ind.kg_hora_str || '0 kg/h');
    setElementText('c3-cadencia-val', ind.prendas_hora_str || '0 /h');
  }

  // Gráfico con líneas de prendas / kg y barras de valle
  renderCalandraChart(machineKey, ind.grafica_hora_a_hora, ind);
}

function renderCalandraChart(machineKey, grafica, ind) {
  const prefix = machineKey === 'CALANDRA_2' ? 'c2' : 'c3';
  const canvas = document.getElementById(`chart-${prefix}`);
  if (!canvas || !grafica) return;

  const ctx = canvas.getContext('2d');
  if (state.charts[machineKey]) {
    state.charts[machineKey].destroy();
  }

  const metric = state.chartMetrics[machineKey] || 'combo';
  const labels = cleanHourLabels(grafica.labels || []);
  const prendasData = grafica.prendas || [];
  const valleData = grafica.tiempo_valle || [];
  const descansoData = grafica.tiempo_descanso || [];
  const isCal2 = (machineKey === 'CALANDRA_2');

  const datasets = [];
  const scales = {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
    }
  };

  if (metric === 'combo') {
    // 1. Línea Prendas Totales
    datasets.push({
      type: 'line',
      label: isCal2 ? 'Prendas Totales' : 'Prendas Producidas',
      data: prendasData,
      borderColor: '#38bdf8',
      backgroundColor: 'rgba(56, 189, 248, 0.12)',
      borderWidth: 2.8,
      pointBackgroundColor: '#0284c7',
      pointBorderColor: '#38bdf8',
      pointRadius: 4,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });

    // En Calandra 2, añadir líneas de Grandes y Pequeñas
    if (isCal2 && grafica.grandes && grafica.pequenas) {
      datasets.push({
        type: 'line',
        label: 'Grandes',
        data: grafica.grandes,
        borderColor: '#c084fc',
        borderWidth: 1.8,
        borderDash: [4, 4],
        pointRadius: 3,
        tension: 0.35,
        fill: false,
        yAxisID: 'yPrendas'
      });
      datasets.push({
        type: 'line',
        label: 'Pequeñas',
        data: grafica.pequenas,
        borderColor: '#60a5fa',
        borderWidth: 1.8,
        borderDash: [2, 2],
        pointRadius: 3,
        tension: 0.35,
        fill: false,
        yAxisID: 'yPrendas'
      });
    }

    // Barras de Tiempo Valle (Eje Derecho)
    datasets.push({
      type: 'bar',
      label: 'Tiempo Valle (min)',
      data: valleData,
      backgroundColor: 'rgba(245, 158, 11, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.45,
      yAxisID: 'yValle'
    });

    // Barras de Tiempo Descanso
    datasets.push({
      type: 'bar',
      label: 'Descanso (min)',
      data: descansoData,
      backgroundColor: 'rgba(185, 28, 28, 0.85)',
      borderColor: '#ef4444',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.45,
      yAxisID: 'yValle'
    });

    scales.yPrendas = {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Prendas', color: '#38bdf8', font: { weight: 'bold', size: 9 } },
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#38bdf8', font: { size: 9 } },
      beginAtZero: true
    };

    scales.yValle = {
      type: 'linear',
      position: 'right',
      title: { display: true, text: 'Valle (min)', color: '#fbbf24', font: { weight: 'bold', size: 9 } },
      grid: { drawOnChartArea: false },
      ticks: { color: '#fbbf24', font: { size: 9 } },
      beginAtZero: true
    };

  } else if (metric === 'kg') {
    // Curva de kilogramos hora a hora
    let kgData = [];
    if (isCal2 && ind.desglose_calandra2) {
      const pGrandes = ind.desglose_calandra2.peso_unitario_grandes || 0.78;
      const pPequenas = ind.desglose_calandra2.peso_unitario_pequenas || 0.47;
      kgData = prendasData.map((p, idx) => {
        const gr = (grafica.grandes && grafica.grandes[idx]) || 0;
        const pq = (grafica.pequenas && grafica.pequenas[idx]) || (p - gr);
        return Math.round((gr * pGrandes) + (pq * pPequenas));
      });
      datasets.push({
        type: 'line',
        label: 'Kg Totales / Hora',
        data: kgData,
        borderColor: '#34d399',
        backgroundColor: 'rgba(52, 211, 153, 0.12)',
        borderWidth: 2.8,
        pointRadius: 4,
        tension: 0.35,
        fill: true
      });
    } else {
      const pUnit = (ind && ind.peso_unitario_info && ind.peso_unitario_info.peso_unitario) || 1.18;
      kgData = prendasData.map(p => Math.round(p * pUnit));
      datasets.push({
        type: 'line',
        label: 'Kg / Hora Estimados',
        data: kgData,
        borderColor: '#34d399',
        backgroundColor: 'rgba(52, 211, 153, 0.12)',
        borderWidth: 2.8,
        pointRadius: 4,
        tension: 0.35,
        fill: true
      });
    }

    scales.y = {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#34d399', font: { size: 9 } },
      beginAtZero: true
    };

  } else {
    // Solo prendas
    datasets.push({
      type: 'line',
      label: 'Prendas Producidas',
      data: prendasData,
      borderColor: '#38bdf8',
      backgroundColor: 'rgba(56, 189, 248, 0.12)',
      borderWidth: 2.8,
      pointRadius: 4,
      tension: 0.35,
      fill: true
    });
    scales.y = {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#38bdf8', font: { size: 9 } },
      beginAtZero: true
    };
  }

  state.charts[machineKey] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(56, 189, 248, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales: scales
    }
  });
}

// 3. Detalle de Túnel VT (Líneas de 3 Vías de Prendas, Total y Tiempo Valle)
function renderTunelVTDetail(data) {
  const ind = data.indicadores || {};
  const turno = data.turno_info || {};

  setElementText('vt-turno-titulo', `${turno.nombre || 'Turno Activo'} (${turno.horario || ''})`);
  setElementText('vt-turno-fecha', turno.fecha || '');
  setElementText('vt-prendas-totales', ind.prendas_totales_str || (ind.prendas_totales ? `${ind.prendas_totales.toLocaleString('es-ES')} prendas` : '0 prendas'));
  setElementText('vt-kgs-totales', ind.kgs_totales_str || '0 kg');
  setElementText('vt-ritmo-prendas', ind.prendas_hora_str || '0 /h');
  setElementText('vt-tiempo-valle', ind.tiempo_valle_total_str || ind.tiempo_valle_str || '0 min');
  setElementText('vt-tiempo-descanso', ind.tiempo_descanso_str || '0 min');

  // Desglose de 3 vías con formato exacto
  if (ind.desglose_entradas) {
    const d = ind.desglose_entradas;
    setElementText('vt-via1-val', `${d.entrada_1_str || '0 prendas'} (${d.kg_e1_str || '0,0 kg'})`);
    setElementText('vt-via2-val', `${d.entrada_2_str || '0 prendas'} (${d.kg_e2_str || '0,0 kg'})`);
    setElementText('vt-via3-val', `${d.entrada_3_str || '0 prendas'} (${d.kg_e3_str || '0,0 kg'})`);
  }

  // Gráfico VT con 3 líneas de entrada y valle
  renderTunelVTChart(ind.grafica_hora_a_hora, ind);
}

function renderTunelVTChart(grafica, ind) {
  const canvas = document.getElementById('chart-vt');
  if (!canvas || !grafica) return;

  const ctx = canvas.getContext('2d');
  if (state.charts.TUNEL_VT) {
    state.charts.TUNEL_VT.destroy();
  }

  const metric = state.chartMetrics.TUNEL_VT || 'combo';
  const labels = cleanHourLabels(grafica.labels || []);
  const e1Data = grafica.entrada_1 || [];
  const e2Data = grafica.entrada_2 || [];
  const e3Data = grafica.entrada_3 || [];
  const totalPrendas = grafica.prendas_totales || [];
  const valleTotal = grafica.valle_total || [];

  const datasets = [];
  const scales = {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
    }
  };

  if (metric === 'combo') {
    // Línea Total Prendas
    datasets.push({
      type: 'line',
      label: 'Total Prendas',
      data: totalPrendas,
      borderColor: '#ffffff',
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
      borderWidth: 3,
      pointRadius: 4,
      pointBackgroundColor: '#ffffff',
      pointBorderColor: '#38bdf8',
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });

    // Líneas de cada entrada (3 vías)
    datasets.push({
      type: 'line',
      label: 'Vía 1',
      data: e1Data,
      borderColor: '#38bdf8',
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });
    datasets.push({
      type: 'line',
      label: 'Vía 2',
      data: e2Data,
      borderColor: '#34d399',
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });
    datasets.push({
      type: 'line',
      label: 'Vía 3',
      data: e3Data,
      borderColor: '#c084fc',
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });

    // Barras Tiempo Valle (Eje Derecho)
    datasets.push({
      type: 'bar',
      label: 'Tiempo Valle (min)',
      data: valleTotal,
      backgroundColor: 'rgba(245, 158, 11, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.45,
      yAxisID: 'yValle'
    });

    scales.yPrendas = {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Prendas', color: '#ffffff', font: { weight: 'bold', size: 9 } },
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#ffffff', font: { size: 9 } },
      beginAtZero: true
    };

    scales.yValle = {
      type: 'linear',
      position: 'right',
      title: { display: true, text: 'Valle (min)', color: '#fbbf24', font: { weight: 'bold', size: 9 } },
      grid: { drawOnChartArea: false },
      ticks: { color: '#fbbf24', font: { size: 9 } },
      beginAtZero: true
    };

  } else if (metric === 'kg') {
    // Modo Kg por hora de Túnel VT
    const pUnit = (ind && ind.peso_unitario) || 0.25;
    const kgTotal = totalPrendas.map(p => Math.round(p * pUnit));
    datasets.push({
      type: 'line',
      label: 'Kg Totales / Hora',
      data: kgTotal,
      borderColor: '#818cf8',
      backgroundColor: 'rgba(129, 140, 248, 0.12)',
      borderWidth: 2.8,
      pointRadius: 4,
      tension: 0.35,
      fill: true
    });
    scales.y = {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#818cf8', font: { size: 9 } },
      beginAtZero: true
    };

  } else {
    // Solo total prendas
    datasets.push({
      type: 'line',
      label: 'Prendas Totales',
      data: totalPrendas,
      borderColor: '#ffffff',
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
      borderWidth: 2.8,
      pointRadius: 4,
      tension: 0.35,
      fill: true
    });
    scales.y = {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#ffffff', font: { size: 9 } },
      beginAtZero: true
    };
  }

  state.charts.TUNEL_VT = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(56, 189, 248, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales: scales
    }
  });
}

// Alternar métrica de gráfico (ej: combo <-> kg <-> prendas/cargas)
function toggleChartMetric(machineKey, metric) {
  state.chartMetrics[machineKey] = metric;
  
  // Actualizar botones activos
  const container = document.getElementById(`toggles-${machineKey.toLowerCase()}`);
  if (container) {
    container.querySelectorAll('.btn-toggle-metric').forEach(btn => {
      if (btn.dataset.metric === metric) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  renderMachineDetail(machineKey);
}

// Redimensionar el gráfico de la pestaña actual
function resizeCurrentChart() {
  const current = state.activeTab;
  if (current === 'resumen') {
    if (state.charts.resumen) state.charts.resumen.resize();
  } else if (current === 'historial') {
    if (state.historial.chart) state.historial.chart.resize();
  } else {
    const key = current.toUpperCase();
    if (state.charts[key]) state.charts[key].resize();
  }
}

// Helpers
function setElementText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/* ==========================================================================
   MÓDULO HISTORIAL DE TURNOS MÓVIL Y TABLET
   ========================================================================== */

// Abre el historial desde cualquier botón de máquina
function openMobileHistorial(machineKey) {
  state.historial.previousTab = (state.activeTab === 'historial') ? 'resumen' : state.activeTab;
  state.historial.currentMachine = machineKey || 'TUNEL_LAVADO';
  
  const sel = document.getElementById('m-historial-maquina-select');
  if (sel) sel.value = state.historial.currentMachine;
  
  switchTab('historial');
}

// Vuelve a la máquina o resumen anterior
function volverDesdeHistorialMobile() {
  const target = state.historial.previousTab || 'resumen';
  switchTab(target);
}

// Enlaza eventos táctiles del historial una sola vez
function bindMobileHistorialEvents() {
  if (state.historial.eventsBound) return;

  const maquinaSel = document.getElementById('m-historial-maquina-select');
  const fechaPicker = document.getElementById('m-historial-fecha-picker');
  const turnoSel = document.getElementById('m-historial-turno-select');

  if (maquinaSel) {
    maquinaSel.addEventListener('change', async (e) => {
      state.historial.currentMachine = e.target.value;
      resetMobileHistorialView();
      await loadMobileHistorialFechas(state.historial.currentMachine);
    });
  }

  if (fechaPicker) {
    fechaPicker.addEventListener('change', async (e) => {
      const val = e.target.value;
      if (val) {
        await loadMobileHistorialShifts(val);
      } else {
        if (turnoSel) {
          turnoSel.innerHTML = '<option value="">-- Seleccionar Turno --</option>';
          turnoSel.disabled = true;
        }
        resetMobileHistorialView();
      }
    });
  }

  if (turnoSel) {
    turnoSel.addEventListener('change', async (e) => {
      const shiftKey = e.target.value;
      if (shiftKey) {
        await loadMobileHistoricalShift(shiftKey);
      } else {
        resetMobileHistorialView();
      }
    });
  }

  state.historial.eventsBound = true;
}

// Inicialización de la pantalla de Historial al seleccionarla
async function initMobileHistorialScreen() {
  const maquinaSel = document.getElementById('m-historial-maquina-select');
  const fechaPicker = document.getElementById('m-historial-fecha-picker');
  
  if (maquinaSel && maquinaSel.value !== state.historial.currentMachine) {
    maquinaSel.value = state.historial.currentMachine;
  }

  // Si aún no hay fecha o se cambió de máquina, cargar fechas disponibles
  if (!fechaPicker || !fechaPicker.value) {
    await loadMobileHistorialFechas(state.historial.currentMachine);
  }
}

// Resetea vista de historial al estado inicial
function resetMobileHistorialView() {
  const placeholder = document.getElementById('m-historial-placeholder');
  const content = document.getElementById('m-historial-dashboard-content');
  if (placeholder) placeholder.style.display = 'block';
  if (content) {
    content.style.display = 'none';
    content.innerHTML = '';
  }
  if (state.historial.chart) {
    try {
      state.historial.chart.destroy();
    } catch (e) {
      console.warn('Error destruyendo state.historial.chart:', e);
    }
    state.historial.chart = null;
  }
}

// Carga las fechas disponibles para la máquina seleccionada
async function loadMobileHistorialFechas(machineKey) {
  const fechaPicker = document.getElementById('m-historial-fecha-picker');
  if (!fechaPicker) return;

  try {
    let endpoint = '/api/produccion/turnos/fechas-disponibles';
    if (machineKey === 'CALANDRA_2' || machineKey === 'CALANDRA_3') {
      endpoint = `/api/produccion/calandras/${machineKey}/turnos-fechas`;
    } else if (machineKey === 'TUNEL_VT') {
      endpoint = '/api/produccion/tunel-vt/turnos-fechas';
    }

    const res = await fetch(endpoint);
    let targetFecha = new Date().toISOString().split('T')[0];
    if (res.ok) {
      const data = await res.json();
      if (data.hoy) targetFecha = data.hoy;
      else if (data.fechas && data.fechas.length > 0) targetFecha = data.fechas[0];
    }

    fechaPicker.max = new Date().toISOString().split('T')[0];
    fechaPicker.value = targetFecha;

    await loadMobileHistorialShifts(targetFecha);
  } catch (err) {
    console.error('Error cargando fechas de historial móvil:', err);
    fechaPicker.value = new Date().toISOString().split('T')[0];
    await loadMobileHistorialShifts(fechaPicker.value);
  }
}

// Carga los turnos para la fecha seleccionada
async function loadMobileHistorialShifts(fechaStr) {
  const turnoSel = document.getElementById('m-historial-turno-select');
  if (!turnoSel) return;

  try {
    turnoSel.innerHTML = '<option value="">Cargando turnos...</option>';
    turnoSel.disabled = true;

    let endpoint = `/api/produccion/turnos/por-fecha/${fechaStr}`;
    if (state.historial.currentMachine === 'CALANDRA_2' || state.historial.currentMachine === 'CALANDRA_3') {
      endpoint = `/api/produccion/calandras/${state.historial.currentMachine}/turnos-por-fecha/${fechaStr}`;
    } else if (state.historial.currentMachine === 'TUNEL_VT') {
      endpoint = `/api/produccion/tunel-vt/turnos-por-fecha/${fechaStr}`;
    }

    const res = await fetch(endpoint);
    if (!res.ok) throw new Error('Error al obtener turnos de la jornada');
    const data = await res.json();

    turnoSel.innerHTML = '<option value="">-- Seleccionar Turno --</option>';

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

          if (state.historial.currentMachine === 'TUNEL_LAVADO') {
            const kgNum = typeof t.total_kg === 'number' ? Math.round(t.total_kg).toLocaleString('es-ES') : (t.total_kg || 0);
            opt.textContent = `${t.nombre_turno} (${t.horario}) — ${kgNum} kg${estadoTag}`;
          } else {
            const pTot = Math.round(t.prendas_totales || 0).toLocaleString('es-ES');
            const kgTot = (typeof t.kgs_totales === 'number' ? t.kgs_totales.toFixed(1) : (t.kgs_totales || 0)).toLocaleString('es-ES');
            const horarioStr = t.horario || t.rango_horario || '';
            opt.textContent = `${t.nombre_turno} (${horarioStr}) — ${pTot} p | ${kgTot} kg${estadoTag}`;
          }
          turnoSel.appendChild(opt);
        });

        turnoSel.disabled = false;
        
        // Auto-seleccionar y cargar el turno más reciente disponible para comodidad táctil
        turnoSel.selectedIndex = 1;
        await loadMobileHistoricalShift(turnoSel.value);
        return;
      }
    }

    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Sin turnos procesados en esta jornada';
    turnoSel.appendChild(opt);
    turnoSel.disabled = true;
    resetMobileHistorialView();

  } catch (err) {
    console.error('Error cargando turnos en historial móvil:', err);
    turnoSel.innerHTML = '<option value="">Error al cargar turnos</option>';
    turnoSel.disabled = true;
    resetMobileHistorialView();
  }
}

// Carga el paquete reconstruido del turno seleccionado
async function loadMobileHistoricalShift(shiftKey) {
  const placeholder = document.getElementById('m-historial-placeholder');
  const content = document.getElementById('m-historial-dashboard-content');
  if (!content) return;

  try {
    if (placeholder) placeholder.style.display = 'none';
    content.style.display = 'block';
    content.innerHTML = `
      <div style="text-align: center; padding: 30px; color: var(--text-secondary);">
        <i class="fas fa-spinner fa-spin" style="font-size: 1.8rem; color: var(--color-cyan); margin-bottom: 10px;"></i>
        <p style="font-size: 0.9rem; font-weight: 600;">Reconstruyendo datos del turno...</p>
      </div>
    `;

    if (state.historial.chart) {
      try {
        state.historial.chart.destroy();
      } catch (e) {
        console.warn('Destruyendo gráfico anterior:', e);
      }
      state.historial.chart = null;
    }

    let endpoint = `/api/produccion/turnos/historial-json/${shiftKey}`;
    if (state.historial.currentMachine === 'CALANDRA_2' || state.historial.currentMachine === 'CALANDRA_3') {
      endpoint = `/api/produccion/calandras/${state.historial.currentMachine}/turnos-historial/${shiftKey}`;
    } else if (state.historial.currentMachine === 'TUNEL_VT') {
      endpoint = `/api/produccion/tunel-vt/turnos-historial/${shiftKey}`;
    }

    const res = await fetch(endpoint);
    if (!res.ok) throw new Error('No se pudo obtener el historial del turno');
    const pkg = await res.json();

    if (state.historial.currentMachine === 'TUNEL_LAVADO') {
      renderMobileShiftTunelLavado(pkg, shiftKey);
    } else if (state.historial.currentMachine === 'CALANDRA_2' || state.historial.currentMachine === 'CALANDRA_3') {
      renderMobileShiftCalandra(pkg, shiftKey, state.historial.currentMachine === 'CALANDRA_2');
    } else if (state.historial.currentMachine === 'TUNEL_VT') {
      renderMobileShiftTunelVT(pkg, shiftKey);
    }

  } catch (err) {
    console.error('Error renderizando dashboard de turno en móvil:', err);
    content.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5; padding: 16px; border-radius: 12px; text-align: center;">
        <i class="fas fa-exclamation-triangle" style="font-size: 1.4rem; margin-bottom: 8px;"></i>
        <p style="font-size: 0.85rem; font-weight: 700;">No se pudo cargar el turno seleccionado.</p>
        <small style="font-size: 0.75rem; opacity: 0.85;">${err.message}</small>
      </div>
    `;
  }
}

// 1. Renderizado de Túnel de Lavado Reconstruido
function renderMobileShiftTunelLavado(pkg, shiftKey) {
  const content = document.getElementById('m-historial-dashboard-content');
  if (!content) return;

  const meta = pkg.meta_info || {};
  const ind = pkg.indicadores_ampliados || {};
  const tot = pkg.totales_promedios || {};
  const desglose = pkg.desglose_horario || {};

  const kgVal = ind.kg_totales_turno?.valor_str || getVal(ind.kg_totales_turno, '0 kg');
  const cargasVal = ind.cargas_totales_turno?.valor_str || getVal(ind.cargas_totales_turno, '0 cargas');
  const hprodVal = ind.productividad_hprod?.valor_str || getVal(ind.productividad_hprod, '0 kg/h');
  
  const ikprod = ind.indice_eficiencia_ikprod || {};
  const ikprodVal = ikprod.pct_str || (typeof ikprod === 'string' ? ikprod : '0.0%');
  const ikprodNeto = ikprod.neto_str || 'ikProd Neto: 0.00';
  const ikprodColor = ikprod.color_codigo === 'red' ? '#ef4444' : (ikprod.color_codigo === 'orange' ? '#f97316' : '#34d399');

  const clientesVal = (ind.clientes_unicos && ind.clientes_unicos.valor_num !== undefined) ? ind.clientes_unicos.valor_num : (ind.clientes_unicos?.valor_str || getVal(ind.clientes_unicos, '0'));
  const programasVal = (ind.programas_unicos && ind.programas_unicos.valor_num !== undefined) ? ind.programas_unicos.valor_num : (ind.programas_unicos?.valor_str || getVal(ind.programas_unicos, '0'));

  content.innerHTML = `
    <!-- Banner de Meta-información del Turno -->
    <div class="m-historial-meta-banner">
      <div class="m-historial-meta-left">
        <div class="machine-avatar-badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;">
          <i class="fas fa-circle-notch"></i>
        </div>
        <div>
          <h4>${meta.nombre_turno || 'Turno'} (${meta.hora_inicio || ''} - ${meta.hora_fin || ''})</h4>
          <span>📅 ${meta.fecha_formateada || meta.fecha || ''} &bull; SQLite (${shiftKey})</span>
        </div>
      </div>
      <div>
        ${meta.is_in_progress ?
          `<span style="font-size: 0.72rem; color: #34d399; font-weight: 700; background: rgba(16, 185, 129, 0.15); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.3);"><i class="fas fa-spinner fa-spin"></i> EN PROCESO</span>` :
          `<span style="font-size: 0.72rem; color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.15); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">📜 HISTORIAL</span>`
        }
      </div>
    </div>

    <!-- Grilla de KPIs del Turno -->
    <div class="landscape-split-layout">
      <div>
        <div class="m-historial-kpis-grid">
          <!-- Kg Totales -->
          <div class="m-historial-kpi-card cyan">
            <div class="h-kpi-head">
              <span>Kg Totales</span>
              <i class="fas fa-balance-scale" style="color: #38bdf8;"></i>
            </div>
            <div class="h-kpi-val" style="color: #38bdf8;">${kgVal}</div>
            <div class="h-kpi-sub">Obj: ${(tot.objetivo_turno_kg || 0).toLocaleString('es-ES')} kg</div>
          </div>

          <!-- ikProd Eficiencia -->
          <div class="m-historial-kpi-card" style="border-left: 3px solid ${ikprodColor};">
            <div class="h-kpi-head">
              <span>ikProd</span>
              <i class="fas fa-chart-line" style="color: ${ikprodColor};"></i>
            </div>
            <div class="h-kpi-val" style="color: ${ikprodColor};">${ikprodVal}</div>
            <div class="h-kpi-sub">${ikprodNeto}</div>
          </div>

          <!-- Cargas Totales -->
          <div class="m-historial-kpi-card amber">
            <div class="h-kpi-head">
              <span>Cargas</span>
              <i class="fas fa-boxes" style="color: #f59e0b;"></i>
            </div>
            <div class="h-kpi-val">${cargasVal}</div>
            <div class="h-kpi-sub">Prom: ${tot.promedio_peso_carga_kg || 0} kg/c</div>
          </div>

          <!-- Ritmo hProd -->
          <div class="m-historial-kpi-card green">
            <div class="h-kpi-head">
              <span>Ritmo hProd</span>
              <i class="fas fa-tachometer-alt" style="color: #34d399;"></i>
            </div>
            <div class="h-kpi-val">${hprodVal}</div>
            <div class="h-kpi-sub">Tprom: ${tot.promedio_tiempo_entre_cargas_min || 0} min</div>
          </div>
        </div>

        <div class="info-extra-card">
          <div class="info-extra-header">
            <i class="fas fa-info-circle" style="color: #38bdf8;"></i>
            <span>Datos Operativos Registrados</span>
          </div>
          <div class="info-extra-rows">
            <div class="info-row">
              <span class="info-row-label"><i class="fas fa-users"></i> Clientes Únicos:</span>
              <span class="info-row-val">${clientesVal}</span>
            </div>
            <div class="info-row">
              <span class="info-row-label"><i class="fas fa-layer-group"></i> Programas Únicos:</span>
              <span class="info-row-val">${programasVal}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Gráfico de Avance del Turno -->
      <div class="chart-panel-card">
        <div class="chart-panel-header">
          <span class="chart-title">
            <i class="fas fa-chart-line" style="color: #38bdf8;"></i>
            <span>Curva Histórica (Kg Acumulados & Cargas)</span>
          </span>
        </div>
        <div class="chart-canvas-wrapper">
          <canvas id="chart-mobile-historial"></canvas>
        </div>
      </div>
    </div>
  `;

  // Renderizar Gráfica
  const canvas = document.getElementById('chart-mobile-historial');
  if (!canvas) return;

  const labels = cleanHourLabels(desglose.labels || []);
  const kgHora = desglose.kg_por_hora || [];
  const cargasHora = desglose.cargas_por_hora || [];
  const kgAcum = desglose.kg_acumulado_por_hora || desglose.kg_acumulado || [];

  const datasets = [
    {
      type: 'line',
      label: 'Kg Acumulados',
      data: kgAcum,
      borderColor: '#00f0ff',
      backgroundColor: 'rgba(0, 240, 255, 0.08)',
      borderWidth: 2.8,
      pointRadius: 3.5,
      tension: 0.3,
      fill: false,
      yAxisID: 'yKgAcum'
    },
    {
      type: 'line',
      label: 'Kg / Hora',
      data: kgHora,
      borderColor: '#ff3b70',
      backgroundColor: 'rgba(255, 59, 112, 0.08)',
      borderWidth: 2.8,
      pointRadius: 3.5,
      tension: 0.3,
      fill: false,
      yAxisID: 'yKgHora'
    },
    {
      type: 'bar',
      label: 'Cargas / Hora',
      data: cargasHora,
      backgroundColor: 'rgba(245, 158, 11, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.45,
      yAxisID: 'yCargas'
    }
  ];

  const scales = {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
    },
    yKgHora: {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Kg/h', color: '#ff3b70', font: { size: 9, weight: 'bold' } },
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#ff3b70', font: { size: 9 } },
      beginAtZero: true
    },
    yKgAcum: {
      type: 'linear',
      position: 'left',
      display: false,
      beginAtZero: true
    },
    yCargas: {
      type: 'linear',
      position: 'right',
      title: { display: true, text: 'Cargas', color: '#fbbf24', font: { size: 9, weight: 'bold' } },
      grid: { drawOnChartArea: false },
      ticks: { color: '#fbbf24', font: { size: 9 } },
      beginAtZero: true
    }
  };

  const ctx = canvas.getContext('2d');
  state.historial.chart = new Chart(ctx, {
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(56, 189, 248, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales
    }
  });
}

// 2. Renderizado de Calandra 2 / Calandra 3 Reconstruido
function renderMobileShiftCalandra(pkg, shiftKey, isCal2) {
  const content = document.getElementById('m-historial-dashboard-content');
  if (!content) return;

  const ind = pkg.indicadores_dashboard || pkg.indicadores || {};
  const meta = pkg.meta_info || {};
  const g = pkg.desglose_hora_a_hora || pkg.grafica_hora_a_hora || ind.grafica_hora_a_hora || {};

  const turno = {
    nombre: meta.nombre_turno || pkg.turno_identificador || pkg.nombre_turno || 'Turno',
    horario: meta.rango_horario || pkg.rango_horario || `${pkg.hora_inicio || ''} - ${pkg.hora_fin || ''}`,
    fecha: meta.fecha_formateada || meta.fecha || pkg.fecha || ''
  };

  const prendasTotales = getVal(ind.prendas_totales_str, '0');
  const kgsTotales = getVal(ind.kgs_totales_str, '0 kg');
  const tiempoValle = getVal(ind.tiempo_valle_str, '0,0 min');
  const tiempoDescanso = getVal(ind.tiempo_descanso_str, '0 min');
  const ritmoPrendas = getVal(ind.prendas_hora_str, '0 p/h');
  const ritmoKgHora = getVal(ind.kg_hora_str, '0,0 kg/h');

  let subInfoHtml = '';
  if (isCal2 && ind.desglose_calandra2) {
    const d = ind.desglose_calandra2;
    subInfoHtml = `
      <div class="info-extra-card">
        <div class="info-extra-header">
          <i class="fas fa-layer-group" style="color: #34d399;"></i>
          <span>Desglose por Tipo de Prenda</span>
        </div>
        <div class="info-extra-rows">
          <div class="info-row">
            <span class="info-row-label"><i class="fas fa-tshirt" style="color: #38bdf8;"></i> Pequeñas:</span>
            <span class="info-row-val">${d.prendas_pequenas_str || '0'} (${d.kg_pequenas_str || '0 kg'})</span>
          </div>
          <div class="info-row">
            <span class="info-row-label"><i class="fas fa-sheet-plastic" style="color: #34d399;"></i> Grandes:</span>
            <span class="info-row-val">${d.prendas_grandes_str || '0'} (${d.kg_grandes_str || '0 kg'})</span>
          </div>
        </div>
      </div>
    `;
  } else if (!isCal2) {
    subInfoHtml = `
      <div class="info-extra-card">
        <div class="info-extra-header">
          <i class="fas fa-layer-group" style="color: #34d399;"></i>
          <span>Parámetros de Inspección IA</span>
        </div>
        <div class="info-extra-rows">
          <div class="info-row">
            <span class="info-row-label"><i class="fas fa-weight-hanging" style="color: #38bdf8;"></i> Peso Unitario:</span>
            <span class="info-row-val">${ind.peso_unitario_str || '1180 gr/u'}</span>
          </div>
          <div class="info-row">
            <span class="info-row-label"><i class="fas fa-balance-scale" style="color: #818cf8;"></i> Ritmo Horario:</span>
            <span class="info-row-val">${ritmoKgHora}</span>
          </div>
        </div>
      </div>
    `;
  }

  content.innerHTML = `
    <!-- Banner de Meta-información -->
    <div class="m-historial-meta-banner">
      <div class="m-historial-meta-left">
        <div class="machine-avatar-badge" style="background: rgba(52, 211, 153, 0.2); color: #34d399;">
          <i class="fas fa-scroll"></i>
          <span class="calandra-badge-num">${isCal2 ? '2' : '3'}</span>
        </div>
        <div>
          <h4>${turno.nombre} (${turno.horario})</h4>
          <span>📅 ${turno.fecha} &bull; SQLite (${shiftKey})</span>
        </div>
      </div>
      <div>
        <span style="font-size: 0.72rem; color: #34d399; font-weight: 700; background: rgba(52, 211, 153, 0.15); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(52, 211, 153, 0.3);">
          📜 HISTORIAL CALANDRA ${isCal2 ? '2' : '3'}
        </span>
      </div>
    </div>

    <div class="landscape-split-layout">
      <div>
        <div class="m-historial-kpis-grid">
          <!-- Prendas Totales -->
          <div class="m-historial-kpi-card green">
            <div class="h-kpi-head">
              <span>Prendas</span>
              <i class="fas fa-tshirt" style="color: #34d399;"></i>
            </div>
            <div class="h-kpi-val" style="color: #34d399;">${prendasTotales}</div>
            <div class="h-kpi-sub">Total procesado</div>
          </div>

          <!-- Kgs Totales -->
          <div class="m-historial-kpi-card cyan">
            <div class="h-kpi-head">
              <span>Kgs Totales</span>
              <i class="fas fa-weight-hanging" style="color: #38bdf8;"></i>
            </div>
            <div class="h-kpi-val">${kgsTotales}</div>
            <div class="h-kpi-sub">Kilos turno</div>
          </div>

          <!-- Tiempo Valle -->
          <div class="m-historial-kpi-card amber">
            <div class="h-kpi-head">
              <span>Tiempo Valle</span>
              <i class="fas fa-stopwatch" style="color: #f59e0b;"></i>
            </div>
            <div class="h-kpi-val" style="color: #f59e0b;">${tiempoValle}</div>
            <div class="h-kpi-sub">Descanso: ${tiempoDescanso}</div>
          </div>

          <!-- Cadencia Prendas/Hora -->
          <div class="m-historial-kpi-card purple">
            <div class="h-kpi-head">
              <span>Ritmo Prendas</span>
              <i class="fas fa-tachometer-alt" style="color: #c084fc;"></i>
            </div>
            <div class="h-kpi-val">${ritmoPrendas}</div>
            <div class="h-kpi-sub">Velocidad media</div>
          </div>
        </div>

        ${subInfoHtml}
      </div>

      <!-- Gráfico de Calandra -->
      <div class="chart-panel-card">
        <div class="chart-panel-header">
          <span class="chart-title">
            <i class="fas fa-chart-line" style="color: #34d399;"></i>
            <span>Curva Histórica (Prendas & Valle)</span>
          </span>
        </div>
        <div class="chart-canvas-wrapper">
          <canvas id="chart-mobile-historial"></canvas>
        </div>
      </div>
    </div>
  `;

  // Renderizar Gráfica
  const canvas = document.getElementById('chart-mobile-historial');
  if (!canvas) return;

  const labels = cleanHourLabels(g.labels || []);
  const prendasData = g.prendas || [];
  const valleData = g.tiempo_valle_min || g.tiempo_valle || [];
  const descansoData = g.tiempo_descanso || g.tiempo_descanso_min || [];

  const datasets = [
    {
      type: 'line',
      label: isCal2 ? 'Prendas Totales' : 'Prendas Producidas',
      data: prendasData,
      borderColor: '#38bdf8',
      backgroundColor: 'rgba(56, 189, 248, 0.12)',
      borderWidth: 2.8,
      pointRadius: 3.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    }
  ];

  if (isCal2 && g.grandes && g.pequenas) {
    datasets.push({
      type: 'line',
      label: 'Grandes',
      data: g.grandes,
      borderColor: '#c084fc',
      borderWidth: 1.8,
      borderDash: [4, 4],
      pointRadius: 2.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });
    datasets.push({
      type: 'line',
      label: 'Pequeñas',
      data: g.pequenas,
      borderColor: '#34d399',
      borderWidth: 1.8,
      borderDash: [2, 2],
      pointRadius: 2.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    });
  }

  // Barras de Valle
  datasets.push({
    type: 'bar',
    label: 'Valle (min)',
    data: valleData,
    backgroundColor: 'rgba(251, 191, 36, 0.75)',
    borderColor: '#fbbf24',
    borderWidth: 1,
    borderRadius: 4,
    barPercentage: 0.45,
    stack: 'valle',
    yAxisID: 'yValle'
  });

  // Barras de Descanso
  datasets.push({
    type: 'bar',
    label: 'Descanso (min)',
    data: descansoData,
    backgroundColor: 'rgba(185, 28, 28, 0.85)',
    borderColor: '#ef4444',
    borderWidth: 1,
    borderRadius: 4,
    barPercentage: 0.45,
    stack: 'valle',
    yAxisID: 'yValle'
  });

  const scales = {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
    },
    yPrendas: {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Prendas', color: '#38bdf8', font: { size: 9, weight: 'bold' } },
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#38bdf8', font: { size: 9 } },
      beginAtZero: true
    },
    yValle: {
      type: 'linear',
      position: 'right',
      title: { display: true, text: 'Valle min', color: '#fbbf24', font: { size: 9, weight: 'bold' } },
      grid: { drawOnChartArea: false },
      ticks: { color: '#fbbf24', font: { size: 9 } },
      beginAtZero: true,
      max: 60,
      stacked: true
    }
  };

  const ctx = canvas.getContext('2d');
  state.historial.chart = new Chart(ctx, {
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#34d399',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(52, 211, 153, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales
    }
  });
}

// 3. Renderizado de Túnel VT Reconstruido
function renderMobileShiftTunelVT(pkg, shiftKey) {
  const content = document.getElementById('m-historial-dashboard-content');
  if (!content) return;

  const ind = pkg.indicadores_dashboard || pkg.indicadores || {};
  const meta = pkg.meta_info || {};
  const de = ind.desglose_entradas || {};
  const g = pkg.desglose_hora_a_hora || pkg.grafica_hora_a_hora || ind.grafica_hora_a_hora || {};

  const turno = {
    nombre: meta.nombre_turno || pkg.turno_identificador || pkg.nombre_turno || 'Turno',
    horario: meta.rango_horario || pkg.rango_horario || `${pkg.hora_inicio || ''} - ${pkg.hora_fin || ''}`,
    fecha: meta.fecha_formateada || meta.fecha || pkg.fecha || ''
  };

  const prendasTotales = getVal(ind.prendas_totales_str, '0');
  const kgsTotales = getVal(ind.kgs_totales_str, '0 kg');
  const tiempoValle = getVal(ind.tiempo_valle_str, '0,0 min');
  const ritmoPrendas = getVal(ind.prendas_hora_str, '0 p/h');

  content.innerHTML = `
    <!-- Banner de Meta-información -->
    <div class="m-historial-meta-banner">
      <div class="m-historial-meta-left">
        <div class="machine-avatar-badge" style="background: rgba(129, 140, 248, 0.2); color: #818cf8;">
          <i class="fas fa-wind"></i>
        </div>
        <div>
          <h4>${turno.nombre} (${turno.horario})</h4>
          <span>📅 ${turno.fecha} &bull; SQLite (${shiftKey})</span>
        </div>
      </div>
      <div>
        <span style="font-size: 0.72rem; color: #818cf8; font-weight: 700; background: rgba(129, 140, 248, 0.15); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(129, 140, 248, 0.3);">
          📜 HISTORIAL TÚNEL VT
        </span>
      </div>
    </div>

    <div class="landscape-split-layout">
      <div>
        <div class="m-historial-kpis-grid">
          <!-- Prendas Totales -->
          <div class="m-historial-kpi-card purple">
            <div class="h-kpi-head">
              <span>Prendas</span>
              <i class="fas fa-tshirt" style="color: #818cf8;"></i>
            </div>
            <div class="h-kpi-val" style="color: #818cf8;">${prendasTotales}</div>
            <div class="h-kpi-sub">Total procesado</div>
          </div>

          <!-- Kgs Totales -->
          <div class="m-historial-kpi-card green">
            <div class="h-kpi-head">
              <span>Kgs Totales</span>
              <i class="fas fa-weight-hanging" style="color: #34d399;"></i>
            </div>
            <div class="h-kpi-val">${kgsTotales}</div>
            <div class="h-kpi-sub">Kilos turno</div>
          </div>

          <!-- Tiempo Valle Total -->
          <div class="m-historial-kpi-card amber">
            <div class="h-kpi-head">
              <span>Tiempo Valle</span>
              <i class="fas fa-stopwatch" style="color: #f59e0b;"></i>
            </div>
            <div class="h-kpi-val" style="color: #f59e0b;">${tiempoValle}</div>
            <div class="h-kpi-sub">Valle acumulado</div>
          </div>

          <!-- Cadencia Prendas/Hora -->
          <div class="m-historial-kpi-card cyan">
            <div class="h-kpi-head">
              <span>Ritmo Prendas</span>
              <i class="fas fa-tachometer-alt" style="color: #38bdf8;"></i>
            </div>
            <div class="h-kpi-val">${ritmoPrendas}</div>
            <div class="h-kpi-sub">Velocidad media</div>
          </div>
        </div>

        <div class="info-extra-card">
          <div class="info-extra-header">
            <i class="fas fa-random" style="color: #818cf8;"></i>
            <span>Producción por Vía de Entrada</span>
          </div>
          <div class="info-extra-rows">
            <div class="info-row">
              <span class="info-row-label"><i class="fas fa-circle-play" style="color: #38bdf8;"></i> Vía 1:</span>
              <span class="info-row-val">${de.entrada_1 || 0} p (${de.kg_e1_str || '0 kg'}) &bull; Valle: ${de.tiempo_valle_e1_str || '0 min'}</span>
            </div>
            <div class="info-row">
              <span class="info-row-label"><i class="fas fa-circle-play" style="color: #818cf8;"></i> Vía 2:</span>
              <span class="info-row-val">${de.entrada_2 || 0} p (${de.kg_e2_str || '0 kg'}) &bull; Valle: ${de.tiempo_valle_e2_str || '0 min'}</span>
            </div>
            <div class="info-row">
              <span class="info-row-label"><i class="fas fa-circle-play" style="color: #c084fc;"></i> Vía 3:</span>
              <span class="info-row-val">${de.entrada_3 || 0} p (${de.kg_e3_str || '0 kg'}) &bull; Valle: ${de.tiempo_valle_e3_str || '0 min'}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Gráfico de Túnel VT -->
      <div class="chart-panel-card">
        <div class="chart-panel-header">
          <span class="chart-title">
            <i class="fas fa-chart-line" style="color: #818cf8;"></i>
            <span>Curva Histórica (3 Vías & Valle)</span>
          </span>
        </div>
        <div class="chart-canvas-wrapper">
          <canvas id="chart-mobile-historial"></canvas>
        </div>
      </div>
    </div>
  `;

  // Renderizar Gráfica
  const canvas = document.getElementById('chart-mobile-historial');
  if (!canvas) return;

  const labels = cleanHourLabels(g.labels || []);
  const v1 = g.via_1 || [];
  const v2 = g.via_2 || [];
  const v3 = g.via_3 || [];
  const total = g.prendas || [];
  const valle = g.tiempo_valle_min || g.tiempo_valle || [];

  const datasets = [
    {
      type: 'line',
      label: 'Total Prendas',
      data: total,
      borderColor: '#ffffff',
      backgroundColor: 'rgba(255, 255, 255, 0.08)',
      borderWidth: 2.8,
      pointRadius: 3.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    {
      type: 'line',
      label: 'Vía 1',
      data: v1,
      borderColor: '#38bdf8',
      borderWidth: 1.8,
      borderDash: [3, 3],
      pointRadius: 2.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    {
      type: 'line',
      label: 'Vía 2',
      data: v2,
      borderColor: '#818cf8',
      borderWidth: 1.8,
      borderDash: [3, 3],
      pointRadius: 2.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    {
      type: 'line',
      label: 'Vía 3',
      data: v3,
      borderColor: '#c084fc',
      borderWidth: 1.8,
      borderDash: [3, 3],
      pointRadius: 2.5,
      tension: 0.35,
      fill: false,
      yAxisID: 'yPrendas'
    },
    {
      type: 'bar',
      label: 'Tiempo Valle (min)',
      data: valle,
      backgroundColor: 'rgba(245, 158, 11, 0.75)',
      borderColor: '#fbbf24',
      borderWidth: 1,
      borderRadius: 4,
      barPercentage: 0.45,
      yAxisID: 'yValle'
    }
  ];

  const scales = {
    x: {
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#94a3b8', font: { size: 9, weight: 'bold' } }
    },
    yPrendas: {
      type: 'linear',
      position: 'left',
      title: { display: true, text: 'Prendas', color: '#818cf8', font: { size: 9, weight: 'bold' } },
      grid: { color: 'rgba(255, 255, 255, 0.06)' },
      ticks: { color: '#818cf8', font: { size: 9 } },
      beginAtZero: true
    },
    yValle: {
      type: 'linear',
      position: 'right',
      title: { display: true, text: 'Valle min', color: '#fbbf24', font: { size: 9, weight: 'bold' } },
      grid: { drawOnChartArea: false },
      ticks: { color: '#fbbf24', font: { size: 9 } },
      beginAtZero: true
    }
  };

  const ctx = canvas.getContext('2d');
  state.historial.chart = new Chart(ctx, {
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#cbd5e1', font: { size: 10, weight: 'bold' }, boxWidth: 12, padding: 8 }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          titleColor: '#818cf8',
          bodyColor: '#f8fafc',
          borderColor: 'rgba(129, 140, 248, 0.3)',
          borderWidth: 1,
          padding: 8
        }
      },
      scales
    }
  });
}
