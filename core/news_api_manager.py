#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEWS API MANAGER ULTRA CORRIGIDO v4.0
Gerenciador de notícias do NewsAPI.org com correções completas
CORREÇÕES: Leitura correta do .env + Busca real de notícias + Cache inteligente
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sqlite3
from pathlib import Path
from core.my_types import TradeSignal, NewsArticle, TradeDirection, Signal
from core.my_types import TradeSignal
from requests.exceptions import HTTPError

# Imports com fallback
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ Requests não disponível - news manager funcionará em modo simulado")

try:
    from dotenv import load_dotenv
    # Carregar .env do diretório atual
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Arquivo .env carregado de: {env_path.absolute()}")
    else:
        print(f"⚠️ Arquivo .env não encontrado em: {env_path.absolute()}")
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("⚠️ python-dotenv não disponível")

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    print("⚠️ TextBlob não disponível — análise de sentimento desativada.")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('news_manager.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class NewsAPIManager:
    """
    Gerenciador de notícias do NewsAPI.org
    Busca, processa e analisa notícias financeiras em tempo real
    """
    
    def __init__(self):
        self.version = "4.0 ULTRA CORRIGIDO"
        self.logger = logging.getLogger("news_api_manager")
    
        # Configuração da API
        self.api_key = self._load_api_key()
        self.base_url = "https://newsapi.org/v2"
        self.endpoints = {
            'everything':    f"{self.base_url}/everything",
            'top_headlines': f"{self.base_url}/top-headlines",
            'sources':       f"{self.base_url}/sources"
        }
    
        # Cache de notícias
        self.cache          = {}
        self.rate_limited   = {}   # ✅ ESSA LINHA RESOLVE O PROBLEMA
        self.cache_duration = 900
    
        # Lista de símbolos
        self.all_symbols   = ["USDJPY", "EURUSD", "BTCUSD"]
        self._batch_index  = 0
        self._batch_size   = 5
    
        # Thread de atualização automática
        self.auto_update_thread  = None
        self.auto_update_running = False
    
        # Estatísticas
        self.stats = {
            'total_fetched':   0,
            'total_processed': 0,
            'last_fetch_time': None,
            'api_calls_today': 0,
            'errors_count':    0
        }
    
        # Logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.logger.info(f"🗞️ News API Manager v{self.version} inicializado")
        self.logger.info(f"🔑 API Key: {'Configurada' if self.api_key else 'Não configurada'}")
    
        # Testa conexão com a API
        self._test_api_connection()


    
    def analyze_with_ai(self, text: str) -> dict:
        """
        Usa IA para gerar resumo, hipótese e risco de uma notícia.
        """
        if not text or not text.strip():
            return {"summary": "", "hypothesis": "", "risk": ""}

        prompt = (
            "Resuma e analise esta notícia:\n\n"
            f"{text}\n\n"
            "Responda em JSON:\n"
            "{"
            "\"summary\": \"...\","
            "\"hypothesis\": \"...\","
            "\"risk\": \"...\""
            "}"
        )

        # Aqui você chama sua IA (exemplo fictício)
        response = self.ia_manager.ask_model(prompt)

        try:
            data = json.loads(response)
            return data
        except Exception:
            self.logger.warning("⚠️ Resposta IA inválida, usando valores vazios.")
            return {"summary": "", "hypothesis": "", "risk": ""}




    def _load_api_key(self) -> Optional[str]:
        """
        Carregar API key do arquivo .env
        """
        try:
            api_key_vars = ['NEWS_API_KEY', 'NEWSAPI_KEY', 'NEWS_API_TOKEN']
            for var in api_key_vars:
                key = os.getenv(var)
                if key and key.strip() and key != 'YOUR_NEWS_API_KEY_HERE':
                    self.logger.info(f"✅ API Key carregada da variável: {var}")
                    return key.strip()

            env_files = ['.env', '../.env', 'config/.env']
            for env_file in env_files:
                if os.path.exists(env_file):
                    with open(env_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            for var in api_key_vars:
                                if line.startswith(f"{var}="):
                                    val = line.split('=',1)[1].strip().strip('"').strip("'")
                                    if val and val != 'YOUR_NEWS_API_KEY_HERE':
                                        self.logger.info(f"✅ API Key encontrada no arquivo {env_file}")
                                        return val
            # Se não achou em lugar nenhum:
            self.logger.warning("⚠️ API Key não encontrada - modo simulado")
            return None

        except Exception as e:
            self.logger.error(f"❌ Erro ao carregar API Key: {e}")
            return None
    


    def _fetch_next_batch(self):
        """
        Busca notícias para os próximos self._batch_size símbolos,
        avançando self._batch_index (com wrap-around).
        """
        start = self._batch_index
        end   = start + self._batch_size
        batch = self.all_symbols[start:end]
        if end > len(self.all_symbols):
            batch += self.all_symbols[0:(end % len(self.all_symbols))]

        for symbol in batch:
            self.fetch_news_for(symbol)

        self._batch_index = (self._batch_index + self._batch_size) % len(self.all_symbols)


    def start_auto_update(self, interval_minutes: int = 30):
        """
        A cada interval_minutes, busca o próximo batch de notícias.
        """
        if self.auto_update_running:
            self.logger.warning("⚠️ Atualização automática já está rodando")
            return

        self.auto_update_running = True

    
    
        # === define a função de loop de atualização dentro do método ===
        def update_loop():
            while self.auto_update_running:
                self.logger.info(
                    f"🔄 Buscando próximo batch de {self._batch_size} símbolos"
                )
                self._fetch_next_batch()
                time.sleep(interval_minutes * 60)  # usa o interval_minutes do método

        # === cria e inicia a thread, ainda dentro do método ===
        self.auto_update_thread = threading.Thread(
            target=update_loop,
            daemon=True
        )
        self.auto_update_thread.start()

        self.logger.info(
            f"✅ Auto-update iniciado (batch de {self._batch_size} a cada {interval_minutes}min)"
        )  


    def fetch_news_for(self, symbol: str) -> List[dict]:
        now = time.time()

        # 0) cooldown por rate-limit
        if symbol in self.rate_limited:
            if now - self.rate_limited[symbol] < 10 * 60:
                self.logger.warning(f"{symbol} em cooldown, retornando cache")
                return self.cache.get(symbol, {}).get('articles', [])
            else:
                del self.rate_limited[symbol]

        # 1) cache simples
        if symbol in self.cache and (now - self.cache[symbol]['timestamp']) < self.cache_duration:
           return self.cache[symbol]['articles']

        # 2) montar requisição
        params = {
            'qInTitle': symbol,
            'language': 'pt',
            'sortBy': 'publishedAt',
            'pageSize': 20
        }
        headers = {'X-API-Key': self.api_key} if self.api_key else {}
        if not REQUESTS_AVAILABLE or not self.api_key:
           self.logger.warning("Modo simulado: sem requests ou API key")
           return []

        # 3) back-off com máximo de tentativas
        backoff, max_attempts = 1, 5
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.get(
                    self.endpoints['everything'],
                    params=params,
                    headers=headers,
                    timeout=10
                )
                try:
                    resp.raise_for_status()
                except HTTPError:
                    if resp.status_code == 429:
                        if attempt < max_attempts:
                            self.logger.warning(f"[{attempt}/{max_attempts}] 429 para {symbol}, dormindo {backoff}s")
                            time.sleep(backoff)
                            backoff = min(backoff * 2, 60)
                            continue
                        self.logger.warning(f"429 persistente para {symbol}, marcando cooldown")
                        self.rate_limited[symbol] = time.time()
                        return self.cache.get(symbol, {}).get('articles', [])
                    else:
                        raise
                break  # sucesso
            except Exception as e:
                self.stats['errors_count'] += 1
                self.logger.error(f"❌ Erro HTTP ao buscar notícias para {symbol} (tentativa {attempt}): {e}")
                if attempt == max_attempts:
                    return self.cache.get(symbol, {}).get('articles', [])

        # 4) processar resposta
        data = resp.json()
        articles = []

        for a in data.get('articles', []):
            content = a.get('content') or ""
            # Aqui chama a IA
            ai_analysis = self.analyze_with_ai(content)
            article_dict = {
                "title":        a.get('title'),
                "description":  a.get('description'),
                "content":      content,
                "url":          a.get('url'),
                "source":       a.get('source', {}).get('name'),
                "author":       a.get('author'),
                "published_at": a.get('publishedAt'),
                "ai_summary":   ai_analysis.get("summary"),
                "ai_hypothesis":ai_analysis.get("hypothesis"),
                "ai_risk":      ai_analysis.get("risk")
            }
            articles.append(article_dict)

        # 5) atualizar cache e retornar
        self.cache[symbol] = {'timestamp': now, 'articles': articles}
        return articles



    def _test_api_connection(self) -> bool:
        """
        Testar conexão com a API
        """
        if not self.api_key or not REQUESTS_AVAILABLE:
            self.logger.warning("⚠️ API não disponível - modo simulado ativado")
            return False
        
        try:
            headers = {'X-API-Key': self.api_key}
            response = requests.get(
                f"{self.base_url}/sources",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("✅ Conexão com NewsAPI estabelecida")
                return True
            elif response.status_code == 401:
                self.logger.error("❌ API Key inválida")
                return False
            elif response.status_code == 429:
                self.logger.warning("⚠️ Limite de requisições excedido")
                return False
            else:
                self.logger.warning(f"⚠️ Resposta inesperada da API: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao testar conexão: {e}")
            return False
    
    def _init_database(self):
        """
        Inicializar banco de dados para cache de notícias
        """
        try:
            os.makedirs("data", exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Tabela de notícias
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    content TEXT,
                    url TEXT UNIQUE,
                    source TEXT,
                    author TEXT,
                    published_at TIMESTAMP,
                    category TEXT,
                    keywords TEXT,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    impact_score REAL,
                    relevance_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabela de estatísticas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE DEFAULT CURRENT_DATE,
                    total_fetched INTEGER DEFAULT 0,
                    total_processed INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news(sentiment_score)')
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ Banco de dados inicializado")
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao inicializar banco: {e}")
    
    def fetch_forex_news(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Buscar notícias relacionadas ao Forex
        """
        try:
            # Verificar cache
            cache_key = f"forex_news_{limit}"
            if self._is_cache_valid(cache_key):
                self.logger.info("📋 Retornando notícias do cache")
                return self.cache[cache_key]['data']
            
            if not self.api_key or not REQUESTS_AVAILABLE:
                return self._get_simulated_forex_news(limit)
            
            # Construir query de busca
            keywords = ' OR '.join(self.search_config['forex_keywords'][:10])  # Limitar keywords
            
            params = {
                'q': keywords,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': min(limit, 100),  # Máximo da API
                'domains': ','.join([
                    'reuters.com', 'bloomberg.com', 'cnbc.com',
                    'marketwatch.com', 'investing.com', 'forexfactory.com'
                ])
            }
            
            headers = {'X-API-Key': self.api_key}
            
            self.logger.info(f"🔍 Buscando notícias Forex: {keywords[:50]}...")
            
            response = requests.get(
                self.endpoints['everything'],
                headers=headers,
                params=params,
                timeout=15
            )
            
            self.stats['api_calls_today'] += 1
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                # Processar notícias
                processed_news = []
                for article in articles:
                    processed_article = self._process_article(article, 'forex')
                    if processed_article:
                        processed_news.append(processed_article)
                
                # Salvar no cache
                self.cache[cache_key] = {
                    'data': processed_news,
                    'timestamp': datetime.now()
                }
                
                # Salvar no banco
                self._save_news_to_db(processed_news)
                
                self.stats['total_fetched'] += len(articles)
                self.stats['total_processed'] += len(processed_news)
                self.stats['last_fetch_time'] = datetime.now()
                
                self.logger.info(f"✅ {len(processed_news)} notícias Forex processadas")
                return processed_news
                
            elif response.status_code == 429:
                self.logger.warning("⚠️ Limite de API excedido - usando cache/simulação")
                return self._get_cached_or_simulated_news('forex', limit)
            else:
                self.logger.error(f"❌ Erro na API: {response.status_code}")
                return self._get_cached_or_simulated_news('forex', limit)
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar notícias Forex: {e}")
            self.stats['errors_count'] += 1
            return self._get_cached_or_simulated_news('forex', limit)
    
    def fetch_market_news(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Buscar notícias do mercado financeiro
        """
        try:
            cache_key = f"market_news_{limit}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            if not self.api_key or not REQUESTS_AVAILABLE:
                return self._get_simulated_market_news(limit)
            
            keywords = ' OR '.join(self.search_config['market_keywords'][:8])
            
            params = {
                'q': keywords,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': min(limit, 100),
                'category': 'business'
            }
            
            headers = {'X-API-Key': self.api_key}
            
            response = requests.get(
                self.endpoints['everything'],
                headers=headers,
                params=params,
                timeout=15
            )
            
            self.stats['api_calls_today'] += 1
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                processed_news = []
                for article in articles:
                    processed_article = self._process_article(article, 'market')
                    if processed_article:
                        processed_news.append(processed_article)
                
                self.cache[cache_key] = {
                    'data': processed_news,
                    'timestamp': datetime.now()
                }
                
                self._save_news_to_db(processed_news)
                
                self.logger.info(f"✅ {len(processed_news)} notícias de mercado processadas")
                return processed_news
            else:
                return self._get_cached_or_simulated_news('market', limit)
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar notícias de mercado: {e}")
            return self._get_cached_or_simulated_news('market', limit)
    
    def fetch_economic_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Buscar notícias econômicas
        """
        try:
            cache_key = f"economic_news_{limit}"
            if self._is_cache_valid(cache_key):
                return self.cache[cache_key]['data']
            
            if not self.api_key or not REQUESTS_AVAILABLE:
                return self._get_simulated_economic_news(limit)
            
            keywords = ' OR '.join(self.search_config['economic_keywords'])
            
            params = {
                'q': keywords,
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': min(limit, 50),
                'domains': 'reuters.com,bloomberg.com,cnbc.com'
            }
            
            headers = {'X-API-Key': self.api_key}
            
            response = requests.get(
                self.endpoints['everything'],
                headers=headers,
                params=params,
                timeout=15
            )
            
            self.stats['api_calls_today'] += 1
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                processed_news = []
                for article in articles:
                    processed_article = self._process_article(article, 'economic')
                    if processed_article:
                        processed_news.append(processed_article)
                
                self.cache[cache_key] = {
                    'data': processed_news,
                    'timestamp': datetime.now()
                }
                
                self._save_news_to_db(processed_news)
                
                self.logger.info(f"✅ {len(processed_news)} notícias econômicas processadas")
                return processed_news
            else:
                return self._get_cached_or_simulated_news('economic', limit)
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar notícias econômicas: {e}")
            return self._get_cached_or_simulated_news('economic', limit)
    
    def get_all_news(self, limit: int = 50) -> Dict[str, List[Dict[str, Any]]]:
        """
        Buscar todas as categorias de notícias
        """
        try:
            self.logger.info("📰 Buscando todas as categorias de notícias...")
            
            all_news = {
                'forex': self.fetch_forex_news(limit // 3),
                'market': self.fetch_market_news(limit // 3),
                'economic': self.fetch_economic_news(limit // 3)
            }
            
            # Combinar e ordenar por data
            combined_news = []
            for category, news_list in all_news.items():
                combined_news.extend(news_list)
            
            # Ordenar por data de publicação
            combined_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)
            
            # Limitar ao número solicitado
            combined_news = combined_news[:limit]
            
            all_news['combined'] = combined_news
            
            self.logger.info(f"✅ Total de {len(combined_news)} notícias obtidas")
            return all_news
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar todas as notícias: {e}")
            return {
                'forex': self._get_simulated_forex_news(10),
                'market': self._get_simulated_market_news(10),
                'economic': self._get_simulated_economic_news(10),
                'combined': []
            }
    
    def _process_article(self, article: Dict[str, Any], category: str) -> Optional[Dict[str, Any]]:
        """
        Processar artigo individual
        """
        try:
            if not article.get('title') or not article.get('url'):
                return None
            
            # Análise de sentimento
            sentiment = self._analyze_sentiment(article.get('title', '') + ' ' + article.get('description', ''))
            
            # Calcular relevância
            relevance = self._calculate_relevance(article, category)
            
            # Calcular impacto
            impact = self._calculate_impact(article, sentiment)
            
            processed = {
                'title': article.get('title', '').strip(),
                'description': article.get('description', '').strip(),
                'content': article.get('content', '').strip(),
                'url': article.get('url', ''),
                'source': article.get('source', {}).get('name', 'Unknown'),
                'author': article.get('author', ''),
                'published_at': article.get('publishedAt', ''),
                'category': category,
                'keywords': self._extract_keywords(article, category),
                'sentiment_score': sentiment['score'],
                'sentiment_label': sentiment['label'],
                'impact_score': impact,
                'relevance_score': relevance,
                'processed_at': datetime.now().isoformat()
            }
            
            return processed
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao processar artigo: {e}")
            return None
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analisar sentimento do texto
        """
        try:
            if TEXTBLOB_AVAILABLE and text:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                
                if polarity > 0.1:
                    label = 'positive'
                elif polarity < -0.1:
                    label = 'negative'
                else:
                    label = 'neutral'
                
                return {
                    'score': polarity,
                    'label': label
                }
            else:
                # Análise simples baseada em palavras-chave
                positive_words = ['gain', 'rise', 'up', 'bull', 'growth', 'strong', 'positive']
                negative_words = ['fall', 'drop', 'down', 'bear', 'decline', 'weak', 'negative']
                
                text_lower = text.lower()
                positive_count = sum(1 for word in positive_words if word in text_lower)
                negative_count = sum(1 for word in negative_words if word in text_lower)
                
                if positive_count > negative_count:
                    return {'score': 0.3, 'label': 'positive'}
                elif negative_count > positive_count:
                    return {'score': -0.3, 'label': 'negative'}
                else:
                    return {'score': 0.0, 'label': 'neutral'}
                    
        except Exception as e:
            self.logger.error(f"❌ Erro na análise de sentimento: {e}")
            return {'score': 0.0, 'label': 'neutral'}
    
    def _calculate_relevance(self, article: Dict[str, Any], category: str) -> float:
        """
        Calcular relevância do artigo
        """
        try:
            relevance_score = 0.0
            text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            
            # Pontuação baseada em palavras-chave da categoria
            keywords = self.search_config.get(f'{category}_keywords', [])
            for keyword in keywords:
                if keyword.lower() in text:
                    relevance_score += 0.1
            
            # Pontuação baseada na fonte
            source = article.get('source', {}).get('name', '').lower()
            if any(trusted in source for trusted in self.trusted_sources):
                relevance_score += 0.3
            
            # Pontuação baseada na recência
            published_at = article.get('publishedAt', '')
            if published_at:
                try:
                    pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    hours_ago = (datetime.now() - pub_date.replace(tzinfo=None)).total_seconds() / 3600
                    if hours_ago < 24:
                        relevance_score += 0.2
                    elif hours_ago < 48:
                        relevance_score += 0.1
                except:
                    pass
            
            return min(relevance_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao calcular relevância: {e}")
            return 0.5
    
    def _calculate_impact(self, article: Dict[str, Any], sentiment: Dict[str, Any]) -> float:
        """
        Calcular impacto potencial do artigo
        """
        try:
            impact_score = 0.5  # Base
            
            # Impacto baseado no sentimento
            sentiment_score = abs(sentiment.get('score', 0))
            impact_score += sentiment_score * 0.3
            
            # Impacto baseado em palavras-chave de alto impacto
            high_impact_words = [
                'federal reserve', 'ecb', 'interest rate', 'inflation',
                'recession', 'crisis', 'crash', 'emergency', 'breaking'
            ]
            
            text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            for word in high_impact_words:
                if word in text:
                    impact_score += 0.2
            
            return min(impact_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao calcular impacto: {e}")
            return 0.5
    
    def _extract_keywords(self, article: Dict[str, Any], category: str) -> str:
        """
        Extrair palavras-chave do artigo
        """
        try:
            text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            keywords = []
            
            # Buscar palavras-chave da categoria
            category_keywords = self.search_config.get(f'{category}_keywords', [])
            for keyword in category_keywords:
                if keyword.lower() in text:
                    keywords.append(keyword)
            
            return ', '.join(keywords[:5])  # Máximo 5 keywords
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao extrair keywords: {e}")
            return ''
    
    def _save_news_to_db(self, news_list: List[Dict[str, Any]]):
        """
        Salvar notícias no banco de dados
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for news in news_list:
                cursor.execute('''
                    INSERT OR REPLACE INTO news (
                        title, description, content, url, source, author,
                        published_at, category, keywords, sentiment_score,
                        sentiment_label, impact_score, relevance_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    news.get('title'),
                    news.get('description'),
                    news.get('content'),
                    news.get('url'),
                    news.get('source'),
                    news.get('author'),
                    news.get('published_at'),
                    news.get('category'),
                    news.get('keywords'),
                    news.get('sentiment_score'),
                    news.get('sentiment_label'),
                    news.get('impact_score'),
                    news.get('relevance_score')
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao salvar no banco: {e}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Verificar se o cache é válido
        """
        if cache_key not in self.cache:
            return False
        
        cache_time = self.cache[cache_key]['timestamp']
        return (datetime.now() - cache_time).seconds < self.cache_duration
    
    def _get_cached_or_simulated_news(self, category: str, limit: int) -> List[Dict[str, Any]]:
        """
        Obter notícias do cache ou simuladas
        """
        try:
            # Tentar cache primeiro
            cache_key = f"{category}_news_{limit}"
            if cache_key in self.cache:
                return self.cache[cache_key]['data']
            
            # Tentar banco de dados
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT title, description, content, url, source, author,
                       published_at, category, keywords, sentiment_score,
                       sentiment_label, impact_score, relevance_score
                FROM news 
                WHERE category = ? 
                ORDER BY published_at DESC 
                LIMIT ?
            ''', (category, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                news_list = []
                for row in rows:
                    news_list.append({
                        'title': row[0],
                        'description': row[1],
                        'content': row[2],
                        'url': row[3],
                        'source': row[4],
                        'author': row[5],
                        'published_at': row[6],
                        'category': row[7],
                        'keywords': row[8],
                        'sentiment_score': row[9],
                        'sentiment_label': row[10],
                        'impact_score': row[11],
                        'relevance_score': row[12]
                    })
                return news_list
            
            # Fallback para notícias simuladas
            if category == 'forex':
                return self._get_simulated_forex_news(limit)
            elif category == 'market':
                return self._get_simulated_market_news(limit)
            elif category == 'economic':
                return self._get_simulated_economic_news(limit)
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao obter notícias: {e}")
            return []
    
    def _get_simulated_forex_news(self, limit: int) -> List[Dict[str, Any]]:
        """
        Gerar notícias Forex simuladas
        """
        simulated_news = [
            {
                'title': 'EUR/USD mantém-se estável após dados do PIB da Eurozona',
                'description': 'O par EUR/USD negocia em torno de 1.1000 após a divulgação dos dados do PIB da Eurozona que ficaram em linha com as expectativas.',
                'content': 'Análise detalhada dos movimentos do EUR/USD...',
                'url': 'https://example.com/news/1',
                'source': 'Reuters',
                'author': 'Analista Forex',
                'published_at': datetime.now().isoformat(),
                'category': 'forex',
                'keywords': 'EUR/USD, PIB, Eurozona',
                'sentiment_score': 0.1,
                'sentiment_label': 'neutral',
                'impact_score': 0.6,
                'relevance_score': 0.8
            },
            {
                'title': 'Federal Reserve sinaliza possível pausa nas subidas de juros',
                'description': 'Membros do Fed indicam que podem pausar o ciclo de aperto monetário se a inflação continuar a desacelerar.',
                'content': 'Análise das declarações do Federal Reserve...',
                'url': 'https://example.com/news/2',
                'source': 'Bloomberg',
                'author': 'Correspondente Econômico',
                'published_at': (datetime.now() - timedelta(hours=2)).isoformat(),
                'category': 'forex',
                'keywords': 'Federal Reserve, juros, inflação',
                'sentiment_score': 0.3,
                'sentiment_label': 'positive',
                'impact_score': 0.9,
                'relevance_score': 0.9
            },
            {
                'title': 'GBP/USD sob pressão após dados de emprego do Reino Unido',
                'description': 'A libra enfraquece contra o dólar após dados de emprego decepcionantes do Reino Unido.',
                'content': 'Análise dos dados de emprego britânicos...',
                'url': 'https://example.com/news/3',
                'source': 'Financial Times',
                'author': 'Analista de Mercados',
                'published_at': (datetime.now() - timedelta(hours=4)).isoformat(),
                'category': 'forex',
                'keywords': 'GBP/USD, emprego, Reino Unido',
                'sentiment_score': -0.4,
                'sentiment_label': 'negative',
                'impact_score': 0.7,
                'relevance_score': 0.8
            }
        ]
        
        return simulated_news[:limit]
    
    def _get_simulated_market_news(self, limit: int) -> List[Dict[str, Any]]:
        """
        Gerar notícias de mercado simuladas
        """
        simulated_news = [
            {
                'title': 'S&P 500 fecha em alta com otimismo sobre resultados corporativos',
                'description': 'O índice S&P 500 subiu 0.8% com investidores otimistas sobre a temporada de resultados.',
                'content': 'Análise do fechamento dos mercados americanos...',
                'url': 'https://example.com/market/1',
                'source': 'CNBC',
                'author': 'Repórter de Mercados',
                'published_at': datetime.now().isoformat(),
                'category': 'market',
                'keywords': 'S&P 500, resultados, otimismo',
                'sentiment_score': 0.5,
                'sentiment_label': 'positive',
                'impact_score': 0.7,
                'relevance_score': 0.8
            },
            {
                'title': 'Volatilidade aumenta nos mercados asiáticos',
                'description': 'Mercados asiáticos mostram maior volatilidade em meio a incertezas geopolíticas.',
                'content': 'Análise da sessão asiática...',
                'url': 'https://example.com/market/2',
                'source': 'MarketWatch',
                'author': 'Correspondente Asiático',
                'published_at': (datetime.now() - timedelta(hours=6)).isoformat(),
                'category': 'market',
                'keywords': 'volatilidade, Ásia, geopolítica',
                'sentiment_score': -0.2,
                'sentiment_label': 'negative',
                'impact_score': 0.6,
                'relevance_score': 0.7
            }
        ]
        
        return simulated_news[:limit]
    
    def _get_simulated_economic_news(self, limit: int) -> List[Dict[str, Any]]:
        """
        Gerar notícias econômicas simuladas
        """
        simulated_news = [
            {
                'title': 'Inflação da Eurozona desacelera para 2.1% em novembro',
                'description': 'A inflação anual da Eurozona caiu para 2.1%, aproximando-se da meta do BCE de 2%.',
                'content': 'Análise dos dados de inflação europeus...',
                'url': 'https://example.com/economic/1',
                'source': 'Reuters',
                'author': 'Correspondente Econômico',
                'published_at': datetime.now().isoformat(),
                'category': 'economic',
                'keywords': 'inflação, Eurozona, BCE',
                'sentiment_score': 0.3,
                'sentiment_label': 'positive',
                'impact_score': 0.8,
                'relevance_score': 0.9
            }
        ]
        
        return simulated_news[:limit]
    
    def start_auto_update(self, interval_minutes: int = 15):
        """
        Iniciar atualização automática de notícias
        """
        if self.auto_update_running:
            self.logger.warning("⚠️ Atualização automática já está rodando")
            return
        
        self.auto_update_running = True
        
        def update_loop():
            while self.auto_update_running:
                try:
                    self.logger.info("🔄 Atualização automática de notícias...")
                    self.get_all_news()
                    time.sleep(interval_minutes * 60)
                except Exception as e:
                    self.logger.error(f"❌ Erro na atualização automática: {e}")
                    time.sleep(60)  # Esperar 1 minuto antes de tentar novamente
        
        self.auto_update_thread = threading.Thread(target=update_loop, daemon=True)
        self.auto_update_thread.start()
        
        self.logger.info(f"✅ Atualização automática iniciada (intervalo: {interval_minutes} min)")
    
    def stop_auto_update(self):
        """
        Parar atualização automática
        """
        self.auto_update_running = False
        if self.auto_update_thread:
            self.auto_update_thread.join(timeout=5)
        self.logger.info("🛑 Atualização automática parada")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obter estatísticas do gerenciador
        """
        return {
            'version': self.version,
            'api_key_configured': bool(self.api_key),
            'api_available': bool(self.api_key and REQUESTS_AVAILABLE),
            'cache_size': len(self.cache),
            'auto_update_running': self.auto_update_running,
            'stats': self.stats.copy()
        }
    
    def clear_cache(self):
        """
        Limpar cache de notícias
        """
        self.cache.clear()
        self.logger.info("🗑️ Cache de notícias limpo")
    
    def __del__(self):
        """
        Destrutor - parar threads
        """
        try:
            self.stop_auto_update()
        except:
            pass

# ═══════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ═══════════════════════════════════════════════════════════════════

def create_news_manager() -> NewsAPIManager:
    """
    Criar instância do gerenciador de notícias
    """
    return NewsAPIManager()

def get_latest_forex_news(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Obter últimas notícias Forex
    """
    manager = create_news_manager()
    return manager.fetch_forex_news(limit)

def get_latest_market_news(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Obter últimas notícias de mercado
    """
    manager = create_news_manager()
    return manager.fetch_market_news(limit)

# ═══════════════════════════════════════════════════════════════════
# TESTE E DEMONSTRAÇÃO
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        print("🗞️ Testando News API Manager v4.0 ULTRA CORRIGIDO")
        print("=" * 60)
        
        # Criar manager
        manager = NewsAPIManager()
        
        # Mostrar estatísticas
        stats = manager.get_stats()
        print(f"📊 Estatísticas:")
        print(f"   API Key: {'✅ Configurada' if stats['api_key_configured'] else '❌ Não configurada'}")
        print(f"   API Disponível: {'✅ Sim' if stats['api_available'] else '❌ Não'}")
        print(f"   Cache: {stats['cache_size']} itens")
        print()
        
        # Buscar notícias
        print("🔍 Buscando notícias Forex...")
        forex_news = manager.fetch_forex_news(5)
        
        print(f"✅ {len(forex_news)} notícias Forex encontradas:")
        for i, news in enumerate(forex_news[:3], 1):
            print(f"   {i}. {news['title'][:60]}...")
            print(f"      Fonte: {news['source']} | Sentimento: {news['sentiment_label']}")
        print()
        
        # Buscar todas as notícias
        print("🔍 Buscando todas as categorias...")
        all_news = manager.get_all_news(10)
        
        print(f"✅ Total de notícias por categoria:")
        for category, news_list in all_news.items():
            if category != 'combined':
                print(f"   {category.capitalize()}: {len(news_list)} notícias")
        print()
        
        # Mostrar estatísticas finais
        final_stats = manager.get_stats()
        print(f"📈 Estatísticas finais:")
        print(f"   Total buscado: {final_stats['stats']['total_fetched']}")
        print(f"   Total processado: {final_stats['stats']['total_processed']}")
        print(f"   Chamadas API hoje: {final_stats['stats']['api_calls_today']}")
        print(f"   Erros: {final_stats['stats']['errors_count']}")
        
        print("\n✅ Teste concluído com sucesso!")
        
    except KeyboardInterrupt:
        print("\n🛑 Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()

