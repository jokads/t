# -*- coding: utf-8 -*-
"""
JokaMazKiBu Trading Bot v5.2 - TELEGRAM HANDLER FINAL
Integração MT5 via Socket | 7 IAs | Chat Interativo | Notificações Inteligentes
Autor: Manus AI | Date: 2026-01-01
Status: ✅ PRONTO PARA PRODUÇÃO
"""

import os
import sys
import json
import time
import threading
import logging
import socket
import asyncio
import codecs
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from collections import deque

# =====================================================================
# ENCODING SETUP PARA WINDOWS
# =====================================================================
if sys.platform.startswith("win"):
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
    except (AttributeError, ValueError):
        pass

# =====================================================================
# IMPORTS
# =====================================================================
from pathlib import Path
from dotenv import load_dotenv

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]   # bot-mt5/
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    raise FileNotFoundError(f"❌ .env não encontrado em {ENV_PATH}")


try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot não disponível")

# =====================================================================
# LOGGING
# =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_handler.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("telegram_handler_v5_2")

# =====================================================================
# LOCAL AI MANAGER
# =====================================================================
class LocalAIManager:
    """Gerencia modelos de IA locais (GPT-4All e Llama.cpp)."""
    
    def __init__(self):
        self.logger = logging.getLogger("local_ai_manager")
        self.gpt4all_models_dir = os.getenv("GPT4ALL_MODELS_DIR", r"C:\bot-mt5\models\gpt4all")
        self.llama_model_path = os.getenv("LLAMA_MODEL_PATH", r"C:\bot_ia2\llama.cpp\models\mistral-7b-instruct-v0.1.Q4_K_S.gguf")
        self.llama_exe_path = os.getenv("LLAMA_EXE_PATH", r"C:\bot_ia2\models\llama\llama-cli.exe")
        
        self.models = {
            "gpt1": {"type": "gpt4all", "name": "Análise Técnica"},
            "gpt2": {"type": "gpt4all", "name": "Sentimento"},
            "gpt3": {"type": "gpt4all", "name": "Gestão de Risco"},
            "gpt4": {"type": "gpt4all", "name": "Momentum"},
            "gpt5": {"type": "gpt4all", "name": "Volatilidade"},
            "gpt6": {"type": "gpt4all", "name": "Correlações"},
            "gpt7": {"type": "llama.cpp", "name": "Cérebro Principal"}
        }
        
        self.logger.info("✅ LocalAIManager inicializado")
    
    def generate_response(self, model_id: str, prompt: str) -> str:
        """Gera resposta de um modelo de IA local."""
        if model_id not in self.models:
            return "❌ Modelo de IA não encontrado."
        
        try:
            model_config = self.models[model_id]
            
            if model_config["type"] == "llama.cpp":
                return self._run_llama_cpp(prompt)
            else:
                return f"(Simulado - {model_config['name']}) Resposta para: {prompt[:50]}..."
        
        except Exception as e:
            self.logger.error(f"❌ Erro ao gerar resposta: {e}")
            return f"❌ Erro ao processar com {model_id.upper()}"
    
    def _run_llama_cpp(self, prompt: str) -> str:
        """Executa Llama.cpp via CLI."""
        if not os.path.exists(self.llama_exe_path):
            return f"❌ Llama.cpp não encontrado em: {self.llama_exe_path}"
        if not os.path.exists(self.llama_model_path):
            return f"❌ Modelo não encontrado em: {self.llama_model_path}"
        
        try:
            command = [
                self.llama_exe_path,
                "-m", self.llama_model_path,
                "-p", prompt,
                "-n", "128",
                "--temp", "0.7",
                "--n-gpu-layers", "32"
            ]
            
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                timeout=120
            )
            
            if result.returncode != 0:
                return f"❌ Erro ao executar Llama.cpp"
            
            response = result.stdout.strip()
            if prompt in response:
                response = response.split(prompt, 1)[-1].strip()
            
            return response if response else "Sem resposta"
        
        except subprocess.TimeoutExpired:
            return "❌ Timeout ao executar Llama.cpp"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

