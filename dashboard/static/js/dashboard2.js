/* ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
   DASHBOARD JAVASCRIPT ULTRA AVANÇADO v5.1 (UNIFICADO)
   Sistema completo de interação para o dashboard do Trading Bot
   - SocketIO para dados em tempo real (conta, posições, stats)
   - APIs REST para dados estáticos (sinais, notícias, estratégias)
   - Animação de triângulos no canvas
   ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */

class TradingDashboard {
    constructor() {
        this.currentSection = 'overview';
        this.charts = {};
        this.aiModels = {};
        this.socket = null;
        this.config = {
            chartColors: {
                primary: '#ffd700',
                success: '#00ff88',
                danger: '#ff4757',
                background: 'rgba(255, 215, 0, 0.1)'
            }
        };
        this.init();
    }

    init() {
        console.log('🚀 Inicializando Dashboard Ultra Avançado v5.1...');
        this.setupEventListeners();
        this.setupNavigation();
        this.initSocketIO();
        this.loadInitialData();
        this.initTriangleAnimation();
        console.log('✅ Dashboard inicializado com sucesso!');
    }

    // ═══════════════════════════════════════════════════════════════════
    // EVENT LISTENERS E NAVEGAÇÃO
    // ═══════════════════════════════════════════════════════════════════

