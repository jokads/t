/**
 * JokaMazKiBu Trading Bot Dashboard v8.0 HARDCORE
 * Ultra Professional JavaScript - Windows Optimized
 * Author: Manus AI | Date: 2026-01-01
 */

// =====================================================================
// CONFIGURATION
// =====================================================================
const CONFIG = {
    SYNC_INTERVAL: 2000,
    CHART_UPDATE_INTERVAL: 5000,
    MAX_LOGS: 100,
    MAX_NEWS: 50,
    NOTIFICATION_TIMEOUT: 5000
};

// =====================================================================
// STATE
// =====================================================================
let state = {
    botConnected: false,
    currentSection: 'overview',
    botState: {},
    activeTrades: {},
    strategies: {},
    aiModels: {},
    systemLogs: [],
    marketNews: [],
    charts: {}
};

// =====================================================================
// SOCKET.IO CONNECTION
// =====================================================================
const socket = io({
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: Infinity,
    transports: ['websocket', 'polling']
});

socket.on('connect', () => {
    console.log('✓ Conectado ao dashboard server');
    state.botConnected = true;
    updateBotStatus();
    showNotification('Conectado ao servidor!', 'success');
});

socket.on('disconnect', () => {
    console.log('✗ Desconectado do servidor');
    state.botConnected = false;
    updateBotStatus();
    showNotification('Desconectado do servidor!', 'error');
});

socket.on('connection_response', (data) => {
    console.log('Dashboard conectado:', data);
});

socket.on('bot_status', (data) => {
    state.botState = data;
    updateBotStatus();
});

socket.on('bot_update', (data) => {
    state.botState = data.bot_state || state.botState;
    state.activeTrades = data.active_trades || state.activeTrades;
    state.strategies = data.strategy_stats || state.strategies;
    
    updateAllUI();
});

socket.on('trades_update', (data) => {
    state.activeTrades = data;
    updateTradesTable();
});

socket.on('strategies_update', (data) => {
    state.strategies = data;
    updateStrategies();
});

socket.on('ai_models_update', (data) => {
    state.aiModels = data;
    updateAIModels();
});

socket.on('system_log', (data) => {
    state.systemLogs.unshift(data);
    if (state.systemLogs.length > CONFIG.MAX_LOGS) {
        state.systemLogs.pop();
    }
    updateLogs();
});

socket.on('trade_executed', (data) => {
    if (data.status === 'success') {
        showNotification(`✓ Trade executado com sucesso! ID: ${data.trade_id}`, 'success');
    } else {
        showNotification(`✗ Erro ao executar trade: ${data.error}`, 'error');
    }
    updateTradesTable();
});

socket.on('trade_failed', (data) => {
    showNotification(`✗ Erro: ${data.error}`, 'error');
});

socket.on('strategy_toggled', (data) => {
    if (data.status === 'success') {
        showNotification(`Estratégia ${data.strategy} ${data.enabled ? 'ativada' : 'desativada'}`, 'success');
    }
});

socket.on('risk_config_updated', (data) => {
    if (data.status === 'success') {
        showNotification('Configuração de risco atualizada!', 'success');
    }
});

socket.on('ai_analysis', (data) => {
    if (data.status === 'success') {
        displayAIAnalysis(data);
    }
});

socket.on('ai_analysis_failed', (data) => {
    showNotification(`✗ Erro na análise: ${data.error}`, 'error');
});

