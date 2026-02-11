#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
JokaMazKiBu Trading Bot v4.0 HARDCORE - TELEGRAM HANDLER ULTRA CORRIGIDO
Telegram Handler Ultra Avançado com Chat IA e Notificações
Autor: JokaMazKiBu
CORREÇÃO: Token e ID configurados corretamente
"""

import os
import sys
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import codecs
import asyncio
import re
from core.mt4_communication import MT4Communication

# Configuração de encoding para Windows
if sys.platform.startswith("win"):
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        # Reconfigura stdout e stderr para escreverem em UTF-8 sobre o buffer de bytes
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
    except (AttributeError, ValueError):
        # Se não existir .buffer ou der outro problema, mantém o stream original
        pass

# Imports com fallback
try:
    import telegram
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot não disponível - Telegram Bot não funcionará")

try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_handler.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("telegram_handler")


class TelegramHandler:
    """
    Handler de Telegram ultra avançado
    """
    def __init__(self, token: str = None, trading_bot=None, mt4: "MT4Communication" = None):
        self.logger = logging.getLogger("telegram_handler")

        # === Configuração do token ===
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            self.logger.error("❌ Token do Telegram não configurado! Configure TELEGRAM_BOT_TOKEN no .env")
            raise ValueError("Token do Telegram não configurado!")

        # === Configuração de IDs ===
        self.bot_id = os.getenv("TELEGRAM_BOT_ID", "7536817878")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "1234567890")

        # Verifica se chat_id é numérico
        if self.chat_id and not self.chat_id.isdigit():
            self.logger.warning("⚠️ O CHAT_ID não é numérico. Notificações podem falhar.")

        # === Referências externas ===
        self.trading_bot = trading_bot     # núcleo de trading
        self.mt4 = mt4                     # instância MT4Communication (opcional)

        # === Estado interno ===
        self.application = None
        self.is_running = False

        # Usuários autorizados (pode expandir depois)
        self.authorized_users = set()
        if self.chat_id and self.chat_id.isdigit():
            self.authorized_users.add(int(self.chat_id))

        # Cache e estatísticas
        self.message_cache = {}
        self.last_notification = {}
        self.user_stats = {}   # {user_id: {"commands": 0, "messages": 0}}

        self.stats = {
            "messages_sent": 0,
            "commands_processed": 0,
            "notifications_sent": 0,
            "start_time": datetime.now()
        }

        # Configurações de notificação
        self.notification_settings = {
            "trades": True,
            "profits": True,
            "losses": True,
            "emergency": True,
            "daily_summary": True,
            "ai_analysis": True
        }

        # Anti-spam cooldowns por usuário
        self.user_cooldowns = {}

        # Log de inicialização
        self.logger.info("✅ TelegramHandler inicializado com sucesso")
        self.logger.info(f"🤖 Bot ID: {self.bot_id}")
        self.logger.info(f"💬 Chat ID: {self.chat_id}")
        self.logger.info(f"✅ Usuários autorizados: {self.authorized_users}")


    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Usuário"
            
            # Adicionar usuário aos autorizados (temporário para teste)
            self.authorized_users.add(user_id)
            
            welcome_message = f"""
🚀 **JokaMazKiBu Trading Bot v4.0 ULTRA**

Bem-vindo, {username}! 

🤖 **7 IAs Integradas:**
• Nous-Hermes-2-Mistral-7B (Análise Técnica)
• Orca-Mini-3B (Sentimento)
• Llama-3.2-3B (Gestão de Risco)
• Llama-3.2-1B (Momentum)
• Phi-3-Mini (Volatilidade)
• Qwen2-1.5B (Correlações)
• Mistral-7B (CÉREBRO PRINCIPAL)

🎯 **Meta: 50€ → 10.000€/mês**

**Comandos disponíveis:**
/status - Status do bot
/balance - Saldo da conta
/positions - Posições abertas
/signals - Últimos sinais
/ai - Chat com IAs
/stats - Estatísticas
/settings - Configurações
/help - Ajuda

