/**
 * JokaMazKiBu Trading Bot Dashboard - Core JavaScript v7.1
 * Versão mais robusta: guards, fetch timeout, polling control, backoff, visibilidade da aba.
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- Configurações / Seletores ---
  const SELECTORS = {
    mainContent: 'mainContent',
    sidebar: 'sidebar',
    menuToggle: 'menuToggle',
    pageTitle: 'pageTitle',
    indicatorsContainer: 'indicatorsContainer',
    activeTradesTableBody: 'activeTradesTableBody',
    activeTradesCountBadge: 'activeTradesCountBadge',
    strategiesTableBody: 'strategiesTableBody',
    aiModelsStatus: 'aiModelsStatus',
    aiModelSelect: 'aiModelSelect',
    aiConsensusContainer: 'aiConsensusContainer',
    aiConsensusDetailContainer: 'aiConsensusDetailContainer',
    latestNewsContainer: 'latestNewsContainer',
    fullNewsContainer: 'fullNewsContainer',
    aiChatInput: 'aiChatInput',
    aiChatSendBtn: 'aiChatSendBtn',
    aiChatWindow: 'aiChatWindow',
    botStatus: 'botStatus',
    mt4Status: 'mt4Status',
  };

  const POLLING_INTERVAL = 5000;
  const DEFAULT_TIMEOUT = 8000;
  const BACKOFF_BASE = 2; // exponencial
  const MAX_BACKOFF = 5; // 2^5 = 32x
  let strategiesData = {};
  let aiModels = {};
  let balanceChartInstance = null;
  let strategyChartInstance = null;

  // store interval IDs & failure counts
  const pollHandles = new Map();
  const failCounts = new Map();

  // --- Utilitários ---
  const el = (id) => document.getElementById(id);
  const formatCurrency = (v) => {
    try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v); }
    catch(e){ return (v===undefined? '—' : v); }
  };
  const getProfitClass = (v) => (v > 0 ? 'positive' : v < 0 ? 'negative' : 'neutral');

  const createToast = (msg, type = 'info') => {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4500);
  };

  const ensureContainerMessage = (containerId, message, level = 'warning') => {
    const c = el(containerId);
    if (!c) return;
    c.innerHTML = `<div class="placeholder placeholder-${level}">${message}</div>`;
  };

  // Fetch with timeout and safe JSON parse
  const fetchWithTimeout = async (url, opts = {}, timeout = DEFAULT_TIMEOUT) => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(url, { ...opts, signal: controller.signal });
      clearTimeout(id);
      const text = await res.text();
      let json = null;
      try { json = text ? JSON.parse(text) : null; } catch (e) { /* not json */ }
      return { ok: res.ok, status: res.status, text, json };
    } catch (err) {
      clearTimeout(id);
      return { ok: false, status: 0, error: err };
    }
  };

  // global endpoint error handler + backoff
  const handleEndpointFailure = (endpoint, errOrStatus) => {
    const c = (failCounts.get(endpoint) || 0) + 1;
    failCounts.set(endpoint, c);
    const backoff = Math.min(MAX_BACKOFF, Math.floor(Math.log2(c + 1)));
    console.warn(`Endpoint ${endpoint} failure #${c} -> backoff ${2 ** backoff}x`);
    // show message in main area if critical endpoints
    if (endpoint.includes('/api/indicators')) {
      ensureContainerMessage(SELECTORS.indicatorsContainer, `Erro ao carregar indicadores (${errOrStatus}). Verifique backend.`, 'error');
    }
  };

  // generic fetch-and-render with guards
  const fetchAndRender = async (endpoint, renderFn, opts = {}) => {
    try {
      const r = await fetchWithTimeout(endpoint, opts);
      if (!r.ok) {
        handleEndpointFailure(endpoint, r.status || r.error);
        console.error(`fetchAndRender error ${endpoint}`, r);
        // Provide fallback visual if renderFn expects container
        if (endpoint.includes('/api/indicators')) {
          ensureContainerMessage(SELECTORS.indicatorsContainer, `API não encontrada (${r.status}). Clique para tentar novamente.`, 'error');
        }
        return null;
      }
      // server returned ok; reset failure count
      failCounts.set(endpoint, 0);
      // if JSON structure uses {success: true, data: ...} handle both cases
      const payload = r.json ?? r.text ? r.json : null;
      // If parsed json contains .success pattern:
      if (payload && typeof payload === 'object' && 'success' in payload) {
        if (payload.success) {
          renderFn(payload.data);
          return payload.data;
        } else {
          console.warn(`${endpoint} returned success:false`, payload);
          return null;
        }
      } else if (payload) {
        renderFn(payload);
        return payload;
      } else {
        // if server returned text (non json), try to render directly (some APIs may return arrays)
        try {
          const parsedAgain = JSON.parse(r.text);
          renderFn(parsedAgain);
          return parsedAgain;
        } catch (e) {
          console.warn('fetchAndRender: response not JSON', endpoint);
          return null;
        }
      }
    } catch (err) {
      console.error('fetchAndRender exception', endpoint, err);
      handleEndpointFailure(endpoint, err);
      return null;
    }
  };

  // stop existing polling for endpoint
  const clearPoll = (key) => {
    if (pollHandles.has(key)) {
      clearInterval(pollHandles.get(key));
      pollHandles.delete(key);
    }
  };

  // start polling for a function with optional dynamic interval/backoff
  const startPollTask = (name, fn, intervalMs) => {
    clearPoll(name);
    // immediate run
    fn();
    const handle = setInterval(() => {
      // if tab hidden, skip to save resources
      if (document.hidden) return;
      fn();
    }, intervalMs);
    pollHandles.set(name, handle);
  };

  // --- Render Helpers (safe) ---
  const renderTable = (tbodyId, data = [], rowFn = () => '', emptyMsg = 'Nenhum item.') => {
    const tbody = el(tbodyId);
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!Array.isArray(data) || data.length === 0) {
      tbody.insertAdjacentHTML('beforeend', `<tr><td colspan="10" class="text-center">${emptyMsg}</td></tr>`);
      return;
    }
    const frag = document.createDocumentFragment();
    data.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = rowFn(item);
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
  };

  // --- Conta e Estatísticas ---
  const renderAccountStats = (data) => {
    if (!data) return;
    const tb = el('totalBalance'); if (tb) tb.textContent = formatCurrency(data.balance);
    const te = el('totalEquity'); if (te) te.textContent = `Equity: ${formatCurrency(data.equity)}`;
    const profitEl = el('totalProfit');
    if (profitEl) {
      profitEl.textContent = formatCurrency(data.profit);
      if (profitEl.parentElement) {
        profitEl.parentElement.className = `card-change ${getProfitClass(data.profit)}`;
        const icon = profitEl.parentElement.querySelector('i');
        if (icon) icon.className = data.profit >= 0 ? 'fas fa-arrow-up' : 'fas fa-arrow-down';
      }
    }
    const fm = el('mt4FreeMargin'); if (fm) fm.textContent = formatCurrency(data.free_margin);
  };

  const renderStatistics = (data) => {
    if (!data) return;
    const p = el('profitTodayText'); if (p) p.textContent = `Profit Hoje: ${formatCurrency(data.profit_today)}`;
    const t = el('totalTradesToday'); if (t) t.textContent = `${data.total_trades_today} trades hoje`;
    const tt = el('totalTrades'); if (tt) tt.textContent = `Total: ${data.total_trades}`;
    const winEl = el('winRate');
    if (winEl) {
      winEl.textContent = `${(data.win_rate || 0).toFixed(1)}%`;
      if (winEl.parentElement) winEl.parentElement.className = `card-change ${getProfitClass((data.win_rate||0) - 50)}`;
    }
  };

  // --- Trades Ativos ---
  const renderActiveTrades = (positions) => {
    if (!Array.isArray(positions)) positions = [];
    renderTable(SELECTORS.activeTradesTableBody, positions, (pos) => {
      const typeClass = (pos.type === 'BUY') ? 'positive' : 'negative';
      const profitClass = getProfitClass(pos.profit || 0);
      return `
        <td>${pos.ticket ?? '—'}</td>
        <td>${pos.symbol ?? '—'}</td>
        <td class="${typeClass}">${pos.type ?? '—'}</td>
        <td>${(pos.volume ?? 0).toFixed ? pos.volume.toFixed(2) : pos.volume}</td>
        <td>${(pos.open_price ?? 0).toFixed ? (pos.open_price).toFixed(5) : pos.open_price}</td>
        <td>${(pos.current_price ?? 0).toFixed ? (pos.current_price).toFixed(5) : pos.current_price}</td>
        <td>${(pos.sl ?? '—')} / ${(pos.tp ?? '—')}</td>
        <td class="${profitClass}">${formatCurrency(pos.profit ?? 0)}</td>
        <td>${pos.strategy ?? '—'}</td>
        <td>${pos.open_time ? new Date(pos.open_time).toLocaleTimeString() : '—'}</td>
      `;
    }, 'Nenhuma posição ativa.');
    const badge = el(SELECTORS.activeTradesCountBadge);
    if (badge) badge.textContent = String((positions && positions.length) || 0);
  };

  // --- Estratégias ---
  const handleStrategyToggle = async (e) => {
    const btn = e.currentTarget;
    const strategy = btn.dataset.strategy;
    const newStatus = btn.dataset.enabled !== 'true';
    btn.disabled = true; const oldText = btn.textContent; btn.textContent = 'Aguarde...';
    try {
      const res = await fetchWithTimeout('/api/strategies/toggle', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ strategy, enabled: newStatus }) }, 9000);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = res.json ?? null;
      if (data && data.success) {
        btn.dataset.enabled = newStatus;
        btn.textContent = newStatus ? 'Desativar' : 'Ativar';
        btn.classList.toggle('btn-success', !newStatus);
        btn.classList.toggle('btn-danger', newStatus);
        const row = btn.closest('tr');
        if (row) {
          const statusCell = row.querySelector('td:nth-child(3)');
          if (statusCell) {
            statusCell.textContent = newStatus ? 'ATIVADA' : 'DESATIVADA';
            statusCell.classList.toggle('positive', newStatus);
            statusCell.classList.toggle('negative', !newStatus);
          }
        }
        if (strategiesData[strategy]) strategiesData[strategy].enabled = newStatus;
        updateStrategyChart();
        createToast(`Estratégia ${strategy} ${newStatus ? 'ativada' : 'desativada'}`, 'success');
      } else throw new Error((data && data.error) || 'Resposta inválida');
    } catch (err) {
      console.error(err);
      createToast(`Erro: ${err.message}`, 'error');
      btn.textContent = oldText;
    } finally {
      btn.disabled = false;
    }
  };

  const renderStrategies = (strategies) => {
    if (!strategies || typeof strategies !== 'object') {
      ensureContainerMessage('strategiesContainer', 'Nenhuma estratégia disponível', 'info');
      return;
    }
    strategiesData = strategies;
    const rows = Object.entries(strategies).map(([k, v]) => ({ key: k, data: v }));
    renderTable(SELECTORS.strategiesTableBody, rows, ({ key, data }) => {
      const statusClass = data.enabled ? 'positive' : 'negative';
      return `
        <td>${String(key).replace(/_/g, ' ').toUpperCase()}</td>
        <td>${data.symbol ?? '—'}</td>
        <td class="${statusClass}">${data.enabled ? 'ATIVADA' : 'DESATIVADA'}</td>
        <td class="${getProfitClass((data.performance || 0) - 60)}">${(data.performance || 0).toFixed(1)}%</td>
        <td>${data.trades ?? 0}</td>
        <td>${(data.win_rate || 0).toFixed(1)}%</td>
        <td class="${getProfitClass(10 - (data.max_drawdown || 0))}">${(data.max_drawdown || 0).toFixed(1)}%</td>
        <td>${(data.profit_factor || 0).toFixed(2)}</td>
        <td>
          <button class="btn btn-sm ${data.enabled ? 'btn-danger' : 'btn-success'} toggle-strategy" data-strategy="${key}" data-enabled="${data.enabled}">
            ${data.enabled ? 'Desativar' : 'Ativar'}
          </button>
        </td>
      `;
    }, 'Nenhuma estratégia configurada.');

    // bind toggles safely
    document.querySelectorAll('.toggle-strategy').forEach(btn => {
      btn.removeEventListener('click', handleStrategyToggle);
      btn.addEventListener('click', handleStrategyToggle);
    });
    updateStrategyChart();
  };

  // --- Indicadores ---
  const renderIndicators = (indicators) => {
    const container = el(SELECTORS.indicatorsContainer);
    if (!container) {
      console.warn('Indicadores: container não encontrado');
      return;
    }
    container.innerHTML = '';
    if (!indicators || Object.keys(indicators).length === 0) {
      container.innerHTML = '<div class="placeholder">Sem indicadores</div>';
      return;
    }
    const frag = document.createDocumentFragment();
    Object.entries(indicators).forEach(([symbol, data]) => {
      const card = document.createElement('div');
      card.className = 'card-mini indicator-group';
      let inner = `<div class="indicator-symbol">${symbol}</div><div class="indicator-list">`;
      Object.entries(data).forEach(([name, ind]) => {
        const sig = (ind.signal || '').toUpperCase();
        const signalClass = sig.includes('BUY') ? 'positive' : sig.includes('SELL') ? 'negative' : 'neutral';
        inner += `<div class="indicator-item">
          <div class="indicator-name">${name} (${ind.timeframe ?? '—'})</div>
          <div class="indicator-value ${signalClass}">${(ind.value !== undefined && ind.value.toFixed) ? ind.value.toFixed(5) : (ind.value ?? '—')}</div>
          <div class="indicator-signal ${signalClass}">${ind.signal ?? '—'}</div>
        </div>`;
      });
      inner += '</div>';
      card.innerHTML = inner;
      frag.appendChild(card);
    });
    container.appendChild(frag);
  };

  // --- IA e Notícias ---
  const renderAIModels = (models) => {
    aiModels = models || {};
    const container = el(SELECTORS.aiModelsStatus);
    const select = el(SELECTORS.aiModelSelect);
    if (container) container.innerHTML = '';
    if (select) {
      select.innerHTML = '<option value="all">Consenso de Todas as IAs</option>';
    }
    if (!models || Object.keys(models).length === 0) {
      if (container) container.innerHTML = '<div class="placeholder">Sem modelos AI</div>';
      return;
    }
    Object.entries(models).forEach(([key, model]) => {
      const statusClass = model.available ? 'online' : 'offline';
      if (container) {
        const div = document.createElement('div');
        div.className = 'ai-model-item';
        div.innerHTML = `<span class="ai-model-name">${model.name}</span>
          <span class="ai-model-specialty">(${model.specialty ?? '—'})</span>
          <span class="ai-model-status status-dot ${statusClass}" title="${statusClass}"></span>`;
        container.appendChild(div);
      }
      if (model.available && select) {
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = `${model.name} (${model.specialty ?? ''})`;
        select.appendChild(opt);
      }
    });
  };

  const renderAIConsensus = (analyses) => {
    const container = el(SELECTORS.aiConsensusContainer);
    const detailContainer = el(SELECTORS.aiConsensusDetailContainer);
    if (container) container.innerHTML = '';
    if (detailContainer) detailContainer.innerHTML = '';
    if (!Array.isArray(analyses) || analyses.length === 0) {
      if (container) container.innerHTML = '<div class="placeholder">Sem análises</div>';
      return;
    }
    analyses.forEach(a => {
      const actionClass = (a.action || '').includes('BUY') ? 'positive' : (a.action || '').includes('SELL') ? 'negative' : 'neutral';
      const confidenceClass = getProfitClass(((a.confidence || 0) - 0.7) * 100);
      if (container) {
        container.insertAdjacentHTML('beforeend', `<div class="ai-consensus-item card-mini">
          <div class="ai-name">${a.ai_name}</div>
          <div class="ai-summary ${actionClass}">${a.response}</div>
          <div class="ai-confidence ${confidenceClass}">Confiança: ${(a.confidence * 100 || 0).toFixed(1)}%</div>
        </div>`);
      }
      if (detailContainer) {
        detailContainer.insertAdjacentHTML('beforeend', `<div class="ai-detail-card card">
          <div class="ai-detail-header">
            <div class="ai-detail-name">${a.ai_name} <span class="ai-detail-specialty">(${a.specialty ?? '—'})</span></div>
            <div class="ai-detail-confidence ${confidenceClass}">Confiança: ${(a.confidence * 100 || 0).toFixed(1)}%</div>
          </div>
          <div class="ai-detail-summary">${a.response}</div>
          <div class="ai-detail-body"><strong>Detalhes:</strong> ${a.details ?? ''}</div>
          <div class="ai-detail-action"><strong>Ação Sugerida:</strong> <span class="action-tag ${actionClass}">${a.action ?? '—'}</span></div>
        </div>`);
      }
    });
  };

  const renderNews = (news) => {
    const overview = el(SELECTORS.latestNewsContainer);
    const full = el(SELECTORS.fullNewsContainer);
    if (overview) overview.innerHTML = '';
    if (full) full.innerHTML = '';
    if (!Array.isArray(news) || news.length === 0) {
      if (overview) overview.innerHTML = '<div class="placeholder">Sem notícias</div>';
      if (full) full.innerHTML = '<div class="placeholder">Sem notícias</div>';
      return;
    }
    news.forEach(n => {
      const impact = (n.impact || '').toLowerCase();
      const impactClass = impact.includes('high') ? 'impact-high' : impact.includes('medium') ? 'impact-medium' : 'impact-low';
      const html = `<div class="news-item">
        <div class="news-time ${impactClass}">${n.time ?? ''}</div>
        <div class="news-content">
          <div class="news-title">${n.title ?? ''}</div>
          <div class="news-source">Fonte: ${n.source ?? ''} | Impacto: <span class="${impactClass}">${n.impact ?? ''}</span></div>
          <div class="news-content-detail">${n.content ?? ''}</div>
        </div>
      </div>`;
      if (overview) overview.insertAdjacentHTML('beforeend', html);
      if (full) full.insertAdjacentHTML('beforeend', html);
    });
  };

  // --- Gráficos (inic/atualiza) ---
  const initCharts = () => {
    const balanceCtx = el('balanceChart');
    if (balanceCtx && window.Chart) {
      try {
        balanceChartInstance = new Chart(balanceCtx.getContext('2d'), {
          type: 'line', data: { labels: [], datasets: [{ label: 'Equity', data: [], borderColor: '#FFD700', fill: true }] },
          options: { responsive: true, maintainAspectRatio: false }
        });
      } catch (e) { console.warn('initCharts balance error', e); }
    }
  };

  const updateStrategyChart = () => {
    const ctx = el('strategyChart');
    if (!ctx || !window.Chart) return;
    try {
      if (!strategyChartInstance) {
        strategyChartInstance = new Chart(ctx.getContext('2d'), {
          type: 'doughnut',
          data: { labels: [], datasets: [{ data: [], backgroundColor: ['#FFD700', '#C0C0C0', '#CD7F32', '#4CAF50', '#FF9800', '#2196F3'] }] },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
        });
      }
      const labels = Object.keys(strategiesData || {}).map(k => k.replace(/_/g, ' ').toUpperCase());
      const ds = Object.values(strategiesData || {}).map(s => s.performance || 0);
      strategyChartInstance.data.labels = labels;
      strategyChartInstance.data.datasets[0].data = ds;
      strategyChartInstance.update();
    } catch (e) { console.warn('updateStrategyChart error', e); }
  };

  // --- Events / UI interactions ---
  // safer nav binding
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
      const secId = item.dataset.section;
      const target = el(`${secId}-section`);
      if (target) target.classList.add('active');
      const pt = el(SELECTORS.pageTitle);
      if (pt) pt.textContent = item.querySelector('span') ? item.querySelector('span').textContent : pt.textContent;
    });
  });

  // menu toggle
  const menuToggleEl = el(SELECTORS.menuToggle);
  const sidebarEl = el(SELECTORS.sidebar);
  const mainContentEl = el(SELECTORS.mainContent);
  menuToggleEl?.addEventListener('click', () => {
    if (sidebarEl) sidebarEl.classList.toggle('collapsed');
    if (mainContentEl) mainContentEl.classList.toggle('expanded');
  });

  // AI Chat
  const aiChatInput = el(SELECTORS.aiChatInput);
  const aiChatSendBtn = el(SELECTORS.aiChatSendBtn);
  const aiChatWindow = el(SELECTORS.aiChatWindow);
  const aiModelSelect = el(SELECTORS.aiModelSelect);

  const addMessageToChat = (sender, message, isBot = false, details = null) => {
    if (!aiChatWindow) return;
    const div = document.createElement('div');
    div.className = `ai-chat-message ${sender}`;
    div.innerHTML = `<p>${message}</p>${details ? `<div class="ai-chat-details"><strong>Detalhes:</strong>${details}</div>` : ''}`;
    aiChatWindow.appendChild(div);
    aiChatWindow.scrollTop = aiChatWindow.scrollHeight;
  };

  const handleAIChat = async () => {
    if (!aiChatInput || !aiModelSelect || !aiChatSendBtn) return;
    const message = aiChatInput.value.trim(); if (!message) return;
    const model = aiModelSelect.value;
    addMessageToChat('user', message); aiChatInput.value = ''; aiChatSendBtn.disabled = true;
    addMessageToChat('bot', 'Processando análise...', true);
    try {
      const res = await fetchWithTimeout('/api/ai/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, model }) }, 20000);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = res.json ?? null;
      // remove the processing message
      const lastChild = aiChatWindow && aiChatWindow.lastChild;
      if (lastChild && lastChild.textContent && lastChild.textContent.includes('Processando análise...')) lastChild.remove();
      if (result && result.success) {
        const responses = result.type === 'multiple' ? result.data : [result.data];
        responses.forEach(a => addMessageToChat('bot', `[${a.ai_name} - ${a.specialty}]: ${a.response}`, true, a.details));
      } else {
        addMessageToChat('bot', `Erro IA: ${(result && result.error) || 'Resposta inválida'}`, true);
      }
    } catch (err) {
      console.error(err);
      addMessageToChat('bot', `Erro de comunicação: ${err.message}`, true);
    } finally {
      aiChatSendBtn.disabled = false;
    }
  };

  aiChatSendBtn?.addEventListener('click', handleAIChat);
  aiChatInput?.addEventListener('keypress', e => { if (e.key === 'Enter') handleAIChat(); });

  // --- Polling orchestration ---
  const tasks = [
    { name: 'account', fn: () => fetchAndRender('/api/account', renderAccountStats), interval: POLLING_INTERVAL },
    { name: 'positions', fn: () => fetchAndRender('/api/positions', renderActiveTrades), interval: POLLING_INTERVAL },
    { name: 'statistics', fn: () => fetchAndRender('/api/statistics', renderStatistics), interval: POLLING_INTERVAL },
    { name: 'strategies', fn: () => fetchAndRender('/api/strategies', renderStrategies), interval: 15000 },
    { name: 'indicators', fn: () => fetchAndRender('/api/indicators', renderIndicators), interval: 15000 },
    { name: 'ai_models', fn: () => fetchAndRender('/api/ai/models', renderAIModels), interval: 30000 }
  ];

  const startPolling = () => {
    tasks.forEach(t => startPollTask(t.name, t.fn, t.interval));
  };

  const stopAllPolling = () => {
    pollHandles.forEach((v, k) => { clearInterval(v); });
    pollHandles.clear();
  };

  // Pause polling when tab hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopAllPolling();
    } else {
      startPolling();
    }
  });

  // --- SocketIO (safe) ---
  let socket = null;
  if (typeof io !== 'undefined') {
    try {
      socket = io(window.location.origin);
      socket.on('connect', () => { const bs = el(SELECTORS.botStatus); if (bs) bs.classList.add('online'); updateStatusSafe('botStatus', true, 'BOT ATIVO'); });
      socket.on('disconnect', () => { updateStatusSafe('botStatus', false, 'BOT OFFLINE'); });
      socket.on('system_heartbeat', (status) => {
        updateStatusSafe('mt4Status', status.mt4_connected, status.mt4_connected ? 'MT4 CONECTADO' : 'MT4 OFFLINE');
        const mt4Conn = el('mt4ConnectionStatus'); if (mt4Conn) mt4Conn.textContent = status.mt4_connected ? 'CONECTADO' : 'DESCONECTADO';
        const uptime = el('systemUptime'); if (uptime) uptime.textContent = status.uptime || '--';
      });
      socket.on('ai_news', payload => renderNews(payload?.data || []));
      socket.on('ai_analyses', payload => renderAIConsensus(payload?.data || []));
    } catch (e) {
      console.warn('SocketIO init failed', e);
    }
  } else {
    console.warn('SocketIO (io) não encontrado. Funções realtime desativadas.');
  }

  // safe status updater
  function updateStatusSafe(id, online, text) {
    const target = el(id);
    if (!target) return;
    target.classList.toggle('online', !!online);
    target.classList.toggle('offline', !online);
    const dot = target.querySelector('.status-dot');
    if (dot) dot.style.backgroundColor = online ? '#4CAF50' : '#F44336';
    const span = target.querySelector('span');
    if (span) span.textContent = text ?? span.textContent;
  }

  // --- Inicialização ---
  initCharts();
  startPolling();

  // expose small debug helper globally (opcional)
  window.jokaDashboard = {
    startPolling, stopAllPolling, fetchAndRender, failCounts
  };
});