// =====================================================================
// DOM ELEMENTS
// =====================================================================
const elements = {
    sections: document.querySelectorAll('.section'),
    navItems: document.querySelectorAll('.nav-item'),
    balance: document.getElementById('balance'),
    equity: document.getElementById('equity'),
    profit: document.getElementById('profit'),
    winRate: document.getElementById('win-rate'),
    tradesCount: document.getElementById('trades-badge'),
    botStatusDot: document.getElementById('bot-status-dot'),
    botStatusText: document.getElementById('bot-status-text'),
    timeDisplay: document.getElementById('time-display'),
    tradesTableBody: document.getElementById('trades-tbody'),
    strategiesContainer: document.getElementById('strategies-container'),
    aiModelsContainer: document.getElementById('ai-models-container'),
    newsContainer: document.getElementById('news-container'),
    logsContainer: document.getElementById('logs-container'),
    historyTableBody: document.getElementById('history-tbody'),
    sectionTitle: document.getElementById('section-title'),
    sectionSubtitle: document.getElementById('section-subtitle'),
    notificationsContainer: document.getElementById('notifications-container'),
    symbolInput: document.getElementById('symbol-input'),
    aiModelSelect: document.getElementById('ai-model-select'),
    btnAnalyze: document.getElementById('btn-analyze'),
    analysisResult: document.getElementById('analysis-result'),
    riskPerTrade: document.getElementById('risk-per-trade'),
    maxDailyLoss: document.getElementById('max-daily-loss'),
    maxConcurrentTrades: document.getElementById('max-concurrent-trades'),
    btnUpdateRisk: document.getElementById('btn-update-risk'),
    btnClearLogs: document.getElementById('btn-clear-logs'),
    btnExecuteTrade: document.getElementById('btn-execute-trade'),
    tradeSymbol: document.getElementById('trade-symbol'),
    tradeDirection: document.getElementById('trade-direction'),
    tradeVolume: document.getElementById('trade-volume'),
    tradeSL: document.getElementById('trade-sl'),
    tradeTP: document.getElementById('trade-tp')
};

// =====================================================================
// INITIALIZATION
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard v8.0 HARDCORE iniciando...');
    
    initializeEventListeners();
    initializeCharts();
    updateClock();
    requestBotData();
    
    setInterval(updateClock, 1000);
    setInterval(requestBotData, CONFIG.SYNC_INTERVAL);
    setInterval(updateCharts, CONFIG.CHART_UPDATE_INTERVAL);
    
    console.log('✓ Dashboard inicializado com sucesso');
});

// =====================================================================
// EVENT LISTENERS
// =====================================================================
function initializeEventListeners() {
    // Navigation
    elements.navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.dataset.section;
            switchSection(section);
        });
    });
    
    // Modals
    document.querySelectorAll('[data-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.modal;
            openModal(modalId);
        });
    });
    
    document.querySelectorAll('[data-close]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.close;
            closeModal(modalId);
        });
    });
    
    // Trade Execution
    elements.btnExecuteTrade?.addEventListener('click', executeTrade);
    
    // AI Analysis
    elements.btnAnalyze?.addEventListener('click', analyzeSymbol);
    
    // Risk Configuration
    elements.btnUpdateRisk?.addEventListener('click', updateRiskConfig);
    
    // Clear Logs
    elements.btnClearLogs?.addEventListener('click', clearLogs);
    
    // Close modals on background click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
}

// =====================================================================
// SECTION SWITCHING
// =====================================================================
function switchSection(sectionName) {
    // Update nav items
    elements.navItems.forEach(item => {
        item.classList.remove('active');
        if (item.dataset.section === sectionName) {
            item.classList.add('active');
        }
    });
    
    // Update sections
    elements.sections.forEach(section => {
        section.classList.remove('active');
    });
    
    const activeSection = document.getElementById(sectionName);
    if (activeSection) {
        activeSection.classList.add('active');
        state.currentSection = sectionName;
        
        // Update header
        const titles = {
            overview: { title: 'Dashboard Overview', subtitle: 'Visão geral do seu bot de trading' },
            trades: { title: 'Trades Ativos', subtitle: 'Gerenciar posições abertas' },
            performance: { title: 'Performance', subtitle: 'Análise de desempenho' },
            strategies: { title: 'Estratégias', subtitle: 'Gerenciar estratégias ativas' },
            ai: { title: 'IA & Análise', subtitle: 'Análise com inteligência artificial' },
            risk: { title: 'Risco & Configurações', subtitle: 'Gerenciar parâmetros de risco' },
            news: { title: 'Notícias do Mercado', subtitle: 'Últimas notícias e análises' },
            history: { title: 'Histórico de Trades', subtitle: 'Trades fechados' },
            logs: { title: 'Logs do Sistema', subtitle: 'Eventos do sistema' },
            settings: { title: 'Configurações', subtitle: 'Preferências gerais' }
        };
        
        if (titles[sectionName]) {
            elements.sectionTitle.textContent = titles[sectionName].title;
            elements.sectionSubtitle.textContent = titles[sectionName].subtitle;
        }
    }
}