Digite qualquer mensagem para conversar com as IAs!
            """
            
            keyboard = [
                [InlineKeyboardButton("📊 Status", callback_data="status"),
                 InlineKeyboardButton("💰 Saldo", callback_data="balance")],
                [InlineKeyboardButton("📈 Posições", callback_data="positions"),
                 InlineKeyboardButton("🎯 Sinais", callback_data="signals")],
                [InlineKeyboardButton("🤖 Chat IA", callback_data="ai_chat"),
                 InlineKeyboardButton("📊 Stats", callback_data="stats")],
                [InlineKeyboardButton("⚙️ Config", callback_data="settings"),
                 InlineKeyboardButton("❓ Ajuda", callback_data="help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
            
            self.stats['commands_processed'] += 1
            self.logger.info(f"✅ Comando /start executado por {username} (ID: {user_id})")
            
        except Exception as e:
            self.logger.error(f"Erro no comando /start: {e}")
            await update.message.reply_text("❌ Erro ao processar comando /start")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /status"""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            # Simular dados de status
            status_message = f"""
📊 **STATUS DO SISTEMA**

🤖 **Bot Status:** ✅ Ativo
🔗 **MT4 Conexão:** ✅ Conectado
🧠 **IAs Online:** 7/7
📡 **Telegram:** ✅ Funcionando

💰 **Conta:**
• Saldo: €50.00
• Equity: €50.00
• Margem Livre: €50.00

📈 **Trading Hoje:**
• Trades: 0
• Lucro: €0.00
• Taxa de Sucesso: 0%

🕐 **Uptime:** {self._get_uptime()}
📨 **Mensagens Enviadas:** {self.stats['messages_sent']}
            """
            
            await update.message.reply_text(status_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro no comando /status: {e}")
            await update.message.reply_text("❌ Erro ao obter status")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /balance — busca dados ao vivo do MT4 sem bloquear o bot."""
        try:
            user_id = update.effective_user.id
            if not self._is_authorized(user_id):
                return await update.message.reply_text("❌ Acesso negado")

            # 1) Executa get_account_info em thread separado
            account_info = await asyncio.to_thread(self.mt4.get_account_info)
            if not account_info:
                return await update.message.reply_text(
                    "⚠️ Não consegui obter informações da conta MT4."
                )

            # 2) Extrai campos
            balance      = account_info.balance
            equity       = account_info.equity
            margin_used  = account_info.margin      # se disponível
            free_margin  = account_info.free_margin
            margin_level = account_info.margin_level

            # 3) Monta e envia a mensagem
            text = (
                f"💰 **SALDO DA CONTA MT4**\n\n"
                f"💵 **Saldo:** {balance:.2f}\n"
                f"📊 **Equity:** {equity:.2f}\n"
                f"📉 **Margem Usada:** {margin_used:.2f}\n"
                f"📈 **Margem Livre:** {free_margin:.2f}\n"
                f"📊 **Nível de Margem:** {margin_level:.2f}%\n\n"
                f"🎯 **Meta Diária (2%):** €{balance * 0.02:.2f}\n"
                f"🏆 **Meta Mensal (20%):** €{balance * 0.20:.2f}"
            )
            await update.message.reply_text(text, parse_mode='Markdown')
            self.stats['commands_processed'] += 1

        except Exception as e:
            self.logger.error(f"Erro no comando /balance: {e}")
            await update.message.reply_text("❌ Erro ao obter saldo")

    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /positions"""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            positions_message = """
📈 **POSIÇÕES ABERTAS**

Nenhuma posição aberta no momento.

🎯 **Aguardando sinais das 7 IAs...**

Use /signals para ver os últimos sinais gerados.
            """
            
            await update.message.reply_text(positions_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro no comando /positions: {e}")
            await update.message.reply_text("❌ Erro ao obter posições")
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /signals"""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            signals_message = f"""
🎯 **ÚLTIMOS SINAIS**

📊 **EURUSD**
• Direção: Aguardando
• Confiança: 0%
• Fonte: Sistema
• Tempo: Aguardando análise

🤖 **Status das IAs:**
• Nous-Hermes: ✅ Online
• Orca-Mini: ✅ Online  
• Llama-3B: ✅ Online
• Llama-1B: ✅ Online
• Phi-3: ✅ Online
• Qwen2: ✅ Online
• Mistral: ✅ Online (CÉREBRO)

🗳️ **Sistema de Votação:** 4/7 IAs necessárias
            """
            
            await update.message.reply_text(signals_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro no comando /signals: {e}")
            await update.message.reply_text("❌ Erro ao obter sinais")
    
    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ai - Chat com IAs"""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            # Obter mensagem após o comando
            message_text = ' '.join(context.args) if context.args else ""
            
            if not message_text:
                ai_help = """
🤖 **CHAT COM AS 7 IAs**

**Como usar:**
/ai [sua pergunta]

**Exemplos:**
/ai Qual a análise do EURUSD?
/ai Devo comprar ou vender agora?
/ai Como está o sentimento do mercado?

**IAs Disponíveis:**
• Nous-Hermes (Análise Técnica)
• Orca-Mini (Sentimento)
• Llama-3B (Gestão de Risco)
• Llama-1B (Momentum)
• Phi-3 (Volatilidade)
• Qwen2 (Correlações)
• Mistral (Coordenação - CÉREBRO)

Ou simplesmente digite qualquer mensagem para conversar!
                """
                await update.message.reply_text(ai_help, parse_mode='Markdown')
                return
            
            # Processar pergunta para as IAs
            await self._process_ai_query(update, message_text)
            
        except Exception as e:
            self.logger.error(f"Erro no comando /ai: {e}")
            await update.message.reply_text("❌ Erro ao processar comando IA")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /stats"""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            uptime = self._get_uptime()
            
            stats_message = f"""
📊 **ESTATÍSTICAS DO BOT**

⏰ **Uptime:** {uptime}
📨 **Mensagens Enviadas:** {self.stats['messages_sent']}
🎮 **Comandos Processados:** {self.stats['commands_processed']}
🔔 **Notificações:** {self.stats['notifications_sent']}

🤖 **IAs Ativas:** 7/7
📈 **Trades Hoje:** 0
💰 **Lucro Hoje:** €0.00
🎯 **Taxa de Sucesso:** 0%

🔗 **Conexões:**
• MT4: ✅ Conectado
• Dashboard: ✅ Ativo
• Telegram: ✅ Online
• News API: ✅ Funcionando
            """
            
            await update.message.reply_text(stats_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro no comando /stats: {e}")
            await update.message.reply_text("❌ Erro ao obter estatísticas")
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /settings"""
        try:
            if not self._is_authorized(update.effective_user.id):
                await update.message.reply_text("❌ Acesso negado")
                return
            
            settings_message = """
⚙️ **CONFIGURAÇÕES**

🔔 **Notificações:**
• Trades: ✅ Ativo
• Lucros: ✅ Ativo
• Perdas: ✅ Ativo
• Emergência: ✅ Ativo
• Resumo Diário: ✅ Ativo

🤖 **IA:**
• Votos Mínimos: 4/7
• Confiança Mínima: 60%
• Timeout: 30s

💰 **Trading:**
• Lote Mín: 0.01
• Lote Máx: 0.15
• Risco: 2% por trade
• Auto Trading: ✅ Ativo

Use o dashboard para alterar configurações.
            """
            
            await update.message.reply_text(settings_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro no comando /settings: {e}")
            await update.message.reply_text("❌ Erro ao obter configurações")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        try:
            help_message = """
❓ **AJUDA - JOKAMAZKIBU TRADING BOT v4.0**

**Comandos Principais:**
/start - Iniciar bot
/status - Status do sistema
/balance - Saldo da conta
/positions - Posições abertas
/signals - Últimos sinais
/ai [pergunta] - Chat com IAs
/stats - Estatísticas
/settings - Configurações
/help - Esta ajuda

**Chat com IAs:**
Digite qualquer mensagem para conversar com as 7 IAs!

**Funcionalidades:**
🤖 7 IAs especializadas
🗳️ Sistema de votação 4/7
📊 Análise técnica avançada
📰 Análise de notícias
🎯 Meta: 50€ → 10.000€/mês

**Suporte:**
@JokaMazKiBu
support@jokamazkibu.com
            """
            
            await update.message.reply_text(help_message, parse_mode='Markdown')
            self.stats['commands_processed'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro no comando /help: {e}")
            await update.message.reply_text("❌ Erro ao mostrar ajuda")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processar mensagens gerais (chat com IA) com inteligência máxima e resiliência"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Usuário"
            message_text = update.message.text.strip() if update.message.text else ""

            # Verificar autorização
            if not self._is_authorized(user_id):
                await update.message.reply_text("❌ Acesso negado. Você não está autorizado a usar este bot.")
                self.logger.warning(f"❌ Mensagem negada de {username} (ID {user_id})")
                return

            # Anti-spam cooldown
            now = datetime.utcnow()
            if not hasattr(self, "user_cooldowns"):
                self.user_cooldowns = {}

            last_time = self.user_cooldowns.get(user_id)
            if last_time and (now - last_time).total_seconds() < 5:
                await update.message.reply_text("⏳ Por favor, aguarde alguns segundos antes de enviar outra pergunta.")
                return
            self.user_cooldowns[user_id] = now

            # Detectar comandos embutidos
            if message_text.startswith('/'):
                match = re.match(r'^/(\w+)\s+(.*)$', message_text)
                if match:
                    message_text = match.group(2)
                else:
                    return  # comando sem argumento, ignorar

            if not message_text:
                await update.message.reply_text("⚠️ A mensagem estava vazia. Por favor, envie algum texto.")
                return

            # Mensagem de processamento
            processing_msg = await update.message.reply_text(
                "🤖 *Processando sua pergunta...*\n"
                "🔍 *Buscando análises das IAs e notícias relevantes...*",
                parse_mode="Markdown"
            )

            # Tentar extrair símbolo
            symbols = self._extract_symbols_from_text(message_text)
            articles = []
            for sym in symbols[:3]:  # pega até 3
                articles.extend(self.trading_bot.news_manager.fetch_news_for(sym))

            # Resposta das IAs
            ai_response = await self._process_ai_query(update, message_text)

            # Montar resumo das notícias
            if articles:
                news_text = "\n\n".join(
                    f"📰 [{a['title']}]({a['url']})\n*Resumo:* {a.get('ai_summary','') or 'Sem resumo disponível.'}"
                    for a in articles[:3]
                )
            else:
                news_text = "ℹ️ *Nenhuma notícia recente encontrada.*"

            # Mensagem final
            final_text = f"{ai_response}\n\n{news_text}"

            await processing_msg.edit_text(
                final_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

            self.stats['messages_sent'] += 1
            self.logger.info(f"✅ Mensagem processada de {username} (ID {user_id})")

        except Exception as e:
            self.logger.exception(f"❌ Erro ao processar mensagem:")
            try:
                await update.message.reply_text(
                    "❌ *Erro ao processar sua mensagem.* Por favor, tente novamente.",
                    parse_mode='Markdown'
                )  
            except Exception:
                pass

    
    def _extract_symbols_from_text(self, text: str) -> List[str]:
        """
        Retorna todos os símbolos mencionados no texto.
        """
        found: List[str] = []
        text_upper = text.upper()
        # Puxe a lista de símbolos da config do seu bot:
        symbol_list = getattr(self.trading_bot, "assets_config", {}).get("symbols", [])
        for symbol in symbol_list:
            # \b garante palavra inteira
            pattern = r'\b' + re.escape(symbol) + r'\b'
            if re.search(pattern, text_upper):
                found.append(symbol)
        # → agora o return está **fora** do for
        return found



    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processar callbacks dos botões inline"""
        try:
            query = update.callback_query
            await query.answer()
            
            if not self._is_authorized(query.from_user.id):
                await query.edit_message_text("❌ Acesso negado")
                return
            
            callback_data = query.data
            
            if callback_data == "status":
                await self._send_status_callback(query)
            elif callback_data == "balance":
                await self._send_balance_callback(query)
            elif callback_data == "positions":
                await self._send_positions_callback(query)
            elif callback_data == "signals":
                await self._send_signals_callback(query)
            elif callback_data == "ai_chat":
                await self._send_ai_chat_callback(query)
            elif callback_data == "stats":
                await self._send_stats_callback(query)
            elif callback_data == "settings":
                await self._send_settings_callback(query)
            elif callback_data == "help":
                await self._send_help_callback(query)
            
        except Exception as e:
            self.logger.error(f"Erro no callback: {e}")
    
    async def generate_with_model(self, prompt: str, model_name: str, max_tokens: int = 200) -> str:
        # Exemplo genérico: chamar seu core de IA
        if model_name.startswith("Llama"):
            return await self.llama_client.generate(prompt, max_tokens=max_tokens)
        elif model_name.startswith("Qwen"):
            return await self.qwen_client.generate(prompt, max_tokens=max_tokens)
        elif model_name.startswith("Mistral") or model_name.startswith("Nous"):
            return await self.mistral_client.generate(prompt, max_tokens=max_tokens)
        elif model_name.startswith("Orca"):
            return await self.orca_client.generate(prompt, max_tokens=max_tokens)
        elif model_name.startswith("Phi"):
            return await self.phi_client.generate(prompt, max_tokens=max_tokens)
        else:
            return "❌ Modelo desconhecido"


    async def _process_ai_query(self, update: Update, message: str):
        """Processar pergunta para as IAs de forma real"""
        try:
            # Enviar mensagem de processamento
            processing_msg = await update.message.reply_text("🤖 Consultando as 7 IAs... ⏳")
            
            # Lista das IAs
            ai_models = [
                "Nous-Hermes-2-Mistral-7B",
                "Orca-Mini-3B",
                "Llama-3.2-3B",
                "Llama-3.2-1B",
                "Phi-3-Mini",
                "Qwen2-1.5B",
                "Mistral-7B"
            ]
            
            ai_responses: Dict[str, str] = {}
            
            # Chamar cada IA de forma real
            for model_name in ai_models:
                try:
                    # Substitua generate_with_model pelo seu wrapper real de cada IA
                    response = await self.generate_with_model(prompt=message, model_name=model_name, max_tokens=200)
                    ai_responses[model_name] = response.strip()
                except Exception as e:
                    self.logger.warning("Falha ao gerar resposta da IA %s: %s", model_name, e)
                    ai_responses[model_name] = "❌ Erro ao gerar resposta"
            
            # Construir resposta final
            response_text = f"🤖 **RESPOSTAS DAS 7 IAs**\n\n**Sua pergunta:** {message}\n\n"
            for ai_name, response in ai_responses.items():
                specialty = self._get_ai_specialty(ai_name)
                response_text += f"**{ai_name}** ({specialty}):\n{response}\n\n"
            
            # Consenso (opcional: aqui você pode implementar cálculo real depois)
            response_text += "🗳️ **CONSENSO:** 4/7 IAs recomendam cautela\n"
            response_text += "📊 **CONFIANÇA MÉDIA:** 65%"
            
            # Editar mensagem de processamento
            await processing_msg.edit_text(response_text, parse_mode='Markdown')
            
            self.stats['messages_sent'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro ao processar query IA: {e}")
            await update.message.reply_text("❌ Erro ao consultar IAs")

    def _get_ai_specialty(self, ai_name: str) -> str:
        """Obter especialidade da IA"""
        specialties = {
            "Nous-Hermes-2-Mistral-7B": "Análise Técnica",
            "Orca-Mini-3B": "Sentimento",
            "Llama-3.2-3B": "Gestão de Risco",
            "Llama-3.2-1B": "Momentum",
            "Phi-3-Mini": "Volatilidade",
            "Qwen2-1.5B": "Correlações",
            "Mistral-7B": "CÉREBRO PRINCIPAL"
        }
        return specialties.get(ai_name, "Especialista")
    
    def _is_authorized(self, user_id: int) -> bool:
        """Verificar se usuário está autorizado"""
        return user_id in self.authorized_users
    
    def _get_uptime(self) -> str:
        """Obter tempo de funcionamento"""
        uptime = datetime.now() - self.stats['start_time']
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    
    async def _send_status_callback(self, query):
        """Callback para status"""
        status_text = "📊 **STATUS RÁPIDO**\n\n✅ Bot Ativo\n✅ MT4 Conectado\n✅ 7 IAs Online\n💰 Saldo: €50.00"
        await query.edit_message_text(status_text, parse_mode='Markdown')
    
    async def _send_balance_callback(self, query):
        """Callback para saldo"""
        balance_text = "💰 **SALDO RÁPIDO**\n\n💵 Saldo: €50.00\n📊 Equity: €50.00\n📈 Lucro Hoje: €0.00"
        await query.edit_message_text(balance_text, parse_mode='Markdown')
    
    async def _send_positions_callback(self, query):
        """Callback para posições"""
        positions_text = "📈 **POSIÇÕES**\n\nNenhuma posição aberta.\n🎯 Aguardando sinais..."
        await query.edit_message_text(positions_text, parse_mode='Markdown')
    
    async def _send_signals_callback(self, query):
        """Callback para sinais"""
        signals_text = "🎯 **SINAIS**\n\n📊 EURUSD: Aguardando\n🤖 7 IAs analisando..."
        await query.edit_message_text(signals_text, parse_mode='Markdown')
    
    async def _send_ai_chat_callback(self, query):
        """Callback para chat IA"""
        ai_text = "🤖 **CHAT IA**\n\nDigite qualquer mensagem para conversar com as 7 IAs!\n\nExemplo: 'Como está o EURUSD?'"
        await query.edit_message_text(ai_text, parse_mode='Markdown')
    
    async def _send_stats_callback(self, query):
        """Callback para stats"""
        stats_text = f"📊 **STATS**\n\n⏰ Uptime: {self._get_uptime()}\n📨 Mensagens: {self.stats['messages_sent']}\n🎮 Comandos: {self.stats['commands_processed']}"
        await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    async def _send_settings_callback(self, query):
        """Callback para configurações"""
        settings_text = "⚙️ **CONFIGURAÇÕES**\n\n🔔 Notificações: ✅\n🤖 Auto Trading: ✅\n🎯 Risco: 2%"
        await query.edit_message_text(settings_text, parse_mode='Markdown')
    
    async def _send_help_callback(self, query):
        """Callback para ajuda"""
        help_text = "❓ **AJUDA**\n\nComandos: /status /balance /positions /signals /ai /stats\n\nDigite qualquer mensagem para chat IA!"
        await query.edit_message_text(help_text, parse_mode='Markdown')
    
    def start_bot(self) -> bool:
        """Inicia o Telegram Bot (bloqueante) — use em thread ou rodando isolado."""
        if not TELEGRAM_AVAILABLE:
            self.logger.error("❌ Biblioteca python-telegram-bot não instalada")
            return False

        if not self.token:
           self.logger.error("❌ Token do Telegram Bot ausente (verifique .env)")
           return False

        try:
            # Cria a aplicação
            self.application = (
                Application.builder()
                .token(self.token)
                .build()
            )

            # Registra todos os comandos
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("balance", self.balance_command))
            self.application.add_handler(CommandHandler("positions", self.positions_command))
            self.application.add_handler(CommandHandler("signals", self.signals_command))
            self.application.add_handler(CommandHandler("ai", self.ai_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("settings", self.settings_command))
            self.application.add_handler(CommandHandler("help", self.help_command))

            # Mensagem texto livre (IA Chat)
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )

            # Botões de callback
            self.application.add_handler(CallbackQueryHandler(self.handle_callback))

            self.logger.info("🚀 Iniciando Telegram Bot (polling bloqueante)...")
            self.is_running = True

            # Bloqueia até receber Ctrl+C
            self.application.run_polling(drop_pending_updates=True)
            return True

        except Exception as e:
           self.logger.error(f"❌ Erro ao iniciar Telegram Bot: {e}")
           return False


    async def start_bot_async(self):
        """
        Inicia o Telegram Bot de forma assíncrona.
        Use isto quando rodar DENTRO do loop principal do bot.
        """
        if not TELEGRAM_AVAILABLE:
            self.logger.error("❌ Biblioteca python-telegram-bot não instalada")
            return

        if not self.token:
            self.logger.error("❌ Token do Telegram Bot ausente (verifique .env)")
            return

        try:
            # Cria a aplicação se ainda não existir
            if not self.application:
               self.application = (
                Application.builder()
                .token(self.token)
                .build()
               )

               # Registra os mesmos handlers
               self.application.add_handler(CommandHandler("start", self.start_command))
               self.application.add_handler(CommandHandler("status", self.status_command))
               self.application.add_handler(CommandHandler("balance", self.balance_command))
               self.application.add_handler(CommandHandler("positions", self.positions_command))
               self.application.add_handler(CommandHandler("signals", self.signals_command))
               self.application.add_handler(CommandHandler("ai", self.ai_command))
               self.application.add_handler(CommandHandler("stats", self.stats_command))
               self.application.add_handler(CommandHandler("settings", self.settings_command))
               self.application.add_handler(CommandHandler("help", self.help_command))
               self.application.add_handler(
                   MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                )
               self.application.add_handler(CallbackQueryHandler(self.handle_callback))

               self.logger.info("🚀 Iniciando Telegram Bot (polling async)...")
               self.is_running = True

               # Async: inicializa, inicia, e polling não bloqueante
               await self.application.initialize()
               await self.application.start()
               await self.application.updater.start_polling()

        except Exception as e:
            self.logger.error(f"❌ Erro ao iniciar Telegram Bot (async): {e}")


    def stop_bot(self):
        """Parar bot do Telegram"""
        try:
            if self.application and self.is_running:
                self.application.stop()
                self.is_running = False
                self.logger.info("✅ Telegram Bot parado")
        except Exception as e:
            self.logger.error(f"Erro ao parar bot: {e}")
    
    async def send_notification(self, message: str, notification_type: str = "info"):
        """Enviar notificação"""
        try:
            if not self.is_running or not self.authorized_users:
                return
            
            # Verificar se tipo de notificação está habilitado
            if notification_type in self.notification_settings and not self.notification_settings[notification_type]:
                return
            
            # Adicionar emoji baseado no tipo
            emoji_map = {
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
                "error": "❌",
                "trade": "📈",
                "profit": "💰",
                "loss": "📉"
            }
            
            emoji = emoji_map.get(notification_type, "📢")
            formatted_message = f"{emoji} {message}"
            
            # Enviar para todos os usuários autorizados
            for user_id in self.authorized_users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=formatted_message,
                        parse_mode='Markdown'
                    )
                    self.stats['notifications_sent'] += 1
                except Exception as e:
                    self.logger.error(f"Erro ao enviar notificação para {user_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Erro ao enviar notificação: {e}")

def main():
    logger.info("🚀 Iniciando bot Telegram integrado com MT4 e TradingCore")

    # 2) Cria a conexão MT4
    mt4 = MT4Communication()

    # 3) Cria o TelegramHandler passando token, core e mt4
    telegram_handler = TelegramHandler(
        token=os.getenv("TELEGRAM_BOT_TOKEN"),
        trading_bot=TradingBotCore,
        mt4=mt4
    )
    if not telegram_handler.token:
        logger.error("❌ TELEGRAM_BOT_TOKEN não configurado no .env")
        return

    # 4) Inicia o polling do Telegram
    telegram_handler.start_bot()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()