import os
import time
import json
import random
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

# ═══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO INICIAL
# ═══════════════════════════════════════════════════════════════════

# Define o diretório base do projeto (loja-ia2)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuração do Flask
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'dashboard', 'templates'),
            static_folder=os.path.join(BASE_DIR, 'dashboard', 'static'))
app.config['SECRET_KEY'] = 'super_secret_key_jokamazkibu_v5_1' # Mudar em produção
app.config['SESSION_COOKIE_SECURE'] = False # Mudar para True em HTTPS

# Configuração do SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ═══════════════════════════════════════════════════════════════════
# SIMULAÇÃO DE GERENCIAMENTO DE DADOS (DATA MANAGER)
# Em um projeto real, esta classe faria a ponte com:
# - mt4_communication.py (para dados de conta e posições)
# - news_api_manager.py (para notícias)
# - ai_manager.py (para análises de IA)
# ═══════════════════════════════════════════════════════════════════

class DataManager:
    def __init__(self):
        self.account_data = {
            'balance': 5000.00,
            'equity': 5000.00,
            'profit': 0.00,
            'margin': 0.00,
            'free_margin': 5000.00,
            'margin_level': 1000.00,
            'currency': 'USD'
        }
        self.positions = []
        self.strategies = self._load_strategies()
        self.ai_models = self._load_ai_models()
        self.system_status = {
            'mt4_connected': True,
            'bot_running': True,
            'news_api_connected': True
        }
        self.stats = {
            'profit_today': 0.00,
            'total_trades_today': 0,
            'winning_trades': 0,
            'win_rate': 0.0,
            'ai_consensus': {'recommendation': 'HOLD', 'confidence': 0}
        }
        self.news = self._load_initial_news()
        self.signals = self._load_initial_signals()
        self.equity_history = [{'time': datetime.now().strftime('%H:%M'), 'equity': 5000.00}]

    def _load_strategies(self):
        # Simulação de carregamento de estratégias do strategies/
        return {
            'ema_crossover': {'name': 'EMA Crossover', 'enabled': True, 'performance': 12.5, 'trades': 150},
            'rsi_divergence': {'name': 'RSI Divergence', 'enabled': False, 'performance': -2.1, 'trades': 50},
            'supertrend': {'name': 'Supertrend', 'enabled': True, 'performance': 8.9, 'trades': 90},
            'adaptive_ml': {'name': 'Adaptive ML', 'enabled': True, 'performance': 25.3, 'trades': 300},
            'ict_concepts': {'name': 'ICT Concepts', 'enabled': False, 'performance': 0.0, 'trades': 0},
        }

    def _load_ai_models(self):
        # Simulação de carregamento de modelos de IA do gpt4all/models/
        return {
            'llama_3_2_1b': {'name': 'Llama-3.2-1B', 'specialty': 'Análise Rápida', 'available': True},
            'llama_3_2_3b': {'name': 'Llama-3.2-3B', 'specialty': 'Análise Profunda', 'available': True},
            'nous_hermes': {'name': 'Nous-Hermes-2', 'specialty': 'Sentimento', 'available': True},
            'orca_mini': {'name': 'Orca-Mini-3B', 'specialty': 'Sinais Curto Prazo', 'available': True},
            'phi_3': {'name': 'Phi-3-mini', 'specialty': 'Notícias', 'available': True},
        }
        
    def _load_initial_news(self):
        return [
            {'id': 1, 'time': '08:30', 'source': 'ForexFactory', 'title': 'Decisão da Taxa de Juros do BCE', 'content': 'O Banco Central Europeu manteve a taxa de juros inalterada, conforme esperado, mas a declaração foi hawkish.'},
            {'id': 2, 'time': '10:00', 'source': 'Reuters', 'title': 'Dados de Emprego dos EUA Superam Expectativas', 'content': 'O payroll não-agrícola veio acima do consenso, fortalecendo o dólar e pressionando o ouro.'},
        ]
        
    def _load_initial_signals(self):
        return [
            {'id': 101, 'time': '10:15:00', 'symbol': 'EURUSD', 'direction': 'SELL', 'confidence': 85.5, 'source': 'Adaptive ML', 'strategy': 'adaptive_ml', 'status': 'EXECUTADO'},
            {'id': 102, 'time': '10:30:00', 'symbol': 'GBPUSD', 'direction': 'BUY', 'confidence': 72.1, 'source': 'Supertrend', 'strategy': 'supertrend', 'status': 'PENDENTE'},
        ]

    def update_account_and_positions(self):
        """ Simula a atualização de dados de conta e posições (deveria vir do mt4_communication.py) """
        
        # 1. Simulação de Trade
        if random.random() < 0.1: # 10% de chance de abrir um trade
            ticket = random.randint(100000, 999999)
            symbol = random.choice(['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD'])
            type = random.choice(['BUY', 'SELL'])
            volume = round(random.uniform(0.01, 0.1), 2)
            open_price = round(random.uniform(1.0, 1.3), 5)
            
            self.positions.append({
                'ticket': ticket,
                'symbol': symbol,
                'type': type,
                'volume': volume,
                'open_price': open_price,
                'current_price': open_price,
                'sl': round(open_price - 0.005, 5) if type == 'BUY' else round(open_price + 0.005, 5),
                'tp': round(open_price + 0.01, 5) if type == 'BUY' else round(open_price - 0.01, 5),
                'profit': 0.00,
                'strategy': random.choice(list(self.strategies.keys()))
            })
            self.stats['total_trades_today'] += 1
            
        # 2. Atualiza Posições e Conta
        total_profit = 0.0
        new_positions = []
        for pos in self.positions:
            # Simula flutuação de preço e lucro
            price_change = random.uniform(-0.0005, 0.0005)
            pos['current_price'] = round(pos['current_price'] + price_change, 5)
            
            # Simula P&L (muito simplificado)
            if pos['type'] == 'BUY':
                pos['profit'] = round((pos['current_price'] - pos['open_price']) * 100000 * pos['volume'], 2)
            else:
                pos['profit'] = round((pos['open_price'] - pos['current_price']) * 100000 * pos['volume'], 2)
            
            total_profit += pos['profit']
            
            # Simula fechamento de trade (1% de chance)
            if random.random() < 0.01:
                self.account_data['balance'] += pos['profit']
                self.stats['profit_today'] += pos['profit']
                if pos['profit'] > 0:
                    self.stats['winning_trades'] += 1
                continue # Não adiciona à nova lista de posições
            
            new_positions.append(pos)
            
        self.positions = new_positions
        
        # 3. Atualiza Dados da Conta
        self.account_data['profit'] = round(total_profit, 2)
        self.account_data['equity'] = round(self.account_data['balance'] + total_profit, 2)
        self.account_data['margin'] = round(len(self.positions) * 1000 * random.uniform(0.9, 1.1), 2) # Simulação de margem
        self.account_data['free_margin'] = round(self.account_data['equity'] - self.account_data['margin'], 2)
        self.account_data['margin_level'] = round((self.account_data['equity'] / self.account_data['margin']) * 100 if self.account_data['margin'] > 0 else 10000, 2)
        
        # 4. Atualiza Estatísticas
        if self.stats['total_trades_today'] > 0:
            self.stats['win_rate'] = round((self.stats['winning_trades'] / self.stats['total_trades_today']) * 100, 1)
        
        # 5. Atualiza Histórico de Equity
        if not self.equity_history or self.equity_history[-1]['equity'] != self.account_data['equity']:
            self.equity_history.append({'time': datetime.now().strftime('%H:%M'), 'equity': self.account_data['equity']})
            if len(self.equity_history) > 100: # Limita o histórico
                self.equity_history.pop(0)

    def toggle_strategy(self, strategy_key, enabled):
        if strategy_key in self.strategies:
            self.strategies[strategy_key]['enabled'] = enabled
            return True
        return False

    def get_ai_analysis(self):
        """ Simula a análise de IA periódica """
        analysis = []
        for key, model in self.ai_models.items():
            if model['available']:
                recommendation = random.choice(['BUY', 'SELL', 'HOLD'])
                confidence = random.randint(50, 99)
                analysis.append({
                    'ai_name': model['name'],
                    'specialty': model['specialty'],
                    'recommendation': recommendation,
                    'confidence': confidence,
                    'response': f"Análise de {model['specialty']}: O mercado sugere fortemente **{recommendation}** com {confidence}% de confiança devido a fatores de {random.choice(['volatilidade', 'tendência', 'notícias'])}."
                })
        
        # Calcula o consenso
        buys = sum(1 for a in analysis if a['recommendation'] == 'BUY')
        sells = sum(1 for a in analysis if a['recommendation'] == 'SELL')
        holds = sum(1 for a in analysis if a['recommendation'] == 'HOLD')
        
        if buys > sells and buys > holds:
            consensus = 'BUY'
        elif sells > buys and sells > holds:
            consensus = 'SELL'
        else:
            consensus = 'HOLD'
            
        total_confidence = sum(a['confidence'] for a in analysis) / len(analysis) if analysis else 0
        
        self.stats['ai_consensus'] = {'recommendation': consensus, 'confidence': round(total_confidence, 0)}
        
        return analysis

    def get_news_update(self):
        """ Simula a atualização de notícias """
        new_news = [
            {'id': random.randint(100, 999), 'time': datetime.now().strftime('%H:%M'), 'source': 'AI News Feed', 'title': f'Alerta de Volatilidade em {random.choice(["EURUSD", "XAUUSD"])}', 'content': 'A IA detectou um aumento incomum na volatilidade. Recomenda-se cautela.'},
        ]
        self.news.extend(new_news)
        self.news = self.news[-10:] # Mantém apenas as 10 mais recentes
        return self.news