// =====================================================================
// REQUEST DATA FROM SERVER
// =====================================================================
function requestBotData() {
    if (!state.botConnected) return;
    
    socket.emit('request_bot_status');
    socket.emit('request_trades');
    socket.emit('request_strategies');
    socket.emit('request_ai_models');
}

// =====================================================================
// UPDATE UI
// =====================================================================
function updateBotStatus() {
    const connected = state.botConnected;
    
    if (elements.botStatusDot) {
        elements.botStatusDot.classList.toggle('online', connected);
    }
    
    if (elements.botStatusText) {
        elements.botStatusText.textContent = connected ? 'Online' : 'Offline';
    }
}

function updateAllUI() {
    updateBotStats();
    updateTradesTable();
    updateStrategies();
    updateAIModels();
}

function updateBotStats() {
    const bot = state.botState;
    
    if (elements.balance) {
        elements.balance.textContent = formatCurrency(bot.balance || 0);
    }
    
    if (elements.equity) {
        elements.equity.textContent = formatCurrency(bot.equity || 0);
    }
    
    if (elements.profit) {
        const profit = bot.profit_loss || 0;
        elements.profit.textContent = formatCurrency(profit);
        elements.profit.className = 'stat-value ' + (profit >= 0 ? 'positive' : 'negative');
    }
    
    if (elements.winRate) {
        elements.winRate.textContent = (bot.win_rate || 0).toFixed(1) + '%';
    }
    
    if (elements.tradesCount) {
        elements.tradesCount.textContent = bot.open_trades || 0;
    }
}

function updateTradesTable() {
    if (!elements.tradesTableBody) return;
    
    const trades = state.activeTrades;
    
    if (Object.keys(trades).length === 0) {
        elements.tradesTableBody.innerHTML = '<tr><td colspan="10" class="text-center">Nenhum trade ativo</td></tr>';
        return;
    }
    
    let html = '';
    for (const [id, trade] of Object.entries(trades)) {
        const profitClass = trade.profit >= 0 ? 'positive' : 'negative';
        html += `
            <tr>
                <td>${id.substring(0, 8)}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td><span class="badge-${trade.direction.toLowerCase()}">${trade.direction}</span></td>
                <td>${trade.volume.toFixed(2)}</td>
                <td>${trade.entry_price.toFixed(5)}</td>
                <td>${trade.sl.toFixed(5)}</td>
                <td>${trade.tp.toFixed(5)}</td>
                <td class="${profitClass}">${formatCurrency(trade.profit)}</td>
                <td>${trade.strategy}</td>
                <td>
                    <button class="btn-close-trade" data-trade-id="${id}">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            </tr>
        `;
    }
    
    elements.tradesTableBody.innerHTML = html;
    
    // Add close trade listeners
    document.querySelectorAll('.btn-close-trade').forEach(btn => {
        btn.addEventListener('click', () => {
            const tradeId = btn.dataset.tradeId;
            closeTrade(tradeId);
        });
    });
}

