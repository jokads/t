/* ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
   DASHBOARD JAVASCRIPT ULTRA AVANÇADO
   Sistema completo de interação para o dashboard do Trading Bot
   ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════ */


   
class TradingDashboard {
    constructor() {
        this.currentSection = 'dashboard';
        this.updateInterval = null;
        this.charts = {};
        this.isLoading = false;
        
        // Configurações
        this.config = {
            updateFrequency: 5000, // 5 segundos
            chartColors: {
                primary: '#ffd700',
                success: '#00ff88',
                danger: '#ff4444',
                info: '#00aaff',
                background: 'rgba(255, 215, 0, 0.1)'
            }
        };
        
        this.init();

        // Socket.IO connection
        const socket = io();

        socket.on(\'connect\', () => {
            console.log(\'Conectado ao servidor Socket.IO\');
        });

        socket.on(\'account_update\', (data) => {
            this.updateAccountOverview(data);
        });

        socket.on(\'open_trades_update\', (data) => {
            this.updateOpenTrades(data);
        });

        socket.on(\'closed_trades_update\', (data) => {
            this.updateClosedTrades(data);
        });
    }
    
    init() {
    console.log('🚀 Inicializando Dashboard Ultra Avançado...');

    this.loadTradingSymbols()
        .then(() => {
            this.setupEventListeners();
            this.setupNavigation();
            this.loadInitialData();
            this.startAutoUpdate();
            console.log('✅ Dashboard inicializado com sucesso!');
        })
        .catch((err) => {
            console.error('❌ Erro ao iniciar dashboard:', err);
            this.showError('Erro ao carregar os símbolos de trading. Verifique o backend ou a conexão.');
        });
}

    setupEventListeners() {
        // Navegação da sidebar
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const section = item.dataset.section;
                this.navigateToSection(section);
            });
        });
        
        // Botões de atualização
        document.getElementById('refresh-positions')?.addEventListener('click', () => {
            this.loadPositions();
        });
        
        document.getElementById('refresh-signals')?.addEventListener('click', () => {
            this.loadSignals();
        });
        
        // Seletores de símbolo
        document.getElementById('analysis-symbol')?.addEventListener('change', (e) => {
            this.loadAIAnalysis(e.target.value);
        });
        
        document.getElementById('indicators-symbol')?.addEventListener('change', (e) => {
            this.loadIndicators(e.target.value);
        });
        
        // Controles de gráfico
        document.querySelectorAll('.chart-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.updateChartPeriod(e.target.dataset.period);
            });
        });
        
        // Filtros de notícias
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.filterNews(e.target.dataset.filter);
            });
        });
        
        // Configurações
        document.getElementById('trading-enabled')?.addEventListener('change', (e) => {
            this.updateTradingSetting('enabled', e.target.checked);
        });
        
        document.getElementById('ai-enabled')?.addEventListener('change', (e) => {
            this.updateAISetting('enabled', e.target.checked);
        });
    }
    
    setupNavigation() {
        // Configurar navegação inicial
         this.navigateToSection('dashboard');
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
        
        // Atualizar título e breadcrumb
            const titles = {
                'dashboard': 'Dashboard',
                'positions': 'Posições',
                'signals': 'Sinais',
                'ai-analysis': 'Análise IA',
                'indicators': 'Indicadores',
                'news': 'Notícias',
                'logs': 'Logs de Erros',
                'strategies': 'Estratégias',
                'settings': 'Configurações'
            };
        
        document.getElementById('page-title').textContent = titles[section] || section;
        document.getElementById('breadcrumb-current').textContent = titles[section] || section;
        
        this.currentSection = section;
        
        // Carregar dados específicos da seção
        this.loadSectionData(section);
    }
    
    loadSectionData(section) {
        switch(section) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'positions':
                this.loadPositions();
                break;
            case 'signals':
                this.loadSignals();
                break;
            case 'ai-analysis':
                this.loadAIAnalysis();
                break;
            case 'indicators':
                this.loadIndicators();
                break;
            case 'news':
                this.loadNews();
                break;
            case 'logs':
                this.loadErrorLogs();
                break;
            case 'strategies':
                this.loadStrategies();
                break;
            case 'settings':
                this.loadSettings();
                break;
        }
    }
    
    async loadInitialData() {
        this.showLoading();
        
        try {
            // Carregar dados básicos
            await Promise.all([
                this.loadAccountInfo(),
                this.loadSystemStatus(),
                this.loadOverviewData()
            ]);
            
        } catch (error) {
            console.error('Erro ao carregar dados iniciais:', error);
            this.showError('Erro ao carregar dados iniciais');
        } finally {
            this.hideLoading();
        }
    }
    
    async loadAccountInfo() {
        try {
            const response = await fetch('/api/account');
            const data = await response.json();
            
            if (response.ok) {
                this.updateAccountDisplay(data);
            } else {
                throw new Error(data.error || 'Erro ao carregar conta');
            }
        } catch (error) {
            console.error('Erro ao carregar conta:', error);
        }
    }
    
    updateAccountDisplay(account) {
        // Atualizar cards de conta
        document.getElementById('account-balance').textContent = `$${account.balance?.toFixed(2) || '0.00'}`;
        document.getElementById('account-equity').textContent = `$${account.equity?.toFixed(2) || '0.00'}`;
        document.getElementById('margin-used').textContent = `$${account.margin_used?.toFixed(2) || '0.00'}`;
        
        // Calcular mudança do saldo (simulado)
        const change = account.profit || 0;
        const changePercent = account.balance ? (change / account.balance * 100) : 0;
        const changeElement = document.getElementById('balance-change');
        
        if (changeElement) {
            changeElement.textContent = `${change >= 0 ? '+' : ''}$${change.toFixed(2)} (${changePercent.toFixed(2)}%)`;
            changeElement.className = `balance-change ${change >= 0 ? 'positive' : 'negative'}`;
        }
    }
    
    async loadSystemStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (response.ok) {
                this.updateSystemStatus(data);
            }
        } catch (error) {
            console.error('Erro ao carregar status:', error);
        }
    }
    
    updateSystemStatus(status) {
        // Atualizar indicadores de status
        const botStatus = document.getElementById("bot-status");
        const mt4Status = document.getElementById("mt4-status");
        
        if (botStatus) {
            botStatus.className = `status-indicator ${status.bot_running ? 'online' : 'offline'}`;
            botStatus.querySelector("span").textContent = status.bot_running ? 'Bot Ativo' : 'Bot Inativo';
        }
        
        if (mt4Status) {
            mt4Status.className = `status-indicator ${status.mt4_connected ? 'online' : 'offline'}`;
            mt4Status.querySelector("span").textContent = status.mt4_connected ? 'MT4 Conectado' : 'MT4 Desconectado';
        }
    }

    updateTelegramStatus(status) {
        const telegramStatus = document.getElementById("telegramStatus");
        if (telegramStatus) {
            telegramStatus.className = `status-indicator ${status.connected ? 'online' : 'offline'}`;
            telegramStatus.querySelector("span").textContent = status.connected ? 'Telegram' : 'Telegram Offline';
        }
    }

    updateNewsAPIStatus(status) {
        const newsApiStatus = document.getElementById("newsApiStatus");
        if (newsApiStatus) {
            newsApiStatus.className = `status-indicator ${status.connected ? 'online' : 'offline'}`;
            newsApiStatus.querySelector("span").textContent = status.connected ? 'NewsAPI' : 'NewsAPI Offline';
        }
    }
    
    async loadDashboardData() {
        try {
            const [statsResponse, aiVotesResponse, telegramStatusResponse, newsApiStatusResponse] = await Promise.all([
                fetch("/api/statistics"),
                this.loadAIVotes(),
                fetch("/api/telegram/status"),
                fetch("/api/newsapi/status")
            ]);

            if (telegramStatusResponse.ok) {
                const telegramStatus = await telegramStatusResponse.json();
                this.updateTelegramStatus(telegramStatus.data);
            }

            if (newsApiStatusResponse.ok) {
                const newsApiStatus = await newsApiStatusResponse.json();
                this.updateNewsAPIStatus(newsApiStatus.data);
            }
            
            if (statsResponse.ok) {
                const stats = await statsResponse.json();
                this.updateStatistics(stats);
            }
            
            // Carregar gráfico de performance
            this.loadPerformanceChart();
            
        } catch (error) {
            console.error('Erro ao carregar visão geral:', error);
        }
    }
    
    updateStatistics(stats) {
        // Atualizar estatísticas
        document.getElementById('daily-profit').textContent = `$${stats.profit_today?.toFixed(2) || '0.00'}`;
        document.getElementById('daily-trades').textContent = stats.total_trades_today || '0';
        document.getElementById('win-rate').textContent = `${stats.win_rate?.toFixed(1) || '0.0'}%`;
        document.getElementById('winning-trades').textContent = stats.winning_trades || '0';
        document.getElementById('total-trades').textContent = stats.total_trades_today || '0';
    }
    
    async loadAIVotes() {
        // Simular votação das IAs
        const aiModels = [
            { name: 'Mistral-7B', vote: 'BUY', confidence: 0.85 },
            { name: 'Orca-Mini', vote: 'BUY', confidence: 0.72 },
            { name: 'Llama-3.2-3B', vote: 'BUY', confidence: 0.90 },
            { name: 'Llama-3.2-1B', vote: 'BUY', confidence: 0.78 },
            { name: 'Phi-3-Mini', vote: 'HOLD', confidence: 0.65 },
            { name: 'Qwen2-1.5B', vote: 'BUY', confidence: 0.70 },
            { name: 'Nous-Hermes', vote: 'BUY', confidence: 0.82 }
        ];
        
        this.updateAIVotes(aiModels);
    }
    
    updateAIVotes(aiModels) {
        const container = document.getElementById('ai-votes-grid');
        if (!container) return;
        
        container.innerHTML = '';
        
        aiModels.forEach(ai => {
            const voteElement = document.createElement('div');
            voteElement.className = `ai-vote-item vote-${ai.vote.toLowerCase()}`;
            
            voteElement.innerHTML = `
                <div class="ai-name">${ai.name}</div>
                <div class="ai-recommendation text-${ai.vote === 'BUY' ? 'success' : ai.vote === 'SELL' ? 'danger' : 'warning'}">${ai.vote}</div>
                <div class="ai-confidence">${(ai.confidence * 100).toFixed(0)}%</div>
            `;
            
            container.appendChild(voteElement);
        });
    }
    
    loadPerformanceChart() {
        const ctx = document.getElementById('performance-chart');
        if (!ctx) return;
        
        // Dados simulados de performance
        const data = {
            labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'],
            datasets: [{
                label: 'Lucro Acumulado',
                data: [0, 5.2, 12.8, 18.5, 25.3, 31.7, 45.75],
                borderColor: this.config.chartColors.primary,
                backgroundColor: this.config.chartColors.background,
                fill: true,
                tension: 0.4
            }]
        };
        
        if (this.charts.performance) {
            this.charts.performance.destroy();
        }
        
        this.charts.performance = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: 'rgba(255, 215, 0, 0.1)'
                        },
                        ticks: {
                            color: '#cccccc'
                        }
                    },
                    y: {
                        grid: {
                            color: 'rgba(255, 215, 0, 0.1)'
                        },
                        ticks: {
                            color: '#cccccc',
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    }
    
    async loadPositions() {
        this.showLoading();
        try {
            const response = await fetch('/api/positions');
            const positions = await response.json();
        
            if (response.ok) {
                this.updatePositionsTable(positions);
            } else {
                throw new Error(positions.error || 'Erro ao carregar posições');
            }
        } catch (error) {
            console.error('Erro ao carregar posições:', error);
            this.showError('Erro ao carregar posições');
        } finally {
            this.hideLoading();
        } 
    }

    updatePositionsTable(positions) {
        const tbody = document.getElementById('positions-tbody');
        if (!tbody) return;

        tbody.innerHTML = '';
 
        if (positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #888;">Nenhuma posição aberta</td></tr>';
            return;
        }

        positions.forEach(position => {
            const row = document.createElement('tr');
 
            const profitClass = position.profit >= 0 ? 'text-success' : 'text-danger';
            const directionClass = position.direction === 'BUY' ? 'text-success' : 'text-danger';

            row.innerHTML = `
                <td>${position.ticket}</td>
                <td><strong>${position.symbol}</strong></td>
                <td><span class="${directionClass}">${position.direction}</span></td>
                <td>${position.lot_size}</td>
                <td>${(position.entry_price ?? 0).toFixed(5)}</td>
                <td>${(position.current_price ?? 0).toFixed(5)}</td>
                <td><span class="${profitClass}">$${(position.profit ?? 0).toFixed(2)}</span></td>
                <td>${position.strategy || 'N/A'}</td>
                <td>${((position.ai_confidence ?? 0) * 100).toFixed(0)}%</td>
                <td>
                    <button class="btn btn-secondary btn-sm btn-close-position" data-ticket="${position.ticket}">
                        <i class="fas fa-times"></i>
                    </button>
                </td>
            `;

            tbody.appendChild(row);
        });

        // Remover event listeners antigos antes de adicionar novos para evitar duplicação
        const oldButtons = tbody.querySelectorAll('.btn-close-position');
        oldButtons.forEach(btn => btn.replaceWith(btn.cloneNode(true)));

        // Adiciona os event listeners após o tbody estar populado
        tbody.querySelectorAll('.btn-close-position').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ticket = e.currentTarget.dataset.ticket;
                if (window.dashboard && typeof window.dashboard.closePosition === 'function') {
                    window.dashboard.closePosition(ticket);
                }
            });
        });
    }
    
    async loadSignals() {
        try {
            const response = await fetch('/api/signals');
            const signals = await response.json();
            
            if (response.ok) {
                this.updateSignalsGrid(signals);
            } else {
                throw new Error(signals.error || 'Erro ao carregar sinais');
            }
        } catch (error) {
            console.error('Erro ao carregar sinais:', error);
            this.showError('Erro ao carregar sinais');
        }
    }
    
    updateSignalsGrid(signals) {
        const container = document.getElementById('signals-grid');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (signals.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #888; grid-column: 1/-1;">Nenhum sinal recente</div>';
            return;
        }
        
        signals.forEach(signal => {
            const signalCard = document.createElement('div');
            signalCard.className = 'signal-card';
            
            const directionClass = signal.direction === 'BUY' ? 'text-success' : 'text-danger';
            const confidenceColor = signal.confidence >= 0.8 ? 'success' : signal.confidence >= 0.6 ? 'warning' : 'danger';
            
            signalCard.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h3>${signal.symbol}</h3>
                    <span class="${directionClass}" style="font-weight: 600;">${signal.direction}</span>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Estratégia:</strong> ${signal.strategy || 'N/A'}
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Confiança:</strong> 
                    <span class="text-${confidenceColor}">${(signal.confidence * 100).toFixed(0)}%</span>
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Votação IA:</strong> ${signal.ai_votes || 'N/A'}
                </div>
                <div style="font-size: 0.85rem; color: #888;">
                    ${new Date(signal.timestamp).toLocaleString('pt-BR')}
                </div>
            `;
            
            container.appendChild(signalCard);
        });
    }
    
    // 🔁 Carrega a análise IA para um símbolo
async loadAIAnalysis(symbol = 'USDJPY') {
    try {
        const response = await fetch(`/api/ai-analysis/${symbol}`);
        const analysis = await response.json();

        if (response.ok) {
            this.updateAIAnalysisGrid(analysis);
        } else {
            throw new Error(analysis.error || 'Erro ao carregar análise');
        }
    } catch (error) {
        console.error(`Erro ao carregar análise IA para ${symbol}:`, error);
        this.showError(`Erro ao carregar análise IA para ${symbol}`);
    }
}

// 🆕 Carrega todos os símbolos disponíveis do backend (via Flask)
async loadTradingSymbols() {
    try {
        const response = await fetch('/api/trading-symbols');
        const data = await response.json();

        if (response.ok && data.success) {
            const select = document.getElementById('analysis-symbol');
            if (!select) return;

            select.innerHTML = ''; // limpa opções anteriores

            data.symbols.forEach(symbol => {
                const option = document.createElement('option');
                option.value = symbol;
                option.textContent = symbol;
                select.appendChild(option);
            });

            // ⚡️ Defina USDJPY como padrão se estiver na lista, senão use o primeiro
            const defaultSymbol = data.symbols.includes("USDJPY") ? "USDJPY" : data.symbols[0];
            select.value = defaultSymbol;

            // ⚡️ Carrega a análise IA para o símbolo padrão
            this.loadAIAnalysis(defaultSymbol);

        } else {
            throw new Error(data.error || 'Erro ao carregar símbolos');
        }
    } catch (error) {
        console.error('Erro ao carregar símbolos de trading:', error);
        this.showError('Erro ao carregar símbolos de trading');
    }
}

    
    updateAIAnalysisGrid(analysis) {
        const container = document.getElementById('ai-analysis-grid');
        if (!container) return;
        
        container.innerHTML = '';
        
        const aiNames = {
            'technical_analysis': 'Análise Técnica',
            'sentiment_analysis': 'Análise de Sentimento',
            'risk_management': 'Gestão de Risco',
            'momentum': 'Momentum',
            'volatility': 'Volatilidade',
            'correlations': 'Correlações',
            'coordination': 'Coordenação'
        };
        
        Object.entries(analysis).forEach(([key, data]) => {
            const analysisCard = document.createElement('div');
            analysisCard.className = 'analysis-card';
            
            const recommendationClass = data.recommendation === 'BUY' ? 'text-success' : 
                                      data.recommendation === 'SELL' ? 'text-danger' : 'text-warning';
            
            analysisCard.innerHTML = `
                <h3>${aiNames[key] || key}</h3>
                <div style="margin: 15px 0;">
                    <strong>Recomendação:</strong> 
                    <span class="${recommendationClass}">${data.recommendation}</span>
                </div>
                <div style="margin: 10px 0;">
                    <strong>Confiança:</strong> 
                    <span class="text-info">${(data.confidence * 100).toFixed(0)}%</span>
                </div>
                <div style="margin: 10px 0; font-size: 0.9rem; color: #ccc;">
                    ${data.reasoning || 'Sem detalhes disponíveis'}
                </div>
            `;
            
            container.appendChild(analysisCard);
        });
    }
    
    async loadIndicators(symbol = 'EURUSD') {
        try {
            const response = await fetch(`/api/indicators/${symbol}`);
            const indicators = await response.json();
            
            if (response.ok) {
                this.updateIndicatorsGrid(indicators);
            } else {
                throw new Error(indicators.error || 'Erro ao carregar indicadores');
            }
        } catch (error) {
            console.error('Erro ao carregar indicadores:', error);
            this.showError('Erro ao carregar indicadores');
        }
    }
    
    updateIndicatorsGrid(indicators) {
        const container = document.getElementById('indicators-grid');
        if (!container) return;
        
        container.innerHTML = '';
        
        const indicatorNames = {
            'rsi': 'RSI',
            'macd': 'MACD',
            'momentum': 'Momentum',
            'fvg': 'Fair Value Gaps',
            'trend_strength': 'Força da Tendência',
            'buy_side_liquidity': 'Liquidez Buy-Side',
            'sell_side_liquidity': 'Liquidez Sell-Side',
            'smt': 'Smart Money Technique',
            'ict_bias': 'ICT Bias',
            'order_blocks': 'Order Blocks'
        };
        
        Object.entries(indicators).forEach(([key, data]) => {
            const indicatorCard = document.createElement('div');
            indicatorCard.className = 'indicator-card';
            
            let content = `<h3>${indicatorNames[key] || key}</h3>`;
            
            if (typeof data === 'object') {
                Object.entries(data).forEach(([subKey, value]) => {
                    if (typeof value === 'number') {
                        content += `<div><strong>${subKey}:</strong> ${value.toFixed(4)}</div>`;
                    } else {
                        content += `<div><strong>${subKey}:</strong> ${value}</div>`;
                    }
                });
            } else {
                content += `<div>${data}</div>`;
            }
            
            indicatorCard.innerHTML = content;
            container.appendChild(indicatorCard);
        });
    }
    
    async loadNews() {
        try {
            const response = await fetch('/api/news');
            const news = await response.json();
            
            if (response.ok) {
                this.updateNewsList(news);
            } else {
                throw new Error(news.error || 'Erro ao carregar notícias');
            }
        } catch (error) {
            console.error('Erro ao carregar notícias:', error);
            this.showError('Erro ao carregar notícias');
        }
    }
    
    updateNewsList(news) {
        const container = document.getElementById('news-list');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (news.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #888;">Nenhuma notícia disponível</div>';
            return;
        }
        
        news.forEach(article => {
            const newsItem = document.createElement('div');
            newsItem.className = 'news-item';
            
            const sentimentClass = article.sentiment === 'POSITIVE' ? 'text-success' : 
                                 article.sentiment === 'NEGATIVE' ? 'text-danger' : 'text-warning';
            
            const impactClass = article.impact === 'HIGH' ? 'text-danger' : 
                              article.impact === 'MEDIUM' ? 'text-warning' : 'text-info';
            
            newsItem.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                    <h3 style="margin: 0; flex: 1;">${article.title}</h3>
                    <div style="display: flex; gap: 10px; margin-left: 15px;">
                        <span class="${sentimentClass}" style="font-size: 0.8rem;">${article.sentiment}</span>
                        <span class="${impactClass}" style="font-size: 0.8rem;">${article.impact}</span>
                    </div>
                </div>
                <p style="margin: 10px 0; color: #ccc;">${article.summary}</p>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #888;">
                    <span>${article.source}</span>
                    <span>${new Date(article.timestamp).toLocaleString('pt-BR')}</span>
                </div>
            `;
            
            container.appendChild(newsItem);
        });
    }
    
    loadSettings() {
        // Configurações já estão no HTML, apenas atualizar se necessário
        console.log('Configurações carregadas');
    }
    
    updateChartPeriod(period) {
        // Atualizar botões ativos
        document.querySelectorAll('.chart-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        document.querySelector(`[data-period="${period}"]`)?.classList.add('active');
        
        // Recarregar gráfico com novo período
        this.loadPerformanceChart();
    }
    
    filterNews(filter) {
        // Atualizar botões ativos
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        document.querySelector(`[data-filter="${filter}"]`)?.classList.add('active');
        
        // Recarregar notícias com filtro
        this.loadNews();
    }

    async loadErrorLogs() {
        this.showLoading();
        try {
            const response = await fetch('/api/logs/errors');
            const data = await response.json();

            if (response.ok && data.success) {
                this.updateErrorLogs(data.data);
            } else {
                throw new Error(data.error || 'Erro ao carregar logs de erros');
            }
        } catch (error) {
            console.error('Erro ao carregar logs de erros:', error);
            this.showError('Erro ao carregar logs de erros');
        } finally {
            this.hideLoading();
        }
    }

    updateErrorLogs(logs) {
        const container = document.getElementById(\'errorLogs\');
        if (!container) return;

        if (logs.length === 0) {
            container.textContent = \'Nenhum erro registado.\';
            return;
        }

        container.textContent = logs.join(\'\\n\');
    }

    async loadStrategies() {
        this.showLoading();
        try {
            const response = await fetch(\'/api/strategies\');
            const data = await response.json();

            if (response.ok && data.success) {
                this.updateStrategiesList(data.data);
            } else {
                throw new Error(data.error || \'Erro ao carregar estratégias\');
            }
        } catch (error) {
            console.error(\'Erro ao carregar estratégias:\', error);
            this.showError(\'Erro ao carregar estratégias\');
        } finally {
            this.hideLoading();
        }
    }

    updateStrategiesList(strategies) {
        const container = document.getElementById(\'strategies-list\');
        if (!container) return;

        container.innerHTML = \'\';

        if (strategies.length === 0) {
            container.innerHTML = \'<div style="text-align: center; color: #888;">Nenhuma estratégia encontrada.</div>\';
            return;
        }

        strategies.forEach(strategy => {
            const strategyCard = document.createElement(\'div\');
            strategyCard.className = \'strategy-card\';
            strategyCard.innerHTML = `
                <h3>${strategy}</h3>
                <div class="strategy-actions">
                    <button class="btn btn-success"><i class="fas fa-play"></i> Iniciar</button>
                    <button class="btn btn-danger"><i class="fas fa-stop"></i> Parar</button>
                    <button class="btn btn-info"><i class="fas fa-edit"></i> Configurar</button>
                </div>
            `;
            container.appendChild(strategyCard);
        });
    }
    
    updateTradingSetting(setting, value) {
        console.log(`Trading ${setting} alterado para:`, value);
        // Aqui seria enviado para o backend
    }
    
    updateAISetting(setting, value) {
        console.log(`IA ${setting} alterado para:`, value);
        // Aqui seria enviado para o backend
    }
    
    closePosition(ticket) {
        if (confirm(`Deseja realmente fechar a posição ${ticket}?`)) {
            console.log(`Fechando posição ${ticket}`);
            // Aqui seria enviado comando para fechar posição
            this.loadPositions(); // Recarregar posições
        }
    }
    
    startAutoUpdate() {
        this.updateInterval = setInterval(async () => {
            if (!this.isLoading) {
                try {
                    await this.updateCurrentSection();
                } catch (error) {
                    console.error('❌ Erro durante atualização automática:', error);
                    this.showError(`Erro ao atualizar seção: ${error.message}`);
                    this.hideLoading(); // Garante que o `isLoading` volte ao normal
                }
            }
        }, this.config.updateFrequency);

        console.log('✅ Atualizações automáticas iniciadas'); 
    }

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
    
    async updateCurrentSection() {
        try {
            switch (this.currentSection) {
                case 'overview':
                    await this.loadAccountInfo();
                    await this.loadSystemStatus();
                    break;
                case 'positions':
                    await this.loadPositions();
                    break;
                case 'signals':
                    await this.loadSignals();
                    break;
                default:
                    console.warn(`⚠️ Seção desconhecida: ${this.currentSection}`);
            }
        } catch (error) {
            console.error(`❌ Erro ao atualizar a seção "${this.currentSection}":`, error);
            this.showError(`Erro ao atualizar dados da seção "${this.currentSection}"`);
            this.hideLoading(); // Garantia de desbloqueio da interface
        } 
    }
    
    showLoading() {
        this.isLoading = true;
        document.getElementById('loading-overlay')?.classList.add('show');
    }
    
    hideLoading() {
        this.isLoading = false;
        document.getElementById('loading-overlay')?.classList.remove('show');
    }
    
    showError(message) {
        console.error('Dashboard Error:', message);
        // Aqui poderia mostrar um toast ou modal de erro
        alert(`Erro: ${message}`);
    }
}

// Inicializar dashboard quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    try {
        console.log('🟡 Inicializando TradingDashboard...');
        window.dashboard = new TradingDashboard();
    } catch (error) {
        console.error('❌ Erro crítico ao inicializar o dashboard:', error);
        alert('Erro ao iniciar o dashboard. Verifique os logs no console.');
    }
});

// Encerrar processos ao sair da página
window.addEventListener('beforeunload', () => {
    try {
        if (window.dashboard && typeof window.dashboard.stopAutoUpdate === 'function') {
            window.dashboard.stopAutoUpdate();
            console.log('🔁 Atualizações automáticas interrompidas com sucesso.');
        }
    } catch (error) {
        console.warn('⚠️ Erro ao tentar interromper atualizações:', error);
    }
});





    updateAccountOverview(data) {
        document.getElementById("account-balance").textContent = `$${data.balance.toFixed(2)}`;
        document.getElementById("account-equity").textContent = `$${data.equity.toFixed(2)}`;
        document.getElementById("account-profit").textContent = `$${data.profit.toFixed(2)}`;
    }

    updateOpenTrades(trades) {
        const tableBody = document.getElementById("open-trades-table-body");
        tableBody.innerHTML = "";

        if (trades.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888;">Nenhum trade aberto</td></tr>';
            return;
        }

        trades.forEach(trade => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${trade.ticket}</td>
                <td>${trade.symbol}</td>
                <td>${trade.type}</td>
                <td>${trade.volume}</td>
                <td>${trade.open_price}</td>
                <td>${trade.sl}</td>
                <td>${trade.tp}</td>
                <td>${trade.profit.toFixed(2)}</td>
            `;
            tableBody.appendChild(row);
        });
    }

    updateClosedTrades(trades) {
        const tableBody = document.getElementById("closed-trades-table-body");
        tableBody.innerHTML = "";

        if (trades.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888;">Nenhum histórico de trades</td></tr>';
            return;
        }

        trades.forEach(trade => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${trade.ticket}</td>
                <td>${trade.symbol}</td>
                <td>${trade.type}</td>
                <td>${trade.volume}</td>
                <td>${trade.open_price}</td>
                <td>${trade.close_price}</td>
                <td>${trade.profit.toFixed(2)}</td>
                <td>${trade.status}</td>
            `;
            tableBody.appendChild(row);
        });
    }