# Inicializa o gerenciador de dados
data_manager = DataManager()

# ═══════════════════════════════════════════════════════════════════
# THREADS DE BROADCAST EM TEMPO REAL (SocketIO)
# ═══════════════════════════════════════════════════════════════════

def background_realtime_broadcast():
    """ Broadcast de dados de alta frequência (conta, posições, stats) """
    while True:
        # 1. Atualiza os dados (simulação de recebimento do MT4)
        data_manager.update_account_and_positions()
        
        # 2. Emite os dados via SocketIO
        with app.app_context():
            socketio.emit('account_update', {'data': data_manager.account_data})
            socketio.emit('positions_update', {'data': data_manager.positions})
            socketio.emit('stats_update', {'data': data_manager.stats})
            socketio.emit('equity_history_update', {'data': data_manager.equity_history})
            
        # Intervalo de alta frequência (2 segundos)
        socketio.sleep(2)

def background_ai_news_broadcast():
    """ Broadcast de dados de baixa frequência (IA, Notícias) """
    while True:
        # 1. Análise de IA
        ai_analysis = data_manager.get_ai_analysis()
        with app.app_context():
            socketio.emit('ai_analysis_update', {'data': ai_analysis})
            
        # 2. Atualização de Notícias
        news_update = data_manager.get_news_update()
        with app.app_context():
            socketio.emit('news_update', {'data': news_update})
            
        # Intervalo de baixa frequência (30 segundos)
        socketio.sleep(30)