function updateStrategies() {
    if (!elements.strategiesContainer) return;
    
    const strategies = state.strategies;
    
    let html = '';
    for (const [name, stats] of Object.entries(strategies)) {
        const statusClass = stats.enabled ? 'active' : 'inactive';
        html += `
            <div class="strategy-card ${statusClass}">
                <div class="strategy-header">
                    <h4>${name}</h4>
                    <label class="toggle-switch">
                        <input type="checkbox" ${stats.enabled ? 'checked' : ''} 
                               data-strategy="${name}" class="strategy-toggle">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="strategy-stats">
                    <p>Trades: <strong>${stats.trades}</strong></p>
                    <p>Taxa: <strong>${(stats.win_rate || 0).toFixed(1)}%</strong></p>
                    <p>Lucro: <strong class="${stats.profit >= 0 ? 'positive' : 'negative'}">
                        ${formatCurrency(stats.profit)}
                    </strong></p>
                </div>
            </div>
        `;
    }
    
    elements.strategiesContainer.innerHTML = html;
    
    // Add toggle listeners
    document.querySelectorAll('.strategy-toggle').forEach(toggle => {
        toggle.addEventListener('change', () => {
            const strategy = toggle.dataset.strategy;
            socket.emit('enable_strategy', {
                strategy: strategy,
                enabled: toggle.checked
            });
        });
    });
}

function updateAIModels() {
    if (!elements.aiModelsContainer) return;
    
    const models = state.aiModels;
    
    let html = '';
    for (const [name, model] of Object.entries(models)) {
        html += `
            <div class="ai-card">
                <div class="ai-header">
                    <h4>${name.toUpperCase()}</h4>
                    <span class="status-badge ${model.status}">${model.status}</span>
                </div>
                <div class="ai-stats">
                    <p>Acurácia: <strong>${(model.accuracy * 100).toFixed(0)}%</strong></p>
                    <p>Último uso: <strong>${model.last_used ? 'Agora' : 'Nunca'}</strong></p>
                </div>
                <button class="btn-select-ai" data-model="${name}">
                    <i class="fas fa-check"></i> Selecionar
                </button>
            </div>
        `;
    }
    
    elements.aiModelsContainer.innerHTML = html;
    
    // Add select listeners
    document.querySelectorAll('.btn-select-ai').forEach(btn => {
        btn.addEventListener('click', () => {
            const model = btn.dataset.model;
            socket.emit('select_ai_model', { model: model });
            elements.aiModelSelect.value = model;
        });
    });
}

function updateLogs() {
    if (!elements.logsContainer) return;
    
    const logs = state.systemLogs.slice(0, CONFIG.MAX_LOGS);
    
    if (logs.length === 0) {
        elements.logsContainer.innerHTML = '<p class="text-center">Nenhum log disponível</p>';
        return;
    }
    
    let html = '';
    logs.forEach(log => {
        const levelClass = log.level.toLowerCase();
        const icon = {
            'info': 'info-circle',
            'warning': 'exclamation-triangle',
            'error': 'times-circle',
            'success': 'check-circle'
        }[levelClass] || 'circle';
        
        html += `
            <div class="log-item ${levelClass}">
                <i class="fas fa-${icon}"></i>
                <span class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
                <span class="log-message">${log.message}</span>
            </div>
        `;
    });
    
    elements.logsContainer.innerHTML = html;
}

// =====================================================================
// ACTIONS
// =====================================================================
function executeTrade() {
    const symbol = elements.tradeSymbol.value.toUpperCase();
    const direction = elements.tradeDirection.value;
    const volume = parseFloat(elements.tradeVolume.value);
    const sl = parseFloat(elements.tradeSL.value);
    const tp = parseFloat(elements.tradeTP.value);
    
    if (!symbol || volume <= 0) {
        showNotification('Preencha todos os campos corretamente!', 'error');
        return;
    }
    
    socket.emit('execute_trade', {
        symbol: symbol,
        direction: direction,
        volume: volume,
        sl: sl,
        tp: tp
    });
    
    closeModal('trade-modal');
}

function analyzeSymbol() {
    const symbol = elements.symbolInput.value.toUpperCase();
    const aiModel = elements.aiModelSelect.value;
    
    if (!symbol) {
        showNotification('Digite um símbolo!', 'error');
        return;
    }
    
    socket.emit('get_ai_analysis', {
        symbol: symbol,
        ai_model: aiModel
    });
}