    setupEventListeners() {
        // Navegação da sidebar
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const section = item.dataset.section;
                this.navigateToSection(section);
            });
        });

        // Toggle da Sidebar
        document.getElementById('menuToggle').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('collapsed');
            document.getElementById('mainContent').classList.toggle('expanded');
        });

        // Botões de Ação
        document.getElementById('refresh-positions')?.addEventListener('click', () => this.loadPositions(true));
        document.getElementById('refresh-signals')?.addEventListener('click', () => this.loadSignals(true));
        document.getElementById('refresh-news')?.addEventListener('click', () => this.loadNews(true));
        document.getElementById('send-ai-message')?.addEventListener('click', () => this.sendAIChatMessage());
        
        // Botões de controle do sistema (simulação)
        document.getElementById('mt4-reconnect-btn')?.addEventListener('click', () => this.systemControlAction('mt4_reconnect'));
        document.getElementById('bot-toggle-btn')?.addEventListener('click', (e) => this.systemControlAction('bot_toggle', e.target.dataset.state));
        document.getElementById('news-reconnect-btn')?.addEventListener('click', () => this.systemControlAction('news_reconnect'));
        
        // Input de Risco
        document.getElementById('risk-per-trade')?.addEventListener('input', (e) => {
            document.getElementById('risk-per-trade-value').textContent = `${e.target.value}%`;
        });
    }
    
    systemControlAction(action, state = null) {
        console.log(`Ação de controle do sistema: ${action} com estado ${state}`);
        fetch('/api/system/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, state })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Ação ${action} executada com sucesso.`);
            } else {
                alert(`Erro ao executar ação ${action}: ${data.error}`);
            }
        })
        .catch(error => console.error('Erro na ação de controle:', error));
    }

    setupNavigation() {
        this.navigateToSection(this.currentSection);
    }

    navigateToSection(section) {
        // Atualizar navegação ativa
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-section="${section}"]`)?.classList.add('active');

        // Mostrar seção correspondente
        document.querySelectorAll('.content-section').forEach(sec => {
            sec.classList.remove('active');
        });
        document.getElementById(`${section}-section`)?.classList.add('active');

        // Atualizar título
        const titles = {
            'overview': 'Overview',
            'account': 'Conta & Saldo',
            'positions': 'Posições Ativas',
            'signals': 'Sinais de Trading',
            'strategies': 'Controlo de Estratégias',
            'ai-analysis': 'IA & Análise',
            'news': 'Notícias & Eventos',
            'risk': 'Gestão de Risco',
            'system-control': 'Controlo do Sistema'
        };
        document.getElementById('pageTitle').textContent = titles[section] || section;

        this.currentSection = section;

        // Carregar dados específicos da seção (dados estáticos ou iniciais)
        this.loadSectionData(section);
    }

    loadSectionData(section) {
        switch(section) {
            case 'strategies':
                this.loadStrategies();
                break;
            case 'ai-analysis':
                this.loadAIModels();
                break;
            case 'news':
                this.loadNews();
                break;
            case 'positions':
                this.loadPositions();
                break;
            case 'signals':
                this.loadSignals();
                break;
            case 'system-control':
                this.loadSystemLogs();
                break;
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // SOCKET.IO (DADOS EM TEMPO REAL)
    // ═══════════════════════════════════════════════════════════════════

    initSocketIO() {
        this.socket = io();

        this.socket.on('connect', () => {
            console.log('Conectado ao servidor Socket.IO');
        });

        // Recebe dados de conta em tempo real
        this.socket.on('account_update', (data) => {
            this.updateAccountDisplay(data.data);
        });

        // Recebe posições em tempo real
        this.socket.on('positions_update', (data) => {
            this.updatePositionsDisplay(data.data);
        });

        // Recebe estatísticas em tempo real
        this.socket.on('stats_update', (data) => {
            this.updateStatsDisplay(data.data);
        });
        
        // Recebe status do sistema em tempo real
        this.socket.on('system_status_update', (data) => {
            this.updateSystemStatus(data.data);
        });
        
        // Recebe análises de IA periódicas
        this.socket.on('ai_analysis_update', (data) => {
            this.updateAIAnalysisDisplay(data.data);
        });
        
        // Recebe notícias periódicas
        this.socket.on('news_update', (data) => {
            this.updateNewsDisplay(data.data);
        });
        
        // Recebe atualização de estratégia (toggle)
        this.socket.on('strategy_update', (data) => {
            this.updateStrategyToggle(data.strategy, data.enabled);
        });
    }

    // ═══════════════════════════════════════════════════════════════════
    // CARREGAMENTO INICIAL (APIs REST)
    // ═══════════════════════════════════════════════════════════════════

    async loadInitialData() {
        try {
            // Carrega dados iniciais via REST (serão atualizados pelo SocketIO)
            await Promise.all([
                this.loadAccountInfo(),
                this.loadSystemStatus(),
                this.loadStrategies(),
                this.loadAIModels(),
                this.loadNews(),
                this.loadSignals()
            ]);
            this.initCharts();
        } catch (error) {
            console.error('Erro ao carregar dados iniciais:', error);
        }
    }
    
    async loadAccountInfo() {
        try {
            const response = await fetch('/api/account');
            const data = await response.json();
            if (data.success) {
                this.updateAccountDisplay(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar conta:', error);
        }
    }
    
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/system/status');
            const data = await response.json();
            if (data.success) {
                this.updateSystemStatus(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar status:', error);
        }
    }

    async loadStrategies() {
        try {
            const response = await fetch('/api/strategies');
            const data = await response.json();
            if (data.success) {
                this.renderStrategies(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar estratégias:', error);
        }
    }
    
    async loadAIModels() {
        try {
            const response = await fetch('/api/ai/models');
            const data = await response.json();
            if (data.success) {
                this.aiModels = data.data;
                this.renderAIModelSelect(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar modelos de IA:', error);
        }
    }
    
    async loadNews(force = false) {
        if (!force && document.getElementById('news-list').children.length > 1) return; // Evita recarregar se já tiver dados
        try {
            const response = await fetch('/api/news');
            const data = await response.json();
            if (data.success) {
                this.updateNewsDisplay(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar notícias:', error);
        }
    }
    
    async loadPositions(force = false) {
        if (!force && this.currentSection !== 'positions') return;
        try {
            const response = await fetch('/api/positions');
            const data = await response.json();
            if (data.success) {
                this.updatePositionsDisplay(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar posições:', error);
        }
    }
    
    async loadSignals(force = false) {
        if (!force && this.currentSection !== 'signals') return;
        try {
            const response = await fetch('/api/signals');
            const data = await response.json();
            if (data.success) {
                this.renderSignals(data.data);
            }
        } catch (error) {
            console.error('Erro ao carregar sinais:', error);
        }
    }
    
    async loadSystemLogs() {
        // Simulação de carregamento de logs
        const logElement = document.getElementById('system-logs');
        if (logElement) {
            logElement.textContent = `[${new Date().toLocaleTimeString()}] INFO: Servidor iniciado com sucesso.\n` +
                                     `[${new Date().toLocaleTimeString()}] INFO: Conexão SocketIO estabelecida.\n` +
                                     `[${new Date().toLocaleTimeString()}] WARNING: MT4 Desconectado. Tentando reconexão...\n` +
                                     `[${new Date().toLocaleTimeString()}] INFO: Carregamento inicial de dados concluído.`;
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // ATUALIZAÇÃO DE UI (SOCKET.IO HANDLERS)
    // ═══════════════════════════════════════════════════════════════════

    updateAccountDisplay(account) {
        const balance = account.balance || 0;
        const equity = account.equity || 0;
        const profit = account.profit || 0;
        const marginUsed = account.margin || 0;
        const freeMargin = account.free_margin || 0;
        const marginLevel = account.margin_level || 0;
        
        // Overview Card
        document.getElementById('totalEquity').textContent = `$${equity.toFixed(2)}`;
        document.getElementById('floatingProfit').textContent = `$${profit.toFixed(2)}`;
        
        const profitElement = document.getElementById('floatingProfit');
        const profitChangeElement = document.getElementById('profitChange');
        
        // Atualiza cor do profit flutuante
        profitElement.style.color = profit >= 0 ? 'var(--success-color)' : 'var(--danger-color)';
        
        // Atualiza o indicador de mudança (simulação simples)
        const changeClass = profit >= 0 ? 'positive' : (profit < 0 ? 'negative' : 'neutral');
        const changeIcon = profit >= 0 ? 'fa-arrow-up' : (profit < 0 ? 'fa-arrow-down' : 'fa-minus');
        profitChangeElement.className = `card-change ${changeClass}`;
        profitChangeElement.innerHTML = `<i class="fas ${changeIcon}"></i><span>${(profit / (balance || 1) * 100).toFixed(2)}%</span>`;
        
        // Account Section
        document.getElementById('account-balance').textContent = `$${balance.toFixed(2)}`;
        document.getElementById('account-equity-full').textContent = `$${equity.toFixed(2)}`;
        document.getElementById('margin-used').textContent = `$${marginUsed.toFixed(2)}`;
        document.getElementById('free-margin').textContent = `$${freeMargin.toFixed(2)}`;
        document.getElementById('margin-level').textContent = `${marginLevel.toFixed(2)}%`;
        document.getElementById('daily-profit-full').textContent = `$${profit.toFixed(2)}`;
        
        // Atualiza o gráfico de saldo (simulação)
        this.updateBalanceChart(equity);
    }
    
    updateStatsDisplay(stats) {
        const profitToday = stats.profit_today || 0;
        const totalTradesToday = stats.total_trades_today || 0;
        const winRate = stats.win_rate || 0;
        const winningTrades = stats.winning_trades || 0;
        const aiConsensus = stats.ai_consensus || { recommendation: 'HOLD', confidence: 0 };
        
        // Overview Card
        document.getElementById('winRateToday').textContent = `${winRate.toFixed(1)}%`;
        document.getElementById('tradesToday').innerHTML = `<i class="fas fa-exchange-alt"></i> <span>${totalTradesToday} trades</span>`;
        
        document.getElementById('aiConsensus').textContent = aiConsensus.recommendation.toUpperCase();
        document.getElementById('aiConfidence').innerHTML = `<i class="fas fa-lightbulb"></i> <span>${aiConsensus.confidence.toFixed(0)}% Confiança</span>`;
        
        // Account Section
        document.getElementById('stat-trades-today').textContent = totalTradesToday;
        document.getElementById('stat-winners-today').textContent = winningTrades;
        document.getElementById('stat-win-rate').textContent = `${winRate.toFixed(1)}%`;
        // Max profit é estático na simulação
    }
    
    updateSystemStatus(status) {
        // Header Status
        const mt4Status = document.getElementById('mt4Status');
        const botStatus = document.getElementById('botStatus');
        
        this.setIndicatorStatus(mt4Status, status.mt4_connected, 'MT4 Conectado', 'MT4 Desconectado');
        this.setIndicatorStatus(botStatus, status.bot_running, 'BOT ATIVO', 'BOT INATIVO');
        
        // System Control Section
        const mt4ControlStatus = document.getElementById('mt4-control-status');
        const botControlStatus = document.getElementById('bot-control-status');
        const newsControlStatus = document.getElementById('news-control-status');
        
        this.setIndicatorStatus(mt4ControlStatus, status.mt4_connected, 'Conectado', 'Desconectado');
        this.setIndicatorStatus(newsControlStatus, status.news_api_connected, 'Conectado', 'Desconectado');
        
        const botToggleBtn = document.getElementById('bot-toggle-btn');
        if (status.bot_running) {
            this.setIndicatorStatus(botControlStatus, true, 'Ativo', 'Inativo');
            botToggleBtn.innerHTML = '<i class="fas fa-pause"></i> Pausar Bot';
            botToggleBtn.className = 'btn btn-warning btn-sm';
            botToggleBtn.dataset.state = 'off';
        } else {
            this.setIndicatorStatus(botControlStatus, false, 'Ativo', 'Inativo');
            botToggleBtn.innerHTML = '<i class="fas fa-play"></i> Iniciar Bot';
            botToggleBtn.className = 'btn btn-success btn-sm';
            botToggleBtn.dataset.state = 'on';
        }
    }
    
    setIndicatorStatus(element, isOnline, onlineText, offlineText) {
        if (element) {
            element.className = `status-indicator ${isOnline ? 'online' : 'offline'}`;
            element.querySelector('span').textContent = isOnline ? onlineText : offlineText;
        }
    }

    updatePositionsDisplay(positions) {
        const overviewBody = document.getElementById('overview-positions-body');
        const fullBody = document.getElementById('positions-full-body');
        
        // Atualiza contagem de posições
        const activeCount = positions.length;
        document.getElementById('active-positions-count').textContent = activeCount;
        
        // Calcula profit flutuante total
        const totalProfit = positions.reduce((sum, pos) => sum + (pos.profit || 0), 0);
        document.getElementById('floatingProfit').textContent = `$${totalProfit.toFixed(2)}`;
        
        // Renderiza tabelas
        this.renderPositionsTable(overviewBody, positions.slice(0, 5), true); // Mini tabela
        if (this.currentSection === 'positions') {
            this.renderPositionsTable(fullBody, positions, false); // Tabela completa
        }
    }
    
    renderPositionsTable(tbody, positions, isOverview) {
        tbody.innerHTML = '';
        if (positions.length === 0) {
            tbody.innerHTML = `<tr><td colspan="${isOverview ? 8 : 10}" class="text-center text-muted">Nenhuma posição ativa.</td></tr>`;
            return;
        }
        
        positions.forEach(pos => {
            const profitClass = (pos.profit || 0) >= 0 ? 'positive-profit' : 'negative-profit';
            const row = `
                <tr>
                    <td>${pos.ticket || 'N/A'}</td>
                    <td>${pos.symbol || 'N/A'}</td>
                    <td><span class="badge ${pos.type === 'BUY' ? 'bg-success' : 'bg-danger'}">${pos.type || 'N/A'}</span></td>
                    <td>${(pos.volume || 0).toFixed(2)}</td>
                    <td>${(pos.open_price || 0).toFixed(5)}</td>
                    <td>${(pos.current_price || 0).toFixed(5)}</td>
                    ${isOverview ? '' : `<td>${(pos.sl || 0).toFixed(5)}</td><td>${(pos.tp || 0).toFixed(5)}</td>`}
                    <td class="${profitClass}">$${(pos.profit || 0).toFixed(2)}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="dashboard.closePosition(${pos.ticket})"><i class="fas fa-times"></i> Fechar</button></td>
                </tr>
            `;
            tbody.innerHTML += row;
        });
    }
    
    closePosition(ticket) {
        console.log(`Tentativa de fechar posição: ${ticket}`);
        fetch('/api/positions/close', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket: ticket })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Posição ${ticket} fechada com sucesso.`);
            } else {
                alert(`Erro ao fechar posição ${ticket}: ${data.error}`);
            }
        })
        .catch(error => console.error('Erro ao fechar posição:', error));
    }
    
    renderSignals(signals) {
        const tbody = document.getElementById('signals-tbody');
        tbody.innerHTML = '';
        
        if (signals.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">Nenhum sinal recente.</td></tr>`;
            return;
        }
        
        signals.forEach(signal => {
            const directionClass = signal.direction === 'BUY' ? 'bg-success' : 'bg-danger';
            const row = `
                <tr>
                    <td>${signal.time || 'N/A'}</td>
                    <td>${signal.symbol || 'N/A'}</td>
                    <td><span class="badge ${directionClass}">${signal.direction || 'N/A'}</span></td>
                    <td>${(signal.confidence || 0).toFixed(1)}%</td>
                    <td>${signal.source || 'N/A'}</td>
                    <td>${signal.strategy || 'N/A'}</td>
                    <td><span class="badge bg-info">${signal.status || 'PENDENTE'}</span></td>
                    <td><button class="btn btn-primary btn-sm" onclick="dashboard.executeSignal(${signal.id})"><i class="fas fa-play"></i> Executar</button></td>
                </tr>
            `;
            tbody.innerHTML += row;
        });
    }
    
    executeSignal(signalId) {
        console.log(`Tentativa de executar sinal: ${signalId}`);
        fetch('/api/signals/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signal_id: signalId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Sinal ${signalId} executado com sucesso.`);
            } else {
                alert(`Erro ao executar sinal ${signalId}: ${data.error}`);
            }
        })
        .catch(error => console.error('Erro ao executar sinal:', error));
    }

    updateAIAnalysisDisplay(analyses) {
        const consensusBox = document.getElementById('ai-consensus-display');
        
        if (consensusBox) {
            consensusBox.innerHTML = '';
            analyses.forEach(a => {
                const item = document.createElement('div');
                item.className = 'ai-consensus-item';
                item.innerHTML = `<strong>${a.ai_name} (${a.specialty}):</strong> ${a.response}`;
                consensusBox.appendChild(item);
            });
            if (analyses.length === 0) {
                consensusBox.innerHTML = '<p class="text-muted">Nenhuma análise de IA disponível.</p>';
            }
        }
    }
    
    updateNewsDisplay(news) {
        const newsList = document.getElementById('news-list');
        if (newsList) {
            newsList.innerHTML = '';
            news.forEach(n => {
                const item = document.createElement('div');
                item.className = 'news-item';
                item.innerHTML = `
                    <div class="news-item-header">
                        <div class="news-item-title">${n.title}</div>
                        <div class="news-item-time">${n.time} - ${n.source}</div>
                    </div>
                    <p class="text-secondary">${n.content}</p>
                `;
                newsList.appendChild(item);
            });
            if (news.length === 0) {
                newsList.innerHTML = '<p class="text-center text-muted">Nenhuma notícia recente.</p>';
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // RENDERIZAÇÃO DE SEÇÕES
    // ═══════════════════════════════════════════════════════════════════
    
    renderStrategies(strategies) {
        const list = document.getElementById('strategies-list');
        list.innerHTML = '';
        
        for (const [key, info] of Object.entries(strategies)) {
            const isEnabled = info.enabled;
            const statusClass = isEnabled ? 'online' : 'offline';
            const statusText = isEnabled ? 'Ativa' : 'Inativa';
            const buttonText = isEnabled ? 'Desativar' : 'Ativar';
            const buttonClass = isEnabled ? 'btn-danger' : 'btn-success';
            const buttonState = isEnabled ? 'off' : 'on';
            
            const card = document.createElement('div');
            card.className = 'card strategy-card';
            card.innerHTML = `
                <div class="card-title">${key.toUpperCase().replace(/_/g, ' ')}</div>
                <p class="text-muted">Performance: ${info.performance.toFixed(2)}% | Trades: ${info.trades}</p>
                <div class="strategy-status">
                    <span class="status-dot ${statusClass}"></span>
                    <span class="status-text">${statusText}</span>
                </div>
                <button class="btn ${buttonClass} btn-sm btn-toggle" data-strategy="${key}" data-enabled="${buttonState}">
                    <i class="fas fa-${isEnabled ? 'pause' : 'play'}"></i> ${buttonText}
                </button>
            `;
            list.appendChild(card);
        }
        
        // Adiciona event listeners para os botões de toggle
        list.querySelectorAll('.btn-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => this.toggleStrategy(e.target));
        });
    }
    
    toggleStrategy(button) {
        const strategy = button.dataset.strategy;
        const currentState = button.dataset.enabled === 'on';
        const newState = !currentState;
        
        fetch('/api/strategies/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy: strategy, enabled: newState })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(data.message);
                // A UI será atualizada pelo SocketIO (strategy_update)
            } else {
                alert(`Erro ao alternar estratégia: ${data.error}`);
            }
        })
        .catch(error => console.error('Erro ao alternar estratégia:', error));
    }
    
    updateStrategyToggle(strategy, enabled) {
        const btn = document.querySelector(`.btn-toggle[data-strategy="${strategy}"]`);
        if (btn) {
            const statusElement = btn.closest('.strategy-card').querySelector('.strategy-status');
            const statusDot = statusElement.querySelector('.status-dot');
            const statusText = statusElement.querySelector('.status-text');
            
            if (enabled) {
                statusDot.className = 'status-dot online';
                statusText.textContent = 'Ativa';
                btn.innerHTML = '<i class="fas fa-pause"></i> Desativar';
                btn.className = 'btn btn-danger btn-sm btn-toggle';
                btn.dataset.enabled = 'off';
            } else {
                statusDot.className = 'status-dot offline';
                statusText.textContent = 'Inativa';
                btn.innerHTML = '<i class="fas fa-play"></i> Ativar';
                btn.className = 'btn btn-success btn-sm btn-toggle';
                btn.dataset.enabled = 'on';
            }
        }
    }
    
    renderAIModelSelect(models) {
        const select = document.getElementById('ai-model-select');
        if (!select) return;
        
        // Limpa opções existentes (exceto 'all')
        Array.from(select.options).forEach((option, index) => {
            if (index > 0) option.remove();
        });
        
        for (const [key, info] of Object.entries(models)) {
            if (info.available) {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = `${info.name} (${info.specialty})`;
                select.appendChild(option);
            }
        }
    }
    
    sendAIChatMessage() {
        const select = document.getElementById('ai-model-select');
        const input = document.getElementById('ai-chat-message');
        const chatBox = document.getElementById('ai-chat-box');
        
        const model = select.value;
        const message = input.value.trim();
        
        if (!message) return;
        
        // Adiciona mensagem do usuário
        this.addChatMessage(chatBox, 'user', message);
        input.value = '';
        
        // Adiciona placeholder de resposta da IA
        const loadingMessage = this.addChatMessage(chatBox, 'ai', '<i class="fas fa-spinner fa-spin"></i> Aguardando resposta da IA...', 'loading');
        
        fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: model, message: message })
        })
        .then(response => response.json())
        .then(data => {
            chatBox.removeChild(loadingMessage);
            if (data.success) {
                if (data.type === 'multiple') {
                    data.data.forEach(res => {
                        this.addChatMessage(chatBox, 'ai', `<strong>${res.ai_name} (${res.specialty}):</strong> ${res.response}`);
                    });
                } else {
                    this.addChatMessage(chatBox, 'ai', `<strong>${data.data.ai_name} (${data.data.specialty}):</strong> ${data.data.response}`);
                }
            } else {
                this.addChatMessage(chatBox, 'ai', `<strong>Erro:</strong> ${data.error}`);
            }
        })
        .catch(error => {
            chatBox.removeChild(loadingMessage);
            this.addChatMessage(chatBox, 'ai', `<strong>Erro de comunicação:</strong> ${error.message}`);
            console.error('Erro no chat com IA:', error);
        });
    }
    
    addChatMessage(chatBox, sender, message) {
        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${sender}`;
        messageElement.innerHTML = `<div class="message-content">${message}</div>`;
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight; // Scroll para o final
        return messageElement;
    }

    // ═══════════════════════════════════════════════════════════════════
    // GRÁFICOS (CHART.JS)
    // ═══════════════════════════════════════════════════════════════════

    initCharts() {
        // Gráfico de Evolução do Saldo (Equity)
        const ctxBalance = document.getElementById('balanceChart').getContext('2d');
        this.charts.balanceChart = new Chart(ctxBalance, {
            type: 'line',
            data: {
                labels: ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
                datasets: [{
                    label: 'Equity',
                    data: [5000, 5050, 5020, 5100, 5150, 5200, 5250, 5300, 5280, 5350, 5400, 5450],
                    borderColor: this.config.chartColors.primary,
                    backgroundColor: 'rgba(255, 215, 0, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'white' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: 'white' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
        
        // Gráfico de Performance por Estratégia (Doughnut)
        const ctxStrategy = document.getElementById('strategyChart').getContext('2d');
        this.charts.strategyChart = new Chart(ctxStrategy, {
            type: 'doughnut',
            data: {
                labels: ['EMA Crossover', 'RSI Divergence', 'Supertrend', 'Adaptive ML'],
                datasets: [{
                    data: [30, 25, 20, 25],
                    backgroundColor: ['#8b5cf6', '#06b6d4', '#ffd700', '#00ff88'],
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: 'white'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Distribuição de Lucro por Estratégia',
                        color: 'white'
                    }
                }
            }
        });
    }
    
    updateBalanceChart(newEquity) {
        if (!this.charts.balanceChart) return;
        
        const chart = this.charts.balanceChart;
        const data = chart.data.datasets[0].data;
        
        // Simula a adição de um novo ponto (mantendo o tamanho do array)
        const now = new Date();
        const label = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        
        // Adiciona o novo ponto se o último ponto for diferente ou se for a primeira atualização
        if (data.length === 0 || data[data.length - 1] !== newEquity) {
            if (data.length >= 12) {
                data.shift();
                chart.data.labels.shift();
            }
            
            data.push(newEquity);
            chart.data.labels.push(label);
            
            chart.update();
        }
    }

    // ═══════════════════════════════════════════════════════════════════
    // ANIMAÇÃO DE TRIÂNGULOS (CANVAS)
    // ═══════════════════════════════════════════════════════════════════

    initTriangleAnimation() {
        const canvas = document.getElementById('triangle-canvas');
        const ctx = canvas.getContext('2d');
        let width, height;
        let mouseX = 0, mouseY = 0;
        const triangles = [];
        const numTriangles = 50;
        const color = 'rgba(255, 215, 0, 0.05)'; // Dourado sutil

        function resizeCanvas() {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }

        function handleMouseMove(event) {
            mouseX = event.clientX;
            mouseY = event.clientY;
        }

        class Triangle {
            constructor() {
                this.reset();
                this.x = Math.random() * width;
                this.y = Math.random() * height;
            }

            reset() {
                this.size = Math.random() * 10 + 5;
                this.speedX = Math.random() * 0.5 - 0.25;
                this.speedY = Math.random() * 0.5 - 0.25;
                this.rotation = Math.random() * 360;
                this.rotationSpeed = Math.random() * 0.5 - 0.25;
                this.x = Math.random() < 0.5 ? -this.size : width + this.size;
                this.y = Math.random() * height;
            }

            update() {
                this.x += this.speedX;
                this.y += this.speedY;
                this.rotation += this.rotationSpeed;

                // Seguir o mouse (atração sutil)
                const dx = mouseX - this.x;
                const dy = mouseY - this.y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 200) {
                    const force = (200 - distance) / 200 * 0.05; // Força de atração mais sutil
                    this.x += dx * force;
                    this.y += dy * force;
                }

                // Resetar se sair da tela
                if (this.x < -this.size || this.x > width + this.size || this.y < -this.size || this.y > height + this.size) {
                    this.reset();
                }
            }

            draw() {
                ctx.save();
                ctx.translate(this.x, this.y);
                ctx.rotate(this.rotation * Math.PI / 180);
                
                ctx.beginPath();
                ctx.moveTo(0, -this.size);
                ctx.lineTo(this.size * 0.866, this.size / 2);
                ctx.lineTo(-this.size * 0.866, this.size / 2);
                ctx.closePath();
                
                ctx.fillStyle = color;
                ctx.fill();
                
                ctx.restore();
            }
        }

        function initTriangles() {
            for (let i = 0; i < numTriangles; i++) {
                triangles.push(new Triangle());
            }
        }

        function animate() {
            requestAnimationFrame(animate);
            ctx.clearRect(0, 0, width, height);

            triangles.forEach(triangle => {
                triangle.update();
                triangle.draw();
            });
        }

        window.addEventListener('resize', resizeCanvas);
        window.addEventListener('mousemove', handleMouseMove);
        resizeCanvas();
        initTriangles();
        animate();
    }
}

// Inicializa o dashboard quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new TradingDashboard();
});