# Inicia as threads de broadcast
socketio.start_background_task(background_realtime_broadcast)
socketio.start_background_task(background_ai_news_broadcast)

# ═══════════════════════════════════════════════════════════════════
# ROTAS DE AUTENTICAÇÃO (MANTIDAS)
# ═══════════════════════════════════════════════════════════════════

# Usuário de simulação (MUDAR PARA UM BANCO DE DADOS REAL)
USERS = {
    "joka": generate_password_hash("jokapass123")
}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and check_password_hash(USERS[username], password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Usuário ou senha inválidos.")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# ═══════════════════════════════════════════════════════════════════
# ROTA PRINCIPAL DO DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    return render_template('dashboard.html', username=session['username'])

# ═══════════════════════════════════════════════════════════════════
# ROTAS DE API (REST - Para carregamento inicial e ações pontuais)
# ═══════════════════════════════════════════════════════════════════

@app.route('/api/account', methods=['GET'])
def api_account():
    """ Retorna dados da conta (para carregamento inicial) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.account_data})

@app.route('/api/positions', methods=['GET'])
def api_positions():
    """ Retorna posições ativas (para carregamento inicial) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.positions})

@app.route('/api/positions/close', methods=['POST'])
def api_close_position():
    """ Fecha uma posição (ação pontual) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
        
    data = request.get_json()
    ticket = data.get('ticket')
    
    if not ticket:
        return jsonify({'success': False, 'error': 'Ticket não fornecido'}), 400
        
    # Simulação de fechamento
    initial_count = len(data_manager.positions)
    data_manager.positions = [pos for pos in data_manager.positions if pos['ticket'] != ticket]
    
    if len(data_manager.positions) < initial_count:
        # Força um broadcast para atualizar a UI imediatamente
        socketio.emit('positions_update', {'data': data_manager.positions})
        return jsonify({'success': True, 'message': f'Posição {ticket} fechada com sucesso (Simulado)'})
    else:
        return jsonify({'success': False, 'error': f'Posição {ticket} não encontrada'}), 404

@app.route('/api/strategies', methods=['GET'])
def api_strategies():
    """ Retorna a lista de estratégias e seus status """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.strategies})

@app.route('/api/strategies/toggle', methods=['POST'])
def api_toggle_strategy():
    """ Alterna o status de uma estratégia """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
        
    data = request.get_json()
    strategy = data.get('strategy')
    enabled = data.get('enabled')
    
    if not strategy or enabled is None:
        return jsonify({'success': False, 'error': 'Dados incompletos'}), 400
        
    if data_manager.toggle_strategy(strategy, enabled):
        # Emite a atualização para todos os clientes
        socketio.emit('strategy_update', {'strategy': strategy, 'enabled': enabled})
        return jsonify({'success': True, 'message': f'Estratégia {strategy} alterada para {enabled}'})
    else:
        return jsonify({'success': False, 'error': f'Estratégia {strategy} não encontrada'}), 404

@app.route('/api/ai/models', methods=['GET'])
def api_ai_models():
    """ Retorna a lista de modelos de IA """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.ai_models})

@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    """ Rota para o chat com IA (ação pontual) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
        
    data = request.get_json()
    model = data.get('model')
    message = data.get('message')
    
    if not model or not message:
        return jsonify({'success': False, 'error': 'Modelo ou mensagem não fornecidos'}), 400
        
    # Simulação de resposta da IA
    if model == 'all':
        # Simula o consenso de todas as IAs
        responses = []
        for key, ai_info in data_manager.ai_models.items():
            if ai_info['available']:
                response_text = f"A minha análise sobre '{message}' é: {random.choice(['O mercado está em consolidação.', 'Procure por sinais de reversão.', 'A tendência de alta continua forte.'])}"
                responses.append({
                    'ai_name': ai_info['name'],
                    'specialty': ai_info['specialty'],
                    'response': response_text
                })
        return jsonify({'success': True, 'type': 'multiple', 'data': responses})
    else:
        # Simula a resposta de um modelo específico
        ai_info = data_manager.ai_models.get(model)
        if ai_info:
            response_text = f"Como {ai_info['specialty']}, a minha resposta para '{message}' é: {random.choice(['Recomendo cautela.', 'É um bom momento para entrar.', 'Aguarde a próxima vela.'])}"
            return jsonify({'success': True, 'type': 'single', 'data': {'ai_name': ai_info['name'], 'specialty': ai_info['specialty'], 'response': response_text}})
        else:
            return jsonify({'success': False, 'error': 'Modelo de IA não encontrado'}), 404