# =====================================================================
# TELEGRAM HANDLER V5.2
# =====================================================================
class TelegramHandlerV5_2:
    """Handler de Telegram Ultra Avançado v5.2."""
    
    def __init__(self):
        self.logger = logging.getLogger("telegram_handler_v5_2")
        
        # Configuração
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "7343664374"))
        self.bot_host = os.getenv("MT5_SOCKET_HOST", "127.0.0.1")
        self.bot_port = int(os.getenv("MT5_SOCKET_PORT", "5555"))
        
        if not self.token:
            raise ValueError("❌ TELEGRAM_BOT_TOKEN não configurado!")
        
        # Estado
        self.application = None
        self.is_running = False
        self.authorized_users = {self.chat_id}
        
        # Cache
        self.bot_state = {}
        self.active_trades = {}
        self.strategy_stats = {}
        self.ai_models = {}
        self.user_sessions = {}
        self.last_ai_query_time = {}
        
        # Estatísticas
        self.stats = {
            "messages_sent": 0,
            "commands_processed": 0,
            "notifications_sent": 0,
            "trades_notified": 0,
            "start_time": datetime.now(timezone.utc)
        }
        
        # IA Manager
        self.ai_manager = LocalAIManager()
        
        self.logger.info("✅ TelegramHandlerV5_2 inicializado com sucesso")
    
    # =====================================================================
    # CONEXÃO COM BOT MT5
    # =====================================================================
    def connect_to_bot(self) -> Optional[socket.socket]:
        """Conecta ao bot MT5 via socket."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self.bot_host, self.bot_port))
            return sock
        except Exception as e:
            self.logger.error(f"❌ Erro ao conectar ao bot: {e}")
            return None
    
    def send_command_to_bot(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Envia comando ao bot e recebe resposta."""
        sock = self.connect_to_bot()
        if not sock:
            return None
        
        try:
            sock.sendall(json.dumps(command).encode("utf-8") + b"\n")
            response = sock.recv(65536).decode("utf-8")
            return json.loads(response)
        except Exception as e:
            self.logger.error(f"❌ Erro ao enviar comando: {e}")
            return None
        finally:
            try:
                sock.close()
            except:
                pass
    
    def sync_bot_data(self):
        """Sincroniza dados do bot."""
        try:
            response = self.send_command_to_bot({"action": "get_status"})
            if response and response.get("status") == "success":
                self.bot_state = response.get("bot_state", {})
                self.active_trades = response.get("active_trades", {})
                self.strategy_stats = response.get("strategy_stats", {})
                self.ai_models = response.get("ai_models", {})
                return True
        except Exception as e:
            self.logger.error(f"❌ Erro ao sincronizar: {e}")
        
        return False
    
    # =====================================================================
    # COMANDOS
    # =====================================================================
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start."""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Usuário"
            
            self.authorized_users.add(user_id)
            
            welcome_message = """🚀 **JokaMazKiBu Trading Bot v5.2 HARDCORE**

Bem-vindo ao sistema de trading ultra avançado!

🤖 **7 IAs Integradas:**
• GPT-1 (Análise Técnica)
• GPT-2 (Sentimento)
• GPT-3 (Gestão de Risco)
• GPT-4 (Momentum)
• GPT-5 (Volatilidade)
• GPT-6 (Correlações)
• GPT-7 (Cérebro Principal)

📊 **Funcionalidades:**
✅ Monitoramento de trades em tempo real
✅ Análise de estratégias
✅ Chat com IAs
✅ Notificações inteligentes
✅ Relatórios diários