function displayAIAnalysis(data) {
    if (!elements.analysisResult) return;
    
    elements.analysisResult.innerHTML = `
        <div class="analysis-box">
            <h4>${data.symbol} - ${data.ai_model.toUpperCase()}</h4>
            <p><strong>Sinal:</strong> <span class="signal-${data.signal.toLowerCase()}">${data.signal}</span></p>
            <p><strong>Confiança:</strong> ${(data.confidence * 100).toFixed(0)}%</p>
            <p><strong>Análise:</strong> ${data.analysis}</p>
            <p><small>Timestamp: ${new Date(data.timestamp).toLocaleString()}</small></p>
        </div>
    `;
    elements.analysisResult.style.display = 'block';
}

function updateRiskConfig() {
    const riskPerTrade = parseFloat(elements.riskPerTrade.value);
    const maxDailyLoss = parseFloat(elements.maxDailyLoss.value);
    const maxConcurrentTrades = parseInt(elements.maxConcurrentTrades.value);
    
    socket.emit('update_risk_config', {
        risk_per_trade: riskPerTrade,
        max_daily_loss: maxDailyLoss,
        max_concurrent_trades: maxConcurrentTrades
    });
}

function closeTrade(tradeId) {
    if (confirm(`Tem certeza que deseja fechar o trade ${tradeId}?`)) {
        socket.emit('close_trade', { trade_id: tradeId });
    }
}

function clearLogs() {
    if (confirm('Tem certeza que deseja limpar todos os logs?')) {
        state.systemLogs = [];
        updateLogs();
        showNotification('Logs limpos!', 'success');
    }
}

// =====================================================================
// CHARTS
// =====================================================================
let chartInstances = {};

function initializeCharts() {
    // Equity Chart
    const equityCtx = document.getElementById('equityChart');
    if (equityCtx) {
        chartInstances.equity = new Chart(equityCtx, {
            type: 'line',
            data: {
                labels: generateTimeLabels(24),
                datasets: [{
                    label: 'Equity',
                    data: generateRandomData(24, 49000, 51000),
                    borderColor: '#FFD700',
                    backgroundColor: 'rgba(255, 215, 0, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: {
                            color: 'rgba(255, 215, 0, 0.05)'
                        },
                        ticks: {
                            color: '#b0b0b0'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#b0b0b0'
                        }
                    }
                }
            }
        });
    }
    
    // Trades Distribution Chart
    const tradesCtx = document.getElementById('tradesChart');
    if (tradesCtx) {
        chartInstances.trades = new Chart(tradesCtx, {
            type: 'doughnut',
            data: {
                labels: ['BUY', 'SELL'],
                datasets: [{
                    data: [65, 35],
                    backgroundColor: ['#00ff88', '#ff4757'],
                    borderColor: '#1a1a1a',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: {
                            color: '#b0b0b0'
                        }
                    }
                }
            }
        });
    }
}

function updateCharts() {
    // Update data
    if (chartInstances.equity) {
        chartInstances.equity.data.datasets[0].data = generateRandomData(24, 49000, 51000);
        chartInstances.equity.update('none');
    }
}

// =====================================================================
// UTILITIES
// =====================================================================
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}

function updateClock() {
    if (!elements.timeDisplay) return;
    
    const now = new Date();
    const time = now.toLocaleTimeString('pt-BR');
    elements.timeDisplay.textContent = time;
}

function generateTimeLabels(count) {
    const labels = [];
    for (let i = count - 1; i >= 0; i--) {
        const date = new Date();
        date.setHours(date.getHours() - i);
        labels.push(date.getHours() + ':00');
    }
    return labels;
}

function generateRandomData(count, min, max) {
    const data = [];
    let value = (min + max) / 2;
    for (let i = 0; i < count; i++) {
        value += (Math.random() - 0.5) * 100;
        value = Math.max(min, Math.min(max, value));
        data.push(value);
    }
    return data;
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'times-circle' : 'info-circle'}"></i>
        ${message}
    `;
    
    elements.notificationsContainer.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, CONFIG.NOTIFICATION_TIMEOUT);
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// =====================================================================
// INITIALIZATION COMPLETE
// =====================================================================
console.log('✓ Dashboard v8.0 HARDCORE carregado com sucesso!');