@app.route('/api/news', methods=['GET'])
def api_news():
    """ Retorna as notícias (para carregamento inicial) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.news})

@app.route('/api/signals', methods=['GET'])
def api_signals():
    """ Retorna os sinais (para carregamento inicial) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.signals})

@app.route('/api/system/status', methods=['GET'])
def api_system_status():
    """ Retorna o status do sistema (para carregamento inicial) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
    return jsonify({'success': True, 'data': data_manager.system_status})

@app.route('/api/system/action', methods=['POST'])
def api_system_action():
    """ Executa ações de controle do sistema (simulação) """
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Não autenticado'}), 401
        
    data = request.get_json()
    action = data.get('action')
    state = data.get('state')
    
    if action == 'bot_toggle':
        new_state = state == 'on'
        data_manager.system_status['bot_running'] = new_state
        socketio.emit('system_status_update', {'data': data_manager.system_status})
        return jsonify({'success': True, 'message': f'Bot alterado para estado: {new_state}'})
    elif action == 'mt4_reconnect':
        data_manager.system_status['mt4_connected'] = True
        socketio.emit('system_status_update', {'data': data_manager.system_status})
        return jsonify({'success': True, 'message': 'Tentativa de reconexão MT4 enviada.'})
    elif action == 'news_reconnect':
        data_manager.system_status['news_api_connected'] = True
        socketio.emit('system_status_update', {'data': data_manager.system_status})
        return jsonify({'success': True, 'message': 'Tentativa de reconexão News API enviada.'})
    else:
        return jsonify({'success': False, 'error': 'Ação de sistema desconhecida'}), 400

# ═══════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO DO SERVIDOR
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # O servidor deve ser iniciado com socketio.run para que as threads funcionem
    print("Iniciando servidor Flask-SocketIO na porta 5000...")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