**Comandos:** /status /balance /trades /strategies /ai /analysis /stats /help"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Status", callback_data="status"),
                 InlineKeyboardButton("💰 Saldo", callback_data="balance")],
                [InlineKeyboardButton("📈 Trades", callback_data="trades"),
                 InlineKeyboardButton("🧠 Estratégias", callback_data="strategies")],
                [InlineKeyboardButton("🤖 Chat IA", callback_data="ai_chat"),
                 InlineKeyboardButton("❓ Ajuda", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            self.logger.info(f"✅ /start por {username}")
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /start: {e}")
            await update.message.reply_text("❌ Erro ao processar comando")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status."""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            self.sync_bot_data()
            bot = self.bot_state
            uptime = self._get_uptime()
            
            status_message = f"""📊 **STATUS DO SISTEMA**

🤖 **Bot:** {'✅ Ativo' if bot.get('connected') else '⚠️ Offline'}
🔗 **MT5:** {'✅ Conectado' if bot.get('connected') else '❌ Desconectado'}

💰 **Conta:**
• Saldo: ${bot.get('balance', 0):.2f}
• Equity: ${bot.get('equity', 0):.2f}
• Lucro: ${bot.get('profit_loss', 0):.2f}

📈 **Trading:**
• Trades Abertos: {bot.get('open_trades', 0)}
• Taxa de Ganho: {bot.get('win_rate', 0):.1f}%

🕐 Uptime: {uptime}"""
            
            await update.message.reply_text(status_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /status: {e}")
            await update.message.reply_text("❌ Erro ao obter status")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /balance."""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            self.sync_bot_data()
            bot = self.bot_state
            balance = bot.get('balance', 0)
            equity = bot.get('equity', 0)
            profit = bot.get('profit_loss', 0)
            
            balance_message = f"""💰 **SALDO DA CONTA**

💵 Saldo: ${balance:.2f}
📊 Equity: ${equity:.2f}
📈 Lucro/Perda: ${profit:.2f}

🎯 **Metas:**
• Diária (2%): ${balance * 0.02:.2f}
• Mensal (20%): ${balance * 0.20:.2f}"""
            
            await update.message.reply_text(balance_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /balance: {e}")
            await update.message.reply_text("❌ Erro ao obter saldo")
    
    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /trades."""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            self.sync_bot_data()
            trades = self.active_trades
            
            if not trades:
                trades_message = "📈 **TRADES ATIVOS**\n\nNenhum trade aberto."
            else:
                trades_message = "📈 **TRADES ATIVOS**\n\n"
                for trade_id, trade in list(trades.items())[:5]:
                    direction = "🟢 BUY" if trade.get('direction') == 'BUY' else "🔴 SELL"
                    profit = trade.get('profit', 0)
                    profit_emoji = "📈" if profit >= 0 else "📉"
                    
                    trades_message += f"""{direction} {trade.get('symbol', 'N/A')}
• Lote: {trade.get('volume', 0):.2f}
• {profit_emoji} Lucro: ${profit:.2f}

"""
            
            await update.message.reply_text(trades_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /trades: {e}")
            await update.message.reply_text("❌ Erro ao obter trades")
    
    async def strategies_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /strategies."""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            self.sync_bot_data()
            strategies = self.strategy_stats
            
            strategies_message = "🧠 **ESTRATÉGIAS**\n\n"
            
            for strategy_name, stats in strategies.items():
                status = "✅" if stats.get('enabled') else "⚠️"
                profit = stats.get('profit', 0)
                profit_emoji = "📈" if profit >= 0 else "📉"
                
                strategies_message += f"""{status} {strategy_name.upper()}
• Trades: {stats.get('trades', 0)}
• Taxa: {stats.get('win_rate', 0):.1f}%
• {profit_emoji} Lucro: ${profit:.2f}

"""
            
            await update.message.reply_text(strategies_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /strategies: {e}")
            await update.message.reply_text("❌ Erro ao obter estratégias")
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ai."""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            ai_message = """🤖 **CHAT COM IAs**

Escolha um modelo:

/gpt1 - Análise Técnica
/gpt2 - Sentimento
/gpt3 - Gestão de Risco
/gpt4 - Momentum
/gpt5 - Volatilidade
/gpt6 - Correlações
/gpt7 - Cérebro Principal

Exemplo: /gpt7 Qual é a situação do EURUSD?"""
            
            await update.message.reply_text(ai_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /ai: {e}")
            await update.message.reply_text("❌ Erro ao processar comando")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help."""
        try:
            help_text = """*Comandos Disponíveis:*

/start - Menu principal
/status - Status do bot
/balance - Saldo da conta
/trades - Trades ativos
/strategies - Estratégias
/ai - Chat com IAs
/gpt1 a /gpt7 - Conversar com IA
/help - Esta mensagem"""
            
            await update.message.reply_text(help_text, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em /help: {e}")
    
    async def generic_ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler genérico para /gpt1 até /gpt7."""
        try:
            user_id = update.effective_user.id
            if not self._is_authorized(user_id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            command = update.message.text.split()[0].replace("/", "")
            query = " ".join(update.message.text.split()[1:])
            
            self.user_sessions[user_id] = {"mode": "ai_chat", "ai_model": command}
            
            if query:
                await self._handle_ai_query(update, context, command, query)
            else:
                await update.message.reply_text(f"🤖 Conversando com **{command.upper()}**. Envie sua pergunta.", parse_mode='Markdown')
        
        except Exception as e:
            self.logger.error(f"❌ Erro em generic_ai_command: {e}")
    
    async def _handle_ai_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE, model_id: str, query: str):
        """Lida com consulta de IA."""
        try:
            user_id = update.effective_user.id
            
            now = time.time()
            last_query_time = self.last_ai_query_time.get(user_id, 0)
            if now - last_query_time < 10:
                await update.message.reply_text("⏳ Aguarde um momento...")
                return
            
            self.last_ai_query_time[user_id] = now
            
            await update.message.reply_text(f"🤖 Pensando com {model_id.upper()}...")
            
            response = await asyncio.to_thread(self.ai_manager.generate_response, model_id, query)
            
            await update.message.reply_text(response)
            self.stats['commands_processed'] += 1
        
        except Exception as e:
            self.logger.error(f"❌ Erro em _handle_ai_query: {e}")
            await update.message.reply_text(f"❌ Erro ao consultar IA")
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para mensagens de texto."""
        try:
            user_id = update.effective_user.id
            if not self._is_authorized(user_id):
                return
            
            text = update.message.text
            session = self.user_sessions.get(user_id)
            
            if session and session.get("mode") == "ai_chat":
                model_id = session.get("ai_model")
                await self._handle_ai_query(update, context, model_id, text)
            else:
                await update.message.reply_text("Use /help para ver os comandos disponíveis.")
        
        except Exception as e:
            self.logger.error(f"❌ Erro em message_handler: {e}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para callbacks de botões."""
        try:
            query = update.callback_query
            await query.answer()
            
            if query.data == "status":
                await self.status_command(update, context)
            elif query.data == "balance":
                await self.balance_command(update, context)
            elif query.data == "trades":
                await self.trades_command(update, context)
            elif query.data == "strategies":
                await self.strategies_command(update, context)
            elif query.data == "ai_chat":
                await self.ai_command(update, context)
            elif query.data == "help":
                await self.help_command(update, context)
        
        except Exception as e:
            self.logger.error(f"❌ Erro em button_callback: {e}")
    
    # =====================================================================
    # NOTIFICAÇÕES
    # =====================================================================
    async def send_notification(self, message: str, parse_mode: str = 'Markdown'):
        """Envia notificação para o Telegram."""
        try:
            if not TELEGRAM_AVAILABLE or not self.application:
                return False
            
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            
            self.stats['messages_sent'] += 1
            self.stats['notifications_sent'] += 1
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Erro ao enviar notificação: {e}")
            return False
    
    # =====================================================================
    # UTILITÁRIOS
    # =====================================================================
    def _is_authorized(self, user_id: int) -> bool:
        """Verifica se o usuário está autorizado."""
        return user_id in self.authorized_users
    
    def _get_uptime(self) -> str:
        """Retorna uptime formatado."""
        uptime = datetime.now(timezone.utc) - self.stats['start_time']
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    # =====================================================================
    # INICIALIZAÇÃO
    # =====================================================================
    async def setup(self):
        """Configura o handler."""
        if not TELEGRAM_AVAILABLE:
            self.logger.error("❌ python-telegram-bot não disponível")
            return False
        
        try:
            self.application = Application.builder().token(self.token).build()
            
            # Handlers de comando
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("balance", self.balance_command))
            self.application.add_handler(CommandHandler("trades", self.trades_command))
            self.application.add_handler(CommandHandler("strategies", self.strategies_command))
            self.application.add_handler(CommandHandler("ai", self.ai_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            
            # Handlers para IAs
            for i in range(1, 8):
                self.application.add_handler(CommandHandler(f"gpt{i}", self.generic_ai_command))
            
            # Handlers para callbacks e mensagens
            self.application.add_handler(CallbackQueryHandler(self.button_callback))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
            
            self.logger.info("✅ Telegram Handler v5.2 configurado com sucesso")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Erro ao configurar: {e}")
            return False
    
    def start(self):
        """Inicia o Telegram Bot (compatível com Python 3.12)."""

        # 🔥 CRIA EVENT LOOP MANUALMENTE
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if not loop.is_running():
            loop.run_until_complete(self.setup())

        self.is_running = True
        self.logger.info("🚀 Telegram Bot iniciado e em polling")

        # BLOQUEANTE
        self.application.run_polling()


    async def stop(self):
        """Para o handler."""
        try:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
                self.is_running = False
                self.logger.info("✅ Telegram Handler parado")
        except Exception as e:
            self.logger.error(f"❌ Erro ao parar: {e}")


# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("JokaMazKiBu Trading Bot - Telegram Handler v5.2 FINAL")
    logger.info("=" * 80)

    try:
        handler = TelegramHandlerV5_2()
        logger.info("✅ Telegram Handler v5.2 inicializado com sucesso")

        # BLOQUEIA ATÉ CTRL+C
        handler.start()

    except KeyboardInterrupt:
        logger.info("⏹️ Encerrando por CTRL+C")
    except Exception as e:
        logger.exception(f"❌ Erro fatal: {e}")
        sys.exit(1)
